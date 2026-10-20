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

    JsonNode probe(String service) {
        JsonNode value = client.get(port(service), "strata".equals(service) ? "/health"
                : "aimedia".equals(service) ? "/api/status" : "/system_stats");
        if (value == null) return null;
        boolean valid = "strata".equals(service) ? "strata".equals(value.path("service").asText())
                : "aimedia".equals(service) ? "AIMedia Studio".equals(value.path("app").asText())
                : value.has("system") && value.has("devices");
        return valid ? value : null;
    }

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

    private boolean h3Installed() {
        File models = new File(properties.getAimediaDir(), "ComfyUI/models");
        for (String file : Arrays.asList("diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors",
                "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
                "vae/minimax_h3_video_vae_fp16.safetensors", "vae/minimax_h3_audio_vae_fp32.safetensors")) {
            if (!new File(models, file).isFile()) return false;
        }
        return true;
    }

    private File directory(String service) {
        return new File("strata".equals(service) ? properties.getStrataDir() : properties.getAimediaDir());
    }

    private File workDirectory(String service) {
        return "h3".equals(service) ? new File(directory(service), "ComfyUI") : directory(service);
    }

    private int timeoutMs() { return properties.getStartupTimeoutSeconds() * 1000; }

    private int port(String service) {
        if ("strata".equals(service)) return properties.getStrataPort();
        if ("aimedia".equals(service)) return properties.getStudioPort();
        if ("h3".equals(service)) return properties.getH3Port();
        throw new LocalServiceException(404, "未知的本机服务");
    }
}
