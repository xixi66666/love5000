package com.ycxandwuqian.love.service;

import com.example.common.util.OssUploadResult;
import com.example.common.util.OssUtil;
import com.ycxandwuqian.love.dao.PhotoDao;
import com.ycxandwuqian.love.model.PhotoRecord;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.interceptor.TransactionAspectSupport;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * 照片墙的业务实现。
 *
 * <p>位于服务层：负责参数校验、对象键规划、OSS 读写、记录落库与响应组装。
 * 数据库访问全部通过 {@link PhotoDao}（SQL 在 {@code PhotoMapper.xml}），
 * 对象存储通过 {@link ObjectProvider} 延迟获取，OSS 关闭时容器中没有对应 Bean，
 * 此时上传接口返回 "OSS is not configured" 的可读失败，服务本身仍可启动。</p>
 *
 * <p>两个关键的补偿设计：</p>
 * <ul>
 *   <li>上传走"先定对象键、再上传"的路径（{@code uploadWithObjectKey}），因此即使 OSS 已经写入
 *       对象而响应丢失或落库失败，也能按同一个键把孤儿对象删掉，不会在 Bucket 里留下无主文件。</li>
 *   <li>删除先删数据库记录、后删 OSS 对象；OSS 清理失败时把事务标记为回滚，
 *       让记录与对象一起保留，而不是留下"记录已删、对象还在"的悬空状态。</li>
 * </ul>
 *
 * <p>所有方法都返回 {@code {success, message, ...}} 形式的 Map，失败通过 {@code message} 表达。</p>
 */
@Service
public class PhotoServiceImpl implements PhotoService {

    /** 仅在补偿删除失败时使用：记录被遗弃的对象键，便于运维按日志清理。 */
    private static final Logger LOGGER = LoggerFactory.getLogger(PhotoServiceImpl.class);

    /** 允许的照片分类，同时作为 OSS 对象键中的二级目录名。 */
    private static final Set<String> ALLOWED_CATEGORIES =
            new HashSet<String>(Arrays.asList("cat", "girl", "us"));

    /** 响应里的时间格式，固定 {@code yyyy-MM-dd HH:mm:ss}，与前端展示一致。 */
    private static final DateTimeFormatter TIME_FORMATTER =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    /** 对象键中的日期分层格式，按天分目录，避免单目录对象过多。 */
    private static final DateTimeFormatter OBJECT_KEY_DATE_FORMATTER =
            DateTimeFormatter.ofPattern("yyyy/MM/dd");

    /** 照片在 OSS 上的根目录，实际对象键在其后追加分类、日期与随机文件名。 */
    private static final String PHOTO_DIRECTORY = "love530/lovestory/photos";

    /** 日志中对象键的最大输出长度，防止异常输入把日志行撑爆。 */
    private static final int MAX_LOG_VALUE_LENGTH = 200;

    /** OSS 工具的延迟提供者；{@code getIfAvailable()} 返回 {@code null} 表示 OSS 未启用。 */
    private final ObjectProvider<OssUtil> ossUtilProvider;

    /** 照片表 DAO，由 MyBatis 的 Mapper 代理实现。 */
    private final PhotoDao photoDao;

    /**
     * 创建业务实现。
     *
     * @param ossUtilProvider OSS 工具的延迟提供者，不能为 {@code null}，但允许取不到实例
     * @param photoDao        照片表 DAO，不能为 {@code null}
     */
    public PhotoServiceImpl(ObjectProvider<OssUtil> ossUtilProvider, PhotoDao photoDao) {
        this.ossUtilProvider = ossUtilProvider;
        this.photoDao = photoDao;
    }

