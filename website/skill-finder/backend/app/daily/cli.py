from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys

from app.core.config import settings
from app.daily import store
from app.daily.pipeline import generate, now


def notify(day: str) -> dict:
    with store.lock():
        report = store.load(day)
        if report.get("status") not in {"pending_review", "approved", "published"}:
            raise RuntimeError("Report is not ready for delivery")
        if report.get("qq_status") == "sent":
            return report
        if not settings.daily_qq_target or not settings.daily_openclaw_command:
            report["qq_status"] = "not_configured"
            store.save(report)
            return report
        url = settings.daily_public_url.rstrip("/") + "/daily-reports?date=" + day
        message = (
            f"{report['title']}已生成。\n中文配音、竖屏视频、项目链接：{url}\n"
            "请先预览，在审核页批准后才会提交抖音发布。"
        )
        subprocess.run([
            settings.daily_openclaw_command, "message", "send", "--channel", "qqbot",
            "--target", settings.daily_qq_target, "--message", message,
        ], check=True, capture_output=True, timeout=120)
        report.update(qq_status="sent", qq_sent_at=now())
        store.save(report)
        return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["generate", "collect", "notify", "publish", "login"])
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--date", default=now()[:10])
    args = parser.parse_args()
    if args.action == "login":
        from app.daily.douyin_login import login

        print(json.dumps(asyncio.run(login())))
        return
    if args.action == "collect":
        from app.core.scheduler import _scheduled_collection

        asyncio.run(_scheduled_collection())
        print(json.dumps({"status": "collection_finished"}))
        return
    if args.action == "generate":
        report = generate(collect=args.collect)
    elif args.action == "notify":
        report = notify(args.date)
    else:
        from app.daily.publisher import publish

        report = asyncio.run(publish(args.date))
    print(json.dumps({key: report.get(key) for key in ("date", "status", "qq_status")}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - sanitize the CLI failure boundary
        print(f"Daily task failed: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
