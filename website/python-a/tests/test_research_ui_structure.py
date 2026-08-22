import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class IdAndButtonParser(HTMLParser):
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
