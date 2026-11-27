"""抖音发布适配层：只有绑定当前成片指纹的人工批准才会触达提交按钮。

`publish` 的顺序保证：先 `store.verify_approval`（状态为 `approved`、批准摘要与
当前视频/口播/文案一致、`video.mp4` 的 SHA-256 与记录一致），再检查发布开关与登录
态，最后才打开创作者后台；上传完成后还会再次校验批准摘要，防止预览与提交之间被
改动。

结果语义：点击「发布」前失败保持 `approved`；已点击但没有看到平台确认则写
`publish_unknown`，绝不自动重发。登录态文件由 `douyin_login` 维护，属于私有运行
数据，其内容不进入报告或日志。
"""
from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.daily import store
from app.daily.pipeline import now
from app.daily.progress import Tracker


async def publish(day: str) -> dict:
    """在人工批准后把当前成片提交到抖音创作者后台。

    顺序保证：先 `store.verify_approval` 校验批准摘要与视频 SHA-256，再检查发布
    开关与登录态，最后才打开创作者后台；上传完成后会再次校验批准摘要，只有仍与
    审核版本一致才点击「发布」。

    Returns:
        更新后的报告；`published` 只在平台明确显示成功后写入。

    Raises:
        ValueError: 没有绑定当前视频的批准，或上传期间批准被改动。
    """
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
                # 页面改版、登录风控或上传结果不确定时一律按失败关闭处理。
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
            # 已提交但结果未知的发布绝不能自动重试。
        store.save(report)
        return report
