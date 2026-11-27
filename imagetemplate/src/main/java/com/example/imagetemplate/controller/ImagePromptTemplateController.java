package com.example.imagetemplate.controller;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.example.imagetemplate.dto.PromptRenderRequest;
import com.example.imagetemplate.dto.PromptRenderResponse;
import com.example.imagetemplate.dto.ImageGenerationRequest;
import com.example.imagetemplate.dto.ImageGenerationResponse;
import com.example.imagetemplate.dto.ImageTemplateMetaResponse;
import com.example.imagetemplate.dto.ImageTemplatePageResponse;
import com.example.imagetemplate.dto.ImageTemplateQuery;
import com.example.imagetemplate.dto.ReferenceImageInput;
import com.example.imagetemplate.dto.TemplateCategoryResponse;
import com.example.imagetemplate.service.ImageGenerationException;
import com.example.imagetemplate.service.ImagePromptTemplateNotFoundException;
import com.example.imagetemplate.service.ImagePromptTemplateService;
import com.example.imagetemplate.service.ImageTemplateQueryValidationException;
import com.example.imagetemplate.service.OpenAiImageGenerationService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 图片提示词模板工作台的 REST 入口。
 *
 * <p>挂在 {@code /api/image-templates} 下，只负责 HTTP 入参绑定、统一响应包装
 * （{@code {success, message, ...}}）和异常到状态码的映射；筛选、分页、渲染与生成
 * 规则全部在 {@link ImagePromptTemplateService} 和 {@link OpenAiImageGenerationService}
 * 中完成，本类不拼接模板内容。</p>
 *
 * <p>异常映射：模板不存在 → 404；查询参数非法（如 {@code size} 超出 1~100）→ 400；
 * 图片生成失败（缺密钥、模型不支持、尺寸非法、上游非 2xx、响应缺图片）→ 502。
 * 三类都统一输出 {@code success=false} 与可读的 {@code message}。</p>
 *
 * <p>列表接口只返回摘要，完整 {@code promptTemplate}/{@code jsonTemplate} 走详情接口；
 * 生成接口按 {@code Content-Type} 分成 JSON 与 multipart 两个重载，后者用于携带参考图。</p>
 */
@RestController
@RequestMapping("/api/image-templates")
public class ImagePromptTemplateController {

    /** 只记录生成失败等需要排障的错误；成功路径不打印，避免 base64 与提示词刷屏。 */
    private static final Logger LOGGER = LoggerFactory.getLogger(ImagePromptTemplateController.class);

    /** 模板聚合、筛选、元数据查询与 prompt 渲染的唯一业务入口。 */
    private final ImagePromptTemplateService imagePromptTemplateService;

    /** 图片生成与模型白名单的唯一出口，所有外部网络调用都不放在 Controller。 */
    private final OpenAiImageGenerationService openAiImageGenerationService;

    /** 用于解析 multipart 表单里以字符串形式提交的 {@code variables} JSON。 */
    private final ObjectMapper objectMapper;

    /**
     * 构造器注入，便于在测试中替换真实服务。
     *
     * @param imagePromptTemplateService   模板查询与渲染服务
     * @param openAiImageGenerationService 图片生成服务
     * @param objectMapper                 Spring 容器内的 ObjectMapper，用于解析表单变量
     */
    public ImagePromptTemplateController(ImagePromptTemplateService imagePromptTemplateService,
                                         OpenAiImageGenerationService openAiImageGenerationService,
                                         ObjectMapper objectMapper) {
        this.imagePromptTemplateService = imagePromptTemplateService;
        this.openAiImageGenerationService = openAiImageGenerationService;
        this.objectMapper = objectMapper;
    }