    /**
     * 上传照片：规划对象键、写 OSS、落库，失败时补偿删除已写入的对象。
     *
     * <p>校验顺序为"文件非空 → 图片后缀 → 分类白名单 → OSS 可用性"，全部通过后才规划对象键；
     * 对象键形如 {@code love530/lovestory/photos/{category}/{yyyy}/{MM}/{dd}/{uuid}.{ext}}，
     * 上传前即已确定，因此 OSS 响应异常或落库失败都能按同一个键回收。
     * 上传结果里的对象键必须与预声明值一致，否则视为上传不可信并抛出异常、触发补偿。</p>
     *
     * <p>本方法未声明 {@code @Transactional}：照片上传只有一条 insert，失败时由补偿删除处理，
     * 不需要数据库事务参与。</p>
     *
     * @param file        图片文件，必填且不得为空；后缀仅允许 jpg、jpeg、png、gif、webp（忽略大小写）
     * @param category    分类，必填，取值 cat、girl、us；会先 trim 并转小写再校验
     * @param description 展示用描述，可为 {@code null} 或空白；有值时 trim 后原样透出
     * @return 成功时含 {@code url} 与 {@code photo} 摘要；参数非法、OSS 未配置、
     *         上传或落库失败时返回 {@code success=false} 与可读原因（运行时异常不外抛）
     */
    @Override
    public Map<String, Object> uploadPhoto(MultipartFile file, String category, String description) {
        Map<String, Object> response = new HashMap<String, Object>();

        if (file == null || file.isEmpty()) {
            return failure(response, "Please select a file");
        }

        String originalFilename = file.getOriginalFilename();
        if (!isSupportedImage(originalFilename)) {
            return failure(response, "Only jpg, jpeg, png, gif and webp images are supported");
        }

        String normalizedCategory = normalizeCategory(category);
        if (!ALLOWED_CATEGORIES.contains(normalizedCategory)) {
            return failure(response, "Unsupported photo category");
        }

        OssUtil ossUtil = ossUtilProvider.getIfAvailable();
        if (ossUtil == null) {
            return failure(response, "OSS is not configured");
        }

        String sanitizedDescription = StringUtils.hasText(description) ? description.trim() : "";
        String objectKey = buildPhotoObjectKey(normalizedCategory, originalFilename);
        boolean uploadAttempted = false;
        boolean persisted = false;

        try {
            // 先确定对象键，再调用 OSS；即使 OSS 接受对象后本地响应异常，也能按该键补偿。
            uploadAttempted = true;
            OssUploadResult uploadResult =
                    ossUtil.uploadWithObjectKey(file, objectKey, file.getContentType());
            if (uploadResult == null
                    || !objectKey.equals(trimToEmpty(uploadResult.getObjectKey()))) {
                throw new IllegalStateException("Uploaded object key could not be confirmed");
            }

            String url = resolveUploadUrl(ossUtil, uploadResult, objectKey);
            PhotoRecord photoRecord = new PhotoRecord();
            photoRecord.setPath(objectKey);
            photoRecord.setType(normalizedCategory);
            photoRecord.setCreateTime(LocalDateTime.now());

            if (photoDao.insert(photoRecord) <= 0) {
                throw new IllegalStateException("Failed to save photo record");
            }
            persisted = true;

            response.put("success", true);
            response.put("message", "Upload succeeded");
            response.put("url", url);
            response.put("photo", buildPhotoResponse(
                    url, normalizedCategory, sanitizedDescription, photoRecord));
            return response;
        } catch (RuntimeException uploadFailure) {
            if (uploadAttempted && !persisted) {
                compensateUploadedObject(ossUtil, objectKey, uploadFailure);
            }
            return failure(response, "Upload failed: " + failureMessage(uploadFailure));
        }
    }

    /**
     * 查询照片列表并解析访问地址。
     *
     * <p>数据库里存的是 OSS 对象键，这里逐条交给 {@link #resolvePhotoUrl(String)} 转成 URL，
     * 不改写数据库。描述由"分类标签 · 上传时间"拼成（例如 {@code Cat · 2026-05-01 12:30:00}），
     * 前端不需要再拼文案。数据库异常被就地捕获，返回 {@code success=false} 与空列表，
     * 页面据此渲染空态。</p>
     *
     * @return 成功时含按上传时间倒序的 {@code photos}；失败时含错误说明与空列表
     */
    @Override
    public Map<String, Object> listPhotos() {
        Map<String, Object> response = new HashMap<String, Object>();

        try {
            List<Map<String, Object>> photos = photoDao.findAll().stream()
                    .map(photoRecord -> buildPhotoResponse(
                            resolvePhotoUrl(photoRecord.getPath()),
                            photoRecord.getType(),
                            buildDefaultDescription(photoRecord),
                            photoRecord))
                    .collect(Collectors.toList());
            response.put("success", true);
            response.put("photos", photos);
        } catch (DataAccessException e) {
            response.put("success", false);
            response.put("message", "Failed to load photos: " + failureMessage(e));
            response.put("photos", Collections.emptyList());
        }

        return response;
    }

