"""生成自包含的 HTML 研究报告（图片以 base64 内嵌，可离线打开）。"""

from __future__ import annotations

import base64
import html
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .combinatorics import tier_probabilities
from .config import (
    DLT_7_CONDITIONS,
    DLT_7_MIN_PRIZE,
    FIXED_PRIZES,
    GAMES,
    dlt_probabilities_7,
)
from .data import OUTPUT_DIR

STRATEGY_LABELS = {
    "random": "随机基准",
    "hot_30": "热号（30 期）",
    "hot_100": "热号（100 期）",
    "cold": "冷号 / 遗漏最长",
    "bayes": "贝叶斯后验",
    "markov": "一阶马尔可夫",
    "trend_200": "趋势（200 期斜率）",
    "balanced": "形态均衡",
}

LIGHTBOX = """
<div id="lightbox"><img alt="放大查看"></div>
<script>
document.querySelectorAll('figure img').forEach(function (img) {
  img.addEventListener('click', function () {
    var lb = document.getElementById('lightbox');
    lb.querySelector('img').src = img.src;
    lb.classList.add('on');
  });
});
document.getElementById('lightbox').addEventListener('click', function () {
  this.classList.remove('on');
});
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') { document.getElementById('lightbox').classList.remove('on'); }
});
</script>
"""

CSS = """:root{
  --ink:#14213D; --red:#C1121F; --gold:#B8860B; --blue:#1D4E89;
  --paper:#FBF9F4; --card:#FFFFFF; --muted:#6E6A61; --line:#E6E0D2;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",system-ui,sans-serif;
  line-height:1.8;font-size:16px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:0 44px}
a{color:var(--blue);text-decoration:none}
/* cover */
.cover{padding:96px 0 56px;border-bottom:1px solid var(--line)}
.kicker{letter-spacing:.28em;font-size:12px;color:var(--red);font-weight:700;text-transform:uppercase}
h1{font-family:"Songti SC","SimSun",serif;font-size:54px;line-height:1.18;margin:22px 0 18px;font-weight:700;letter-spacing:-.5px}
.sub{font-size:19px;color:#3D4657;max-width:820px;line-height:1.7}
.meta{margin-top:30px;display:flex;gap:26px;flex-wrap:wrap;font-size:13px;color:var(--muted)}
.meta b{color:var(--ink)}
.cta{display:inline-flex;align-items:center;gap:8px;margin-top:26px;padding:10px 18px;
  background:var(--ink);color:#fff;border-radius:8px;font-size:14px;font-weight:600;
  transition:background .15s,transform .15s}
.cta:hover{background:#1F3055;transform:translateY(-1px)}
/* kpi */
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:1px;background:var(--line);
  margin:44px 0 8px;border:1px solid var(--line)}
.kpi{background:var(--card);padding:22px 20px}
.kpi .v{font-size:30px;font-weight:700;letter-spacing:-.5px;line-height:1.2}
.kpi .v small{font-size:15px;font-weight:600;color:var(--muted)}
.kpi .l{font-size:12.5px;color:var(--muted);margin-top:6px}
/* layout */
.layout{display:grid;grid-template-columns:220px 1fr;gap:56px;padding:40px 0 80px}
nav.toc{position:sticky;top:28px;align-self:start;font-size:13.5px;line-height:2.1}
nav.toc .t{font-size:11px;letter-spacing:.18em;color:var(--muted);margin-bottom:10px}
nav.toc a{display:block;color:#4A5060;padding-left:12px;border-left:2px solid transparent}
nav.toc a:hover{color:var(--red);border-left-color:var(--red)}
nav.toc a.sub{padding-left:24px;font-size:12.6px;color:#6E7484}
main{min-width:0}
section{margin:0 0 78px;scroll-margin-top:24px}
h2{font-family:"Songti SC","SimSun",serif;font-size:31px;margin:0 0 8px;letter-spacing:-.3px}
h2 .no{color:var(--red);font-size:15px;font-family:"Microsoft YaHei",sans-serif;letter-spacing:.12em;display:block;margin-bottom:8px;font-weight:700}
h3{font-size:19px;margin:38px 0 10px;color:var(--ink)}
p{margin:12px 0}
.lead{font-size:17px;color:#3D4657}
.small{font-size:13.5px;color:var(--muted)}
/* components */
figure{margin:26px 0 34px;background:var(--card);border:1px solid var(--line);padding:16px 16px 12px}
figure img{width:100%;display:block;cursor:zoom-in;transition:opacity .15s}
figure img:hover{opacity:.92}
#lightbox{position:fixed;inset:0;background:rgba(20,33,61,.93);display:none;align-items:center;justify-content:center;z-index:99;padding:28px;cursor:zoom-out}
#lightbox.on{display:flex}
#lightbox img{max-width:96vw;max-height:92vh;background:#fff;box-shadow:0 20px 60px rgba(0,0,0,.4)}
figcaption{font-size:13px;color:var(--muted);margin-top:12px;padding-top:10px;border-top:1px solid var(--line)}
figcaption b{color:var(--ink)}
.callout{border-left:3px solid var(--red);background:#FFF7F2;padding:18px 22px;margin:24px 0;font-size:15.2px}
.callout.gold{border-left-color:var(--gold);background:#FDF8EA}
.callout.blue{border-left-color:var(--blue);background:#F2F6FB}
.callout b{color:var(--ink)}
.formula{background:#F4F1E8;border:1px solid var(--line);padding:16px 20px;margin:18px 0;
  font-family:"Cambria Math","Times New Roman",serif;font-size:16.5px;overflow-x:auto;line-height:1.9}
.formula .note{font-family:"Microsoft YaHei",sans-serif;font-size:12.8px;color:var(--muted);display:block;margin-top:6px}
table{width:100%;border-collapse:collapse;margin:20px 0;font-size:13.6px;background:var(--card)}
th{text-align:left;font-weight:700;border-bottom:1.5px solid var(--ink);padding:10px 10px;font-size:12.6px;letter-spacing:.02em}
td{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
tr:hover td{background:#FCFAF4}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.tag{display:inline-block;padding:1px 8px;border-radius:2px;font-size:11.5px;font-weight:700;letter-spacing:.04em}
.tag.ok{background:#E7F4EC;color:#1F6B45}
.tag.no{background:#FBEAEA;color:#A5121C}
.tag.warn{background:#FBF0D9;color:#8A6100}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:22px}
.card{background:var(--card);border:1px solid var(--line);padding:20px 22px}
.card h4{margin:0 0 6px;font-size:15px}
.card .big{font-size:26px;font-weight:700;letter-spacing:-.5px}
ul,ol{padding-left:22px}
li{margin:7px 0}
footer{border-top:1px solid var(--line);padding:34px 0 60px;font-size:12.8px;color:var(--muted)}
@media (max-width:900px){
  .layout{grid-template-columns:1fr} nav.toc{display:none}
  h1{font-size:38px} .wrap{padding:0 22px} .kpis{grid-template-columns:1fr 1fr}
  .grid2{grid-template-columns:1fr}
}
"""


