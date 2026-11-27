"""抓取工作台的后端内核层。

包含浏览器单例（`browser_manager`）、会话与历史回放（`session`）、页面内 DOM
提取脚本（`dom_extractor`）以及调度任务的 SQLite 访问（`db`）。这一层不注册
HTTP 路由，只被 `main.py` 与 `services/` 调用；本包不导出任何符号，
各模块都按完整路径导入以保持依赖方向清晰（core 不依赖 services）。
"""
