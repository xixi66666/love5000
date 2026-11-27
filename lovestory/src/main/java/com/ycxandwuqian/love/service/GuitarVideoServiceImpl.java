package com.ycxandwuqian.love.service;

import com.example.common.util.OssUploadResult;
import com.example.common.util.OssUtil;
import com.ycxandwuqian.love.dao.GuitarVideoDao;
import com.ycxandwuqian.love.model.GuitarVideoRecord;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

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
import java.util.stream.Collectors;

/**
 * 吉他视频卡片的业务实现。
 *
 * <p>位于服务层：负责标题与后缀校验、OSS 上传（视频与可选封面）、记录组装、
 * 软删除以及响应字段归一化。数据库访问全部下沉到 {@link GuitarVideoDao}，
 * 对象存储通过 {@link ObjectProvider} 延迟获取——OSS 关闭时容器中不存在对应 Bean。</p>
 *
 * <p>非显然行为：</p>
 * <ul>
 *   <li>OSS 不可用时上传类接口返回 {@code success=false}（"OSS is not configured"），
 *       而列表与删除仍然可用：删除在无 OSS 时只做数据库软删除。</li>
 *   <li>{@code @Transactional} 只覆盖数据库写入，OSS 操作不参与事务。视频已上传但
 *       insert 失败会留下孤儿对象，本类不做补偿删除（照片业务在 {@code PhotoServiceImpl}
 *       中才有该补偿），需要时按 OSS 目录人工清理。</li>
 *   <li>响应中的视频/封面地址会尽量解析成可访问 URL；数据库里存的是完整 URL 时原样返回。</li>
 * </ul>
 */
@Service
public class GuitarVideoServiceImpl implements GuitarVideoService {

    /** 视频在 OSS 上的存放目录，相对 Bucket 根，不带首尾斜杠。 */
    private static final String VIDEO_DIRECTORY = "love530/lovestory/videos";

    /** 封面图在 OSS 上的存放目录，与视频目录同级嵌套，便于按前缀批量清理。 */
    private static final String COVER_DIRECTORY = "love530/lovestory/videos/covers";

    /** 展示状态值，对应 {@code guitar_video.status}，1 显示、0 隐藏。 */
    private static final int DISPLAY_STATUS = 1;

    /** 响应里的时间格式，固定 {@code yyyy-MM-dd HH:mm:ss}，与前端卡片展示保持一致。 */
    private static final DateTimeFormatter TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    /** 允许的视频后缀（小写比较），不在集合内的后缀会在上传 OSS 之前被拒。 */
    private static final Set<String> VIDEO_EXTENSIONS =
            new HashSet<String>(Arrays.asList("mp4", "webm", "mov"));

    /** 允许的封面图后缀（小写比较），比照片业务少了 gif，与前端截帧输出对齐。 */
    private static final Set<String> IMAGE_EXTENSIONS =
            new HashSet<String>(Arrays.asList("jpg", "jpeg", "png", "webp"));

    /** OSS 工具的延迟提供者；{@code getIfAvailable()} 返回 {@code null} 表示 OSS 未启用。 */
    private final ObjectProvider<OssUtil> ossUtilProvider;

    /** 视频表 DAO，由 MyBatis 的 Mapper 代理实现。 */
    private final GuitarVideoDao guitarVideoDao;

    /**
     * 创建业务实现。
     *
     * @param ossUtilProvider OSS 工具的延迟提供者，不能为 {@code null}，但允许取不到实例
     * @param guitarVideoDao  视频表 DAO，不能为 {@code null}
     */
    public GuitarVideoServiceImpl(ObjectProvider<OssUtil> ossUtilProvider, GuitarVideoDao guitarVideoDao) {
        this.ossUtilProvider = ossUtilProvider;
        this.guitarVideoDao = guitarVideoDao;
    }

    /**
     * 查询展示中的视频卡片并组装为前端结构。
     *
     * <p>数据库异常被就地捕获：返回 {@code success=false} 与空列表，让前端可以整块隐藏
     * 视频模块而不影响照片墙和留言板，也不把异常栈抛到页面。</p>
     *
     * @return 成功时含 {@code success=true} 与 {@code videos}；失败时含错误说明与空列表
     */
    @Override
    public Map<String, Object> listVideos() {
        Map<String, Object> response = new HashMap<String, Object>();
        try {
            List<Map<String, Object>> videos = guitarVideoDao.findVisible().stream()
                    .map(this::buildVideoResponse)
                    .collect(Collectors.toList());
            response.put("success", true);
            response.put("videos", videos);
        } catch (DataAccessException e) {
            response.put("success", false);
            response.put("message", "Failed to load videos: " + e.getMessage());
            response.put("videos", Collections.emptyList());
        }
        return response;
    }

