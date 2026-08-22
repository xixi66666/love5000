import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

import server


class HealthEndpointTests(unittest.TestCase):
    def test_health_returns_unified_service_status(self):
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
