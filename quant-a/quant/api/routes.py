from fastapi import APIRouter

from quant.common.config import load_app_config
from quant.common.response import success

router = APIRouter(prefix="/api")


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
