"""抖音创作者后台的扫码登录流程。

用 Playwright 的 headless Chromium 打开创作者上传页，每 2 秒把截图写到
`settings.douyin_storage_state` 所在目录（`login-screen.png` 供操作台查看），直到
同时出现 `sessionid` Cookie 与上传用的 file input，才把 storage state 写盘并收紧为
`0o600`。

过程状态写入同目录的 `login-status.json`：starting / scan_required / ready /
timed_out / browser_or_network_unavailable。整个流程持有日报全局锁，锁被占用时直接
返回 `another_daily_task_running`，不会并发打开第二个浏览器。私有登录态目录属于
运行时数据，其内容不得出现在日志或接口响应中。
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from filelock import Timeout

from app.core.config import settings
from app.daily import store


def private_dir() -> Path:
    """返回登录态所在目录并确保存在。

    目录由 `settings.douyin_storage_state` 推导，登录态与扫码截图都落在这里，
    不写入受版本控制的路径。
    """
    path = Path(settings.douyin_storage_state).resolve().parent
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_status(status: str) -> None:
    """原子写入登录状态供操作台读取。

    Args:
        status: `starting`、`scan_required`、`ready`、`timed_out` 或
            `browser_or_network_unavailable`。
    """
    path = private_dir() / "login-status.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"status": status}), encoding="utf-8")
    temp.replace(path)


async def login() -> dict:
    """在日报全局锁内执行扫码登录。

    Returns:
        `{"status": "ready"}` 表示登录态已保存；锁被占用时返回
        `{"status": "another_daily_task_running"}`，不会并发打开第二个浏览器。
    """
    try:
        with store.lock():
            return await _login()
    except Timeout:
        return {"status": "another_daily_task_running"}


async def _login() -> dict:
    """打开创作者后台，轮询 Cookie 与上传控件直到登录成功或超时。

    每 2 秒刷新 `login-screen.png` 供人工扫码，最多轮询 90 次（约 3 分钟）；成功后
    把 storage state 写盘并收紧为 `0o600`。

    Returns:
        `{"status": "ready"}`，其余情况返回 `{"status": "login_required"}`，具体
        原因写在 `login-status.json`。Playwright 在函数内导入，缺少浏览器依赖时
        只影响登录，不影响其他日报功能。
    """
    from playwright.async_api import Error, async_playwright

    save_status("starting")
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(viewport={"width": 1200, "height": 820})
            page = await context.new_page()
            await page.goto("https://creator.douyin.com/creator-micro/content/upload")
            for _ in range(90):
                screenshot = private_dir() / "login-screen.tmp.png"
                await page.screenshot(path=str(screenshot))
                screenshot.replace(private_dir() / "login-screen.png")
                cookies = await context.cookies()
                logged_in = any(
                    cookie["name"] in {"sessionid", "sessionid_ss"} and cookie["value"]
                    for cookie in cookies
                )
                if logged_in and await page.locator('input[type="file"]').count():
                    state = Path(settings.douyin_storage_state)
                    await context.storage_state(path=str(state))
                    os.chmod(state, 0o600)
                    save_status("ready")
                    await browser.close()
                    return {"status": "ready"}
                save_status("scan_required")
                await asyncio.sleep(2)
            await browser.close()
        save_status("timed_out")
    except (Error, OSError):
        save_status("browser_or_network_unavailable")
    return {"status": "login_required"}
