# 健康管理
<!-- impeccable:product-schema 1 -->

## Platform
web

## Users
本机单用户，定期导入体检原件，按时间比较结果并回查证据。

## Product Purpose
把分散的体检报告放到同一张时间轴，异常优先，每个值都能回到原始报告。

## Operating Context
独立 Spring Boot 应用和本机 Mirobody 子进程。Obsidian Vault 为资料源，健康应用负责体检条目写入。

## Capabilities and Constraints
按次授权模型处理，保留本地解析、OCR、AI 草稿、逐页回查和标准编码。仅真实资料可作为指标来源。临时测试使用合成资料。
