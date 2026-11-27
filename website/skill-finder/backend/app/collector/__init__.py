"""GitHub Trending 采集子包。

``trending`` 用 Scrapling 抓取日/周/月三个榜单页并解析 HTML，``classifier`` 依据
topic 与名称/描述里的关键词把仓库归入 AGENT/SKILL/MCP/PLUGIN，``github_client``
通过 GitHub API 补全 Star、topic、README 等字段，``service`` 负责把三者编排成一次
可落库的采集任务。

设计约束：采集必须降级——单个周期的页面抓不到只让本轮变成 ``PARTIAL`` 并保留上一次
榜单，绝不伪造成功；任何模块都不打印 GitHub Token 或数据库凭据。
"""
