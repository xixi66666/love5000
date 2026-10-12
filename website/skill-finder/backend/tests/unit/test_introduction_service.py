import json

import httpx
import pytest

from app.services.introduction_service import (
    IntroductionGenerationError,
    RepositoryBrief,
    _build_prompt,
    _model_chain,
    _parse_introductions,
    _resolve_api_key,
    generate_introductions,
    generate_introductions_resilient,
)

GATEWAY = "https://opencode.ai/zen/go/v1/chat/completions"


def make_brief(
    name: str = "demo-skill",
    topics: list[str] | None = None,
    readme: str | None = None,
) -> RepositoryBrief:
    return RepositoryBrief(
        owner="octocat",
        name=name,
        description="A demo agent skill",
        language="Python",
        topics=topics or ["ai-skills"],
        stars_count=1234,
        homepage=None,
        html_url="https://github.com/octocat/demo-skill",
        readme=readme,
    )


def rich_payload(**overrides: object) -> dict:
    payload = {
        "introduction": "简介",
        "highlights": [],
        "requirements": [],
        "usage": "",
        "audience": "",
        "domains": [],
    }
    payload.update(overrides)
    return payload


def _content_payload(text: str) -> dict:
    return {
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "usage": {"total_tokens": 100},
    }


def test_build_prompt_contains_repo_info() -> None:
    prompt = _build_prompt([make_brief(readme="# Demo\nRun `npm install`.")])
    assert "demo-skill" in prompt
    assert "ai-skills" in prompt
    assert "octocat" in prompt
    assert "JSON" in prompt
    assert "highlights" in prompt
    assert "requirements" in prompt
    assert "usage" in prompt
    assert "audience" in prompt
    assert "domains" in prompt
    assert "npm install" in prompt


def test_build_prompt_without_readme_omits_section() -> None:
    prompt = _build_prompt([make_brief()])
    assert "README 原文：" not in prompt
    assert "的 README" not in prompt


def test_parse_introductions_from_json_array() -> None:
    text = (
        '[{"introduction": "第一个仓库的简介。", "highlights": ["亮点一"], '
        '"requirements": ["Node.js 22+"], "usage": "直接运行", "audience": "开发者", '
        '"domains": ["AI Agent"]}, '
        '{"introduction": "第二个仓库的简介。", "usage": "pip 安装", '
        '"domains": ["自动化", "RAG"]}]'
    )
    assert _parse_introductions(text, 2) == [
        json.dumps(
            {
                "introduction": "第一个仓库的简介。",
                "highlights": ["亮点一"],
                "requirements": ["Node.js 22+"],
                "usage": "直接运行",
                "audience": "开发者",
                "domains": ["AI Agent"],
            },
            ensure_ascii=False,
        ),
        json.dumps(
            {
                "introduction": "第二个仓库的简介。",
                "highlights": [],
                "requirements": [],
                "usage": "pip 安装",
                "audience": "",
                "domains": ["自动化", "RAG"],
            },
            ensure_ascii=False,
        ),
    ]


def test_parse_introductions_with_surrounding_text() -> None:
    text = (
        '好的，以下是简介：\n```\n'
        '[{"introduction": "简介甲", "usage": "用法甲", "domains": ["领域甲"]}, '
        '{"introduction": "简介乙", "usage": "用法乙", "domains": ["领域乙"]}]\n```'
    )
    assert _parse_introductions(text, 2) == [
        json.dumps(rich_payload(introduction="简介甲", usage="用法甲", domains=["领域甲"]), ensure_ascii=False),
        json.dumps(rich_payload(introduction="简介乙", usage="用法乙", domains=["领域乙"]), ensure_ascii=False),
    ]


def test_parse_introductions_accepts_plain_strings() -> None:
    text = '["简介一", "简介二"]'
    assert _parse_introductions(text, 2) == [
        json.dumps(rich_payload(introduction="简介一"), ensure_ascii=False),
        json.dumps(rich_payload(introduction="简介二"), ensure_ascii=False),
    ]


def test_parse_introductions_raises_on_garbage() -> None:
    with pytest.raises(IntroductionGenerationError):
        _parse_introductions("抱歉，我无法完成这个请求。", 1)


def test_model_chain_strips_provider_prefix_and_dedupes() -> None:
    assert _model_chain(" opencode-go/ox-alpha-free, opencode-go/deepseek-v4-flash, ox-alpha-free ") == [
        "ox-alpha-free",
        "deepseek-v4-flash",
    ]
    assert _model_chain("") == []


def test_resolve_api_key_prefers_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.introduction_service.settings.opencode_api_key", "sk-test"
    )
    assert _resolve_api_key() == "sk-test"