    /**
     * 删除照片：先删数据库记录，成功后再清理 OSS 对象。
     *
     * <p>顺序不可颠倒：若先删对象再删记录，一旦数据库删除失败，列表里就会出现打不开的图片。
     * 反过来，记录删除成功但 OSS 清理失败时，这里会把当前事务标记为回滚，
     * 让数据库删除一并撤销，保持记录与对象同生共死。{@code deleteById} 返回 0 行时再查一次：
     * 记录已不存在说明是并发或重复删除，按目标状态返回成功；仍存在则报失败。</p>
     *
     * @param id 照片主键
     * @return 成功时含 {@code success=true} 与回显的 {@code id}；记录不存在、删除失败或
     *         OSS 清理失败时返回 {@code success=false} 与原因
     */
    @Override
    @Transactional
    public Map<String, Object> deletePhoto(Long id) {
        Map<String, Object> response = new HashMap<String, Object>();

        try {
            PhotoRecord photoRecord = photoDao.findById(id);
            if (photoRecord == null) {
                return failure(response, "Photo not found");
            }

            // 先确认数据库记录删除成功，避免 OSS 已删除但照片记录仍留在列表里。
            if (photoDao.deleteById(id) <= 0) {
                if (photoDao.findById(id) == null) {
                    // 并发或重复的删除请求：记录已经被另一请求删除，按目标状态返回成功。
                    return deleted(response, id);
                }
                return failure(response, "Failed to delete photo record");
            }

            OssUtil ossUtil = ossUtilProvider.getIfAvailable();
            if (ossUtil != null && StringUtils.hasText(photoRecord.getPath())) {
                ossUtil.delete(photoRecord.getPath());
            }

            return deleted(response, id);
        } catch (RuntimeException deleteFailure) {
            // deletePhoto 由 Spring 事务代理调用；OSS 清理失败时回滚刚完成的数据库删除，
            // 让记录和对象保持同一状态，而不是留下指向已删除对象的照片记录。
            markRollbackOnlyIfActive();
            return failure(response, "Delete failed: " + failureMessage(deleteFailure));
        }
    }

    /**
     * 统一的失败响应写法：只放 {@code success=false} 与可读原因，不带 id 或列表字段，
     * 前端据此判定失败。
     *
     * @param response 复用的响应 Map，避免每个分支都新建
     * @param message  给用户看的原因
     * @return 传入的同一个 Map，便于直接 {@code return failure(...)}
     */
    private Map<String, Object> failure(Map<String, Object> response, String message) {
        response.put("success", false);
        response.put("message", message);
        return response;
    }

    /**
     * 统一的"已删除"成功响应，含 {@code success}、{@code message} 与被删 id。
     *
     * @param response 复用的响应 Map
     * @param id       已删除照片的主键
     * @return 传入的同一个 Map
     */
    private Map<String, Object> deleted(Map<String, Object> response, Long id) {
        response.put("success", true);
        response.put("message", "Photo deleted");
        response.put("id", id);
        return response;
    }

    /**
     * 规划照片的对象键：{@code love530/lovestory/photos/{category}/{yyyy/MM/dd}/{uuid}.{ext}}。
     *
     * <p>随机 UUID 保证同名文件不互相覆盖；日期分层便于按前缀做生命周期管理；
     * 原始文件名不进入对象键，避免中文、空格或特殊字符造成编码问题，只保留规范化后的后缀。</p>
     *
     * @param category         已校验的分类，直接作为二级目录
     * @param originalFilename 原始文件名，用于取后缀；无后缀时对象键没有扩展名
     * @return 完整对象键（相对 Bucket 根，不带前导斜杠）
     */
    private String buildPhotoObjectKey(String category, String originalFilename) {
        StringBuilder objectKey = new StringBuilder(PHOTO_DIRECTORY)
                .append('/')
                .append(category)
                .append('/')
                .append(LocalDate.now().format(OBJECT_KEY_DATE_FORMATTER))
                .append('/')
                .append(UUID.randomUUID());
        String extension = getExtension(originalFilename);
        if (StringUtils.hasText(extension)) {
            objectKey.append('.').append(extension);
        }
        return objectKey.toString();
    }

