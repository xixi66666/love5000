from typing import Any, Dict


def success(data: Any = None, message: str = "") -> Dict[str, Any]:
    return {
        "success": True,
        "data": {} if data is None else data,
        "message": message,
    }


def failure(message: str) -> Dict[str, Any]:
    return {
        "success": False,
        "message": message,
    }
