"""中文简介服务的提示词、解析、模型链与降级策略。

被测对象是 `app.services.introduction_service`：`_build_prompt` 的提示词结构、
`_parse_introductions` 的宽松解析（JSON 数组、裸字符串、夹带说明文字或代码围栏）、
`_model_chain` 的模型链去重、`_resolve_api_key` 的密钥来源，以及
`generate_introductions(_resilient)` 的模型回退与批次拆分。

重点是几条“宁可不写也不能写错”的边界：

- HTTP 401 必须立刻停止：不换模型、不拆批次，错误信息里不能出现上游响应体；
- 已选统一模型时优先走 `model_hub.try_chat`，且不再读取原提供方密钥；统一模型失败
  也只报一次，不回退到原配置；
- 宽松降级只在非认证错误时发生：先整批、再拆单条、最后去掉 README 重试，仍失败的
  条目返回 `None`，不能编造简介。

隔离方式：`isolate_private_intro_configuration` 以 autouse 方式把 `model_hub.try_chat`
改成“未选择统一模型”，并把密钥、地址、模型链替换为测试值，因此不读本机
`model.properties`；HTTP 全部由 respx 拦截，`asyncio.sleep` 换成空实现，
不联网也不真的等待重试退避。
"""

import json

import httpx
import pytest

from app.services import _model_properties as model_properties
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


@pytest.fixture(autouse=True)
def isolate_private_intro_configuration(monkeypatch):
    """把简介配置与统一模型入口固定成测试值，避免读取本机私有配置。

    `model_hub.try_chat` 默认返回 `None`，表示“没有选统一模型”，服务因此走原配置
    链路（这样才能用 respx 观察请求体）；密钥置空、地址指向测试网关、模型链按传入
    字符串解析。需要验证统一模型分支的用例会自己再覆盖 `try_chat`。
    """
    from app.services import introduction_service as module
    from app.services import model_hub

    async def native_mode(payload):
        return None

    def _models(override=""):
        return [part.split("/")[-1].strip() for part in override.split(",") if part.strip()]

    monkeypatch.setattr(model_hub, "try_chat", native_mode)
    monkeypatch.setattr(module.model_settings, "intro_api_key", lambda: "")
    monkeypatch.setattr(module.model_settings, "intro_base_url", lambda: "https://opencode.ai/zen/go/v1")
    monkeypatch.setattr(module.model_settings, "intro_models", _models)


def test_reads_intro_key_from_model_properties(tmp_path):
    path = tmp_path / "model.properties"
    path.write_text(
        "intro.base-url=https://example.invalid/v1\n"
        "intro.api-key=test-private-value\n"
        "intro.models=test-model\n"
        "service.skill-finder=intro:test-model\n",
        encoding="utf-8",
    )
    settings = model_properties.ModelProperties.load(path)
    assert settings.provider("intro").api_key == "test-private-value"
    assert settings.provider("intro").base_url == "https://example.invalid/v1"
    assert settings.route("skill-finder").model_id == "test-model"


def test_missing_intro_key_raises_without_exposing_configuration(monkeypatch):
    with pytest.raises(IntroductionGenerationError) as caught:
        _resolve_api_key()
    assert "model.properties" in str(caught.value)


async def test_expired_key_does_not_retry_models_or_split_batches(monkeypatch, respx_mock):
    monkeypatch.setattr("app.services.introduction_service.model_settings.intro_api_key", lambda: "test-key")
    monkeypatch.setattr("app.services.introduction_service.model_settings.intro_models",
                        lambda override="": ["m1", "m2"])
    route = respx_mock.post(GATEWAY).mock(
        return_value=httpx.Response(401, json={"error": "expired private credential"})
    )
    with pytest.raises(IntroductionGenerationError, match="认证失败") as caught:
        await generate_introductions_resilient([make_brief(str(i)) for i in range(5)])
    assert route.call_count == 1
    assert "private credential" not in str(caught.value)


async def test_global_model_bypasses_native_credentials_and_provider(monkeypatch):
    from app.services import model_hub

    calls = []

    async def complete(payload):
        calls.append(payload)
        return {"choices": [{"message": {"content": '["统一模型生成的介绍"]'}}]}

    monkeypatch.setattr(model_hub, "try_chat", complete)
    monkeypatch.setattr("app.services.introduction_service.model_settings.intro_api_key",
                        lambda: pytest.fail("统一模型不应读取原提供方密钥"))
    generated = await generate_introductions([make_brief()])
    assert json.loads(generated[0])["introduction"] == "统一模型生成的介绍"
    assert len(calls) == 1
    assert "model" not in calls[0]


async def test_selected_model_failure_stops_without_fallback(monkeypatch):
    from app.services import model_hub

    calls = []

    async def fail(payload):
        calls.append(payload)
        raise RuntimeError("private upstream detail")

    monkeypatch.setattr(model_hub, "try_chat", fail)
    with pytest.raises(IntroductionGenerationError, match="统一模型") as caught:
        await generate_introductions_resilient([make_brief(), make_brief("second")])
    assert len(calls) == 1
    assert "private upstream detail" not in str(caught.value)


def make_brief(
    name: str = "demo-skill",
    topics: list[str] | None = None,
    readme: str | None = None,
) -> RepositoryBrief:
    """构造一条仓库简介输入。

    默认带 `ai-skills` topic 与 GitHub 地址，足够拼出完整提示词；传 `readme` 可以
    让用例走到“带 README”与“去掉 README 重试”两条分支。
    """
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
    """构造解析后的标准结构。

    除 `introduction` 外的字段都给了默认值（空列表或空串），这正是解析器对缺失字段
    补齐的结果，因此可以直接和 `_parse_introductions` 的输出比对。
    """
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
    """包一层 OpenAI 兼容的 chat completions 响应壳，`content` 放模型输出文本。"""
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


def test_resolve_api_key_reads_model_properties(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.introduction_service.model_settings.intro_api_key", lambda: "sk-test"
    )
    assert _resolve_api_key() == "sk-test"


def test_resolve_api_key_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(IntroductionGenerationError):
        _resolve_api_key()


@pytest.mark.asyncio
async def test_generate_uses_first_model_and_sends_auth(
    monkeypatch: pytest.MonkeyPatch, respx_mock
) -> None:
    monkeypatch.setattr(
        "app.services.introduction_service.model_settings.intro_api_key", lambda: "sk-test"
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
        "app.services.introduction_service.model_settings.intro_api_key", lambda: "sk-test"
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
        "app.services.introduction_service.model_settings.intro_api_key", lambda: "sk-test"
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
    """替代 `asyncio.sleep`，让模型回退之间的退避不真的等待。"""
    return None  # noqa: RET501


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
    """整批失败后拆成单条；单条仍失败则去掉 README 再试一次，两次都失败才记为缺失。"""
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
