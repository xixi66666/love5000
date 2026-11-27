"""日报操作台的进度留痕、素材上传与派发护栏。

被测对象是 `app.daily.console.snapshot`、`app.daily.progress` 的 Tracker/tracking，
以及 `/api/v1/daily-reports` 的 console、generate、素材与样片接口。本模块锁定：

- 失败步骤必须落盘为 `failed` 并把计数停在中断处，写入文件的异常信息要脱敏——
  私有密钥与上游响应体不能出现在 `workflow.json` 或接口响应里；
- 历史任务没有 `workflow.json` 时只把前 7 步标 `untracked`，绝不补造进度；
  “审核”一步的状态取自日报状态，与进度记录无关；
- 进程中断后遗留的 `generating` 必须先判定为 `interrupted` 才能重跑；
- 素材上传的判定顺序是管理鉴权 → 真实图片 → 体积上限，坏文件和超限请求不得破坏
  已经校验通过的素材；
- 派发要挡住重复点击（`.dispatch.lock`）和覆盖已审核的版本；样片入口只暴露成片，
  不能带出 `render-manifest.json` 这类工作文件。

隔离方式：`workspace` fixture 把日报/素材目录指到 `tmp_path`、注入测试用
`admin_key`、清空 QQ 目标并落一份假日报；`TestClient` 用 `http://localhost` 作为
`base_url` 以通过“仅 HTTPS 或本机来源”的管理接口限制。全程不连数据库，不跑
ffmpeg/node 渲染，也不发送任何通知。
"""

import io
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock
from PIL import Image

from app.core.config import settings
from app.daily import store
from app.daily.console import snapshot
from app.daily.progress import Tracker, current, now, tracking
from app.main import app


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """把日报目录、素材目录与管理密钥都固定到测试环境。

    三个 `daily_*` 路径改成 `tmp_path` 下的子目录，避免读写 `backend/data/` 的真实
    运行数据；`admin_key` 换成 `console-test-only`，供管理写接口直接带 header 调用；
    清空 `daily_qq_target` 让通知步骤稳定停在 `skipped`。返回的假日报会写进日报
    目录，供 `/console` 读取成真实输入。
    """
    monkeypatch.setattr(settings, "daily_reports_dir", str(tmp_path / "reports"))
    monkeypatch.setattr(settings, "daily_assets_dir", str(tmp_path / "assets"))
    monkeypatch.setattr(settings, "admin_key", type(settings.admin_key)("console-test-only"))
    monkeypatch.setattr(settings, "daily_qq_target", "")
    report = {"date": now()[:10], "status": "failed", "items": [
        {"full_name": "org/demo", "rank": 1, "summary": "实际用途。", "url": "https://github.com/org/demo", "daily_stars": 5},
    ]}
    store.save(report)
    return report


def client():
    """管理接口只放行 HTTPS 或本机来源，这里用 localhost 作为 base_url 通过校验。"""
    return TestClient(app, base_url="http://localhost")


def test_failed_stage_is_durable_and_sanitized(workspace):
    with pytest.raises(RuntimeError), tracking(workspace["date"]) as progress:
        progress.finish("collection", "采集结束。")
        progress.begin("voice", "正在配音。", total=3)
        progress.tick("voice", "第一段完成。")
        raise RuntimeError("private-key-and-upstream-body")
    saved = Tracker(workspace["date"]).data
    voice = next(stage for stage in saved["stages"] if stage["id"] == "voice")
    assert voice["status"] == "failed"
    assert voice["done"] == 1 and voice["total"] == 3
    assert "private-key" not in json.dumps(saved)
    assert current() is None


def test_legacy_history_has_no_invented_progress(workspace):
    """前 7 步只标 `untracked`；第 8 步“审核”由日报状态推导，因此仍是 `waiting`。"""
    workspace["status"] = "pending_review"
    store.save(workspace)
    value = snapshot(workspace["date"])
    assert value["recorded"] is False
    assert all(stage["status"] == "untracked" for stage in value["workflow"]["stages"][:7])
    assert value["workflow"]["stages"][7]["status"] == "waiting"


