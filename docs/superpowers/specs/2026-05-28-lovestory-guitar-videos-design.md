# lovestory 吉他视频卡片模块设计

## 背景

`lovestory` 主页面当前的 `甜蜜回忆 · Memory Cards` 与后续照片墙在内容形态上重复。新的方向是保留卡片式体验，但把该模块替换为更有心意的吉他视频模块：用户弹吉他后上传视频到 OSS，后端保存视频记录，主页按记录渲染视频卡片。

## 目标

- 移除主页面 `甜蜜回忆 · Memory Cards` 模块。
- 新增 `吉他小剧场 · Guitar Videos` 模块。
- 每个视频对应一张视频卡片。
- 增加视频上传能力，上传成功后保存 OSS 视频 URL 到 MySQL。
- 支持可选封面图上传；没有封面时使用前端默认封面样式或默认图片。
- 点击视频卡片后打开弹窗播放器，按需加载对应 OSS 视频。
- 不影响照片墙、照片上传、小游戏、成就和留言板。

## 建表语句

```sql
CREATE TABLE `guitar_video` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `title` VARCHAR(100) NOT NULL COMMENT '视频标题或歌曲名',
  `description` VARCHAR(500) DEFAULT NULL COMMENT '想说的话或视频说明',
  `tag` VARCHAR(50) DEFAULT NULL COMMENT '标签，例如吉他弹唱、给xixi、练习版',
  `video_url` VARCHAR(1000) NOT NULL COMMENT 'OSS视频访问地址',
  `cover_url` VARCHAR(1000) DEFAULT NULL COMMENT 'OSS封面图访问地址',
  `duration_seconds` INT DEFAULT NULL COMMENT '视频时长，单位秒，可为空',
  `sort_order` INT NOT NULL DEFAULT 0 COMMENT '排序值，越大越靠前',
  `status` TINYINT NOT NULL DEFAULT 1 COMMENT '状态：1展示，0隐藏',
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_status_sort_time` (`status`, `sort_order`, `create_time`),
  KEY `idx_create_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='吉他视频卡片表';
```

## 接口设计

推荐新增接口：

```text
GET    /api/guitar-videos
POST   /api/guitar-videos/upload
DELETE /api/guitar-videos/{id}
```

上传字段：

```text
file         MultipartFile，必填，视频文件
cover        MultipartFile，可选，封面图
title        string，必填
description  string，可选
tag          string，可选
sortOrder    int，可选
```

视频文件建议限制为 `mp4`、`webm`、`mov`。封面图建议限制为 `jpg`、`jpeg`、`png`、`webp`。

## 前端交互

页面展示一组视频卡片。每张卡片包含：

- 视频封面图。
- 歌曲名或视频标题。
- 日期。
- 一句想说的话。
- 可选标签。

用户点击卡片时：

- 打开居中的视频弹窗。
- 将当前卡片的 `videoUrl` 设置为 `<video controls>` 的 `src`。
- 关闭弹窗时暂停视频，并清空 `src`，避免后台继续加载或播放。

## 文件范围

预计修改：

- `lovestory/src/main/resources/static/index.html`
- `lovestory/src/main/java/com/ycxandwuqian/love/controller/`
- `lovestory/src/main/java/com/ycxandwuqian/love/service/`
- `lovestory/src/main/java/com/ycxandwuqian/love/dao/`
- `lovestory/src/main/java/com/ycxandwuqian/love/model/`
- `lovestory/src/main/resources/mapper/`

实现时继续使用 MyBatis DAO + XML Mapper，不新增 JPA、JdbcTemplate 或 Java 内联 SQL。

## 验证方式

- 启动 `lovestory` 后访问 `http://localhost:8081/`。
- 确认原 `甜蜜回忆 · Memory Cards` 已被替换。
- 确认视频卡片来自 `GET /api/guitar-videos`。
- 上传视频后，视频文件进入 OSS，视频记录进入 `guitar_video` 表。
- 点击每张卡片能打开播放器弹窗。
- 视频播放器使用数据库记录中的 OSS URL。
- 关闭弹窗后视频停止播放。
- 确认照片墙、上传照片、小游戏入口和留言板不受影响。