def test_resolve_api_key_raises_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(
        "app.services.introduction_service.settings.opencode_api_key", ""
    )
    monkeypatch.setattr(
        "app.services.introduction_service.Path.home", lambda: tmp_path
    )
    with pytest.raises(IntroductionGenerationError):
        _resolve_api_key()


@pytest.mark.asyncio
async def test_generate_uses_first_model_and_sends_auth(
    monkeypatch: pytest.MonkeyPatch, respx_mock
) -> None:
    monkeypatch.setattr(
        "app.services.introduction_service.settings.opencode_api_key", "sk-test"
    )
    route = respx_mock.post(GATEWAY).mock(
        return_value=httpx.Response(
            200,
            json=_content_payload(
                '[{"introduction": "简介一", "usage": "用法一", "domains": ["领域一"]}]'
            ),
        )
    )
    texts = await generate_introductions([make_brief("a")], model="opencode-go/ox-alpha-free")
    assert texts == [
        json.dumps(
            rich_payload(introduction="简介一", usage="用法一", domains=["领域一"]),
            ensure_ascii=False,
        )
    ]
    assert route.called
    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer sk-test"
    assert request.headers["x-opencode-session"]
    body = json.loads(request.content)
    assert body["model"] == "ox-alpha-free"


@pytest.mark.asyncio
async def test_generate_falls_back_after_upstream_errors(
    monkeypatch: pytest.MonkeyPatch, respx_mock
) -> None:
    monkeypatch.setattr(
        "app.services.introduction_service.settings.opencode_api_key", "sk-test"
    )
    monkeypatch.setattr("asyncio.sleep", _noop_sleep)

    async def _sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(
        "app.services.introduction_service.asyncio.sleep", _sleep
    )
    ok = _content_payload(
        '[{"introduction": "兜底简介", "usage": "", "domains": []}]'
    )

    def _handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body["model"] == "ox-alpha-free":
            return httpx.Response(503, json={"error": "unavailable"})
        return httpx.Response(200, json=ok)

    respx_mock.post(GATEWAY).mock(side_effect=_handler)
    texts = await generate_introductions(
        [make_brief("a")], model="opencode-go/ox-alpha-free,opencode-go/deepseek-v4-flash"
    )
    assert texts[0] == json.dumps(
        rich_payload(introduction="兜底简介"),
        ensure_ascii=False,
    )


@pytest.mark.asyncio
async def test_generate_raises_when_all_models_fail(
    monkeypatch: pytest.MonkeyPatch, respx_mock
) -> None:
    monkeypatch.setattr(
        "app.services.introduction_service.settings.opencode_api_key", "sk-test"
    )

    async def _sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(
        "app.services.introduction_service.asyncio.sleep", _sleep
    )
    respx_mock.post(GATEWAY).mock(
        return_value=httpx.Response(503, json={"error": "unavailable"})
    )
    with pytest.raises(IntroductionGenerationError):
        await generate_introductions([make_brief()], model="m1,m2")


async def _noop_sleep(seconds: float) -> None:
    return None


@pytest.mark.asyncio
async def test_resilient_returns_batch_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.introduction_service as intro_module

    async def fake(briefs, **kwargs):
        return [f"intro:{brief.name}" for brief in briefs]

    monkeypatch.setattr(intro_module, "generate_introductions", fake)
    result = await generate_introductions_resilient([make_brief("a"), make_brief("b")])
    assert result == ["intro:a", "intro:b"]


@pytest.mark.asyncio
async def test_resilient_splits_batch_and_skips_risky_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.introduction_service as intro_module

    calls: list[list[str]] = []

    async def fake(briefs, **kwargs):
        names = [brief.name for brief in briefs]
        calls.append(names)
        if len(briefs) > 1:
            raise IntroductionGenerationError("batch rejected")
        if names == ["bad"]:
            raise IntroductionGenerationError("Content Exists Risk")
        return [f"intro:{names[0]}"]

    monkeypatch.setattr(intro_module, "generate_introductions", fake)

    briefs = [
        make_brief("a"),
        make_brief("bad", readme="# risky readme"),
        make_brief("c"),
    ]
    result = await generate_introductions_resilient(briefs)

    assert result == ["intro:a", None, "intro:c"]
    assert ["a", "bad", "c"] in calls
    assert calls.count(["bad"]) == 2


@pytest.mark.asyncio
async def test_resilient_retries_without_readme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.introduction_service as intro_module

    seen_readmes: list[str | None] = []

    async def fake(briefs, **kwargs):
        seen_readmes.append(briefs[0].readme)
        if briefs[0].readme:
            raise IntroductionGenerationError("Content Exists Risk")
        return ["intro:ok"]

    monkeypatch.setattr(intro_module, "generate_introductions", fake)

    result = await generate_introductions_resilient([make_brief("a", readme="# readme")])

    assert result == ["intro:ok"]
    assert seen_readmes == ["# readme", None]
