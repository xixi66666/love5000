package com.example.guitar.favorite.vo;

import java.time.LocalDateTime;

public class FavoriteFolderResponse {

    private final Long id;
    private final String name;
    private final Integer sortOrder;
    private final LocalDateTime createTime;
    private final LocalDateTime updateTime;

    public FavoriteFolderResponse(Long id, String name, Integer sortOrder,
                                  LocalDateTime createTime, LocalDateTime updateTime) {
        this.id = id;
        this.name = name;
        this.sortOrder = sortOrder;
        this.createTime = createTime;
        this.updateTime = updateTime;
    }

    public Long getId() { return id; }
    public String getName() { return name; }
    public Integer getSortOrder() { return sortOrder; }
    public LocalDateTime getCreateTime() { return createTime; }
    public LocalDateTime getUpdateTime() { return updateTime; }
}