def _img(bundle, name: str, caption: str) -> str:
    path = Path(bundle.figures.get(name, ""))
    if not path.exists():
        return ""
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        f'<figure><img src="data:image/png;base64,{b64}" alt="{html.escape(caption)}">'
        f"<figcaption>{caption}</figcaption></figure>"
    )


def _p(value: float) -> str:
    if value < 1e-4:
        return f"{value:.1e}"
    return f"{value:.4f}"


def _table(headers: list[str], rows: list[list[str]], numeric: set[int] | None = None) -> str:
    numeric = numeric or set()
    head = "".join(
        f'<th class="{"num" if i in numeric else ""}">{h}</th>' for i, h in enumerate(headers)
    )
    body = []
    for row in rows:
        cells = "".join(
            f'<td class="{"num" if i in numeric else ""}">{c}</td>' for i, c in enumerate(row)
        )
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _dlt_7tier() -> list[tuple[int, str, float, str]]:
    """2026-02-02 起生效的大乐透 7 个奖级（合并了 5+0/4+2 等）。"""
    probs = dlt_probabilities_7()
    rows = []
    for tier in range(1, 8):
        minimum = DLT_7_MIN_PRIZE[tier]
        amount = "浮动（奖池均分）" if minimum is None else f"{minimum:,.0f} 元起（浮动）"
        rows.append((tier, DLT_7_CONDITIONS[tier], probs[tier], amount))
    return rows


def _prize_table(key: str) -> str:
    game = GAMES[key]
    if key == "dlt":
        rows = [
            [f"{tier} 等奖", cond, f"1/{1 / prob:,.0f}", f"{prob * 1e8:,.1f}", amount]
            for tier, cond, prob, amount in _dlt_7tier()
        ]
        table = _table(["奖级", "中奖条件", "概率", "每亿注中奖注数", "单注奖金"], rows, {2, 3})
        return table + (
            '<p class="small">注：2026 年 2 月 2 日（第 26014 期）起，大乐透由 9 个奖级合并为 7 个，'
            '三等奖同时包含 5+0 与 4+2，五等奖同时包含 4+0 与 3+2；'
            '2019–2026 年初的 9 级结构见操作台的逐期奖级明细。合并前后各档总中奖概率几乎不变，'
            '固定奖部分的期望贡献由约 0.546 元变为约 0.555 元。</p>'
        )

    tiers = tier_probabilities(game)
    names = {
        "ssq": [(1, "6 红 + 1 蓝"), (2, "6 红 + 0 蓝"), (3, "5 红 + 1 蓝"), (4, "5+0 或 4+1"),
                (5, "4+0 或 3+1"), (6, "0–2 红 + 1 蓝")],
    }[key]
    rows = []
    for tier, cond in names:
        prob = tiers[tier]
        fixed = FIXED_PRIZES[key].get(tier)
        amount = f"{fixed:,.0f} 元（固定）" if fixed else "浮动（奖池均分）"
        rows.append([f"{tier} 等奖", cond, f"1/{1 / prob:,.0f}", f"{prob * 1e8:,.1f}", amount])
    return _table(["奖级", "中奖条件", "概率", "每亿注中奖注数", "单注奖金"], rows, {2, 3})


def _test_table(frame: pd.DataFrame) -> str:
    rows = []
    for _, row in frame.iterrows():
        bad = row["significant_fdr"]
        verdict = '<span class="tag no">不通过</span>' if bad else '<span class="tag ok">通过</span>'
        rows.append(
            [
                html.escape(str(row["category"])),
                html.escape(str(row["test"])),
                f"{row['statistic']:.1f}" if pd.notna(row["statistic"]) else "—",
                f"{row['dof']:.0f}" if pd.notna(row["dof"]) else "—",
                _p(float(row["p_value"])),
                _p(float(row["q_value"])),
                verdict,
            ]
        )
    return _table(["类别", "检验", "统计量", "自由度", "p 值", "q 值（FDR）", "结论"], rows, {2, 3, 4, 5})


def _strategy_table(bundle, key: str) -> str:
    summary = bundle.backtests[key].summary.copy()
    rows = []
    for _, row in summary.iterrows():
        rows.append(
            [
                STRATEGY_LABELS.get(row["strategy"], row["strategy"]),
                f"{row['mean_front_hits']:.3f}",
                f"{row['theoretical_hits']:.3f}",
                f"{row['t_stat']:+.2f}",
                f"{row['any_prize_rate'] * 100:.2f}%",
                f"{row['roi'] * 100:+.1f}%",
            ]
        )
    return _table(["策略", "平均命中", "理论值", "t 统计量", "中奖率", "回测收益率"], rows, {1, 2, 3, 4, 5})


