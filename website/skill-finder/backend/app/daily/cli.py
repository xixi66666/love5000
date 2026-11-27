"""日报命令行入口，供 cron、容器和本机手工排查共用。

子命令与 API 走同一套实现：`generate` 生成当日日报（`--collect` 才真正采集）、
`notify` 发送 QQ 日报链接、`publish` 提交已批准成片、`login` 完成抖音扫码登录、
`sample` 用当前引擎制作样片、`collect` 只跑采集。

运行时读写 `settings.daily_reports_dir` 下的报告与产物；外部命令为 openclaw
（QQ 通知）、node / ffmpeg / ffprobe（经生成流程间接调用）。失败统一只打印异常
类型到 stderr 并以退出码 1 结束，避免把私有路径或上游响应带进日志。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys

from app.core.config import settings
from app.daily import store
from app.daily.pipeline import generate, now
from app.daily.progress import Tracker


def notify(day: str) -> dict:
    """把已就绪日报的预览链接通过已配置的 QQ 接入口发送一次。

    先确认报告已进入 `pending_review` 及之后的状态，避免把草稿外发；`qq_status`
    已是 `sent` 时直接返回，不重复打扰。未配置目标或 openclaw 命令时记为
    `not_configured` 并正常返回，不影响视频流程。

    Args:
        day: `YYYY-MM-DD`，用于定位任务目录与预览链接。

    Returns:
        更新后的报告字典。

    Raises:
        RuntimeError: 报告还没进入可投递状态。
        OSError / subprocess.SubprocessError: 发送失败，进度步骤记为 `failed`
            后原样抛出。
    """
    with store.lock():
        report = store.load(day)
        if report.get("status") not in {"pending_review", "approved", "published"}:
            raise RuntimeError("Report is not ready for delivery")
        if report.get("qq_status") == "sent":
            return report
        if not settings.daily_qq_target or not settings.daily_openclaw_command:
            report["qq_status"] = "not_configured"
            store.save(report)
            Tracker(day).set("notify", "skipped", "QQ 接入口暂未配置。")
            return report
        url = settings.daily_public_url.rstrip("/") + "/daily-reports?date=" + day
        message = (
            f"{report['title']}已生成。\n中文配音、竖屏视频、项目链接：{url}\n"
            "请先预览，在审核页批准后才会提交抖音发布。"
        )
        progress = Tracker(day)
        progress.begin("notify", "正在通过已配置的 QQ 接入口发送日报链接。")
        try:
            subprocess.run([
                settings.daily_openclaw_command, "message", "send", "--channel", "qqbot",
                "--target", settings.daily_qq_target, "--message", message,
            ], check=True, capture_output=True, timeout=120)
        except (OSError, subprocess.SubprocessError):
            progress.set("notify", "failed", "通知发送失败，请检查 QQ 接入口配置后重试。")
            raise
        report.update(qq_status="sent", qq_sent_at=now())
        store.save(report)
        progress.finish("notify", "QQ 日报链接已送达。")
        return report


def main() -> None:
    """CLI 分发入口：generate / collect / notify / publish / login / sample。

    重依赖（Playwright、Whisper、渲染器）都在分支内延迟导入，保证 `--help` 和
    `collect` 不会拉起浏览器进程。`generate` 默认复用数据库里当天的榜单，
    只有显式 `--collect` 才真正采集。
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["generate", "collect", "notify", "publish", "login", "sample"])
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--date", default=now()[:10])
    args = parser.parse_args()
    if args.action == "sample":
        from app.daily.sample import generate_sample

        print(json.dumps(generate_sample(), ensure_ascii=False))
        return
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
