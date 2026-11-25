# service-doctor 本地服务诊断台

独立、只读的本地服务健康检查工具。使用 Python 3.7+ 标准库实现，不引入第三方依赖，不启动、停止或修改任何服务，也不读取用户配置或凭据。

它只探测**显式清单**中列出的 `http://` 或 `https://` 回环地址，输出终端结果，并可按需生成一份自包含中文 HTML 报告。

## 目录内容

```text
tools/service-doctor/
├── service_doctor.py        # CLI 与全部实现
├── services.example.json    # 内置本机服务清单
├── README.md
├── AGENTS.md
└── tests/
    └── test_service_doctor.py
```

## 快速开始

在仓库根目录执行：

```bash
python tools/service-doctor/service_doctor.py
```

默认读取同目录的 `services.example.json`，按清单顺序探测：

| 服务 | 地址 | 校验方式 |
| --- | --- | --- |
| website | `http://127.0.0.1:8080/api/services/health` | 聚合接口，读取巡检结果的 `success` 和 `healthy` |
| lovestory | `http://127.0.0.1:8081/api/health` | 标准服务：HTTP 200 + `success=true` + `service=lovestory` |
| imagetemplate | `http://127.0.0.1:8082/api/health` | 标准服务，预期 `imagetemplate` |
| python-a | `http://127.0.0.1:5174/api/health` | 标准服务，预期 `python-a` |
| quant-a | `http://127.0.0.1:5175/api/health` | 标准服务，预期 `quant-a` |
| scrapling-ui | `http://127.0.0.1:5176/api/health` | 标准服务，预期 `scrapling-ui` |
| skill-finder | `http://127.0.0.1:5177/api/health` | 标准服务，预期 `skill-finder` |
| personal-agent | `http://127.0.0.1:5178/api/health` | 标准服务，预期 `personal-agent` |
| lottery | `http://127.0.0.1:5179/api/health` | 标准服务，预期 `lottery` |

`website` 的 `kind=aggregate` 探测读取最近一次巡检结果。HTTP 200 且 `success=true` 时，工具根据 `healthy` 判断下游健康状态。

自定义清单与报告：

```bash
python tools/service-doctor/service_doctor.py \
  --manifest ./my-services.json \
  --timeout 2.5 \
  --jobs 4 \
  --html ./service-report.html
```

参数：

| 参数 | 说明 |
| --- | --- |
| `-m, --manifest PATH` | 自定义 JSON 清单，默认 `services.example.json` |
| `-o, --html PATH` | 额外写入一份 UTF-8 自包含中文 HTML 报告 |
| `-t, --timeout SECONDS` | 单次连接/读取超时，默认 `3.0`，范围 `0.05`–`60` |
| `-j, --jobs N` | 并发上限，默认 `8`，范围 `1`–`32` |

结果始终按清单中的输入顺序输出。并发只限制同时执行的探测数量，不改变顺序。

## 清单格式

```json
{
  "services": [
    {
      "name": "website",
      "url": "http://127.0.0.1:8080/api/services/health",
      "kind": "aggregate"
    },
    {
      "name": "lovestory",
      "url": "http://127.0.0.1:8081/api/health",
      "kind": "service",
      "expected_service": "lovestory"
    }
  ]
}
```

规则：

- 顶层只允许 `services` 字段，且必须是非空数组，最多 256 项。
- 每项只允许 `name`、`url`、`kind`、`expected_service`。
- `kind=service` 时必须提供非空的 `expected_service`；HTTP 200 后，JSON 顶层必须是对象，`success` 必须是字面布尔 `true`（字符串 `"true"` 或数字 `1` 都不通过），`service` 必须是字符串且与预期完全一致。
- `kind=aggregate` 使用 `success=true`、布尔值 `healthy` 和 `services` 数组。响应结构有效且 `healthy=false` 时，报告下游不健康。
- 服务名称不能重复，不能包含控制字符。
- 清单必须是 UTF-8 编码，文件不超过 1 MiB。

### URL 限制

- 只允许 `http://` 或 `https://`。
- 主机使用 IPv4 回环地址（`127.0.0.0/8`）或 IPv6 回环地址（`[::1]`）。
- 不允许 URL 中包含用户名、密码或片段（`#`）。
- 端口必须是 `1`–`65535`；未写端口时分别使用 HTTP 80、HTTPS 443。
- URL 必须为 ASCII、无空白、无控制字符、长度不超过 2048。

工具使用 `http.client` 直接连接目标，不读取 `HTTP_PROXY`、`HTTPS_PROXY` 等代理环境变量，也不会跟随 3xx 重定向。HTTPS 使用 Python 默认证书校验。

## 状态与退出码

状态分类：

| 状态 | 含义 |
| --- | --- |
| `healthy` / 正常 | HTTP 200，且所有要求字段匹配 |
| `downstream_unhealthy` / 下游不健康 | 聚合接口响应有效，`healthy=false` |
| `connection_refused` / 连接被拒绝 | 目标端口明确拒绝连接 |
| `timeout` / 超时 | 在 `--timeout` 内未完成 |
| `http_error` / HTTP 错误 | HTTP 状态不是 200；3xx 也不会被跟随 |
| `format_error` / 格式错误 | 响应非 JSON、顶层不是对象、`success` 不是字面 `true`、`service` 缺失/类型错误/不匹配、响应体为空或超过 256 KiB |
| `connection_error` / 其他连接错误 | 连接重置、TLS、响应格式损坏等其他网络错误 |

退出码：

| 退出码 | 含义 |
| --- | --- |
| `0` | 全部检查正常 |
| `1` | 至少一项服务检查失败 |
| `2` | 清单、URL、参数等配置错误；或 HTML 报告无法写入 |

配置错误会直接返回 `2`，不会对任何服务发起探测。

## HTML 报告

使用 `--html PATH` 时生成单文件 HTML：

- 中文界面，CSS 内联，不依赖外部字体、图片、脚本或任何前端运行时。
- 所有动态插值（服务名、URL、预期 service、说明、时间等）都经过 HTML 逃逸。
- 不包含响应正文；只记录状态、HTTP 码、耗时和固定说明。
- 报告包含输入顺序、总数、正常数、失败数及每项状态。

## 测试

```bash
python -m unittest discover -s tools/service-doctor/tests -v
```

测试使用 `unittest` 和运行在 `127.0.0.1:0` 的临时 HTTP fixture，覆盖正常、聚合、连接拒绝、超时、HTTP 错误、格式错误、其他连接错误、代理忽略、重定向不跟随、有界并发/顺序、HTML 逃逸、响应正文不进入报告、配置错误退出码和 CLI 报告生成。

测试不会探测 `8080`、`8081`、`5174`–`5179` 等现有服务，也不会启动或停止服务。临时清单和报告只写入本工具目录下的临时子目录，并在测试结束时清理。

## 明确边界

- 不启动、停止、重启或修复任何服务。
- 不读取项目配置、环境文件、数据库配置、密钥或用户目录。
- 不修改清单之外的目标，不扫描端口，不进行服务发现。
- 不发布、不部署、不提交。
- 无第三方依赖，无 Maven 集成，无前端构建。
