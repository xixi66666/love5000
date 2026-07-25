from __future__ import annotations

import json
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path


VIDEO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = VIDEO_ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from anime_tools.task_manager import TaskManager
from anime_tools.web_api import create_handler


def test_health_returns_unified_service_status(tmp_path):
    handler = create_handler(
        service=object(),
        task_manager=TaskManager(),
        static_root=tmp_path,
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{httpd.server_port}/api/health",
            timeout=2,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)

    assert payload["success"] is True
    assert payload["service"] == "video"
