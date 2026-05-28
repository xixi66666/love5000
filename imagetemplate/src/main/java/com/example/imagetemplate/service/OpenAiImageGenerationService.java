package com.example.imagetemplate.service;

import com.example.imagetemplate.dto.ImageGenerationRequest;
import com.example.imagetemplate.dto.ImageGenerationResponse;
import com.example.imagetemplate.dto.PromptRenderRequest;
import com.example.imagetemplate.dto.ReferenceImageInput;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.env.Environment;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
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

    private static final Logger LOGGER = LoggerFactory.getLogger(OpenAiImageGenerationService.class);

    private static final int MAX_REFERENCE_IMAGES = 16;

    private static final long MAX_REFERENCE_IMAGE_BYTES = 50L * 1024L * 1024L;

    private static final String DEFAULT_IMAGE_SIZE = "1024x1024";

    private static final int MAX_IMAGE_SIDE = 3840;

    private static final int MIN_IMAGE_PIXELS = 655360;

    private static final int MAX_IMAGE_PIXELS = 8294400;

    private final ImagePromptTemplateService imagePromptTemplateService;

    private final RestTemplate restTemplate;

    private final String apiKey;

    private final String baseUrl;

    private final String imageModel;

    public OpenAiImageGenerationService(ImagePromptTemplateService imagePromptTemplateService, Environment environment) {
        this.imagePromptTemplateService = imagePromptTemplateService;
        this.apiKey = environment.getProperty("openai.api-key", "");
        this.baseUrl = environment.getProperty("openai.base-url", "https://nimabo.cn/v1");
        this.imageModel = environment.getProperty("openai.image-model", "gpt-image-2");

        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(readInt(environment, "openai.connect-timeout-ms", 300000));
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
        String imageSize = normalizeImageSize(generationRequest.getSize());
        String prompt = resolvePrompt(templateId, generationRequest);
        String outputFormat = normalizeOption(generationRequest.getOutputFormat(), "png");
        String mimeType = mimeType(outputFormat);
        List<ReferenceImageInput> referenceImages = validateReferenceImages(generationRequest.getReferenceImages());

        if (!referenceImages.isEmpty()) {
            LOGGER.info("Generating image with references. templateId={}, model={}, endpoint={}, size={}, quality={}, outputFormat={}, background={}, referenceImageCount={}",
                    templateId,
                    imageModel,
                    "/images/edits",
                    imageSize,
                    normalizeOption(generationRequest.getQuality(), "low"),
                    outputFormat,
                    normalizeOption(generationRequest.getBackground(), "auto"),
                    referenceImages.size());
            return generateFromReferenceImages(templateId, prompt, generationRequest, referenceImages, outputFormat, mimeType, imageSize, effectiveApiKey);
        }

        LOGGER.info("Generating image. templateId={}, model={}, endpoint={}, size={}, quality={}, outputFormat={}, background={}",
                templateId,
                imageModel,
                "/images/generations",
                imageSize,
                normalizeOption(generationRequest.getQuality(), "low"),
                outputFormat,
                normalizeOption(generationRequest.getBackground(), "auto"));

        Map<String, Object> requestBody = new HashMap<String, Object>();
        requestBody.put("model", imageModel);
        requestBody.put("prompt", prompt);
        requestBody.put("size", imageSize);
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
            logOpenAiHttpError("generation", templateId, "/images/generations", exception);
            throw new ImageGenerationException("OpenAI image generation failed: " + readableResponseBody(exception), exception);
        } catch (ResourceAccessException exception) {
            LOGGER.error("OpenAI image generation connection failed. templateId={}, endpoint={}, baseUrl={}, message={}",
                    templateId, "/images/generations", cleanBaseUrl(), exception.getMessage(), exception);
            throw new ImageGenerationException("Cannot connect to OpenAI image API. Check network access, OPENAI_BASE_URL, or OPENAI_PROXY_HOST/OPENAI_PROXY_PORT. Detail: " + exception.getMessage(), exception);
        } catch (RuntimeException exception) {
            LOGGER.error("OpenAI image generation failed before a valid response was returned. templateId={}, endpoint={}, message={}",
                    templateId, "/images/generations", exception.getMessage(), exception);
            throw new ImageGenerationException("OpenAI image generation failed: " + exception.getMessage(), exception);
        }
    }

    private ImageGenerationResponse generateFromReferenceImages(String templateId,
                                                                String prompt,
                                                                ImageGenerationRequest generationRequest,
                                                                List<ReferenceImageInput> referenceImages,
                                                                String outputFormat,
                                                                String mimeType,
                                                                String imageSize,
                                                                String effectiveApiKey) {
        MultiValueMap<String, Object> requestBody = new LinkedMultiValueMap<String, Object>();
        requestBody.add("model", imageModel);
        requestBody.add("prompt", prompt);
        requestBody.add("size", imageSize);
        requestBody.add("quality", normalizeOption(generationRequest.getQuality(), "low"));
        requestBody.add("output_format", outputFormat);
        requestBody.add("background", normalizeOption(generationRequest.getBackground(), "auto"));
        for (ReferenceImageInput image : referenceImages) {
            requestBody.add("image[]", toImagePart(image));
        }

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(effectiveApiKey);
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);

        try {
            ResponseEntity<Map> response = restTemplate.exchange(
                    cleanBaseUrl() + "/images/edits",
                    HttpMethod.POST,
                    new HttpEntity<MultiValueMap<String, Object>>(requestBody, headers),
                    Map.class);
            return toGenerationResponse(templateId, prompt, outputFormat, mimeType, response.getBody());
        } catch (HttpStatusCodeException exception) {
            logOpenAiHttpError("edit", templateId, "/images/edits", exception);
            throw new ImageGenerationException("OpenAI image edit failed: " + readableResponseBody(exception), exception);
        } catch (ResourceAccessException exception) {
            LOGGER.error("OpenAI image edit connection failed. templateId={}, endpoint={}, baseUrl={}, referenceImageCount={}, message={}",
                    templateId, "/images/edits", cleanBaseUrl(), referenceImages.size(), exception.getMessage(), exception);
            throw new ImageGenerationException("Cannot connect to OpenAI image API. Check network access, OPENAI_BASE_URL, or OPENAI_PROXY_HOST/OPENAI_PROXY_PORT. Detail: " + exception.getMessage(), exception);
        } catch (RuntimeException exception) {
            LOGGER.error("OpenAI image edit failed before a valid response was returned. templateId={}, endpoint={}, referenceImageCount={}, message={}",
                    templateId, "/images/edits", referenceImages.size(), exception.getMessage(), exception);
            throw new ImageGenerationException("OpenAI image edit failed: " + exception.getMessage(), exception);
        }
    }

    private HttpEntity<NamedByteArrayResource> toImagePart(ReferenceImageInput image) {
        HttpHeaders partHeaders = new HttpHeaders();
        partHeaders.setContentType(MediaType.parseMediaType(normalizeImageContentType(image.getContentType())));
        return new HttpEntity<NamedByteArrayResource>(
                new NamedByteArrayResource(image.getBytes(), safeFileName(image.getFileName(), image.getContentType())),
                partHeaders);
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

    private List<ReferenceImageInput> validateReferenceImages(List<ReferenceImageInput> images) {
        if (images == null || images.isEmpty()) {
            return java.util.Collections.emptyList();
        }
        if (images.size() > MAX_REFERENCE_IMAGES) {
            throw new ImageGenerationException("At most 16 reference images can be uploaded.");
        }
        for (ReferenceImageInput image : images) {
            if (image == null || image.getBytes() == null || image.getBytes().length == 0) {
                throw new ImageGenerationException("Reference image cannot be empty.");
            }
            if (image.getBytes().length > MAX_REFERENCE_IMAGE_BYTES) {
                throw new ImageGenerationException("Each reference image must be 50MB or smaller.");
            }
            String contentType = normalizeImageContentType(image.getContentType());
            if (!"image/png".equals(contentType) && !"image/jpeg".equals(contentType) && !"image/webp".equals(contentType)) {
                throw new ImageGenerationException("Reference images must be PNG, JPEG, or WebP files.");
            }
        }
        return images;
    }

    private String normalizeImageContentType(String contentType) {
        if (!hasText(contentType)) {
            return "application/octet-stream";
        }
        String value = contentType.trim().toLowerCase(Locale.ROOT);
        return "image/jpg".equals(value) ? "image/jpeg" : value;
    }

    private String safeFileName(String fileName, String contentType) {
        if (hasText(fileName)) {
            return fileName.trim();
        }
        String contentTypeValue = normalizeImageContentType(contentType);
        if ("image/jpeg".equals(contentTypeValue)) {
            return "reference-image.jpg";
        }
        if ("image/webp".equals(contentTypeValue)) {
            return "reference-image.webp";
        }
        return "reference-image.png";
    }

    private void logOpenAiHttpError(String operation, String templateId, String endpoint, HttpStatusCodeException exception) {
        LOGGER.error("OpenAI image {} request failed. templateId={}, endpoint={}, baseUrl={}, statusCode={}, statusText={}, responseBody={}",
                operation,
                templateId,
                endpoint,
                cleanBaseUrl(),
                exception.getRawStatusCode(),
                exception.getStatusText(),
                readableResponseBody(exception),
                exception);
    }

    private String readableResponseBody(HttpStatusCodeException exception) {
        String responseBody = exception.getResponseBodyAsString();
        if (hasText(responseBody)) {
            return responseBody;
        }
        return "HTTP " + exception.getRawStatusCode() + " " + exception.getStatusText() + " with empty response body";
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

    private static String normalizeImageSize(String value) {
        String size = hasTextStatic(value) ? value.trim().toLowerCase(Locale.ROOT) : DEFAULT_IMAGE_SIZE;
        if (!size.matches("\\d+x\\d+")) {
            throw new ImageGenerationException("Image size must use WIDTHxHEIGHT format, for example 3840x2160.");
        }
        String[] parts = size.split("x");
        int width = parseImageSide(parts[0], "width");
        int height = parseImageSide(parts[1], "height");
        if (width % 16 != 0 || height % 16 != 0) {
            throw new ImageGenerationException("Image width and height must both be multiples of 16.");
        }
        if (width > MAX_IMAGE_SIDE || height > MAX_IMAGE_SIDE) {
            throw new ImageGenerationException("Image width and height must be 3840px or smaller.");
        }
        int longest = Math.max(width, height);
        int shortest = Math.min(width, height);
        if (longest > shortest * 3) {
            throw new ImageGenerationException("Image aspect ratio must not exceed 3:1.");
        }
        int pixels = width * height;
        if (pixels < MIN_IMAGE_PIXELS || pixels > MAX_IMAGE_PIXELS) {
            throw new ImageGenerationException("Image total pixels must be between 655360 and 8294400.");
        }
        return width + "x" + height;
    }

    private static int parseImageSide(String value, String name) {
        try {
            int side = Integer.parseInt(value);
            if (side <= 0) {
                throw new NumberFormatException("non-positive");
            }
            return side;
        } catch (NumberFormatException exception) {
            throw new ImageGenerationException("Image " + name + " must be a positive integer.", exception);
        }
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

    private static boolean hasTextStatic(String value) {
        return value != null && !value.trim().isEmpty();
    }

    private static class NamedByteArrayResource extends ByteArrayResource {

        private final String fileName;

        NamedByteArrayResource(byte[] byteArray, String fileName) {
            super(byteArray);
            this.fileName = fileName;
        }

        @Override
        public String getFilename() {
            return fileName;
        }
    }
}
