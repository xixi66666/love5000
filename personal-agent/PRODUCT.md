# 个人长期资料库
<!-- impeccable:product-schema 1 -->

## Platform
web

## Users
单人、本机使用。用户在 Obsidian 长期记录财务、健康、工作和其他个人资料，在网页检索、阅读并主动请求 AI 分析。

## Product Purpose
以真实 Vault 为唯一资料源，保留时间、来源、历史与矛盾信息；分析报告可回溯到生成时的资料版本。

## Operating Context
5178 独立 Java 服务；website 的03入口点击启动。Quartz 实际构建私有资料页。默认创建 knowledge-vault，旧 H2 和 vault 保留。支持连接其他已有 Obsidian Vault。

## Capabilities and Constraints
本地登录、笔记创建与版本校验编辑、搜索、领域分类、Obsidian 打开链接、Quartz 全文检索与关系图、用户确认来源后进行 AI 分析。没有后台自动上传；报告标记为 AI 草稿，不自动变成事实。

## Brand Commitments
用户已明确选择 Quartz 的资料阅读与双链界面。重构替换原 Agent 的森林视频、财务账本与对话业务。

## Evidence on Hand
运行数据由用户提供；初始说明与模板不能伪装成真实个人资料。测试仅使用构造数据，不调用真实模型。

## Product Principles
- 原文件、时间与证据可追溯。
- 用户决定哪些资料交给模型。
- 历史快照不能冒充当前情况。
- 先完成阅读与记录，再增加视觉表达。
