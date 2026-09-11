# love5000 / love530

## 统一健康检查

`lovestory`、`imagetemplate`、`python-a` 和 `quant-a`
统一提供 `GET /api/health`，响应顶层包含 `success=true` 与稳定的 `service`。
启动 `website` 后可访问 `GET http://127.0.0.1:8080/api/services/health` 并行查看四个服务；
HTTP 200 表示聚合成功，`healthy` 表示是否全部在线。Java 探测默认连接/读取超时为
2000/3000ms。

相关 Java 回归命令：

```bash
mvn -pl website,lovestory,imagetemplate -am test
```

`love5000` 是一个 Java 8 + Spring Boot 2.6.13 的 Maven 多模块项目，父工程 artifactId 为 `love530`。仓库同时托管两个独立 Python 微应用，用于 A 股研究和量化研究。

## 模块

Maven 聚合模块：

- `common`：公共 OSS 工具、自动配置和通用 Session 认证能力。
- `lovestory`：恋爱相册、照片上传、留言板和吉他视频卡片 Web 应用。
- `website`：电影化个人主页/展示站点、提示词控制台，以及 5 个服务入口、实时健康状态和 Python 子服务自动启动；首页提供四场景视频切换与响应式液态玻璃服务 Dock。
- `imagetemplate`：聚合 47 条精选图片模板和 Prompt Console 的 4409 条公开提示词，总计 4456 条，并按 15 个一级功能与二级场景检索；提供按需详情和 OpenAI Images API 生成服务，前端采用虎主题编辑式黑色工作台、橙色高对比操作、dense 模板展廊和本地 GSAP 滚动动效，模板 JSON 与变量剧本均可手工编辑。

独立 Python 微应用：

- `website/python-a`：A 股自选股 AI 研究台，默认端口 `5174`。
- `website/quant-a`：A 股多因子量化研究台，默认端口 `5175`。

根目录下的 `python-a/`、`quant-a/` 不是当前主要接入路径；当前运行和文档维护以 `website/` 下的两个子服务为准。

## 快速开始

从仓库根目录执行：

```bash
cd C:/Code/Java_Code/love5000
mvn test
```

启动 `website`：

```bash
mvn -pl website -am spring-boot:run
```

`website` 默认端口为 `8080`，启动时会检查并自动拉起 `website/python-a` 和 `website/quant-a`。如果对应健康检查已经可用，会复用已有服务。

首页是无需前端构建的单视口原生页面，集中展示恋爱相册、图片模板、Prompt Console、A 股研究台和 Quant 研究台。每个入口保留端口标识和实时状态；顶部只保留登录、注册账户操作，登录后切换为退出，移动端继续使用横向可滑动服务 Dock。

`imagetemplate` 首页同样无需前端构建，按“灵感大厅 → 模板解构 → Prompt 编导台 → 图片生成舱”组织为编辑式黑色 AI 创作工作台。页面使用本地虎主题背景、宽幅分屏首屏、内嵌图像标题、创作理念轮播、橙色高对比操作和三段横向交互面板；灵感大厅默认每页 48 条，顶部常驻搜索、仅图片开关、结果计数和清除筛选，桌面端左侧集中展示“一级功能 + 二级场景”及高级筛选，右侧使用 dense 密排结果网格。页面支持 300ms 搜索防抖、加载更多和详情按需读取；模板解构中的 JSON 可直接编辑并校验，进入 Prompt 编导台时同步到可继续修改的变量剧本。GSAP 3.13.0 与 ScrollTrigger 从模块本地静态资源加载，并对脚本缺失及 `prefers-reduced-motion` 提供静态降级；窄屏流程恢复为底部横向排列，切换场景保留已选模板、Prompt、生成参数和结果。

Prompt Console 大库的唯一源码是 `website/src/main/resources/static/prompt-console/data/prompt-library.json`。构建 imagetemplate 时 Maven 会将它复制到 jar 的 `templates/prompt-console/prompt-library.json`，运行时不要求 website 服务在线；`GET /api/image-templates/meta` 可检查 4456 条聚合数据、功能分类树及其 `READY` 状态。

