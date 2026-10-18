# 腾讯云部署与每日 AI 项目视频

## 代码基线与对照

权威源码为 `love5000/website/skill-finder`；独立仓库为 `C:/Code/skills-finder`。
部署包只包含这个微服务的 FastAPI 后端、Vue 构建产物与部署脚本。
不打包 Java 父工程，不修改现有 Maven 模块或首页服务边界。

同步前的核心差异：

| 部分 | love5000 版本 |
| --- | --- |
| 后端 `app/core/config.py` | 复用 website 的 xixi 配置、环境变量解析与凭据转义 |
| 后端 `app/main.py` | `/api/health`、前端同端口托管、SPA fallback、JS MIME 修复 |
| 前端 | 更新后的电影化主页、GSAP、仓库封面、导航、主题与移动端样式；13 个源文件有差异 |
| 依赖与测试 | MySQL SHA-2 的 cryptography、共享配置测试、健康及静态资源回归 |

本次在上述版本上增加 `app/daily/`、日报 API、`/daily-reports` 页面和容器部署，
修复未配置 GitHub Token 时错误发送空 Bearer 头的问题。
公开仓库允许无 Token 访问；遇到 API 限流则明确失败，不把旧榜单冒充当天结果。
当某一期所有项目补全失败时保留该期旧数据，不清空已保存榜单。

## 云端布局

入口：`https://49.232.128.132/skill-finder/`。
审核：`https://49.232.128.132/skill-finder/daily-reports`。
统一健康：`/skill-finder/api/health`。

- CentOS 7 上使用 Docker 的 Python 3.12 / Debian bookworm，避免改动主机 Python。
- 发布源码：`/opt/skill-finder/releases/20261018`，`current` 指向当前版本。
- Python 容器：`skill-finder:20261018`，只监听主机回环 `127.0.0.1:15177`。
- Nginx 新增独立 vhost，将 `/skill-finder/` 转发至后端；原站点根路径保留。
- 前端以 `VITE_BASE_PATH=/skill-finder/`、`VITE_API_BASE_URL=/skill-finder/api/v1` 构建。
  本机默认仍为 `/` 和 `/api/v1`，Vue history 使用 Vite BASE_URL。
- 业务数据库继续使用 `xixi` 的原五张表；独立 `skill_finder_service@localhost` 仅有
  五张业务表的 SELECT/INSERT/UPDATE/DELETE 权限。不重建数据库，不删除其他表。
- 服务配置：`/etc/skill-finder/service.env`；OpenClaw 配置：`/etc/skill-finder/openclaw.env`，
  均为 root 可读的私有环境文件，禁止复制到 Git。
- 日报及媒体：`/var/lib/skill-finder/reports/YYYY-MM-DD/`；
  抖音登录态及私有页面截图：`/var/lib/skill-finder/private/`。
- Docker 容器以非 root 用户运行，根文件系统只读，限制内存、CPU、进程数和日志大小。
- 不依赖操作电脑、本机代理或 Codex 在线；临时安装代理不得写入运行配置。

## 每天北京时间 08:00

`deploy/cron` 安装为 `/etc/cron.d/skill-finder`；主机时区必须是 Asia/Shanghai。
定时任务由服务器 crond 执行，无需在 Codex 桌面另建重复提醒。

1. 07:10 采集 GitHub Trending 日/周/月榜，沿用 AI / Agent / Skill / MCP / Plugin 范围。
2. 07:30 生成当天日报、中文配音、字幕和 720×1280 竖屏视频；07:45 对失败任务重试。
3. 08:00 调用送达任务。QQ 当前按用户要求不配置，任务记录 `not_configured`，不谎报送达。
4. 报告进入 `pending_review`，网站可预览、下载；不会因 08:00 到点而自动批准。

生成读取当天的快照；没有新数据则失败。AI 项目不足十个时如实标注数量，不补入旧数据。
视频由后向前倒数，每项展示名称、今日新增 Star、实际用途和来源日期；保留配音与字幕文件。
配音使用 Edge TTS `zh-CN-YunxiNeural`，失败时明确报告失败，不生成“静音成功”视频。
中文项目介绍通过用户明确提供的 DeepSeek Key 调用官方 API；`INTRO_API_KEY` 优先于旧 OpenCode 配置。
非 OpenCode 模型地址未配置通用密钥时，不会回退读取本机 OpenCode 凭据。

手动运行：

