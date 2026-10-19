from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from filelock import FileLock, Timeout
from pydantic import BaseModel, Field

from app.api.v1.daily_reports import require_daily_admin
from app.daily import store, templates

router = APIRouter(prefix="/daily-reports/template", tags=["template-editor"])


class Restore(BaseModel):
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")


@router.get("", dependencies=[Depends(require_daily_admin)])
def get_template() -> dict:
    return templates.document()


def editor_lock() -> FileLock:
    return FileLock(str(templates.root() / ".editor.lock"), timeout=0)


def compile_error(error: templates.CompilationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"code": "TEMPLATE_COMPILE_FAILED",
                        "message": "模板未通过编译，请检查标注位置。", "diagnostics": error.diagnostics})


@router.post("/preview", dependencies=[Depends(require_daily_admin)])
def preview_template(body: templates.Draft):
    try:
        with editor_lock():
            _, metadata = templates.compile_draft(body)
            return metadata
    except Timeout:
        raise HTTPException(409, "Another template compilation is running") from None
    except templates.CompilationError as error:
        return compile_error(error)
    except (OSError, RuntimeError, ValueError):
        raise HTTPException(503, "Template preview unavailable; check Node and renderer dependencies") from None


@router.put("", dependencies=[Depends(require_daily_admin)])
def save_template(body: templates.Draft):
    try:
        with store.lock(), editor_lock():
            return templates.save(body)
    except Timeout:
        raise HTTPException(409, "A daily task or template compilation is running") from None
    except FileExistsError:
        raise HTTPException(409, "Template changed; reload the current version") from None
    except templates.CompilationError as error:
        return compile_error(error)
    except (OSError, RuntimeError, ValueError):
        raise HTTPException(422, "Template runtime check failed; current active version is unchanged") from None


@router.post("/restore", dependencies=[Depends(require_daily_admin)])
def restore_template(body: Restore):
    try:
        with store.lock(), editor_lock():
            return templates.restore(body.revision, body.expected_revision)
    except Timeout:
        raise HTTPException(409, "A daily task or template compilation is running") from None
    except FileExistsError:
        raise HTTPException(409, "Template changed; reload the current version") from None
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Template version not found or invalid") from None


@router.get("/previews/{preview_id}/{filename:path}")
def preview_file(preview_id: str, filename: str, request: Request):
    # 随机能力地址仅开放编译结果与已复制媒体；源码、配置和版本数据不在白名单。
    if not re.fullmatch(r"[a-f0-9]{32}", preview_id) or not (
        filename in {"index.html", "app.js"}
        or re.fullmatch(r"media/\d+\.(wav|mp3|mp4|png|jpg|jpeg|ttc|ttf)", filename)
    ):
        raise HTTPException(404, "Preview file not found")
    project = templates.root() / "previews" / preview_id
    target_root = (project / "preview").resolve()
    path = (target_root / filename).resolve()
    if not path.is_relative_to(target_root) or not path.is_file() or not (project / "preview.json").is_file():
        raise HTTPException(404, "Preview file not found")
    origin = f"{request.url.scheme}://{request.url.netloc}"
    headers = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
               "Access-Control-Allow-Origin": "*", "X-Content-Type-Options": "nosniff",
               "Content-Security-Policy": f"default-src 'none'; script-src {origin}; style-src 'unsafe-inline'; "
               f"img-src {origin} data: blob:; media-src {origin} blob:; font-src {origin} data:; "
               f"connect-src {origin}; worker-src blob:; frame-src 'none'; form-action 'none'; base-uri 'none'"}
    return FileResponse(path, headers=headers, media_type="text/javascript" if filename == "app.js" else None)
