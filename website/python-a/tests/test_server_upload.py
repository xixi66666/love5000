from io import BytesIO
from email.message import Message
import unittest

from server import read_uploaded_image


class UploadImageTests(unittest.TestCase):
    def test_read_uploaded_image_extracts_file_and_trade_date(self):
        boundary = "----python-a-test"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="trade_date"\r\n\r\n'
            "2026-06-05\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="account.jpg"\r\n'
            "Content-Type: image/jpeg\r\n\r\n"
        ).encode("utf-8") + b"\xff\xd8\xff\xd9" + f"\r\n--{boundary}--\r\n".encode("utf-8")
        headers = Message()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        headers["Content-Length"] = str(len(body))
        handler = type("FakeHandler", (), {"headers": headers, "rfile": BytesIO(body)})()

        result = read_uploaded_image(handler)

        self.assertEqual(result["trade_date"], "2026-06-05")
        self.assertEqual(result["mime_type"], "image/jpeg")
        self.assertEqual(result["image_bytes"], b"\xff\xd8\xff\xd9")


if __name__ == "__main__":
    unittest.main()
