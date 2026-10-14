# personal-agent

- 本目录与 website/lovestory 同级，是 Java8 + Spring Boot2.6.13 Maven模块，已加入父pom；不使用Python。
- 主类 `com.example.personalagent.PersonalAgentApplication`，默认回环地址5178，静态前端在 `src/main/resources/static`。
- 前端保留MotionSites参考的顶部胶囊导航、大字排版和原生切页动效；全屏背景为Pexels森林湖泊晨雾实拍，4K原片转1920×1080，森林灰绿配色与深色玻璃面板保障阅读。视频与海报在static/media/，作者、授权和处理方式见其README；更新素材时同步资源版本，motion.js使用原生视频与Web Animations，不接入远程字体/CDN或前端框架。工作台统计必须来自实际API，不填演示资产或伪造增长图。
- 页面资料请求保留旧视图，最新viewToken在数据就绪后统一commitView转场；不要恢复清空为loading的闪烁切页。后台暂停视频，用户暂停不能被导航/返回前台覆盖；减少动画时默认不加载视频，保留静态海报。验证node src/test/js/motion.test.js。
- 只由03 Deep Woods入口点击启动已构建jar，不随website自动启动/停止；website只维护集成入口/启动/健康。
- 真实私人数据默认在 LOCALAPPDATA/ Love530/PersonalAgent，禁止写入代码、测试fixture、日志或提交；本目录`.runtime/`仅构造测试使用。
- 本地H2持久化经storage.DocumentDao与mapper/DocumentMapper.xml；禁止JdbcTemplate、JPA或Java内联SQL。金额用BigDecimal和十进制字符串。
- Vault系统记录受哈希保护，外部编辑进入待核对，不自动覆盖。人工心得/原始笔记单独索引；记录UUID稳定，事件排序与录入目录分开。
- 不执行读书skill脚本，不读取未经允许目录的书源；不把用户私人内容发送到公开搜索URL。
- 模型/行情测试用替身，不用真实Key或资产。接口只允许本机，健康接口没有私人字段，其余API独立Session+CSRF。
- 首页`/`和`/index.html`允许无Origin的GET顶层文档导航跨站进入，兼容localhost:8080跳到127.0.0.1:5178；不能把例外扩大到API、iframe或跨站fetch，修改时保留入口及安全边界回归测试。
- 每次API/配置/数据/启动变化同步本README、AGENTS和根/website文档。验证 `mvn -pl personal-agent -am test`，前端 `node --check src/main/resources/static/app.js`。
