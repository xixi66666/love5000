#!/usr/bin/env python3
"""选号方法的逐期样本外回测；仅使用 Python 标准库，不修改开奖数据。"""

import argparse
import csv
import math
import random
from collections import deque
from datetime import date as calendar_date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAMES = {
    "ssq": ("双色球", (("红球", 33, 6, [f"red{i}" for i in range(1, 7)]),
                     ("蓝球", 16, 1, ["blue"]))),
    "dlt": ("大乐透", (("前区", 35, 5, [f"front{i}" for i in range(1, 6)]),
                     ("后区", 12, 2, ["back1", "back2"]))),
}
METHODS = ("random", "hot100", "cold100", "overdue")
LABELS = {"random": "随机基准", "hot100": "近100期热号", "cold100": "近100期冷号", "overdue": "最大遗漏"}


def load_draws(key, areas):
    with (ROOT / "data" / (key + ".csv")).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{key} 开奖数据为空")
    draws = []
    seen = set()
    for row in rows:
        try:
            issue = int(row["issue"])
            date = row["date"]
            calendar_date.fromisoformat(date)
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"{key} 期号或日期无效: {row.get('issue')}, {row.get('date')}") from exc
        if issue in seen:
            raise ValueError(f"{key} 存在重复期号: {issue}")
        seen.add(issue)
        values = []
        for _, pool, count, columns in areas:
            numbers = {int(row[col]) for col in columns}
            if len(numbers) != count or any(n < 1 or n > pool for n in numbers):
                raise ValueError(f"{key} {issue} 号码错误")
            values.append(numbers)
        draws.append((date, issue, values))
    draws.sort(key=lambda draw: (draw[0], draw[1]))
    if any(draws[i][1] >= draws[i + 1][1] for i in range(len(draws) - 1)):
        raise ValueError(f"{key} 日期与期号顺序不一致")
    return draws


def run_area(draws, area_index, pool, count, warmup, evaluation, seed):
    start = max(warmup, len(draws) - evaluation)
    if start >= len(draws):
        raise ValueError("数据不足，请减小 warmup 或提供更多数据")
    # 各方法独立随机数发生器；同分数的号码随机打破平局。
    rng = {method: random.Random(seed + area_index * 100 + i) for i, method in enumerate(METHODS)}
    recent = deque()
    frequencies = [0] * (pool + 1)
    last_seen = [-1] * (pool + 1)
    scores = {method: [] for method in METHODS}
    for t, (_, _, values) in enumerate(draws):
        actual = values[area_index]
        if t >= start:
            for method in METHODS:
                order = list(range(1, pool + 1))
                rng[method].shuffle(order)
                if method == "hot100":
                    order.sort(key=lambda n: frequencies[n], reverse=True)
                elif method == "cold100":
                    order.sort(key=lambda n: frequencies[n])
                elif method == "overdue":
                    order.sort(key=lambda n: last_seen[n])
                scores[method].append(len(set(order[:count]) & actual))
        # 预测和计分之后才加入当期开奖结果。
        for n in actual:
            frequencies[n] += 1
            last_seen[n] = t
        recent.append(actual)
        if len(recent) > 100:
            for n in recent.popleft():
                frequencies[n] -= 1
    return start, scores


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warmup", type=int, default=500, help="最低历史预热期数")
    parser.add_argument("--evaluation", type=int, default=1500, help="最近样本外期数")
    parser.add_argument("--seed", type=int, default=20261106)
    args = parser.parse_args()
    if args.warmup < 100 or args.evaluation < 2:
        parser.error("warmup 至少 100，evaluation 至少 2")

    print(f"选号方法逐期样本外回测：预热至少 {args.warmup} 期，最近 {args.evaluation} 期，随机种子 {args.seed}")
    print("理论随机期望 = 每区选号数的平方 / 号码池大小；一个方法每期生成一注，同分数随机打破平局。")
    print("近100期冷热号按出现次数降序/升序选号；最大遗漏按上次出现时间从早到晚选号。")
    print("所有选号只使用当期开奖前的历史数据。后区按其自身数据独立选号。")
    hypothesis_tests = []
    for game_index, (key, (game_name, areas)) in enumerate(GAMES.items()):
        draws = load_draws(key, areas)
        print(f"\n{game_name}：原始数据 {len(draws)} 期")
        for area_index, (area_name, pool, count, _) in enumerate(areas):
            start, scores = run_area(draws, area_index, pool, count, args.warmup,
                                     args.evaluation, args.seed + 1000 * game_index)
            n = len(scores["random"])
            split = n // 2
            expected = count * count / pool
            variance = count * (count / pool) * (1 - count / pool) * ((pool - count) / (pool - 1))
            print(f"\n  {area_name}: {draws[start][0]} 第{draws[start][1]}期 至 {draws[-1][0]} 第{draws[-1][1]}期，{n} 期；理论均值 {expected:.4f}")
            print("  方法             平均命中   比理论   前半段   后半段   至少中1个")
            for method in METHODS:
                hits = scores[method]
                mean = sum(hits) / n
                p = math.erfc(abs(mean - expected) / math.sqrt(2 * variance / n))
                if method != "random":
                    hypothesis_tests.append((p, f"{game_name}{area_name}/{LABELS[method]}"))
                print(f"  {LABELS[method]:10s}  {mean:8.4f}  {mean - expected:+7.4f}  {sum(hits[:split])/split:7.4f}  {sum(hits[split:])/(n-split):7.4f}  {sum(x > 0 for x in hits)/n:8.2%}")
    # 对所有彩种、区域及三个策略的检验统一进行 Holm 校正，控制家族错误率。
    adjusted, previous = [], 0.0
    ordered = sorted(hypothesis_tests)
    for i, (p, label) in enumerate(ordered):
        previous = max(previous, min(1.0, p * (len(ordered) - i)))
        adjusted.append((label, p, previous))
    print("\n偏离理论的双侧正态近似检验（独立均匀开奖假设；12项 Holm 校正）：")
    for label, raw, corrected in adjusted:
        print(f"  {label}: 原始 p={raw:.4f}, 校正 p={corrected:.4f}")
    print("说明：多重校正依赖事先固定的方法；本次属于探索性历史回测，并非未来表现保证。")
    print("命中号码数不是中奖率或收益率；本报告未模拟奖级、奖金、成本和规则变化。")


if __name__ == "__main__":
    main()