    /**
     * 上传视频（可选封面）并写入视频表。
     *
     * <p>校验按"标题 → 视频文件 → 视频后缀 → 封面后缀 → OSS 可用性"的顺序短路，
     * 任一步失败都只返回可读的 {@code message}，不会访问 OSS 或数据库。
     * 通过后先用 {@code OssUtil#upload} 上传视频（得到目录内的随机对象键与访问地址），
     * 再按需上传封面，最后落库；标题、描述、标签会先去空白再按列宽截断，
     * 未提供封面时 {@code cover_url} 存空串而不是 {@code null}，前端据此判断是否显示占位图。</p>
     *
     * <p>事务只包住数据库写入：OSS 上传成功后若插入失败，已上传的对象不会被回滚或删除。</p>
     *
     * @param file        视频文件，必填且不得为空；后缀仅允许 mp4、webm、mov
     * @param cover       封面图，可为 {@code null}；非空时后缀仅允许 jpg、jpeg、png、webp
     * @param title       标题，去空白后不得为空，落库截断到 100 字符
     * @param description 描述，可为 {@code null}，落库截断到 500 字符
     * @param tag         标签，可为 {@code null}，落库截断到 50 字符
     * @param sortOrder   排序值，为 {@code null} 时按 0 处理
     * @return 成功时含 {@code video} 摘要（含数据库回填的 id），失败时含 {@code success=false}
     *         与原因；{@code IllegalArgumentException}、{@code IllegalStateException} 与
     *         {@code DataAccessException} 会被就地转成失败响应，其余运行时异常仍向上抛出
     */
    @Override
    @Transactional
    public Map<String, Object> uploadVideo(MultipartFile file, MultipartFile cover, String title,
                                           String description, String tag, Integer sortOrder) {
        Map<String, Object> response = new HashMap<String, Object>();

        String normalizedTitle = normalizeText(title);
        if (!StringUtils.hasText(normalizedTitle)) {
            response.put("success", false);
            response.put("message", "Video title must not be blank");
            return response;
        }

        if (file == null || file.isEmpty()) {
            response.put("success", false);
            response.put("message", "Please select a video file");
            return response;
        }

        if (!hasAllowedExtension(file.getOriginalFilename(), VIDEO_EXTENSIONS)) {
            response.put("success", false);
            response.put("message", "Only mp4, webm and mov videos are supported");
            return response;
        }

        if (cover != null && !cover.isEmpty() && !hasAllowedExtension(cover.getOriginalFilename(), IMAGE_EXTENSIONS)) {
            response.put("success", false);
            response.put("message", "Only jpg, jpeg, png and webp covers are supported");
            return response;
        }

        OssUtil ossUtil = ossUtilProvider.getIfAvailable();
        if (ossUtil == null) {
            response.put("success", false);
            response.put("message", "OSS is not configured");
            return response;
        }

        try {
            OssUploadResult videoUpload = ossUtil.upload(file, VIDEO_DIRECTORY);
            String coverUrl = "";
            if (cover != null && !cover.isEmpty()) {
                coverUrl = ossUtil.upload(cover, COVER_DIRECTORY).getUrl();
            }

            GuitarVideoRecord record = new GuitarVideoRecord();
            record.setTitle(truncate(normalizedTitle, 100));
            record.setDescription(truncate(normalizeText(description), 500));
            record.setTag(truncate(normalizeText(tag), 50));
            record.setVideoUrl(videoUpload.getUrl());
            record.setCoverUrl(coverUrl);
            record.setSortOrder(sortOrder == null ? 0 : sortOrder);
            record.setStatus(DISPLAY_STATUS);
            record.setCreateTime(LocalDateTime.now());
            record.setUpdateTime(record.getCreateTime());
            guitarVideoDao.insert(record);

            response.put("success", true);
            response.put("message", "Upload succeeded");
            response.put("video", buildVideoResponse(record));
        } catch (IllegalArgumentException | IllegalStateException | DataAccessException e) {
            response.put("success", false);
            response.put("message", "Upload failed: " + e.getMessage());
        }

        return response;
    }