def test_stopped_generation_is_recoverable(workspace):
    from datetime import datetime

    workspace["status"] = "generating"
    store.save(workspace)
    progress = Tracker(workspace["date"])
    progress.begin("render", "正在渲染。")
    # 判定 stale 的阈值是 30 秒，把 updated_at 退到 2 分钟前才能命中 interrupted 分支。
    progress.data["updated_at"] = (datetime.fromisoformat(now()) - timedelta(minutes=2)).isoformat()
    (store.report_dir(workspace["date"]) / "workflow.json").write_text(json.dumps(progress.data))
    assert snapshot(workspace["date"])["status"] == "interrupted"


def test_console_only_returns_safe_environment_metadata(workspace, monkeypatch):
    from types import SimpleNamespace

    from app.services import model_settings

    monkeypatch.setattr(model_settings, "mimo",
                        lambda: SimpleNamespace(api_key="private-tts-value", base_url="https://example.invalid/v1"))
    monkeypatch.setattr(settings, "daily_whisper_model", "C:/private/models/small")
    response = client().get("/api/v1/daily-reports/console", params={"day": workspace["date"]})
    assert response.status_code == 200
    assert "private-tts-value" not in response.text
    assert "C:/private" not in response.text
    assert response.json()["assets"][0]["status"] == "missing"


def test_generation_rejects_duplicate_dispatch(workspace):
    with FileLock(str(store.root() / ".dispatch.lock"), timeout=0):
        response = client().post("/api/v1/daily-reports/generate", headers={"X-Admin-Key": "console-test-only"})
    assert response.status_code == 409


def test_generation_cannot_overwrite_reviewed_report(workspace, monkeypatch):
    workspace["status"] = "pending_review"
    store.save(workspace)
    task = AsyncMock()
    monkeypatch.setattr("app.api.v1.daily_reports.task", task)
    response = client().post("/api/v1/daily-reports/generate", headers={"X-Admin-Key": "console-test-only"})
    assert response.status_code == 409
    task.assert_not_called()


def test_upload_checks_authentication_and_actual_image(workspace):
    url = f"/api/v1/daily-reports/{workspace['date']}/assets/org/demo"
    params = {"filename": "demo.png", "source": "https://github.com/org/demo"}
    assert client().put(url, params=params, content=b"invalid").status_code == 401
    headers = {"X-Admin-Key": "console-test-only", "Content-Type": "application/octet-stream"}
    assert client().put(url, params=params, headers=headers, content=b"invalid").status_code == 422
    image = io.BytesIO()
    Image.new("RGB", (20, 20)).save(image, format="PNG")
    assert client().put(url, params=params, headers=headers, content=image.getvalue()).status_code == 200
    assert snapshot(workspace["date"])["assets"][0]["status"] == "ready"
    root = settings.daily_assets_dir
    manifest = json.loads((Path(root) / "org--demo.json").read_text())
    assert manifest["file"].endswith(".png")
    # 后续坏文件不能破坏已经校验过的素材。
    assert client().put(url, params=params, headers=headers, content=b"bad").status_code == 422
    assert snapshot(workspace["date"])["assets"][0]["status"] == "ready"


def test_upload_rejects_oversize_without_changing_assets(workspace, monkeypatch):
    """体积上限在写盘前生效：超限直接 413，且素材目录里不会留下任何文件。"""
    monkeypatch.setattr("app.daily.assets.MAX_ASSET_BYTES", 3)
    response = client().put(
        f"/api/v1/daily-reports/{workspace['date']}/assets/org/demo",
        params={"filename": "demo.png", "source": "https://github.com/org/demo"},
        headers={"X-Admin-Key": "console-test-only"}, content=b"1234",
    )
    assert response.status_code == 413
    assert not list(Path(settings.daily_assets_dir).glob("*"))


def test_sample_downloads_never_expose_work_files(workspace, tmp_path):
    directory = tmp_path / "video-samples" / "20261019-150000"
    directory.mkdir(parents=True)
    (directory / "video.mp4").write_bytes(b"sample")
    (directory / "render-manifest.json").write_text('{"private":"work"}')
    assert client().get("/api/v1/daily-reports/samples/20261019-150000/files/video.mp4").status_code == 200
    assert client().get("/api/v1/daily-reports/samples/20261019-150000/files/render-manifest.json").status_code == 404
