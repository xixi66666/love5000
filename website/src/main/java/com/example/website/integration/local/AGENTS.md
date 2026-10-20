# 本机服务集成

管理三个固定服务：Strata/Qwen（9999）、AIMedia 操作台（8190）、H3 的 ComfyUI 引擎（8189）。它们是既有独立应用，不加入 Maven 聚合，不随 website 自动启动或关闭。默认目录为 F:/model/Strata 和 D:/Code/Java_Code/AIMedia，可用 STRATA_HOME、AIMEDIA_HOME 覆盖。

启动 Strata 使用 --lazy，仅启动服务；加载/卸载通过既有 /load、/unload。H3 通过提交生成任务加载权重，启动引擎不代表 H3 已加载；/free 释放 ComfyUI 缓存中的模型，是异步请求，不能谎报已经完成释放。停止和释放视频引擎前检查 ComfyUI 队列及 AIMedia 作业，忙碌或无法确认队列时拒绝操作。

控制 API 为 /api/services/local/{strata|aimedia|h3}/{status|health|start|load|unload|stop}。只有 Strata 支持 load，AIMedia 不支持 unload。仅允许回环连接、localhost/127.0.0.1/::1 Host 和同源 Origin；修改请求需 X-Love530-Local: 1。禁止接受浏览器传入的命令、PID、路径或任意 URL。

停止脚本必须同时核对 Python 命令中的项目路径、服务脚本和端口，不按 python.exe 进程名批量结束。若监听端口属于其他应用，拒绝停止。日志和响应不得包含凭据、提示词或用户作品内容。

单元测试使用模拟客户端和进程启动器，不加载真实模型或生成视频。运行 mvn -pl website -am test -Dtest=LocalServicesManagerTest,LocalServicesControllerTest -Dsurefire.failIfNoSpecifiedTests=false。改动入口和 API 时同步根文档与 website 文档。


## 健康巡检频率与 IDEA 日志

`ServiceHealthMonitor` 在 website 的 `ApplicationReadyEvent` 后统一巡检一次，完成后每半小时巡检；
`GET /api/services/health` 返回最近结果，打开或刷新多个首页不会额外请求子服务。
首页按 `data-health-service` 项目名匹配聚合结果，每半小时读取一次；website 自身页面入口仍检查页面可达性。
本机模型管理页首次进入读取状态，此后每半小时自动刷新，手动启停、加载及卸载后立即更新状态。
后台巡检不依赖浏览器是否打开。启动子服务时必要的就绪确认保留，不使用半小时周期等待启动。

配置在 `website/src/main/resources/application.yml`：
`website.service-health.check-interval-ms: 1800000`（毫秒），
`website.service-health.scheduled-enabled: true`；测试设置后者为 false，避免后台访问真实服务。
健康日志统一包含 `[健康检查][项目=skill-finder]` 等明确项目名，以及状态、HTTP 状态码和耗时；
本机模型状态日志也携带 strata / aimedia / h3 项目名，不记录凭据。
IDEA 中重新运行 `WebsiteApplication` 后生效，浏览器刷新首页以加载新脚本。
验证：`mvn -pl website -am test`、`node website/src/test/js/service-health.test.js`、
`node website/src/test/js/homepage-motion.test.js`。定时测试通过捕获调度回调模拟半小时流逝，无需实际等待。
