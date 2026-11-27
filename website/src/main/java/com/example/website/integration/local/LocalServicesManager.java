package com.example.website.integration.local;

import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.io.File;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * Strata、AIMedia、H3 三个本机服务的管理编排。
 *
 * <p>属于 integration/local 的服务层，组合 {@link LocalServiceClient}（HTTP）、
 * {@link LocalServiceProcessRunner}（进程）与 {@link LocalServiceProperties}
 * （目录、端口、等待时长），对外只暴露 {@link #status(String)} 与
 * {@link #action(String, String)}。操作范围固定为这三个服务：端口与命令行由本类拼装，
 * 不接受浏览器传入的命令、PID 或路径。</p>
 *
 * <p>关键约束：</p>
 * <ul>
 *   <li>只有 Strata 支持 {@code load}，AIMedia 不支持 {@code unload}，其余组合一律 400。</li>
 *   <li>停止或释放前先确认空闲：H3 检查 ComfyUI 队列，AIMedia 检查操作台作业；
 *       忙碌返回 409，无法确认队列则返回 503 并拒绝操作。</li>
 *   <li>启动时先探测，已在线直接复用；拉起后按 300 毫秒轮询，最多等待
 *       {@code startup-timeout-seconds}（默认 180 秒），超时后不会重复拉起进程。</li>
 *   <li>{@code action} 是同步方法，同一时刻只允许一个启停操作，避免并发重复派生进程；
 *       已派生的进程缓存在 {@code processes} 中，供停止时清理。</li>
 * </ul>
 */
@Component
public class LocalServicesManager {
    private static final Logger log = LoggerFactory.getLogger(LocalServicesManager.class);
    private final LocalServiceProperties properties;
    private final LocalServiceClient client;
    private final LocalServiceProcessRunner runner;
    private final Map<String, Process> processes = new HashMap<>();

    public LocalServicesManager(LocalServiceProperties properties, LocalServiceClient client,
                                LocalServiceProcessRunner runner) {
        this.properties = properties;
        this.client = client;
        this.runner = runner;
    }

    /**
     * 读取单个本机服务的状态。
     *
     * @param service 服务标识：strata、aimedia 或 h3
     * @return 固定字段的状态表：{@code success} 恒为 true，{@code running} 表示探测通过，
     *         {@code url} 为服务首页地址；{@code loaded} 仅 Strata 有值；{@code modelState}
     *         对 H3 固定为 {@code on-demand}，因为引擎在线不代表权重已加载；
     *         {@code installed} 表示 H3 的四个模型文件是否齐全
     * @throws LocalServiceException 服务标识未知时抛出 404
     */
    public Map<String, Object> status(String service) {
        int port = port(service);
        JsonNode remote = probe(service);
        log.info("[健康检查][项目={}] 本机服务状态={}", service, remote != null ? "在线" : "离线");
        Map<String, Object> state = new LinkedHashMap<>();
        state.put("success", true);
        state.put("service", service);
        state.put("running", remote != null);
        state.put("url", "http://127.0.0.1:" + port + "/");
        state.put("loaded", "strata".equals(service) && remote != null ? remote.path("loaded").asBoolean() : null);
        state.put("modelState", "h3".equals(service) ? "on-demand" : null);
        if ("h3".equals(service)) state.put("installed", h3Installed());
        return state;
    }

    /**
     * 执行本机服务的启停与模型加载、释放操作。
     *
     * <p>先做能力矩阵校验，再按操作分派：{@code start} 拉起服务；{@code load} 拉起后调用
     * Strata 的 {@code /load}；{@code unload} 与 {@code stop} 在服务在线时先确认空闲，
     * 再调用 {@code /unload}（Strata）或 {@code /free}（H3），{@code stop} 最后执行停止脚本。
     * AIMedia 的停止直接校验操作台是否空闲。返回的是操作后的最新状态，便于前端立即刷新。</p>
     *
     * @param service 服务标识
     * @param action  操作名，仅支持 start、load、unload、stop
     * @return 操作后的状态，并附带 {@code action} 与结果 {@code message}
     * @throws LocalServiceException 服务标识未知（404）、操作不受支持（400）、
     *                               任务忙碌（409）、无法确认状态或执行失败（503）时抛出
     */
    public synchronized Map<String, Object> action(String service, String action) {
        port(service);
        if (!Arrays.asList("start", "load", "unload", "stop").contains(action)
                || (!"strata".equals(service) && "load".equals(action))
                || ("aimedia".equals(service) && "unload".equals(action))) {
            throw new LocalServiceException(400, "该服务不支持此操作");
        }
        if ("start".equals(action) || "load".equals(action)) {
            start(service);
            if ("load".equals(action)) client.post(port(service), "/load", "{}", timeoutMs());
        } else {
            if ("aimedia".equals(service)) {
                assertStudioIdle();
            } else if (probe(service) != null) {
                if ("h3".equals(service)) assertVideoIdle();
                client.post(port(service), "strata".equals(service) ? "/unload" : "/free",
                        "strata".equals(service) ? "{}" : "{\"unload_models\":true,\"free_memory\":true}", timeoutMs());
            }
            if ("stop".equals(action)) {
                runner.stop(service, directory(service), port(service));
                processes.remove(service);
            }
        }
        Map<String, Object> result = status(service);
        result.put("action", action);
        result.put("message", "h3".equals(service) && "unload".equals(action)
                ? "已提交模型释放请求，引擎继续在线" : "操作完成");
        return result;
    }

    /**
     * 拉起服务并等待其可用。
     *
     * <p>先探测一次，已在线直接复用，避免重复派生进程；进程缓存里已有存活进程时同样复用。
     * 随后按 300 毫秒轮询，直到探测通过、进程退出或超过等待时长。超过等待时长不算失败，
     * 只返回 503 提示稍后刷新状态，并且不会再次启动新进程。</p>
     *
     * @param service 服务标识
     * @throws LocalServiceException 进程启动失败、等待被中断或等待超时时抛出
     */
    private void start(String service) {
        if (probe(service) != null) return;
        Process existing = processes.get(service);
        if (existing == null || !existing.isAlive()) {
            processes.put(service, runner.start(workDirectory(service), command(service)));
        }
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(properties.getStartupTimeoutSeconds());
        while (System.nanoTime() < deadline) {
            if (probe(service) != null) return;
            if (!processes.get(service).isAlive()) {
                throw new LocalServiceException(503, "服务启动失败，请检查项目目录内的 love530-service.log");
            }
            try { Thread.sleep(300); } catch (InterruptedException exception) {
                Thread.currentThread().interrupt();
                throw new LocalServiceException(503, "服务启动被中断");
            }
        }
        throw new LocalServiceException(503, "服务仍在启动，请稍后刷新状态；不会重复启动进程");
    }

    /**
     * 探测服务是否在线，并按各自协议校验响应特征。
     *
     * <p>三个服务没有统一健康协议，因此分别读取 Strata 的 {@code /health}（要求
     * {@code service=strata}）、AIMedia 的 {@code /api/status}（要求
     * {@code app=AIMedia Studio}）与 ComfyUI 的 {@code /system_stats}（要求同时含
     * {@code system} 与 {@code devices}）。端口被其它应用占用时会因字段不匹配而判为离线，
     * 避免把别人的服务误认成自己的。</p>
     *
     * @param service 服务标识
     * @return 原始响应；离线、超时或字段不匹配时返回 {@code null}
     */
    JsonNode probe(String service) {
        JsonNode value = client.get(port(service), "strata".equals(service) ? "/health"
                : "aimedia".equals(service) ? "/api/status" : "/system_stats");
        if (value == null) return null;
        boolean valid = "strata".equals(service) ? "strata".equals(value.path("service").asText())
                : "aimedia".equals(service) ? "AIMedia Studio".equals(value.path("app").asText())
                : value.has("system") && value.has("devices");
        return valid ? value : null;
    }

    /**
     * 停止或释放 H3 前确认没有视频任务在跑。
     *
     * <p>先读 ComfyUI 的 {@code /queue}：响应缺失或缺少 {@code queue_running}、
     * {@code queue_pending} 数组时无法判断，直接拒绝操作；存在运行中或排队任务时返回 409。
     * 队列空闲后还要确认 AIMedia 操作台没有作业，避免操作台已提交、引擎尚未入队的空窗期。</p>
     *
     * @throws LocalServiceException 无法确认队列（503）或仍有任务（409）时抛出
     */
    private void assertVideoIdle() {
        JsonNode queue = client.get(properties.getH3Port(), "/queue");
        if (queue == null || !queue.path("queue_running").isArray() || !queue.path("queue_pending").isArray()) {
            throw new LocalServiceException(503, "无法确认视频任务状态，未释放或停止引擎");
        }
        if (queue.path("queue_running").size() > 0 || queue.path("queue_pending").size() > 0) {
            throw new LocalServiceException(409, "视频正在生成或排队，请先在视频操作台完成或停止任务");
        }
        assertStudioIdle();
    }

    /**
     * 确认 AIMedia 操作台当前没有运行中、排队中或正在停止的作业。
     *
     * <p>操作台不在线时视为空闲直接返回；在线但拿不到作业数组时拒绝操作（503）。
     * 这里只读取作业状态字段，不终止任何任务。</p>
     *
     * @throws LocalServiceException 无法确认作业列表（503）或存在活动作业（409）时抛出
     */
    private void assertStudioIdle() {
        if (probe("aimedia") == null) return;
        JsonNode response = client.get(properties.getStudioPort(), "/api/jobs");
        JsonNode jobs = response != null && response.isArray() ? response : response == null ? null : response.get("jobs");
        if (jobs == null || !jobs.isArray()) throw new LocalServiceException(503, "无法确认操作台任务状态，未停止服务");
        for (JsonNode job : jobs) {
            if (Arrays.asList("running", "queued", "stopping").contains(job.path("status").asText())) {
                throw new LocalServiceException(409, "操作台仍有任务，请先完成或停止任务");
            }
        }
    }

    /**
     * 拼装各服务的启动命令行。
     *
     * <p>解释器固定使用项目内虚拟环境：Strata 为 {@code .venv/Scripts/python.exe}，
     * H3 为 {@code ComfyUI/.venv-rocm/Scripts/python.exe}；AIMedia 额外加 {@code -I}
     * 以隔离用户级 site-packages。Strata 以 {@code --engine strata --lazy} 启动，权重留到
     * 首次生成或手动加载；H3 以 {@code --listen 127.0.0.1 --reserve-vram 3} 启动，
     * 只监听回环地址；端口统一追加在末尾。</p>
     *
     * @param service 服务标识
     * @return 完整命令行；包内可见，便于测试直接断言参数顺序
     */
    List<String> command(String service) {
        File root = directory(service);
        List<String> command = new ArrayList<>();
        command.add(new File(root, "strata".equals(service) ? ".venv/Scripts/python.exe"
                : "ComfyUI/.venv-rocm/Scripts/python.exe").getAbsolutePath());
        if ("aimedia".equals(service)) command.add("-I");
        command.add("-u");
        command.add(new File(root, "strata".equals(service) ? "serve/server.py"
                : "aimedia".equals(service) ? "services/studio/server.py" : "ComfyUI/main.py").getAbsolutePath());
        if ("strata".equals(service)) {
            command.addAll(Arrays.asList("--engine", "strata", "--config", new File(root, "strata-iq3_s.json").getAbsolutePath(),
                    "--host", "127.0.0.1", "--lazy"));
        } else if ("h3".equals(service)) {
            command.addAll(Arrays.asList("--listen", "127.0.0.1", "--reserve-vram", "3",
                    "--database-url", "sqlite:///user/comfyui-gpu.db"));
        }
        command.addAll(Arrays.asList("--port", String.valueOf(port(service))));
        return command;
    }

    /**
     * 检查 H3 依赖的四个模型文件是否齐全。
     *
     * <p>只判断文件是否存在，不校验大小或完整性；缺任何一个即视为未安装，
     * 避免页面把「引擎在线」误报成「模型可用」。</p>
     *
     * @return 四个权重文件都存在时为 {@code true}
     */
    private boolean h3Installed() {
        File models = new File(properties.getAimediaDir(), "ComfyUI/models");
        for (String file : Arrays.asList("diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors",
                "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
                "vae/minimax_h3_video_vae_fp16.safetensors", "vae/minimax_h3_audio_vae_fp32.safetensors")) {
            if (!new File(models, file).isFile()) return false;
        }
        return true;
    }

    /**
     * 取服务对应的项目根目录：Strata 使用自身目录，AIMedia 与 H3 都从 AIMedia 目录派生。
     *
     * @param service 服务标识
     * @return 项目根目录，不保证存在
     */
    private File directory(String service) {
        return new File("strata".equals(service) ? properties.getStrataDir() : properties.getAimediaDir());
    }

    /**
     * 取服务的工作目录。
     *
     * <p>H3 的进程需要以 {@code ComfyUI} 子目录为基准启动，其余服务直接用项目根目录；
     * 子进程日志文件也写在这个目录下。</p>
     *
     * @param service 服务标识
     * @return 子进程工作目录
     */
    private File workDirectory(String service) {
        return "h3".equals(service) ? new File(directory(service), "ComfyUI") : directory(service);
    }

    /**
     * 长耗时操作的读取超时，复用启动等待时长（默认 180 秒），
     * 供加载、卸载模型这类可能持续数分钟的本机调用使用。
     *
     * @return 超时毫秒数
     */
    private int timeoutMs() { return properties.getStartupTimeoutSeconds() * 1000; }

    /**
     * 取服务监听端口。
     *
     * @param service 服务标识
     * @return 配置中的端口
     * @throws LocalServiceException 服务标识未知时抛出 404
     */
    private int port(String service) {
        if ("strata".equals(service)) return properties.getStrataPort();
        if ("aimedia".equals(service)) return properties.getStudioPort();
        if ("h3".equals(service)) return properties.getH3Port();
        throw new LocalServiceException(404, "未知的本机服务");
    }
}
