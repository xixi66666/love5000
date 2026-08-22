package com.example.website.integration.health;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;
import java.net.ConnectException;
import java.net.HttpURLConnection;
import java.net.SocketTimeoutException;
import java.net.URL;
import java.util.concurrent.TimeUnit;

@Component
public class ServiceHealthChecker {

    interface Sleeper {
        void sleep(long millis) throws InterruptedException;
    }

    private final ObjectMapper objectMapper;
    private final ServiceHealthProperties properties;
    private final Sleeper sleeper;

    @Autowired
    public ServiceHealthChecker(ObjectMapper objectMapper, ServiceHealthProperties properties) {
        this(objectMapper, properties, Thread::sleep);
    }

    ServiceHealthChecker(ObjectMapper objectMapper,
                         ServiceHealthProperties properties,
                         Sleeper sleeper) {
        this.objectMapper = objectMapper;
        this.properties = properties;
        this.sleeper = sleeper;
    }

    public ServiceHealthResult check(ServiceHealthDefinition definition) {
        long startedAt = System.nanoTime();
        HttpURLConnection connection = null;
        Integer statusCode = null;
        try {
            connection = (HttpURLConnection) new URL(definition.getUrl()).openConnection();
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(properties.getConnectTimeoutMs());
            connection.setReadTimeout(properties.getReadTimeoutMs());
            connection.setUseCaches(false);

            statusCode = connection.getResponseCode();
            if (statusCode < 200 || statusCode >= 300) {
                return ServiceHealthResult.unhealthy(
                        definition, statusCode, elapsedMillis(startedAt), "HTTP " + statusCode);
            }

            try (InputStream body = connection.getInputStream()) {
                JsonNode root = objectMapper.readTree(body);
                JsonNode success = root == null ? null : root.get("success");
                if (success == null || !success.isBoolean() || !success.booleanValue()) {
                    return invalidResponse(definition, statusCode, startedAt);
                }
            } catch (JsonProcessingException e) {
                return invalidResponse(definition, statusCode, startedAt);
            }

            return ServiceHealthResult.healthy(definition, statusCode, elapsedMillis(startedAt));
        } catch (SocketTimeoutException e) {
            return ServiceHealthResult.unhealthy(
                    definition, statusCode, elapsedMillis(startedAt), "Timed out");
        } catch (ConnectException e) {
            return ServiceHealthResult.unhealthy(
                    definition, statusCode, elapsedMillis(startedAt), "Connection failed");
        } catch (IOException e) {
            return ServiceHealthResult.unhealthy(
                    definition, statusCode, elapsedMillis(startedAt), "Connection failed");
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    public boolean waitUntilHealthy(ServiceHealthDefinition definition, int timeoutSeconds) {
        int attempts = Math.max(1, timeoutSeconds);
        for (int attempt = 0; attempt < attempts; attempt++) {
            if (check(definition).isHealthy()) {
                return true;
            }
            if (attempt + 1 >= attempts) {
                break;
            }
            try {
                sleeper.sleep(1000L);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return false;
            }
        }
        return false;
    }

    public String buildLocalUrl(int port, String healthPath) {
        String normalizedPath = healthPath.startsWith("/") ? healthPath : "/" + healthPath;
        return "http://127.0.0.1:" + port + normalizedPath;
    }

    private ServiceHealthResult invalidResponse(ServiceHealthDefinition definition,
                                                Integer statusCode,
                                                long startedAt) {
        return ServiceHealthResult.unhealthy(
                definition, statusCode, elapsedMillis(startedAt), "Invalid health response");
    }

    private long elapsedMillis(long startedAt) {
        return TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - startedAt);
    }
}
