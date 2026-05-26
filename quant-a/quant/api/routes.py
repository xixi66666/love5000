from fastapi import APIRouter

from quant.common.response import success

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return success({
        "service": "quant-a",
        "status": "ok",
        "port": 5175,
    })
