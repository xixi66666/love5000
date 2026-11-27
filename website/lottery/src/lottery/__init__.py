"""双色球与大乐透的数学解剖。

本包把官方开奖历史（``data/ssq.csv``、``data/dlt.csv``）当作一份只读的随机试验样本，
用精确组合分布、假设检验、时间外回测与蒙特卡洛回答三个问题：开奖能否与均匀随机抽样
区分、各种“选号技巧”是否比随机更强、以及单注的期望回报是多少。

公开面（按数据流顺序）：
    * :mod:`lottery.config`：彩种规则、奖级映射与概率常量；
    * :mod:`lottery.data`：只读加载与校验，产出 ``LotteryData``；
    * :mod:`lottery.features` / :mod:`lottery.combinatorics`：逐期形态与理论分布；
    * :mod:`lottery.tests`：假设检验与 Benjamini–Hochberg 校正；
    * :mod:`lottery.models` / :mod:`lottery.backtest`：8 种策略与时间外回测；
    * :mod:`lottery.simulation` / :mod:`lottery.popularity`：期望值、蒙特卡洛与奖金分摊；
    * :mod:`lottery.charts` / :mod:`lottery.console` / :mod:`lottery.report`：产物层；
    * :mod:`lottery.run`：一键编排上述全部步骤。

数据边界：本包自身不修改 ``data/`` 下的官方 CSV，只读取；缓存写入 ``cache/``，
产物写入 ``output/``。CSV 的追加与修复由 ``scripts/update_daily.py`` 完成，
且每次落盘前都会备份到 ``data/backup/<时间戳>/``。

结论边界：所有“命中率”“收益率”“策略优劣”都只是对历史样本的描述。
开奖是相互独立的随机试验，本包不提供、也不可能提供下一期的预测，更不构成购彩建议。
"""

# 包版本：只在对外数据结构或产物格式不兼容变更时递增，与开奖期次无关。
__version__ = "0.1.0"
