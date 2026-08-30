---
project: love530
type: overview
module: all
updated: 2026-08-26
---

# love530

`love530` 是 Java 8 + Spring Boot 2.6.13 的 Maven 多模块项目。父工程 artifactId 为 `love530`，根目录 `pom.xml` 负责模块聚合、公共版本和依赖管理，业务代码放在各业务模块内，跨模块公共能力优先放入 [[Development Rules|common 模块约定]]。

## 模块

- `common`：公共能力模块，提供 OSS 自动配置、上传工具、删除工具、URL 生成、object key 解析，以及通用认证抽象与自动配置。
- `lovestory`：恋爱相册 Web 应用，提供静态页面、照片上传、照片列表、删除接口、留言板和小游戏页面。
- `website`：个人主页/展示站点 Web 应用，包含主页静态资源、Web Demo、OSS Demo、Nacos Discovery 示例和提示词控制台入口。
- `imagetemplate`：图片提示词模板 Web 服务，提供模板库检索、prompt 渲染和 OpenAI 图片生成能力。
- `guitar`：Guitar 曲谱平台，提供认证、公开曲谱、上传、收藏夹和管理员审核能力。
- `website/python-a`：独立 A 股自选股 AI 研究台，不是 Maven 模块。
- `website/quant-a`：独立 FastAPI 量化研究台，不是 Maven 模块。

## 技术栈

- Java 8
- Maven
- Spring Boot 2.6.13
- Spring MVC / Spring Boot Starter Web
- MySQL
- MyBatis DAO + XML Mapper
- Alibaba Druid
- Aliyun OSS SDK
- OpenAI Images API
- Python 3.9+ / FastAPI / Uvicorn
- JUnit 5 / Spring Boot Test / AssertJ / Maven Surefire 2.22.2
- 原生 HTML / CSS / JavaScript

## 端口

- `website`：`8080`
- `lovestory`：`8081`
- `imagetemplate`：`8082`
- `guitar`：`8088`
- `python-a`：`5174`
- `quant-a`：`5175`
- `common`：不是独立 Web 服务，不作为应用端口启动

## 常用命令

```bash
mvn clean install
mvn test
mvn clean package -DskipTests
mvn -pl common test
mvn -pl lovestory -am test
mvn -pl website -am test
mvn -pl imagetemplate -am test
mvn -pl guitar -am test
mvn -pl lovestory -am spring-boot:run -Dspring-boot.run.main-class=com.ycxandwuqian.love.LovestoryApplication
mvn -pl website -am spring-boot:run
mvn -pl imagetemplate -am spring-boot:run
mvn -f guitar/pom.xml spring-boot:run
cd website/python-a && python server.py
cd website/quant-a && python -m uvicorn main:app --host 127.0.0.1 --port 5175
```

## 相关笔记

- [[Architecture]]
- [[Development Rules]]
- [[Testing]]
- [[API]]
- [[Decisions]]
- [[Tasks]]
