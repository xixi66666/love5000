package com.example.common.util;

import com.aliyun.oss.OSS;
import com.aliyun.oss.OSSClientBuilder;
import com.aliyun.oss.model.ObjectMetadata;
import com.aliyun.oss.model.PutObjectRequest;
import com.aliyun.oss.model.PutObjectResult;
import com.example.common.config.OssProperties;
import org.springframework.util.Assert;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.URISyntaxException;
import java.net.URLConnection;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

/**
 * 阿里云 OSS 操作工具：上传、删除、存在性判断、访问地址拼接与对象键解析。
 *
 * <p>属于基础工具层，由 {@code OssAutoConfiguration} 在 {@code love530.oss.enabled=true} 时创建，
 * 全部行为由构造时传入的 {@code OssProperties} 决定，类内不读取环境变量。</p>
 *
 * <p>几处非显然的取舍：</p>
 *
 * <p>一是每次调用都新建 {@code OSSClient} 并在 finally 中关闭，不做客户端复用。
 * 好处是无共享状态、可被多线程直接调用；代价是缺少连接池，不适合高并发批量上传。</p>
 *
 * <p>二是自动生成的对象键形如「目录/yyyy/MM/dd/UUID.扩展名」，日期取自 JVM 默认时区，
 * 跨时区部署时同一自然日的上传可能落到不同目录；需要可预先确定的存储位置时，
 * 应改用 {@link #uploadWithObjectKey} 由调用方先生成对象键。</p>
 *
 * <p>三是远端 SDK 异常一律包装为 {@code IllegalStateException} 并保留原始 cause，
 * 而空文件、非法对象键这类调用方错误抛 {@code IllegalArgumentException}，
 * 调用方据此区分「请求本身不合法」与「远端故障」。</p>
 */
public class OssUtil {

    /** 对象键中的日期目录格式，固定为 {@code yyyy/MM/dd}，使用 JVM 默认时区。 */
    private static final DateTimeFormatter DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyy/MM/dd");

    /**
     * 常见图片扩展名，仅在没有 contentType 且无法由文件名推断 MIME 时作为兜底判断依据；
     * 元素为小写、不带点。
     */
    private static final Set<String> IMAGE_EXTENSIONS = new HashSet<String>(
            Arrays.asList("jpg", "jpeg", "png", "gif", "bmp", "webp", "svg"));

    private final OssProperties ossProperties;

    /**
     * 使用给定配置构造工具；配置对象按引用持有，不做拷贝，运行期修改会立即影响后续调用。
     *
     * @param ossProperties 已完成绑定的 OSS 配置
     */
    public OssUtil(OssProperties ossProperties) {
        this.ossProperties = ossProperties;
    }

    /**
     * 上传到配置的默认目录（{@code love530.oss.base-dir}）。
     *
     * @param file 上传文件，不能为 {@code null}
     * @return 含对象键与访问地址的上传结果
     * @throws IllegalArgumentException 文件为空时抛出
     * @throws IllegalStateException 读取文件流或调用 OSS 失败时抛出
     */
    public OssUploadResult upload(MultipartFile file) {
        return upload(file, ossProperties.getBaseDir());
    }
    /**
     * 上传到指定目录，目录为空时回落到默认目录。
     *
     * @param file 上传文件，不能为 {@code null} 也不能为空文件
     * @param directory 目标目录，可带或不带首尾斜杠；空白时使用默认目录
     * @return 含对象键与访问地址的上传结果
     * @throws IllegalArgumentException 文件为 {@code null} 或内容为空时抛出
     * @throws IllegalStateException 读取文件流或调用 OSS 失败时抛出
     */
    public OssUploadResult upload(MultipartFile file, String directory) {
        Assert.notNull(file, "Upload file must not be null");
        if (file.isEmpty()) {
            throw new IllegalArgumentException("Upload file must not be empty");
        }

        try (InputStream inputStream = file.getInputStream()) {
            return upload(inputStream, file.getSize(), file.getOriginalFilename(), file.getContentType(), directory);
        } catch (IOException e) {
            throw new IllegalStateException("Failed to read upload file", e);
        }
    }

