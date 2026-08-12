from __future__ import annotations

from ai_intel.config import Settings
from ai_intel.github import GitHubMetricsClient
from ai_intel.utils.github import normalize_github_repo_url


class FakeResponse:
    def __init__(self, status: int, payload: dict[str, object], headers: dict[str, str] | None = None) -> None:
        self.status = status
        self._payload = payload
        self.headers = headers or {}

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def json(self) -> dict[str, object]:
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.requested_url: str | None = None
        self.requested_headers: dict[str, str] | None = None

    def get(self, url: str, headers: dict[str, str]) -> FakeResponse:
        self.requested_url = url
        self.requested_headers = headers
        return FakeResponse(
            200,
            {
                "html_url": "https://github.com/openai/whisper",
                "full_name": "openai/whisper",
                "stargazers_count": 777,
            },
        )


def test_normalize_github_repo_url_strips_tree_and_git_suffix() -> None:
    normalized = normalize_github_repo_url("https://github.com/openai/whisper.git/tree/main")

    assert normalized is not None
    assert normalized.owner == "openai"
    assert normalized.repo == "whisper"
    assert normalized.api_url == "https://api.github.com/repos/openai/whisper"


async def test_github_metrics_client_extracts_stargazers_count() -> None:
    session = FakeSession()
    metrics = await GitHubMetricsClient(Settings()).fetch_metrics(
        session,
        "https://github.com/openai/whisper",
    )

    assert metrics is not None
    assert session.requested_url == "https://api.github.com/repos/openai/whisper"
    assert metrics.stars == 777
    assert metrics.owner == "openai"
    assert metrics.repo == "whisper"

