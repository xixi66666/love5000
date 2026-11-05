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
- **研究报告**：`output/report.html`（本地生成，含 16 张图与全部检验/回测结果）。

## 前后端

纯 Python 标准库 + numpy / pandas / requests，无 npm 构建：

| 文件 | 职责 |
|---|---|
| `server.py` | 本地服务：静态托管、`/api/health`、`/api/status`、`/api/update` |
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

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查，返回 `success=true` 与数据截止期次 |
| GET | `/api/status` | 当前数据期次与产物时间 |
| POST | `/api/update` | 增量更新，纯文本流式返回日志，末尾 `__DONE__ {...}` |
| GET | `/` | 操作台页面 |

`/api/update` 需要请求头 `X-Console: 1` 且同一时间只允许一个任务（并发返回 429）。

## 说明

本项目源码源自独立仓库 `D:\Code\8000000`，此处为集成到 love5000 的部署副本；
分析代码与数据完全一致，差异仅在入口端口（`5179`）、服务脚本 `server.py` 与构建目标
（只重建操作台，不重建 16 张图和报告，因此不依赖 scipy / matplotlib）。
