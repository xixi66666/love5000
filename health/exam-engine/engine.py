"""体检子进程。stdin/stdout 只传单个 JSON，模型和文件持久化由 Java 负责。"""

import asyncio
import base64
import html
import io
import json
import math
import re
import sys
import zipfile

MAX_BYTES = 12 * 1024 * 1024
MAX_TEXT = 200_000
MAX_ROWS = 400
PAGE_MARKER = re.compile(r"^--- page ([1-9]\d*) ---\n", re.MULTILINE)
SHEET_MARKER = re.compile(r"^--- sheet: (.{1,80}) ---\n", re.MULTILINE)
TABLE_ROW = re.compile(r"<tr(?:\s[^>]*)?>(.*?)</tr\s*>", re.I | re.S)
TABLE_CELL = re.compile(r"<t[hd](?:\s[^>]*)?>(.*?)</t[hd]\s*>", re.I | re.S)
DECIMAL = re.compile(r"[+-]?\d{1,12}(?:\.\d{1,8})?\Z")


def normalize(rows):
    from mirobody import resolve_reading
    from mirobody.units import canonicalize, normalize_unit

    output = []
    for row in rows:
        name, value, unit = (row[key] for key in ("name", "value", "unit"))
        result = resolve_reading(name, value, unit)
        code = {"state": "pending"}
        if result.resolved and result.method == "lexical" and result.loinc:
            code = {"state": "coded", "loinc": result.loinc, "label": result.canonical}
            ucum = normalize_unit(unit) if result.unit_recognized else None
            if ucum and DECIMAL.fullmatch(value) and {"property", "scale"} <= set(result.evidence):
                comparable = canonicalize(float(value), ucum)
                if math.isfinite(comparable.value):
                    code.update(unit=ucum, comparison_unit=comparable.unit,
                                comparison_value=format(comparable.value, ".12g"))
        output.append(code)
    return output


def plain(text):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", text)).split())


def printed_rows(text):
    for row in TABLE_ROW.finditer(text):
        yield [plain(cell) for cell in TABLE_CELL.findall(row[1])]
    for line in text.splitlines():
        if line.strip().startswith("|"):
            yield [" ".join(html.unescape(cell).split()) for cell in line.strip().strip("|").split("|")]


def row_evidence(row, candidates):
    fields = {key: " ".join(str(row.get(source, "")).split()) for key, source in (
        ("name", "original_indicator"), ("value", "value"), ("unit", "unit"),
        ("range", "reference_range"), ("flag", "_printed_flag"),
    )}
    if not fields["name"] or not fields["value"] or any(len(text) > 100 for text in fields.values()):
        return None
    # 每个提取字段必须属于同一原始表格行，值必须是独立单元格或附有单位、标记的单元格首部。
    required = [value for key, value in fields.items() if key != "value" and value]
    sample = fields["value"]
    found = set()
    for cells in candidates:
        if fields["name"] not in cells:
            continue
        quote = " | ".join(cell for cell in cells if cell)
        for cell in cells:
            if cell != sample and not re.match(re.escape(sample) + r"(?=\s|[↑↓(（]|[^\W\d_])", cell):
                continue
            if all(part in quote for part in required) and len(quote) <= 500:
                found.add(quote)
    if len(found) == 1:
        return {**fields, "quote": next(iter(found))}
    return None


def extract_metrics(sections):
    from mirobody.collect.files.services.table_indicators import table_indicators

    metrics, dropped = [], 0
    for location, text in sections:
        readings, _, unread = table_indicators(text)
        candidates = list(printed_rows(text))
        dropped += unread
        seen = set()
        for row in readings:
            metric = row_evidence(row, candidates)
            if not metric or len(metrics) >= MAX_ROWS:
                dropped += 1
                continue
            key = tuple(metric.values())
            if key not in seen:
                metrics.append({**metric, "location": location})
                seen.add(key)
    return {"metrics": metrics, "omitted": dropped}


def split_sections(text, pattern, label):
    markers = list(pattern.finditer(text))
    return [(label.format(match[1]), text[match.end():markers[i + 1].start() if i + 1 < len(markers) else len(text)])
            for i, match in enumerate(markers)]


async def parse(request):
    from mirobody.documents import extract

    if "transcripts" in request:
        sections = [(f"第 {i} 页", text) for i, text in enumerate(request["transcripts"], 1)]
    else:
        data = base64.b64decode(request["bytes"], validate=True)
        suffix = request["extension"]
        if len(data) > MAX_BYTES:
            raise ValueError("size")
        if suffix == "pdf":
            text = await extract.pdf_text(data)
            sections = split_sections(text, PAGE_MARKER, "第 {} 页")
        elif suffix in {"docx", "xlsx"}:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sum(item.file_size for item in archive.infolist()) > 32 * 1024 * 1024:
                    raise ValueError("archive size")
            text = await extract.extract_text("report." + suffix, None, data)
            sections = split_sections(text, SHEET_MARKER, "工作表 {}") if suffix == "xlsx" else [("Word 表格", text)]
        else:
            raise ValueError("unsupported")
    if sum(len(text) for _, text in sections) > MAX_TEXT:
        raise ValueError("text size")
    return extract_metrics(sections)


def main():
    try:
        request = json.loads(sys.stdin.buffer.read(18 * 1024 * 1024))
        operation = request["operation"]
        if operation == "normalize":
            result = normalize(request["rows"])
        elif operation == "parse":
            result = asyncio.run(parse(request))
        else:
            raise ValueError("operation")
        json.dump({"ok": True, "data": result}, sys.stdout, ensure_ascii=False)
    except Exception:
        # 原件、转录、路径及第三方异常详情均不回传。
        json.dump({"ok": False}, sys.stdout)


if __name__ == "__main__":
    main()
