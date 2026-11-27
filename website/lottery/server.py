#!/usr/bin/env python
"""开奖数据操作台 · love5000 本地服务。

托管 `output/` 下的数据操作台页面，并提供「刷新数据」所需的接口：
    GET  /api/health    健康检查（love5000 首页 Dock 使用，返回 success=true）
    GET  /api/status    当前数据截止期次
    GET  /api/recent    最近若干期开奖及形态（和值/跨度/奇偶/三区/连号/AC/重号）
    GET  /api/selection 生成候选号码，附带每注形态与最近 20 期数据
    POST /api/update    增量抓取官方开奖并重建操作台，日志实时流回页面

只监听 127.0.0.1，默认端口 5179；由 love5000 首页「开奖数据操作台」卡片点击启动。

命令行参数与默认值：
    --port     监听端口，默认取环境变量 `LOTTERY_PORT`，再退回 5179；
               端口被占用时自动向上探测最多 12 个候选端口。
    --open     启动后用浏览器打开首页，默认关闭。
    --verbose  打印每个请求的访问日志，默认只打印 4xx/5xx。

副作用：首次启动、产物缺失或页面模板更新时，会以子进程执行
`main.py --console-only --port <port>` 重建 `output/console.html`；
`POST /api/update` 会以子进程执行 `scripts/update_daily.py --build-target console
--console-port 5179`，由该脚本负责校验、备份到 `data/backup/<时间戳>/` 与写回，
本模块自身不写开奖 CSV。

约束：`POST /api/update` 要求 `X-Console: 1` 请求头（防跨站表单误触发），页面用同源
fetch 带上；跨域只放行 `file://`（Origin 为 `null`）与同端口 localhost/127.0.0.1。
更新脚本失败时返回非零码且既有数据不变。选号接口只给号码与形态，不构成任何中奖保证。

退出码：正常停服（Ctrl+C）返回 0；构建操作台失败或候选端口全部被占用时以 1 退出。
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

# 单进程内的全局更新锁：UPDATE 与选号共用，避免读到写了一半的 CSV。
UPDATE_LOCK = threading.Lock()

try:  # Windows 控制台默认 GBK，统一成 UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass


def data_status() -> dict:
    """读取本地数据的最新期次（只读 issue/date 两列）。

    Returns:
        `{"ssq": {...}, "dlt": {...}, "built_at": ...}`。每个彩种含中文名、期数、
        最新期号与日期；读取失败时该彩种只带 `error` 字段而不是抛异常——
        健康检查不该因为某个 CSV 缺失就整体报错。

    `built_at` 取 `output/console.html` 的修改时间，用于提示页面产物是否比数据旧。
    """
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
    """首次启动、产物缺失或页面模板更新时构建操作台。

    复用判断有三个条件：产物存在、不比模板旧、且已包含 `/selection` 入口。
    第三个条件是兼容旧产物——早期模板没有选号页，只比修改时间会漏掉这类过期产物。

    Args:
        port: 写进操作台刷新按钮的服务端口。

    Raises:
        SystemExit: 构建子进程返回非零码。错误信息附带 stderr（为空时取 stdout）
            末尾 1500 字符，便于直接看到 Python 侧的真实异常。
    """
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
    """从首选端口开始向上探测一个当时可绑定的端口。

    Args:
        preferred: 首选端口。
        tries: 连续探测的端口个数，默认 12。

    Returns:
        第一个能绑定 `127.0.0.1` 的端口号。

    Raises:
        SystemExit: 连续 `tries` 个端口都被占用。这里必须报错而不是退到随机端口：
            首页入口与健康检查都写死 5179，随机端口会让页面再也找不到服务。

    探测时设置 `SO_REUSEADDR` 并立即关闭套接字，所以返回的端口只是「刚才空闲」，
    真正的绑定仍在 `main` 中完成，极小概率会被其他进程抢先占用。
    """
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
    """操作台页面与 JSON 接口的请求处理器。

    继承 `SimpleHTTPRequestHandler` 只为复用 `output/` 的静态文件服务与 MIME 表，
    接口分支全部手写在 `do_GET` / `do_POST` 里，不引入额外框架。

    `port` 是类属性，由 `main` 在启动时改成实际监听端口，`_cors` 用它校验同源来源；
    因此同一个类不能在两个端口上同时使用。
    """

    port = DEFAULT_PORT
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(OUTPUT), **kwargs)

    def log_message(self, fmt, *args):  # 安静一点，只打印错误
        """只把 4xx/5xx 写到 stderr，避免页面轮询时刷屏。

        `--verbose` 启动时会被替换回父类实现以打印全部访问日志。
        """
        if args and str(args[1]).startswith(("4", "5")):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _cors(self) -> None:
        """为同源页面与 `file://` 打开的页面补上 CORS 响应头。

        `file://` 页面的 Origin 是字符串 `null`，无法与端口比较，只能单独放行；
        其余只接受本端口的 localhost/127.0.0.1。不匹配时不写任何头，由浏览器自行拦截，
        这样接口仍然只对本机页面可用。
        """
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
        """响应跨域预检：只回 204 与 CORS 头，不带内容。"""
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        """路由静态页面与只读接口。

        参数校验统一按「白名单 + 每个键只出现一次」处理：多传或重复参数直接返回 400，
        而不是悄悄取第一个，避免前端拼错参数时拿到看似正常的结果。

        选号接口与更新接口共用 `UPDATE_LOCK`：更新期间选号返回 409，因为生成过程要读
        同一批 CSV，读到写了一半的数据会给出错误形态。
        """
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/selection", "/selection.html"):
            # 选号页在源码目录而非 output/，因此单独读取并手写响应头。
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
            # 只允许 game 与 count；出现其他键说明调用方拼错参数，直接拒绝。
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
            # 三个参数都必须存在且各出现一次，避免 count 重复时出现歧义。
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
            # 首页即操作台；其余路径交给父类按 output/ 目录解析静态文件。
            self.path = "/console.html"
        super().do_GET()

    def do_POST(self):  # noqa: N802
        """只处理 `POST /api/update`。

        除 `X-Console: 1` 外还要求取到非阻塞锁：同一时刻只允许一个更新进程，否则两个
        子进程会同时写同一批 CSV。锁被占用返回 429 而不是排队，让页面立刻给出
        「正在更新」的提示。
        """
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
        """按 UTF-8 输出 JSON 响应。

        Args:
            payload: 可 JSON 序列化的响应体。
            status: HTTP 状态码，默认 200。

        `ensure_ascii=False` 让中文错误提示在浏览器里直接可读；`Cache-Control: no-store`
        是因为所有响应都带实时数据状态，被缓存会误导用户看到过期期次。
        """
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _stream_update(self) -> None:
        """以纯文本流式返回一次增量更新，结尾追加一行 `__DONE__` JSON。

        先发响应头再启动子进程，页面因此能边跑边显示日志；输出按行透传，客户端提前
        断开（BrokenPipe/ConnectionReset）时只停止写入、仍让子进程跑完——半途杀掉
        可能留下写了一半的数据。

        结束时比较更新前后的期号，把 `code`、`changed` 与最新状态写进 `__DONE__` 行，
        客户端不必再单独请求 `/api/status`。子进程以非零码退出时同样返回该行，
        由 `code` 区分成败；既有数据由 `update_daily.py` 保证未被破坏。
        """
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
    """解析参数、构建操作台并启动只监听回环地址的服务器。

    Returns:
        进程退出码：正常停止返回 0。

    Raises:
        SystemExit: 候选端口全被占用（见 `pick_port`）或操作台构建失败
            （见 `ensure_console`）时以 1 退出，首页卡片据此显示启动失败。
    """
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