    /**
     * 以流的方式上传到默认目录，不指定内容类型。
     *
     * @param inputStream 数据流，由调用方负责关闭
     * @param contentLength 内容字节数；仅用于设置元数据，不与实际读取长度比对
     * @param originalFilename 原始文件名，用于推断扩展名与 MIME 类型
     * @return 含对象键与访问地址的上传结果
     */
    public OssUploadResult upload(InputStream inputStream, long contentLength, String originalFilename) {
        return upload(inputStream, contentLength, originalFilename, null, ossProperties.getBaseDir());
    }

    /**
     * 以流的方式上传到指定目录，对象键由当前时间与随机 UUID 自动生成。
     *
     * <p>因为键里包含随机段，返回值中的 {@code objectKey} 只代表本次调用实际写入的位置，
     * 调用方需要保留它才能在后续删除或补偿时定位对象。</p>
     *
     * @param inputStream 数据流，由调用方负责关闭
     * @param contentLength 内容字节数
     * @param originalFilename 原始文件名，可为 {@code null}
     * @param contentType 内容类型，可为 {@code null}，为空时按文件名推断
     * @param directory 目标目录，空白时使用默认目录
     * @return 含对象键与访问地址的上传结果
     */
    public OssUploadResult upload(InputStream inputStream, long contentLength, String originalFilename,
                                  String contentType, String directory) {
        Assert.notNull(inputStream, "Upload stream must not be null");

        String objectKey = buildObjectKey(directory, originalFilename);
        return uploadWithObjectKey(inputStream, contentLength, objectKey, originalFilename, contentType);
    }

    /**
     * 使用调用方预先生成的对象键上传。
     *
     * <p>适用于「先确定存储位置、再上传」的补偿型流程：即使上传后本地事务失败，
     * 调用方也已经知道对象键，可以按该键删除或重试，不会产生无法定位的孤儿对象。</p>
     *
     * <p>对象键会先经过 {@link #validateObjectKey} 校验；传入 {@code null} 流或非法键时
     * 在建立连接之前就失败，不会产生任何远端副作用。</p>
     *
     * @param inputStream 数据流，由调用方负责关闭
     * @param contentLength 内容字节数
     * @param objectKey 预声明的对象键，必须通过格式校验
     * @param originalFilename 原始文件名，可为 {@code null}，仅用于元数据与 MIME 推断
     * @param contentType 内容类型，可为 {@code null}
     * @return 含对象键与访问地址的上传结果
     * @throws IllegalArgumentException 数据流为 {@code null} 或对象键非法时抛出
     * @throws IllegalStateException 调用 OSS 失败时抛出
     */
    public OssUploadResult uploadWithObjectKey(InputStream inputStream, long contentLength,
                                               String objectKey, String originalFilename,
                                               String contentType) {
        Assert.notNull(inputStream, "Upload stream must not be null");
        String validatedObjectKey = validateObjectKey(objectKey);
        ObjectMetadata metadata = buildMetadata(contentLength, originalFilename, contentType);

        OSS ossClient = createClient();
        try {
            PutObjectRequest putObjectRequest =
                    new PutObjectRequest(ossProperties.getBucketName(), validatedObjectKey, inputStream, metadata);
            PutObjectResult result = ossClient.putObject(putObjectRequest);
            return new OssUploadResult(
                    ossProperties.getBucketName(),
                    validatedObjectKey,
                    getObjectUrl(validatedObjectKey),
                    result.getETag(),
                    originalFilename,
                    contentLength
            );
        } catch (Exception e) {
            throw new IllegalStateException("Failed to upload file to OSS", e);
        } finally {
            ossClient.shutdown();
        }
    }

    /**
     * 使用预声明对象键上传 {@code MultipartFile}。
     *
     * @param file 上传文件，不能为 {@code null} 也不能为空文件
     * @param objectKey 预声明的对象键
     * @param contentType 内容类型，可为 {@code null}
     * @return 含对象键与访问地址的上传结果
     * @throws IllegalArgumentException 文件为 {@code null}、内容为空或对象键非法时抛出
     * @throws IllegalStateException 读取文件流或调用 OSS 失败时抛出
     */
    public OssUploadResult uploadWithObjectKey(MultipartFile file, String objectKey, String contentType) {
        Assert.notNull(file, "Upload file must not be null");
        if (file.isEmpty()) {
            throw new IllegalArgumentException("Upload file must not be empty");
        }
        try (InputStream inputStream = file.getInputStream()) {
            return uploadWithObjectKey(inputStream, file.getSize(), objectKey,
                    file.getOriginalFilename(), contentType);
        } catch (IOException exception) {
            throw new IllegalStateException("Failed to read upload file", exception);
        }
    }

