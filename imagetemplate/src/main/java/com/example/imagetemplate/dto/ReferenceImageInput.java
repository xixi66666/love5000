package com.example.imagetemplate.dto;

/**
 * 参考图的内存视图。
 *
 * <p>由 Controller 从 multipart 上传文件一次性读出，只在单次生成请求内使用，
 * 不落盘也不缓存。{@code bytes} 会原样转成 multipart part 发给上游
 * {@code /images/edits}，因此数量与体积上限（16 张、单张 50MB）由
 * {@link com.example.imagetemplate.service.OpenAiImageGenerationService} 校验。</p>
 */
public class ReferenceImageInput {

    /** 上传时的原始文件名，用作上游 part 的文件名；为空时服务端按 MIME 类型补默认名。 */
    private String fileName;

    /** 浏览器上报的 MIME 类型；仅 PNG/JPEG/WebP 允许，缺失时按 application/octet-stream 处理。 */
    private String contentType;

    /** 文件原始字节；单张上限 50MB，超过即拒绝，不写入磁盘。 */
    private byte[] bytes;

    public ReferenceImageInput() {
    }

    public ReferenceImageInput(String fileName, String contentType, byte[] bytes) {
        this.fileName = fileName;
        this.contentType = contentType;
        this.bytes = bytes;
    }

    public String getFileName() {
        return fileName;
    }

    public void setFileName(String fileName) {
        this.fileName = fileName;
    }

    public String getContentType() {
        return contentType;
    }

    public void setContentType(String contentType) {
        this.contentType = contentType;
    }

    public byte[] getBytes() {
        return bytes;
    }

    public void setBytes(byte[] bytes) {
        this.bytes = bytes;
    }
}

