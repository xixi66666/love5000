# personal-agent

- 本目录与 website/lovestory 同级，是 Java8 + Spring Boot2.6.13 Maven模块，已加入父pom；不使用Python。
- 主类 `com.example.personalagent.PersonalAgentApplication`，默认回环地址5178，静态前端在 `src/main/resources/static`。
- 前端使用本机参考目录中第3/10/11份原创设计提示词：黑白/冰蓝、银白波浪、本地SVG图标、玻璃面板、双栏登录与响应式导航。不要改成旧深绿衬线版或接入远程字体/CDN；工作台统计必须来自实际API，不填演示资产或伪造增长图。
- 只由03 Deep Woods入口点击启动已构建jar，不随website自动启动/停止；website只维护集成入口/启动/健康。
- 真实私人数据默认在 LOCALAPPDATA/ Love530/PersonalAgent，禁止写入代码、测试fixture、日志或提交；本目录`.runtime/`仅构造测试使用。
- 本地H2持久化经storage.DocumentDao与mapper/DocumentMapper.xml；禁止JdbcTemplate、JPA或Java内联SQL。金额用BigDecimal和十进制字符串。
- Vault系统记录受哈希保护，外部编辑进入待核对，不自动覆盖。人工心得/原始笔记单独索引；记录UUID稳定，事件排序与录入目录分开。
- 不执行读书skill脚本，不读取未经允许目录的书源；不把用户私人内容发送到公开搜索URL。
- 模型/行情测试用替身，不用真实Key或资产。接口只允许本机，健康接口没有私人字段，其余API独立Session+CSRF。
- 每次API/配置/数据/启动变化同步本README、AGENTS和根/website文档。验证 `mvn -pl personal-agent -am test`，前端 `node --check src/main/resources/static/app.js`。
