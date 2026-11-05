"""可视化层。

统一视觉规范：米白底、深墨蓝主色、朱红/鎏金点缀；
所有图都回答一个明确问题，不做"为了好看"的装饰性图表。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter, LogLocator

from .combinatorics import (
    feature_table,
    hypergeom_pmf,
    tier_probabilities,
)
from .config import GAMES, Game, dlt_probabilities_7
from .data import FIGURE_DIR

if TYPE_CHECKING:
    from .run import Bundle

INK = "#14213D"
RED = "#C1121F"
BLUE = "#1D4E89"
GOLD = "#D99A00"
GRAY = "#8D99AE"
LIGHT = "#F6F3EC"
GREEN = "#2A6F4E"
PURPLE = "#6A4C93"

PALETTE = [INK, RED, BLUE, GOLD, GREEN, PURPLE, GRAY, "#B56576"]

plt.rcParams.update(
    {
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#D8D4CB",
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": "#5C5C5C",
        "ytick.color": "#5C5C5C",
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 10.5,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "grid.color": "#E8E4DA",
        "grid.linewidth": 0.8,
        "figure.dpi": 150,
        "savefig.dpi": 160,
        "savefig.bbox": "tight",
    }
)


def _clean(ax, grid_axis="y"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color("#C9C4B8")
    ax.spines["bottom"].set_color("#C9C4B8")
    if grid_axis:
        ax.grid(axis=grid_axis, color="#ECE8DE", linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)


def _save(fig, name: str) -> str:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURE_DIR / name
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return str(path)


def _year(game: Game, issue: np.ndarray) -> np.ndarray:
    year = issue.astype(np.int64) // 1000
    return year if game.key == "ssq" else 2000 + year


def _issue_label(game: Game, issue: int) -> str:
    return str(issue) if game.key == "ssq" else f"{issue:05d}"


# ---------------------------------------------------------------------------
# 1. 奖级概率阶梯
# ---------------------------------------------------------------------------
def fig_odds(bundle: "Bundle") -> str:
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 5.2), gridspec_kw={"wspace": 0.28})
    for ax, key in zip(axes, ("ssq", "dlt")):
        game = GAMES[key]
        if key == "ssq":
            values = tier_probabilities(game)[1:7]
        else:
            values = np.asarray(dlt_probabilities_7()[1:])
        colors = [RED if i == 0 else (GOLD if i == 1 else BLUE) for i in range(len(values))]
        bars = ax.bar(range(1, len(values) + 1), values * 100, color=colors, width=0.66)
        ax.set_yscale("log")
        ax.set_xticks(range(1, len(values) + 1))
        ax.set_xticklabels([str(i) for i in range(1, len(values) + 1)])
        ax.set_xlabel("奖级")
        ax.set_ylabel("单注中奖概率（%，对数轴）")
        ax.set_title(f"{game.name}：奖级概率阶梯", loc="left")
        _clean(ax)
        for bar, value in zip(bars, values):
            if value <= 0:
                continue
            ax.annotate(
                f"1/{1 / value:,.0f}" if value < 1e-3 else f"{value * 100:.2f}%",
                (bar.get_x() + bar.get_width() / 2, value * 100),
                textcoords="offset points",
                xytext=(0, 4),
                ha="center",
                fontsize=7.6,
                color="#4A4A4A",
            )
        ax.set_ylim(values.min() * 40, values.max() * 25)

    fig.suptitle(
        "一注 2 元：你在为什么买单",
        x=0.06,
        ha="left",
        fontsize=16,
        fontweight="bold",
        y=1.03,
    )
    fig.text(
        0.06,
        0.955,
        "一等奖概率：双色球 1/17,721,088；大乐透 1/21,425,712。"
        "作为参照，连续抛 24 次硬币全为正面的概率约为 1/16,777,216。",
        fontsize=9.5,
        color="#5C5C5C",
    )
    return _save(fig, "fig01_odds_ladder.png")


# ---------------------------------------------------------------------------
# 2. 销量与奖池
# ---------------------------------------------------------------------------
def fig_sales(bundle: "Bundle") -> str:
    fig, axes = plt.subplots(2, 1, figsize=(12.4, 7.2), sharex=False)
    for ax, key, color in zip(axes, ("ssq", "dlt"), (RED, BLUE)):
        data = bundle.data[key]
        df = data.df.dropna(subset=["sales"]).copy()
        df["year"] = _year(data.game, df["issue"].to_numpy())
        yearly = df.groupby("year").agg(sales=("sales", "sum"), pool=("pool", "median")).reset_index()
        ax.bar(yearly["year"], yearly["sales"] / 1e8, color=color, alpha=0.85, width=0.7, label="年销量（亿元）")
        ax.set_ylabel("年销量（亿元）", color=color)
        ax.tick_params(axis="y", colors=color)
        _clean(ax)
        ax2 = ax.twinx()
        ax2.plot(yearly["year"], yearly["pool"] / 1e8, color=GOLD, linewidth=2, marker="o", markersize=3, label="奖池中位数（亿元）")
        ax2.set_ylabel("奖池中位数（亿元）", color=GOLD)
        ax2.tick_params(axis="y", colors=GOLD)
        ax2.spines["top"].set_visible(False)
        ax2.grid(False)
        ax.set_title(f"{data.game.name}：销量与奖池（{int(yearly.year.min())}–{int(yearly.year.max())}）", loc="left")
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc="upper left", ncol=2)
    fig.suptitle("一个年销数百亿的市场", x=0.06, ha="left", fontsize=16, fontweight="bold", y=1.02)
    fig.text(0.06, 0.965, "销量决定奖池，奖池决定头奖，但都不改变单注中奖概率。", fontsize=9.5, color="#5C5C5C")
    fig.tight_layout()
    return _save(fig, "fig02_sales_pool.png")


# ---------------------------------------------------------------------------
# 3. 频率热力图
# ---------------------------------------------------------------------------
def fig_frequency_heatmap(bundle: "Bundle") -> str:
    fig, axes = plt.subplots(2, 2, figsize=(14.0, 9.2), gridspec_kw={"wspace": 0.16, "hspace": 0.36})
    panels = [
        ("ssq", "front", "红球（1–33）"),
        ("ssq", "back", "蓝球（1–16）"),
        ("dlt", "front", "前区（1–35）"),
        ("dlt", "back", "后区（1–12）"),
    ]
    for ax, (key, area, title) in zip(axes.ravel(), panels):
        data = bundle.data[key]
        matrix = data.front if area == "front" else data.back
        years = _year(data.game, data.df["issue"].to_numpy())
        unique_years = np.unique(years)
        counts = np.zeros((len(unique_years), matrix.shape[1]))
        for i, year in enumerate(unique_years):
            counts[i] = matrix[years == year].sum(axis=0)
        draws = np.array([(years == year).sum() for year in unique_years])[:, None]
        rate = matrix.sum() / (matrix.shape[0] * matrix.shape[1])
        expected = draws * rate
        z = (counts - expected) / np.sqrt(expected * (1 - rate))
        im = ax.imshow(z.T, aspect="auto", cmap="RdBu_r", vmin=-3, vmax=3, origin="lower")
        step_y = 1 if matrix.shape[1] <= 16 else 2
        ax.set_yticks(range(0, matrix.shape[1], step_y))
        ax.set_yticklabels(range(1, matrix.shape[1] + 1, step_y), fontsize=7.2)
        step = 2
        ax.set_xticks(range(0, len(unique_years), step))
        ax.set_xticklabels(unique_years[::step], rotation=0, fontsize=7.8)
        ax.set_title(title, loc="left", fontsize=11)
        ax.grid(False)
        if key == "dlt" and area == "front":
            idx = list(unique_years).index(2014)
            ax.axvline(idx - 0.5, color=INK, linewidth=1.4, linestyle=(0, (4, 3)))
            ax.text(
                idx + 0.35,
                matrix.shape[1] * 0.55,
                "2014 规则调整",
                fontsize=7.8,
                color=INK,
                rotation=90,
                va="center",
                bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="none", alpha=0.75),
            )
    cbar = fig.colorbar(im, ax=axes, fraction=0.018, pad=0.012)
    cbar.set_label("标准化残差 z", fontsize=9)
    fig.suptitle("号码出现频率的年度漂移", x=0.06, ha="left", fontsize=16, fontweight="bold", y=0.99)
    fig.text(
        0.06,
        0.945,
        "颜色 = 当年出现次数相对全样本平均的标准化残差。大乐透前区在 2007–2013 年明显偏向大号，2014 年后恢复均匀——"
        "这是数据中最强的结构性信号，也是任何'热号模型'最容易踩的坑。",
        fontsize=9.2,
        color="#5C5C5C",
    )
    return _save(fig, "fig03_frequency_heatmap.png")


# ---------------------------------------------------------------------------
# 4. 均匀性残差
# ---------------------------------------------------------------------------
def fig_residuals(bundle: "Bundle") -> str:
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.8))
    for ax, key in zip(axes, ("ssq", "dlt")):
        analysis = bundle.analysis[key]
        z = analysis["front_residuals"]
        colors = [RED if abs(v) > 2 else BLUE for v in z]
        ax.bar(np.arange(1, len(z) + 1), z, color=colors, width=0.72)
        ax.axhline(0, color=INK, linewidth=0.8)
        for level, style in ((2, (0, (3, 3))), (-2, (0, (3, 3)))):
            ax.axhline(level, color=GRAY, linewidth=1, linestyle=style)
        ax.set_xlabel("号码")
        ax.set_ylabel("标准化残差 (O−E)/√E")
        ax.set_title(f"{GAMES[key].name}：号码频数残差", loc="left")
        ax.set_xticks(range(1, len(z) + 1, 3))
        _clean(ax)
        ax.text(
            0.99,
            0.94,
            "虚线为 ±2σ\n|z|>2 的号码用红色标出",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=8,
            color="#5C5C5C",
        )
    fig.suptitle("公平性检验：每个号码偏离期望有多远", x=0.06, ha="left", fontsize=15, fontweight="bold", y=1.02)
    fig.tight_layout()
    return _save(fig, "fig04_residuals.png")


# ---------------------------------------------------------------------------
# 5. 遗漏值
# ---------------------------------------------------------------------------
def fig_omission(bundle: "Bundle") -> str:
    fig, axes = plt.subplots(1, 2, figsize=(13.2, 4.9), gridspec_kw={"width_ratios": [1.35, 1]})
    ax = axes[0]
    width = 0.38
    for offset, key, color, label in ((-width / 2, "ssq", RED, "双色球红球"), (width / 2, "dlt", BLUE, "大乐透前区")):
        data = bundle.data[key]
        omission = bundle.analysis[key]["current_omission"]
        ax.bar(np.arange(1, len(omission) + 1) + offset, omission, width=width, color=color, label=label, alpha=0.9)
    ax.set_xlabel("号码")
    ax.set_ylabel("当前遗漏（期）")
    ax.set_title("当前遗漏值：谁最久没出现", loc="left")
    ax.legend(loc="upper left")
    _clean(ax)

    ax = axes[1]
    for key, color, label in (("ssq", RED, "双色球"), ("dlt", BLUE, "大乐透")):
        data = bundle.data[key]
        rate = data.game.front_rate
        gaps = []
        for j in range(data.front.shape[1]):
            idx = np.flatnonzero(data.front[:, j])
            gaps.extend((np.diff(idx) - 1).tolist())
        gaps = np.array(gaps)
        max_gap = 30
        hist = np.bincount(np.clip(gaps, 0, max_gap), minlength=max_gap + 1).astype(float)
        hist /= hist.sum()
        ax.plot(np.arange(max_gap + 1), hist, color=color, linewidth=1.8, label=f"{label}实测")
        theory = (1 - rate) ** np.arange(max_gap + 1) * rate
        theory[-1] = 1 - theory[:-1].sum()
        ax.plot(np.arange(max_gap + 1), theory, color=color, linewidth=1.4, linestyle=(0, (3, 2)), alpha=0.75, label=f"{label}几何分布")
    ax.set_yscale("log")
    ax.set_xlabel("连续未出现期数")
    ax.set_ylabel("频率（对数轴）")
    ax.set_title("遗漏长度分布 vs 几何分布", loc="left")
    ax.legend(fontsize=8)
    _clean(ax, "y")
    fig.suptitle("遗漏不是'该出了'的理由", x=0.06, ha="left", fontsize=15, fontweight="bold", y=1.02)
    fig.tight_layout()
    return _save(fig, "fig05_omission.png")


# ---------------------------------------------------------------------------
# 6. 和值分布
# ---------------------------------------------------------------------------
def fig_sum(bundle: "Bundle") -> str:
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.8))
    for ax, key in zip(axes, ("ssq", "dlt")):
        data = bundle.data[key]
        features = bundle.features[key]
        table = feature_table(data.game)
        values = np.array(sorted(int(k) for k in table.counts["sum"]))
        probs = np.array([table.counts["sum"][str(v)] / table.total for v in values])
        ax.bar(values, probs * 100, width=1.0, color="#D9D4C7", label="精确组合分布")
        observed = features["sum"].value_counts().sort_index()
        ax.plot(observed.index, observed.values / observed.sum() * 100, color=RED, linewidth=1.6, label="实际开奖")
        ax.set_xlabel("和值")
        ax.set_ylabel("概率（%）")
        ax.set_title(f"{GAMES[key].name}：和值分布", loc="left")
        ax.legend(loc="upper left")
        _clean(ax)
        mean = float(np.average(values, weights=probs))
        ax.axvline(mean, color=BLUE, linewidth=1, linestyle=(0, (4, 3)))
        ax.text(mean, ax.get_ylim()[1] * 0.9, f" 理论均值 {mean:.1f}", color=BLUE, fontsize=8.4)
    fig.suptitle("和值：由组合数决定的钟形曲线", x=0.06, ha="left", fontsize=15, fontweight="bold", y=1.02)
    fig.tight_layout()
    return _save(fig, "fig06_sum_distribution.png")


# ---------------------------------------------------------------------------
# 7. 形态分布网格
# ---------------------------------------------------------------------------
def fig_shape(bundle: "Bundle") -> str:
    specs = [("odd", "奇数个数"), ("big", "大号个数"), ("consecutive", "连号组数"), ("ac", "AC 值")]
    fig, axes = plt.subplots(2, 4, figsize=(14.2, 6.4), gridspec_kw={"hspace": 0.55, "wspace": 0.32})
    for row, key in enumerate(("ssq", "dlt")):
        data = bundle.data[key]
        features = bundle.features[key]
        table = feature_table(data.game)
        for col, (feature, label) in enumerate(specs):
            ax = axes[row, col]
            values = np.array(sorted(int(k) for k in table.counts[feature]))
            probs = np.array([table.counts[feature][str(v)] / table.total for v in values])
            ax.bar(values, probs * 100, color="#DCD7CA", width=0.8, label="理论")
            obs = features[feature].value_counts().reindex(values, fill_value=0)
            ax.plot(values, obs.values / obs.sum() * 100, color=RED if key == "ssq" else BLUE, marker="o", markersize=3, linewidth=1.4, label="实测")
            ax.set_title(f"{GAMES[key].name} · {label}", loc="left", fontsize=9.8)
            ax.set_xlabel(label)
            ax.set_ylabel("概率（%）")
            _clean(ax)
            if row == 0 and col == 0:
                ax.legend(fontsize=7.6, loc="upper right")
    fig.suptitle("形态分布：每一种'规律'都有精确的理论基准", x=0.06, ha="left", fontsize=15, fontweight="bold", y=1.0)
    fig.text(0.06, 0.945, "灰色为 C(n,k) 全枚举得到的精确分布，折线为 2003 年以来的真实开奖。", fontsize=9, color="#5C5C5C")
    return _save(fig, "fig07_shape_grid.png")


# ---------------------------------------------------------------------------
# 8. 序列与自相关
# ---------------------------------------------------------------------------
def _acf(series: np.ndarray, lags: int = 30) -> np.ndarray:
    x = series - series.mean()
    denom = np.dot(x, x)
    return np.array([np.dot(x[:-k], x[k:]) / denom for k in range(1, lags + 1)])


def fig_sequence(bundle: "Bundle") -> str:
    fig = plt.figure(figsize=(13.0, 6.8))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.5, 1], width_ratios=[1.6, 1], hspace=0.45, wspace=0.22)
    for row, key in enumerate(("ssq", "dlt")):
        data = bundle.data[key]
        features = bundle.features[key]
        ax = fig.add_subplot(gs[row, 0])
        sums = features["sum"].to_numpy()
        ax.plot(np.arange(len(sums)), sums, color=GRAY, linewidth=0.5, alpha=0.7, label="和值")
        roll = pd.Series(sums).rolling(100, min_periods=50).mean()
        ax.plot(np.arange(len(sums)), roll, color=RED if key == "ssq" else BLUE, linewidth=2, label="100 期滚动均值")
        sum_values, sum_probs = feature_table(data.game).pmf("sum")
        theoretical = float(np.average(sum_values, weights=sum_probs))
        ax.axhline(theoretical, color=INK, linewidth=1, linestyle=(0, (4, 3)), label="理论均值")
        if key == "dlt":
            years = _year(data.game, data.df["issue"].to_numpy())
            idx = int(np.argmax(years >= 2014))
            ax.axvline(idx, color=GOLD, linewidth=1.6, linestyle=(0, (5, 3)))
            ax.text(idx + 25, ax.get_ylim()[1] * 0.92, "2014 断点", color=GOLD, fontsize=8.6)
        ax.set_title(f"{data.game.name}：和值序列与趋势", loc="left", fontsize=10.5)
        ax.set_xlabel("期序")
        ax.set_ylabel("和值")
        ax.legend(fontsize=7.6, loc="lower left", ncol=3)
        _clean(ax)

        ax2 = fig.add_subplot(gs[row, 1])
        acf = _acf(sums, 30)
        ax2.bar(np.arange(1, 31), acf, color=INK, width=0.7)
        band = 1.96 / np.sqrt(len(sums))
        ax2.axhspan(-band, band, color=GOLD, alpha=0.18, label="95% 置信带")
        ax2.axhline(0, color=INK, linewidth=0.7)
        ax2.set_title("和值自相关（ACF）", loc="left", fontsize=10.5)
        ax2.set_xlabel("滞后阶数")
        ax2.set_ylabel("自相关系数")
        _clean(ax2)
        ax2.legend(fontsize=7.6, loc="upper right")
    fig.suptitle("独立性：上一期能不能告诉你下一期", x=0.06, ha="left", fontsize=15, fontweight="bold", y=0.99)
    return _save(fig, "fig08_sequence.png")


# ---------------------------------------------------------------------------
# 9. p 值 QQ 图
# ---------------------------------------------------------------------------
def fig_pvalues(bundle: "Bundle") -> str:
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 5.0))
    for ax, key in zip(axes, ("ssq", "dlt")):
        frame = bundle.analysis[key]["results"]
        p = np.sort(frame["p_value"].to_numpy())
        m = len(p)
        expected = (np.arange(1, m + 1) - 0.5) / m
        ax.scatter(expected, p, s=36, color=RED if key == "ssq" else BLUE, zorder=3)
        ax.plot([0, 1], [0, 1], color=GRAY, linewidth=1, linestyle=(0, (3, 3)))
        ax.axhline(0.05, color=GOLD, linewidth=1)
        ax.set_xlabel("Uniform(0,1) 理论分位数")
        ax.set_ylabel("实测 p 值")
        ax.set_title(f"{GAMES[key].name}：{m} 项检验的 p 值", loc="left")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        _clean(ax, None)
        ax.text(0.02, 0.06, "点落在对角线上 = 与随机不可区分", fontsize=8, color="#5C5C5C")
    fig.suptitle("多重检验：随机也会制造'显著'", x=0.06, ha="left", fontsize=15, fontweight="bold", y=1.02)
    fig.tight_layout()
    return _save(fig, "fig09_pvalues.png")


# ---------------------------------------------------------------------------
# 10. 号码对共现
# ---------------------------------------------------------------------------
def fig_pairs(bundle: "Bundle") -> str:
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.6), gridspec_kw={"wspace": 0.18})
    for ax, key in zip(axes, ("ssq", "dlt")):
        analysis = bundle.analysis[key]
        z = analysis["pair_z"].copy()
        np.fill_diagonal(z, np.nan)
        im = ax.imshow(z, cmap="RdBu_r", vmin=-4, vmax=4)
        ax.set_title(f"{GAMES[key].name}：号码对共现 z 值", loc="left")
        ax.set_xticks(range(0, z.shape[0], 3))
        ax.set_xticklabels(range(1, z.shape[0] + 1, 3), fontsize=7)
        ax.set_yticks(range(0, z.shape[0], 3))
        ax.set_yticklabels(range(1, z.shape[0] + 1, 3), fontsize=7)
        ax.grid(False)
        ax.text(
            0.02,
            -0.12,
            f"蒙特卡洛 p = {analysis['pair_p']:.3f}；|z|>3 的号码对 "
            f"{int((np.abs(z[np.isfinite(z)]) > 3).sum() / 2)} 对（共 {int(np.isfinite(z).sum() / 2)} 对）",
            transform=ax.transAxes,
            fontsize=8.2,
            color="#5C5C5C",
        )
    cbar = fig.colorbar(im, ax=axes, fraction=0.02, pad=0.012)
    cbar.set_label("共现频数标准化残差", fontsize=9)
    fig.suptitle("号码之间的'关系'：528 对号码的共现检验", x=0.06, ha="left", fontsize=15, fontweight="bold", y=1.02)
    return _save(fig, "fig10_pairs.png")


# ---------------------------------------------------------------------------
# 11. 回测结果
# ---------------------------------------------------------------------------
def fig_backtest(bundle: "Bundle") -> str:
    fig = plt.figure(figsize=(13.2, 6.2))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.15, 1], wspace=0.25)
    ax = fig.add_subplot(gs[0, 0])
    offsets = {"ssq": -0.18, "dlt": 0.18}
    order = (
        bundle.backtests["ssq"].summary.sort_values("mean_front_hits")["strategy"].tolist()
    )
    for key, color in (("ssq", RED), ("dlt", BLUE)):
        summary = bundle.backtests[key].summary.set_index("strategy").loc[order]
        y = np.arange(len(order)) + offsets[key]
        ratio = summary["mean_front_hits"] / summary["theoretical_hits"]
        error = 1.96 * summary["se"] / summary["theoretical_hits"]
        ax.errorbar(
            ratio,
            y,
            xerr=error,
            fmt="o",
            color=color,
            markersize=6,
            capsize=3,
            label=f"{GAMES[key].name}（{bundle.backtests[key].end - bundle.backtests[key].start} 期）",
        )
    ax.axvline(1.0, color=INK, linewidth=1.2, linestyle=(0, (4, 3)))
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(
        [
            {"hot_30": "热号 30 期", "hot_100": "热号 100 期", "bayes": "贝叶斯后验", "markov": "马尔可夫",
             "cold": "冷号/遗漏", "trend_200": "趋势 200 期", "random": "随机基准", "balanced": "形态均衡"}.get(s, s)
            for s in order
        ],
        fontsize=8.6,
    )
    ax.set_xlabel("平均命中数 / 理论期望（95% CI；1.0 = 与随机无异）")
    ax.set_title("各策略的相对表现", loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, fontsize=8.4)
    _clean(ax, "x")

    ax2 = fig.add_subplot(gs[0, 1])
    key = "ssq"
    dist = bundle.backtests[key].hit_distribution
    theory = dist[dist.strategy == "random"].set_index("hits")["theory"]
    ax2.bar(theory.index - 0.2, theory.values * 100, width=0.4, color="#D9D4C7", label="超几何理论")
    observed = dist[dist.strategy == "hot_30"].set_index("hits")["observed"]
    ax2.bar(observed.index + 0.2, observed.values * 100, width=0.4, color=RED, alpha=0.85, label="热号策略实测")
    ax2.set_xlabel("红球命中个数")
    ax2.set_ylabel("概率（%）")
    ax2.set_title("双色球：命中数分布", loc="left")
    ax2.set_yscale("log")
    ax2.legend(fontsize=8.4)
    _clean(ax2)
    fig.suptitle("回测：七种选号哲学与一枚硬币", x=0.06, ha="left", fontsize=15, fontweight="bold", y=1.0)
    return _save(fig, "fig11_backtest.png")


# ---------------------------------------------------------------------------
# 12. 概率校准
# ---------------------------------------------------------------------------
def fig_calibration(bundle: "Bundle") -> str:
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.8), gridspec_kw={"wspace": 0.26})
    ax = axes[0]
    for i, (key, color) in enumerate((("ssq", RED), ("dlt", BLUE))):
        calib = bundle.backtests[key].calibration
        for j, strategy in enumerate(["bayes", "markov", "hot_100"]):
            part = calib[calib.strategy == strategy].sort_values("predicted")
            if part.empty:
                continue
            ax.plot(
                part["predicted"],
                part["observed"],
                marker="o",
                markersize=3,
                linewidth=1.2,
                color=color,
                alpha=0.45 + 0.2 * j,
                label=f"{GAMES[key].name}·{strategy}",
            )
    ax.plot([0, 0.5], [0, 0.5], color=GRAY, linestyle=(0, (3, 3)), linewidth=1)
    ax.set_xlabel("模型预测概率")
    ax.set_ylabel("实际出现频率")
    ax.set_title("校准曲线", loc="left")
    ax.legend(fontsize=7.2, ncol=2, loc="upper left")
    _clean(ax, None)

    ax2 = axes[1]
    keys = ["ssq", "dlt"]
    strategies = bundle.backtests["ssq"].logloss["strategy"].tolist()
    width = 0.38
    for i, key in enumerate(keys):
        logloss = bundle.backtests[key].logloss.set_index("strategy").loc[strategies]
        ax2.barh(
            np.arange(len(strategies)) + (i - 0.5) * width,
            logloss["lift"],
            height=width,
            color=RED if key == "ssq" else BLUE,
            alpha=0.85,
            label=GAMES[key].name,
        )
    ax2.axvline(0, color=INK, linewidth=0.9)
    ax2.set_yticks(range(len(strategies)))
    ax2.set_yticklabels(strategies, fontsize=8.6)
    ax2.set_xlabel("相对均匀分布的对数损失改善（>0 才有预测力）")
    ax2.set_title("预测力检验：对数损失", loc="left")
    ax2.legend(fontsize=8.4)
    _clean(ax2, "x")
    fig.suptitle("别问'准不准'，先问'比随机好多少'", x=0.06, ha="left", fontsize=15, fontweight="bold", y=1.02)
    fig.tight_layout()
    return _save(fig, "fig12_calibration.png")


# ---------------------------------------------------------------------------
# 13. 期望值
# ---------------------------------------------------------------------------
def fig_ev(bundle: "Bundle") -> str:
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.8), gridspec_kw={"wspace": 0.26})
    ax = axes[0]
    for key, color in (("ssq", RED), ("dlt", BLUE)):
        curve = bundle.ev_curve[key]
        ax.plot(curve["jackpot"] / 1e4, curve["ev"], color=color, linewidth=2, label=GAMES[key].name)
        max_jackpot = float(bundle.data[key].df["p1_amount"].max())
        ax.axvline(max_jackpot / 1e4, color=color, linewidth=1, linestyle=(0, (2, 3)), alpha=0.6)
        ax.annotate(
            f"{GAMES[key].name}历史最高\n{max_jackpot / 1e4:,.0f} 万",
            (max_jackpot / 1e4, 2.22 if key == "ssq" else 0.85),
            fontsize=7.2,
            color=color,
            ha="center",
            va="center",
        )
    ax.axhline(2.0, color=INK, linewidth=1.2, linestyle=(0, (4, 3)))
    ax.text(300, 2.06, "票价 2 元", fontsize=8.6, color=INK)
    ax.set_xlabel("一等奖单注奖金（万元）")
    ax.set_ylabel("单注期望回报（元）")
    ax.set_title("期望回报：要追平票价，头奖需约 2500 万", loc="left")
    ax.legend(fontsize=8.6, loc="lower right")
    _clean(ax)

    ax2 = axes[1]
    for key, color in (("ssq", RED), ("dlt", BLUE)):
        ev = bundle.ev[key]
        rolling = ev.set_index("date")["rtp"].rolling(100, min_periods=30).mean()
        ax2.plot(ev["date"], rolling, color=color, linewidth=1.6, label=GAMES[key].name)
    ax2.axhline(0.5, color=INK, linewidth=1, linestyle=(0, (4, 3)))
    ax2.text(pd.Timestamp("2022-06-01"), 0.503, "50% 理论返奖率", fontsize=7.8, color=INK, va="bottom")
    ax2.set_ylabel("100 期滚动返奖率")
    ax2.set_title("历史返奖率（按当期奖金计算）", loc="left")
    ax2.legend(fontsize=8.6)
    _clean(ax2)
    fig.suptitle("期望值：每一注的数学价格是 1 元左右，标价 2 元", x=0.06, ha="left", fontsize=15, fontweight="bold", y=1.02)
    fig.tight_layout()
    return _save(fig, "fig13_ev.png")


# ---------------------------------------------------------------------------
# 14. 等待时间与蒙特卡洛
# ---------------------------------------------------------------------------
def fig_waiting(bundle: "Bundle") -> str:
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.9), gridspec_kw={"wspace": 0.28})
    ax = axes[0]
    years_grid = np.logspace(0, 6, 400)
    for key, color in (("ssq", RED), ("dlt", BLUE)):
        game = GAMES[key]
        p = game.jackpot_odds
        draws = years_grid * 150
        prob = 1 - (1 - p) ** draws
        ax.plot(years_grid, prob, color=color, linewidth=2, label=game.name)
    ssq_p = GAMES["ssq"].jackpot_odds
    for q, text_xy in ((0.5, (2.2e5, 0.30)), (0.95, (2.2e5, 0.62))):
        years = np.log(1 - q) / np.log(1 - ssq_p) / 150
        ax.plot([years], [q], marker="o", markersize=6, color=RED, zorder=5)
        ax.annotate(
            f"{'50%' if q == 0.5 else '95%'} 需要 {years / 1e4:.1f} 万年",
            (years, q),
            xytext=text_xy,
            textcoords="data",
            fontsize=8.4,
            color=RED,
            arrowprops=dict(arrowstyle="-", color=RED, linewidth=0.8, shrinkA=0, shrinkB=4),
            va="center",
        )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(1, 1e6)
    ax.set_ylim(1e-8, 1.5)
    ax.set_xlabel("连续购买年数（对数轴）")
    ax.set_ylabel("至少中一次头奖的概率（对数轴）")
    ax.set_title("等待头奖：时间尺度以万年计", loc="left")
    ax.legend(fontsize=8.6, loc="lower right")
    _clean(ax, None)
    ax.grid(True, which="major", color="#ECE8DE", linewidth=0.8)

    ax2 = axes[1]
    bins = np.logspace(2, 6.6, 90)
    for key, color in (("ssq", RED), ("dlt", BLUE)):
        mc = bundle.mc[key]
        ax2.hist(mc["total_payout"], bins=bins, color=color, alpha=0.5, label=GAMES[key].name)
    ax2.axvline(1500 * 2, color=INK, linewidth=1.2, linestyle=(0, (4, 3)))
    top = ax2.get_ylim()[1]
    ax2.text(1500 * 2 * 1.05, top * 0.9, "15 年投入 3000 元", fontsize=8.2, color=INK)
    ax2.set_xscale("log")
    ax2.set_xlabel("15 年总回报（元，对数轴）")
    ax2.set_ylabel("模拟次数")
    ax2.set_title("蒙特卡洛：每期 1 注、连买 15 年", loc="left")
    ax2.legend(fontsize=8.6, loc="upper right")
    _clean(ax2)
    ssq_mc = bundle.mc["ssq"]
    ax2.text(
        0.03,
        0.72,
        f"双色球中位回报 {ssq_mc['median_payout']:.0f} 元\n"
        f"盈利概率 {ssq_mc['prob_profit'] * 100:.2f}%\n"
        f"15 年中头奖概率 {ssq_mc['prob_any_jackpot'] * 100:.4f}%",
        transform=ax2.transAxes,
        fontsize=8.2,
        color="#4A4A4A",
        va="top",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#E6E0D2", alpha=0.85),
    )
    fig.suptitle("把不确定性算清楚", x=0.06, ha="left", fontsize=15, fontweight="bold", y=1.02)
    fig.subplots_adjust(top=0.84, bottom=0.16, left=0.07, right=0.98)
    return _save(fig, "fig14_waiting.png")


# ---------------------------------------------------------------------------
# 15. 覆盖
# ---------------------------------------------------------------------------
def fig_coverage(bundle: "Bundle") -> str:
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.9), gridspec_kw={"wspace": 0.26})
    ax = axes[0]
    for key, color in (("ssq", RED), ("dlt", BLUE)):
        cov = bundle.coverage[key]
        ax.plot(cov["cost"], cov["prob"], color=color, linewidth=2, label=GAMES[key].name)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("投入金额（元，对数轴）")
    ax.set_ylabel("至少中一次头奖的概率")
    ax.set_title("买得越多，确定性越高——但成本是线性增长", loc="left")
    for cost, label in ((2, "1 注"), (2000, "1000 注"), (2_000_000, "100 万注")):
        ax.axvline(cost, color=GRAY, linewidth=0.7, linestyle=(0, (2, 3)))
        ax.text(cost * 1.1, 1e-7, label, fontsize=7.6, color="#5C5C5C", rotation=90, va="bottom")
    ax.legend(fontsize=8.6, loc="lower right")
    _clean(ax, None)
    ax.grid(True, which="major", color="#ECE8DE", linewidth=0.8)

    ax2 = axes[1]
    table = bundle.system_bet["ssq"]
    pivot = table.pivot_table(index="front_picked", columns="back_picked", values="cost", aggfunc="max")
    im = ax2.imshow(np.log10(pivot.to_numpy()), cmap="YlOrRd", aspect="auto")
    ax2.set_xticks(range(pivot.shape[1]))
    ax2.set_xticklabels(pivot.columns)
    ax2.set_yticks(range(pivot.shape[0]))
    ax2.set_yticklabels(pivot.index)
    ax2.set_xlabel("蓝球复选个数")
    ax2.set_ylabel("红球复选个数")
    ax2.set_title("双色球复式投注金额（log10 元）", loc="left")
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value = pivot.to_numpy()[i, j]
            ax2.text(j, i, f"{value:,.0f}", ha="center", va="center", fontsize=6.6, color="black")
    ax2.grid(False)
    fig.suptitle("复式与胆拖：用钱买覆盖率", x=0.06, ha="left", fontsize=15, fontweight="bold", y=1.02)
    fig.tight_layout()
    return _save(fig, "fig15_coverage.png")


# ---------------------------------------------------------------------------
# 16. 流行度与奖金分摊
# ---------------------------------------------------------------------------
def fig_popularity(bundle: "Bundle") -> str:
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.9), gridspec_kw={"wspace": 0.3})
    ax = axes[0]
    for key, color in (("ssq", RED), ("dlt", BLUE)):
        bins = bundle.popularity_bins[key]
        ax.plot(bins["sum_mean"], bins["winners_per_million"], marker="o", color=color, linewidth=1.8, label=GAMES[key].name)
    ax.set_xlabel("当期号码和值")
    ax.set_ylabel("每百万元销量的一等奖注数（中位数）")
    ax.set_title("和值越低（越像生日号），中奖人数越多", loc="left")
    ax.legend(fontsize=8.6)
    _clean(ax)

    ax2 = axes[1]
    table = bundle.popularity["ssq"]
    part = table[table.variable != "all_even"].iloc[::-1]
    colors = [RED if q < 0.05 else GRAY for q in part["q_value"]]
    ax2.barh(range(len(part)), part["effect_pct"], color=colors, alpha=0.88)
    ax2.set_yticks(range(len(part)))
    ax2.set_yticklabels(part["label"], fontsize=8.6)
    ax2.axvline(0, color=INK, linewidth=0.8)
    ax2.set_xlabel("一等奖注数变化（%，每变动一个标准差）")
    ax2.set_title("控制销量后的“流行度”效应", loc="left")
    _clean(ax2, "x")
    fig.suptitle("选号改变不了概率，但能改变分到多少钱", x=0.06, ha="left", fontsize=15, fontweight="bold", y=1.02)
    fig.text(
        0.06,
        0.94,
        "红色 = FDR q<0.05。样本：双色球 3523 期；因变量 log(1+一等奖注数)，每个形态单独回归并控制 log(销量)、log(奖池) 与时间趋势。",
        fontsize=8.2,
        color="#5C5C5C",
    )
    fig.tight_layout()
    return _save(fig, "fig16_popularity.png")
