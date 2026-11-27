import base64
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest


WORKER = Path(__file__).with_name("engine.py")
HEAD = ("Test item", "Result", "Unit", "Reference range", "Flag")
ROWS = (("Hemoglobin", "140", "g/L", "120-160", ""), ("ALT", "62", "U/L", "8-40", "H"),
        ("Creatinine", "72", "umol/L", "44-97", ""), ("Albumin", "44", "g/L", "35-52", ""))


def run_worker(request):
    result = subprocess.run([sys.executable, "-I", "-B", "-X", "utf8", str(WORKER)],
                            input=json.dumps(request).encode(), capture_output=True, check=True, timeout=25)
    reply = json.loads(result.stdout)
    if not reply["ok"]:
        raise AssertionError("worker rejected the synthetic fixture")
    return reply["data"]


def report_pdf():
    text = ["BT /F1 11 Tf 1 0 0 1 50 750 Tm (Synthetic laboratory report) Tj ET"]
    for i, row in enumerate((HEAD, *ROWS)):
        for x, cell in zip((50, 215, 290, 360, 500), row):
            if cell:
                text.append(f"BT /F1 10 Tf 1 0 0 1 {x} {700 - i * 20} Tm ({cell}) Tj ET")
    content = "\n".join(text).encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream"]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(b"%d 0 obj\n" % number + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets:
        pdf.extend(b"%010d 00000 n \n" % offset)
    pdf.extend(b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % xref)
    return bytes(pdf)


class EngineTest(unittest.TestCase):
    def parse(self, extension, contents):
        return run_worker({"operation": "parse", "extension": extension,
                           "bytes": base64.b64encode(contents).decode()})["metrics"]

    def test_offline_alias_and_compatible_units(self):
        rows = [{"name": name, "value": value, "unit": unit} for name, value, unit in (
            ("血红蛋白", "140", "g/L"), ("Hemoglobin", "14", "g/dL"), ("血脂", "3", "g/L"),
        )]
        first, second, unknown = run_worker({"operation": "normalize", "rows": rows})
        self.assertEqual(first["loinc"], "718-7")
        self.assertEqual(first["loinc"], second["loinc"])
        self.assertEqual(first["comparison_unit"], second["comparison_unit"])
        self.assertEqual(first["comparison_value"], second["comparison_value"])
        self.assertEqual(unknown["state"], "pending")

    def test_pdf_table_returns_page_and_original_fields(self):
        metrics = self.parse("pdf", report_pdf())
        alt = next(row for row in metrics if row["name"] == "ALT")
        self.assertEqual((alt["location"], alt["value"], alt["range"], alt["flag"]), ("第 1 页", "62", "8-40", "H"))

    def test_xlsx_docx_and_visual_transcripts(self):
        from docx import Document
        from openpyxl import Workbook

        workbook = Workbook()
        document = Document()
        table = document.add_table(rows=0, cols=5)
        for row in (HEAD, *ROWS):
            workbook.active.append(row)
            for cell, value in zip(table.add_row().cells, row):
                cell.text = value
        for suffix, source in (("xlsx", workbook), ("docx", document)):
            with self.subTest(suffix=suffix):
                buffer = io.BytesIO()
                source.save(buffer)
                self.assertEqual(len(self.parse(suffix, buffer.getvalue())), len(ROWS))
        transcript = "\n".join("| " + " | ".join(row) + " |" for row in (HEAD, ("---",) * 5, *ROWS))
        parsed = run_worker({"operation": "parse", "transcripts": [transcript]})
        self.assertEqual(len(parsed["metrics"]), len(ROWS))


if __name__ == "__main__":
    unittest.main()
