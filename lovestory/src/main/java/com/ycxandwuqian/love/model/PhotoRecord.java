package com.ycxandwuqian.love.model;

import java.time.LocalDateTime;

/**
 * {@code photo} 表对应的数据模型。
 *
 * <p>位于模型层，只有字段与 getter/setter。三列的业务含义：</p>
 * <ul>
 *   <li>{@code path} 存的是 OSS 对象键（形如 {@code love530/lovestory/photos/cat/2026/05/01/uuid.jpg}），
 *       不是完整 URL；对外响应时才由 {@code OssUtil#getObjectUrl} 结合配置拼出访问地址，
 *       因此更换 CDN 域名或开启自定义 {@code url-prefix} 都不需要改数据。</li>
 *   <li>{@code type} 是照片分类，取值 cat、girl、us，同时决定对象键中的二级目录。</li>
 *   <li>{@code create_time} 由数据库默认值生成，插入时不赋值。</li>
 * </ul>
 */
public class PhotoRecord {

    private Long id;

    private String path;

    private String type;

    private LocalDateTime createTime;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getPath() {
        return path;
    }

    public void setPath(String path) {
        this.path = path;
    }

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public LocalDateTime getCreateTime() {
        return createTime;
    }

    public void setCreateTime(LocalDateTime createTime) {
        this.createTime = createTime;
    }
}
