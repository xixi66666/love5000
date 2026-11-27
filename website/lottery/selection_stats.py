"""选号工具的号码形态统计。

口径与操作台 `src/lottery/features.py` 保持一致：
和值、跨度、奇偶比、大小比、三区比、连号组数、AC 值、与上期重号。
两处算法必须同步修改，否则选号页与操作台会对同一注号码给出不同形态。

本模块只读历史 CSV，不写文件、不联网，没有命令行参数，也不调用 `sys.exit`；
号码合法性由 `scripts/selection_backtest.load_draws` 在读取阶段统一校验，这里不重复兜底。
"""

from scripts.selection_backtest import GAMES, load_draws

PRIMES = frozenset((2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31))


def zone_edges(pool):
    """三区边界，与 `Game.zone_edges` 相同。

    Args:
        pool: 号码池大小（双色球红球 33、大乐透前区 35）。

    Returns:
        `(第一区上界, 第二区上界)`，四舍五入到整数。区间用「小于等于上界」划分，
        因此正好落在边界上的号码归入前一个区。
    """
    return round(pool / 3), round(pool * 2 / 3)


def front_stats(numbers, pool):
    """计算一组前区/红球号码的形态指标。

    Args:
        numbers: 号码序列，顺序任意，函数内部先排序。
        pool: 号码池大小，决定三区边界与大小号划分（大于 `pool // 2` 记为 big）。

    Returns:
        形态字典：和值 `sum`、跨度 `span`、奇数个数 `odd`、大号个数 `big`、
        三区比字符串 `zone` 与列表 `zone_parts`、相邻连号对数 `consecutive`、
        最长连号长度 `max_run`、离散度 `ac`（两两差值去重数减 `k-1`）、
        质数个数 `prime`、不同尾数个数 `tail_distinct`。
    """
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
    """计算后区/蓝球的形态指标。

    双色球蓝球只选 1 个，此时和值与跨度没有比较意义，只回号码本身并把跨度固定为 0，
    避免前端为单球再写一次特判。

    Args:
        numbers: 后区/蓝球号码序列。
        pool: 号码池大小（蓝球 16、后区 12）；当前实现未使用，保留是为了与
            `front_stats` 及各调用点的签名一致。
        pick: 每注选号个数，1 表示单球。
    """
    nums = sorted(int(n) for n in numbers)
    if pick == 1:
        return {"number": nums[0], "sum": nums[0], "span": 0}
    return {
        "sum": int(sum(nums)),
        "span": int(nums[-1] - nums[0]),
        "odd": int(sum(1 for n in nums if n % 2)),
    }


def recent_draws(game, limit=20):
    """取最近若干期开奖及形态，最新一期在前。

    多读一期再切片，是为了让返回序列的最早一行也能算出与「上一期」的重号数；
    只读 `limit` 期会让这一行缺对照组。因此某行的 `repeat` 为 `None` 只表示
    没有更早的期次可比，不代表这期没有重号。

    Args:
        game: 彩种代号，必须在 `GAMES` 中。
        limit: 期数，默认 20；数据不足时返回现有全部。

    Returns:
        列表，元素为含期号、日期、前后区号码、形态统计与 `repeat` 的字典，
        按期号降序排列（最新在前）。

    Raises:
        ValueError: 彩种未知。
    """
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
