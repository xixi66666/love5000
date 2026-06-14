# website

`website` 是 `love530` 聚合工程中的个人主页/展示站点 Web 服务，默认端口 `8080`。它同时负责提供博客、提示词控制台、静态首页入口，以及 `python-a`、`quant-a`、`video` 三个独立 Python 子服务的自动启动和健康检查。

## 功能

- 个人主页静态站点。
- 博客 API 和前端页面。
- 提示词控制台和静态提示词库页面。
- `python-a`、`quant-a`、`video` 的入口、健康检测和自动启动。
- Web、OSS、Nacos Discovery 示例代码。

## 运行

```bash
mvn -pl website -am spring-boot:run
```

访问：

```text
http://localhost:8080/
```

直接启动 `website` 时，会默认检查并拉起：

```text
http://127.0.0.1:5174/api/health  python-a
http://127.0.0.1:5175/api/health  quant-a
http://127.0.0.1:5176/api/health  video
```

## 主要目录

```text
src/main/java/com/example/website/
  auth/         common 认证适配
  blog/         博客 API
  demos/        示例代码
  integration/  Python 子服务自动启动
  prompt/       提示词控制台后端
src/main/resources/static/
  index.html
  blog/
  css/
  js/
  media/
  prompt-console/
python-a/
quant-a/
video/
```

## 测试

```bash
mvn -pl website -am test
```

修改 Python 子服务自动启动逻辑时，至少运行对应的 `PythonAAutoStartRunnerTest`、`QuantAAutoStartRunnerTest` 或 `VideoAutoStartRunnerTest`。测试必须关闭外部子进程自动启动。

## 文档维护

每次修改首页入口、提示词控制台、博客、自动启动配置、Python 子服务集成、端口、API、静态资源目录或测试方式时，必须同步更新 `website/AGENTS.md`、本 README，以及根目录 `AGENTS.md` / `README.md` 中相关内容。