    /**
     * 优先取上传结果里的访问地址，缺失时按对象键反推。
     *
     * @param ossUtil      已确认可用的 OSS 工具实例
     * @param uploadResult 上传返回值，可为 {@code null}
     * @param objectKey    预声明的对象键，用作反推依据
     * @return 可访问地址；反推也拿不到时返回空串，保证响应结构稳定
     */
    private String resolveUploadUrl(OssUtil ossUtil, OssUploadResult uploadResult, String objectKey) {
        if (uploadResult != null && StringUtils.hasText(uploadResult.getUrl())) {
            return uploadResult.getUrl();
        }
        String url = ossUtil.getObjectUrl(objectKey);
        return url == null ? "" : url;
    }

    /**
     * 补偿删除已经写入 OSS 的孤儿对象。
     *
     * <p>清理本身也可能失败（网络、权限、OSS 已关闭）。此时不改变对外报错，
     * 而是把清理异常挂到原始失败的 suppressed 列表上，并打一条警告日志，
     * 既保留根因，又不让清理失败掩盖真正的错误。</p>
     *
     * @param ossUtil         已确认可用的 OSS 工具实例
     * @param objectKey       预声明的对象键；为空时不做任何事
     * @param originalFailure 触发补偿的原始异常，用于附加 suppressed 与决定是否记录日志
     */
    private void compensateUploadedObject(OssUtil ossUtil, String objectKey, RuntimeException originalFailure) {
        if (!StringUtils.hasText(objectKey)) {
            return;
        }
        try {
            ossUtil.delete(objectKey);
        } catch (RuntimeException cleanupFailure) {
            if (cleanupFailure != originalFailure) {
                originalFailure.addSuppressed(cleanupFailure);
            }
            LOGGER.warn("Failed to remove orphaned photo object, objectKey="
                    + sanitizeForLog(objectKey), cleanupFailure);
        }
    }

    /**
     * 仅在确实处于事务中时把当前事务标记为回滚。
     *
     * <p>删除失败需要撤销已完成的数据库删除，但同一方法也可能在事务代理之外被调用
     * （例如单元测试直接 new 出实例），此时 {@code currentTransactionStatus()} 会抛
     * {@code NoTransactionException}，因此先做判断。</p>
     */
    private void markRollbackOnlyIfActive() {
        if (TransactionSynchronizationManager.isActualTransactionActive()) {
            TransactionAspectSupport.currentTransactionStatus().setRollbackOnly();
        }
    }

    /**
     * 判断文件名是否属于允许的图片类型。
     *
     * @param originalFilename 原始文件名，可为 {@code null}
     * @return 命中 jpg/jpeg/png/gif/webp（忽略大小写）返回 {@code true}；
     *         文件名缺失或不匹配返回 {@code false}
     */
    private boolean isSupportedImage(String originalFilename) {
        if (!StringUtils.hasText(originalFilename)) {
            return false;
        }

        String lowerCaseName = originalFilename.toLowerCase(Locale.ROOT);
        return lowerCaseName.matches(".*\\.(jpg|jpeg|png|gif|webp)$");
    }

    /**
     * 归一化分类：去首尾空白并转小写，空值转成空串。
     *
     * @param category 前端提交的分类，可为 {@code null}
     * @return 归一化后的分类；空串会在后续白名单校验中被拒绝
     */
    private String normalizeCategory(String category) {
        if (!StringUtils.hasText(category)) {
            return "";
        }
        return category.trim().toLowerCase(Locale.ROOT);
    }

    /**
     * 取小写后缀（不含点），用最后一个点切分以兼容多点的文件名。
     *
     * @param originalFilename 原始文件名，可为 {@code null}
     * @return 小写后缀；文件名缺失或不含点时返回空串
     */
    private String getExtension(String originalFilename) {
        if (!StringUtils.hasText(originalFilename) || !originalFilename.contains(".")) {
            return "";
        }
        return originalFilename.substring(originalFilename.lastIndexOf('.') + 1)
                .toLowerCase(Locale.ROOT);
    }

