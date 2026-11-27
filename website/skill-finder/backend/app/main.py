"""skill-finder 服务入口（FastAPI，默认端口 5177）。

一个进程同时提供三件事：``/api/v1`` 业务路由、统一健康检查 ``/api/health``
（``success=true`` + ``service=skill-finder``，供 website 巡检），以及
``frontend/dist`` 的静态托管（``/assets`` 挂载 + SPA fallback + 路径穿越防护）。

未匹配的 ``/api/**`` 始终返回 404，不会被前端 fallback 吞掉；``dist`` 未构建时
根路径返回 503 并提示先执行 ``npm run build``。调度器只在
``settings.scheduler_enabled`` 为真时启动，并由 lifespan 负责关闭。
"""
import mimetypes
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import (
    ApiError,
    api_error_handler,
    http_exception_handler,
    internal_error_handler,
)
from app.api.v1 import (
    admin,
    collections,
    daily_reports,
    health,
    last30days,
    repositories,
    stats,
    template_editor,
)
from app.core.config import settings
from app.core.scheduler import start_scheduler

# Python 的 mimetypes 在 Windows 会读注册表，注册表常把 .js 标成 text/plain，
# 浏览器对 <script type="module"> 做严格 MIME 校验后直接拒绝执行，表现为页面黑屏。
# 这两行必须在任何静态文件响应前生效；test_health.py 中的 MIME 断言覆盖该回归，不要删除。
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")

# parents[2] 是 skill-finder 目录；dist 是 npm run build 的产物，不提交仓库。
FRONTEND_DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期：按配置启动调度器，关闭时优雅停止。

    调度器默认不启用（``scheduler_enabled=False``），因此本机开发与 pytest 都不会
    在后台发起真实网络请求；启用时延迟导入 APScheduler，未安装依赖也不影响启动。

    Yields:
        控制权交回 FastAPI，应用运行期间保持挂起。
    """
    scheduler = start_scheduler() if settings.scheduler_enabled else None
    yield
    if scheduler is not None:
        scheduler.shutdown()


# 应用实例：lifespan 负责调度器的启停，路由与异常处理器在下面统一注册。
app = FastAPI(title="Skill Finder API", lifespan=lifespan)


@app.get("/api/health")
async def service_health() -> dict[str, object]:
    """统一健康检查。

    请求：``GET /api/health``。
    响应：200 ``{"success": true, "service": "skill-finder"}``；website 的巡检要求
    顶层布尔 ``success=true`` 且 ``service`` 稳定，因此这两个字段不能改名。
    不检查数据库与 GitHub，数据库故障时仍为 200（避免被巡检当成“进程挂了”）。
    """
    return {"success": True, "service": "skill-finder"}


# 所有业务路由统一挂在 /api/v1；各模块自己的 prefix（如 /admin、/repositories）叠加在后。
app.include_router(health.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(collections.router, prefix="/api/v1")
app.include_router(repositories.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")
app.include_router(last30days.router, prefix="/api/v1")
app.include_router(template_editor.router, prefix="/api/v1")
app.include_router(daily_reports.router, prefix="/api/v1")

# 三类错误各自收敛成统一错误体；最后的 Exception 处理器保证兜底响应不含敏感信息。
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(Exception, internal_error_handler)


# 与 API 同源托管前端构建产物：只在 dist/assets 存在时挂载，
# 未构建时根路径走下面的 503 提示，而不是启动失败。
if (FRONTEND_DIST_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="frontend-assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    """SPA fallback：静态文件存在就返回文件，否则回 ``index.html``。

    三条约束：① ``api`` 前缀一律 404，不能让拼错的接口被 index.html 掩盖；
    ② ``dist`` 未构建时回 503 并给出构建命令；③ 解析后的路径必须仍在 ``dist`` 内，
    否则 404——否则 ``../`` 形式的路径可以读到仓库里的其他文件。

    Args:
        full_path: 通配的请求路径（不含前导斜杠）。

    Raises:
        HTTPException: ``/api/**`` 与非法的越界路径返回 404，前端未构建返回 503。
    """
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")

    index_file = FRONTEND_DIST_DIR / "index.html"
    if not index_file.is_file():
        raise HTTPException(
            status_code=503,
            detail=(
                "Frontend build not found. Run 'npm install && npm run build' in "
                "website/skill-finder/frontend first."
            ),
        )

    dist_root = FRONTEND_DIST_DIR.resolve()
    if full_path:
        candidate = (FRONTEND_DIST_DIR / full_path).resolve()
        try:
            candidate.relative_to(dist_root)
        except ValueError:
            raise HTTPException(status_code=404, detail="Not Found")
        if candidate.is_file():
            return FileResponse(candidate)

    return FileResponse(index_file)
