import io
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit

TOOL_DIR = Path(__file__).resolve().parents[1]
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import service_doctor as sd  # noqa: E402


BODY_MARKER = "REPORT_BODY_SECRET_MARKER_9c1"


class _FixtureHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        return

    def log_error(self, format, *args):
        return

    def _write_body(self, status_code, body):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass

    def _write_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._write_body(status_code, body)

    def do_GET(self):
        server = self.server
        server.note_hit(self.path)
        with server.lock:
            server.active += 1
            server.max_active = max(server.max_active, server.active)
        try:
            parsed = urlsplit(self.path)
            path = parsed.path
            if path == "/ok":
                self._write_json(
                    200, {"success": True, "service": "alpha"}
                )
            elif path == "/aggregate":
                self._write_json(
                    200, {"success": True, "healthy": True, "services": []}
                )
            elif path == "/aggregate-offline":
                self._write_json(200, {"success": True, "healthy": False, "services": []})
            elif path == "/aggregate-incomplete":
                self._write_json(200, {"success": True, "healthy": True})
            elif path == "/aggregate-false":
                self._write_json(200, {"success": False})
            elif path == "/string-success":
                self._write_json(
                    200, {"success": "true", "service": "alpha"}
                )
            elif path == "/false-success":
                self._write_json(
                    200, {"success": False, "service": "alpha"}
                )
            elif path == "/missing-success":
                self._write_json(200, {"service": "alpha"})
            elif path == "/service-number":
                self._write_json(200, {"success": True, "service": 123})
            elif path == "/missing-service":
                self._write_json(200, {"success": True})
            elif path == "/mismatch":
                self._write_json(
                    200, {"success": True, "service": "beta"}
                )
            elif path == "/malformed":
                self._write_body(200, b'{"success": true')
            elif path == "/not-object":
                self._write_body(200, b"[]")
            elif path == "/empty":
                self._write_body(200, b"")
            elif path == "/oversize":
                body = (
                    b'{"success":true,"service":"alpha","pad":"'
                    + b"x" * (sd.MAX_RESPONSE_BYTES + 10)
                    + b'"}'
                )
                self._write_body(200, body)
            elif path == "/http-500":
                self._write_json(
                    500, {"success": True, "service": "alpha"}
                )
            elif path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/ok")
                self.send_header("Content-Length", "0")
                self.send_header("Connection", "close")
                self.end_headers()
            elif path == "/secret":
                self._write_json(
                    200,
                    {
                        "success": True,
                        "service": "alpha",
                        "secret": BODY_MARKER,
                    },
                )
            elif path == "/slow":
                time.sleep(0.45)
                self._write_json(
                    200, {"success": True, "service": "alpha"}
                )
            elif path == "/parallel":
                query = parse_qs(parsed.query)
                try:
                    delay = float(query.get("delay", ["0"])[0])
                except ValueError:
                    delay = 0.0
                time.sleep(max(0.0, delay))
                self._write_json(
                    200, {"success": True, "service": "alpha"}
                )
            else:
                self._write_json(
                    404, {"success": False, "service": "fixture"}
                )
        finally:
            with server.lock:
                server.active -= 1


class _FixtureServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler):
        super().__init__(address, handler)
        self.lock = threading.Lock()
        self.hits = []
        self.active = 0
        self.max_active = 0

    def note_hit(self, path):
        with self.lock:
            self.hits.append(path)

    def reset_stats(self):
        with self.lock:
            self.hits = []
            self.active = 0
            self.max_active = 0

    def handle_error(self, request, client_address):
        return


