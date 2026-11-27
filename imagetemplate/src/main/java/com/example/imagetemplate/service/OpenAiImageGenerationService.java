package com.example.imagetemplate.service;

import com.example.imagetemplate.dto.ImageGenerationRequest;
import com.example.imagetemplate.dto.ImageGenerationResponse;
import com.example.imagetemplate.dto.PromptRenderRequest;
import com.example.imagetemplate.dto.ReferenceImageInput;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ByteArrayResource;
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

/**
 * OpenAI Images API 调用服务，本模块唯一的外部网络出口。
 *
 * <p>配置来自根目录 {@code model.properties} 的 {@code image.*}（经 common 的
 * {@code ModelProperties} 读取）：{@code base-url}、{@code api-key}、
 * {@code image-model}/{@code image-models}、连接与读取超时、HTTP/SOCKS 代理。
 * 密钥只在此处使用，不写日志、不返回给页面。</p>
 *
 * <p>调用分两条路径：没有参考图时走 {@code POST /images/generations}（JSON）；
 * 带参考图时走 {@code POST /images/edits}（multipart，字段名 {@code image[]}）。
 * 无论哪条路径，都在触网之前完成参数校验：</p>
 * <ul>
 *   <li>尺寸必须为 {@code 宽x高}，宽高为 16 的正整数倍，单边不超过
 *       {@value #MAX_IMAGE_SIDE}，长短边比例不超过 3:1，总像素在
 *       {@value #MIN_IMAGE_PIXELS} 到 {@value #MAX_IMAGE_PIXELS} 之间；
 *       空白时默认 {@value #DEFAULT_IMAGE_SIZE}。这套阈值与前端校验必须保持一致。</li>
 *   <li>参考图最多 {@value #MAX_REFERENCE_IMAGES} 张，单张不超过 50MB，
 *       仅接受 PNG/JPEG/WebP。</li>
 *   <li>模型必须在 {@code image-models} 白名单内；未配置密钥时直接报错。</li>
 * </ul>
 *
 * <p>所有失败路径统一包装成 {@link ImageGenerationException}：HTTP 状态异常会带上游
 * 响应体片段，连接失败会提示检查网络、{@code image.base-url} 或代理配置。</p>
 */
@Service
public class OpenAiImageGenerationService {

    private static final Logger LOGGER = LoggerFactory.getLogger(OpenAiImageGenerationService.class);

    /** 单次请求允许的参考图张数上限；超过时直接拒绝，避免上游 multipart 体积失控。 */
    private static final int MAX_REFERENCE_IMAGES = 16;

    /** 单张参考图字节上限（50MB）；由调用方解出字节后按实际长度校验。 */
    private static final long MAX_REFERENCE_IMAGE_BYTES = 50L * 1024L * 1024L;

    /** 未指定尺寸时的默认值；满足全部校验规则的最小常用方形尺寸。 */
    private static final String DEFAULT_IMAGE_SIZE = "1024x1024";

    /** 单边像素上限；与前端尺寸选项一致，超过后上游可能拒绝或质量下降。 */
    private static final int MAX_IMAGE_SIDE = 3840;

    /** 总像素下限（约 0.65MP）；低于此值画面信息量不足。 */
    private static final int MIN_IMAGE_PIXELS = 655360;

    /** 总像素上限（8294400，即 4K 横版 3840x2160）；超过后生成耗时会显著上升。 */
    private static final int MAX_IMAGE_PIXELS = 8294400;

    /** 用于把请求里的模板与变量渲染成最终 Prompt；本服务不自己拼模板。 */
    private final ImagePromptTemplateService imagePromptTemplateService;

    /** 构造期创建并复用；{@link SimpleClientHttpRequestFactory} 每次请求新建连接，无状态共享。 */
    private final RestTemplate restTemplate;

    /** 图片提供方密钥，来自 {@code image.api-key}；为空时生成入口直接报错。 */
    private final String apiKey;

    /** 提供方基础地址，来自 {@code image.base-url}，使用前会去掉尾部斜杠。 */
    private final String baseUrl;

    /** 默认图片模型，来自 {@code image.image-model}；未配置时回退内置值。 */
    private final String imageModel;