    /**
     * 分页查询模板摘要。
     *
     * <p>多个筛选条件之间是「与」关系；字符串先 trim 再转小写，空值或 {@code all} 表示该维度
     * 不筛选。{@code functionCategory}/{@code functionScene} 同时接受 slug 与中文名，
     * {@code source} 只匹配来源 ID，{@code category} 匹配原始分类的 slug 或中文名；
     * {@code keyword} 为小写子串匹配，范围是标题、摘要、原始分类、来源名、标签与完整 prompt。</p>
     *
     * @param page             页码，从 1 开始，默认 1；小于 1 由 service 判为非法请求
     * @param size             每页条数，默认 48，允许 1~100；越界由 service 判为非法请求
     * @param keyword          关键词，可为 {@code null}
     * @param source           来源 ID，可为 {@code null}
     * @param category         原始分类 slug 或中文名，可为 {@code null}
     * @param functionCategory 一级功能 slug 或中文名，可为 {@code null}
     * @param functionScene    二级场景 slug 或中文名，可为 {@code null}
     * @param imageOnly        为 {@code true} 时只返回图片相关模板，默认 {@code false}
     * @return 当前页摘要；{@code libraryStatus}/{@code message} 会带上大库聚合状态，
     *         降级时仍返回已加载的数据而不是报错
     */
    @GetMapping
    public ImageTemplatePageResponse listTemplates(
            @RequestParam(value = "page", defaultValue = "1") int page,
            @RequestParam(value = "size", defaultValue = "48") int size,
            @RequestParam(value = "keyword", required = false) String keyword,
            @RequestParam(value = "source", required = false) String source,
            @RequestParam(value = "category", required = false) String category,
            @RequestParam(value = "functionCategory", required = false)
                    String functionCategory,
            @RequestParam(value = "functionScene", required = false)
                    String functionScene,
            @RequestParam(value = "imageOnly", defaultValue = "false") boolean imageOnly) {
        ImageTemplateQuery query = new ImageTemplateQuery();
        query.setPage(page);
        query.setSize(size);
        query.setKeyword(keyword);
        query.setSource(source);
        query.setCategory(category);
        query.setFunctionCategory(functionCategory);
        query.setFunctionScene(functionScene);
        query.setImageOnly(imageOnly);
        return imagePromptTemplateService.search(query);
    }

    /**
     * 列出原始分类（{@code categorySlug}）及各自条数。
     *
     * <p>返回的是模板数据里的原始分类，与 {@code /meta} 的两级功能分类树是两套维度：
     * 前者兼容旧筛选参数，后者用于工作台的功能导航。</p>
     *
     * @return {@code {success: true, categories: [...]}}，count 为聚合后的实际条数
     */
    @GetMapping("/categories")
    public Map<String, Object> listCategories() {
        List<TemplateCategoryResponse> categories = imagePromptTemplateService.listCategories();
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("success", true);
        result.put("categories", categories);
        return result;
    }

    /**
     * 返回聚合元数据：总量、精选/大库条数、图片相关条数、来源、原始分类与两级功能树。
     *
     * <p>响应本身就是数据体，不再额外包一层；{@code success} 恒为 true。大库异常不会让
     * 该接口失败，而是写进 {@code status}：{@code READY} 表示条数符合预期，
     * {@code DEGRADED} 表示有缺失或解析问题，前端据此显示预期数量与实际数量。</p>
     *
     * @return 首屏分类导航与聚合告警所需的完整元数据
     */
    @GetMapping("/meta")
    public ImageTemplateMetaResponse getMeta() {
        return imagePromptTemplateService.getMeta();
    }

    /**
     * 返回当前服务可选的图片模型白名单。
     *
     * <p>数据来自根目录 {@code model.properties} 的 {@code image.*}，由
     * {@link OpenAiImageGenerationService#modelOptions()} 组装：默认模型、候选模型列表，
     * 以及恒为 false 的 {@code verified}（本服务不主动探测上游可用性）。
     * 主页的文本模型选择不会覆盖图片模型。</p>
     *
     * @return {@code {success, defaultModel, models, verified, message}}
     */
    @GetMapping("/models")
    public Map<String, Object> getImageModels() {
        return openAiImageGenerationService.modelOptions();
    }

    /**
     * 按 ID 查询单个模板的完整内容，含 {@code promptTemplate} 与 {@code jsonTemplate}。
     *
     * @param id 模板 ID；精选模板为小写 slug，大库条目形如
     *           {@code library-<来源>-<原始id>-<内容指纹>}
     * @return {@code {success: true, template: {...}}}；ID 不存在时抛
     *         {@link ImagePromptTemplateNotFoundException}，由异常处理器转 404
     */
    @GetMapping("/{id}")
    public Map<String, Object> getTemplate(@PathVariable("id") String id) {
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("success", true);
        result.put("template", imagePromptTemplateService.findById(id));
        return result;
    }