class _LoopbackServerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = _FixtureServer(("127.0.0.1", 0), _FixtureHandler)
        cls.port = cls.server.server_address[1]
        cls.server_thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=3)

    def setUp(self):
        self.server.reset_stats()
        self.tmpdir = tempfile.TemporaryDirectory(
            dir=str(TOOL_DIR), prefix=".test-tmp-"
        )
        self.addCleanup(self.tmpdir.cleanup)
        self._manifest_counter = 0

    def _url(self, path):
        return "http://127.0.0.1:{}{}".format(self.port, path)

    def _write_manifest(self, services):
        self._manifest_counter += 1
        path = Path(self.tmpdir.name) / "manifest-{}.json".format(
            self._manifest_counter
        )
        path.write_text(
            json.dumps({"services": services}, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def _specs(self, entries):
        return sd.load_manifest(self._write_manifest(entries))

    def _spec(self, path, expected_service="alpha", kind="service", name="svc"):
        entry = {
            "name": name,
            "url": self._url(path),
            "kind": kind,
        }
        if kind == "service":
            entry["expected_service"] = expected_service
        return self._specs([entry])[0]

    def _run_main(self, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = sd.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()


class CheckStatusTests(_LoopbackServerTestCase):
    def test_standard_service_healthy(self):
        result = sd.check_service(self._spec("/ok"), timeout=1.0)
        self.assertEqual(sd.STATUS_HEALTHY, result.status)
        self.assertEqual(200, result.http_status)
        self.assertEqual("alpha", result.expected_service)
        self.assertIn("service 匹配", result.detail)

    def test_aggregate_distinguishes_offline_targets_from_invalid_payload(self):
        result = sd.check_service(
            self._spec("/aggregate", kind="aggregate"), timeout=1.0
        )
        self.assertEqual(sd.STATUS_HEALTHY, result.status)
        self.assertIn("聚合接口", result.detail)

        offline = self._spec("/aggregate-offline", kind="aggregate")
        self.assertEqual(sd.STATUS_DOWNSTREAM_UNHEALTHY, sd.check_service(offline).status)
        manifest = self._write_manifest([{"name": "website", "url": offline.url, "kind": "aggregate"}])
        code, stdout, _ = self._run_main("--manifest", str(manifest))
        self.assertEqual(1, code)
        self.assertIn("下游", stdout)

        for path in ("/aggregate-false", "/aggregate-incomplete"):
            with self.subTest(path=path):
                invalid = sd.check_service(self._spec(path, kind="aggregate"))
                self.assertEqual(sd.STATUS_FORMAT_ERROR, invalid.status)

    def test_literal_boolean_success_is_required(self):
        for path in ("/string-success", "/false-success", "/missing-success"):
            with self.subTest(path=path):
                result = sd.check_service(self._spec(path), timeout=1.0)
                self.assertEqual(sd.STATUS_FORMAT_ERROR, result.status)
                self.assertIn("success", result.detail)

    def test_service_identity_must_be_string_and_match(self):
        for path in ("/service-number", "/missing-service", "/mismatch"):
            with self.subTest(path=path):
                result = sd.check_service(self._spec(path), timeout=1.0)
                self.assertEqual(sd.STATUS_FORMAT_ERROR, result.status)
                self.assertIn("service", result.detail)

    def test_malformed_and_non_object_json_are_format_errors(self):
        for path in ("/malformed", "/not-object"):
            with self.subTest(path=path):
                result = sd.check_service(self._spec(path), timeout=1.0)
                self.assertEqual(sd.STATUS_FORMAT_ERROR, result.status)

    def test_empty_and_oversized_body_are_format_errors(self):
        for path in ("/empty", "/oversize"):
            with self.subTest(path=path):
                result = sd.check_service(self._spec(path), timeout=2.0)
                self.assertEqual(sd.STATUS_FORMAT_ERROR, result.status)

    def test_http_error_and_redirect_are_not_followed(self):
        result = sd.check_service(self._spec("/http-500"), timeout=1.0)
        self.assertEqual(sd.STATUS_HTTP_ERROR, result.status)
        self.assertEqual(500, result.http_status)

        self.server.reset_stats()
        result = sd.check_service(self._spec("/redirect"), timeout=1.0)
        self.assertEqual(sd.STATUS_HTTP_ERROR, result.status)
        self.assertEqual(302, result.http_status)
        self.assertIn("/redirect", self.server.hits)
        self.assertNotIn("/ok", self.server.hits)

    def test_connection_refused_is_distinct(self):
        class RefusingConnection:
            def __init__(self, *args, **kwargs):
                pass

            def request(self, *args, **kwargs):
                raise ConnectionRefusedError()

            def close(self):
                pass

        spec = self._specs(
            [
                {
                    "name": "closed",
                    "url": "http://127.0.0.1:9/api/health",
                    "kind": "service",
                    "expected_service": "closed",
                }
            ]
        )[0]
        with mock.patch.object(
            sd.http.client, "HTTPConnection", RefusingConnection
        ):
            result = sd.check_service(spec, timeout=0.5)
        self.assertEqual(sd.STATUS_CONNECTION_REFUSED, result.status)
        self.assertIn("连接被拒绝", result.detail)

    def test_timeout_is_distinct(self):
        result = sd.check_service(self._spec("/slow"), timeout=0.12)
        self.assertEqual(sd.STATUS_TIMEOUT, result.status)
        self.assertIn("0.12", result.detail)

    def test_other_connection_error_is_distinct(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(3)
        port = listener.getsockname()[1]

        def serve_bad_http():
            try:
                conn, _ = listener.accept()
                with conn:
                    conn.recv(1024)
                    conn.sendall(b"NOT HTTP\r\n\r\n")
                    time.sleep(0.05)
            except OSError:
                pass
            finally:
                listener.close()

        thread = threading.Thread(target=serve_bad_http, daemon=True)
        thread.start()
        self.addCleanup(listener.close)
        url = "http://127.0.0.1:{}/".format(port)
        spec = self._specs(
            [
                {
                    "name": "bad-http",
                    "url": url,
                    "kind": "service",
                    "expected_service": "bad-http",
                }
            ]
        )[0]
        result = sd.check_service(spec, timeout=1.0)
        self.assertEqual(sd.STATUS_CONNECTION_ERROR, result.status)
        thread.join(timeout=3)

    def test_proxy_environment_variables_are_ignored(self):
        proxy_env = {
            "HTTP_PROXY": "http://127.0.0.1:1",
            "HTTPS_PROXY": "http://127.0.0.1:1",
            "ALL_PROXY": "http://127.0.0.1:1",
            "http_proxy": "http://127.0.0.1:1",
            "https_proxy": "http://127.0.0.1:1",
            "all_proxy": "http://127.0.0.1:1",
        }
        with mock.patch.dict(os.environ, proxy_env, clear=False):
            result = sd.check_service(self._spec("/ok"), timeout=1.0)
        self.assertEqual(sd.STATUS_HEALTHY, result.status)

    def test_bounded_parallel_preserves_input_order(self):
        entries = []
        for name, delay in (
            ("one", 0.30),
            ("two", 0.15),
            ("three", 0.15),
            ("four", 0.0),
        ):
            entries.append(
                {
                    "name": name,
                    "url": self._url("/parallel?delay={}".format(delay)),
                    "kind": "service",
                    "expected_service": "alpha",
                }
            )
        specs = self._specs(entries)
        results = sd.run_checks(specs, timeout=2.0, jobs=2)
        self.assertEqual(["one", "two", "three", "four"], [r.name for r in results])
        self.assertTrue(all(result.ok for result in results))
        self.assertLessEqual(self.server.max_active, 2)
        self.assertGreaterEqual(self.server.max_active, 2)


class ReportTests(_LoopbackServerTestCase):
    def test_html_escapes_every_interpolation(self):
        result = sd.CheckResult(
            name="<script>{0}</script>",
            url=self._url("/?q=<img src=x onerror=alert(1)>"),
            kind=sd.KIND_SERVICE,
            expected_service="alpha<&>",
            status=sd.STATUS_FORMAT_ERROR,
            http_status=200,
            elapsed_ms=12,
            detail="<b>bad</b>",
        )
        document = sd.render_html_report(
            [result],
            generated_at="<time>",
            timeout=0.5,
            jobs=2,
        )
        self.assertIn("&lt;script&gt;{0}&lt;/script&gt;", document)
        self.assertNotIn("<script>", document.lower())
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", document)
        self.assertNotIn("<img src=x", document)
        self.assertIn("alpha&lt;&amp;&gt;", document)
        self.assertIn("&lt;b&gt;bad&lt;/b&gt;", document)
        self.assertIn("&lt;time&gt;", document)
        self.assertNotIn("<time>", document)
        self.assertIn('lang="zh-CN"', document)
        self.assertIn("<style>", document)
        self.assertNotIn("<link", document.lower())
        self.assertNotIn("<img", document.lower())

    def test_html_never_contains_response_body(self):
        result = sd.check_service(self._spec("/secret"), timeout=1.0)
        self.assertEqual(sd.STATUS_HEALTHY, result.status)
        document = sd.render_html_report([result])
        self.assertNotIn(BODY_MARKER, document)
        self.assertIn("本地服务诊断报告", document)
        self.assertIn("service 匹配", document)

    def test_html_contains_all_status_labels(self):
        results = []
        for index, status in enumerate(sd.STATUS_ORDER):
            results.append(
                sd.CheckResult(
                    name="svc-{}".format(index),
                    url=self._url("/ok"),
                    kind=sd.KIND_SERVICE,
                    expected_service="svc",
                    status=status,
                    http_status=None if index == 0 else 500,
                    elapsed_ms=index,
                    detail="detail-{}".format(index),
                )
            )
        document = sd.render_html_report(results)
        for label in sd.STATUS_LABELS.values():
            self.assertIn(label, document)


class ManifestValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(
            dir=str(TOOL_DIR), prefix=".test-tmp-"
        )
        self.addCleanup(self.tmpdir.cleanup)
        self._counter = 0

    def _write(self, document):
        self._counter += 1
        path = Path(self.tmpdir.name) / "manifest-{}.json".format(
            self._counter
        )
        if isinstance(document, str):
            path.write_text(document, encoding="utf-8")
        else:
            path.write_text(
                json.dumps(document, ensure_ascii=False), encoding="utf-8"
            )
        return path

    def _load_entries(self, entries):
        return sd.load_manifest(self._write({"services": entries}))

    def test_bundled_manifest_has_expected_loopback_services(self):
        specs = sd.load_manifest(sd.DEFAULT_MANIFEST)
        self.assertEqual(
            [
                "website",
                "lovestory",
                "imagetemplate",
                "python-a",
                "quant-a",
                "scrapling-ui",
                "skill-finder",
                "personal-agent",
                "lottery",
            ],
            [spec.name for spec in specs],
        )
        self.assertEqual("aggregate", specs[0].kind)
        self.assertIsNone(specs[0].expected_service)
        self.assertEqual("/api/services/health", urlsplit(specs[0].url).path)
        for spec in specs[1:]:
            self.assertEqual("service", spec.kind)
            self.assertEqual(spec.name, spec.expected_service)
            self.assertEqual("/api/health", urlsplit(spec.url).path)
            self.assertTrue(spec.url.startswith("http://127.0.0.1:"))

    def test_custom_manifest_accepts_loopback_ipv4_and_ipv6(self):
        specs = self._load_entries(
            [
                {
                    "name": "ipv4",
                    "url": "http://127.0.0.1:9001/api/health",
                    "kind": "service",
                    "expected_service": "ipv4",
                },
                {
                    "name": "ipv6",
                    "url": "https://[::1]:9002/api/health",
                    "kind": "aggregate",
                },
            ]
        )
        self.assertEqual(["ipv4", "ipv6"], [s.name for s in specs])
        self.assertEqual(9001, specs[0].port)
        self.assertEqual("https", specs[1].scheme)
        self.assertEqual(9002, specs[1].port)
        self.assertEqual("::1", specs[1].host)

    def test_non_loopback_and_unsafe_urls_are_rejected(self):
        bad_urls = [
            "http://localhost:8080/api/health",
            "http://example.com:8080/api/health",
            "http://192.168.1.2:8080/api/health",
            "http://8.8.8.8:8080/api/health",
            "http://0.0.0.0:8080/api/health",
            "http://127.0.0.1.evil.test:8080/api/health",
            "ftp://127.0.0.1:8080/api/health",
            "127.0.0.1:8080/api/health",
            "http://user:pass@127.0.0.1:8080/api/health",
            "http://127.0.0.1:8080/api/health#fragment",
            "http://127.0.0.1:0/api/health",
            "http://127.0.0.1:65536/api/health",
            "http://127.0.0.1:8080/api/health x",
            "http://127.0.0.1:8080/\u5065\u5eb7",
        ]
        for url in bad_urls:
            with self.subTest(url=url):
                with self.assertRaises(sd.ConfigError):
                    self._load_entries(
                        [
                            {
                                "name": "bad",
                                "url": url,
                                "kind": "aggregate",
                            }
                        ]
                    )

    def test_manifest_structure_and_entries_are_strict(self):
        cases = [
            "not json",
            "[]",
            '{"services": []}',
            '{"services": [{"name":"a","url":"http://127.0.0.1:9/","kind":"service"}]}',
            (
                '{"services": [{"name":"a","url":"http://127.0.0.1:9/",'
                '"kind":"aggregate","expected_service":"a"}]}'
            ),
            (
                '{"services": [{"name":"a","url":"http://127.0.0.1:9/",'
                '"kind":"service","expected_service":"a","extra":1}]}'
            ),
            (
                '{"services": ['
                '{"name":"a","url":"http://127.0.0.1:9/","kind":"service",'
                '"expected_service":"a"},'
                '{"name":"a","url":"http://127.0.0.1:10/","kind":"service",'
                '"expected_service":"a"}]}'
            ),
        ]
        for document in cases:
            with self.subTest(document=document):
                with self.assertRaises(sd.ConfigError):
                    sd.load_manifest(self._write(document))

    def test_missing_manifest_is_config_error(self):
        missing = Path(self.tmpdir.name) / "missing.json"
        with self.assertRaises(sd.ConfigError):
            sd.load_manifest(missing)


class CliTests(_LoopbackServerTestCase):
    def test_exit_zero_and_html_report_on_success(self):
        manifest = self._write_manifest(
            [
                {
                    "name": "alpha",
                    "url": self._url("/secret"),
                    "kind": "service",
                    "expected_service": "alpha",
                }
            ]
        )
        report = Path(self.tmpdir.name) / "report.html"
        code, stdout, stderr = self._run_main(
            "--manifest",
            str(manifest),
            "--timeout",
            "1",
            "--jobs",
            "2",
            "--html",
            str(report),
        )
        self.assertEqual(sd.EXIT_OK, code)
        self.assertIn("正常 1/1", stdout)
        self.assertEqual("", stderr)
        self.assertTrue(report.exists())
        document = report.read_text(encoding="utf-8")
        self.assertIn("本地服务诊断报告", document)
        self.assertIn("alpha", document)
        self.assertNotIn(BODY_MARKER, document)

    def test_service_failure_uses_exit_one(self):
        manifest = self._write_manifest(
            [
                {
                    "name": "alpha",
                    "url": self._url("/http-500"),
                    "kind": "service",
                    "expected_service": "alpha",
                }
            ]
        )
        code, stdout, stderr = self._run_main(
            "--manifest", str(manifest), "--timeout", "1"
        )
        self.assertEqual(sd.EXIT_SERVICE_FAILURE, code)
        self.assertIn("HTTP 错误", stdout)
        self.assertEqual("", stderr)

    def test_configuration_failure_uses_exit_two(self):
        manifest = self._write_manifest(
            [
                {
                    "name": "remote",
                    "url": "http://example.com:8080/api/health",
                    "kind": "aggregate",
                }
            ]
        )
        code, stdout, stderr = self._run_main("--manifest", str(manifest))
        self.assertEqual(sd.EXIT_CONFIG_ERROR, code)
        self.assertEqual("", stdout)
        self.assertIn("配置错误", stderr)

    def test_invalid_timeout_uses_exit_two_without_probing(self):
        manifest = self._write_manifest(
            [
                {
                    "name": "alpha",
                    "url": self._url("/ok"),
                    "kind": "service",
                    "expected_service": "alpha",
                }
            ]
        )
        code, stdout, stderr = self._run_main(
            "--manifest", str(manifest), "--timeout", "0"
        )
        self.assertEqual(sd.EXIT_CONFIG_ERROR, code)
        self.assertEqual("", stdout)
        self.assertIn("--timeout", stderr)
        self.assertEqual([], self.server.hits)

    def test_report_write_failure_uses_exit_two(self):
        manifest = self._write_manifest(
            [
                {
                    "name": "alpha",
                    "url": self._url("/ok"),
                    "kind": "service",
                    "expected_service": "alpha",
                }
            ]
        )
        code, stdout, stderr = self._run_main(
            "--manifest",
            str(manifest),
            "--timeout",
            "1",
            "--html",
            self.tmpdir.name,
        )
        self.assertEqual(sd.EXIT_CONFIG_ERROR, code)
        self.assertIn("正常 1/1", stdout)
        self.assertIn("配置错误", stderr)


if __name__ == "__main__":
    unittest.main()
