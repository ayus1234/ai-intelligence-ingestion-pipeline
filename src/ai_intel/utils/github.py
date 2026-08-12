"""GitHub repository URL normalization."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class NormalizedGitHubRepo:
    owner: str
    repo: str
    html_url: str
    api_url: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"


def normalize_github_repo_url(url: str | None) -> NormalizedGitHubRepo | None:
    if not url:
        return None
    value = url.strip()
    if value.startswith("git@github.com:"):
        value = "https://github.com/" + value.split(":", 1)[1]
    parts = urlsplit(value)
    host = parts.netloc.lower()
    if host not in {"github.com", "www.github.com"}:
        return None
    path_parts = [part for part in parts.path.strip("/").split("/") if part]
    if len(path_parts) < 2:
        return None
    owner = path_parts[0]
    repo = path_parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        return None
    html_url = f"https://github.com/{owner}/{repo}"
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    return NormalizedGitHubRepo(owner=owner, repo=repo, html_url=html_url, api_url=api_url)
