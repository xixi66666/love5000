"""可视化爬虫工作台的 FastAPI 入口。

一个进程同时提供 REST API 与前端构建产物：默认监听 127.0.0.1:5176，
``frontend/dist`` 存在时把 ``/assets`` 挂成静态目录，其余非 ``/api`` 路径走 SPA
fallback 返回 ``index.html``。

公开接口（全部无鉴权，仅建议在本机回环地址使用）：

- ``GET /api/health``：统一健康检查，返回 ``{"success": true, "service": "scrapling-ui"}``。
- ``POST /api/session/start`` / ``action`` / ``update-history`` / ``close`` /
  ``query-selector``：浏览器会话的开始、交互、历史重放、关闭与选择器探测。
- ``POST /api/generate-code`` / ``run-code``：把历史编译成 Scrapling 配方、执行配方。
- ``POST /api/ai/heal-selector``：请求统一文本模型修复失效选择器。
- ``GET|POST /api/todo``：读写路线图面板。
- ``GET|POST /api/scheduler/jobs``、``POST /api/scheduler/jobs/{id}/toggle``、
  ``DELETE /api/scheduler/jobs/{id}``、``POST /api/scheduler/jobs/{id}/run``：
  定时任务增删改查与手动触发。

持久化：调度任务写入 ``backend/jobs.db``（见 `core.db`），路线图写入项目根的
``todo_list.md``（可用 ``SCRAPLING_TODO_PATH`` 覆盖）。

失败行为：业务异常统一映射成 ``HTTPException`` 的 ``detail``，除 ``/api/health``
外的会话类接口在会话不存在时返回 404；未匹配的 ``/api/**`` 一律返回 JSON 404，
不会被 SPA fallback 吞掉；``frontend/dist`` 未构建时根路径返回 503 并提示构建命令。
"""

import mimetypes
import os
import uuid
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

# Windows sometimes registers ".js" as "text/plain" (HKEY_CLASSES_ROOT\.js
# Content Type), which blocks ES module scripts under strict MIME checking.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")

# Local module imports
from models import (
    StartSessionRequest,
    ActionRequest,
    CloseSessionRequest,
    GenerateCodeRequest,
    UpdateHistoryRequest,
    RunCodeRequest,
    TodoListUpdateRequest,
    QuerySelectorRequest,
    SaveJobRequest,
    ToggleJobRequest,
    HealSelectorRequest
)
from core.browser_manager import pw_manager
from core.session import Session, active_sessions
from services.code_generator import generate_scrapling_code
from services.code_runner import execute_run_code
from core.db import get_all_jobs, get_job, save_job, delete_job, update_job_enabled
from services.scheduler import start_scheduler, stop_scheduler, run_crawler_job, sync_db_to_scheduler, scheduler
from services.deepseek_healer import heal_selector