    /**
     * 删除视频：清理 OSS 对象后把记录标记为隐藏。
     *
     * <p>顺序是"查记录 → 删 OSS 上的视频与封面 → 软删除数据库"。OSS 未启用时跳过清理，
     * 只做软删除，因此本地无凭据环境仍可把卡片从列表里移走。
     * {@code hideById} 返回 0 行视为失败并回滚事务；OSS 删除抛出的运行时异常同样会被
     * 捕获成失败响应，此时数据库记录仍处于展示状态，可重试。</p>
     *
     * @param id 视频主键
     * @return 成功时含 {@code success=true} 与回显的 {@code id}；记录不存在或隐藏失败时
     *         返回 {@code success=false} 与原因
     */
    @Override
    @Transactional
    public Map<String, Object> deleteVideo(Long id) {
        Map<String, Object> response = new HashMap<String, Object>();
        try {
            GuitarVideoRecord record = guitarVideoDao.findById(id);
            if (record == null) {
                response.put("success", false);
                response.put("message", "Video not found");
                return response;
            }

            OssUtil ossUtil = ossUtilProvider.getIfAvailable();
            if (ossUtil != null) {
                deleteQuietly(ossUtil, record.getVideoUrl());
                deleteQuietly(ossUtil, record.getCoverUrl());
            }

            if (guitarVideoDao.hideById(id) <= 0) {
                response.put("success", false);
                response.put("message", "Failed to delete video record");
                return response;
            }

            response.put("success", true);
            response.put("message", "Video deleted");
            response.put("id", id);
        } catch (IllegalArgumentException | IllegalStateException | DataAccessException e) {
            response.put("success", false);
            response.put("message", "Delete failed: " + e.getMessage());
        }
        return response;
    }

    /**
     * 为已有视频单独上传或替换封面。
     *
     * <p>校验顺序为"封面非空 → 封面后缀 → 记录存在 → OSS 可用"，全部通过后才上传。
     * 上传成功后写入 {@code cover_url}；更新影响 0 行视为失败。旧封面对象不会在此删除，
     * 会作为历史文件留在 OSS 上，需要时按封面目录人工清理。</p>
     *
     * @param id    视频主键
     * @param cover 封面图，必填且不得为空；后缀仅允许 jpg、jpeg、png、webp
     * @return 成功时含更新后的 {@code video} 摘要（其中 {@code coverUrl} 已是新地址）；
     *         失败时返回 {@code success=false} 与可读原因
     */
    @Override
    @Transactional
    public Map<String, Object> uploadCover(Long id, MultipartFile cover) {
        Map<String, Object> response = new HashMap<String, Object>();
        if (cover == null || cover.isEmpty()) {
            response.put("success", false);
            response.put("message", "Please select a cover image");
            return response;
        }
        if (!hasAllowedExtension(cover.getOriginalFilename(), IMAGE_EXTENSIONS)) {
            response.put("success", false);
            response.put("message", "Only jpg, jpeg, png and webp covers are supported");
            return response;
        }

        try {
            GuitarVideoRecord record = guitarVideoDao.findById(id);
            if (record == null) {
                response.put("success", false);
                response.put("message", "Video not found");
                return response;
            }

            OssUtil ossUtil = ossUtilProvider.getIfAvailable();
            if (ossUtil == null) {
                response.put("success", false);
                response.put("message", "OSS is not configured");
                return response;
            }

            OssUploadResult coverUpload = ossUtil.upload(cover, COVER_DIRECTORY);
            record.setCoverUrl(coverUpload.getUrl());
            if (guitarVideoDao.updateCoverUrl(id, coverUpload.getUrl()) <= 0) {
                response.put("success", false);
                response.put("message", "Failed to update video cover");
                return response;
            }

            response.put("success", true);
            response.put("message", "Cover uploaded");
            response.put("video", buildVideoResponse(record));
        } catch (IllegalArgumentException | IllegalStateException | DataAccessException e) {
            response.put("success", false);
            response.put("message", "Cover upload failed: " + e.getMessage());
        }

        return response;
    }

    /**
     * 把数据库记录转换成前端可直接使用的卡片结构。
     *
     * <p>使用 {@link LinkedHashMap} 固定字段顺序，便于前端与接口调试时肉眼比对；
     * {@code createTime} 为空时整个字段被省略（而不是给空串），前端需要按缺省值处理；
     * {@code durationSeconds} 与 {@code sortOrder} 可能为 {@code null}，原样透出。</p>
     *
     * @param record 数据库记录，不应为 {@code null}
     * @return 含 id、标题、描述、标签、媒体地址、时长、排序值与格式化时间的响应 Map
     */
    private Map<String, Object> buildVideoResponse(GuitarVideoRecord record) {
        Map<String, Object> video = new LinkedHashMap<String, Object>();
        video.put("id", record.getId());
        video.put("title", record.getTitle());
        video.put("description", emptyIfNull(record.getDescription()));
        video.put("tag", emptyIfNull(record.getTag()));
        video.put("videoUrl", resolveMediaUrl(record.getVideoUrl()));
        video.put("coverUrl", resolveMediaUrl(record.getCoverUrl()));
        video.put("durationSeconds", record.getDurationSeconds());
        video.put("sortOrder", record.getSortOrder());
        if (record.getCreateTime() != null) {
            video.put("createTime", TIME_FORMATTER.format(record.getCreateTime()));
        }
        return video;
    }

