package com.example.website.integration.local;

import org.springframework.stereotype.Component;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * 本机服务进程的启动与停止。
 *
 * <p>属于 integration/local 的进程层，只被 {@code LocalServicesManager} 调用。
 * 启动前校验项目目录与解释器可执行文件是否存在，把本可以变成无上下文 500 的
 * {@code ProcessBuilder} 失败提前转成可读的 503；子进程输出统一追加到项目目录的
 * {@code love530-service.log}，并注入 {@code PYTHONUTF8=1}、{@code PYTHONUNBUFFERED=1}
 * 规避 Windows 控制台编码问题并保证日志实时落盘。</p>
 *
 * <p>停止依赖 classpath 中的 {@code local-services/stop-service.ps1}：脚本会同时核对
 * Python 命令行里的项目路径、服务脚本与端口，只结束匹配的那一个进程；若端口被其它应用
 * 占用，脚本以非 0 退出，这里转成 409 并明确「未停止其他应用」。停止入口仅支持 Windows，
 * 单次停止最多等待 15 秒，超时后强制结束脚本进程。</p>
 */
@Component
public class LocalServiceProcessRunner {
    /**
     * 启动本机服务进程。
     *
     * @param directory 服务工作目录，同时决定日志文件位置
     * @param command   完整命令行，第一个元素必须是指向 Python 解释器的现存文件
     * @return 已启动的进程，调用方负责缓存并在停止时清理
     * @throws LocalServiceException 目录或解释器不存在、进程创建失败时抛出（HTTP 503）
     */
    public Process start(File directory, List<String> command) {
        if (!directory.isDirectory() || !new File(command.get(0)).isFile()) {
            throw new LocalServiceException(503, "本机项目目录或 Python 环境不存在，请检查本地服务配置");
        }
        try {
            ProcessBuilder builder = new ProcessBuilder(command).directory(directory);
            builder.environment().put("PYTHONUTF8", "1");
            builder.environment().put("PYTHONUNBUFFERED", "1");
            builder.redirectErrorStream(true);
            builder.redirectOutput(ProcessBuilder.Redirect.appendTo(new File(directory, "love530-service.log")));
            return builder.start();
        } catch (IOException exception) {
            throw new LocalServiceException(503, "本机服务启动失败，请检查 Python 环境和服务日志");
        }
    }

    /**
     * 调用 PowerShell 停止脚本结束本机服务。
     *
     * <p>脚本先从 classpath 复制到临时文件再执行，执行完立即删除；删除失败时改用
     * {@code deleteOnExit} 兜底，避免残留可执行脚本。</p>
     *
     * @param service   服务标识（strata、aimedia、h3），传给脚本作为匹配与日志依据
     * @param directory 服务项目根目录，脚本据此核对命令行
     * @param port      服务监听端口，脚本据此定位进程
     * @throws LocalServiceException 非 Windows 平台、脚本缺失、执行超时（503），
     *                               或进程不属于本项目、无法停止（409）时抛出
     */
    public void stop(String service, File directory, int port) {
        if (!System.getProperty("os.name").toLowerCase().contains("windows")) {
            throw new LocalServiceException(503, "本机停止入口目前仅支持 Windows");
        }
        Path script = null;
        try (InputStream input = getClass().getResourceAsStream("/local-services/stop-service.ps1")) {
            if (input == null) throw new IOException("Missing stop script");
            script = Files.createTempFile("love530-stop-", ".ps1");
            Files.copy(input, script, StandardCopyOption.REPLACE_EXISTING);
            Process process = new ProcessBuilder("powershell.exe", "-NoProfile", "-NonInteractive",
                    "-ExecutionPolicy", "Bypass", "-File", script.toString(), "-Service", service,
                    "-Root", directory.getCanonicalPath(), "-Port", String.valueOf(port))
                    .redirectOutput(new File("NUL"))
                    .redirectError(new File("NUL")).start();
            if (!process.waitFor(15, TimeUnit.SECONDS)) {
                process.destroyForcibly();
                throw new LocalServiceException(503, "停止服务超时，请检查本机进程");
            }
            if (process.exitValue() != 0) {
                throw new LocalServiceException(409, "端口上的进程不属于配置的项目，或进程无法停止；未停止其他应用");
            }
        } catch (IOException exception) {
            throw new LocalServiceException(503, "停止本机服务失败");
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new LocalServiceException(503, "停止服务被中断");
        } finally {
            if (script != null) {
                try { Files.deleteIfExists(script); } catch (IOException ignored) { script.toFile().deleteOnExit(); }
            }
        }
    }
}