    /**
     * 渲染指定模板的提示词，供页面预览与复制。
     *
     * <p>请求体可省略：{@code DIRECT} 模板以 {@code promptTemplate} 为底，追加非空变量与
     * 补充要求；结构化模板则把 {@code jsonTemplate} 与变量逐层合并后拼成自然语言指令。
     * 具体规则见 {@link ImagePromptTemplateService#renderPrompt(String, PromptRenderRequest)}。</p>
     *
     * @param id      模板 ID
     * @param request 变量与补充要求，可为 {@code null}
     * @return 恒为 {@code success=true} 的渲染结果；模板不存在时由异常处理器转 404
     */
    @PostMapping("/{id}/prompt")
    public PromptRenderResponse renderPrompt(@PathVariable("id") String id,
                                             @RequestBody(required = false) PromptRenderRequest request) {
        return new PromptRenderResponse(true, id, imagePromptTemplateService.renderPrompt(id, request));
    }

    /**
     * 以 JSON 请求体生成图片（不含参考图）。
     *
     * <p>未传字段沿用 {@link ImageGenerationRequest} 的默认值：尺寸 {@code 1024x1024}、
     * 质量 {@code low}、格式 {@code png}、背景 {@code auto}。尺寸规则、模型白名单与密钥
     * 都在触网前由 service 校验，失败抛 {@link ImageGenerationException} 并映射为 502。</p>
     *
     * @param id      模板 ID，用于渲染 prompt 与回填 {@code templateId}
     * @param request 生成参数，可为 {@code null}（全部取默认值）
     * @return 含 base64 图片与 data URL 的生成结果
     */
    @PostMapping(value = "/{id}/generate", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ImageGenerationResponse generateImage(@PathVariable("id") String id,
                                                 @RequestBody(required = false) ImageGenerationRequest request) {
        return openAiImageGenerationService.generate(id, request);
    }

    /**
     * 以 multipart 表单生成图片，可同时上传参考图。
     *
     * <p>表单字段与 JSON 请求体同名同义，只有 {@code variables} 是 JSON 字符串；
     * 参考图写在 {@code referenceImages} 多值字段中，只有非空文件会被读取，
     * 因此「勾选但未选文件」不会变成空图上传。存在参考图时 service 改走上游
     * {@code /images/edits}（图生图），限制最多 16 张、单张不超过 50MB、仅 PNG/JPEG/WebP。</p>
     *
     * @param id               模板 ID
     * @param variables        变量 JSON 字符串，可为 {@code null} 或空白
     * @param extraInstruction 追加的补充要求，可为 {@code null}
     * @param prompt           直接指定的 prompt，非空白时跳过模板渲染
     * @param size             宽x高，可为 {@code null}（默认 1024x1024）
     * @param quality          常用 low/medium/high，可为 {@code null}（默认 low）
     * @param outputFormat     png/jpeg/webp，可为 {@code null}（默认 png）
     * @param background       auto/transparent/opaque，可为 {@code null}（默认 auto）
     * @param model            图片模型 ID，须在白名单内，可为 {@code null}（用默认模型）
     * @param referenceImages  参考图文件数组，可为 {@code null}
     * @return 含 base64 图片与 data URL 的生成结果
     * @throws ImageGenerationException {@code variables} 不是合法 JSON，或读取上传文件失败
     */
    @PostMapping(value = "/{id}/generate", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ImageGenerationResponse generateImageWithReferences(@PathVariable("id") String id,
                                                               @RequestParam(value = "variables", required = false) String variables,
                                                               @RequestParam(value = "extraInstruction", required = false) String extraInstruction,
                                                               @RequestParam(value = "prompt", required = false) String prompt,
                                                               @RequestParam(value = "size", required = false) String size,
                                                               @RequestParam(value = "quality", required = false) String quality,
                                                               @RequestParam(value = "outputFormat", required = false) String outputFormat,
                                                               @RequestParam(value = "background", required = false) String background,
                                                               @RequestParam(value = "model", required = false) String model,
                                                               @RequestParam(value = "referenceImages", required = false) MultipartFile[] referenceImages) {
        ImageGenerationRequest request = new ImageGenerationRequest();
        request.setVariables(readVariables(variables));
        request.setExtraInstruction(extraInstruction);
        request.setPrompt(prompt);
        request.setSize(size);
        request.setQuality(quality);
        request.setOutputFormat(outputFormat);
        request.setBackground(background);
        request.setModel(model);
        request.setReferenceImages(readReferenceImages(referenceImages));
        return openAiImageGenerationService.generate(id, request);
    }

    /**
     * 解析 multipart 表单里的 {@code variables} 字段。
     *
     * <p>空值返回可变空 Map，调用方不必判空；解析失败转成
     * {@link ImageGenerationException}，让调用方拿到 502 与可读原因，
     * 而不是 Spring 默认的泛化参数错误。</p>
     *
     * @param variables JSON 字符串，可为 {@code null} 或空白
     * @return 变量键值对，值为 Jackson 反序列化出的通用类型（String/Number/Map/List）
     * @throws ImageGenerationException 字符串不是合法的 JSON 对象
     */
    private Map<String, Object> readVariables(String variables) {
        if (variables == null || variables.trim().isEmpty()) {
            return new LinkedHashMap<String, Object>();
        }
        try {
            return objectMapper.readValue(variables, new TypeReference<Map<String, Object>>() {
            });
        } catch (IOException exception) {
            throw new ImageGenerationException("Variables must be valid JSON.", exception);
        }
    }

    /**
     * 把上传文件读成服务层使用的参考图对象。
     *
     * <p>跳过 {@code null} 与空文件（浏览器未选择文件时仍可能提交空 part），其余文件
     * 一次性读入内存；数量、单张体积与 MIME 类型由 service 再次校验，这里不做截断。</p>
     *
     * @param files multipart 解析出的文件数组，可为 {@code null}
     * @return 非空文件的内存副本，保持上传顺序
     * @throws ImageGenerationException 某个文件读取失败
     */
    private List<ReferenceImageInput> readReferenceImages(MultipartFile[] files) {
        List<ReferenceImageInput> images = new ArrayList<ReferenceImageInput>();
        if (files == null) {
            return images;
        }
        for (MultipartFile file : files) {
            if (file == null || file.isEmpty()) {
                continue;
            }
            try {
                images.add(new ReferenceImageInput(file.getOriginalFilename(), file.getContentType(), file.getBytes()));
            } catch (IOException exception) {
                throw new ImageGenerationException("Failed to read reference image: " + file.getOriginalFilename(), exception);
            }
        }
        return images;
    }

    /**
     * 模板不存在映射为 404。
     *
     * @param exception service 查找失败时抛出的异常，消息形如
     *                  {@code Image prompt template not found: <id>}
     * @return {@code {success: false, message}}
     */
    @ExceptionHandler(ImagePromptTemplateNotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public Map<String, Object> handleNotFound(ImagePromptTemplateNotFoundException exception) {
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("success", false);
        result.put("message", exception.getMessage());
        return result;
    }

    /**
     * 查询参数校验失败映射为 400。
     *
     * <p>常见触发点是 {@code page < 1} 或 {@code size} 超出 1~100；消息为中文，
     * 可直接展示给调用方。</p>
     *
     * @param exception service 校验抛出的异常
     * @return {@code {success: false, message}}
     */
    @ExceptionHandler(ImageTemplateQueryValidationException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Map<String, Object> handleQueryValidation(
            ImageTemplateQueryValidationException exception) {
        Map<String, Object> result = new LinkedHashMap<String, Object>();
        result.put("success", false);
        result.put("message", exception.getMessage());
        return result;
    }

    /**
     * 图片生成失败映射为 502。
     *
     * <p>原因包括未配置 {@code image.api-key}、模型不在白名单、尺寸非法、上游非 2xx
     * 或响应缺少 {@code b64_json}。日志记录完整堆栈，响应只回传 {@code message}，
     * 不会输出密钥或请求头。</p>
     *
     * @param exception 生成链路的统一异常
     * @return {@code {success: false, message}}
     */
    @ExceptionHandler(ImageGenerationException.class)
    @ResponseStatus(HttpStatus.BAD_GATEWAY)
    public Map<String, Object> handleGenerationError(ImageGenerationException exception) {
        LOGGER.error("Image generation request failed. message={}", exception.getMessage(), exception);
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("success", false);
        result.put("message", exception.getMessage());
        return result;
    }
}