    /** 允许的图片模型白名单：默认模型 + {@code image-models} 声明的集合，顺序去重。 */
    private final java.util.List<String> imageModels;

    /**
     * Spring 构造入口：从项目根目录 {@code model.properties} 读取 {@code image} 提供方配置。
     *
     * @param imagePromptTemplateService 负责按模板渲染 Prompt
     */
    @org.springframework.beans.factory.annotation.Autowired
    public OpenAiImageGenerationService(ImagePromptTemplateService imagePromptTemplateService) {
        this(imagePromptTemplateService, com.example.common.ai.ModelProperties.load().provider("image"));
    }

    /**
     * 可注入提供方配置的构造入口，测试用它避免读取真实 {@code model.properties}。
     *
     * <p>{@code provider} 为 {@code null} 时使用内置默认值：地址
     * {@code https://nimabo.io/v1}、模型 {@code gpt-image-2.5-sunburst} 与
     * {@code gpt-image-2.5-sunburst}/{@code gpt-image-2.5-flare} 白名单、
     * 连接超时 300000ms、读取超时 180000ms。代理仅在 host 非空且端口大于 0 时生效。</p>
     *
     * @param imagePromptTemplateService 负责按模板渲染 Prompt
     * @param provider                   图片提供方配置，可为 {@code null}
     */
    OpenAiImageGenerationService(ImagePromptTemplateService imagePromptTemplateService,
                                 com.example.common.ai.ModelProperties.Provider provider) {
        this.imagePromptTemplateService = imagePromptTemplateService;
        this.apiKey = provider == null ? "" : provider.apiKey();
        this.baseUrl = provider == null ? "https://nimabo.io/v1" : provider.baseUrl();
        this.imageModel = provider == null ? "gpt-image-2.5-sunburst"
                : provider.option("image-model", "gpt-image-2.5-sunburst");
        java.util.Set<String> configuredModels = new java.util.LinkedHashSet<String>();
        configuredModels.add(imageModel);
        java.util.List<String> configured = provider == null
                ? java.util.Arrays.asList("gpt-image-2.5-sunburst", "gpt-image-2.5-flare")
                : provider.optionList("image-models");
        for (String model : configured) {
            if (!model.trim().isEmpty()) configuredModels.add(model.trim());
        }
        this.imageModels = java.util.Collections.unmodifiableList(new java.util.ArrayList<String>(configuredModels));

        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(provider == null ? 300000 : provider.intOption("connect-timeout-ms", 300000));
        requestFactory.setReadTimeout(provider == null ? 180000 : provider.intOption("read-timeout-ms", 180000));
        configureProxy(requestFactory, provider);
        this.restTemplate = new RestTemplate(requestFactory);
    }

