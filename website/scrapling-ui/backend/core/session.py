"""一次可视化抓取会话的运行时状态。

`Session` 包住一个 Playwright ``Page``，在它之上维护三份可回传前端的状态：
网络请求/响应日志、操作历史（配方来源）、以及按历史重放后得到的结构化数据。
公开入口是 `Session` 类的方法与模块级注册表 `active_sessions`
（``session_id -> Session``，由 ``main.py`` 的路由读写）。

失败行为：会话在浏览器侧异常关闭时 `close()` 只打日志；`replay_history` 是唯一
会中断流程的方法——某一步失败就整体抛出，调用方据此回 500，此时页面已停在
失败那一步的状态；`get_state` 的降级是分段的，截图失败会抛出，
DOM 提取或单列提取失败只影响对应字段（分别为 ``None`` / 空列表）。
"""

import base64
import asyncio
import uuid
from typing import Dict, List, Any
from playwright.async_api import Browser, BrowserContext, Page
from .dom_extractor import DOM_EXTRACTOR_JS

class Session:
    """单个浏览器页签及其抓取上下文。

    构造时立即在 ``page`` 上挂 request/response 监听，所以后续所有网络活动都会
    自动记进 ``network_logs``，无需业务代码打点。

    Attributes:
        session_id: 会话标识，由 ``/api/session/start`` 生成的 UUID。
        browser: 共享的浏览器进程（进程级单例，不随会话关闭）。
        context: 该会话独占的 BrowserContext，带自己的视口与 UA。
        page: 当前页面对象，所有动作与求值都在它上面执行。
        solve_cloudflare: 是否请求过盾；当前只留在会话上，配方生成仍用固定默认值。
        block_ads: 是否按关键词拦截广告/统计域名；``main.py`` 据此安装页面路由过滤器。
        disable_resources: 是否在「极速模式」下拦截图片、媒体、字体与样式表。
        network_logs: 请求日志列表，与 ``history`` 一起原样回传前端。
        history: 可回放的操作历史，是代码生成与重放的唯一事实来源。
        _request_map: Playwright ``Request`` 对象到日志 id 的映射；命中不到时
            `_handle_response` 再用 URL + 方法兜底匹配，条目随页面关闭一并丢弃。
    """

    def __init__(self, session_id: str, browser: Browser, context: BrowserContext, page: Page, solve_cloudflare: bool = True, block_ads: bool = True, disable_resources: bool = False):
        self.session_id = session_id
        self.browser = browser
        self.context = context
        self.page = page
        self.solve_cloudflare = solve_cloudflare
        self.block_ads = block_ads
        self.disable_resources = disable_resources
        self.network_logs: List[Dict[str, Any]] = []
        self.history: List[Dict[str, Any]] = []
        self._request_map = {}

        # 注册请求/响应监听，供网络日志与重放使用
        self.page.on("request", self._handle_request)
        self.page.on("response", self._handle_response)

    async def _handle_request(self, request):
        """记录一条出站请求的初始快照，此时状态码与响应体还未知。

        Args:
            request: Playwright ``Request`` 对象；``post_data`` 在读取失败时
                （如流式上传）保持 ``None``，不影响其余字段。
        """
        req_id = str(uuid.uuid4())
        self._request_map[request] = req_id
        
        post_data = None
        try:
            post_data = request.post_data
        except Exception:
            pass

        self.network_logs.append({
            "id": req_id,
            "url": request.url,
            "method": request.method,
            "resource_type": request.resource_type,
            "request_headers": dict(request.headers),
            "post_data": post_data,
            "status": None,
            "response_headers": None,
            "response_body": None,
            "size": 0,
        })

    async def _handle_response(self, response):
        """把响应信息回填到对应的请求日志条目。

        先按 ``_request_map`` 精确匹配；匹配不到时用「同 URL + 同方法 + 尚未回填状态」
        从后往前兜底，兼容重定向和 Service Worker 转发产生的不同 Request 对象。

        Args:
            response: Playwright ``Response`` 对象。

        响应体只对 JSON/文本/XML/JS/HTML 读取，超过 50000 字符截断并标注；
        二进制响应只记占位串。读取失败（下载被中断、页面已跳走）记
        ``[Body reading failed/aborted]``，不向上抛异常。
        """
        request = response.request
        req_id = self._request_map.get(request)
        
        entry = None
        if req_id:
            for log in self.network_logs:
                if log["id"] == req_id:
                    entry = log
                    break
        else:
            for log in reversed(self.network_logs):
                if log["url"] == response.url and log["method"] == request.method and log["status"] is None:
                    entry = log
                    break

        if not entry:
            return

        entry["status"] = response.status
        try:
            entry["response_headers"] = dict(response.headers)
        except Exception:
            pass
        
        try:
            sizes = await response.sizes()
            entry["size"] = sizes.get("responseHeadersSize", 0) + sizes.get("responseBodySize", 0)
        except Exception:
            pass

        try:
            content_type = response.headers.get("content-type", "").lower()
            if any(t in content_type for t in ["json", "text", "xml", "javascript", "html"]):
                body = await response.text()
                if len(body) > 50000:
                    entry["response_body"] = body[:50000] + "\n... [TRUNCATED]"
                else:
                    entry["response_body"] = body
            else:
                entry["response_body"] = "[Non-text response]"
        except Exception:
            entry["response_body"] = "[Body reading failed/aborted]"

    async def get_state(self):
        """汇总一次完整的前端渲染状态。

        Returns:
            含 ``session_id``、整页截图 data URI、DOM 树、网络日志、操作历史
            与 ``scraped_data`` 的字典；这是绝大多数路由的统一响应体。

        固定等待 0.5 秒让动画与懒加载落定后再截图，否则元素坐标与截图会对不上。
        截图使用 JPEG(质量 80)+整页模式，避免 PNG 体积过大撑爆响应；
        ``page.screenshot`` 本身失败（页面已崩溃）会抛出，DOM 提取失败只让
        ``dom_tree`` 变成 ``None``。
        """
        # 稍等片刻，让渲染与动画稳定下来，避免截到中间态
        await asyncio.sleep(0.5)

        # 截整页图，前端画布可直接滚动查看
        screenshot_bytes = await self.page.screenshot(type="jpeg", quality=80, full_page=True)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        screenshot_data_uri = f"data:image/jpeg;base64,{screenshot_b64}"
        
        # 提取 DOM 树
        try:
            dom_tree = await self.page.evaluate(DOM_EXTRACTOR_JS)
        except Exception as e:
            print(f"Error evaluating DOM Extractor JS: {e}")
            dom_tree = None

        return {
            "session_id": self.session_id,
            "screenshot": screenshot_data_uri,
            "dom_tree": dom_tree,
            "network_logs": self.network_logs,
            "history": self.history,
            "scraped_data": await self.get_scraped_data()
        }

    async def get_scraped_data(self) -> List[Dict[str, str]]:
        """把 ``extract_list`` 步骤在页面上重跑一遍，拼成行列表。

        Returns:
            行字典列表，键为各提取步骤的 ``name``；没有列表提取步骤时返回空列表。
            各列长度不一致时短列补空串，长度以最长列为准。

        选择器与属性名被直接拼进 JS 字符串，只对单引号做转义，因此包含换行或
        反引号的选择器会导致该列求值失败——失败时该列退化为空列表，其余列照常。
        """
        list_steps = [s for s in self.history if s["action"] == "extract_list"]
        if not list_steps:
            return []
            
        columns = {}
        max_len = 0
        for step in list_steps:
            name = step.get("name", "data")
            selector = step.get("selector", "")
            attr = step.get("attribute", "text")
            escaped_selector = selector.replace("'", "\\'")
            
            js_query = f"""
            () => {{
                try {{
                    const elms = document.querySelectorAll('{escaped_selector}');
                    return Array.from(elms).map(el => {{
                        if ('{attr}' === 'text') return el.textContent ? el.textContent.trim() : '';
                        if ('{attr}' === 'html') return el.innerHTML || '';
                        return el.getAttribute('{attr}') || '';
                    }});
                }} catch (e) {{
                    return [];
                }}
            }}
            """
            try:
                vals = await self.page.evaluate(js_query)
                columns[name] = vals
                max_len = max(max_len, len(vals))
            except Exception as e:
                print(f"Error executing list extraction: {e}")
                columns[name] = []
                
        # 列转行：按最长一列补齐缺失值
        rows = []
        for i in range(max_len):
            row = {}
            for col_name, col_vals in columns.items():
                row[col_name] = col_vals[i] if i < len(col_vals) else ""
            rows.append(row)
            
        return rows

    async def replay_history(self, new_history: List[Dict[str, Any]]):
        """按新的操作历史重放整段流程，用于撤销/编辑配方后重新对齐页面。

        先清空当前 ``history``、``network_logs`` 与 ``_request_map``，再从历史中
        第一条 ``navigate`` 重新打开页面，因此重放后前端看到的历史只包含
        本次成功执行的步骤。

        Args:
            new_history: 前端提交的完整历史；缺少 ``navigate`` 步骤时清空状态后
                直接返回，不会报错。

        Raises:
            Exception: 首个导航失败，或任一步骤失败时抛出带步骤名的中文+英文混合消息；
                此时页面停在失败步骤之前的状态，已成功的步骤保留在 ``history`` 中。
        """
        self.history = []
        self.network_logs = []
        self._request_map = {}
        
        # 定位历史中的导航动作，作为重放起点
        start_url = None
        for step in new_history:
            if step["action"] == "navigate":
                start_url = step.get("url")
                break
                
        if not start_url:
            return
            
        try:
            await self.page.goto(start_url, wait_until="load", timeout=30000)
            self.history.append({"action": "navigate", "url": start_url})
        except Exception as e:
            print(f"Failed to navigate during replay: {e}")
            raise Exception(f"Failed to navigate to {start_url}: {e}")
            
        for step in new_history:
            action = step["action"]
            if action == "navigate":
                continue
                
            try:
                if action == "click":
                    selector = step["selector"]
                    await self.page.click(selector, timeout=5000)
                    self.history.append({"action": "click", "selector": selector})
                    
                elif action == "fill":
                    selector = step["selector"]
                    val = step["value"]
                    await self.page.fill(selector, val, timeout=5000)
                    self.history.append({"action": "fill", "selector": selector, "value": val})
                    
                elif action == "scroll":
                    y = step.get("y", 300)
                    await self.page.evaluate(f"window.scrollBy(0, {y})")
                    self.history.append({"action": "scroll", "y": y})
                    await asyncio.sleep(1.0)
                    
                elif action == "extract":
                    self.history.append({
                        "action": "extract",
                        "name": step["name"],
                        "selector": step["selector"],
                        "attribute": step["attribute"]
                    })
                    
                elif action == "extract_list":
                    self.history.append({
                        "action": "extract_list",
                        "name": step["name"],
                        "selector": step["selector"],
                        "attribute": step["attribute"]
                    })
                    
                elif action == "back":
                    try:
                        await self.page.go_back(timeout=5000)
                    except Exception:
                        pass
                    self.history.append({"action": "back"})
                    
                elif action == "forward":
                    try:
                        await self.page.go_forward(timeout=5000)
                    except Exception:
                        pass
                    self.history.append({"action": "forward"})
                    
                elif action == "reload":
                    await self.page.reload(timeout=20000)
                    self.history.append({"action": "reload"})
                    
                elif action == "pagination":
                    selector = step["selector"]
                    max_pages = step["max_pages"]
                    await self.page.click(selector, timeout=5000)
                    self.history.append({
                        "action": "pagination",
                        "selector": selector,
                        "max_pages": max_pages
                    })
            except Exception as e:
                print(f"Replay failed on step {step}: {e}")
                raise Exception(f"Failed to replay step '{action}' on '{step.get('selector', '')}': {str(e)}")

    async def close(self):
        """关闭页签与上下文；浏览器进程由 ``pw_manager`` 统一管理，不在这里关。

        关闭失败（页面已崩、上下文已释放）只打日志，避免清理路径把正常响应变成 500。
        """
        try:
            await self.page.close()
            await self.context.close()
        except Exception as e:
            print(f"Error closing session: {e}")

active_sessions: Dict[str, Session] = {}
