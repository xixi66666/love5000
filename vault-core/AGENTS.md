# Vault 基础库

- 属于非独立服务的 Maven 模块。通过相同包命名空间提供 Vault 路径边界、Markdown 读写与版本保护、登录状态和模型入口；供 health 与 personal-agent 共用。
- `AgentConfig.examOwner` 默认关闭，健康应用开启。不能在普通笔记写入口绕开受保护的体检目录。两进程可读同一 Vault，必须使用不同运行目录。
- 用调用模块的合成 Vault 集成测试验证。配置或接口变更同步两个调用模块和根文档。
