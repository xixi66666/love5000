package com.example.imagetemplate.dto;

import java.util.LinkedHashMap;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 图片生成请求参数。
 *
 * <p>同时服务两个入口：{@code POST /{id}/generate} 的 JSON 请求体，以及 multipart 表单
 * （由 Controller 逐字段装配）。字段初始值即默认行为，未传时按此执行：尺寸
 * {@code 1024x1024}、质量 {@code low}、格式 {@code png}、背景 {@code auto}。</p>
 *
 * <p>本类只承载数据，不做校验：尺寸规则、模型白名单、参考图数量/体积/类型都在
 * {@link com.example.imagetemplate.service.OpenAiImageGenerationService} 内、
 * 真实调用上游之前校验，非法输入抛
 * {@link com.example.imagetemplate.service.ImageGenerationException}，由 Controller 映射为 502。</p>
 *
 * <p>字段声明顺序并不统一：{@code model} 及其读写方法位于类首，其余字段的读写方法集中在
 * 文件末尾，这是后续增量加入模型白名单时留下的结构。</p>
 */
public class ImageGenerationRequest {

    /**
     * 图片模型 ID；为 {@code null} 或空白时使用 {@code image.image-model}。
     *
     * <p>取值必须命中 {@code image.image-models} 白名单，否则请求在触网前被拒绝。</p>
     */
    private String model;

    public String getModel() { return model; }

    public void setModel(String model) { this.model = model; }

    /**
     * 模板变量，key 需与 {@code jsonTemplate} 中的字段同名才能覆盖默认值。
     *
     * <p>默认可变空 Map：{@code DIRECT} 模板会把非空变量作为「用户变量」段落追加到
     * prompt，结构化模板则逐层替换同名字段。</p>
     */
    private Map<String, Object> variables = new LinkedHashMap<String, Object>();

    /** 追加在 prompt 末尾的补充要求（如版式、背景）；{@code null} 或空白视为未填。 */
    private String extraInstruction;

    /** 直接指定的完整 prompt；非空白时跳过模板渲染，变量与补充要求不再生效。 */
    private String prompt;

    /**
     * 输出尺寸，格式为 {@code 宽x高}，默认 {@code 1024x1024}。
     *
     * <p>约束：宽高为正整数且均为 16 的倍数、单边不超过 3840、长宽比不超过 3:1、
     * 总像素在 655360~8294400 之间；违规在调用上游前即拒绝。</p>
     */
    private String size = "1024x1024";

    /** 生成质量，常用 low/medium/high，默认 low；服务端只做小写与去空白归一化，不做白名单校验。 */
    private String quality = "low";

    /** 输出格式，取值 png/jpeg/webp，默认 png；决定 {@code mimeType} 与 data URL 前缀，其它值按 png 处理。 */
    private String outputFormat = "png";

    /** 背景模式，取值 auto/transparent/opaque，默认 auto；服务端只做小写归一化，不校验取值。 */
    private String background = "auto";

    /**
     * 参考图列表，默认空列表；非空时改走上游 {@code /images/edits}（图生图）。
     *
     * <p>上限 16 张、单张不超过 50MB，仅接受 PNG/JPEG/WebP。</p>
     */
    private List<ReferenceImageInput> referenceImages = new ArrayList<ReferenceImageInput>();

    public Map<String, Object> getVariables() {
        return variables;
    }

    public void setVariables(Map<String, Object> variables) {
        this.variables = variables;
    }

    public String getExtraInstruction() {
        return extraInstruction;
    }

    public void setExtraInstruction(String extraInstruction) {
        this.extraInstruction = extraInstruction;
    }

    public String getPrompt() {
        return prompt;
    }

    public void setPrompt(String prompt) {
        this.prompt = prompt;
    }

    public String getSize() {
        return size;
    }

    public void setSize(String size) {
        this.size = size;
    }

    public String getQuality() {
        return quality;
    }

    public void setQuality(String quality) {
        this.quality = quality;
    }

    public String getOutputFormat() {
        return outputFormat;
    }

    public void setOutputFormat(String outputFormat) {
        this.outputFormat = outputFormat;
    }

    public String getBackground() {
        return background;
    }

    public void setBackground(String background) {
        this.background = background;
    }

    public List<ReferenceImageInput> getReferenceImages() {
        return referenceImages;
    }

    public void setReferenceImages(List<ReferenceImageInput> referenceImages) {
        this.referenceImages = referenceImages;
    }
}

