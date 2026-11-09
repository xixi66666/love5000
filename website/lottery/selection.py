"""基于本地历史开奖生成候选号码；不修改数据。"""

import math
import secrets

from scripts.selection_backtest import GAMES, load_draws

from selection_stats import back_stats, front_stats

METHODS = {"random", "hot100", "cold100", "overdue", "weighted"}


def generate(game, method, count, rng=None):
    """计算单注或多注号码；同分时随机决定顺序。"""
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
            for age, (_, _, values) in enumerate(reversed(draws[-100:])):
                weight = math.pow(0.5, age / 30.0) if method == "weighted" else 1
                for number in values[area_index]:
                    scores[number] += weight
        elif method == "overdue":
            scores = [-1] * (pool + 1)
            for position, (_, _, values) in enumerate(draws):
                for number in values[area_index]:
                    scores[number] = position
        rankings.append((pool, pick, scores))

    last_front = set(draws[-1][2][0])
    tickets = []
    for _ in range(count):
        selections = []
        for pool, pick, scores in rankings:
            numbers = list(range(1, pool + 1))
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
