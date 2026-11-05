"""一键运行：分析 → 回测 → 模拟 → 图表 → 报告。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import charts
from .backtest import BacktestResult, run_backtest
from .config import GAMES
from .data import LotteryData, ensure_dirs, load, prize_amounts
from .models import default_strategies
from .popularity import popularity_bins, popularity_regression
from .simulation import (
    coverage,
    ev_curve,
    ev_frame,
    monte_carlo_bankroll,
    rtp_series,
    system_bet_table,
    waiting_time,
)
from .tests import analyze_game

TEST_DRAWS = 1500


@dataclass
class Bundle:
    data: dict[str, LotteryData]
    features: dict[str, pd.DataFrame]
    analysis: dict[str, dict]
    backtests: dict[str, BacktestResult]
    ev: dict[str, pd.DataFrame]
    ev_curve: dict[str, pd.DataFrame]
    rtp: dict[str, pd.DataFrame]
    waiting: dict[str, pd.DataFrame]
    coverage: dict[str, pd.DataFrame]
    system_bet: dict[str, pd.DataFrame]
    mc: dict[str, dict]
    popularity: dict[str, pd.DataFrame]
    popularity_bins: dict[str, pd.DataFrame]
    figures: dict[str, str] = field(default_factory=dict)

    def kpis(self) -> dict:
        out = {}
        for key in ("ssq", "dlt"):
            data = self.data[key]
            analysis = self.analysis[key]
            bt = self.backtests[key]
            best = bt.summary.iloc[0]
            out[key] = {
                "name": data.game.name,
                "draws": data.n,
                "first_date": str(data.df["date"].iloc[0].date()),
                "last_date": str(data.df["date"].iloc[-1].date()),
                "last_issue": str(data.df["issue"].iloc[-1]),
                "front_pool": data.game.front_pool,
                "front_pick": data.game.front_pick,
                "back_pool": data.game.back_pool,
                "back_pick": data.game.back_pick,
                "total_combinations": data.game.total_combinations,
                "entropy": analysis["entropy"],
                "max_entropy": analysis["max_entropy"],
                "tests": len(analysis["results"]),
                "sig_raw": int((analysis["results"]["p_value"] < 0.05).sum()),
                "sig_fdr": int(analysis["results"]["significant_fdr"].sum()),
                "front_chi2_p": float(analysis["results"].iloc[0]["p_value"]),
                "pair_p": analysis["pair_p"],
                "bt_start": str(data.df["date"].iloc[bt.start].date()),
                "bt_end": str(data.df["date"].iloc[bt.end - 1].date()),
                "bt_draws": bt.end - bt.start,
                "bt_best": best["strategy"],
                "bt_best_hits": float(best["mean_front_hits"]),
                "bt_best_t": float(best["t_stat"]),
                "bt_random_hits": float(bt.summary.set_index("strategy").loc["random", "mean_front_hits"]),
                "bt_random_roi": float(bt.summary.set_index("strategy").loc["random", "roi"]),
                "mc_prob_profit": self.mc[key]["prob_profit"],
                "mc_median": self.mc[key]["median_payout"],
                "rtp_median": float(self.rtp[key]["rtp"].median()),
                "ev_mean": float(self.ev[key]["ev"].mean()),
            }
        return out


def build_bundle(verbose: bool = True) -> Bundle:
    ensure_dirs()
    data, features, analysis, backtests = {}, {}, {}, {}
    ev, curves, rtp, waiting, cover, system, mc = {}, {}, {}, {}, {}, {}, {}
    pop, pop_bins = {}, {}

    for key, game in GAMES.items():
        t0 = time.time()
        dataset = load(key)
        result = analyze_game(dataset)
        data[key] = dataset
        features[key] = result["features"]
        analysis[key] = result
        if verbose:
            print(f"[{game.name}] 数据 {dataset.n} 期，统计检验完成（{time.time() - t0:.1f}s）")

        t0 = time.time()
        start = max(dataset.n - TEST_DRAWS, dataset.game.front_pool * 3)
        backtests[key] = run_backtest(dataset, result["features"], default_strategies(), start=start)
        if verbose:
            print(f"[{game.name}] 回测 {start}–{dataset.n - 1} 期完成（{time.time() - t0:.1f}s）")

        ev[key] = ev_frame(dataset)
        curves[key] = ev_curve(game)
        rtp[key] = rtp_series(dataset)
        waiting[key] = waiting_time(game)
        cover[key] = coverage(game)
        system[key] = system_bet_table(game)
        mc[key] = monte_carlo_bankroll(dataset, draws=1500, simulations=4000)
        pop[key] = popularity_regression(dataset, result["features"])
        pop_bins[key] = popularity_bins(dataset, result["features"])
        if verbose:
            print(f"[{game.name}] 期望值/蒙特卡洛/流行度完成")

    return Bundle(
        data=data,
        features=features,
        analysis=analysis,
        backtests=backtests,
        ev=ev,
        ev_curve=curves,
        rtp=rtp,
        waiting=waiting,
        coverage=cover,
        system_bet=system,
        mc=mc,
        popularity=pop,
        popularity_bins=pop_bins,
    )


def main() -> None:
    t0 = time.time()
    bundle = build_bundle()

    renderers = [
        ("fig01_odds_ladder.png", charts.fig_odds),
        ("fig02_sales_pool.png", charts.fig_sales),
        ("fig03_frequency_heatmap.png", charts.fig_frequency_heatmap),
        ("fig04_residuals.png", charts.fig_residuals),
        ("fig05_omission.png", charts.fig_omission),
        ("fig06_sum_distribution.png", charts.fig_sum),
        ("fig07_shape_grid.png", charts.fig_shape),
        ("fig08_sequence.png", charts.fig_sequence),
        ("fig09_pvalues.png", charts.fig_pvalues),
        ("fig10_pairs.png", charts.fig_pairs),
        ("fig11_backtest.png", charts.fig_backtest),
        ("fig12_calibration.png", charts.fig_calibration),
        ("fig13_ev.png", charts.fig_ev),
        ("fig14_waiting.png", charts.fig_waiting),
        ("fig15_coverage.png", charts.fig_coverage),
        ("fig16_popularity.png", charts.fig_popularity),
    ]
    for name, renderer in renderers:
        path = renderer(bundle)
        bundle.figures[name] = path
        print(f"  [OK] {name}")

    from .console import write_console
    from .report import write_report

    write_console()
    write_report(bundle)
    print(f"完成，用时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
