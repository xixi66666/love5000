from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.collector.github_client import (
    README_MAX_CHARS,
    GitHubAuthError,
    GitHubClient,
    GitHubRateLimitError,
    GitHubRequestError,
)

API = "https://api.github.com"


@respx.mock
async def test_public_repository_without_token_omits_authorization_header() -> None:
    route = respx.get(f"{API}/repos/octocat/agent-hub").mock(
        return_value=httpx.Response(200, json=make_repo_payload())
    )
    async with GitHubClient(token="") as anonymous:
        assert await anonymous.get_repository("octocat/agent-hub") is not None
    assert "authorization" not in route.calls.last.request.headers


def make_repo_payload(github_id: int = 1, name: str = "agent-hub") -> dict:
    return {
        "id": github_id,
        "name": name,
        "full_name": f"octocat/{name}",
        "owner": {"login": "octocat"},
        "html_url": f"https://github.com/octocat/{name}",
        "homepage": None,
        "description": "A useful agent",
        "language": "Python",
        "topics": ["ai-agent"],
        "stargazers_count": 150,
        "forks_count": 10,
        "open_issues_count": 2,
        "archived": False,
        "disabled": False,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-08-01T00:00:00Z",
        "ignored_field": "must be ignored",
    }


@pytest.fixture()
def client() -> GitHubClient:
    return GitHubClient(token="test-token", retry_delays=(0.0, 0.0, 0.0))


@respx.mock
async def test_get_repository_returns_none_on_404(client: GitHubClient) -> None:
    respx.get(f"{API}/repos/octocat/missing").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )
    async with client:
        repo = await client.get_repository("octocat/missing")
    assert repo is None


@respx.mock
async def test_get_repository_parses_dto(client: GitHubClient) -> None:
    respx.get(f"{API}/repos/octocat/agent-hub").mock(
        return_value=httpx.Response(200, json=make_repo_payload())
    )
    async with client:
        repo = await client.get_repository("octocat/agent-hub")
    assert repo is not None
    assert repo.full_name == "octocat/agent-hub"
    assert repo.stars_count == 150
    assert repo.topics == ["ai-agent"]
    assert repo.github_created_at.year == 2026


@respx.mock
async def test_get_readme_returns_raw_text(client: GitHubClient) -> None:
    route = respx.get(f"{API}/repos/octocat/agent-hub/readme").mock(
        return_value=httpx.Response(200, text="# Agent Hub\n\nInstall with pip.")
    )
    async with client:
        readme = await client.get_readme("octocat/agent-hub")
    assert readme == "# Agent Hub\n\nInstall with pip."
    assert "application/vnd.github.raw" in route.calls.last.request.headers["accept"]


@respx.mock
async def test_get_readme_returns_none_on_404(client: GitHubClient) -> None:
    respx.get(f"{API}/repos/octocat/missing/readme").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )
    async with client:
        readme = await client.get_readme("octocat/missing")
    assert readme is None


@respx.mock
async def test_get_readme_truncates_long_text(client: GitHubClient) -> None:
    respx.get(f"{API}/repos/octocat/huge/readme").mock(
        return_value=httpx.Response(200, text="x" * (README_MAX_CHARS + 500))
    )
    async with client:
        readme = await client.get_readme("octocat/huge")
    assert readme is not None
    assert len(readme) == README_MAX_CHARS


@respx.mock
async def test_rate_limit_error_when_remaining_zero(client: GitHubClient) -> None:
    respx.get(f"{API}/repos/octocat/agent-hub").mock(
        return_value=httpx.Response(
            403,
            json={"message": "API rate limit exceeded"},
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1752000000"},
        )
    )
    async with client:
        with pytest.raises(GitHubRateLimitError) as exc_info:
            await client.get_repository("octocat/agent-hub")
    assert exc_info.value.reset_at == datetime.fromtimestamp(1752000000, tz=UTC)


@respx.mock
async def test_auth_error_on_401(client: GitHubClient) -> None:
    respx.get(f"{API}/repos/octocat/agent-hub").mock(
        return_value=httpx.Response(401, json={"message": "Bad credentials"})
    )
    async with client:
        with pytest.raises(GitHubAuthError):
            await client.get_repository("octocat/agent-hub")


@respx.mock
async def test_retries_three_times_then_raises(client: GitHubClient) -> None:
    route = respx.get(f"{API}/repos/octocat/agent-hub").mock(
        return_value=httpx.Response(500, json={"message": "boom"})
    )
    async with client:
        with pytest.raises(GitHubRequestError):
            await client.get_repository("octocat/agent-hub")
    assert len(route.calls) == 3


@respx.mock
async def test_retries_transport_disconnect_then_wraps_error(client: GitHubClient) -> None:
    route = respx.get(f"{API}/repos/octocat/flaky").mock(
        side_effect=httpx.RemoteProtocolError("server disconnected")
    )

    async with client:
        with pytest.raises(GitHubRequestError, match="transport failed"):
            await client.get_repository("octocat/flaky")

    assert len(route.calls) == 3


@respx.mock
async def test_get_rate_limit_parses_headers(client: GitHubClient) -> None:
    respx.get(f"{API}/rate_limit").mock(
        return_value=httpx.Response(
            200,
            json={"resources": {"core": {"remaining": 42, "reset": 1752000000}}},
            headers={"X-RateLimit-Remaining": "42"},
        )
    )
    async with client:
        rate_limit = await client.get_rate_limit()
    assert rate_limit.remaining == 42
    assert rate_limit.reset_at == datetime.fromtimestamp(1752000000, tz=UTC)