    /**
     * 校验并规范化 OSS 对象键。
     *
     * <p>规则：去首尾空格后长度不超过 500，不能以斜杠开头或结尾，不能出现反斜杠、连续双斜杠、
     * 问号或井号，不能含控制字符，按斜杠切分后不能有空段、单个点段或双点段。
     * 这些限制同时挡住越权覆盖其他前缀对象与路径穿越两类问题。</p>
     *
     * <p>本方法只做格式校验，不访问远端，也不校验 Bucket 是否存在。</p>
     *
     * @param objectKey 待校验的对象键
     * @return 去掉首尾空格后的对象键，可直接用于上传或删除
     * @throws IllegalArgumentException 为空白或不满足上述任一规则时抛出
     */
    public String validateObjectKey(String objectKey) {
        if (!StringUtils.hasText(objectKey)) {
            throw new IllegalArgumentException("OSS object key must not be blank");
        }
        String candidate = objectKey.trim();
        if (candidate.length() > 500 || candidate.startsWith("/") || candidate.endsWith("/")) {
            throw new IllegalArgumentException("Illegal OSS object key");
        }
        if (candidate.indexOf('\\') >= 0 || candidate.indexOf("//") >= 0
                || candidate.indexOf('?') >= 0 || candidate.indexOf('#') >= 0) {
            throw new IllegalArgumentException("Illegal OSS object key");
        }
        for (int index = 0; index < candidate.length(); index++) {
            if (Character.isISOControl(candidate.charAt(index))) {
                throw new IllegalArgumentException("Illegal OSS object key");
            }
        }
        String[] segments = candidate.split("/");
        for (String segment : segments) {
            if (segment.isEmpty() || ".".equals(segment) || "..".equals(segment)) {
                throw new IllegalArgumentException("Illegal OSS object key");
            }
        }
        return candidate;
    }

    /**
     * 判断对象是否存在。
     *
     * @param objectKeyOrUrl 对象键或完整访问 URL，内部会先解析成对象键
     * @return 对象存在时为 {@code true}
     * @throws IllegalArgumentException 入参为空白或 URL 无法解析时抛出
     * @throws IllegalStateException 调用 OSS 失败时抛出
     */
    public boolean exists(String objectKeyOrUrl) {
        String objectKey = extractObjectKey(objectKeyOrUrl);
        OSS ossClient = createClient();
        try {
            return ossClient.doesObjectExist(ossProperties.getBucketName(), objectKey);
        } catch (Exception e) {
            throw new IllegalStateException("Failed to check OSS object existence", e);
        } finally {
            ossClient.shutdown();
        }
    }

    /**
     * 删除对象。
     *
     * <p>幂等：先判断存在再删除，对象本就不存在时静默返回，不报错。
     * 存在期间被并发删除时，也只会让后续的删除调用失败，不影响最终状态。</p>
     *
     * @param objectKeyOrUrl 对象键或完整访问 URL
     * @throws IllegalArgumentException 入参为空白或 URL 无法解析时抛出
     * @throws IllegalStateException 调用 OSS 失败时抛出
     */
    public void delete(String objectKeyOrUrl) {
        String objectKey = extractObjectKey(objectKeyOrUrl);
        OSS ossClient = createClient();
        try {
            if (ossClient.doesObjectExist(ossProperties.getBucketName(), objectKey)) {
                ossClient.deleteObject(ossProperties.getBucketName(), objectKey);
            }
        } catch (Exception e) {
            throw new IllegalStateException("Failed to delete OSS object", e);
        } finally {
            ossClient.shutdown();
        }
    }

