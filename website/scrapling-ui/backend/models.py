"""工作台 REST 接口的请求体模型。

全部用 Pydantic 定义，``main.py`` 的路由直接以这些类型接收请求体。字段校验由
Pydantic 完成：缺必填字段或类型不符时 FastAPI 在进入业务代码前就返回 HTTP 422，
因此路由里只需处理「语义非法」（例如 click 缺少 selector）这类 400。

这里的模型只描述入站请求；响应用普通字典拼装，见 ``main.py`` 各路由的说明。
"""

from pydantic import BaseModel
from typing import Dict, List, Any, Optional

class StartSessionRequest(BaseModel):
    """``POST /api/session/start`` 的请求体：入口网址与浏览器开关。"""

    url: str
    width: int = 1280
    height: int = 800
    solve_cloudflare: bool = True
    block_ads: bool = True
    disable_resources: bool = False

class ActionRequest(BaseModel):
    """``POST /api/session/action`` 的请求体：一个动作及其可选参数。

    不同 ``action_type`` 需要的字段不同，缺字段由路由返回 400（不是 422），
    因为这些字段本身都是可选的。
    """

    session_id: str
    action_type: str  # "click", "fill", "scroll", "navigate", "extract", "extract_list", "back", "forward", "reload", "pagination"
    selector: Optional[str] = None
    value: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    extract_name: Optional[str] = None
    extract_attribute: Optional[str] = None

class CloseSessionRequest(BaseModel):
    """``POST /api/session/close`` 的请求体。"""

    session_id: str

class GenerateCodeRequest(BaseModel):
    """``POST /api/generate-code`` 的请求体。"""

    session_id: str

class UpdateHistoryRequest(BaseModel):
    """``POST /api/session/update-history`` 的请求体：整段替换用的历史。"""

    session_id: str
    history: List[Dict[str, Any]]

class RunCodeRequest(BaseModel):
    """``POST /api/run-code`` 的请求体。

    ``session_id`` 为空表示不在现有页面执行，而是另起子进程独立跑这份代码。
    """

    code: str
    session_id: Optional[str] = None

class SubTaskModel(BaseModel):
    """路线图里的子项：一行文字加勾选状态。"""

    text: str
    checked: bool

class TaskModel(BaseModel):
    """路线图里的主任务；``status`` 会原样写回 Markdown 的方括号标记。"""

    title: str
    checked: bool
    status: str
    subtasks: List[SubTaskModel]

class TodoListUpdateRequest(BaseModel):
    """``POST /api/todo`` 的请求体：整份任务列表。"""

    tasks: List[TaskModel]

class QuerySelectorRequest(BaseModel):
    """``POST /api/session/query-selector`` 的请求体：CSS 选择器或 XPath。"""

    session_id: str
    selector: str

class SaveJobRequest(BaseModel):
    """``POST /api/scheduler/jobs`` 的请求体。

    ``id`` 为空表示新建（服务端生成 UUID），非空表示覆盖同主键任务。
    """

    id: Optional[str] = None
    name: str
    url: str
    history: List[Dict[str, Any]]
    cron_expression: str
    webhook_url: str
    enabled: bool = True

class ToggleJobRequest(BaseModel):
    """``POST /api/scheduler/jobs/{job_id}/toggle`` 的请求体。"""

    enabled: bool

class HealSelectorRequest(BaseModel):
    """``POST /api/ai/heal-selector`` 的请求体：失效选择器与它原本要做的动作。"""

    session_id: str
    broken_selector: str
    action_type: str
