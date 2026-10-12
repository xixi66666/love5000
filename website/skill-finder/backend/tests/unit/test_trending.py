from __future__ import annotations

from app.collector.trending import (
    TrendingRepository,
    build_ai_matcher,
    is_ai_related,
    parse_trending_html,
    select_trending,
)

ROW = """
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/{owner}/{name}">
      <span class="text-normal">{owner} /</span>
      {name}
    </a>
  </h2>
  {description}
  <div class="f6 color-fg-muted mt-2">
    {language}
    <a href="/{owner}/{name}/stargazers" class="Link--muted d-inline-block mr-3">
      <svg aria-hidden="true"></svg>
      {stars}
    </a>
    <span class="d-inline-block float-sm-right">
      {gained}
    </span>
  </div>
</article>
"""


def make_row(
    owner: str,
    name: str,
    stars: str = "1,234",
    gained: str = "56 stars today",
    description: str = '<p class="col-9">An agent framework</p>',
    language: str = '<span itemprop="programmingLanguage">Python</span>',
) -> str:
    return ROW.format(
        owner=owner,
        name=name,
        stars=stars,
        gained=gained,
        description=description,
        language=language,
    )


HTML = "<html><body>" + "".join(
    [
        make_row("openai", "agents", stars="12,345", gained="1,234 stars today"),
        make_row(
            "acme",
            "mcp-tools",
            stars="2,000",
            gained="456 stars today",
            description='<p class="col-9">MCP server toolkit</p>',
            language='<span itemprop="programmingLanguage">TypeScript</span>',
        ),
        make_row(
            "acme",
            "plain-utils",
            stars="900",
            gained="123 stars today",
            description="<p class=\"col-9\">Utility helpers</p>",
        ),
    ]
) + "</body></html>"


def test_parses_trending_rows() -> None:
    repos = parse_trending_html(HTML, "daily")

    assert [repo.full_name for repo in repos] == [
        "openai/agents",
        "acme/mcp-tools",
        "acme/plain-utils",
    ]
    first = repos[0]
    assert first.owner == "openai"
    assert first.name == "agents"
    assert first.description == "An agent framework"
    assert first.language == "Python"
    assert first.stars_total == 12345
    assert first.stars_gained == 1234
    assert first.rank == 1
    assert repos[1].language == "TypeScript"
    assert repos[1].stars_total == 2000
    assert repos[1].stars_gained == 456


def test_parses_weekly_and_monthly_labels() -> None:
    html = "<html><body>" + make_row("acme", "llm-kit", gained="789 stars this week") + "</body></html>"
    weekly = parse_trending_html(html, "weekly")
    assert weekly[0].stars_gained == 789

    html = "<html><body>" + make_row("acme", "llm-kit", gained="321 stars this month") + "</body></html>"
    monthly = parse_trending_html(html, "monthly")
    assert monthly[0].stars_gained == 321


def test_missing_description_and_language() -> None:
    html = (
        "<html><body>"
        + make_row("acme", "bare", description="", language="")
        + "</body></html>"
    )
    repo = parse_trending_html(html, "daily")[0]
    assert repo.description is None
    assert repo.language is None


def test_empty_page_returns_no_repositories() -> None:
    assert parse_trending_html("<html><body>no rows</body></html>", "daily") == []


def make_repo(
    name: str, gained: int, rank: int, description: str = "AI agent toolkit"
) -> TrendingRepository:
    return TrendingRepository(
        owner="acme",
        name=name,
        full_name=f"acme/{name}",
        description=description,
        language="Python",
        stars_total=1000,
        stars_gained=gained,
        rank=rank,
    )


def test_build_ai_matcher_matches_word_boundaries() -> None:
    matcher = build_ai_matcher("ai,mcp")
    assert matcher is not None
    assert matcher.search("build ai agents") is not None
    assert matcher.search("email client") is None
    assert matcher.search("we make gains") is None


def test_is_ai_related_checks_name_and_description() -> None:
    matcher = build_ai_matcher("agent")
    assert matcher is not None
    assert is_ai_related(make_repo("my-agent", 10, 1, "toolkit"), matcher)
    assert is_ai_related(
        make_repo("toolkit", 10, 1, "An agent framework"), matcher
    )
    assert not is_ai_related(make_repo("toolkit", 10, 1, "A CSS library"), matcher)


def test_select_trending_filters_and_sorts() -> None:
    repositories = [
        make_repo("plain", 500, 1, "just a tool"),
        make_repo("agent-low", 10, 2),
        make_repo("agent-high", 900, 3),
        make_repo("agent-mid", 100, 4),
    ]

    selected = select_trending(repositories, "agent", top_n=2)

    assert [repo.name for repo in selected] == ["agent-high", "agent-mid"]


def test_select_trending_without_keywords_keeps_all_and_sorts() -> None:
    repositories = [
        make_repo("first", 10, 1),
        make_repo("second", 900, 2),
    ]

    selected = select_trending(repositories, "", top_n=10)

    assert [repo.name for repo in selected] == ["second", "first"]
