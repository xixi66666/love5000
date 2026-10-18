from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.daily import store
from app.daily.pipeline import now


async def publish(day: str) -> dict:
    """Only a hash-bound human approval can reach the creator-center submit button."""
    with store.lock():
        report = store.load(day)
        if report.get("status") == "published":
            return report
        if not store.verify_approval(report):
            raise ValueError("A current, explicit video approval is required")
        state = Path(settings.douyin_storage_state)
        if not settings.douyin_publish_enabled or not state.is_file():
            report["publisher_status"] = "awaiting_login"
            store.save(report)
            return report
        from playwright.async_api import Error, async_playwright

        submitted = False
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
                submitted = True
                await button.click()
                await page.get_by_text("发布成功", exact=False).first.wait_for(timeout=120000)
                report.update(
                    status="published", publisher_status="published", published_at=now(),
                    publisher_receipt_url=page.url,
                )
                await context.storage_state(path=str(state))
                await browser.close()
        except (Error, OSError, ValueError, RuntimeError) as exc:
            report.update(
                status="publish_unknown" if submitted else "approved",
                publisher_status="verify_manually" if submitted else "login_or_ui_required",
                publisher_error=type(exc).__name__,
            )
            # A submission with an unknown outcome must never be automatically retried.
        store.save(report)
        return report
