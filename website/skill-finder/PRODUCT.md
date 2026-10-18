# Skill Finder

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

个人使用者每天早上查看 AI 开源项目热榜，预览中文口播视频，并决定是否发布到自己的抖音账号。

## Product Purpose

每天北京时间 08:00 提供基于 GitHub Trending 的 AI 项目 Top10 日报、中文配音、字幕和竖屏视频。
QQ 为指定通知渠道，本次用户明确暂不配置。抖音通过创作者后台登录，发布必须经过本人审核。

## Capabilities and Constraints

以 love5000/website/skill-finder 为代码基线，保留已有筛选、健康检查、界面与共享 xixi 数据库。
每天取当日 AI 范围的真实新增 Star 排名，数量不足十项时如实标记。
服务器为 CentOS 7、2GB 内存，保留已有站点和数据；视频任务串行执行。
审核绑定视频及口播文案；修改内容后不得复用批准记录。

## Brand Commitments

沿用 love5000 已有 Skill Finder 界面。参考视频采用第十名倒数到第一名、逐个介绍用途的内容结构。

## Evidence on Hand

已有 GitHub Trending 采集、MySQL 五张业务表、项目中文介绍、Vue 前端和测试。
QQ 接入密钥暂不提供；抖音尚未登录或授权，不得声称已完成消息送达或视频发布。
