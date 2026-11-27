"""Star 日增/周增回退计算的边界用例。

`calculate_growth` 仅在 `trending_entries` 没有对应周期榜单行时启用：以目标业务日期
为基准，取不晚于「今天 -1 天」与「今天 -7 天」的最近一条 `star_snapshots` 快照做差。
快照按天离散落库、允许有缺口，所以这里重点覆盖：连续两天、中间缺天、只有首条快照、
星数下降、恰好 7 天边界、7 天前缺快照时向前回退，以及完全没有快照。
缺数据时必须是 `None` 而不是伪造 0，前端据此显示“—”。纯函数，无数据库与网络。
"""

from datetime import date

from app.services.trend import SnapshotPoint, calculate_growth


def test_growth_across_consecutive_days() -> None:
    snapshots = [
        SnapshotPoint(date(2026, 8, 1), 100),
        SnapshotPoint(date(2026, 8, 2), 104),
    ]
    result = calculate_growth(snapshots, date(2026, 8, 2))
    assert result.daily == 4
    assert result.weekly is None


def test_growth_with_missing_day_uses_latest_previous_snapshot() -> None:
    snapshots = [
        SnapshotPoint(date(2026, 8, 1), 100),
        SnapshotPoint(date(2026, 8, 2), 104),
        SnapshotPoint(date(2026, 8, 9), 121),
    ]
    result = calculate_growth(snapshots, date(2026, 8, 9))
    assert result.daily == 17
    assert result.weekly == 17


def test_first_snapshot_has_no_baseline() -> None:
    snapshots = [SnapshotPoint(date(2026, 8, 1), 100)]
    result = calculate_growth(snapshots, date(2026, 8, 1))
    assert result.daily is None
    assert result.weekly is None


def test_star_decrease_is_negative() -> None:
    snapshots = [
        SnapshotPoint(date(2026, 8, 1), 100),
        SnapshotPoint(date(2026, 8, 2), 95),
    ]
    result = calculate_growth(snapshots, date(2026, 8, 2))
    assert result.daily == -5


def test_weekly_boundary_uses_7_days_back() -> None:
    snapshots = [
        SnapshotPoint(date(2026, 8, 1), 100),
        SnapshotPoint(date(2026, 8, 2), 110),
        SnapshotPoint(date(2026, 8, 8), 120),
        SnapshotPoint(date(2026, 8, 10), 130),
    ]
    result = calculate_growth(snapshots, date(2026, 8, 10))
    assert result.daily == 10
    assert result.weekly == 20


def test_weekly_uses_earlier_snapshot_when_7_days_ago_missing() -> None:
    snapshots = [
        SnapshotPoint(date(2026, 8, 1), 100),
        SnapshotPoint(date(2026, 8, 8), 110),
        SnapshotPoint(date(2026, 8, 10), 120),
    ]
    result = calculate_growth(snapshots, date(2026, 8, 10))
    assert result.daily == 10
    assert result.weekly == 20


def test_no_prior_snapshot_at_all_returns_none() -> None:
    snapshots: list[SnapshotPoint] = []
    result = calculate_growth(snapshots, date(2026, 8, 1))
    assert result.daily is None
    assert result.weekly is None
