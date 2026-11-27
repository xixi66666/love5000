"""近 30 天最热多源研究：封装用户级 last30days skill 的调用边界。

研究本身由用户目录下已安装的 skill（`~/.codex/skills/last30days` 等）执行，本包只
负责发现运行时、限制子进程环境、解析 JSON 结果并缓存排名，不实现第二套采集。
数据库读写只经 `Last30DaysReportStore`；超时、重试与降级都在 `service` 里统一处理，
路由层不重复实现。
"""
