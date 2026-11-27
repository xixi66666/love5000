"""``/api/v1`` 路由子包。

这里只汇总 last30days 路由；admin、collections、repositories、stats、health、
template_editor、daily_reports 由 :mod:`app.main` 逐个 include，最终统一挂在
``/api/v1`` 前缀下。
"""
from .last30days import router as last30days_router

__all__ = ["last30days_router"]
