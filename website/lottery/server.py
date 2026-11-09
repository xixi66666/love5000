#!/usr/bin/env python
"""开奖数据操作台 · love5000 本地服务。

托管 `output/` 下的数据操作台页面，并提供「刷新数据」所需的接口：
    GET  /api/health    健康检查（love5000 首页 Dock 使用，返回 success=true）
    GET  /api/status    当前数据截止期次
    GET  /api/recent    最近若干期开奖及形态（和值/跨度/奇偶/三区/连号/AC/重号）
    GET  /api/selection 生成候选号码，附带每注形态与最近 20 期数据
    POST /api/update    增量抓取官方开奖并重建操作台，日志实时流回页面

只监听 127.0.0.1，默认端口 5179；由 love5000 首页「开奖数据操作台」卡片点击启动。
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

from selection import METHODS, GAMES, generate
from selection_stats import recent_draws

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
UPDATE_SCRIPT = ROOT / "scripts" / "update_daily.py"
MAIN_SCRIPT = ROOT / "main.py"
DEFAULT_PORT = 5179
SERVICE_NAME = "lottery"

UPDATE_LOCK = threading.Lock()

try:  # Windows 控制台默认 GBK，统一成 UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass


def data_status() -> dict:
    """读取本地数据的最新期次（只读 issue/date 两列）。"""
    out: dict = {}
    for key, name in (("ssq", "双色球"), ("dlt", "大乐透")):
        path = ROOT / "data" / f"{key}.csv"
        try:
            frame = pd.read_csv(path, encoding="utf-8-sig", usecols=["issue", "date"])
            out[key] = {
                "name": name,
                "count": int(len(frame)),
                "issue": int(frame["issue"].max()),
                "date": str(frame["date"].max()),
            }
        except Exception as exc:  # 数据缺失时不要让接口挂掉
            out[key] = {"name": name, "error": str(exc)}
    console = OUTPUT / "console.html"
    out["built_at"] = (
        datetime.fromtimestamp(console.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        if console.exists() else None
    )
    return out


def ensure_console(port: int) -> None:
    """首次启动、产物缺失或页面模板更新时构建操作台。"""
    console = OUTPUT / "console.html"
    template = ROOT / "src" / "lottery" / "console_template.html"
    if (console.exists() and console.stat().st_mtime >= template.stat().st_mtime
            and b'href="/selection"' in console.read_bytes()):
        return
    OUTPUT.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(MAIN_SCRIPT), "--console-only", "--port", str(port)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise SystemExit("操作台构建失败：\n" + (result.stderr or result.stdout)[-1500:])


def pick_port(preferred: int, tries: int = 12) -> int:
    for port in range(preferred, preferred + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise SystemExit(f"端口 {preferred}–{preferred + tries - 1} 都被占用，请用 --port 指定其他端口")


class Handler(SimpleHTTPRequestHandler):
    port = DEFAULT_PORT
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(OUTPUT), **kwargs)

    def log_message(self, fmt, *args):  # 安静一点，只打印错误
        if args and str(args[1]).startswith(("4", "5")):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _cors(self) -> None:
        origin = self.headers.get("Origin")
        allowed = ""
        if origin == "null":
            allowed = "null"
        elif origin and (origin.startswith(f"http://127.0.0.1:{self.port}")
                         or origin.startswith(f"http://localhost:{self.port}")):
            allowed = origin
        if allowed:
            self.send_header("Access-Control-Allow-Origin", allowed)
            self.send_header("Access-Control-Allow-Headers", "X-Console, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/selection", "/selection.html"):
            try:
                body = (ROOT / "src" / "lottery" / "selection.html").read_bytes()
            except OSError:
                self.send_error(404, "selection page unavailable")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/recent":
            params = parse_qs(parsed.query, keep_blank_values=True)
            if "game" not in params or len(params["game"]) != 1 or set(params) - {"game", "count"}:
                self._json({"success": False, "message": "请提供有效的彩种"}, 400)
                return
            try:
                count = int(params.get("count", ["20"])[0])
                if params["game"][0] not in GAMES or not 1 <= count <= 50:
                    raise ValueError("请求参数无效")
            except ValueError:
                self._json({"success": False, "message": "彩种或期数不合法"}, 400)
                return
            try:
                rows = recent_draws(params["game"][0], count)
            except (OSError, KeyError, IndexError, ValueError) as exc:
                sys.stderr.write(f"最近开奖读取失败: {exc}\n")
                self._json({"success": False, "message": "开奖数据读取失败，请检查本地数据"}, 500)
                return
            self._json({"success": True, "game": params["game"][0], "count": count, "draws": rows})
            return
        if path == "/api/selection":
            params = parse_qs(parsed.query, keep_blank_values=True)
            if set(params) != {"game", "method", "count"} or any(len(v) != 1 for v in params.values()):
                self._json({"success": False, "message": "请提供有效的彩种、选号方法和注数"}, 400)
                return
            try:
                count = int(params["count"][0])
                if params["game"][0] not in GAMES or params["method"][0] not in METHODS or not 1 <= count <= 10:
                    raise ValueError("请求参数无效")
            except ValueError:
                self._json({"success": False, "message": "彩种、选号方法或注数不合法"}, 400)
                return
            if not UPDATE_LOCK.acquire(blocking=False):
                self._json({"success": False, "message": "数据正在更新，请稍后再试"}, 409)
                return
            try:
                try:
                    result = generate(params["game"][0], params["method"][0], count)
                except (OSError, KeyError, IndexError, ValueError) as exc:
                    sys.stderr.write(f"选号数据读取失败: {exc}\n")
                    self._json({"success": False, "message": "开奖数据读取失败，请检查本地数据"}, 500)
                    return
                try:
                    result["recent"] = recent_draws(params["game"][0], 20)
                except (OSError, KeyError, IndexError, ValueError) as exc:
                    sys.stderr.write(f"最近开奖读取失败: {exc}\n")
                    result["recent"] = []
            finally:
                UPDATE_LOCK.release()
            self._json(result)
            return
        if path == "/api/health":
            self._json({"success": True, "service": SERVICE_NAME, "status": "ok",
                        "data": data_status(), "updated": datetime.now().isoformat(timespec="seconds")})
            return
        if path == "/api/status":
            self._json(data_status())
            return
        if path in ("/", "/index.html"):
            self.path = "/console.html"
        super().do_GET()

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        if path != "/api/update":
            self.send_error(404, "unknown api")
            return
        if self.headers.get("X-Console") != "1":
            self.send_error(403, "missing X-Console header")
            return
        if not UPDATE_LOCK.acquire(blocking=False):
            self.send_error(429, "update already running")
            return
        try:
            self._stream_update()
        finally:
            UPDATE_LOCK.release()

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _stream_update(self) -> None:
        before = data_status()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self._cors()
        self.end_headers()

        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        proc = subprocess.Popen(
            [sys.executable, "-X", "utf8", str(UPDATE_SCRIPT),
             "--build-target", "console", "--console-port", str(DEFAULT_PORT)],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        def emit(line: str) -> None:
            try:
                self.wfile.write(line.encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        assert proc.stdout is not None
        for line in proc.stdout:
            emit(line)
        code = proc.wait()

        after = data_status()
        changed = any(
            before.get(k, {}).get("issue") != after.get(k, {}).get("issue")
            for k in ("ssq", "dlt")
        )
        emit("\n__DONE__ " + json.dumps({"code": code, "changed": changed, "status": after},
                                        ensure_ascii=False) + "\n")
        self.close_connection = True


def main() -> int:
    parser = argparse.ArgumentParser(description="开奖数据操作台本地服务")
    parser.add_argument("--port", type=int, default=int(os.environ.get("LOTTERY_PORT", DEFAULT_PORT)))
    parser.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    parser.add_argument("--verbose", action="store_true", help="打印每个请求")
    args = parser.parse_args()

    port = pick_port(args.port)
    Handler.port = port
    if args.verbose:
        Handler.log_message = SimpleHTTPRequestHandler.log_message  # type: ignore[assignment]

    ensure_console(port)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    status = data_status()
    print("=" * 52)
    print("  开奖数据操作台 · love5000")
    print("=" * 52)
    print(f"  地址：{url}")
    for key in ("ssq", "dlt"):
        info = status.get(key, {})
        if "issue" in info:
            print(f"  {info['name']}：{info['count']:,} 期，最新 {info['issue']}（{info['date']}）")
    print("  按 Ctrl+C 停止服务")
    print("=" * 52)

    if args.open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