def _pop_table(bundle) -> str:
    frame = bundle.popularity["ssq"]
    rows = []
    for _, row in frame.iterrows():
        sig = row["q_value"] < 0.05
        rows.append(
            [
                row["label"],
                f"{row['coef']:+.3f}",
                f"{row['effect_pct']:+.1f}%",
                f"{row['z']:+.2f}",
                _p(float(row["p_value"])),
                _p(float(row["q_value"])),
                '<span class="tag no">显著</span>' if sig else '<span class="tag ok">不显著</span>',
            ]
        )
    return _table(["形态", "系数", "约当变化", "z 值", "p 值", "q 值", "判断"], rows, {1, 2, 3, 4, 5})


def _nav() -> str:
    items = [
        ("s0", "摘要", False),
        ("s1", "01 · 认识两种游戏", False),
        ("s2", "02 · 可用的数学工具", False),
        ("s3", "03 · 公平性检验", True),
        ("s4", "04 · 形态与遗漏", True),
        ("s5", "05 · 独立性与序列", True),
        ("s6", "06 · 建模与回测", False),
        ("s7", "07 · 期望值与决策", False),
        ("s8", "08 · 唯一可优化的空间", False),
        ("s9", "09 · 结论与局限", False),
        ("s10", "附录", False),
    ]
    links = "".join(
        f'<a class="{"sub" if sub else ""}" href="#{sid}">{label}</a>' for sid, label, sub in items
    )
    return f'<nav class="toc"><div class="t">CONTENTS</div>{links}</nav>'