    /**
     * 生成对象的访问地址。
     *
     * <p>优先级：配置了 {@code url-prefix} 时以它为前缀；否则若 endpoint 自带协议，
     * 则在协议后插入 Bucket 名；两者都没有时按 {@code use-https} 选择协议，
     * 拼成 {@code bucket.endpoint} 形式。重复传入完整 URL 也会被解析后重新拼接。</p>
     *
     * @param objectKeyOrUrl 对象键或已拼好的 URL
     * @return 可公开访问的完整 URL
     * @throws IllegalArgumentException 入参为空白时抛出
     */
    public String getObjectUrl(String objectKeyOrUrl) {
        String objectKey = extractObjectKey(objectKeyOrUrl);
        if (StringUtils.hasText(ossProperties.getUrlPrefix())) {
            return joinUrl(trimTrailingSlash(ossProperties.getUrlPrefix().trim()), objectKey);
        }

        String endpoint = trimTrailingSlash(ossProperties.getEndpoint().trim());
        if (endpoint.startsWith("http://") || endpoint.startsWith("https://")) {
            return joinUrl(endpoint.replace("://", "://" + ossProperties.getBucketName() + "."), objectKey);
        }

        String schema = ossProperties.isUseHttps() ? "https://" : "http://";
        return joinUrl(schema + ossProperties.getBucketName() + "." + endpoint, objectKey);
    }

    /**
     * 从对象键或 URL 中解析出对象键。
     *
     * <p>支持三种输入：以 {@code url-prefix} 开头的自定义域名 URL（按前缀截断）、
     * 普通 http 或 https URL（取 path 部分）、以及已经是对象键的字符串。
     * 解析结果会去掉开头的斜杠以及 query、fragment，便于直接用于 OSS API。</p>
     *
     * @param objectKeyOrUrl 对象键或 URL
     * @return Bucket 内的对象键
     * @throws IllegalArgumentException 入参为空白或 URL 语法非法时抛出
     */
    public String extractObjectKey(String objectKeyOrUrl) {
        if (!StringUtils.hasText(objectKeyOrUrl)) {
            throw new IllegalArgumentException("OSS object key must not be blank");
        }

        String candidate = objectKeyOrUrl.trim();
        if (StringUtils.hasText(ossProperties.getUrlPrefix())) {
            String urlPrefix = trimTrailingSlash(ossProperties.getUrlPrefix().trim());
            if (candidate.startsWith(urlPrefix)) {
                return sanitizeObjectKey(candidate.substring(urlPrefix.length()));
            }
        }

        if (candidate.startsWith("http://") || candidate.startsWith("https://")) {
            try {
                return sanitizeObjectKey(new URI(candidate).getPath());
            } catch (URISyntaxException e) {
                throw new IllegalArgumentException("Illegal OSS url: " + candidate, e);
            }
        }

        return sanitizeObjectKey(candidate.replace("\\", "/"));
    }

    /**
     * 按当前配置创建 OSS 客户端；每次调用都是新实例，必须由调用方在 finally 中关闭。
     *
     * @return 新建的客户端实例
     */
    private OSS createClient() {
        return new OSSClientBuilder().build(
                ossProperties.getEndpoint(),
                ossProperties.getAccessKeyId(),
                ossProperties.getAccessKeySecret()
        );
    }

    /**
     * 生成「目录/日期/UUID.扩展名」形式的对象键；目录为空时省略前缀，无扩展名时省略后缀。
     *
     * @param directory 目标目录，空白时回落到默认目录
     * @param originalFilename 原始文件名，用于取扩展名
     * @return 自动生成的对象键
     */
    private String buildObjectKey(String directory, String originalFilename) {
        String normalizedDirectory = normalizeDirectory(directory);
        String datePath = LocalDate.now().format(DATE_FORMATTER);
        String extension = getExtension(originalFilename);

        StringBuilder objectKeyBuilder = new StringBuilder();
        if (StringUtils.hasText(normalizedDirectory)) {
            objectKeyBuilder.append(normalizedDirectory).append("/");
        }
        objectKeyBuilder.append(datePath).append("/").append(UUID.randomUUID());
        if (StringUtils.hasText(extension)) {
            objectKeyBuilder.append(".").append(extension);
        }
        return objectKeyBuilder.toString();
    }

