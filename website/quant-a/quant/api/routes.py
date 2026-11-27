"""quant-a 的 HTTP 接口层（前缀 `/api`，由 `main.py` 挂载）。

接口分三类：健康与状态（`/health`、`/status`）、数据同步（`/data/sync`、
`/data/sync-daily` 及其后台批量流程）、研究与回测（`/scores/run`、
`/backtests/run`）。响应统一由 `quant.common.response.success` / `failure` 组装：
成功为 `{success, data, message}`，失败为 `{success, message}`；`/health` 另外把
`service` 提到顶层，供 `website` 的 `ServiceHealthChecker` 判定健康。

数据与降级：路由不直接访问上游，行情请求全部经 `QuantPipeline` 与 Provider，
超时和降级由 Provider 负责；本地数据不足时 `run_scores` 返回 HTTP 400 和中文原因。
同步接口会整表替换 DuckDB 数据，属于破坏性操作；评分与回测只用于研究，
不构成投资建议。
"""

from threading import Lock
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from quant.common.config import load_app_config
from quant.common.response import failure, success
from quant.services.pipeline import QuantPipeline

router = APIRouter(prefix="/api")
# 保护"全市场批量补行情"这一后台任务：只允许一轮在跑，抢锁失败时接口立即返回 syncing。
# 锁由后台任务在 finally 中释放，因此任务异常不会把锁永久占住。
daily_sync_lock = Lock()


class SyncRequest(BaseModel):
    """同步请求。

    Attributes:
        start_date: 区间起（含），`YYYY-MM-DD`。
        end_date: 区间止（含），`YYYY-MM-DD`；同时作为指数成分的查询日。
        index_codes: 指数代码列表；`FULL_MARKET`/`ALL` 表示全市场。
        force: 为真时忽略当天已存在的数据快照，强制重新同步。
    """

    start_date: str
    end_date: str
    index_codes: List[str]
    force: bool = False


class ScoreRequest(BaseModel):
    """评分请求。

    Attributes:
        trade_date: 评分交易日，`YYYY-MM-DD`；本地必须有该日之前（含）的行情、
            估值与财务数据，否则返回 400。
        index_codes: 选股池的指数代码，或 `FULL_MARKET`/`ALL`。
    """

    trade_date: str
    index_codes: List[str]


class BacktestRequest(BaseModel):
    """回测请求。

    Attributes:
        start_date: 回测区间起（含），`YYYY-MM-DD`。
        end_date: 回测区间止（含）；区间内月末信号在下一交易日成交，若超出该日则丢弃。
        index_codes: 选股池的指数代码，或 `FULL_MARKET`/`ALL`。
        initial_cash: 初始资金，单位人民币元。
    """

    start_date: str
    end_date: str
    index_codes: List[str]
    initial_cash: float


def get_pipeline() -> QuantPipeline:
    """FastAPI 依赖：为每个请求构造流水线。

    每次调用都会按 `configs/app.yaml` 新建 Provider 与 DuckDB 连接，因此测试可以用
    `app.dependency_overrides[get_pipeline]` 注入临时目录的流水线，避免污染本地数据。

    Returns:
        新构造的 `QuantPipeline`；配置缺失或 DuckDB 无法打开时抛异常，由 FastAPI
        转成 500。
    """
    return QuantPipeline()


def run_daily_sync_task():
    """FastAPI 依赖：返回真正执行后台同步的函数。

    这层间接让测试可以覆盖 `app.dependency_overrides[run_daily_sync_task]`，
    用假任务替代真实的全市场抓取，从而不联网、不长时间占用锁。

    Returns:
        `_run_daily_sync` 函数对象本身，供 `BackgroundTasks` 以参数调用。
    """
    return _run_daily_sync


def _run_daily_sync(pipeline: QuantPipeline, request: SyncRequest) -> None:
    """后台执行"股票池 + 分批行情"的完整同步。

    先做一次快速同步写入股票池、日历、财务与成分，再循环调用
    `sync_market_data_batch` 直到 `remaining_count == 0`。分批是为了让单次外部请求
    可控，也便于前端轮询看到进度。

    失败路径：任何一步抛异常都会中断循环，但 `finally` 一定释放 `daily_sync_lock`，
    已经写入的批次不回滚——下一次同步会按"缺行情/缺估值"重新挑出未完成的代码。

    Args:
        pipeline: 执行同步的流水线。
        request: 同步区间、指数池与是否强制重跑。
    """
    try:
        pipeline.sync_data_daily_fast(
            request.start_date,
            request.end_date,
            request.index_codes,
            force=request.force,
        )
        while True:
            result = pipeline.sync_market_data_batch(request.start_date, request.end_date)
            if result["remaining_count"] == 0:
                break
    finally:
        daily_sync_lock.release()


@router.get("/health")
def health():
    """健康检查。

    Returns:
        `success` 为真、`data` 里带服务名/状态/端口，并把 `service` 复制到顶层。
        `website` 的健康巡检只读顶层 `success` 与 `service`，端口字段固定 5175，
        与实际监听端口解耦（便于反向代理场景）。
    """
    return {
        **success({
            "service": "quant-a",
            "status": "ok",
            "port": 5175,
        }),
        "service": "quant-a",
    }


