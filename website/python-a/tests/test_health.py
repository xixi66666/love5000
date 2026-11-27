"""统一健康检查接口 ``GET /api/health`` 的进程内集成测试。

被测对象：``server.AShareHandler`` 返回的健康响应。website 的 ServiceHealthChecker 依赖
顶层布尔值 ``success`` 与稳定的 ``service`` 标识判断能否复用进程，所以两者都必须断言。

隔离：把 ``AShareHandler`` 挂在 ``127.0.0.1:0``（由系统分配空闲端口）的后台线程上，
不占用固定端口、不访问外网、不写文件；用例结束通过 shutdown/server_close/join 收尾，
即使断言失败也不会留下监听线程。
"""
import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

import server


class HealthEndpointTests(unittest.TestCase):
    """只断言健康协议本身：HTTP 200、顶层 success 为真、service 标识为 python-a。"""
    def test_health_returns_unified_service_status(self):
        # 端口传 0 让系统分配空闲端口，避免与本地已启动的 5174 冲突。
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.AShareHandler)
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

        self.assertTrue(payload["success"])
        self.assertEqual("python-a", payload["service"])


if __name__ == "__main__":
    unittest.main()
