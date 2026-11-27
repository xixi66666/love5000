"""开奖抓取脚本共用的 HTTP、字段解析与 CSV 写出工具。

`fetch_ssq.py`、`fetch_dlt.py`、`update_daily.py` 通过 `sys.path` 直接以模块名
`_common` 导入，因此文件名带下划线前缀：它不是可独立运行的服务入口，没有命令行参数，
也不会主动退出进程，退出码由调用脚本决定。

副作用：`save_json` / `write_csv` 会创建父目录并覆盖目标文件；`get` / `get_json`
会真实访问上游站点，失败按线性退避重试。上游普遍存在临时 5xx 与限流，重试耗尽后
统一抛 `RuntimeError`，由调用方决定整轮放弃还是仅记录，本模块不吞异常。
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
# 上游原始响应按彩种存一份快照，便于回查某期数据到底来自哪一次抓取。
RAW_DIR = DATA_DIR / "raw"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def get(url, *, params=None, headers=None, timeout=30, retries=5):
    """带重试的 GET，返回已通过状态码校验的响应对象。

    Args:
        url: 完整地址。
        params: 查询参数，由 requests 负责编码。
        headers: 额外请求头，会与默认 `User-Agent` 合并；调用方常用它设置 `Referer`，
            官方接口在缺少同站 `Referer` 时会拒绝请求。
        timeout: 单次请求超时秒数。
        retries: 总尝试次数（含第一次）。

    Returns:
        `requests.Response`，已调用 `raise_for_status()`。

    Raises:
        RuntimeError: 重试耗尽仍失败。错误信息只带 URL，不带上游响应体，
            真正的异常以 `__cause__` 保留。逐次重试的间隔为 1s、2s……用于避开
            上游瞬时限流，最后一次失败后不再等待。
    """
    merged_headers = {"User-Agent": USER_AGENT}
    if headers:
        merged_headers.update(headers)

    last_error = None
    for attempt in range(retries):
        try:
            response = requests.get(
                url,
                params=params,
                headers=merged_headers,
                timeout=timeout,
            )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"request failed: {url}") from last_error


def get_json(url, *, params=None, headers=None, timeout=30, retries=5):
    """GET 并按 UTF-8 解析 JSON。

    上游响应头偶有缺失或声明错误，因此直接从字节解码而不是依赖 `response.json()`
    的编码探测，避免中文日期被解成乱码。

    Args:
        url: 完整地址。
        params: 查询参数。
        headers: 额外请求头。
        timeout: 单次请求超时秒数。
        retries: 总尝试次数。

    Returns:
        解析后的 JSON 对象，结构随接口而定。

    Raises:
        RuntimeError: 请求重试耗尽（见 `get`）。
        json.JSONDecodeError: 响应不是合法 JSON，例如被上游换成验证页。
    """
    response = get(
        url,
        params=params,
        headers=headers,
        timeout=timeout,
        retries=retries,
    )
    return json.loads(response.content.decode("utf-8"))


def to_int(value):
    """尽量把上游字段转成整数，转不了返回 `None`。

    先去掉千分位逗号再走 float，是因为官方接口同一字段既可能给 `"12345678"`，
    也可能给 `"12345678.0"`；空串与空值一律视为缺失，避免把缺数据写成 0。

    Args:
        value: 原始字段值，可为 `None`、字符串或数字。

    Returns:
        转换成功的 `int`，或 `None` 表示缺失/无法解析。本函数不抛异常，
        缺字段因此不会中断整页解析。
    """
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def normalize_issue_ssq(issue):
    """把 500.com 的 5 位期号补成官方 7 位期号。

    500.com 历史页按 `YYNNN` 给期号（如 `03001`），官方接口用 `YYYYNNN`；
    两段数据要按 `issue` 合并，必须先把年份补成 2000 年后四位。

    Args:
        issue: 原始期号，位数非 5 时原样返回，便于兼容已是 7 位的来源。
    """
    text = str(issue).strip()
    if len(text) == 5:
        return f"20{text}"
    return text


def save_json(path, payload):
    """把上游响应落盘为便于人工比对的 JSON 快照。

    覆盖写入，父目录不存在时自动创建；`indent=1` 与 `ensure_ascii=False` 是为了让
    快照可读、中文不被转义，这些文件只用于排查，不参与后续计算。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)


def write_csv(path, fieldnames, rows):
    """按固定列序写出 UTF-8 BOM 的 CSV，并打印行数与相对路径。

    使用 `utf-8-sig` 是为了让 Excel 直接打开时中文表头不乱码；`extrasaction="ignore"`
    允许行字典带有多余键，这样抓取阶段的临时字段不会导致写盘失败。

    Args:
        path: 目标文件，父目录不存在时自动创建，已存在的文件会被整体覆盖。
        fieldnames: 列顺序；行字典按此顺序取值，缺键写成空列。
        rows: 行字典序列。

    副作用：覆盖目标文件并向 stdout 打印一行统计。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows):>6,} rows -> {path.relative_to(ROOT)}")
