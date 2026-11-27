package com.ycxandwuqian.love.model;

import java.time.LocalDateTime;

/**
 * {@code guitar_video} 表对应的数据模型。
 *
 * <p>位于模型层，只承载字段与 getter/setter，不含校验与业务逻辑；
 * 映射由 {@code GuitarVideoMapper.xml} 的 resultMap 声明，插入时通过 setter 回填自增主键。
 * 时间字段使用 {@link LocalDateTime}，直接对应 MySQL 的 {@code DATETIME}。
 * 字段与表结构的对应关系以 {@code GuitarVideoMapper.xml} 为准，改表时必须同步本类。</p>
 */
public class GuitarVideoRecord {

    private Long id;

    private String title;

    private String description;

    private String tag;

    /** 视频地址：OSS 对象键或完整 URL，两种形态业务层都能解析。 */
    private String videoUrl;

    /** 封面地址：OSS 对象键或完整 URL；空串表示上传时未提供封面，尚未截帧生成。 */
    private String coverUrl;

    /** 视频时长，单位秒；前端未提供时为 {@code null}，页面需按可空处理。 */
    private Integer durationSeconds;

    /** 排序值，越大越靠前；同值时再按创建时间倒序。 */
    private Integer sortOrder;

    /** 状态位：1 表示在卡片墙展示，0 表示已隐藏（软删除）。 */
    private Integer status;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public String getTag() {
        return tag;
    }

    public void setTag(String tag) {
        this.tag = tag;
    }

    public String getVideoUrl() {
        return videoUrl;
    }

    public void setVideoUrl(String videoUrl) {
        this.videoUrl = videoUrl;
    }

    public String getCoverUrl() {
        return coverUrl;
    }

    public void setCoverUrl(String coverUrl) {
        this.coverUrl = coverUrl;
    }

    public Integer getDurationSeconds() {
        return durationSeconds;
    }

    public void setDurationSeconds(Integer durationSeconds) {
        this.durationSeconds = durationSeconds;
    }

    public Integer getSortOrder() {
        return sortOrder;
    }

    public void setSortOrder(Integer sortOrder) {
        this.sortOrder = sortOrder;
    }

    public Integer getStatus() {
        return status;
    }

    public void setStatus(Integer status) {
        this.status = status;
    }

    public LocalDateTime getCreateTime() {
        return createTime;
    }

    public void setCreateTime(LocalDateTime createTime) {
        this.createTime = createTime;
    }

    public LocalDateTime getUpdateTime() {
        return updateTime;
    }

    public void setUpdateTime(LocalDateTime updateTime) {
        this.updateTime = updateTime;
    }
}
