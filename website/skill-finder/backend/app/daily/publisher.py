from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.daily import store
from app.daily.pipeline import now
from app.daily.progress import Tracker


async def publish(day: str) -> dict:
    """Only a hash-bound human approval can reach the creator-center submit button."""
    with store.lock():
        report = store.load(day)
        if report.get("status") == "published":
            return report
        if not store.verify_approval(report):
            raise ValueError("A current, explicit video approval is required")
        state = Path(settings.douyin_storage_state)
        progress = Tracker(day)
        if not settings.douyin_publish_enabled or not state.is_file():
            report["publisher_status"] = "awaiting_login"
            store.save(report)
            progress.set("publish", "blocked", "请启用抖音发布并完成创作者账号登录。")
            return report
        from playwright.async_api import Error, async_playwright

        submitted = False
        report["publisher_status"] = "uploading"
        store.save(report)
        progress.begin("publish", "正在打开创作者后台并上传当前批准的视频。")
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                context = await browser.new_context(storage_state=str(state))
                page = await context.new_page()
                await page.goto("https://creator.douyin.com/creator-micro/content/upload")
                file_input = page.locator('input[type="file"]')
                await file_input.wait_for(timeout=30000)
                await file_input.set_input_files(str(store.report_dir(day) / "video.mp4"))
                title = page.get_by_placeholder("填写作品标题，为作品获得更多流量")
                await title.fill(report["title"][:30], timeout=120000)
                caption = page.locator('[contenteditable="true"]').first
                await caption.fill(report["caption"])
                # UI changes, login challenges, or ambiguous upload state fail closed.
                button = page.get_by_role("button", name="发布", exact=True)
                await button.wait_for(state="visible", timeout=120000)
                if not await button.is_enabled():
                    raise RuntimeError("Creator center is not ready for publication")
                if not store.verify_approval(store.load(day)):
                    raise ValueError("Approval changed during upload")
                report.update(status="publishing", publisher_status="submitting")
                store.save(report)
                progress.begin("publish", "上传已就绪，正在提交并等待平台确认。")
                submitted = True
                await button.click()
                await page.get_by_text("发布成功", exact=False).first.wait_for(timeout=120000)
                report.update(
                    status="published", publisher_status="published", published_at=now(),
                    publisher_receipt_url=page.url,
                )
                await context.storage_state(path=str(state))
                await browser.close()
                progress.finish("publish", "平台已显示发布成功。")
        except (Error, OSError, ValueError, RuntimeError) as exc:
            report.update(
                status="publish_unknown" if submitted else "approved",
                publisher_status="verify_manually" if submitted else "login_or_ui_required",
                publisher_error=type(exc).__name__,
            )
            progress.set("publish", "uncertain" if submitted else "blocked",
                         "提交结果未确认，请到抖音作品管理核查，系统不会自动重发。" if submitted
                         else "请检查账号登录或创作者后台页面后再重试。")
            # A submission with an unknown outcome must never be automatically retried.
        store.save(report)
        return report
