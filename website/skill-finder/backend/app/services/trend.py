from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class SnapshotPoint:
    snapshot_date: date
    stars_count: int


@dataclass(frozen=True)
class Growth:
    daily: int | None
    weekly: int | None


def calculate_growth(snapshots: list[SnapshotPoint], target_date: date) -> Growth:
    latest = _latest_at_or_before(snapshots, target_date)
    if latest is None:
        return Growth(daily=None, weekly=None)

    baseline_daily = _latest_at_or_before(snapshots, target_date - timedelta(days=1))
    baseline_weekly = _latest_at_or_before(snapshots, target_date - timedelta(days=7))

    daily = latest.stars_count - baseline_daily.stars_count if baseline_daily else None
    weekly = latest.stars_count - baseline_weekly.stars_count if baseline_weekly else None
    return Growth(daily=daily, weekly=weekly)


def _latest_at_or_before(snapshots: list[SnapshotPoint], cutoff: date) -> SnapshotPoint | None:
    for snapshot in reversed(snapshots):
        if snapshot.snapshot_date <= cutoff:
            return snapshot
    return None
