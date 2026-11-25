# AGENTS.md — tools/service-doctor

本目录维护独立的本地服务诊断 CLI。

## 工作边界

- 不启动、停止、重启或修复任何服务；工具只发起清单中声明的 `GET` 健康检查。
- 不读取用户配置、`.env`、数据库配置、密钥、凭据或用户目录。
- 不扫描端口、不做服务发现、不读取清单之外的 URL。
- 不引入第三方 Python 依赖、前端运行时或构建步骤；保持 Python 3.7+ 标准库可运行。
- 不加入 Maven 模块，不依赖 Spring、Node 或浏览器。
- 测试和默认验证不得探测 `8080`、`8081`、`5174`–`5179` 等现有服务；使用临时回环 HTTP fixture，并让操作系统分配端口。

## 必须保持的安全契约

1. URL 使用 `http://` 或 `https://`，主机必须是数值回环 IP（`127.0.0.0/8`、`::1`）。
2. 拒绝 URL 中的用户名、密码、片段、空白、控制字符和非 ASCII 内容。
3. 使用 `http.client` 直连，禁用系统代理和重定向跟随；3xx 必须判为 HTTP 错误。
4. 不读取环境变量中的代理设置。
5. HTTP 200 后才解析响应；`success` 必须是字面布尔 `true`，不能接受字符串或数字。
6. 标准服务（`kind=service`）的 `service` 必须是非空字符串且与 `expected_service` 完全匹配。
7. `kind=aggregate` 校验 `success=true`、布尔值 `healthy` 和 `services` 数组。有效响应中的 `healthy=false` 单独报告下游不健康。
8. 所有连接/读取有超时；并发数必须有上限（`--jobs`），结果必须保持清单输入顺序。
9. 不将响应正文写入终端结果或 HTML 报告。
10. HTML 中所有动态插值必须经过 HTML 逃逸；报告必须自包含，不含外部资源或脚本。
11. 配置错误和服务失败必须使用不同退出码：`0` 全部正常，`1` 服务失败，`2` 配置/输出错误。
12. 默认清单只能包含本机回环地址；新增服务时同步维护 URL、`kind` 和预期 `service`。

## 当前文件职责

- `service_doctor.py`：CLI、清单校验、URL 安全校验、单服务探测、有界并行、终端输出、HTML 报告。
- `services.example.json`：内置的九项本机服务清单；website 为聚合接口，其余为标准服务。
- `tests/test_service_doctor.py`：unittest 与临时回环 HTTP fixture；不得探测真实服务。
- `README.md`：用户使用说明、清单格式、状态和退出码。
- `AGENTS.md`：本文件，维护边界与不变量。

## 修改与验证要求

- 修改状态含义、退出码、清单字段、URL 策略、超时/并发语义或报告内容时，同步更新 `README.md` 和本文件。
- 新增状态分类时，必须同时更新终端标签、HTML 标签/样式、汇总逻辑和测试。
- 保持 HTML 报告无响应正文、无外部依赖、无未逃逸插值。
- 修改后从仓库根目录执行：

```bash
python -m unittest discover -s tools/service-doctor/tests -v
python -m py_compile tools/service-doctor/service_doctor.py
```

- 不通过启动真实服务来让测试通过；测试必须能在没有 8080/8081/5174–5179 服务的机器上通过。
- 若容器或平台对回环未监听端口的连接行为不稳定，连接拒绝分类应通过可控的单元测试模拟，而不是依赖真实端口行为。