@router.get("/status")
def status(pipeline: QuantPipeline = Depends(get_pipeline)):
    """返回运行状态与本地数据完整性。

    Args:
        pipeline: 依赖注入的流水线，用于统计各表行数与可评分股票数。

    Returns:
        `data` 含服务名、当前 Provider、模型/配置版本、存储配置，以及
        `data_integrity`（各表计数、行情与估值补齐进度、最近可评分日期、
        `score_ready` 和阻断原因）。只读，不改动任何数据。
    """
    config = load_app_config()
    return success({
        "service": config["app"]["name"],
        "provider": config["provider"]["active"],
        "model_version": config["versions"]["model_version"],
        "config_version": config["versions"]["config_version"],
        "storage": config["storage"],
        "data_integrity": pipeline.data_integrity(),
    })


@router.post("/data/sync")
def sync_data(request: SyncRequest, pipeline: QuantPipeline = Depends(get_pipeline)):
    """一次性全量同步（会清空并重写本地表）。

    日历与行情按传入区间拉取，股票基础、财务与指数成分则是一次全量快照；
    每张表都用 `replace_table` 覆盖（事务内清空再插入）。全市场抓取可能耗时很久，
    页面上的日常刷新应改用 `/data/sync-daily`。

    Args:
        request: 同步区间与指数池。
        pipeline: 依赖注入的流水线。

    Returns:
        `data` 含 `data_version` 与各表写入行数。

    Raises:
        Exception: Provider 的上游异常不在这里捕获，直接由 FastAPI 转成 500。
    """
    return success(pipeline.sync_data(request.start_date, request.end_date, request.index_codes))


@router.post("/data/sync-daily")
def sync_data_daily(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    pipeline: QuantPipeline = Depends(get_pipeline),
    daily_sync_task=Depends(run_daily_sync_task),
):
    """启动（或复用）当天的增量同步，结果写回后台。

    三条返回路径：
    1. 当天快照已完整且未强制刷新：直接返回 `status=cached`，不启动后台任务；
    2. 已有另一轮同步在跑（拿不到 `daily_sync_lock`）：返回 `status=syncing`，
       不重复排队；
    3. 其余情况：注册后台任务并返回 `status=syncing`；若存在不完整快照，则额外带上
       行情/估值的补齐进度，并通过 `cache_hit=true` 说明"用的是旧快照但还在补"。

    Args:
        request: 同步区间、指数池与 `force`。
        background_tasks: FastAPI 后台任务容器，响应返回后才执行。
        pipeline: 依赖注入的流水线。
        daily_sync_task: 后台任务函数；测试可覆盖依赖注入假任务。

    Returns:
        `data` 至少含 `status`、`cache_hit`、`message`；命中快照时还含同步版本与
        各表计数。
    """
    cached_snapshot = pipeline.daily_sync_snapshot()
    if cached_snapshot and not request.force and cached_snapshot.get("status") == "cached":
        return success(cached_snapshot)

    if not daily_sync_lock.acquire(blocking=False):
        return success({
            "status": "syncing",
            "cache_hit": False,
            "message": "今日数据同步正在执行，请稍后查看。",
        })

    background_tasks.add_task(daily_sync_task, pipeline, request)
    if cached_snapshot and not request.force:
        return success({
            **cached_snapshot,
            "status": "syncing",
            "cache_hit": True,
            "message": "本地快照存在，但行情或估值尚未补齐，已继续后台同步。",
        })

    return success({
        "status": "syncing",
        "cache_hit": False,
        "message": "今日数据同步已启动，请稍后查看。",
    })


@router.post("/scores/run")
def run_scores(request: ScoreRequest, pipeline: QuantPipeline = Depends(get_pipeline)):
    """对指定交易日运行选股池、因子与评分。

    Args:
        request: 交易日与指数池。
        pipeline: 依赖注入的流水线。

    Returns:
        成功时 `data` 含 `trade_date` 与按总分降序的 `scores`（含维度分、排名、
        数据/模型版本）。评分只用于研究排序，不构成买入建议。

    Raises:
        ValueError: 本地数据不足（缺行情/估值/财务）时由流水线抛出，被捕获后转为
            HTTP 400 与 `{success: false, message}`；其他异常不捕获，返回 500。
    """
    try:
        return success(pipeline.run_scores(request.trade_date, request.index_codes))
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=failure(str(exc)),
        )


@router.post("/backtests/run")
def run_backtest(request: BacktestRequest, pipeline: QuantPipeline = Depends(get_pipeline)):
    """按月末调仓运行回测并生成报告。

    Args:
        request: 回测区间、指数池与初始资金（元）。
        pipeline: 依赖注入的流水线。

    Returns:
        `data` 含三部分：`backtest`（`nav` 净值曲线、`orders` 成交明细、
        `holdings` 期末持仓）、`report`（收益、最大回撤、偏差披露）与
        `skipped_score_dates`（因本地数据不足而被跳过的月末信号及原因）。

    Raises:
        Exception: 缺少成交价等错误不被捕获，由 FastAPI 转成 500；`run_backtest`
            只对评分阶段的 `ValueError` 做跳过处理。
    """
    return success(pipeline.run_backtest(
        request.start_date,
        request.end_date,
        request.index_codes,
        request.initial_cash,
    ))