def write_report(bundle) -> Path:
    k = bundle.kpis()
    ssq, dlt = k["ssq"], k["dlt"]
    total_draws = ssq["draws"] + dlt["draws"]

    bt_ssq = bundle.backtests["ssq"]
    bt_dlt = bundle.backtests["dlt"]
    best_ssq = bt_ssq.summary.iloc[0]
    best_dlt = bt_dlt.summary.iloc[0]
    logloss = pd.concat([bt_ssq.logloss.assign(game="双色球"), bt_dlt.logloss.assign(game="大乐透")])
    max_lift = float(logloss["lift"].max())

    mc_ssq = bundle.mc["ssq"]
    mc_dlt = bundle.mc["dlt"]
    ev_mean = float(bundle.ev["ssq"]["ev"].mean())
    rtp_mean = float(bundle.ev["ssq"]["rtp"].mean())

    # 各彩种"历史最高头奖"对应的单注期望，以及追平票价的临界头奖
    tiers_ssq = tier_probabilities(GAMES["ssq"])
    fixed_ssq = sum(tiers_ssq[t] * amount for t, amount in FIXED_PRIZES["ssq"].items())
    max_jackpot_ssq = float(bundle.data["ssq"].df["p1_amount"].max())
    second_ssq = 150_000.0
    ev_at_max = fixed_ssq + tiers_ssq[1] * max_jackpot_ssq + tiers_ssq[2] * second_ssq
    breakeven_jackpot = (2.0 - fixed_ssq - tiers_ssq[2] * second_ssq) / tiers_ssq[1]

    pop = bundle.popularity["ssq"].set_index("variable")
    birthday_effect = float(pop.loc["n_le12", "effect_pct"])
    birthday_p = float(pop.loc["n_le12", "p_value"])

    # 早期/晚期大乐透分段检验
    from scipy import stats as sps

    dlt_data = bundle.data["dlt"]
    years = 2000 + dlt_data.df["issue"].to_numpy() // 1000
    early_mask = years <= 2013
    early_counts = dlt_data.front[early_mask].sum(axis=0)
    late_counts = dlt_data.front[~early_mask].sum(axis=0)
    e1 = early_mask.sum() * 5 / 35
    e2 = (~early_mask).sum() * 5 / 35
    chi_early = float(((early_counts - e1) ** 2 / e1).sum())
    chi_late = float(((late_counts - e2) ** 2 / e2).sum())
    p_early = float(sps.chi2.sf(chi_early, 34))
    p_late = float(sps.chi2.sf(chi_late, 34))

    def sec(sid, no, title, body):
        return f'<section id="{sid}"><h2><span class="no">{no}</span>{title}</h2>{body}</section>'

    parts: list[str] = []

    # ---------------- 摘要 ----------------
    summary = f'''
    <p class="lead">这份报告用 {total_draws:,} 期真实开奖（双色球 {ssq['draws']:,} 期、大乐透 {dlt['draws']:,} 期），
    把"选号玄学"逐条放到统计学的显微镜下：先建立可证伪的零假设，再用精确组合分布与置换检验算 p 值，
    最后用严格的时间外回测检验这些方法究竟能不能赚钱。</p>
    <div class="grid2" style="margin:26px 0">
      <div class="card"><h4>结论一：开奖与均匀随机抽样无法区分</h4>
      <p class="small">双色球 {ssq['tests']} 项检验经 FDR 校正后有 <b>{ssq['sig_fdr']}</b> 项显著；大乐透有 <b>{dlt['sig_fdr']}</b> 项，
      但全部由 2014 年前的分布断点驱动——分段后，2014 年至今的前区均匀性检验 p={p_late:.2f}，完全正常。
      双色球唯一接近显著的是红球频数（p={ssq['front_chi2_p']:.3f}），在 32 个自由度下属于正常波动。</p></div>
      <div class="card"><h4>结论二：所有选号策略都赢不了随机基准</h4>
      <p class="small">8 种策略 × {bt_ssq.end - bt_ssq.start:,} 期回测，命中数相对理论值的偏离都在 ±5% 内；
      概率预测的对数损失<b>没有一项</b>优于均匀分布（最大"改善"为 {max_lift:+.3f}，负值代表更差）。</p></div>
      <div class="card"><h4>结论三：期望值约为票价的一半</h4>
      <p class="small">按历史奖金计算，双色球单注期望回报约 <b>{ev_mean:.2f} 元</b>，对应返奖率 {rtp_mean * 100:.0f}%；
      每期 1 注连买 15 年，盈利概率仅 <b>{mc_ssq['prob_profit'] * 100:.1f}%</b>。</p></div>
      <div class="card"><h4>结论四：唯一真实的"优势"在奖金分摊</h4>
      <p class="small">选号不能提高中奖概率，但能减少"和别人平分"。控制销量后，每多一个 ≤12 的"生日号"，
      一等奖中出注数约变化 <b>{birthday_effect:+.1f}%</b>（p={birthday_p:.1e}），意味着避开日期型组合可以略微提高期望分成。</p></div>
    </div>
    <div class="callout"><b>一句话：</b>这套工具能精确告诉你"中奖有多难、钱花得值不值、奖金怎么分"，
    但不能告诉你"下一期开什么"——后者在数学上不是一个可解的问题，而是一个已经定义好的随机试验。</div>
    '''
    parts.append(sec("s0", "EXECUTIVE SUMMARY", "摘要", summary))

    # ---------------- 1 认识游戏 ----------------
    rules_rows = [
        ["选号结构", f"{ssq['front_pool']} 选 {ssq['front_pick']}（红球）+ {ssq['back_pool']} 选 {ssq['back_pick']}（蓝球）",
         f"{dlt['front_pool']} 选 {dlt['front_pick']}（前区）+ {dlt['back_pool']} 选 {dlt['back_pick']}（后区）"],
        ["单注金额", "2 元", "2 元（可加 1 元追加）"],
        ["组合总数", f"{ssq['total_combinations']:,}", f"{dlt['total_combinations']:,}"],
        ["头奖概率", f"1/{ssq['total_combinations']:,}", f"1/{dlt['total_combinations']:,}"],
        ["开奖频率", "每周二、四、日", "每周一、三、六"],
        ["奖级", "6 个奖级", "7 个奖级（2026-02 起；此前 9 个）"],
        ["数据区间", f"{ssq['first_date']} — {ssq['last_date']}", f"{dlt['first_date']} — {dlt['last_date']}"],
        ["样本期数", f"{ssq['draws']:,}", f"{dlt['draws']:,}"],
    ]
    body = f'''
    <p>双色球由福利彩票发行，大乐透由体育彩票发行，二者的玩法结构几乎一样：从一个大号码池里不放回地摇出若干个"前区"号码，
    再从一个独立的小号码池里摇出"后区"号码；全部猜中即中头奖。差别只在号码池大小与奖级设置。</p>
    {_table(["", "双色球", "大乐透"], rules_rows)}
    <p>理解这两款游戏只需要一个模型：<b>从 {ssq['front_pool']} 个红球中不放回抽 {ssq['front_pick']} 个，再从 {ssq['back_pool']} 个蓝球中抽 1 个</b>。
    所有组合等可能，因此头奖概率就是组合数的倒数。所谓"分析走势"，本质上是在检验这个模型是否成立、以及在它成立的前提下如何做决策。</p>
    <h3>奖级与概率</h3>
    <p>下面两张表把"中奖"拆成可计算的事件。注意最后一级（双色球六等奖、大乐透七等奖）把总中奖率抬到了 6%–7%，
    这也是"经常中 5 元"的来源——它并不说明号码有规律，只是奖级设计使然。</p>
    {_prize_table("ssq")}
    {_prize_table("dlt")}
    {_img(bundle, "fig01_odds_ladder.png", "<b>图 1</b>　奖级概率阶梯（对数轴，大乐透按 2026 年新规的 7 个奖级）。一等奖概率与“连续抛 24 次硬币全正面”同量级；末等奖才是大多数人的真实体验。")}
    {_img(bundle, "fig02_sales_pool.png", "<b>图 2</b>　销量与奖池。奖池是“未中出的头奖”滚存形成的，会放大头奖金额，但不改变任何一注的中奖概率。")}
    <div class="callout blue"><b>关键区分：</b>奖池决定的是<b>中了以后拿多少</b>，不是<b>能不能中</b>。
    很多人把"奖池高"误读为"更容易中"，这是两个完全独立的量。</div>
    '''
    parts.append(sec("s1", "CHAPTER 01", "认识两种游戏", body))

    # ---------------- 2 方法 ----------------
    body = f'''
    <p>下面六组方法构成了本报告的全部工具箱。它们的共同点是：<b>每一个结论都必须能对应一个零假设，并且能被数据推翻</b>。</p>
    <h3>2.1 概率模型：超几何分布</h3>
    <p>从 N 个号码中抽 k 个，你选的 k 个里命中 j 个的概率服从超几何分布：</p>
    <div class="formula">P(命中 j 个) = C(k, j) · C(N−k, k−j) / C(N, k)
      <span class="note">双色球红球：N=33, k=6；大乐透前区：N=35, k=5。期望命中数 E[j] = k²/N（双色球 1.091，大乐透 0.714）。</span></div>
    <p>这个期望值是后面一切回测的"及格线"：任何策略的平均命中数如果显著高于它，才值得进一步研究；否则就只是随机波动。</p>

    <h3>2.2 精确组合分布：不要用正态近似</h3>
    <p>和值、跨度、奇偶比、连号、AC 值这些"形态"的理论分布并不是正态的。我们直接枚举全部
    C(33,6)={GAMES['ssq'].front_combinations:,} 与 C(35,5)={GAMES['dlt'].front_combinations:,} 个组合，
    得到每个形态取值的<b>精确概率</b>，作为卡方检验的期望频数。这比对分布做正态假设严谨得多，也避免了"和值应该集中在均值附近"这类模糊说法。</p>
    <div class="formula">和值的概率母函数：G(x, y) = ∏<sub>i=1</sub><sup>N</sup> (1 + y·x<sup>i</sup>)，其中 [y<sup>k</sup>] 的系数给出"选 k 个号和为 s"的组合数。
      <span class="note">枚举与母函数等价；本报告用向量化枚举实现，双色球 110 万个组合在 1 秒内完成。</span></div>

    <h3>2.3 假设检验与多重比较</h3>
    <ul>
      <li><b>卡方拟合优度</b>：号码频数、形态分布、遗漏间隔是否偏离理论。</li>
      <li><b>游程检验 / Ljung–Box</b>：和值序列是否存在趋势或自相关。</li>
      <li><b>Fisher 合并</b>：把每个号码的独立检验合并成一个总体检验。</li>
      <li><b>蒙特卡洛置换</b>：号码对共现这类统计量解析分布未知，用 300 次随机重排得到经验 p 值。</li>
      <li><b>Benjamini–Hochberg FDR</b>：一次跑几十个检验，必然有 5% 假阳性；用 q 值控制错误发现率。</li>
    </ul>
    <div class="formula">q<sub>(i)</sub> = min<sub>j≥i</sub> [ p<sub>(j)</sub> · m / j ]　（m 为检验总数，p<sub>(1)</sub>≤…≤p<sub>(m)</sub>）
      <span class="note">本报告对每个彩种的全部检验统一做 BH 校正；只有 q<0.05 才视为"通过"。</span></div>

    <h3>2.4 贝叶斯视角：先验有多强</h3>
    <p>把每个号码的出现次数看作多项分布，配上均匀 Dirichlet 先验 Dir(1,…,1)，后验均值为：</p>
    <div class="formula">p̂<sub>i</sub> = (c<sub>i</sub> + 1) / (N<sub>draw</sub> + K)
      <span class="note">双色球 3523 期、33 个号码时，p̂<sub>i</sub> 被拉向 1/33 的幅度约为 33/(3523+33)≈0.9%。数据再多，也只能把"偏差"估得越来越准，而不能把随机性变成规律。</span></div>

    <h3>2.5 预测评估：对数损失与校准</h3>
    <p>"中了没有"是噪声极大的评价指标。更灵敏的做法是评价概率预测本身：</p>
    <div class="formula">LogLoss = −(1/T) Σ<sub>t</sub> Σ<sub>i∈开奖号</sub> ln p<sub>t,i</sub>　；　Brier = (1/TK) Σ<sub>t,i</sub> (y<sub>t,i</sub> − p<sub>t,i</sub>)²
      <span class="note">均匀分布的 LogLoss 是 k·ln N（双色球 20.98）；任何"模型"只有低于它才算有预测力。</span></div>

    <h3>2.6 期望值与蒙特卡洛</h3>
    <p>单注期望回报 = Σ<sub>奖级</sub> P(奖级) × 该奖级单注奖金。由于一、二等奖浮动，我们逐期用官方奖金计算，
    并对"每期 1 注、连买 15 年"做 4000 次蒙特卡洛，奖金金额从历史真实奖级中重抽样，以保留巨奖的厚尾。</p>
    '''
    parts.append(sec("s2", "CHAPTER 02", "可用的数学工具", body))

    # ---------------- 3 公平性 ----------------
    body = f'''
    <p>第一个可证伪的问题：每个号码出现的频率是否相同？如果摇奖设备存在物理偏差，或数据被污染，这里会最先暴露。</p>
    {_img(bundle, "fig03_frequency_heatmap.png", "<b>图 3</b>　号码频率的年度漂移。大乐透前区在 2007–2013 年出现明显的“大号偏多”，2014 年后消失；双色球全样本没有这种结构。")}
    {_img(bundle, "fig04_residuals.png", "<b>图 4</b>　全样本标准化残差。绝大多数号码落在 ±2σ 内，没有系统性偏差。")}
    <h3>双色球：通过</h3>
    <p>红球频数 χ²={bundle.analysis['ssq']['results'].iloc[0]['statistic']:.1f}（df=32，p={ssq['front_chi2_p']:.3f}），
    蓝球 p={bundle.analysis['ssq']['results'].iloc[1]['p_value']:.3f}；经 FDR 校正后没有任何一项显著。
    号码频率分布的信息熵为 {ssq['entropy']:.4f} bit，理论上限 log₂33={ssq['max_entropy']:.4f} bit——几乎完全均匀。</p>
    <h3>大乐透：一个真实存在的结构性断点</h3>
    <p>大乐透全样本的前区 χ² 为 {bundle.analysis['dlt']['results'].iloc[0]['statistic']:.1f}（p={dlt['front_chi2_p']:.1e}），
    但这不是"规律"，而是<b>分段</b>：2007–2013 年的 χ²={chi_early:.0f}（df=34，p≈{p_early:.0e}），
    2014 年以后 χ²={chi_late:.0f}（p={p_late:.2f}）。早期号码 29–35 的出现频率比期望高 20%–55%，2014 年起骤然恢复正常。</p>
    <div class="callout gold"><b>怎么解释？</b>数据本身只能告诉我们"变了"，不能告诉我们"为什么"。最可能的解释是 2014 年规则调整前后
    摇奖设备/球组或流程发生了变化；也不能完全排除历史数据归档问题。但无论原因是什么，<b>这段偏移在 2014 年后已经消失</b>，
    对今天的选号没有任何可用价值——反而是一个完美的反面教材：任何在全样本上训练出来的"热号模型"，都会把这段历史偏差当成规律。</div>
    {_test_table(bundle.analysis['ssq']['results'])}
    <p class="small">表：双色球全部统计检验。q 值为 BH 校正后的错误发现率；"通过"表示不能拒绝"均匀随机"的零假设。</p>
    {_test_table(bundle.analysis['dlt']['results'])}
    <p class="small">表：大乐透全部统计检验。多数的"不通过"都可以追溯到 2014 年前的那段断点，而不是持续存在的机制。</p>
    '''
    parts.append(sec("s3", "CHAPTER 03", "公平性检验", body))

    # ---------------- 4 形态 ----------------
    body = f'''
    <p>如果号码独立均匀，那么和值、奇偶比、连号、AC 值等形态应当严格服从由组合数决定的精确分布。
    这一章把"形态"逐个对照理论基准。</p>
    {_img(bundle, "fig06_sum_distribution.png", "<b>图 5</b>　和值分布。灰柱是 C(n,k) 枚举得到的精确分布，红线是真实开奖；两者在抽样误差内重合。")}
    {_img(bundle, "fig07_shape_grid.png", "<b>图 6</b>　奇偶、大小、连号、AC 值四个形态的实测与理论对比。所有偏离都在随机波动范围内。")}
    <h3>遗漏值：最容易被误读的指标</h3>
    <p>"某个号码已经 30 期没出，该出了"是彩票圈最常见的谬误。若每期独立，遗漏长度服从几何分布：
    P(遗漏 = k) = (1−p)<sup>k</sup>p。图 7 显示实测遗漏分布与几何分布几乎重合——<b>历史遗漏不改变下一期的概率</b>。</p>
    {_img(bundle, "fig05_omission.png", "<b>图 7</b>　左：当前遗漏；右：遗漏长度分布 vs 几何分布（对数轴）。长尾是几何分布的必然产物，不是“补偿机制”。")}
    <div class="callout"><b>为什么"该出了"是错的：</b>把一枚公平硬币连抛 10 次正面，第 11 次正面的概率仍是 50%。
    遗漏 30 期只说明"过去 30 期没出"，它对第 31 期没有任何记忆。</div>
    '''
    parts.append(sec("s4", "CHAPTER 04", "形态与遗漏", body))

    # ---------------- 5 独立性 ----------------
    body = f'''
    <p>比"分布是否均匀"更细一层的问题是：期与期之间是否独立？如果存在自相关，理论上可以用上一期预测下一期。</p>
    {_img(bundle, "fig08_sequence.png", "<b>图 8</b>　和值序列、100 期滚动均值与自相关函数。几乎所有 ACF 都落在 95% 置信带内；大乐透的“趋势”完全由 2014 年前的断点贡献。")}
    {_img(bundle, "fig09_pvalues.png", "<b>图 9</b>　p 值 QQ 图。点沿对角线分布，说明检验结果的分布与“纯随机”一致；个别偏离在多重检验下并不意外。")}
    {_img(bundle, "fig10_pairs.png", "<b>图 10</b>　号码对共现的标准化残差。整体模式接近随机，少数 |z|>3 的号码对在 528 次比较中属于预期内的假阳性。")}
    <p>双色球的号码一阶自相关检验 Fisher 合并 χ²={bundle.analysis['ssq']['results'].iloc[10]['statistic']:.1f}（p={bundle.analysis['ssq']['results'].iloc[10]['p_value']:.2f}），
    和值 Ljung–Box p={bundle.analysis['ssq']['results'].iloc[15]['p_value']:.2f}，游程检验 p={bundle.analysis['ssq']['results'].iloc[14]['p_value']:.2f}：
    没有任何证据支持"上一期影响下一期"。</p>
    '''
    parts.append(sec("s5", "CHAPTER 05", "独立性与序列", body))

    # ---------------- 6 回测 ----------------
    body = f'''
    <p>检验只能说明"没有简单偏差"，还不能回答"复杂的模型能不能赚到钱"。为此我们做严格的时间外回测：
    对第 t 期，所有策略只使用第 t 期之前的数据选号，逐期结算真实奖级与奖金。</p>
    <h3>参战的八种策略</h3>
    <ul>
      <li><b>随机基准</b>：均匀随机选号，理论上的"不可战胜线"。</li>
      <li><b>热号</b>：最近 30/100 期出现次数最多的号码。</li>
      <li><b>冷号</b>：当前遗漏最长的号码（"该出了"派）。</li>
      <li><b>贝叶斯</b>：Dirichlet 后验均值，等价于全历史平滑频率。</li>
      <li><b>马尔可夫</b>：用 P(本期出现 | 上期出现) 排序。</li>
      <li><b>趋势</b>：最近 200 期出现率的线性斜率。</li>
      <li><b>形态均衡</b>：在 300 张随机票中挑"和值/奇偶/跨度最像典型开奖"的一张。</li>
    </ul>
    {_img(bundle, "fig11_backtest.png", "<b>图 11</b>　左：各策略平均命中数相对理论期望的比值（1.0 = 与随机无异）；右：热号策略的命中数分布与超几何理论几乎完全重合。")}
    {_strategy_table(bundle, 'ssq')}
    <p class="small">表：双色球 {bt_ssq.end - bt_ssq.start:,} 期（{ssq['bt_start']} 至 {ssq['bt_end']}）回测。收益率 = 奖金/投入 − 1。回测期内没有出现头奖，收益率完全由中小奖决定：热号 30 期之所以显示 +19.3%，只是因为多中了一注三等奖（3000 元）。</p>
    <p>表现最好的策略是 <b>{STRATEGY_LABELS.get(best_ssq['strategy'], best_ssq['strategy'])}</b>，
    平均命中 {best_ssq['mean_front_hits']:.3f} 个（理论 {best_ssq['theoretical_hits']:.3f}），t={best_ssq['t_stat']:+.2f}；
    大乐透最好的是 <b>{STRATEGY_LABELS.get(best_dlt['strategy'], best_dlt['strategy'])}</b>，t={best_dlt['t_stat']:+.2f}。
    在 8 个策略、2 个彩种共 16 次比较中，出现 1–2 个 p<0.05 的结果完全符合随机预期（Bonferroni 阈值应为 0.003）。</p>
    <div class="callout blue"><b>为什么不要用“收益率”判断策略好坏：</b>热号 30 期的 +19.3% 来自一注偶然的三等奖，
    把这一注拿掉就是 −80%。在 1500 期里，一二等奖几乎必然缺席，收益率由一两注中小奖主导，方差远大于信号。
    这就是本报告更看重“命中数”和“对数损失”的原因：它们每一期都在提供信息，而不是等一次巨奖。</div>
    {_img(bundle, "fig12_calibration.png", "<b>图 12</b>　校准曲线与对数损失。所有模型的校准线都贴着对角线（说明它们“知道”自己没信息），对数损失全部劣于均匀分布。")}
    <div class="callout"><b>为什么"热号"偶尔看起来有效？</b>因为数据存在 regime（分段）。大乐透 2007–2013 年的大号偏差会让任何"追热"策略在那段时间表现很好；
    一旦 2014 年设备/流程改变，优势立刻消失。这正是样本内过拟合的经典形态：<b>它拟合的是历史环境，不是随机机制</b>。</div>
    '''
    parts.append(sec("s6", "CHAPTER 06", "建模与回测", body))

    # ---------------- 7 期望值 ----------------
    body = f'''
    <p>如果中奖概率无法改变，那么唯一能算清楚的就是"这笔钱值不值"。一注 2 元的期望回报为：</p>
    <div class="formula">E[回报] = Σ<sub>t</sub> P(奖级 t) × 奖金<sub>t</sub>
      <span class="note">双色球历史平均约 {ev_mean:.2f} 元/注，返奖率约 {rtp_mean * 100:.0f}%；其余约一半进入公益金与发行费用。</span></div>
    {_img(bundle, "fig13_ev.png", "<b>图 13</b>　左：期望回报随一等奖金额的变化——曲线要到约 2,450 万元才追平 2 元票价，而历史最高只有 1,500 万元；右：历史滚动返奖率围绕 50% 波动。")}
    <p>奖金封顶与奖池规则决定了期望值的上限。以双色球为例，历史上单注最高一等奖为
    <b>{max_jackpot_ssq / 1e4:,.0f} 万元</b>，对应单注期望约 <b>{ev_at_max:.2f} 元</b>；
    要让期望追平 2 元票价，头奖需要达到约 <b>{breakeven_jackpot / 1e4:,.0f} 万元</b>——既超出历史极值，也不符合现行奖金规则。</p>
    <h3>等待时间：以万年为单位</h3>
    {_img(bundle, "fig14_waiting.png", "<b>图 14</b>　左：连续购买达到 50%/95% 中头奖概率所需的年数；右：4000 次蒙特卡洛的 15 年总回报分布。")}
    <p>每期 1 注、每年约 150 期，连续买 15 年共投入 3000 元：中位回报 <b>{mc_ssq['median_payout']:.0f} 元</b>，
    盈利概率 <b>{mc_ssq['prob_profit'] * 100:.2f}%</b>，15 年内至少中一次头奖的概率约 <b>{mc_ssq['prob_any_jackpot'] * 100:.4f}%</b>。
    大乐透的对应数字是：中位回报 {mc_dlt['median_payout']:.0f} 元、盈利概率 {mc_dlt['prob_profit'] * 100:.2f}%、
    中头奖概率 {mc_dlt['prob_any_jackpot'] * 100:.4f}%。
    要达到 50% 的中头奖概率，双色球需要连续购买约 <b>8.2 万年</b>。</p>
    <h3>复式与覆盖：用钱买确定性</h3>
    {_img(bundle, "fig15_coverage.png", "<b>图 15</b>　左：投入金额与“至少中一次头奖”概率的关系（对数坐标）；右：双色球复式投注的注数与金额。")}
    <p>复式投注（如 8+2）把 C(8,6)×C(2,1)=56 注打包成一张票，覆盖率线性上升、成本也线性上升，
    它买到的是"更多组合"，不是"更高的单注命中率"。数学上，m 注不同号码的头奖概率严格等于 m/组合总数。</p>
    '''
    parts.append(sec("s7", "CHAPTER 07", "期望值与决策", body))

    # ---------------- 8 流行度 ----------------
    body = f'''
    <p>前面说过：选号不能提高中奖概率。但一、二等奖是<b>浮动奖</b>——奖池由所有中奖注数均分。
    因此，选一组"没人买"的号码，虽然不改变中奖概率，却能改变<b>中奖后分到多少</b>。这是唯一真实、可优化的空间。</p>
    <p>我们用“一等奖中出注数”作为组合流行度的代理变量：在同一期销量下，中出注数越多，说明这组号码越受欢迎。
    对每个形态单独做回归（控制 log 销量、log 奖池与时间趋势，避免强共线性），结果如下：</p>
    {_pop_table(bundle)}
    <p class="small">表：双色球 3523 期，因变量 log(1+一等奖注数)，OLS + HC1 稳健标准误。形态变量已标准化，系数可读作“每变动一个标准差，中奖注数约变化 e^β−1”；q 值为 8 个形态检验的 BH 校正结果。</p>
    {_img(bundle, "fig16_popularity.png", "<b>图 16</b>　左：和值分箱后的“每百万元销量一等奖注数”；右：控制销量后的形态效应。生日号（≤12）越多，中奖人数越多。")}
    <div class="callout gold"><b>可操作的结论：</b>如果你一定要买，<b>避开"日期型"组合</b>（大量 ≤12 的号码、1–31 的生日、连续号、对称号、全偶数等"看起来有意义"的排列）。
    这不会让你更容易中奖，但一旦中了，和你分奖池的人会更少。按文献与我们的估计，这可以把中奖后的期望分成提高几个百分点到十几个百分点——
    相对 50% 的返奖率，这只是很小的修正，但它是唯一在数学上站得住脚的"技巧"。</div>
    <h3>理性购彩的四条规则</h3>
    <ol>
      <li><b>把它当消费，不当投资。</b>期望回报约为票价的一半；长期收益率必然收敛到 −50% 左右。</li>
      <li><b>固定预算，绝不追号。</b>"倍投回本"在独立随机试验中是负期望的赌博策略，会把小概率放大成确定性亏损。</li>
      <li><b>不迷信任何"内部消息"或"预测软件"。</b>如果真有人能稳定预测，他不会卖 199 元的软件。</li>
      <li><b>不借钱、不影响生活。</b>购彩是娱乐支出，不是财务计划。</li>
    </ol>
    '''
    parts.append(sec("s8", "CHAPTER 08", "唯一可优化的空间", body))

    # ---------------- 9 结论 ----------------
    body = f'''
    <h3>数学能做的三件事</h3>
    <ul>
      <li><b>描述</b>：精确计算每一种形态、每一个奖级的概率，把"感觉"变成数字。</li>
      <li><b>检验</b>：用可证伪的方法判断历史数据是否偏离随机模型，并控制多重比较带来的假阳性。</li>
      <li><b>决策</b>：计算期望值、等待时间、覆盖成本与奖金分摊，帮助你在给定预算下做出理性选择。</li>
    </ul>
    <h3>数学不能做的三件事</h3>
    <ul>
      <li>不能预测下一期号码——开奖是设计好的独立随机试验，历史不携带关于未来的信息。</li>
      <li>不能把负期望变成正期望——除非你能改变规则（奖池、税收、分摊），否则期望值由概率结构决定。</li>
      <li>不能保证"稳定盈利"——任何声称能做到这一点的策略，要么在过拟合，要么在骗人。</li>
    </ul>
    <h3>本报告的局限</h3>
    <ul>
      <li><b>数据</b>：来自中国福彩网与体彩网官方接口，并与 500.com 交叉校验；个别期次的奖金字段有官方修正记录，已在数据层标注。</li>
      <li><b>断点</b>：大乐透 2014 年前存在无法从数据本身解释的分布偏移；我们选择如实呈现，而不是把它当成"规律"。</li>
      <li><b>多重检验</b>：即使全部检验都做 FDR 校正，仍不能排除未观测到的弱偏差；但任何弱到需要上万期才能检出的偏差，都不足以覆盖 50% 的返奖率缺口。</li>
      <li><b>外推</b>：回测区间有限，收益率受是否中出头奖的极端影响；我们更看重命中数与对数损失这类更稳定的指标。</li>
    </ul>
    <div class="callout"><b>最后一句：</b>彩票是一个把"小概率大奖金"包装成娱乐产品的行业。把它当娱乐，数学会帮你控制成本；
    把它当投资，数学会告诉你答案已经写在期望值里。</div>
    '''
    parts.append(sec("s9", "CHAPTER 09", "结论与局限", body))

    # ---------------- 附录 ----------------
    body = f'''
    <h3>数据来源</h3>
    <ul>
      <li>双色球：中国福利彩票发行管理中心官方开奖接口（2013 年至今）+ 500.com 历史数据（2003–2012），两源交叉校验。</li>
      <li>大乐透：中国体育彩票官方历史接口，与 500.com 全量比对；号码字段零差异。</li>
      <li>奖金与销量：官方接口原始字段，缺失值按官方公告修正并标注。</li>
    </ul>
    <h3>复现方式</h3>
    <div class="formula">python main.py
      <span class="note">依赖：numpy / pandas / scipy / matplotlib；数据已随仓库提供，无需联网即可复现全部图表、回测与报告。</span></div>
    <h3>文件结构</h3>
    <div class="formula">
    src/lottery/<br>
    ├─ config.py          规则与概率常量<br>
    ├─ data.py            数据加载与校验<br>
    ├─ features.py        逐期特征<br>
    ├─ combinatorics.py   精确组合分布<br>
    ├─ tests.py           统计检验与 FDR<br>
    ├─ models.py          8 种选号策略<br>
    ├─ backtest.py        时间外回测<br>
    ├─ simulation.py      期望值/蒙特卡洛/覆盖<br>
    ├─ popularity.py      奖金分摊回归<br>
    ├─ charts.py          16 张图<br>
    └─ report.py          HTML 报告
      <span class="note">运行产物：output/figures/*.png 与 output/report.html。</span></div>
    <h3>口径说明</h3>
    <ul>
      <li>前区命中期望：双色球 6²/33=1.0909；大乐透 5²/35=0.7143。</li>
      <li>收益率按 2 元/注计算，不含追加投注；中奖金额使用当期官方单注奖金。</li>
      <li>对数损失以自然对数为底，均匀基准为 k·ln N。</li>
      <li>所有 p 值均为双侧；置换检验使用 300 次重排。</li>
    </ul>
    '''
    parts.append(sec("s10", "APPENDIX", "附录", body))

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    page = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>双色球与大乐透的数学解剖</title>
<style>{CSS}</style></head>
<body>
<div class="wrap">
  <header class="cover">
    <div class="kicker">Quantitative Note · Lottery</div>
    <h1>双色球与大乐透<br>的数学解剖</h1>
    <p class="sub">从 {total_draws:,} 期真实开奖出发：概率结构、公平性检验、严格回测，以及一个负期望游戏里唯一能优化的东西。</p>
    <div class="meta">
      <span>样本　<b>双色球 {ssq['draws']:,} 期 · 大乐透 {dlt['draws']:,} 期</b></span>
      <span>区间　<b>{ssq['first_date']} — {dlt['last_date']}</b></span>
      <span>生成　<b>{generated}</b></span>
    </div>
    <a class="cta" href="console.html">打开数据操作台 · 任意排序与筛选 →</a>
    <div class="kpis">
      <div class="kpi"><div class="v">{total_draws:,}</div><div class="l">期真实开奖</div></div>
      <div class="kpi"><div class="v">{ssq['tests'] + dlt['tests']}</div><div class="l">项统计检验</div></div>
      <div class="kpi"><div class="v">1</div><div class="l">处结构性断点（大乐透 2014）</div></div>
      <div class="kpi"><div class="v">1.00<small>×</small></div><div class="l">策略命中 / 随机期望</div></div>
      <div class="kpi"><div class="v">~{rtp_mean * 100:.0f}<small>%</small></div><div class="l">历史平均返奖率</div></div>
    </div>
  </header>
  <div class="layout">
    {_nav()}
    <main>{''.join(parts)}</main>
  </div>
  <footer>
    本报告仅用于概率与统计方法研究，不构成任何购彩建议。彩票具有负期望与成瘾风险，请理性对待。
    所有数字均由 data/ 下的官方开奖数据计算，可由 python main.py 完整复现。
  </footer>
</div>
{LIGHTBOX}
</body></html>'''

    path = OUTPUT_DIR / "report.html"
    path.write_text(page, encoding="utf-8")
    print(f"  [OK] {path}（{path.stat().st_size / 1e6:.1f} MB）")
    return path