Prompt Console 页面（`prompt-console/index.html`）的数据已服务端化：4409 条提示词、10 个大分类和 6 个来源导入 MySQL `xixi` 库的 `prompt_entry`/`prompt_source`/`prompt_group` 三张表，页面通过 `GET /api/prompts/meta`、`GET /api/prompts`（服务端分页/搜索，`size` 默认 48 最大 100）和 `GET /api/prompts/{id}` 读取，不再直接 fetch 本地 JSON。页面提供"添加提示词"按钮，通过 `POST /api/prompts` 手动写入（大分类按库中既有归属自动推导，未知小分类归入"其他"，来源默认"手动添加"）；当前添加接口不加鉴权。大分类 slug 在导入时按 `prompt-category-groups.js` 的同一映射写入，`prompt-category-groups.js` 保留为导入工具与 node 测试的数据源。

其他服务：

```bash
mvn -pl lovestory -am spring-boot:run -Dspring-boot.run.main-class=com.ycxandwuqian.love.LovestoryApplication
mvn -pl imagetemplate -am spring-boot:run
```

Python 子服务可单独启动：

```bash
cd website/python-a && python server.py
cd website/quant-a && python -m uvicorn main:app --host 127.0.0.1 --port 5175
```

## 端口

- `website`：`8080`
- `lovestory`：`8081`
- `imagetemplate`：`8082`
- `python-a`：`5174`
- `quant-a`：`5175`

## 测试

Java 模块：

```bash
mvn test
mvn -pl common test
mvn -pl lovestory -am test
mvn -pl website -am test
mvn -pl imagetemplate -am test
```

验证 imagetemplate 独立包包含聚合大库：

```powershell
mvn -pl imagetemplate -am clean package -DskipTests
jar tf imagetemplate/target/imagetemplate-0.0.1-SNAPSHOT.jar | Select-String "templates/prompt-console/prompt-library.json"
```

Python 子服务：

```bash
cd website/python-a && python -m unittest discover -s tests -v
cd website/quant-a && python -m pytest -v
```

## 配置与安全

不要提交真实数据库密码、OSS AccessKey、OpenAI API Key、DeepSeek Key、Tushare Token、腾讯云密钥或 DashScope Key。新增配置优先使用环境变量或本地私有配置文件。

`lovestory` 默认连接本机 `lovestory` 数据库并关闭 OSS。需要连接其他数据库或启用 OSS 时，使用 `LOVESTORY_DB_URL`、`LOVESTORY_DB_USERNAME`、`LOVESTORY_DB_PASSWORD` 和 `LOVE530_OSS_*` 环境变量覆盖。`website` 数据库使用 `WEBSITE_DB_URL`、`WEBSITE_DB_USERNAME`、`WEBSITE_DB_PASSWORD` 覆盖，默认指向腾讯云 `xixi` 库（`jdbc:mysql://49.232.128.132:3306/xixi`），提示词库和认证共用该数据源；密码必须走环境变量，仓库内不提供真实凭据默认值。

常见私有文件已在 `.gitignore` 中忽略，例如：

- `website/python-a/deepseek.local.json`
- `website/quant-a/data/`
- `.env`、`.venv/`、`__pycache__/`、`.pytest_cache/`、`*.log`

## 文档维护规则

每次修改项目结构、模块职责、启动命令、端口、配置项、API、数据目录、测试方式或部署入口时，必须同步更新根 `AGENTS.md` / `README.md`，以及受影响模块或微应用目录下的 `AGENTS.md` / `README.md`。文档和代码不一致时，本次改动不能视为完成。

开发代理细节、模块边界、API 清单和测试要求见根目录 `AGENTS.md`，模块目录下的 `AGENTS.md` / `README.md` 以各自模块为准。

## 代码提交
本地代码提交到远程仓库时，通常会遇到网络问题导致提交失败，不用处理，直接进行重试，直到成功为止。
