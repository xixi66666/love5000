"""基于本地历史开奖生成候选号码，只读历史 CSV，不修改任何数据。

支持五种方法（`METHODS`）：随机、近 100 期热号、近 100 期冷号、最大遗漏、时间衰减
加权。冷热与加权方法需要至少 100 期历史，不足时直接报错而不是退化成随机，避免把
「数据不够」伪装成一次正常选号。

本模块不联网、不写文件，也不对中奖概率作任何承诺：每期开奖相互独立，方法只决定
从号码池里挑哪几个号，不能提高中奖概率；接口与页面文案都不得声称能够保证中奖。
没有命令行参数，也不调用 `sys.exit`，参数错误一律通过 `ValueError` 交给调用方处理。
"""

import math
import secrets

from scripts.selection_backtest import GAMES, load_draws

from selection_stats import back_stats, front_stats

METHODS = {"random", "hot100", "cold100", "overdue", "weighted"}


def generate(game, method, count, rng=None):
    """生成 `count` 注号码，每注附带形态统计。

    Args:
        game: 彩种代号，必须在 `GAMES` 中（`ssq` / `dlt`）。
        method: 选号方法，必须在 `METHODS` 中。
        count: 注数，1-10；`bool` 被显式排除，因为它是 `int` 的子类且非预期输入。
        rng: 可注入的随机源。默认 `secrets.SystemRandom()`（不可预测，适合线上）；
            测试传入 `random.Random(seed)` 以获得可复现结果。

    Returns:
        响应字典：`success` 恒为真，另含彩种、方法、最近一期期号与日期，以及
        `tickets` 列表；每注含前后区号码、形态统计与和最近一期的重号数。

    Raises:
        ValueError: 彩种、方法或注数不合法，或历史不足 100 期却选了依赖频次/遗漏的
            方法（`hot100` / `cold100` / `weighted`）。
    """
    if game not in GAMES or method not in METHODS or not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 10:
        raise ValueError("彩种、选号方法或注数不合法")
    rng = rng or secrets.SystemRandom()
    _, areas = GAMES[game]
    draws = load_draws(game, areas)
    if len(draws) < 100 and method in ("hot100", "cold100", "weighted"):
        raise ValueError("历史数据不足 100 期，无法使用该方法")

    rankings = []
    for area_index, (_, pool, pick, _) in enumerate(areas):
        scores = [0.0] * (pool + 1)
        if method in ("hot100", "cold100", "weighted"):
            # 只统计最近 100 期；weighted 额外按半衰期 30 期做指数衰减，越新权重越大。
            for age, (_, _, values) in enumerate(reversed(draws[-100:])):
                weight = math.pow(0.5, age / 30.0) if method == "weighted" else 1
                for number in values[area_index]:
                    scores[number] += weight
        elif method == "overdue":
            # 记录每个号码最后一次出现的下标；从未出现的保持 -1，因此会被优先选中。
            scores = [-1] * (pool + 1)
            for position, (_, _, values) in enumerate(draws):
                for number in values[area_index]:
                    scores[number] = position
        rankings.append((pool, pick, scores))

    # 与最近一期前区/红球的重号个数，仅用于页面提示，不参与选号。
    last_front = set(draws[-1][2][0])
    tickets = []
    for _ in range(count):
        selections = []
        for pool, pick, scores in rankings:
            numbers = list(range(1, pool + 1))
            # 先洗牌再稳定排序：同分数的号码顺序由随机源决定，不会每次都偏向小号。
            rng.shuffle(numbers)
            if method != "random":
                numbers.sort(key=lambda number: scores[number], reverse=method in ("hot100", "weighted"))
            selections.append(sorted(numbers[:pick]))
        tickets.append(
            {
                "front": selections[0],
                "back": selections[1],
                "stats": front_stats(selections[0], areas[0][1]),
                "back_stats": back_stats(selections[1], areas[1][1], areas[1][2]),
                "repeat": len(set(selections[0]) & last_front),
            }
        )
    return {"success": True, "game": game, "method": method,
            "data_issue": draws[-1][1], "data_date": draws[-1][0], "tickets": tickets}