@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务生命周期：启动浏览器与调度器，关闭时按相反顺序回收。

    启动阶段只拉起一个共享浏览器进程（不打开页面），真正的页面在
    ``/api/session/start`` 按需创建，因此空跑不会占用多余内存。

    关闭阶段先停调度器，再逐个关闭会话、清空 ``active_sessions``，最后关浏览器。
    某次会话关闭失败不会阻断后续清理（`Session.close` 自己吞异常）。
    """
    # Initialize Playwright browser manager
    await pw_manager.start()
    # Start background scheduler
    start_scheduler()
    yield
    # Stop background scheduler
    stop_scheduler()
    # Clean up active browser sessions
    for session in list(active_sessions.values()):
        await session.close()
    active_sessions.clear()
    # Close browser manager
    await pw_manager.stop()

app = FastAPI(lifespan=lifespan)

# Configure CORS Middleware
# 工作台前端与 API 同源，理论上不需要 CORS；这里全放开是为了让本机调试页面
# （例如 file:// 打开或换端口起的开发服务器）也能直接调接口。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 前端构建产物目录：backend 的上一级（即 scrapling-ui/frontend/dist）。
FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

@app.get("/api/health")
async def health():
    """``GET /api/health``：返回 ``{"success": true, "service": "scrapling-ui"}``。

    只表明进程与路由可用，不探测浏览器内核，也不触发启动；
    ``website`` 首页的统一健康巡检依赖这个固定响应。
    """
    return {"success": True, "service": "scrapling-ui"}

@app.post("/api/session/start")
async def start_session(req: StartSessionRequest):
    """``POST /api/session/start``：新建上下文与页面、按开关装拦截规则并打开首个 URL。

    请求体见 `models.StartSessionRequest`（``url`` 必填，``width``/``height`` 默认
    1280×800，三个开关默认开启）。响应为 `Session.get_state` 的完整状态：
    ``{session_id, screenshot, dom_tree, network_logs, history, scraped_data}``。

    失败路径：浏览器未初始化时返回 500；导航超时或建页失败时先关闭刚建的
    上下文、从 ``active_sessions`` 移除，再返回 500，避免留下僵尸会话。
    """
    if not pw_manager.browser:
        raise HTTPException(status_code=500, detail="Browser manager not initialized")
    
    session_id = str(uuid.uuid4())
    try:
        # Create a new context and page
        context = await pw_manager.browser.new_context(
            viewport={"width": req.width, "height": req.height},
            # 固定桌面 Chrome UA：部分站点会对 HeadlessChrome 直接返回不同页面。
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        session = Session(
            session_id, 
            pw_manager.browser, 
            context, 
            page,
            solve_cloudflare=req.solve_cloudflare,
            block_ads=req.block_ads,
            disable_resources=req.disable_resources
        )
        active_sessions[session_id] = session
        
        # Configure route blocking for Ad Blocking & Speed Mode
        if req.block_ads or req.disable_resources:
            async def route_filter(route, request):
                """页面路由过滤器：按开关中断资源请求，其余放行。

                极速模式优先命中（图片/媒体/字体/样式表），其次才是按域名关键词
                拦截广告与统计；两者都不命中时 ``route.continue_()``，
                漏掉这一步会让请求一直挂起直到超时。
                """
                url = request.url.lower()
                resource_type = request.resource_type
                
                # Speed Mode: block media, fonts, images, stylesheets
                if req.disable_resources and resource_type in ["image", "media", "font", "stylesheet"]:
                    await route.abort()
                # Ad Blocking: check simple ad-blocking patterns
                elif req.block_ads and any(ad_word in url for ad_word in ["googleads", "googlesyndication", "doubleclick", "adservice", "analytics", "telemetry"]):
                    await route.abort()
                else:
                    await route.continue_()
            
            await page.route("**/*", route_filter)
            
        # Add a default navigate step in history
        # 首个 navigate 必须先入历史，重放与代码生成都靠它确定入口网址。
        session.history.append({"action": "navigate", "url": req.url})
        
        await page.goto(req.url, wait_until="load", timeout=30000)
        
        return await session.get_state()
    except Exception as e:
        # Cleanup if failure occurs during start
        if session_id in active_sessions:
            await active_sessions[session_id].close()
            del active_sessions[session_id]
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")

@app.post("/api/session/action")
async def execute_action(req: ActionRequest):
    """``POST /api/session/action``：在已有页面上执行一个交互动作并返回新状态。

    请求体见 `models.ActionRequest`；``action_type`` 支持 click / fill / scroll /
    navigate / extract / back / forward / reload / extract_list / pagination。
    响应为 `Session.get_state` 的完整状态。

    失败路径：会话不存在 404；必填字段缺失或 ``max_pages`` 非整数 400；
    页面侧失败（选择器超时、导航失败）统一包成 500 ``Action failed: ...``。
    注意绝大多数动作是「先写历史再执行」，执行失败时该步仍留在历史里，
    需要前端再调 ``/api/session/update-history`` 回退。
    """
    session = active_sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    try:
        if req.action_type == "click":
            if not req.selector:
                raise HTTPException(status_code=400, detail="Selector required for click action")
            # Log action
            session.history.append({"action": "click", "selector": req.selector})
            # Click
            await session.page.click(req.selector, timeout=5000)
            
        elif req.action_type == "fill":
            if not req.selector or req.value is None:
                raise HTTPException(status_code=400, detail="Selector and value required for fill action")
            session.history.append({"action": "fill", "selector": req.selector, "value": req.value})
            await session.page.fill(req.selector, req.value, timeout=5000)
            
        elif req.action_type == "scroll":
            # Scroll relative to the page
            # 优先用字符串 value 当像素值（前端输入框直传），其次才用整数 y；
            # 解析失败静默退回默认 300px，不因为一个坏参数让整次操作 400。
            y_scroll = 300
            if req.value:
                try:
                    y_scroll = int(req.value)
                except ValueError:
                    pass
            elif req.y is not None:
                y_scroll = req.y
                
            session.history.append({"action": "scroll", "y": y_scroll})
            await session.page.evaluate(f"window.scrollBy(0, {y_scroll})")
            
        elif req.action_type == "navigate":
            if not req.value:
                raise HTTPException(status_code=400, detail="URL value required for navigate action")
            session.history.append({"action": "navigate", "url": req.value})
            await session.page.goto(req.value, wait_until="load", timeout=30000)
            
        elif req.action_type == "extract":
            if not req.selector or not req.extract_name or not req.extract_attribute:
                raise HTTPException(status_code=400, detail="Selector, extract_name, and extract_attribute required for extract action")
            # 单值提取只登记到历史，真正取值在 get_scraped_data 里做，
            # 这样撤销历史后不会残留已取出的数据。
            session.history.append({
                "action": "extract",
                "name": req.extract_name,
                "selector": req.selector,
                "attribute": req.extract_attribute
            })

        elif req.action_type == "extract_list":
            if not req.selector or not req.extract_name or not req.extract_attribute:
                raise HTTPException(status_code=400, detail="Selector, extract_name, and extract_attribute required for extract_list action")
            session.history.append({
                "action": "extract_list",
                "name": req.extract_name,
                "selector": req.selector,
                "attribute": req.extract_attribute
            })
            
        elif req.action_type == "back":
            session.history.append({"action": "back"})
            try:
                await session.page.go_back(timeout=5000)
            except Exception as e:
                # 无历史可退时 Playwright 会超时；这属于正常边界，不向调用方报错。
                print(f"Warning: go_back failed (likely no history): {e}")
            
        elif req.action_type == "forward":
            session.history.append({"action": "forward"})
            try:
                await session.page.go_forward(timeout=5000)
            except Exception as e:
                print(f"Warning: go_forward failed (likely no history): {e}")
            
        elif req.action_type == "reload":
            session.history.append({"action": "reload"})
            await session.page.reload(timeout=20000)
            
        elif req.action_type == "pagination":
            if not req.selector or not req.value:
                raise HTTPException(status_code=400, detail="Selector and max_pages value required for pagination action")
            try:
                max_pages = int(req.value)
            except ValueError:
                raise HTTPException(status_code=400, detail="max_pages must be an integer")
            
            session.history.append({
                "action": "pagination",
                "selector": req.selector,
                "max_pages": max_pages
            })
            await session.page.click(req.selector, timeout=5000)
            
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action type: {req.action_type}")
            
        return await session.get_state()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Action failed: {str(e)}")

@app.post("/api/session/update-history")
async def update_history(req: UpdateHistoryRequest):
    """``POST /api/session/update-history``：用前端编辑后的历史重放到页面。

    请求体为 ``{session_id, history}``，响应为 `Session.get_state`。
    重放会清空既有网络日志与历史，因此「撤销某一步」也走这个接口。

    失败路径：会话不存在 404；任一步骤失败时把原始异常消息作为 500 的 ``detail``
    直接返回（前端据此提示是哪一步的选择器失效）。
    """
    session = active_sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    try:
        await session.replay_history(req.history)
        return await session.get_state()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/session/close")
async def close_session(req: CloseSessionRequest):
    """``POST /api/session/close``：关闭页签与上下文并从注册表移除。

    请求体为 ``{session_id}``，响应 ``{"success": true}``。
    会话已不存在时返回 404；关闭过程中的浏览器异常由 `Session.close` 吞掉，
    这里始终按成功处理，保证前端可以无条件重开新会话。
    """
    session = active_sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    await session.close()
    del active_sessions[req.session_id]
    return {"success": True}

@app.post("/api/generate-code")
async def generate_code(req: GenerateCodeRequest):
    """``POST /api/generate-code``：把当前会话历史编译成可运行的 Scrapling 脚本。

    请求体为 ``{session_id}``，响应 ``{"code": "<python 源码>"}``；生成过程不触网、
    也不执行代码，只是字符串拼接（见 `services.code_generator`）。
    会话不存在时返回 404。
    """
    session = active_sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return {"code": generate_scrapling_code(session.history)}

@app.post("/api/run-code")
async def run_code(req: RunCodeRequest):
    """``POST /api/run-code``：在当前页面执行用户提交的配方代码。

    请求体为 ``{code, session_id?}``；带 ``session_id`` 时在进程内对着已有页面
    ``exec``，不带时另起子进程独立运行。响应为
    ``{stdout, stderr, exit_code, state}``，``state`` 在子进程模式下为 ``None``。

    失败路径：执行错误不会抛给路由，而是写进 ``stderr`` 并把 ``exit_code`` 置 1；
    只有子进程创建失败才返回 500。这里没有沙箱，等价于在本机执行任意 Python。
    """
    try:
        return await execute_run_code(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/session/query-selector")
async def query_selector(req: QuerySelectorRequest):
    """``POST /api/session/query-selector``：统计一个 CSS 选择器或 XPath 命中的可见元素。

    请求体为 ``{session_id, selector}``；以 ``/`` 开头或带 ``xpath=`` 前缀时按 XPath
    求值，否则按 CSS 求值。响应 ``{"matches": [{tag, classes, id, rect}...]}``，
    已过滤掉宽或高为 0 的隐藏元素，前端用这些矩形画选框。

    失败路径：会话不存在 404；脚本求值异常 500；选择器语法错误在 JS 内被捕获，
    返回空列表而不是报错。
    """
    session = active_sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    js_eval = """
    (selector) => {
        try {
            let elms = [];
            if (selector.startsWith('/') || selector.startsWith('xpath=')) {
                let xpath = selector.startsWith('xpath=') ? selector.substring(6) : selector;
                let result = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                for (let i = 0; i < result.snapshotLength; i++) {
                    elms.push(result.snapshotItem(i));
                }
            } else {
                elms = Array.from(document.querySelectorAll(selector));
            }
            return elms.map(el => {
                if (el.nodeType !== Node.ELEMENT_NODE) return null;
                const rect = el.getBoundingClientRect();
                return {
                    tag: el.tagName.toLowerCase(),
                    classes: Array.from(el.classList).join(' '),
                    id: el.id || '',
                    rect: {
                        x: Math.round(rect.left + (window.scrollX || window.pageXOffset || 0)),
                        y: Math.round(rect.top + (window.scrollY || window.pageYOffset || 0)),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height)
                    }
                };
            }).filter(e => e && e.rect.width > 0 && e.rect.height > 0);
        } catch (e) {
            return [];
        }
    }
    """
    try:
        matches = await session.page.evaluate(js_eval, req.selector)
        return {"matches": matches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@app.post("/api/ai/heal-selector")
async def ai_heal_selector(req: HealSelectorRequest):
    """``POST /api/ai/heal-selector``：请统一文本模型给出修复后的选择器。

    请求体为 ``{session_id, broken_selector, action_type}``；服务端先抓一段简化后的
    页面 HTML（最多 6000 字符）作为上下文，再交给 `services.deepseek_healer`。

    响应 ``{"healed_selector": str, "original": str}``；模型无法给出不同选择器时
    ``healed_selector`` 为 ``null`` 并附 ``detail`` 说明，前端据此提示手动修改。

    失败路径：会话不存在 404；模型未配置、网关失败或响应不可解析时返回 500
    ``AI healing failed: ...``（消息来自封装层，不含密钥）。
    """
    session = active_sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        healed = await heal_selector(
            broken_selector=req.broken_selector,
            action_type=req.action_type,
            page=session.page,
        )
        if healed:
            return {"healed_selector": healed, "original": req.broken_selector}
        return {"healed_selector": None, "original": req.broken_selector, "detail": "Could not determine a fix"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI healing failed: {str(e)}")

# 路线图文件位置：默认读 scrapling-ui/todo_list.md（backend 的上一级），
# 允许用 SCRAPLING_TODO_PATH 指到别处，便于测试或用别的仓库做演示。
TODO_FILE_PATH = os.environ.get(
    "SCRAPLING_TODO_PATH",
    os.path.join(os.path.dirname(__file__), "..", "todo_list.md")
)

@app.get("/api/todo")
async def get_todo_list():
    """``GET /api/todo``：把 ``todo_list.md`` 解析成 ``{"tasks": [...]}``。

    每个任务为 ``{title, checked, status, subtasks}``：主项来自形如
    ``- [x] **标题**`` 再跟一个反引号包裹的状态标记的行，子项来自其后的缩进列表行；
    ``status`` 缺省时按勾选状态推断 ``DONE`` / ``TODO`` 并转大写。

    Returns:
        任务列表；文件不存在或为空时返回 ``{"tasks": []}``，不报错。
        解析是逐行正则匹配，无法识别的行直接跳过，非约定格式的内容不会中断读取。
    """
    path = TODO_FILE_PATH
    if not os.path.exists(path):
        return {"tasks": []}
            
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        
    lines = content.split('\n')
    tasks = []
    current_task = None
    
    for line in lines:
        main_match = re.match(r'^\s*-\s*\[([ xX])\]\s*\*\*(.*?)\*\*(?:\s*`\[(.*?)\]`)?', line)
        if main_match:
            checked = main_match.group(1).lower() == 'x'
            title = main_match.group(2).strip()
            status = main_match.group(3) or ("DONE" if checked else "TODO")
            current_task = {
                "title": title,
                "checked": checked,
                "status": status.strip().upper(),
                "subtasks": []
            }
            tasks.append(current_task)
            continue
            
        if current_task is not None:
            sub_match = re.match(r'^\s+-\s*(?:\[([ xX])\]\s*)?(.*)', line)
            if sub_match:
                sub_checked = False
                if sub_match.group(1):
                    sub_checked = sub_match.group(1).lower() == 'x'
                text = sub_match.group(2).strip()
                current_task["subtasks"].append({
                    "text": text,
                    "checked": sub_checked
                })
                
    return {"tasks": tasks}

@app.post("/api/todo")
async def update_todo_list(req: TodoListUpdateRequest):
    """``POST /api/todo``：用请求体里的任务列表整体重写 ``todo_list.md``。

    请求体为 ``{"tasks": [{title, checked, status, subtasks}]}``；响应回显
    ``{"status": "success", "tasks": [...]}``。文件头、分隔符与「Active Work」
    段落是固定模板，正文由任务重新生成，所以手工写在别处的段落会被覆盖。

    失败路径：写盘异常（目录不可建、磁盘只读）只打印日志，接口仍返回成功——
    面板不该因为路线图是辅助数据而报错。
    """
    lines = [
        "# Scrapling UI - Feature Todo List",
        "",
        "This file tracks the status of major features and enhancements proposed to scale the visual web scraping builder.",
        "",
        "---",
        "",
        "## 📋 Features Checklist",
        ""
    ]
    for task in req.tasks:
        checkbox = "x" if task.checked else " "
        status_str = f" `[{task.status.upper()}]`" if task.status else ""
        lines.append(f"- [{checkbox}] **{task.title}**{status_str}")
        for sub in task.subtasks:
            sub_checkbox = "x" if sub.checked else " "
            lines.append(f"  - [{sub_checkbox}] {sub.text}")
            
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 🛠 Active Work")
    
    active_tasks = [t for t in req.tasks if t.status.upper() == "ACTIVE"]
    if active_tasks:
        lines.append(f"We are active on **{active_tasks[0].title}**.")
    else:
        lines.append("No active task selected. Choose one in the Scrapling UI!")
        
    md_content = "\n".join(lines) + "\n"
    
    try:
        dir_name = os.path.dirname(TODO_FILE_PATH)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        with open(TODO_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(md_content)
    except Exception as e:
        print(f"Failed to write todo list to {TODO_FILE_PATH}: {e}")
            
    return {"status": "success", "tasks": req.tasks}

# Add scheduled endpoints
@app.get("/api/scheduler/jobs")
async def list_jobs():
    """``GET /api/scheduler/jobs``：列出全部定时任务。

    响应 ``{"jobs": [{id, name, url, history, cron_expression, webhook_url,
    enabled, last_run, next_run, created_at}]}``，按创建时间倒序。
    读库异常（``jobs.db`` 被占用或损坏）会冒泡成 500。
    """
    return {"jobs": get_all_jobs()}

@app.post("/api/scheduler/jobs")
async def create_or_update_job(req: SaveJobRequest):
    """``POST /api/scheduler/jobs``：新建或覆盖一条定时任务并立即同步到调度器。

    请求体见 `models.SaveJobRequest`；``id`` 为空时生成 UUID，非空即视为编辑。
    响应 ``{"status": "success", "job": {...}}``。

    ``sync_db_to_scheduler`` 会重建全部定时任务，所以非法 cron 表达式不会让本接口
    报错，而是让该任务在调度器日志里被标记为调度失败（库里仍保留这条记录）。
    """
    job_id = req.id if req.id else str(uuid.uuid4())
    job = save_job(
        job_id=job_id,
        name=req.name,
        url=req.url,
        history=req.history,
        cron_expression=req.cron_expression,
        webhook_url=req.webhook_url,
        enabled=req.enabled
    )
    sync_db_to_scheduler()
    return {"status": "success", "job": job}

@app.post("/api/scheduler/jobs/{job_id}/toggle")
async def toggle_job(job_id: str, req: ToggleJobRequest):
    """``POST /api/scheduler/jobs/{job_id}/toggle``：启用或停用一条任务。

    请求体为 ``{"enabled": bool}``，响应 ``{"status": "success", "enabled": ...}``。
    任务不存在时返回 404；改完立即重建调度表，所以停用会真正摘掉定时触发器，
    而不是只改库里的标记。
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    update_job_enabled(job_id, req.enabled)
    sync_db_to_scheduler()
    return {"status": "success", "enabled": req.enabled}

