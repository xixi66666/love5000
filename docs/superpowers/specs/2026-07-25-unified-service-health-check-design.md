# 统一微服务健康检查设计

## 背景

`website` 当前通过三个独立的 `ApplicationRunner` 检查并自动启动
`python-a`、`quant-a` 和 `video`。三个类各自实现 URL 拼装、HTTP 请求和启动等待，
存在重复代码，并且 `python-a` 只校验 HTTP 2xx，另外两个服务还校验
`success=true`。

主页还会直接探测 `lovestory`、`imagetemplate`、`guitar` 和三个 Python 服务，
但目前没有 Java 后端聚合接口，也没有统一的健康响应协议。

## 目标

- 所有独立服务提供 `GET /api/health`。
- 健康响应统一包含 `success=true` 和稳定的 `service` 标识。
- `website` 使用一个可复用的 Java 组件执行所有远程健康检查。
- 三个 Python 自动启动器复用统一组件，不再自行实现探测和轮询。
- `website` 提供 `GET /api/services/health` 聚合接口。
- 某个服务不可用时仍返回其他服务的检查结果。

## 非目标

- 不使用 Spring Boot Actuator。
- 不由 `website` 自动启动 `lovestory`、`imagetemplate` 或 `guitar`。
- 不改变各服务现有业务接口。
- 本次不把主页状态点切换到聚合接口；主页保持现有浏览器直连探测。
- `common` 不是可独立运行的服务，不加入健康检查清单。
- `website` 本身不加入自己的远程聚合清单，避免自调用。

## 统一协议

各独立服务新增或保留：

```text
GET /api/health
```

健康响应为 HTTP 2xx，且至少包含：

```json
{
  "success": true,
  "service": "lovestory"
}
```

服务标识固定为：

- `lovestory`
- `imagetemplate`
- `guitar`
- `python-a`
- `quant-a`
- `video`

远程探测只有在 HTTP 状态为 2xx、响应可解析为 JSON，并且顶层
`success` 严格等于布尔值 `true` 时才判定健康。缺失字段、字符串形式的
`"true"`、非法 JSON、非 2xx、超时及连接失败均判定为不健康。

## Java 组件设计

在 `website` 的 `integration.health` 包新增以下组件：

### `ServiceHealthChecker`

职责：

- 使用统一的连接和读取超时发送 HTTP GET。
- 严格解析统一健康协议。
- 返回结构化的 `ServiceHealthResult`。
- 按指定启动超时时间每秒轮询，供自动启动器等待服务就绪。

该组件不负责启动进程，也不保存服务清单。

默认连接超时为 2 秒，读取超时为 3 秒。超时值通过
`website.service-health` 配置，可在测试和部署环境覆盖。

### `ServiceHealthDefinition`

描述一个被检查的服务：

- `name`
- `url`

服务 URL 直接通过配置提供，避免工具类硬编码不同模块的端口和路径。

### `ServiceHealthResult`

包含：

- `name`
- `url`
- `healthy`
- `statusCode`，未收到 HTTP 响应时为空
- `durationMs`
- `message`，健康时为空，失败时为稳定且不包含堆栈的摘要

响应不得暴露异常堆栈、本机文件路径、密钥或响应正文。

### `ServiceHealthProperties`

绑定配置：

```yaml
website:
  service-health:
    connect-timeout-ms: 2000
    read-timeout-ms: 3000
    services:
      - name: lovestory
        url: http://127.0.0.1:8081/api/health
      - name: imagetemplate
        url: http://127.0.0.1:8082/api/health
      - name: guitar
        url: http://127.0.0.1:8088/api/health
      - name: python-a
        url: http://127.0.0.1:5174/api/health
      - name: quant-a
        url: http://127.0.0.1:5175/api/health
      - name: video
        url: http://127.0.0.1:5176/api/health
```

服务名称必须非空且唯一，URL 只允许 `http` 或 `https`。配置错误应在
`website` 启动时失败，而不是运行到第一次请求时才暴露。

## 自动启动器集成

`PythonAAutoStartRunner`、`QuantAAutoStartRunner` 和
`VideoAutoStartRunner` 注入 `ServiceHealthChecker`。

