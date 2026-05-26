from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from quant.common.config import load_app_config
from quant.common.response import success
from quant.services.pipeline import QuantPipeline

router = APIRouter(prefix="/api")
pipeline = QuantPipeline()


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
def sync_data(request: SyncRequest):
    return success(pipeline.sync_data(request.start_date, request.end_date, request.index_codes))


@router.post("/scores/run")
def run_scores(request: ScoreRequest):
    return success(pipeline.run_scores(request.trade_date, request.index_codes))


@router.post("/backtests/run")
def run_backtest(request: BacktestRequest):
    return success(pipeline.run_backtest(
        request.start_date,
        request.end_date,
        request.index_codes,
        request.initial_cash,
    ))
