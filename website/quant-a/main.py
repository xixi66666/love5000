"""quant-a A 股量化研究台的 FastAPI 应用入口。

对外暴露的表面：`web/` 下的工作台单页（`GET /` 与 `/static/*`）以及
`quant/api/routes.py` 注册的 `/api/**` 路由——健康检查、运行状态、数据同步、
评分与回测。默认以 `python -m uvicorn main:app --host 127.0.0.1 --port 5175`
启动，`website` 通过 `http://127.0.0.1:5175/api/health` 复用或拉起本服务。

数据来源与边界：行情/估值/财务统一来自 `quant.providers` 中按 `configs/app.yaml`
选择的 Provider，本地 DuckDB 与配置都留在 `website/quant-a/` 内，不写入
`website/python-a/obsidian-vault/`。上游请求的超时与降级由各 Provider 负责；
评分与回测只输出研究排序和历史模拟结果，不给出确定性的买卖结论，回测报告另附
`known_biases` 偏差披露。
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from quant.api.routes import router

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

app = FastAPI(title="quant-a", version="0.1.0")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
app.include_router(router)


@app.get("/", response_class=HTMLResponse)
def workbench():
    """返回量化研究工作台单页。

    Returns:
        `web/index.html` 的完整文本，页面再按相对路径加载 `/static/app.js` 与
        `/static/styles.css`；文件缺失时抛 `FileNotFoundError`，由 FastAPI 转成 500。
    """
    return (WEB_DIR / "index.html").read_text(encoding="utf-8")