    /**
     * 组装对象元数据：内容长度、内容类型与 {@code no-cache} 缓存策略。
     *
     * @param contentLength 内容字节数，负数表示未知，此时不设置长度
     * @param originalFilename 原始文件名，用于推断 MIME
     * @param contentType 调用方给定的内容类型，优先使用
     * @return 填充完成的元数据对象
     */
    private ObjectMetadata buildMetadata(long contentLength, String originalFilename, String contentType) {
        ObjectMetadata metadata = new ObjectMetadata();
        if (contentLength >= 0) {
            metadata.setContentLength(contentLength);
        }
        metadata.setContentType(resolveContentType(originalFilename, contentType));
        metadata.setCacheControl("no-cache");
        return metadata;
    }

    /**
     * 解析内容类型：调用方给定值优先，其次是文件名推断，最后兜底为二进制流。
     *
     * @param originalFilename 原始文件名，可为 {@code null}
     * @param contentType 调用方给定的内容类型，可为 {@code null}
     * @return 非空的 MIME 字符串
     */
    private String resolveContentType(String originalFilename, String contentType) {
        if (StringUtils.hasText(contentType)) {
            return contentType;
        }

        if (StringUtils.hasText(originalFilename)) {
            String detectedContentType = URLConnection.getFileNameMap().getContentTypeFor(originalFilename);
            if (StringUtils.hasText(detectedContentType)) {
                return detectedContentType;
            }

            String extension = getExtension(originalFilename);
            if (IMAGE_EXTENSIONS.contains(extension)) {
                if ("svg".equals(extension)) {
                    return "image/svg+xml";
                }
                return "image/" + ("jpg".equals(extension) ? "jpeg" : extension);
            }
        }

        return "application/octet-stream";
    }

    /**
     * 归一化上传目录：去空格、反斜杠转正斜杠、去掉首尾斜杠；空白时回落到配置的默认目录。
     *
     * @param directory 原始目录，可为 {@code null}
     * @return 不带首尾斜杠的目录，配置也为空时返回空串
     */
    private String normalizeDirectory(String directory) {
        String finalDirectory = StringUtils.hasText(directory) ? directory : ossProperties.getBaseDir();
        if (!StringUtils.hasText(finalDirectory)) {
            return "";
        }
        return stripLeadingSlash(trimTrailingSlash(finalDirectory.trim().replace("\\", "/")));
    }

    /**
     * 取小写扩展名（不含点）；文件名缺失或没有扩展名时返回空串。
     *
     * @param originalFilename 原始文件名，可为 {@code null}
     * @return 小写扩展名或空串
     */
    private String getExtension(String originalFilename) {
        if (!StringUtils.hasText(originalFilename) || !originalFilename.contains(".")) {
            return "";
        }
        return originalFilename.substring(originalFilename.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT);
    }

    /**
     * 拼接前缀与对象键，自动去掉两侧重复的斜杠，保证结果只有一个分隔符。
     *
     * @param prefix URL 前缀
     * @param objectKey 对象键
     * @return 拼接后的地址
     */
    private String joinUrl(String prefix, String objectKey) {
        return trimTrailingSlash(prefix) + "/" + stripLeadingSlash(objectKey);
    }

    /**
     * 去掉结尾的全部斜杠；用于容忍配置里手写的多余分隔符。
     *
     * @param value 原始字符串，不允许为 {@code null}
     * @return 不含结尾斜杠的字符串
     */
    private String trimTrailingSlash(String value) {
        String result = value;
        while (result.endsWith("/")) {
            result = result.substring(0, result.length() - 1);
        }
        return result;
    }

    /**
     * 去掉开头的全部斜杠；{@code null} 按空串处理。
     *
     * @param value 原始字符串，可为 {@code null}
     * @return 不含开头斜杠的字符串
     */
    private String stripLeadingSlash(String value) {
        if (value == null) {
            return "";
        }

        String result = value;
        while (result.startsWith("/")) {
            result = result.substring(1);
        }
        return result;
    }

    /**
     * 去掉开头斜杠以及 query、fragment，得到可直接用于 OSS API 的对象键。
     *
     * @param value 解析出的路径片段
     * @return 净化后的对象键
     */
    private String sanitizeObjectKey(String value) {
        String normalized = stripLeadingSlash(value);
        int queryIndex = normalized.indexOf('?');
        if (queryIndex >= 0) {
            normalized = normalized.substring(0, queryIndex);
        }
        int fragmentIndex = normalized.indexOf('#');
        if (fragmentIndex >= 0) {
            normalized = normalized.substring(0, fragmentIndex);
        }
        return normalized;
    }
}