每个启动器继续根据自己的端口和 `health-path` 构造目标 URL，以保持现有配置兼容；
统一组件负责请求、响应校验和等待轮询。现有进程启动、工作目录解析、日志转发和
关闭逻辑不变。

本次会把 `python-a` 的判断收紧为统一协议：仅返回 HTTP 2xx 不再视为健康，
响应还必须包含布尔值 `success=true`。

## 聚合接口

`website` 新增：

```text
GET /api/services/health
```

Controller 将配置的服务清单交给聚合 Service。聚合 Service 使用有界线程池并行调用
`ServiceHealthChecker`，以避免多个离线服务串行叠加超时时间。

接口成功完成聚合时始终返回 HTTP 200。顶层 `success=true` 表示聚合请求执行成功，
`healthy` 表示所有目标服务是否健康：

```json
{
  "success": true,
  "healthy": false,
  "services": [
    {
      "name": "guitar",
      "url": "http://127.0.0.1:8088/api/health",
      "healthy": true,
      "statusCode": 200,
      "durationMs": 12
    },
    {
      "name": "video",
      "url": "http://127.0.0.1:5176/api/health",
      "healthy": false,
      "statusCode": null,
      "durationMs": 7,
      "message": "Connection failed"
    }
  ]
}
```

结果顺序与配置顺序一致。单项检查抛出异常时转换成该服务的不健康结果，不中断其他
检查。只有聚合器自身无法执行时，才按照项目错误响应约定返回 `success=false`。

并行执行使用应用管理的固定大小执行器，线程数不超过服务数，并在应用关闭时释放；
不为每次 HTTP 请求新建线程池。

## 各服务改动

- `lovestory`：新增无数据库依赖的健康 Controller。
- `imagetemplate`：新增无 OpenAI 调用的健康 Controller。
- `guitar`：保留现有 `HealthController`，确认响应符合统一协议。
- `python-a`：保留现有路由，补齐或确认稳定的 `service` 字段。
- `quant-a`：保留现有路由，补齐或确认稳定的 `service` 字段。
- `video`：保留现有路由，补齐或确认稳定的 `service` 字段。

健康接口只表示进程可以处理 HTTP 请求，不访问 MySQL、OSS、OpenAI、DeepSeek、
行情数据源或 FFmpeg，避免外部依赖抖动导致进程存活检查失真。

## 测试

按测试驱动方式实现：

- `ServiceHealthCheckerTest`
  - 2xx + 合法 `success=true`
  - 非 2xx
  - `success` 缺失、类型错误或为 false
  - 非法 JSON
  - 连接失败和读取超时
  - 等待轮询最终成功及超时
- 聚合 Service/Controller 测试
  - 全部健康
  - 部分离线但仍返回全部结果
  - 保持配置顺序
  - 顶层 `healthy` 计算
  - 单项异常隔离
- 三个 `AutoStartRunnerTest`
  - 确认使用统一检查器判断已有服务
  - 确认启动后使用统一检查器等待
  - 保留工作目录和命令构造回归测试
- `lovestory`、`imagetemplate`、`guitar` Controller 测试
  - HTTP 200
  - `success=true`
  - 正确的 `service`
- Python 服务现有健康测试补充 `service` 字段断言。

验证命令至少包括：

```bash
mvn -pl website,lovestory,imagetemplate,guitar -am test
cd website/quant-a && python -m pytest
cd website/video && python -m pytest
cd website/python-a && python -m unittest discover -s tests
```

如果 Python 微应用使用的实际测试入口与上述命令不同，以各目录当前配置为准并同步文档。

## 文档同步

实现时同步更新：

- 根目录 `AGENTS.md`、`README.md`
- `website/AGENTS.md`、`website/README.md`
- `lovestory/AGENTS.md`、`lovestory/README.md`
- `imagetemplate/AGENTS.md`、`imagetemplate/README.md`
- `guitar/AGENTS.md`、`guitar/README.md`
- 三个 Python 微应用各自的 `AGENTS.md`、`README.md`

文档需记录统一健康协议、聚合接口、配置清单、超时语义和测试命令。
