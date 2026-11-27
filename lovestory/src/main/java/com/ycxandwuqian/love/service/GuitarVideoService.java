package com.ycxandwuqian.love.service;

import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

/**
 * 吉他视频卡片的业务契约。
 *
 * <p>位于服务层，向上被 {@code GuitarVideoController} 调用，向下组合
 * {@link com.ycxandwuqian.love.dao.GuitarVideoDao} 与 {@code OssUtil}。
 * 所有方法都以 {@code {success, message, ...}} 形式的 Map 作为统一响应：
 * 校验失败、OSS 未配置、数据库异常都通过 {@code message} 表达而不是抛异常，
 * 因此调用方不需要 try-catch，页面也可以按同一结构渲染。</p>
 */
public interface GuitarVideoService {

    /**
     * 查询展示中的视频卡片。
     *
     * @return 成功时含 {@code success=true} 与 {@code videos} 列表（按排序值倒序）；
     *         数据库访问失败时 {@code success=false} 且 {@code videos} 为空列表
     */
    Map<String, Object> listVideos();

    /**
     * 上传视频，可选一并上传封面并写入数据库。
     *
     * @param file        视频文件，必填且不得为空；后缀仅允许 mp4、webm、mov
     * @param cover       封面图，可为 {@code null}；提供时后缀仅允许 jpg、jpeg、png、webp
     * @param title       标题，去空白后不得为空，落库时截断到 100 字符
     * @param description 描述，可为 {@code null}，落库时截断到 500 字符
     * @param tag         标签，可为 {@code null}，落库时截断到 50 字符
     * @param sortOrder   排序值，为 {@code null} 时按 0 处理
     * @return 成功时含 {@code video} 卡片信息；任一校验或上传步骤失败时返回
     *         {@code success=false} 与可读原因
     */
    Map<String, Object> uploadVideo(MultipartFile file, MultipartFile cover, String title,
                                    String description, String tag, Integer sortOrder);

    /**
     * 为已有视频单独上传或替换封面。
     *
     * @param id    视频主键，必须已存在
     * @param cover 封面图，必填且不得为空；后缀仅允许 jpg、jpeg、png、webp
     * @return 成功时含更新后的 {@code video}；记录不存在、OSS 未配置或更新失败时
     *         返回 {@code success=false} 与可读原因
     */
    Map<String, Object> uploadCover(Long id, MultipartFile cover);

    /**
     * 删除视频卡片：尽力清理 OSS 对象，并把数据库记录置为隐藏。
     *
     * @param id 视频主键
     * @return 成功时回显 {@code id}；记录不存在或隐藏失败时返回 {@code success=false}
     */
    Map<String, Object> deleteVideo(Long id);
}