    /**
     * 把库里的路径解析成可访问 URL。
     *
     * <p>空值返回空串；已是 {@code http(s)://} 的完整地址原样返回（兼容历史数据或外链）；
     * 其余当作 OSS 对象键交给 {@code OssUtil#getObjectUrl} 拼接。OSS 未启用时返回原始对象键，
     * 页面可能加载不到图，但不会因为缺 Bean 抛异常。</p>
     *
     * @param path 数据库中的 {@code photo.path}
     * @return 可访问地址；无法解析时返回原始值
     */
    private String resolvePhotoUrl(String path) {
        if (!StringUtils.hasText(path)) {
            return "";
        }

        if (path.startsWith("http://") || path.startsWith("https://")) {
            return path;
        }

        OssUtil ossUtil = ossUtilProvider.getIfAvailable();
        if (ossUtil == null) {
            return path;
        }
        return ossUtil.getObjectUrl(path);
    }

    /**
     * 生成列表项的默认描述：{@code 分类标签 · 创建时间}。
     *
     * @param photoRecord 数据库记录；创建时间为空时只返回分类标签
     * @return 用于前端展示的描述文案
     */
    private String buildDefaultDescription(PhotoRecord photoRecord) {
        String categoryLabel = categoryLabel(photoRecord.getType());
        if (photoRecord.getCreateTime() == null) {
            return categoryLabel;
        }
        return categoryLabel + " · " + TIME_FORMATTER.format(photoRecord.getCreateTime());
    }

    /**
     * 组装单个照片的响应结构，字段顺序固定，便于前端与调试时比对。
     *
     * <p>{@code id} 只在记录非空时写入（此时可能尚未回填，值为 {@code null}），
     * {@code createTime} 还需要字段本身有值才写入；描述为空时回落到分类标签，
     * 保证前端永远拿到可展示的文案。</p>
     *
     * @param url         已解析的可访问地址
     * @param category    分类标识
     * @param description 用户填写的描述，可为空白
     * @param photoRecord 数据库记录，可为 {@code null}
     * @return 含 id、创建时间、url、分类与描述的响应 Map
     */
    private Map<String, Object> buildPhotoResponse(String url, String category,
                                                   String description, PhotoRecord photoRecord) {
        Map<String, Object> photo = new LinkedHashMap<String, Object>();
        if (photoRecord != null) {
            photo.put("id", photoRecord.getId());
            if (photoRecord.getCreateTime() != null) {
                photo.put("createTime", TIME_FORMATTER.format(photoRecord.getCreateTime()));
            }
        }
        photo.put("url", url);
        photo.put("category", category);
        photo.put("description",
                StringUtils.hasText(description) ? description : categoryLabel(category));
        return photo;
    }

    /**
     * 分类标识到展示标签的映射。
     *
     * @param category 分类标识，大小写不敏感
     * @return 固定标签 Cat、Girl、Us；未知分类回落到 Memory，保证列表文案不为空
     */
    private String categoryLabel(String category) {
        if ("cat".equalsIgnoreCase(category)) {
            return "Cat";
        }
        if ("girl".equalsIgnoreCase(category)) {
            return "Girl";
        }
        if ("us".equalsIgnoreCase(category)) {
            return "Us";
        }
        return "Memory";
    }

    /**
     * 提取可直接拼进响应与日志的失败信息。
     *
     * @param failure 捕获到的异常，不应为 {@code null}
     * @return 异常的 message；message 为空时退化为异常类简单名，
     *         避免出现 "Upload failed: null" 这种无法定位问题的文案
     */
    private String failureMessage(Throwable failure) {
        String message = failure.getMessage();
        return StringUtils.hasText(message) ? message : failure.getClass().getSimpleName();
    }

    private String trimToEmpty(String value) {
        return value == null ? "" : value.trim();
    }

    /**
     * 清洗要写进警告日志的对象键：控制字符替换为问号并限长。
     *
     * <p>对象键由程序生成，理论上不含控制字符；这里仍然兜底清洗与截断，
     * 防止异常值把单行日志打断或撑爆。只影响日志输出，不改变传给 OSS 的真实值。</p>
     *
     * @param value 原始对象键，可为 {@code null}
     * @return 适合单行输出的字符串；{@code null} 转为空串
     */
    private String sanitizeForLog(String value) {
        if (value == null) {
            return "";
        }
        String sanitized = value.replaceAll("[\\p{Cntrl}]", "?");
        return sanitized.length() > MAX_LOG_VALUE_LENGTH
                ? sanitized.substring(0, MAX_LOG_VALUE_LENGTH)
                : sanitized;
    }
}
