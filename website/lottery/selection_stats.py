"""选号工具的号码形态统计。

口径与操作台 `src/lottery/features.py` 保持一致：
和值、跨度、奇偶比、大小比、三区比、连号组数、AC 值、与上期重号。
"""

from scripts.selection_backtest import GAMES, load_draws

PRIMES = frozenset((2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31))


def zone_edges(pool):
    """三区边界，与 Game.zone_edges 相同。"""
    return round(pool / 3), round(pool * 2 / 3)


def front_stats(numbers, pool):
    """一组前区/红球号码的形态指标。"""
    nums = sorted(int(n) for n in numbers)
    k = len(nums)
    gaps = [b - a for a, b in zip(nums, nums[1:])]

    e1, e2 = zone_edges(pool)
    zone = [
        sum(1 for n in nums if n <= e1),
        sum(1 for n in nums if e1 < n <= e2),
        sum(1 for n in nums if n > e2),
    ]

    run = best = 1
    for gap in gaps:
        run = run + 1 if gap == 1 else 1
        best = max(best, run)

    diffs = {abs(a - b) for i, a in enumerate(nums) for b in nums[i + 1:]}
    return {
        "sum": int(sum(nums)),
        "span": int(nums[-1] - nums[0]),
        "odd": int(sum(1 for n in nums if n % 2)),
        "big": int(sum(1 for n in nums if n > pool // 2)),
        "zone": "|".join(str(z) for z in zone),
        "zone_parts": zone,
        "consecutive": int(sum(1 for g in gaps if g == 1)),
        "max_run": int(best),
        "ac": int(len(diffs) - (k - 1)),
        "prime": int(sum(1 for n in nums if n in PRIMES)),
        "tail_distinct": int(len({n % 10 for n in nums})),
    }


def back_stats(numbers, pool, pick):
    """后区/蓝球的形态指标；单球只给号码本身。"""
    nums = sorted(int(n) for n in numbers)
    if pick == 1:
        return {"number": nums[0], "sum": nums[0], "span": 0}
    return {
        "sum": int(sum(nums)),
        "span": int(nums[-1] - nums[0]),
        "odd": int(sum(1 for n in nums if n % 2)),
    }


def recent_draws(game, limit=20):
    """最近若干期开奖及形态，最新一期在前。"""
    if game not in GAMES:
        raise ValueError("未知彩种")
    _, areas = GAMES[game]
    draws = load_draws(game, areas)
    start = max(0, len(draws) - limit - 1)
    previous = None
    rows = []
    for date, issue, values in draws[start:]:
        front = sorted(values[0])
        back = sorted(values[1])
        rows.append(
            {
                "issue": int(issue),
                "date": date,
                "front": front,
                "back": back,
                "stats": front_stats(front, areas[0][1]),
                "back_stats": back_stats(back, areas[1][1], areas[1][2]),
                "repeat": None if previous is None else len(set(front) & previous),
            }
        )
        previous = set(front)
    return rows[-limit:][::-1]