    /**
     * 生成图片并返回 Base64 数据。
     *
     * <p>执行顺序：解析模型 → 校验尺寸 → 解析 Prompt（请求自带 {@code prompt} 优先，
     * 否则按模板与变量渲染）→ 归一化输出格式与 MIME → 校验参考图 → 读取密钥。
     * 参考图非空时走 {@code /images/edits}，否则走 {@code /images/generations}。
     * 校验全部在触网前完成，非法尺寸或未配置密钥时不会产生外部请求。</p>
     *
     * <p>响应体必须包含非空的 {@code data[0].b64_json}，缺失时同样视为失败；
     * 成功时额外把实际使用的模型写回响应，便于前端核对。</p>
     *
     * @param templateId 模板 ID，用于渲染 Prompt 与日志定位
     * @param request    生成请求，{@code null} 时按全默认值处理（1024x1024、png、low、auto）
     * @return 含 {@code imageBase64}、{@code dataUrl}、Prompt 与实际模型的结果
     * @throws ImageGenerationException 模型不在白名单、尺寸非法、参考图非法、缺密钥、
     *                                 上游非 2xx、连接失败或响应缺图片数据
     * @throws ImagePromptTemplateNotFoundException 请求未自带 Prompt 且模板 ID 不存在
     */
    public ImageGenerationResponse generate(String templateId, ImageGenerationRequest request) {
        ImageGenerationRequest generationRequest = request == null ? new ImageGenerationRequest() : request;
        String selectedModel = resolveModel(generationRequest.getModel());
        String imageSize = normalizeImageSize(generationRequest.getSize());
        String prompt = resolvePrompt(templateId, generationRequest);
        String outputFormat = normalizeOption(generationRequest.getOutputFormat(), "png");
        String mimeType = mimeType(outputFormat);
        List<ReferenceImageInput> referenceImages = validateReferenceImages(generationRequest.getReferenceImages());
        String effectiveApiKey = resolveApiKey();

        if (!referenceImages.isEmpty()) {
            LOGGER.info("Generating image with references. templateId={}, model={}, endpoint={}, size={}, quality={}, outputFormat={}, background={}, referenceImageCount={}",
                    templateId,
                    selectedModel,
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
                selectedModel,
                "/images/generations",
                imageSize,
                normalizeOption(generationRequest.getQuality(), "low"),
                outputFormat,
                normalizeOption(generationRequest.getBackground(), "auto"));

        Map<String, Object> requestBody = new HashMap<String, Object>();
        requestBody.put("model", selectedModel);
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
            ImageGenerationResponse result = toGenerationResponse(templateId, prompt, outputFormat, mimeType, response.getBody());
            result.setModel(selectedModel);
            return result;
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

    /**
     * 带参考图的图片编辑调用。
     *
     * <p>请求体是 multipart 表单，除 model/prompt/size/quality/output_format/background
     * 五个普通字段外，每张参考图以 {@code image[]} 追加，各自带独立 Content-Type 与文件名。
     * 这里会重新解析一次模型名，保证与日志中记录的模型一致。</p>
     *
     * @param templateId        模板 ID，仅用于日志与响应回填
     * @param prompt            已渲染好的最终 Prompt
     * @param generationRequest 原始请求，提供模型、质量、背景等参数
     * @param referenceImages   已通过校验的参考图
     * @param outputFormat      归一化后的输出格式
     * @param mimeType          输出格式对应的 MIME 类型
     * @param imageSize         已校验的尺寸字符串
     * @param effectiveApiKey   已确认非空的密钥
     * @return 生成结果
     * @throws ImageGenerationException 上游非 2xx、连接失败、其他运行时异常或响应缺图片数据
     */
    private ImageGenerationResponse generateFromReferenceImages(String templateId,
                                                                String prompt,
                                                                ImageGenerationRequest generationRequest,
                                                                List<ReferenceImageInput> referenceImages,
                                                                String outputFormat,
                                                                String mimeType,
                                                                String imageSize,
                                                                String effectiveApiKey) {
        MultiValueMap<String, Object> requestBody = new LinkedMultiValueMap<String, Object>();
        String selectedModel = resolveModel(generationRequest.getModel());
        requestBody.add("model", selectedModel);
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
            ImageGenerationResponse result = toGenerationResponse(templateId, prompt, outputFormat, mimeType, response.getBody());
            result.setModel(selectedModel);
            return result;
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

    /**
     * 构造单个 multipart 图片分片。
     *
     * <p>分片自己的 Content-Type 取自图片的 MIME（{@code image/jpg} 已归一成
     * {@code image/jpeg}）；文件名为空时按 MIME 补一个带正确扩展名的默认名，
     * 因为部分代理会依据文件名后缀推断格式。</p>
     *
     * @param image 参考图元数据
     * @return 携带命名资源与分片头的实体
     */
    private HttpEntity<NamedByteArrayResource> toImagePart(ReferenceImageInput image) {
        HttpHeaders partHeaders = new HttpHeaders();
        partHeaders.setContentType(MediaType.parseMediaType(normalizeImageContentType(image.getContentType())));
        return new HttpEntity<NamedByteArrayResource>(
                new NamedByteArrayResource(image.getBytes(), safeFileName(image.getFileName(), image.getContentType())),
                partHeaders);
    }

    /**
     * 决定最终提交给上游的 Prompt。
     *
     * <p>请求自带非空 {@code prompt} 时直接使用（前端已手工编辑或拼接），
     * 否则把变量与补充要求交给 {@link ImagePromptTemplateService#renderPrompt} 渲染，
     * 因此请求可以不传 prompt，但模板 ID 必须有效。</p>
     *
     * @param templateId 模板 ID
     * @param request    生成请求
     * @return 去首尾空白后的 Prompt
     * @throws ImagePromptTemplateNotFoundException 需要渲染但模板不存在
     */
    private String resolvePrompt(String templateId, ImageGenerationRequest request) {
        if (hasText(request.getPrompt())) {
            return request.getPrompt().trim();
        }
        PromptRenderRequest promptRequest = new PromptRenderRequest();
        promptRequest.setVariables(request.getVariables());
        promptRequest.setExtraInstruction(request.getExtraInstruction());
        return imagePromptTemplateService.renderPrompt(templateId, promptRequest);
    }

    /**
     * 校验参考图列表。
     *
     * <p>阈值：最多 {@value #MAX_REFERENCE_IMAGES} 张，每张字节非空且不超过 50MB，
     * MIME 必须是 PNG、JPEG 或 WebP（{@code image/jpg} 会被归一成 {@code image/jpeg}）。
     * 任一条不满足即抛异常，不做“丢弃非法项后继续”的降级，避免用户以为参考图已生效。</p>
     *
     * @param images 原始参考图列表，可为 {@code null} 或空
     * @return 原列表引用；无参考图时返回空列表
     * @throws ImageGenerationException 数量、体积、空数据或 MIME 不合法
     */
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

    /**
     * 归一化图片 MIME。
     *
     * <p>浏览器与旧数据常把 JPEG 写成 {@code image/jpg}，这里统一成标准写法；
     * 空白值返回 {@code application/octet-stream}，随后会被参考图校验拒绝。</p>
     *
     * @param contentType 原始 Content-Type，可为 {@code null}
     * @return 小写 MIME
     */
    private String normalizeImageContentType(String contentType) {
        if (!hasText(contentType)) {
            return "application/octet-stream";
        }
        String value = contentType.trim().toLowerCase(Locale.ROOT);
        return "image/jpg".equals(value) ? "image/jpeg" : value;
    }

    /**
     * multipart 分片文件名兜底。
     *
     * <p>有文件名就原样使用；没有时按 MIME 补 {@code reference-image.jpg}、
     * {@code reference-image.webp} 或 {@code reference-image.png}，
     * 保证上游能按扩展名识别格式。</p>
     *
     * @param fileName    调用方提供的文件名，可为 {@code null}
     * @param contentType 图片 MIME
     * @return 非空文件名
     */
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

    /**
     * 记录上游 HTTP 错误日志。
     *
     * <p>日志包含操作类型、模板 ID、endpoint、baseUrl、状态码、状态文本与响应体，
     * 便于区分“密钥失效”“模型不存在”“尺寸被拒”和“参数拼写错误”。
     * 不记录 Authorization 头，密钥不会进入日志。</p>
     *
     * @param operation 操作名（{@code generation} 或 {@code edit}），写入日志便于区分路径
     * @param templateId 模板 ID
     * @param endpoint 实际调用的路径
     * @param exception 上游状态异常
     */
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

    /**
     * 提取可读的上游错误体。
     *
     * <p>上游返回空响应体时，用状态码与状态文本拼一句说明，
     * 避免错误消息以冒号结尾却没有任何内容。</p>
     *
     * @param exception 上游状态异常
     * @return 非空的错误描述
     */
    private String readableResponseBody(HttpStatusCodeException exception) {
        String responseBody = exception.getResponseBodyAsString();
        if (hasText(responseBody)) {
            return responseBody;
        }
        return "HTTP " + exception.getRawStatusCode() + " " + exception.getStatusText() + " with empty response body";
    }

    /**
     * 把上游 JSON 响应转换成统一结果对象。
     *
     * <p>逐层校验：响应体非空 → {@code data} 是非空列表 → 首元素是 Map →
     * {@code b64_json} 是非空字符串。任一层不满足都抛异常而不是返回空图片，
     * 避免前端拿到 {@code success=true} 却无法渲染。成功时顺带拼好 data URL，
     * 并透传 {@code usage} 供页面展示计费信息。</p>
     *
     * <p>{@code model} 先填默认模型，调用方会用本次请求实际选择的模型覆盖它。</p>
     *
     * @param templateId   模板 ID
     * @param prompt       本次提交的 Prompt
     * @param outputFormat 归一化后的输出格式
     * @param mimeType     输出 MIME
     * @param responseBody 上游响应体，可为 {@code null}
     * @return 生成结果
     * @throws ImageGenerationException 响应缺少 {@code data}、首元素或 {@code b64_json}
     */
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

    /**
     * 返回页面的图片模型选项。
     *
     * <p>只暴露配置里的模型名，不含密钥与地址；{@code verified=false} 表示这些模型
     * 未被实际探测过，可用性取决于提供方与当前密钥，提示文案也据此说明
     * “主页文本模型不会覆盖图片任务”。</p>
     *
     * @return 含 {@code success}、{@code defaultModel}、{@code models} 的响应 Map
     */
    public Map<String, Object> modelOptions() {
        Map<String, Object> result = new java.util.LinkedHashMap<String, Object>();
        result.put("success", true);
        result.put("defaultModel", imageModel);
        result.put("models", imageModels);
        result.put("verified", false);
        result.put("message", "以下为服务配置的图片模型，实际可用性取决于提供方和当前密钥。主页文本模型不会覆盖图片任务。");
        return result;
    }

    /**
     * 解析并校验请求模型名。
     *
     * <p>请求未指定时回退默认模型；指定值必须在 {@code image-models} 白名单内，
     * 否则报错要求从模型列表选择，防止把任意字符串透传给上游。</p>
     *
     * @param requested 请求中的模型名，可为 {@code null}
     * @return 白名单内的模型名
     * @throws ImageGenerationException 模型不在白名单
     */
    private String resolveModel(String requested) {
        String model = hasText(requested) ? requested.trim() : imageModel;
        if (!imageModels.contains(model)) throw new ImageGenerationException("不支持的图片模型，请从模型列表选择。");
        return model;
    }

    /**
     * 读取并校验密钥。
     *
     * <p>缺失时不发请求，直接提示在 {@code model.properties} 的 {@code image.api-key}
     * 填写密钥；页面不再接收用户自填密钥。</p>
     *
     * @return 去空白后的密钥
     * @throws ImageGenerationException 未配置密钥
     */
    private String resolveApiKey() {
        if (hasText(apiKey)) {
            return apiKey.trim();
        }
        throw new ImageGenerationException("图片模型未配置：请在项目根目录 model.properties 的 image.api-key 填写密钥。");
    }

    /**
     * 归一化 base URL。
     *
     * <p>去掉尾部全部斜杠，避免拼出 {@code //images/generations}；
     * 配置为空时回退官方地址 {@code https://api.openai.com/v1}。</p>
     *
     * @return 可直接拼接路径的基础地址
     */
    private String cleanBaseUrl() {
        String value = hasText(baseUrl) ? baseUrl.trim() : "https://api.openai.com/v1";
        while (value.endsWith("/")) {
            value = value.substring(0, value.length() - 1);
        }
        return value;
    }

    /**
     * 按配置给请求工厂挂代理。
     *
     * <p>仅当 {@code proxy-host} 非空白且 {@code proxy-port} 大于 0 时生效，
     * 也就是“不填代理就不走代理”；{@code proxy-type} 只有显式写 {@code SOCKS}
     * （忽略大小写）才用 SOCKS，其余一律按 HTTP 代理处理。</p>
     *
     * @param requestFactory 已设置超时的请求工厂
     * @param provider       图片提供方配置，可为 {@code null}
     */
    private void configureProxy(SimpleClientHttpRequestFactory requestFactory,
                                com.example.common.ai.ModelProperties.Provider provider) {
        if (provider == null) {
            return;
        }
        String proxyHost = provider.option("proxy-host", "");
        int proxyPort = provider.intOption("proxy-port", 0);
        if (!hasText(proxyHost) || proxyPort <= 0) {
            return;
        }
        String proxyType = provider.option("proxy-type", "HTTP");
        Proxy.Type type = "SOCKS".equalsIgnoreCase(proxyType) ? Proxy.Type.SOCKS : Proxy.Type.HTTP;
        requestFactory.setProxy(new Proxy(type, new InetSocketAddress(proxyHost.trim(), proxyPort)));
    }

    /**
     * 归一化可选枚举值。
     *
     * <p>去空白并转小写，空白时回退默认值；quality/background/outputFormat
     * 都以该形式提交给上游，避免大小写差异被上游判为非法值。</p>
     *
     * @param value    请求值，可为 {@code null}
     * @param fallback 缺省值
     * @return 归一化后的值
     */
    private String normalizeOption(String value, String fallback) {
        return hasText(value) ? value.trim().toLowerCase(Locale.ROOT) : fallback;
    }

    /**
     * 校验并归一化图片尺寸。
     *
     * <p>规则必须与前端保持完全一致，任一条不满足都在触网前抛异常：</p>
     * <ol>
     *   <li>格式为 {@code 宽x高}（先统一转小写，因此大写 {@code X} 也能接受），
     *       空白时用 {@value #DEFAULT_IMAGE_SIZE}；</li>
     *   <li>宽高都是正整数，且都是 16 的倍数；</li>
     *   <li>单边不超过 {@value #MAX_IMAGE_SIDE}；</li>
     *   <li>长边不超过短边的 3 倍；</li>
     *   <li>总像素在 {@value #MIN_IMAGE_PIXELS} 到 {@value #MAX_IMAGE_PIXELS} 之间。</li>
     * </ol>
     *
     * <p>注意比例校验用整数乘法而非浮点除法，边界值 3:1 恰好通过。</p>
     *
     * @param value 请求中的尺寸字符串，可为 {@code null}
     * @return 校验通过的规范化尺寸（{@code 宽x高}）
     * @throws ImageGenerationException 格式、倍数、单边、比例或像素数不合法
     */
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

    /**
     * 解析单边像素并校验为正整数。
     *
     * <p>非数字、超出 int 范围或小于等于 0 都转成统一的图片生成异常，
     * 消息里带上 {@code width}/{@code height} 便于定位是哪一侧出错。</p>
     *
     * @param value 数字片段
     * @param name  字段名（{@code width} 或 {@code height}）
     * @return 正整数边长
     * @throws ImageGenerationException 非正整数
     */
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

    /**
     * 输出格式到 MIME 的映射。
     *
     * <p>只识别 jpeg/jpg 与 webp，其余（含 {@code png} 与未知值）一律按 PNG 处理，
     * 与上游默认返回格式保持一致。</p>
     *
     * @param outputFormat 归一化后的输出格式
     * @return 对应的 MIME 类型
     */
    private String mimeType(String outputFormat) {
        if ("jpeg".equals(outputFormat) || "jpg".equals(outputFormat)) {
            return "image/jpeg";
        }
        if ("webp".equals(outputFormat)) {
            return "image/webp";
        }
        return "image/png";
    }

    /**
     * 判断字符串是否包含非空白字符。
     *
     * @param value 待判断文本，可为 {@code null}
     * @return {@code null} 或纯空白返回 {@code false}
     */
    private boolean hasText(String value) {
        return value != null && !value.trim().isEmpty();
    }

    /** 静态版本的空白判断，供静态校验方法使用；语义与实例方法一致。 */
    private static boolean hasTextStatic(String value) {
        return value != null && !value.trim().isEmpty();
    }

    /**
     * 带文件名的内存资源，用于 multipart 上传。
     *
     * <p>{@link ByteArrayResource} 默认不提供文件名，而上游需要文件名判断图片格式，
     * 因此在这里覆盖 {@link #getFilename()}。</p>
     */
    private static class NamedByteArrayResource extends ByteArrayResource {

        private final String fileName;

        /**
         * @param byteArray 图片原始字节
         * @param fileName  上游可见的文件名，不得为空
         */
        NamedByteArrayResource(byte[] byteArray, String fileName) {
            super(byteArray);
            this.fileName = fileName;
        }

        /**
         * 返回上游可见的文件名。
         *
         * @return 构造时传入的文件名
         */
        @Override
        public String getFilename() {
            return fileName;
        }
    }
}
