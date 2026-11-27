"""调度任务的 SQLite 持久层。

任务（cron 配方）保存在 ``backend/jobs.db`` 的 ``jobs`` 表，路径由本文件位置推导
而来，与启动时的工作目录无关。公开函数：`init_db`、`save_job`、`get_job`、
`get_all_jobs`、`delete_job`、`update_job_enabled`、`update_job_runs`。

约定与失败行为：

- 每个公开函数都先调用 `init_db()`，因此首次访问时会自动建表，不存在“忘记初始化”；
  数据库文件不存在时由 sqlite3 自动创建。
- ``history`` 以 JSON 文本列存储，读写时统一序列化/反序列化，调用方拿到的是列表。
- ``with get_db_connection()`` 只负责提交或回滚事务，不会关闭连接：每次调用都新开
  一条连接，由解释器回收，所以这里没有显式 close。
- 路径不可写、磁盘满或 JSON 列被外部改坏时按 sqlite3/JSON 异常向上抛出，由调用方
  处理（路由转成 500，调度器打印日志后跳过该任务），不会静默吞掉。
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

# 数据库固定落在 backend/ 目录（本文件的父目录的父目录），便于整目录删除重建。
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jobs.db")

def get_db_connection():
    """打开 ``jobs.db`` 连接并把行工厂设为 sqlite3.Row。

    Returns:
        新建的连接；``row_factory`` 使查询结果支持按列名取值，`get_job`
        等函数才能直接 ``dict(row)``。
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """建表（幂等）。

    表结构对应 `services.scheduler` 的读写字段：``history`` 为 JSON 文本，
    ``enabled`` 用 0/1 存布尔，``last_run``/``next_run`` 存 ISO 时间字符串。
    使用 ``CREATE TABLE IF NOT EXISTS``，重复调用不会清空已有任务。
    """
    with get_db_connection() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            history TEXT NOT NULL,
            cron_expression TEXT NOT NULL,
            webhook_url TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            last_run TEXT,
            next_run TEXT,
            created_at TEXT NOT NULL
        )
        """)
        conn.commit()

def save_job(job_id: str, name: str, url: str, history: List[Dict[str, Any]], cron_expression: str, webhook_url: str, enabled: bool = True) -> Dict[str, Any]:
    """新增或整体覆盖一条任务记录。

    使用 ``INSERT OR REPLACE``，因此同一 ``job_id`` 再次保存会重置 ``last_run`` /
    ``next_run``（新记录里没有这两列的值，落回 NULL），下次调度时重新计算。

    Args:
        job_id: 任务主键，新建时由路由层生成 UUID，编辑时沿用前端回传的 id。
        name: 任务名，用于日志与 webhook 报文。
        url: 入口网址，仅供展示与 webhook 使用。
        history: 录制下来的操作历史，按 JSON 文本落库。
        cron_expression: 五段式 crontab 表达式，由 APScheduler 解析。
        webhook_url: 抓取完成后的回传地址；空字符串表示不回调。
        enabled: 是否启用；以 0/1 存储。

    Returns:
        写入后重新读取的完整记录（含布尔化后的 ``enabled`` 与解析后的 ``history``）。

    Raises:
        sqlite3.Error: 数据库不可写或表结构被破坏。
    """
    init_db()
    created_at = datetime.utcnow().isoformat()
    history_json = json.dumps(history)
    enabled_val = 1 if enabled else 0
    
    with get_db_connection() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO jobs (id, name, url, history, cron_expression, webhook_url, enabled, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_id, name, url, history_json, cron_expression, webhook_url, enabled_val, created_at))
        conn.commit()
        
    return get_job(job_id)

def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """按主键读取单条任务。

    Args:
        job_id: 任务主键。

    Returns:
        任务字典（``history`` 已反序列化为列表、``enabled`` 已转成 bool）；
        记录不存在时返回 ``None``，而不是抛异常，调用方据此返回 HTTP 404。
    """
    init_db()
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row:
            job = dict(row)
            job["history"] = json.loads(job["history"])
            job["enabled"] = bool(job["enabled"])
            return job
    return None

def get_all_jobs() -> List[Dict[str, Any]]:
    """读取全部任务，按创建时间倒序（最新任务排在最前，供列表面板展示）。

    Returns:
        任务列表；没有任务时为空列表。``history``/``enabled`` 的转换规则与
        `get_job` 一致。单条记录的 ``history`` 若被外部写成非法 JSON，
        ``json.loads`` 会抛出 ``ValueError`` 并中断整个列表查询。
    """
    init_db()
    jobs = []
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
        for row in rows:
            job = dict(row)
            job["history"] = json.loads(job["history"])
            job["enabled"] = bool(job["enabled"])
            jobs.append(job)
    return jobs

def delete_job(job_id: str):
    """删除一条任务；主键不存在时不报错（删除是幂等的）。

    Args:
        job_id: 要删除的任务主键。
    """
    init_db()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()

def update_job_enabled(job_id: str, enabled: bool):
    """只切换启用状态，不动历史与 cron 配置。

    Args:
        job_id: 任务主键。
        enabled: ``True`` 写 1、``False`` 写 0；随后由调度器同步决定是否挂载定时任务。
    """
    init_db()
    enabled_val = 1 if enabled else 0
    with get_db_connection() as conn:
        conn.execute("UPDATE jobs SET enabled = ? WHERE id = ?", (enabled_val, job_id))
        conn.commit()

def update_job_runs(job_id: str, last_run: str, next_run: Optional[str] = None):
    """记录最近执行时间与下一次计划时间。

    Args:
        job_id: 任务主键。
        last_run: 最近一次执行的 UTC ISO 时间；调度器回填失败时可能是空值。
        next_run: 下次计划执行时间；为 ``None``/空串时只更新 ``last_run``，
            保留库里原来的 ``next_run``，避免手动执行把计划时间清空。
    """
    init_db()
    with get_db_connection() as conn:
        if next_run:
            conn.execute("UPDATE jobs SET last_run = ?, next_run = ? WHERE id = ?", (last_run, next_run, job_id))
        else:
            conn.execute("UPDATE jobs SET last_run = ? WHERE id = ?", (last_run, job_id))
        conn.commit()

# 导入即建表：测试用 TestClient 直接导入 main 时无需再显式初始化。
init_db()
