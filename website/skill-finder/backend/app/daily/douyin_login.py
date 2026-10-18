from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from filelock import Timeout

from app.core.config import settings
from app.daily import store


def private_dir() -> Path:
    path = Path(settings.douyin_storage_state).resolve().parent
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_status(status: str) -> None:
    path = private_dir() / "login-status.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"status": status}), encoding="utf-8")
    temp.replace(path)


async def login() -> dict:
    try:
        with store.lock():
            return await _login()
    except Timeout:
        return {"status": "another_daily_task_running"}


async def _login() -> dict:
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
