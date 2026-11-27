"""python-a 的 JSON 运行数据存储原语。

对外提供 ``JsonStore``（``path_for`` / ``read_list`` / ``write_list`` /
``append_row``）以及三个与业务日期相关的小工具 ``now_iso``、``new_id``、
``filter_by_date``。账户、交易、解析草稿、股票名称映射等模块都通过这里落盘，
不使用数据库，也不访问网络。

磁盘布局：所有相对路径相对 ``JsonStore.root`` 解析（生产环境为
``obsidian-vault/A股AI``），一个文件对应一个 JSON 数组，UTF-8 无 BOM、缩进 2、
中文不转义。写入先落到同目录的 ``<文件名>.tmp``，再用 ``os.replace`` 原子替换，
读者不会看到写了一半的文件，进程崩溃也只留下一个可丢弃的临时文件。

降级策略：文件不存在视为空数组；文件不是合法 JSON 时先改名为
``<文件名>.corrupt-<YYYYmmddHHMMSS>`` 再抛 ``ValueError``，宁可让本次请求失败也
不能静默清空用户的交易记录；内容不是数组时抛 ``ValueError``。读取使用
``utf-8-sig``，兼容被编辑器加上 BOM 的手工修改文件。
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def now_iso() -> str:
    """返回带本机时区偏移的 ISO 8601 时间戳，精确到秒。

    形如 ``2024-05-06T15:04:05+08:00``。所有 ``created_at`` / ``written_at`` /
    ``confirmed_at`` 字段都用它，保证同一份 JSON 内的时间字符串可按字典序比较。
    """
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_id(prefix: str, date_value: Optional[str], sequence: int) -> str:
    """拼出 ``<prefix>_<YYYYMMDD>_<NNN>`` 形式的业务编号。

    Args:
        prefix: 业务前缀，资金流水为 ``cf``、账户快照为 ``as``、交易为 ``tr``、
            解析草稿为 ``pd``。
        date_value: 业务日期 ``YYYY-MM-DD``；为空时退化为本机当天，调用方通常
            总会传入业务日期。
        sequence: 调用方给的序号，补零到 3 位，超过 999 后自然变长；是否按日
            累计由调用方决定，本函数只负责拼格式。

    Returns:
        去掉日期分隔符的编号字符串，例如 ``tr_20240506_001``；只保证格式唯一，
        真正的去重由调用方比对已有编号。
    """
    clean_date = (date_value or datetime.now().strftime("%Y-%m-%d")).replace("-", "")
    return f"{prefix}_{clean_date}_{sequence:03d}"


def filter_by_date(rows: List[Dict[str, Any]], date_value: Optional[str]) -> List[Dict[str, Any]]:
    """按业务日期过滤行，同时兼容 ``trade_date`` 与 ``date`` 两种字段名。

    资金流水用 ``date``、账户快照用 ``trade_date``，这里两种都认，调用方不必先统一
    字段名。``date_value`` 为空时返回全部行的浅拷贝，调用方追加元素不会改动存储
    中的原始列表；行元素本身仍是共享引用。

    Args:
        rows: 已从 JSON 读出的行列表。
        date_value: ``YYYY-MM-DD``；为空表示不过滤。

    Returns:
        命中日期的行；顺序与入参一致（即写入顺序）。
    """
    if not date_value:
        return list(rows)
    return [
        row
        for row in rows
        if row.get("trade_date") == date_value or row.get("date") == date_value
    ]


class JsonStore:
    """以“一个文件一个 JSON 数组”为单位的轻量存储。

    一个实例绑定一个根目录，文件路径由调用方以相对路径给出。本层不做路径越界
    校验，因为所有调用方传的都是模块内固定常量，不会拼接请求参数；新增调用方时
    必须保持这一点。实例本身无锁：``append_row`` 是读-改-写，多线程并发会相互
    覆盖，需要串行化的场景由调用方加锁（``TradeService`` 使用模块级 ``RLock``）。
    """

    def __init__(self, root: Path):
        """绑定存储根目录。

        Args:
            root: 运行数据目录，通常是 ``obsidian-vault/A股AI``；目录不要求已存在，
                首次写入时由 ``write_list`` 自动创建父目录。
        """
        self.root = Path(root)

    def path_for(self, relative_path: str) -> Path:
        """把相对路径拼成绝对路径，只做拼接，不检查文件是否存在。"""
        return self.root / relative_path

    def read_list(self, relative_path: str) -> List[Dict[str, Any]]:
        """读取一个 JSON 数组文件。

        Args:
            relative_path: 相对存储根目录的文件名，例如 ``trades.json``。

        Returns:
            文件中的行列表；文件不存在时返回空列表，让空账本和缺失文件行为一致。

        Raises:
            ValueError: 内容不是合法 JSON 或不是数组。前者会先把原文件改名成
                ``<文件名>.corrupt-<YYYYmmddHHMMSS>`` 保留现场；改名本身失败
                （例如文件被其他程序占用）时 ``OSError`` 会直接冒泡。
        """
        path = self.path_for(relative_path)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            backup = path.with_name(f"{path.name}.corrupt-{datetime.now().strftime('%Y%m%d%H%M%S')}")
            path.replace(backup)
            raise ValueError(f"JSON 文件损坏，已备份到 {backup}") from exc
        if not isinstance(data, list):
            raise ValueError(f"{relative_path} 必须是 JSON 数组")
        return data

    def write_list(self, relative_path: str, rows: List[Dict[str, Any]]) -> None:
        """用给定行整体覆盖一个 JSON 数组文件。

        先写 ``<文件名>.tmp`` 再 ``os.replace`` 原子替换：Windows 上同一目录内的
        替换是原子的，读者要么看到旧文件要么看到新文件；``os.replace`` 也允许覆盖
        已存在的目标，避免先删后建出现空窗。

        Args:
            relative_path: 相对存储根目录的文件名。
            rows: 完整行列表，按调用方给定顺序写入；``ensure_ascii=False`` 让中文
                在 Obsidian 里保持可读。
        """
        path = self.path_for(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(temp_path), str(path))

    def append_row(self, relative_path: str, row: Dict[str, Any]) -> Dict[str, Any]:
        """在文件末尾追加一行并返回该行。

        读-改-写三步不是原子的：两个请求同时追加可能丢掉其中一行，因此需要
        唯一性或顺序保证的调用方必须自己串行化。返回值就是入参对象本身，方便
        调用方直接作为响应体回传。

        Args:
            relative_path: 相对存储根目录的文件名。
            row: 已校验并补齐派生字段的行。

        Returns:
            追加进去的那一行。
        """
        rows = self.read_list(relative_path)
        rows.append(row)
        self.write_list(relative_path, rows)
        return row
