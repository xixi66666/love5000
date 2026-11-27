"""python-a 的服务层包，承载与 HTTP 层解耦、可单独测试的业务逻辑。

本包按职责拆分：账户与交易记账（``account_service`` / ``trade_service``）、
JSON 运行数据持久化（``storage_service``）、Obsidian 写入
（``obsidian_service`` / ``knowledge_graph_service``）、股票名称匹配与行业概念
元数据（``stock_match_service`` / ``stock_metadata_service``）、上游研究数据源
（``tencent_quote_provider`` / ``eastmoney_research_provider`` /
``sina_fund_flow_provider`` / ``cninfo_announcement_provider``）、统一模型入口
（``model_hub``）以及截图视觉解析（``vision_parse_service``）。

``__init__`` 刻意不导入任何子模块：既避免服务启动时的循环导入，也保证每个模块
都能被 unittest 单独加载。数据来源是本地 JSON 文件与腾讯、东方财富、新浪、巨潮等
公开行情和公告接口，全程不使用数据库；运行数据写入 ``obsidian-vault/A股AI`` 下的
JSON 与 Markdown。所有网络请求和文件写入都在各自模块内降级为可读错误，不向
``server.py`` 的请求处理器抛裸异常。
"""