```sh
/opt/skill-finder/current/deploy/run-daily.sh collect
/opt/skill-finder/current/deploy/run-daily.sh generate
docker exec skill-finder python -m app.daily.cli generate --collect
docker logs --tail 100 skill-finder
tail -100 /var/log/skill-finder-daily.log
```

任务通过进程间文件锁串行执行；已进入审核及之后状态的当日成品保持不可变，重试不会覆盖批准对象。

## 审核与抖音

审核页展示视频、完整口播、标题和实际发布文案，管理操作使用 `X-Admin-Key`。
私有审核密钥在服务器环境文件，操作电脑另保存于被 Git 忽略的
`backend/.secrets/cloud-admin-key`。HTTP 公网请求只读；管理请求必须 HTTPS 或本机 SSH 隧道。

点“登录抖音（扫码）”后，以手机抖音扫描服务器浏览器的登录二维码。
登录截图必须持有审核密钥才能访问，登录态只保存在私有目录；不公开 cookie。
浏览器首次准备：

```sh
docker exec -e PLAYWRIGHT_BROWSERS_PATH=/data/browsers skill-finder \
  python -m playwright install chromium --only-shell
```

人工批准绑定视频 SHA-256、标题、口播与发布文案的摘要。内容变化后旧批准失效。
未批准、已退回、登录失效或发布适配器未启用时不提交视频。
需 `DOUYIN_PUBLISH_ENABLED=true` 且已有登录态，批准后才执行创作者后台上传与发布。
发布适配器依赖真实创作者后台，未登录账号前不能声称发布端到端验证完成；页面变化时停止并显示原因。
提交后若没有确认“发布成功”，记录 `publish_unknown`，必须人工核查，不自动重发。

## OpenClaw 与 QQ

OpenClaw 固定版本 2026.10.4，使用 Node 24 容器，监听 `127.0.0.1:18789`。
网关启用随机 token，仅开放 SSH 隧道访问；不公开到公网。
OpenClaw 容器内存上限为 768MiB（含 swap 上限 1536MiB），私有缓存与临时目录分别挂载，
根文件系统保持只读。关闭未使用的记忆向量检索和周期性心跳，避免额外模型调用。
使用用户提供的 DeepSeek Key，模型为经 `/models` 和实际请求验证的 `deepseek-flash`。
安装依赖的执行脚本按 npm 固定版本允许清单管理，不开启所有脚本。
QQ 根据用户要求暂不绑定，未安装或未授权的渠道不被报告成已连接。
后续提供机器人 AppID/AppSecret 和接收端 OpenID，再安装并配置官方 QQ 插件、测试送达，
将 `DAILY_OPENCLAW_COMMAND` 指向可用客户端并设置 `DAILY_QQ_TARGET`。
确定性采集与合成由主机定时任务控制，OpenClaw 模型调用不直接拥有视频批准权。

## HTTPS、续签与回滚

使用 Let’s Encrypt 的公开 IP shortlived 证书，有效期约六天。
`renew-certificate.sh` 每六小时检查续期并让 Nginx 重载证书，不能漏装该任务。
证书及私钥存放在 `/opt/skill-finder/letsencrypt/`，ACME webroot 在 `/opt/skill-finder/acme/`。
不得关闭 TLS 验证或用自签名证书冒充有效公网证书。

新版本发布到新的 release 目录；保留旧目录及镜像，再更新 current 和重建本服务容器。
回滚只切换本服务版本，不回滚或 DROP 共享数据库。

## 测试

后端 `ruff check .`、`pytest -q`；集成测试只允许独立 TEST_DATABASE_URL，未设置时跳过。
`tests/unit/test_daily_reports.py` 覆盖认证、哈希绑定、拒绝发布、无新数据失败和日期校验。
`test_github_client.py` 覆盖空 Token 匿名请求不发送 Authorization。
前端执行 lint、typecheck、Vitest 和 build；再通过实际 HTTPS 做健康、榜单和页面检查。
本次没有测试生产库的 DROP fixture，也没有未经审核提交任何抖音作品。

实际验收：后端 137 项通过、14 项独立测试库集成测试跳过；前端 30 项通过，
lint、类型检查和构建通过。公网 HTTPS 在 1440、375、320 像素视口无脚本错误或横向溢出。
2026-10-19 成品包含 10 个项目，720×1280 H.264/AAC 视频约 4 分 45 秒，处于待审核状态。
OpenClaw 已验证网关存活与模型配置，DeepSeek 官方 API 已完成真实调用；
QQ 送达和抖音真实账号发布尚未完成端到端验证。