@app.delete("/api/scheduler/jobs/{job_id}")
async def remove_job(job_id: str):
    """``DELETE /api/scheduler/jobs/{job_id}``：删除任务并尽力摘除定时器。

    响应固定 ``{"status": "success"}``；任务不存在也算成功（删除幂等）。
    调度器里的定时器可能已被重建而查不到，因此 ``remove_job`` 的异常被忽略——
    库里的记录才是唯一事实来源。
    """
    delete_job(job_id)
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass
    return {"status": "success"}

@app.post("/api/scheduler/jobs/{job_id}/run")
async def trigger_job_run(job_id: str):
    """``POST /api/scheduler/jobs/{job_id}/run``：后台立即跑一次任务。

    响应先返回 ``{"status": "success", "message": ...}``，真实执行通过
    ``asyncio.create_task`` 排到事件循环里，抓取结果不会随本次响应返回，
    需要看 ``jobs.db`` 的 ``last_run`` 与调度器日志。任务不存在时
    `run_crawler_job` 直接返回，接口仍报成功。
    """
    import asyncio
    asyncio.create_task(run_crawler_job(job_id))
    return {"status": "success", "message": "Job execution triggered headlessly in background"}

# Serve the built frontend (frontend/dist) from the same origin as the API.
# 只在构建产物存在时挂载 /assets，避免 dist 未构建时模块导入即报错；
# 之后所有非 API 路径由下面的 catch-all 路由处理。
if (FRONTEND_DIST_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="frontend-assets")

@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    """SPA fallback：返回 ``dist`` 里的真实文件，找不到就回 ``index.html``。

    注册在最后，因此不会遮蔽前面更具体的路由。

    Args:
        full_path: 不含前导斜杠的请求路径。

    Raises:
        HTTPException: ``api``/``api/**`` 一律 404（未知 API 必须返回 JSON 而不是
            前端 HTML，否则前端会把 404 当成接口成功）；``index.html`` 缺失时 503
            并提示先执行 ``npm run build``；解析后跳出 ``dist`` 的路径（``../``）
            同样 404，防止目录穿越。

    Returns:
        命中的静态文件，否则 ``index.html``（由前端路由自行渲染）。
    """
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")

    index_file = FRONTEND_DIST_DIR / "index.html"
    if not index_file.is_file():
        raise HTTPException(
            status_code=503,
            detail="Frontend build not found. Run 'npm install && npm run build' in website/scrapling-ui/frontend first.",
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
