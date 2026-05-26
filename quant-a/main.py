from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from quant.api.routes import router

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

app = FastAPI(title="quant-a", version="0.1.0")
app.include_router(router)


@app.get("/", response_class=HTMLResponse)
def workbench():
    return (WEB_DIR / "index.html").read_text(encoding="utf-8")
