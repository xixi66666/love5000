package com.ycxandwuqian.love.service;

import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

/**
 * 照片墙业务：上传、列表和删除。
 *
 * <p>位于服务层，向上被 {@code UploadPhotoController} 调用，向下组合
 * {@link com.ycxandwuqian.love.dao.PhotoDao} 与 {@code OssUtil}。约定与实现一致：
 * 一律返回 {@code {success, message, ...}} 形式的 Map，失败通过 {@code message} 表达，
 * 不向上抛业务异常。</p>
 */
public interface PhotoService {

    /**
     * 上传照片：对象键先定后传，落库失败时按该键补偿删除已写入的 OSS 对象。
     *
     * @param file        图片文件，必填且不得为空；后缀仅允许 jpg、jpeg、png、gif、webp
     * @param category    分类，取值 cat、girl、us（大小写与首尾空白会被归一化），同时作为 OSS 二级目录
     * @param description 展示用描述，可为空；为空时由分类与上传时间拼出默认文案
     * @return 成功时含 {@code url} 与 {@code photo} 摘要；参数非法、OSS 未配置或写入失败时
     *         返回 {@code success=false} 与可读原因
     */
    Map<String, Object> uploadPhoto(MultipartFile file, String category, String description);

    /**
     * 查询照片列表，按创建时间倒序。
     *
     * @return 成功时含 {@code photos}；数据库访问失败时 {@code success=false} 且列表为空
     */
    Map<String, Object> listPhotos();

    /**
     * 删除照片：先删数据库记录，成功后再清理 OSS 对象。
     *
     * @param id 照片主键
     * @return 成功时回显 {@code id}；记录不存在、删除失败或 OSS 清理失败时返回
     *         {@code success=false} 与原因（清理失败会回滚事务，保持记录与对象一致）
     */
    Map<String, Object> deletePhoto(Long id);
}
