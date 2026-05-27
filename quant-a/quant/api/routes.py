from threading import Lock
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel

from quant.common.config import load_app_config
from quant.common.response import success
from quant.services.pipeline import QuantPipeline

router = APIRouter(prefix="/api")
daily_sync_lock = Lock()


class SyncRequest(BaseModel):
    start_date: str
    end_date: str
    index_codes: List[str]


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
        pipeline.sync_data_daily(request.start_date, request.end_date, request.index_codes)
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
def status():
    config = load_app_config()
    return success({
        "service": config["app"]["name"],
        "provider": config["provider"]["active"],
        "model_version": config["versions"]["model_version"],
        "config_version": config["versions"]["config_version"],
        "storage": config["storage"],
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
    if cached_snapshot:
        return success(cached_snapshot)

    if not daily_sync_lock.acquire(blocking=False):
        return success({
            "status": "syncing",
            "cache_hit": False,
            "message": "今日数据同步正在执行，请稍后查看。",
        })

    background_tasks.add_task(daily_sync_task, pipeline, request)
    return success({
        "status": "syncing",
        "cache_hit": False,
        "message": "今日数据同步已启动，请稍后查看。",
    })


@router.post("/scores/run")
def run_scores(request: ScoreRequest, pipeline: QuantPipeline = Depends(get_pipeline)):
    return success(pipeline.run_scores(request.trade_date, request.index_codes))


@router.post("/backtests/run")
def run_backtest(request: BacktestRequest, pipeline: QuantPipeline = Depends(get_pipeline)):
    return success(pipeline.run_backtest(
        request.start_date,
        request.end_date,
        request.index_codes,
        request.initial_cash,
    ))
