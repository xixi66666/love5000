"""Star 增长计算（纯函数，无 I/O）。

详情接口优先复用 ``trending_entries`` 里榜单页给出的增量；只有当某个周期没有榜单行
（例如仓库刚入库、只在日榜出现过）时才用 ``star_snapshots`` 回退计算。
本模块只做回退部分，日期比较全部按调用方传入的业务日期，不读系统时区。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class SnapshotPoint:
    """一天的总 Star 快照。

    Attributes:
        snapshot_date: 业务时区下的日期。
        stars_count: 当日总 Star。
    """

    snapshot_date: date
    stars_count: int


@dataclass(frozen=True)
class Growth:
    """一个仓库的日/周增量。

    两个字段都可能为 ``None``：缺少基准快照时无法计算，接口会返回 ``null``
    而不是伪造 0，前端据此显示“—”。
    """

    daily: int | None
    weekly: int | None


def calculate_growth(snapshots: list[SnapshotPoint], target_date: date) -> Growth:
    """按目标日期计算日增与周增。

    “基准”取目标日期之前（含当天向前推 1/7 天）最近的一条快照，因此快照有缺口时
    仍然可用，只是天数区间被拉长；完全取不到基准则该维度返回 ``None``。

    Args:
        snapshots: 按 ``snapshot_date`` **升序**排列的快照列表。
        target_date: 业务日期（“今天”）。

    Returns:
        :class:`Growth`；没有任何不晚于 ``target_date`` 的快照时两个维度都为 ``None``。
    """
    latest = _latest_at_or_before(snapshots, target_date)
    if latest is None:
        return Growth(daily=None, weekly=None)

    baseline_daily = _latest_at_or_before(snapshots, target_date - timedelta(days=1))
    baseline_weekly = _latest_at_or_before(snapshots, target_date - timedelta(days=7))

    daily = latest.stars_count - baseline_daily.stars_count if baseline_daily else None
    weekly = latest.stars_count - baseline_weekly.stars_count if baseline_weekly else None
    return Growth(daily=daily, weekly=weekly)


def _latest_at_or_before(snapshots: list[SnapshotPoint], cutoff: date) -> SnapshotPoint | None:
    """取不晚于 ``cutoff`` 的最近一条快照。

    依赖入参已按日期升序排列，因此从尾部往前找，命中第一条即可返回。

    Args:
        snapshots: 升序快照列表。
        cutoff: 日期上界（含）。

    Returns:
        命中的快照；全部晚于 ``cutoff`` 时返回 ``None``。
    """
    for snapshot in reversed(snapshots):
        if snapshot.snapshot_date <= cutoff:
            return snapshot
    return None
