"""定时抓取任务的调度层。

模块级单例 ``scheduler``（APScheduler 的 AsyncIOScheduler）在 FastAPI lifespan 里
启动与关闭；任务定义本身存在 ``backend/jobs.db`` 的 ``jobs`` 表，这里只负责把它们
同步成定时触发器并执行。

一次执行的流程：读库 → 用 `services.code_generator` 把历史编译成脚本 → 写临时
``.py`` → 起子进程跑 → 从 stdout 里捡出 ``{...}`` 形式的字典行 → 有 webhook 就
POST 过去 → 回写 ``last_run``/``next_run``。

失败行为：读库之后的执行过程整段包在 try/except 里，任何异常只打印日志、不向调度器
抛，否则 APScheduler 会把该任务标记为失效；临时文件在 finally 里删除；
webhook 失败只记日志，不影响 ``last_run`` 的更新。``get_job`` 本身在 try 之外，
数据库不可用时异常会直接冒泡到调度器。
"""

import sys
import tempfile
import asyncio
import os
import requests
import ast
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from core.db import get_job, get_all_jobs, update_job_runs, update_job_enabled

# Initialize scheduler
# 进程级单例：路由层用它摘除单个定时器，lifespan 用它启停。
scheduler = AsyncIOScheduler()

async def run_crawler_job(job_id: str):
    """执行一次定时任务：编译配方、跑子进程、回传 webhook、记录时间。

    Args:
        job_id: ``jobs`` 表主键；cron 触发与 ``POST /api/scheduler/jobs/{job_id}/run``
            都走这个入口。

    副作用：写临时文件、起子进程、发起 webhook 请求、更新数据库行。
    任务不存在或已停用时直接返回，不报错——手动触发一个被停用的任务是合法操作。
    """
    job = get_job(job_id)
    if not job or not job.get("enabled"):
        return
        
    print(f"⏰ [Scheduler] Triggered crawler run for job '{job['name']}' ({job_id})")
    
    # Imports code generator dynamically to avoid circular dependencies
    from services.code_generator import generate_scrapling_code
    
    # 1. Compile history into Python Scrapling recipe
    # 定时执行固定使用「过盾 + 拦广告 + 保留资源」的配置，不支持按任务覆盖。
    code = generate_scrapling_code(
        job["history"], 
        solve_cloudflare=True, 
        block_ads=True, 
        disable_resources=False
    )
    
    temp_file_path = None
    try:
        # 2. Write code to temp file
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write(code)
            temp_file_path = f.name
            
        # 3. Launch subprocess headless run
        process = await asyncio.create_subprocess_exec(
            sys.executable, temp_file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        stdout_str = stdout.decode("utf-8", errors="ignore")
        stderr_str = stderr.decode("utf-8", errors="ignore")
        
        # 4. Extract printed dictionary objects
        # 配方用 print(dict) 输出每一行数据，这里按「以 { 开头、以 } 结尾」逐行还原；
        # 用 literal_eval 而不是 eval，避免执行抓取结果里的任意表达式。
        scraped_data = []
        for line in stdout_str.split("\n"):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    item = ast.literal_eval(line)
                    if isinstance(item, dict):
                        scraped_data.append(item)
                except Exception:
                    pass
                    
        print(f"📊 [Scheduler] Job '{job['name']}' completed. Crawled {len(scraped_data)} items.")
        if stderr_str.strip():
            print(f"⚠️ [Scheduler] Warnings/Errors for '{job['name']}':\n{stderr_str}")
            
        # 5. Dispatch webhook POST
        # 没有抓到任何数据时不回传：避免下游把空数组覆盖掉上一次的好结果。
        if job.get("webhook_url") and scraped_data:
            webhook_url = job["webhook_url"]
            print(f"🌐 [Scheduler] POSTing payload to webhook: {webhook_url}")
            try:
                # requests 是同步库，丢到默认线程池执行，避免阻塞事件循环。
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: requests.post(
                        webhook_url, 
                        json={
                            "job_id": job_id,
                            "job_name": job["name"],
                            "url": job["url"],
                            "timestamp": datetime.utcnow().isoformat(),
                            "count": len(scraped_data),
                            "data": scraped_data
                        }, 
                        headers={"Content-Type": "application/json"},
                        timeout=15
                    )
                )
                print(f"✅ [Scheduler] Webhook sent successfully for job '{job['name']}'")
            except Exception as wh_err:
                print(f"❌ [Scheduler] Webhook dispatch failed for job '{job['name']}': {wh_err}")
                
        # 6. Update database record with execution details
        last_run_str = datetime.utcnow().isoformat()
        
        # Calculate next run time
        # 只有仍在调度表里的任务才有 next_run_time；手动触发且任务被停用时为 None，
        # 此时 update_job_runs 会保留库里原有的 next_run。
        aps_job = scheduler.get_job(job_id)
        next_run_str = None
        if aps_job and aps_job.next_run_time:
            next_run_str = aps_job.next_run_time.isoformat()
            
        update_job_runs(job_id, last_run_str, next_run_str)
        
    except Exception as e:
        print(f"❌ [Scheduler] Execution error running job '{job['name']}': {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

def sync_db_to_scheduler():
    """把 SQLite 里启用的任务全量重建到当前 APScheduler 实例。

    先清空调度器里所有定时器，再为每条 ``enabled`` 的任务按 cron 重新挂载，
    因此它是「全量重建」而不是增量同步：任何一条任务的改动都会重排其余任务。
    单条任务的 cron 非法只打印日志并跳过该任务，其余任务照常调度。
    """
    # 1. Clear existing jobs to reload
    for active_job in scheduler.get_jobs():
        scheduler.remove_job(active_job.id)
        
    jobs = get_all_jobs()
    for job in jobs:
        if job["enabled"]:
            try:
                scheduler.add_job(
                    run_crawler_job,
                    trigger=CronTrigger.from_crontab(job["cron_expression"]),
                    id=job["id"],
                    args=[job["id"]],
                    replace_existing=True
                )
                print(f"📅 [Scheduler] Scheduled job '{job['name']}' (Cron: {job['cron_expression']})")
                
                # Fetch next run time to save in db
                aps_job = scheduler.get_job(job["id"])
                if aps_job and aps_job.next_run_time:
                    update_job_runs(job["id"], job.get("last_run"), aps_job.next_run_time.isoformat())
            except Exception as e:
                print(f"❌ [Scheduler] Failed to schedule job '{job['name']}': {e}")

def start_scheduler():
    """启动调度器并载入库里的任务；已启动时不做任何事（lifespan 可重入）。

    启动后才调用 `sync_db_to_scheduler`，因为未运行的调度器不能计算
    ``next_run_time``。
    """
    if not scheduler.running:
        scheduler.start()
        print("🚀 [Scheduler] APScheduler Background Service Started.")
        sync_db_to_scheduler()

def stop_scheduler():
    """停止调度器；未启动时调用无副作用。

    只停调度器，不改数据库里的 ``enabled``，所以下次启动会按原配置恢复。
    """
    if scheduler.running:
        scheduler.shutdown()
        print("🛑 [Scheduler] APScheduler Background Service Stopped.")
