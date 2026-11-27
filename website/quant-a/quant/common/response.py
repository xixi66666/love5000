"""`/api/**` 响应的统一封装。

成功响应的固定形状是 `{"success": true, "data": ..., "message": ""}`，失败响应是
`{"success": false, "message": "..."}`。`website` 的健康巡检只判断顶层布尔
`success`，因此字段名与形状必须保持稳定；错误响应刻意不含 `data`，避免前端把
错误当成功数据渲染。
"""

from typing import Any, Dict


def success(data: Any = None, message: str = "") -> Dict[str, Any]:
    """组装成功响应。

    Args:
        data: 业务数据；传 `None` 时返回空对象而不是 `null`，前端无需判空即可取字段。
        message: 可选提示文案，默认空串。

    Returns:
        可直接交给 FastAPI 序列化的字典，`success` 恒为 `True`。
    """
    return {
        "success": True,
        "data": {} if data is None else data,
        "message": message,
    }


def failure(message: str) -> Dict[str, Any]:
    """组装失败响应。

    只含 `success=false` 与 `message`，不返回 `data` 键；路由层把它和 HTTP 400
    一起返回（例如本地数据不足无法评分时）。
    """
    return {
        "success": False,
        "message": message,
    }
