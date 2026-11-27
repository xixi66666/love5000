"""执行用户在面板里编辑过的抓取代码。

两种执行方式，由请求是否带 ``session_id`` 决定：

- 带会话：把代码 ``exec`` 进一个独立的 ``locals`` 字典，取出其中的
  ``perform_actions`` 协程函数并用当前 ``session.page`` 调用，改动能立刻反映到
  画布上。标准输出/错误被重定向到内存缓冲区后随响应返回。
- 不带会话：把代码写入临时 ``.py`` 文件，用同一个解释器起子进程跑完再删除文件，
  适合「先独立验证脚本」的场景。

安全边界：两种方式都没有沙箱。进程内路径能访问整个后端进程；子进程路径等价于
在主机上执行任意 Python。接口因此不加鉴权也只应对本机使用。

失败行为：进程内执行抛出的异常被转成 ``stderr`` 与 ``exit_code=1``，不向路由抛出；
子进程路径的异常（临时文件写入、进程创建、清理）统一包成 ``Exception`` 交给路由转 500。
"""

import sys
import tempfile
import io
import traceback
import asyncio
import os
from typing import Optional, Dict, Any
from contextlib import redirect_stdout, redirect_stderr
from core.session import Session, active_sessions
from models import RunCodeRequest

def make_code_async(code: str) -> str:
    """把同步版配方改写成可对着异步 ``Page`` 执行的版本。

    先生成出来的代码是 Scrapling 的同步写法（``page.click(...)``），直接在
    异步页面对象上调用只会拿到未 await 的协程。转换分三步：先剥掉所有已有的
    ``await page.<method>(``（使重复转换幂等），再把 ``perform_actions`` 的签名
    统一成 ``async def``（先降级再升级，避免出现 ``async async def``），
    最后重新加上 ``await``。

    Args:
        code: 用户提交的源码文本。

    Returns:
        改写后的源码文本；不含 ``page.*`` 调用的代码原样返回。

    这是纯文本替换，不做语法分析：方法名出现在字符串或注释里也会被改动。
    """
    normalized = code
    methods = ["click", "fill", "wait_for_load_state", "evaluate", "wait_for_timeout", "go_back", "go_forward", "reload"]
    for method in methods:
        normalized = normalized.replace(f"await page.{method}(", f"page.{method}(")
    # 统一 perform_actions 的签名：先降级再升级，避免 await 被叠加两次
    normalized = normalized.replace("async def perform_actions(page):", "def perform_actions(page):")
    normalized = normalized.replace("def perform_actions(page):", "async def perform_actions(page):")
    for method in methods:
        normalized = normalized.replace(f"page.{method}(", f"await page.{method}(")
    return normalized

async def execute_run_code(req: RunCodeRequest):
    """按请求决定执行方式并收集输出。

    Args:
        req: 含 ``code`` 与可选 ``session_id`` 的请求体。

    Returns:
        ``{stdout, stderr, exit_code, state}``。进程内成功且没有输出时，
        ``stdout`` 填一句提示文案而不是空串；``state`` 是执行后的页面快照
        （`Session.get_state`），子进程路径下为 ``None``。
        子进程路径的 ``stderr`` 非空并不影响返回 200，调用方需要自己看 ``exit_code``。

    Raises:
        Exception: 只有子进程创建失败（解释器路径异常等）才抛出，消息前缀
            ``Failed to run code:``。
    """
    session = active_sessions.get(req.session_id) if req.session_id else None
    
    if session:
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        async_code = make_code_async(req.code)
        
        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                # 独立的 locals 保证用户脚本的顶层变量不污染本模块命名空间；
                # globals 仍传本模块的命名空间，脚本里才能直接用到已导入的依赖。
                local_vars = {}
                exec(async_code, globals(), local_vars)
                perform_actions = local_vars.get("perform_actions")
                if perform_actions:
                    await perform_actions(session.page)
            
            # 只把「有不有 stderr 输出」当作失败信号，因为 exec 成功时没有异常可判。
            exit_code = 1 if stderr_buf.getvalue() else 0
            state = await session.get_state()
            return {
                "stdout": stdout_buf.getvalue() or "Script executed successfully on the active browser page.",
                "stderr": stderr_buf.getvalue(),
                "exit_code": exit_code,
                "state": state
            }
        except Exception as e:
            err_msg = traceback.format_exc()
            return {
                "stdout": stdout_buf.getvalue(),
                "stderr": err_msg,
                "exit_code": 1,
                "state": await session.get_state()
            }
    else:
        try:
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
                f.write(req.code)
                temp_file_path = f.name
                
            process = await asyncio.create_subprocess_exec(
                sys.executable, temp_file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # 先删临时文件再返回，避免异常分支留下垃圾文件。
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
            return {
                "stdout": stdout.decode("utf-8", errors="ignore"),
                "stderr": stderr.decode("utf-8", errors="ignore"),
                "exit_code": process.returncode,
                "state": None
            }
        except Exception as e:
            raise Exception(f"Failed to run code: {str(e)}")
