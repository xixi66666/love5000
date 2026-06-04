from threading import Lock
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from quant.common.config import load_app_config
from quant.common.response import failure, success
from quant.services.pipeline import QuantPipeline

router = APIRouter(prefix="/api")
daily_sync_lock = Lock()


class SyncRequest(BaseModel):
    start_date: str
    end_date: str
    index_codes: List[str]
    force: bool = False


class ScoreRequest(BaseModel):
    trade_date: str
    index_codes: List[str]


class BacktestRequest(BaseModel):
    start_date: str
    end_date: str
    index_codes: List[str]
    initial_cash: float


def get_pipeline() -> QuantPipeline:
    return QuantPipeline()


def run_daily_sync_task():
    return _run_daily_sync


def _run_daily_sync(pipeline: QuantPipeline, request: SyncRequest) -> None:
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
    return success({
        "service": "quant-a",
        "status": "ok",
        "port": 5175,
    })


@router.get("/status")
def status(pipeline: QuantPipeline = Depends(get_pipeline)):
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
    return success(pipeline.sync_data(request.start_date, request.end_date, request.index_codes))


@router.post("/data/sync-daily")
def sync_data_daily(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    pipeline: QuantPipeline = Depends(get_pipeline),
    daily_sync_task=Depends(run_daily_sync_task),
):
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
    try:
        return success(pipeline.run_scores(request.trade_date, request.index_codes))
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=failure(str(exc)),
        )


@router.post("/backtests/run")
def run_backtest(request: BacktestRequest, pipeline: QuantPipeline = Depends(get_pipeline)):
    return success(pipeline.run_backtest(
        request.start_date,
        request.end_date,
        request.index_codes,
        request.initial_cash,
    ))
