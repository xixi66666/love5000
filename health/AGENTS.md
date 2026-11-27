# 健康管理（5180）

- Spring Boot 独立模块，health 健康标识。website 的 03 Deep Woods 卡片按需启动，既有个人资料库入口重定向到此。
- 独占写入 Vault 的 `30-健康/体检`、`99-附件/体检`、`80-AI分析/体检`，文件名、UUID、版本和旧 Markdown 保持兼容。个人资料库仅索引和读取。不得用真实 Vault 或真实模型执行集成测试。
- `vault-core` 管理本机鉴权、Vault IO 与模型访问。首次从旧运行状态导入仓库选择与密码哈希，之后使用独立的状态与 Session。文本模型沿用 `personal-agent` scope，分页 OCR 读取根 `model.properties` 的 `vision.*`。
- `exam-engine` 使用 Python 3.12+ 和锁定的 Mirobody，工作进程由 Java 按请求调用。只读写 stdio，无数据库或长期监听端口。
- UI 约束见 `DESIGN.md`。验证 `mvn -pl health,personal-agent -am test`、`node --check health/src/main/resources/static/health-app.js`、`exam-engine` 的 `test_engine.py` 和首页入口用例。
