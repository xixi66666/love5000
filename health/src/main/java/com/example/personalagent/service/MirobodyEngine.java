package com.example.personalagent.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.stereotype.Service;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

import static com.example.personalagent.Api.map;

/** 调用本地 Mirobody 子进程，协议仅传数据，原件和诊断信息均不进入命令行或日志。 */
@Service
public class MirobodyEngine {
    private static final int MAX_RESPONSE = 2 * 1024 * 1024;
    private final ObjectMapper json;
    private final Path directory;
    private final Path python;
    private final Semaphore slots = new Semaphore(2);
    private final Map<List<String>,JsonNode> codes = new LinkedHashMap<List<String>,JsonNode>(64, 0.75f, true) {
        @Override protected boolean removeEldestEntry(Map.Entry<List<String>,JsonNode> oldest) { return size() > 4096; }
    };

    public MirobodyEngine(ObjectMapper json) {
        this.json = json;
        directory = engineDirectory();
        python = directory.resolve(windows() ? ".venv/Scripts/python.exe" : ".venv/bin/python");
    }

    public boolean available() {
        if (!Files.isRegularFile(python) || !Files.isRegularFile(directory.resolve("engine.py"))) return false;
        Path environment = directory.resolve(".venv");
        if (windows()) return installed(environment.resolve("Lib/site-packages"));
        try (DirectoryStream<Path> versions = Files.newDirectoryStream(environment.resolve("lib"), "python*")) {
            for (Path version : versions) if (installed(version.resolve("site-packages"))) return true;
        } catch (IOException unavailable) { return false; }
        return false;
    }

    public JsonNode parse(byte[] bytes, String extension) throws IOException {
        return call(map("operation","parse","extension",extension,"bytes",bytes),60);
    }

    public JsonNode parseTranscripts(List<String> transcripts) throws IOException {
        return call(map("operation","parse","transcripts",transcripts),60);
    }

    public void annotate(List<JsonNode> reports) {
        if (!available()) return;
        Map<List<String>,List<ObjectNode>> targets = new LinkedHashMap<>();
        for (JsonNode report : reports) {
            if (!report.path("textEvidenceVerified").asBoolean()) continue;
            for (JsonNode metric : report.path("metrics")) {
                if (!metric.isObject()) continue;
                List<String> key = Arrays.asList(metric.path("name").asText(),metric.path("value").asText(),metric.path("unit").asText());
                if (key.get(0).isEmpty() || key.stream().anyMatch(value -> value.length() > 100)) continue;
                String quote = metric.path("quote").asText();
                if (!key.stream().allMatch(quote::contains)) continue;
                targets.computeIfAbsent(key, ignored -> new ArrayList<>()).add((ObjectNode) metric);
            }
        }
        List<List<String>> missing = new ArrayList<>();
        synchronized (codes) {
            targets.forEach((key,rows) -> {
                JsonNode code = codes.get(key);
                if (code == null) missing.add(key);
                else rows.forEach(row -> row.set("standardization",code));
            });
        }
        for (int start = 0; start < missing.size(); start += 1000) {
            List<List<String>> batch = missing.subList(start, Math.min(start + 1000, missing.size()));
            List<Map<String,Object>> inputs = new ArrayList<>();
            batch.forEach(key -> inputs.add(map("name",key.get(0),"value",key.get(1),"unit",key.get(2))));
            try {
                JsonNode results = call(map("operation","normalize","rows",inputs),20);
                if (!results.isArray() || results.size() != batch.size()) return;
                synchronized (codes) {
                    for (int i = 0; i < batch.size(); i++) {
                        JsonNode code = results.get(i);
                        List<String> key = batch.get(i);
                        if (!code.isObject()) continue;
                        codes.put(key,code);
                        targets.get(key).forEach(row -> row.set("standardization",code));
                    }
                }
            } catch (IOException unavailable) { return; }
        }
    }

    private JsonNode call(Map<String,Object> request, long seconds) throws IOException {
        if (!available() || !slots.tryAcquire()) throw new IOException("Mirobody unavailable");
        Process process = null;
        try {
            ProcessBuilder builder = new ProcessBuilder(python.toString(),"-I","-B","-X","utf8","engine.py");
            builder.directory(directory.toFile());
            builder.redirectError(ProcessBuilder.Redirect.to(new File(windows() ? "NUL" : "/dev/null")));
            builder.environment().keySet().removeIf(key -> key.endsWith("_API_KEY") || key.endsWith("_TOKEN"));
            process = builder.start();
            Process child = process;
            FutureTask<JsonNode> exchange = new FutureTask<>(() -> exchange(child,request));
            Thread io = new Thread(exchange,"exam-engine-io");
            io.setDaemon(true);
            io.start();
            return exchange.get(seconds,TimeUnit.SECONDS);
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            throw new IOException("Mirobody interrupted");
        } catch (ExecutionException | TimeoutException failed) {
            throw new IOException("Mirobody failed");
        } finally {
            if (process != null && process.isAlive()) process.destroyForcibly();
            slots.release();
        }
    }

    private JsonNode exchange(Process process, Map<String,Object> request) throws IOException, InterruptedException {
        try (OutputStream input = process.getOutputStream()) { json.writeValue(input,request); }
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        try (InputStream stream = process.getInputStream()) {
            byte[] buffer = new byte[8192];
            for (int length; (length = stream.read(buffer)) != -1;) {
                if (output.size() + length > MAX_RESPONSE) throw new IOException("Mirobody response limit");
                output.write(buffer,0,length);
            }
        }
        JsonNode answer = json.readTree(output.toByteArray());
        if (process.waitFor() != 0 || answer == null || !answer.path("ok").asBoolean()) throw new IOException("Mirobody failed");
        return answer.path("data");
    }

    private static boolean installed(Path packages) {
        return Files.isRegularFile(packages.resolve("mirobody/__init__.py"))
            && Files.isRegularFile(packages.resolve("pypdfium2/__init__.py"));
    }

    private static Path engineDirectory() {
        Path cwd = Paths.get("").toAbsolutePath();
        for (Path current = cwd; current != null; current = current.getParent()) {
            for (Path candidate : Arrays.asList(current.resolve("exam-engine"), current.resolve("health/exam-engine"))) {
                if (Files.isRegularFile(candidate.resolve("engine.py"))) return candidate;
            }
        }
        return cwd.resolve("exam-engine");
    }

    private static boolean windows() { return System.getProperty("os.name", "").startsWith("Windows"); }
}
