"""Playwright 浏览器实例的进程级单例。

工作台只维护一个 Edge/Chromium 进程，用户每次「开始抓取」在同一浏览器上新建
BrowserContext，因此这里不做按会话的启停。公开入口是模块级单例 ``pw_manager``
（FastAPI 的 lifespan 在启动时 `start()`、关闭时 `stop()`）以及它的两个异步方法。

失败行为：`start()` 不做异常兜底，缺少浏览器内核或 ``msedge`` 通道未安装时异常直接
抛给 lifespan，服务启动失败；`stop()` 只按属性判断，可重复调用。
"""

from playwright.async_api import async_playwright, Browser

class PlaywrightManager:
    """持有 Playwright 驱动与浏览器进程。

    Attributes:
        playwright: ``async_playwright()`` 的驱动句柄；为 ``None`` 表示尚未启动，
            同时被 `start()` 当作幂等标志，重复调用不会另起驱动。
        browser: 浏览器进程句柄；路由层用它是否为空判断服务是否可用
            （``/api/session/start`` 为空时直接返回 HTTP 500）。
    """

    def __init__(self):
        self.playwright = None
        self.browser = None

    async def start(self):
        """首次调用时启动驱动并拉起一个无头浏览器；已启动则直接返回。

        ``channel="msedge"`` 复用本机已安装的 Edge，避免必须额外执行
        ``playwright install chromium``；三个启动参数放开同源策略、
        允许 HTTPS 页面加载混合内容，并关闭站点隔离试验，
        以便在跨域 iframe 与老站点上完成可视化选元素。

        Raises:
            playwright.async_api.Error: 本机没有可用的 ``msedge`` 通道或内核损坏。
        """
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                channel="msedge",
                args=[
                    "--disable-web-security",
                    "--allow-running-insecure-content",
                    "--disable-site-isolation-trials"
                ]
            )

    async def stop(self):
        """关闭浏览器进程并停止驱动，供服务退出时回收。

        顺序固定：先关浏览器再停驱动，否则 Playwright 传输层已断开时会抛
        ``TargetClosedError``。各分支都有存在性判断，未启动时调用无副作用。
        """
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

pw_manager = PlaywrightManager()