    /**
     * 把库里存的媒体地址解析成浏览器可访问的 URL。
     *
     * <p>三种情况：空值返回空串；已是 {@code http(s)://} 的完整地址原样返回（兼容历史数据
     * 或手工写入的外链）；其余一律当作 OSS 对象键，交给 {@code OssUtil#getObjectUrl}
     * 结合 {@code url-prefix}、Bucket 与 endpoint 拼接。OSS 未启用时没有可用的拼接能力，
     * 返回原始对象键——页面可能加载失败，但至少不会因为缺 Bean 抛异常。</p>
     *
     * @param urlOrObjectKey 数据库中的 {@code video_url} 或 {@code cover_url}
     * @return 可访问地址；无法解析时返回原始值
     */
    private String resolveMediaUrl(String urlOrObjectKey) {
        if (!StringUtils.hasText(urlOrObjectKey)) {
            return "";
        }
        if (urlOrObjectKey.startsWith("http://") || urlOrObjectKey.startsWith("https://")) {
            return urlOrObjectKey;
        }
        OssUtil ossUtil = ossUtilProvider.getIfAvailable();
        if (ossUtil == null) {
            return urlOrObjectKey;
        }
        return ossUtil.getObjectUrl(urlOrObjectKey);
    }

    /**
     * 删除单个 OSS 对象，值为空时直接跳过。
     *
     * <p>方法名中的 quiet 只表示"空地址不发起调用"；{@code OssUtil#delete} 内部异常
     * （例如网络或权限问题）仍会向上抛出，由调用方的事务与 catch 分支统一处理。</p>
     *
     * @param ossUtil        已确认可用的 OSS 工具实例
     * @param urlOrObjectKey 待删除的对象键或完整 URL；{@code null} 与空白值不处理
     */
    private void deleteQuietly(OssUtil ossUtil, String urlOrObjectKey) {
        if (StringUtils.hasText(urlOrObjectKey)) {
            ossUtil.delete(urlOrObjectKey);
        }
    }

    /**
     * 判断文件名后缀是否在白名单内。
     *
     * @param originalFilename  浏览器提交的原始文件名，可为 {@code null}
     * @param allowedExtensions 允许的后缀集合，元素均为小写且不含点
     * @return 后缀命中返回 {@code true}；无文件名、无扩展名或不在集合内返回 {@code false}
     */
    private boolean hasAllowedExtension(String originalFilename, Set<String> allowedExtensions) {
        String extension = getExtension(originalFilename);
        return allowedExtensions.contains(extension);
    }

    /**
     * 取小写后缀（不含点）。
     *
     * <p>用最后一个点切分，兼容 {@code my.song.MP4} 这类含多点的文件名；
     * 大小写统一到 {@link Locale#ROOT}，避免土耳其语等区域设置把 {@code I} 转成 {@code ı}
     * 导致后缀与白名单失配。</p>
     *
     * @param originalFilename 原始文件名，可为 {@code null}
     * @return 小写后缀；文件名缺失或不含点时返回空串，交由白名单判断为不允许
     */
    private String getExtension(String originalFilename) {
        if (!StringUtils.hasText(originalFilename) || !originalFilename.contains(".")) {
            return "";
        }
        return originalFilename.substring(originalFilename.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT);
    }

    /**
     * 去空白归一化文本。
     *
     * @param value 原始文本，可为 {@code null}
     * @return 去首尾空白后的文本；{@code null}、空串或纯空白统一返回空串，便于后续按列宽截断
     */
    private String normalizeText(String value) {
        return StringUtils.hasText(value) ? value.trim() : "";
    }

    /**
     * 按字符数截断，避免超出数据库列宽导致插入失败。
     *
     * <p>只按长度截取、不做省略号或词边界处理；{@code null} 原样返回，
     * 由调用方决定是否再转成空串。</p>
     *
     * @param value     待截断文本，可为 {@code null}
     * @param maxLength 允许的最大字符数，与 {@code guitar_video} 的列宽一致
     * @return 不超长时返回原字符串，否则返回前 {@code maxLength} 个字符
     */
    private String truncate(String value, int maxLength) {
        if (value == null || value.length() <= maxLength) {
            return value;
        }
        return value.substring(0, maxLength);
    }

    private String emptyIfNull(String value) {
        return value == null ? "" : value;
    }
}
