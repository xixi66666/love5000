"""A 股研究台前端静态结构的回归测试。

被测对象：``index.html`` 里研究区的三个页签与各面板容器 id，以及 ``app.js`` 中懒加载、渲染和
转义函数是否存在；这些契约一旦被改名，页面会在运行时才静默失效，所以在这里静态校验。

隔离：只用标准库 ``html.parser`` 解析 HTML 文本、用 ``Path.read_text`` 读取脚本源码，
不启动服务、不打开浏览器、不访问网络，也不需要执行 app.js。
"""
import unittest
from html.parser import HTMLParser
from pathlib import Path


# 测试文件位于 website/python-a/tests，上一级即微应用根目录，页面与脚本都相对它定位。
ROOT = Path(__file__).resolve().parents[1]


class IdAndButtonParser(HTMLParser):
    """收集页面里所有 id 和带 ``data-research-tab`` 的按钮，作为结构断言的输入。"""
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.research_tabs = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        if tag == "button" and attributes.get("data-research-tab"):
            self.research_tabs.append(attributes["data-research-tab"])


class ResearchUiStructureTests(unittest.TestCase):
    """覆盖两处契约：页面上的研究页签与面板/列表容器 id，以及 app.js 的懒加载与安全渲染函数。"""
    def test_research_tabs_and_panels_exist(self):
        parser = IdAndButtonParser()
        parser.feed((ROOT / "index.html").read_text(encoding="utf-8"))

        self.assertEqual(parser.research_tabs, ["overview", "capital", "events"])
        for element_id in (
            "researchOverviewPanel",
            "researchCapitalPanel",
            "researchEventsPanel",
            "researchOverviewContent",
            "fundFlowBlock",
            "marginBlock",
            "shareholdersBlock",
            "lockupsBlock",
            "reportsList",
            "announcementsList",
            "loadMoreReportsBtn",
            "loadMoreAnnouncementsBtn",
        ):
            with self.subTest(element_id=element_id):
                self.assertIn(element_id, parser.ids)

    def test_app_contains_lazy_research_loading_and_safe_rendering(self):
        script = (ROOT / "app.js").read_text(encoding="utf-8")

        for function_name in (
            "loadResearchSection",
            "renderResearchSection",
            "escapeHtml",
            "safeExternalUrl",
        ):
            with self.subTest(function_name=function_name):
                self.assertIn("function {}".format(function_name), script)
        self.assertIn("research_snapshot", script)


if __name__ == "__main__":
    unittest.main()
