"""日报视频模板编辑器端点（``/api/v1/daily-reports/template``）。

提供四件事：读取当前模板源码、编译预览、保存启用、回滚到历史版本，另外还有
只读的预览产物下载。除预览下载外的接口都要求 ``X-Admin-Key`` 且仅允许 HTTPS 或本机连接
（复用 :func:`app.api.v1.daily_reports.require_daily_admin`）。

并发控制用两把锁：``store.lock()`` 与模板目录下的非阻塞 ``.editor.lock``。
拿不到锁回 409，编译失败回 422 并带诊断信息，Node/渲染依赖缺失回 503——
保存失败时当前生效版本保持不变，不会因为一次编译错误把线上模板改坏。
"""
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
    """回滚请求体。

    ``revision`` 是要恢复的历史版本摘要，``expected_revision`` 是客户端以为的当前版本。
    两者都由前端原样回传，服务端用 ``expected_revision`` 做乐观并发校验：
    版本已被别人改过时抛 ``FileExistsError`` 并回 409，避免覆盖他人保存。
    """

    engine: templates.Engine = "remotion"
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")


@router.get("", dependencies=[Depends(require_daily_admin)])
def get_template(engine: templates.Engine | None = None) -> dict:
    """读取当前生效的模板源码与版本信息。

    请求：``GET /api/v1/daily-reports/template?engine=remotion|hyperframes``。
    响应：``templates.document`` 的字典（源码、可编辑文件清单、当前版本摘要）。

    Raises:
        HTTPException: 模板文件缺失、版本元数据损坏或引擎名未知时返回 503，
            提示当前引擎的模板文件不可用，而不是抛出未处理异常。
    """
    try:
        return templates.document(engine)
    except (OSError, ValueError, KeyError):
        raise HTTPException(503, "Template files unavailable for the selected engine") from None


def editor_lock(engine: templates.Engine) -> FileLock:
    """返回模板目录上的非阻塞互斥锁句柄。

    ``timeout=0`` 表示立即失败：两个编译/保存请求同时到达时，后来的请求直接得到
    :class:`filelock.Timeout` 并回 409，不会排队等待长时间的类型检查与渲染。
    锁文件放在模板目录内，按引擎天然隔离。

    Args:
        engine: 目标渲染引擎，决定锁文件所在目录。

    Returns:
        尚未获取的 FileLock；调用方用 ``with`` 语句获取并自动释放。
    """
    return FileLock(str(templates.root(engine) / ".editor.lock"), timeout=0)


def compile_error(error: templates.CompilationError) -> JSONResponse:
    """把编译错误转成 422 响应，供编辑器定位到具体行列。

    Returns:
        状态码 422、``code`` 为 ``TEMPLATE_COMPILE_FAILED``、并带 ``diagnostics``
        列表的 JSONResponse；诊断只含编译器输出的位置与原因。
    """
    return JSONResponse(status_code=422, content={"code": "TEMPLATE_COMPILE_FAILED",
                        "message": "模板未通过编译，请检查标注位置。", "diagnostics": error.diagnostics})


@router.post("/preview", dependencies=[Depends(require_daily_admin)])
def preview_template(body: templates.Draft):
    """编译未保存的模板草稿并返回预览元数据。

    请求：``POST /api/v1/daily-reports/template/preview``，体为 ``templates.Draft``
    （引擎 + 被修改的源码文件）。
    响应：编译成功时返回预览元数据（预览地址、时长等）；预览产物隔离在带随机
    能力地址的目录下，不覆盖当前生效版本。

    Raises:
        HTTPException: 409 另一个编译正在进行或版本已变化；422 编译失败（带诊断）；
            503 Node 或渲染依赖不可用。
    """
    try:
        with editor_lock(body.engine):
            _, metadata = templates.compile_draft(body)
            return metadata
    except Timeout:
        raise HTTPException(409, "Another template compilation is running") from None
    except FileExistsError:
        raise HTTPException(409, "Template changed; reload the current version") from None
    except templates.CompilationError as error:
        return compile_error(error)
    except (OSError, RuntimeError, ValueError):
        raise HTTPException(503, "Template preview unavailable; check Node and renderer dependencies") from None


@router.put("", dependencies=[Depends(require_daily_admin)])
def save_template(body: templates.Draft):
    """保存并启用新模板版本。

    请求：``PUT /api/v1/daily-reports/template``，体为 ``templates.Draft``。
    响应：保存成功后的模板文档与版本摘要。

    先拿 ``store.lock()`` 再拿模板锁，防止与日报任务或其他编辑同时改动数据目录；
    保存前会做类型检查、打包与一帧真实渲染，全部通过才原子切换生效版本。
    新版本只影响后续生成的成片，已有成片与审核结论不变。

    Raises:
        HTTPException: 409 有日报任务或编译在跑、版本已变化；422 运行时自检失败
            （此时当前生效版本保持原样）；503 依赖不可用。
    """
    try:
        with store.lock(), editor_lock(body.engine):
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
    """回滚到指定的历史模板版本。

    请求：``POST /api/v1/daily-reports/template/restore``，体为 :class:`Restore`。
    响应：恢复后的模板文档与版本摘要。

    Raises:
        HTTPException: 409 锁被占用或 ``expected_revision`` 已过期；404 目标版本不存在
            或摘要格式非法。
    """
    try:
        with store.lock(), editor_lock(body.engine):
            return templates.restore(body.revision, body.expected_revision, body.engine)
    except Timeout:
        raise HTTPException(409, "A daily task or template compilation is running") from None
    except FileExistsError:
        raise HTTPException(409, "Template changed; reload the current version") from None
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Template version not found or invalid") from None


@router.get("/previews/{preview_id}/{filename:path}")
def legacy_preview_file(preview_id: str, filename: str, request: Request):
    """兼容旧版预览地址（不带引擎段），固定按 remotion 解析。

    请求：``GET /api/v1/daily-reports/template/previews/{preview_id}/{filename}``。
    响应：转发到 :func:`preview_file`，校验与响应头完全一致。
    """
    return preview_file(preview_id, filename, request, "remotion")


@router.get("/engines/{engine}/previews/{preview_id}/{filename:path}")
def preview_file(preview_id: str, filename: str, request: Request, engine: templates.Engine):
    """下载一次编译产生的预览产物（HTML / JS / 固化媒体）。

    请求：``GET /api/v1/daily-reports/template/engines/{engine}/previews/{preview_id}/{filename}``。
    响应：文件流；``app.js`` 以 ``text/javascript`` 返回，其余由文件名推断类型。

    该地址不要求管理密钥（编译器需要直接加载资源），因此改用随机能力地址：
    ``preview_id`` 必须是 32 位十六进制，``filename`` 只能落在白名单内，
    解析后还要确认仍在预览目录中，防止路径穿越读到源码或配置。
    响应头固定加 ``no-store`` 与严格 CSP，只允许从当前源加载脚本、媒体与字体。

    Raises:
        HTTPException: 标识或文件名不合规、文件不存在、预览元数据缺失时统一 404，
            不区分具体原因以免被用来探测目录结构。
    """
    # 随机能力地址仅开放编译结果与已复制媒体；源码、配置和版本数据不在白名单。
    if not re.fullmatch(r"[a-f0-9]{32}", preview_id) or not (
        filename in {"index.html", "app.js"}
        or re.fullmatch(r"media/\d+\.(wav|mp3|mp4|png|jpg|jpeg|ttc|ttf)", filename)
    ):
        raise HTTPException(404, "Preview file not found")
    project = templates.root(engine) / "previews" / preview_id
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
