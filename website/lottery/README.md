# 开奖数据操作台（website/lottery）

双色球 / 大乐透历史数据操作台与研究报告，作为 love5000 首页 **01 Golden Hour 第 09 个入口**
（端口 `5179`）运行。

## 它是什么

- **6,466 期官方开奖**：双色球 3,523 期（2003-02 起）、大乐透 2,944 期（2007-05 起），
  与 500.com 交叉校验，号码零差异。
- **四个视图**：数据表（任意列排序、多列排序、号码必含/排除、区间筛选、CSV 导出）、
  走势矩阵（期 × 号码，命中显示号码，其余显示当时遗漏并按长短上色）、
  统计视图（频次、当前遗漏、和值、奇数个数、相邻重号）、分组透视（年/月/星期/和值区间等）。
- **逐期详情**：奖级明细、形态指标、与上期重号，`←` `→` 翻上下期。
- **选号工具**：操作台导航进入 `/selection`，支持随机、近 100 期热号、冷号、最大遗漏及近 100 期指数衰减频率（半衰期 30 期），一次生成 1–10 注；每注自动标注和值、跨度、奇偶、大小、三区比、连号组数、AC 值与和上期的重号，页面下方对照最近 20 期开奖（同口径形态）。相同分数随机排序，多注可能重复。数据仅作历史统计，不提供中奖预测或他人投注数据。
- **研究报告**：`output/report.html`（本地生成，含 16 张图与全部检验/回测结果）。

## 前后端

纯 Python 标准库 + numpy / pandas / requests，无 npm 构建：

| 文件 | 职责 |
|---|---|
| `server.py` | 本地服务：页面托管、健康与状态、数据更新及选号接口 |
| `selection.py` | 从本地开奖数据生成候选号码，不修改历史数据 |
| `main.py` | `--console-only` 只重建操作台；不带参数重建全部产物 |
| `src/lottery/` | 数据加载、精确组合分布、统计检验、回测、操作台与报告生成 |
| `scripts/update_daily.py` | 增量抓取 + 校验 + 备份 + 重建 |
| `scripts/fetch_*.py` | 首次全量回填（含 500.com 交叉校验） |
| `data/` | 官方开奖 CSV（提交） |
| `output/` | `console.html` 等产物（gitignored，首次启动自动构建） |

## 启动

由 love5000 首页卡片点击启动（`POST /api/services/lottery/start`），或手动：

```bash
cd website/lottery
python server.py            # 默认 127.0.0.1:5179
python server.py --open     # 顺便打开浏览器
```

首次启动若 `output/console.html` 不存在，会先执行 `python main.py --console-only --port 5179`
构建（约 3 秒）。
模板更新或旧页面缺少选号入口时，下次启动会自动重建；已运行的旧服务需要重启才能加载新接口。

依赖：

```bash
pip install numpy pandas requests
```

## 刷新数据

页面顶部「刷新数据」按钮调用 `POST /api/update`：

1. 只拉官方接口第 1 页，与本地最大期号比对，不做全量重抓；
2. 校验号码范围、期内去重、期次递增，异常直接放弃，不动现有数据；
3. 有新期次才备份到 `data/backup/<时间戳>/`（保留最近 10 份）；
4. 追加 CSV，只重建操作台，完成后页面自动刷新。

命令行等价：

```bash
python scripts/update_daily.py                 # 增量更新并重建
python scripts/update_daily.py --check         # 只看有没有新数据
python scripts/update_daily.py --force-build   # 没有新数据也重建一次
```

## 选号方法回测

在仓库根目录执行 `python -X utf8 website/lottery/scripts/selection_backtest.py`，
只读取本地 CSV，不修改数据。脚本以最近 1500 期逐期回测近 100 期热号、冷号及最大遗漏，
比较随机基准和理论平均命中数，并输出前后半段和 Holm 多重检验结果。
可用 `--warmup`、`--evaluation` 和 `--seed` 调整参数；它只依赖 Python 标准库。
该探索性回测不计算中奖率或收益，历史结果不保证未来表现。

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查，返回 `success=true` 与数据截止期次 |
| GET | `/api/status` | 当前数据期次与产物时间 |
| POST | `/api/update` | 增量更新，纯文本流式返回日志，末尾 `__DONE__ {...}` |
| GET | `/api/selection?game=ssq&method=random&count=1` | 生成候选号码；`game` 为 `ssq` / `dlt`，`method` 为 `random` / `hot100` / `cold100` / `overdue` / `weighted`，`count` 为 1–10；返回截止期次、日期、`tickets`（含 `stats` / `back_stats` / `repeat`）和最近 20 期 `recent`，参数错误返回 400，数据更新中返回 409 |
| GET | `/api/recent?game=ssq&count=20` | 最近若干期开奖及形态；`count` 为 1–50（默认 20），返回 `draws`，参数错误返回 400 |
| GET | `/` | 操作台页面 |
| GET | `/selection` | 选号工具页面 |

`/api/update` 需要请求头 `X-Console: 1` 且同一时间只允许一个任务（并发返回 429）。

选号逻辑和接口测试：`python -X utf8 -m unittest discover -s tests -v`（工作目录为 `website/lottery`）。

## 说明

本项目源码源自独立仓库 `D:\Code\8000000`，此处为集成到 love5000 的部署副本；
分析代码与数据完全一致，差异仅在入口端口（`5179`）、服务脚本 `server.py` 与构建目标
（只重建操作台，不重建 16 张图和报告，因此不依赖 scipy / matplotlib）。
