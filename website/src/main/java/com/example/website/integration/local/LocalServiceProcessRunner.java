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

@Component
public class LocalServiceProcessRunner {
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
