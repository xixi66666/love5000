package com.example.imagetemplate.service;

import com.example.imagetemplate.dto.ImageGenerationRequest;
import com.example.imagetemplate.dto.ImageGenerationResponse;
import com.example.imagetemplate.dto.PromptRenderRequest;
import org.springframework.core.env.Environment;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestTemplate;

import java.net.InetSocketAddress;
import java.net.Proxy;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Service
public class OpenAiImageGenerationService {

    private final ImagePromptTemplateService imagePromptTemplateService;

    private final RestTemplate restTemplate;

    private final String apiKey;

    private final String baseUrl;

    private final String imageModel;

    public OpenAiImageGenerationService(ImagePromptTemplateService imagePromptTemplateService, Environment environment) {
        this.imagePromptTemplateService = imagePromptTemplateService;
        this.apiKey = environment.getProperty("openai.api-key", "");
        this.baseUrl = environment.getProperty("openai.base-url", "https://api.openai.com/v1");
        this.imageModel = environment.getProperty("openai.image-model", "gpt-image-2");

        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(readInt(environment, "openai.connect-timeout-ms", 30000));
        requestFactory.setReadTimeout(readInt(environment, "openai.read-timeout-ms", 180000));
        configureProxy(requestFactory, environment);
        this.restTemplate = new RestTemplate(requestFactory);
    }

    public ImageGenerationResponse generate(String templateId, ImageGenerationRequest request) {
        return generate(templateId, request, null);
    }

    public ImageGenerationResponse generate(String templateId, ImageGenerationRequest request, String userApiKey) {
        String effectiveApiKey = resolveApiKey(userApiKey);
        ImageGenerationRequest generationRequest = request == null ? new ImageGenerationRequest() : request;
        String prompt = resolvePrompt(templateId, generationRequest);
        String outputFormat = normalizeOption(generationRequest.getOutputFormat(), "png");
        String mimeType = mimeType(outputFormat);

        Map<String, Object> requestBody = new HashMap<String, Object>();
        requestBody.put("model", imageModel);
        requestBody.put("prompt", prompt);
        requestBody.put("size", normalizeOption(generationRequest.getSize(), "1024x1024"));
        requestBody.put("quality", normalizeOption(generationRequest.getQuality(), "low"));
        requestBody.put("output_format", outputFormat);
        requestBody.put("background", normalizeOption(generationRequest.getBackground(), "auto"));

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(effectiveApiKey);
        headers.setContentType(MediaType.APPLICATION_JSON);

        try {
            ResponseEntity<Map> response = restTemplate.exchange(
                    cleanBaseUrl() + "/images/generations",
                    HttpMethod.POST,
                    new HttpEntity<Map<String, Object>>(requestBody, headers),
                    Map.class);
            return toGenerationResponse(templateId, prompt, outputFormat, mimeType, response.getBody());
        } catch (HttpStatusCodeException exception) {
            throw new ImageGenerationException("OpenAI image generation failed: " + exception.getResponseBodyAsString(), exception);
        } catch (ResourceAccessException exception) {
            throw new ImageGenerationException("Cannot connect to OpenAI image API. Check network access, OPENAI_BASE_URL, or OPENAI_PROXY_HOST/OPENAI_PROXY_PORT. Detail: " + exception.getMessage(), exception);
        } catch (RuntimeException exception) {
            throw new ImageGenerationException("OpenAI image generation failed: " + exception.getMessage(), exception);
        }
    }

    private String resolvePrompt(String templateId, ImageGenerationRequest request) {
        if (hasText(request.getPrompt())) {
            return request.getPrompt().trim();
        }
        PromptRenderRequest promptRequest = new PromptRenderRequest();
        promptRequest.setVariables(request.getVariables());
        promptRequest.setExtraInstruction(request.getExtraInstruction());
        return imagePromptTemplateService.renderPrompt(templateId, promptRequest);
    }

    @SuppressWarnings("unchecked")
    private ImageGenerationResponse toGenerationResponse(String templateId,
                                                         String prompt,
                                                         String outputFormat,
                                                         String mimeType,
                                                         Map<String, Object> responseBody) {
        if (responseBody == null) {
            throw new ImageGenerationException("OpenAI image generation failed: empty response");
        }
        Object dataObject = responseBody.get("data");
        if (!(dataObject instanceof List) || ((List<?>) dataObject).isEmpty()) {
            throw new ImageGenerationException("OpenAI image generation failed: response contains no image data");
        }
        Object firstObject = ((List<?>) dataObject).get(0);
        if (!(firstObject instanceof Map)) {
            throw new ImageGenerationException("OpenAI image generation failed: invalid image payload");
        }
        Map<String, Object> firstImage = (Map<String, Object>) firstObject;
        Object imageBase64Object = firstImage.get("b64_json");
        if (!(imageBase64Object instanceof String) || !hasText((String) imageBase64Object)) {
            throw new ImageGenerationException("OpenAI image generation failed: missing b64_json image data");
        }
        String imageBase64 = ((String) imageBase64Object).trim();

        ImageGenerationResponse response = new ImageGenerationResponse();
        response.setSuccess(true);
        response.setTemplateId(templateId);
        response.setModel(imageModel);
        response.setPrompt(prompt);
        response.setOutputFormat(outputFormat);
        response.setMimeType(mimeType);
        response.setImageBase64(imageBase64);
        response.setDataUrl("data:" + mimeType + ";base64," + imageBase64);
        Object usage = responseBody.get("usage");
        if (usage instanceof Map) {
            response.setUsage((Map<String, Object>) usage);
        }
        return response;
    }

    private String resolveApiKey(String userApiKey) {
        if (hasText(userApiKey)) {
            return userApiKey.trim();
        }
        if (hasText(apiKey)) {
            return apiKey.trim();
        }
        throw new ImageGenerationException("No OpenAI API key is available. Enter your API key on the page or set OPENAI_API_KEY before starting imagetemplate.");
    }

    private String cleanBaseUrl() {
        String value = hasText(baseUrl) ? baseUrl.trim() : "https://api.openai.com/v1";
        while (value.endsWith("/")) {
            value = value.substring(0, value.length() - 1);
        }
        return value;
    }

    private void configureProxy(SimpleClientHttpRequestFactory requestFactory, Environment environment) {
        String proxyHost = environment.getProperty("openai.proxy.host", "");
        int proxyPort = readInt(environment, "openai.proxy.port", 0);
        if (!hasText(proxyHost) || proxyPort <= 0) {
            return;
        }
        String proxyType = environment.getProperty("openai.proxy.type", "HTTP");
        Proxy.Type type = "SOCKS".equalsIgnoreCase(proxyType) ? Proxy.Type.SOCKS : Proxy.Type.HTTP;
        requestFactory.setProxy(new Proxy(type, new InetSocketAddress(proxyHost.trim(), proxyPort)));
    }

    private int readInt(Environment environment, String name, int fallback) {
        String value = environment.getProperty(name);
        if (!hasText(value)) {
            return fallback;
        }
        try {
            return Integer.parseInt(value.trim());
        } catch (NumberFormatException exception) {
            return fallback;
        }
    }

    private String normalizeOption(String value, String fallback) {
        return hasText(value) ? value.trim().toLowerCase(Locale.ROOT) : fallback;
    }

    private String mimeType(String outputFormat) {
        if ("jpeg".equals(outputFormat) || "jpg".equals(outputFormat)) {
            return "image/jpeg";
        }
        if ("webp".equals(outputFormat)) {
            return "image/webp";
        }
        return "image/png";
    }

    private boolean hasText(String value) {
        return value != null && !value.trim().isEmpty();
    }
}
