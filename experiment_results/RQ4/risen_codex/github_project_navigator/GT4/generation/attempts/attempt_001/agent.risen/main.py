from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen


GITHUB_API_VERSION = "2026-03-10"
USER_AGENT = "cnlp-github-project-assistant"


def _read_dotenv() -> dict[str, str]:
    """Read simple KEY=VALUE entries from the current directory's .env file."""
    values: dict[str, str] = {}
    env_path = Path.cwd() / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return values
    except OSError as exc:
        raise RuntimeError(f"Could not read .env: {exc}") from exc

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def _setting(name: str, dotenv: dict[str, str]) -> str:
    # A process environment variable is the most explicit configuration.
    return os.environ.get(name, dotenv.get(name, "")).strip()


class RuntimeLanguageModel:
    """Small adapter around the official OpenAI Python client."""

    def __init__(self) -> None:
        dotenv = _read_dotenv()
        api_key = _setting("OPENAI_API_KEY", dotenv)
        base_url = _setting("BASE_URL", dotenv)
        model = _setting("CNLP_REFERENCE_LLM_MODEL", dotenv) or _setting(
            "OPENAI_MODEL", dotenv
        )
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured in the environment or .env."
            )
        if not base_url:
            raise RuntimeError(
                "BASE_URL is not configured in the environment or .env."
            )
        if not model:
            raise RuntimeError(
                "Set CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL in the environment or .env."
            )

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The official OpenAI Python client is required; install the 'openai' package."
            ) from exc

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def _complete(self, prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            reasoning={"effort": "high"},
        )
        text = getattr(response, "output_text", "")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("The language model returned an empty response.")
        return text.strip()

    def text(self, prompt: str) -> str:
        return self._complete(prompt)

    def json(self, prompt: str) -> dict[str, Any]:
        raw = self._complete(
            prompt
            + "\n\nReturn only one valid JSON object. Do not use Markdown fences."
        )
        candidate = raw.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate).strip()
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start < 0 or end <= start:
                raise RuntimeError("The language model returned invalid JSON.")
            try:
                value = json.loads(candidate[start : end + 1])
            except json.JSONDecodeError as exc:
                raise RuntimeError("The language model returned invalid JSON.") from exc
        if not isinstance(value, dict):
            raise RuntimeError("The language model returned a JSON value that is not an object.")
        return value


def parse_github_repository_input(project_input: str) -> dict[str, str]:
    """Convert one explicit GitHub Repository input into canonical fields."""
    if not isinstance(project_input, str):
        raise ValueError("GitHub Repository input must be a string.")
    value = project_input.strip()
    if not value:
        raise ValueError("GitHub Repository input must not be empty.")

    if "://" in value:
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("GitHub Repository URL is malformed.") from exc
        hostname = parsed.hostname.lower() if parsed.hostname else ""
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or hostname not in {"github.com", "www.github.com"}
            or parsed.username is not None
            or parsed.password is not None
            or port not in {None, 80, 443}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("GitHub Repository URL is invalid.")
        parts = [unquote(part) for part in parsed.path.split("/") if part]
    else:
        if any(character.isspace() for character in value):
            raise ValueError("GitHub owner/repository identifier is invalid.")
        parts = value.split("/")

    if len(parts) != 2 or not all(parts):
        raise ValueError(
            "GitHub Repository input must identify exactly one owner and repository."
        )
    owner, repository = parts
    if repository.lower().endswith(".git"):
        repository = repository[:-4]
    owner_pattern = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?")
    repository_pattern = re.compile(r"[A-Za-z0-9._-]+")
    if not owner_pattern.fullmatch(owner) or not repository_pattern.fullmatch(repository):
        raise ValueError("GitHub owner or repository name is invalid.")
    return {
        "owner": owner,
        "repository": repository,
        "repository_url": f"https://github.com/{owner}/{repository}",
    }


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": USER_AGENT,
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _read_json(url: str, *, error_prefix: str) -> Any:
    try:
        request = Request(url, headers=_github_headers(), method="GET")
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"{error_prefix} returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{error_prefix} could not be read: {type(exc).__name__}: {exc}") from exc


def _repo_api_url(owner: str, repository: str) -> str:
    valid_component = re.compile(r"^[A-Za-z0-9_.-]+$")
    owner_value = str(owner).strip()
    repository_value = str(repository).strip()
    if (
        not owner_value
        or not repository_value
        or not valid_component.fullmatch(owner_value)
        or not valid_component.fullmatch(repository_value)
    ):
        raise ValueError("Invalid GitHub owner or repository name.")
    return "https://api.github.com/repos/" + quote(owner_value, safe="") + "/" + quote(
        repository_value, safe=""
    )


def get_github_project_overview(owner: str, repository: str) -> dict[str, object]:
    """Read repository metadata and README, treating only HTTP 404 as not found."""
    repository_api_url = _repo_api_url(owner, repository)
    try:
        metadata = _read_json(repository_api_url, error_prefix="GitHub repository metadata")
    except RuntimeError as exc:
        if "returned HTTP 404" in str(exc):
            return {
                "found": False,
                "full_name": "",
                "repository_url": "",
                "description": "",
                "readme": "",
                "license": "",
                "primary_language": "",
                "topics": [],
                "stars": 0,
                "forks": 0,
                "open_issues": 0,
                "archived": False,
                "updated_at": "",
            }
        raise
    if not isinstance(metadata, dict):
        raise RuntimeError("GitHub returned malformed repository metadata.")

    readme = ""
    readme_headers = _github_headers()
    readme_headers["Accept"] = "application/vnd.github.raw+json"
    try:
        request = Request(repository_api_url + "/readme", headers=readme_headers, method="GET")
        with urlopen(request, timeout=30) as response:
            readme = response.read(50001).decode("utf-8", errors="replace")
            if len(readme) > 50000:
                readme = readme[:50000]
    except HTTPError as exc:
        if exc.code != 404:
            raise RuntimeError(f"GitHub README lookup returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"GitHub README could not be read: {type(exc).__name__}: {exc}") from exc

    license_data = metadata.get("license")
    license_name = (
        str(license_data.get("spdx_id") or license_data.get("name") or "")
        if isinstance(license_data, dict)
        else ""
    )
    raw_topics = metadata.get("topics")
    topics = [str(item) for item in raw_topics if isinstance(item, str)] if isinstance(raw_topics, list) else []
    return {
        "found": True,
        "full_name": str(metadata.get("full_name") or ""),
        "repository_url": str(metadata.get("html_url") or ""),
        "description": str(metadata.get("description") or ""),
        "readme": readme,
        "license": license_name,
        "primary_language": str(metadata.get("language") or ""),
        "topics": topics,
        "stars": int(metadata.get("stargazers_count") or 0),
        "forks": int(metadata.get("forks_count") or 0),
        "open_issues": int(metadata.get("open_issues_count") or 0),
        "archived": bool(metadata.get("archived", False)),
        "updated_at": str(metadata.get("updated_at") or ""),
    }


def get_github_issue_information(owner: str, repository: str) -> dict[str, object]:
    """Read at most the first 100 recently updated open Issues, excluding PRs."""
    url = _repo_api_url(owner, repository) + "/issues?" + urlencode(
        {"state": "open", "sort": "updated", "direction": "desc", "per_page": 100, "page": 1}
    )
    payload = _read_json(url, error_prefix="GitHub Issues")
    if not isinstance(payload, list):
        raise RuntimeError("GitHub returned malformed Issue data.")
    issues: list[str] = []
    for item in payload:
        if not isinstance(item, dict) or "pull_request" in item:
            continue
        raw_labels = item.get("labels", [])
        labels = [
            str(label["name"])
            for label in raw_labels
            if isinstance(label, dict) and label.get("name")
        ] if isinstance(raw_labels, list) else []
        body = str(item.get("body") or "")[:4000]
        issues.append(
            "\n".join(
                [
                    f"#{int(item.get('number') or 0)}: {str(item.get('title') or '')}",
                    f"URL: {item.get('html_url') or ''}",
                    f"State: {item.get('state') or ''}",
                    f"Updated at: {item.get('updated_at') or ''}",
                    f"Comments: {int(item.get('comments') or 0)}",
                    f"Labels: {', '.join(labels) if labels else 'none'}",
                    f"Body: {body}",
                ]
            )
        )
    return {"analyzed_issue_count": len(issues), "issues": issues}


def get_github_release(owner: str, repository: str) -> dict[str, object]:
    """Read only latest Release metadata and maintainer-uploaded asset metadata."""
    selected = _read_json(
        _repo_api_url(owner, repository) + "/releases/latest",
        error_prefix="GitHub Release data",
    )
    if not isinstance(selected, dict):
        raise RuntimeError("GitHub returned malformed Release data.")
    raw_assets = selected.get("assets", [])
    assets = [
        {
            "name": str(asset.get("name") or ""),
            "download_url": str(asset.get("browser_download_url") or ""),
            "size": int(asset.get("size") or 0),
            "digest": str(asset.get("digest") or ""),
        }
        for asset in raw_assets
        if isinstance(asset, dict)
    ] if isinstance(raw_assets, list) else []
    return {
        "version": str(selected.get("tag_name") or ""),
        "release_name": str(selected.get("name") or ""),
        "release_notes": str(selected.get("body") or "")[:50000],
        "published_at": str(selected.get("published_at") or ""),
        "assets": assets,
        "source_zip_url": str(selected.get("zipball_url") or ""),
        "source_tar_url": str(selected.get("tarball_url") or ""),
    }


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} bytes"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size / (1024 * 1024):.1f} MiB"


def _is_source_archive(asset: dict[str, object], release: dict[str, object]) -> bool:
    url = str(asset.get("download_url") or "")
    name = str(asset.get("name") or "").lower()
    return url in {str(release.get("source_zip_url") or ""), str(release.get("source_tar_url") or "")} or name in {
        "source.zip",
        "source.tar.gz",
        "source.tar",
        "source code.zip",
        "source code.tar.gz",
    }


class GitHubProjectAssistant:
    def __init__(self) -> None:
        self.project_input = ""
        self.input_kind = "unclear"
        self.repository_input_retry_count = 0
        self.repository_input_limit_exceeded = False
        self.llm: RuntimeLanguageModel | None = None

    def _language_model(self) -> RuntimeLanguageModel:
        if self.llm is None:
            self.llm = RuntimeLanguageModel()
        return self.llm

    def _ask_yes_no(self, answer: str, question: str) -> str:
        result = self._language_model().json(
            "Classify the user's answer to the question below as exactly yes or no. "
            "Use yes only when the user clearly agrees/opts in; use no when they decline "
            "or do not opt in. If the answer is ambiguous, choose no.\n"
            f"Question: {question}\nUser answer: {answer}\n"
            'Return JSON with exactly this field: {"choice":"yes" or "no"}.'
        )
        choice = str(result.get("choice", "")).strip().lower()
        if choice not in {"yes", "no"}:
            raise RuntimeError("The language model did not return a valid yes/no choice.")
        return choice

    def _project_summary(self, overview: dict[str, object]) -> str:
        prompt = (
            "You are summarizing one GitHub repository using only the evidence supplied. "
            "Write clear English prose with short labeled paragraphs. Explain the project "
            "name, purpose, core capabilities, typical use cases, intended users, primary "
            "technology, execution or installation entry points, license, maintenance status, "
            "and important README limitations. Distinguish facts from unavailable information; "
            "do not invent commands, features, or conclusions. Do not assess quality from stars "
            "or open issue count alone. Do not merely copy the README.\n\n"
            f"Repository evidence:\n{json.dumps(overview, ensure_ascii=False, indent=2)}"
        )
        return self._language_model().text(prompt)

    def _analyze_issues(self, selected: dict[str, str]) -> dict[str, object]:
        information = get_github_issue_information(selected["owner"], selected["repository"])
        count = int(information["analyzed_issue_count"])
        prompt = (
            "Analyze the supplied limited sample of recently updated, open GitHub Issues. "
            "Return evidence-based JSON fields common_problems, confirmed_problems, "
            "unresolved_problems, representative_issues, and limitations, each an array of "
            "English strings. Distinguish repeated concerns, isolated reports, maintainer-"
            "confirmed problems, and unresolved reports. Only call something common when the "
            "sample supports repetition, and never turn one user report into a general problem. "
            "Select a small representative set using issue numbers and URLs where available. "
            f"The exact sample count is {count}; state that scope and what it cannot establish "
            "in limitations. Do not infer facts absent from the issue text.\n\n"
            f"Issue sample:\n{json.dumps(information, ensure_ascii=False, indent=2)}"
        )
        result = self._language_model().json(prompt)
        limitations = _as_string_list(result.get("limitations"))
        scope = f"Analysis covers exactly {count} recently updated open Issues returned by GitHub (pull requests excluded)."
        if scope not in limitations:
            limitations.insert(0, scope)
        if not any("cannot establish" in item.lower() for item in limitations):
            limitations.append(
                "This limited, recently updated sample cannot establish the full project's issue history_result_before_revision, prevalence, or overall quality."
            )
        return {
            "analyzed_issue_count": count,
            "common_problems": _as_string_list(result.get("common_problems")),
            "confirmed_problems": _as_string_list(result.get("confirmed_problems")),
            "unresolved_problems": _as_string_list(result.get("unresolved_problems")),
            "representative_issues": _as_string_list(result.get("representative_issues")),
            "limitations": limitations,
        }

    def _release_advice(
        self, selected: dict[str, str], request: dict[str, str]
    ) -> dict[str, object]:
        release = get_github_release(selected["owner"], selected["repository"])
        latest_url = f"https://github.com/{selected['owner']}/{selected['repository']}/releases/latest"
        if request["analysis_mode"] == "overview":
            summary = self._language_model().text(
                "Write a concise English overview of this latest official GitHub Release. "
                "Include key points from the release notes without inventing details. Mention "
                f"the exact asset count ({len(release['assets'])}). This is metadata-only guidance; "
                "do not suggest that any file was downloaded or operated on.\n\n"
                f"Release metadata:\n{json.dumps(release, ensure_ascii=False, indent=2)}"
            )
            return {
                "status": "overview",
                "version": str(release["version"]),
                "summary": summary,
                "acquisition_url": latest_url,
                "integrity_guidance": "No file operation was performed. If you later obtain an asset yourself, verify its published digest when one is available.",
                "limitations": [
                    "Only the latest official public Release was examined.",
                    "Release metadata was read without downloading, creating, installing, extracting, or executing any file.",
                ],
            }

        usable_assets = [
            asset for asset in release["assets"] if not _is_source_archive(asset, release)
        ]
        selection = self._language_model().json(
            "Choose the most suitable maintainer-uploaded Release asset for the stated user "
            "preferences. Exclude automatically generated Source code zip/tar archives and do "
            "not treat them as installable software. Infer compatibility from asset names only "
            "when the name provides evidence; if no suitable asset is supported, return found "
            "false. Return JSON with found (boolean), asset_name (string or empty), reason "
            "(string), compatibility_rationale (string), and verification_guidance (string).\n"
            f"Preferences: {json.dumps(request, ensure_ascii=False)}\n"
            f"Candidate maintainer-uploaded assets (metadata only): {json.dumps(usable_assets, ensure_ascii=False, indent=2)}"
        )
        found = bool(selection.get("found"))
        chosen_name = str(selection.get("asset_name") or "")
        chosen = next((asset for asset in usable_assets if asset["name"] == chosen_name), None)
        reason = str(selection.get("reason") or "No candidate asset was supported by the available metadata.")
        if not found or chosen is None:
            return {
                "status": "no_match",
                "version": str(release["version"]),
                "summary": reason,
                "acquisition_url": latest_url,
                "integrity_guidance": "No asset was selected. Do not download or install a file based on this result.",
                "limitations": [
                    "No maintainer-uploaded asset could be matched with sufficient evidence to all requested preferences.",
                    "Automatically generated Source code archives are not installable assets by default.",
                    "No file was downloaded, created, installed, extracted, or executed.",
                ],
            }

        digest = str(chosen.get("digest") or "")
        integrity = str(selection.get("verification_guidance") or "Verify the downloaded file against the published digest before use.")
        if digest:
            integrity += f" Published digest: {digest}."
        else:
            integrity += " GitHub did not provide a digest for this asset."
        summary = (
            f"Recommended asset: {chosen['name']} ({_format_size(int(chosen['size']))}). "
            f"{str(selection.get('compatibility_rationale') or reason)}"
        )
        return {
            "status": "recommended",
            "version": str(release["version"]),
            "summary": summary,
            "acquisition_url": str(chosen["download_url"]),
            "integrity_guidance": integrity,
            "limitations": [
                "Compatibility is based on the Release asset metadata and the stated preferences; local hardware and platform details were not tested.",
                "No file was downloaded, created, installed, extracted, or executed.",
            ],
            "asset": {
                "name": str(chosen["name"]),
                "download_url": str(chosen["download_url"]),
                "size": int(chosen["size"]),
                "digest": digest,
            },
        }

    @staticmethod
    def _parse_release_request(answer: str) -> dict[str, str]:
        parts = [part.strip().lower() for part in answer.strip().split(";")]
        if len(parts) == 1 and parts[0] == "overview":
            return {"analysis_mode": "overview"}
        if len(parts) != 4 or parts[0] != "asset_match":
            raise ValueError(
                "Release request must be exactly 'overview' or 'asset_match;operating_system;architecture;package_preference'."
            )
        allowed = [
            {"windows", "macos", "linux", "other"},
            {"x64", "arm64", "unknown"},
            {"installer", "portable", "archive", "any"},
        ]
        if any(value not in choices for value, choices in zip(parts[1:], allowed)):
            raise ValueError("Release request contains an unsupported operating system, architecture, or package preference.")
        return {
            "analysis_mode": "asset_match",
            "operating_system": parts[1],
            "architecture": parts[2],
            "package_preference": parts[3],
        }

    def run(self) -> dict[str, object]:
        print(
            "I am GitHubProjectAssistant. Provide a complete GitHub Repository URL or an explicit "
            "owner/repository identifier. I can summarize public project information, analyze "
            "recent open Issues, and provide Release guidance without downloading files."
        )
        self.project_input = input("Repository: ").strip()
        try:
            selected = parse_github_repository_input(self.project_input)
            self.input_kind = "repository_url" if "://" in self.project_input else "repository_name"
        except (TypeError, ValueError):
            self.input_kind = "unclear"

        while self.input_kind == "unclear" and self.repository_input_retry_count < 3:
            print(
                "The current input does not uniquely identify a Repository. Please enter a complete "
                "GitHub Repository URL or an explicit owner/repository identifier."
            )
            self.project_input = input("Repository: ").strip()
            self.repository_input_retry_count += 1
            try:
                selected = parse_github_repository_input(self.project_input)
                self.input_kind = "repository_url" if "://" in self.project_input else "repository_name"
            except (TypeError, ValueError):
                self.input_kind = "unclear"

        self.repository_input_limit_exceeded = (
            self.input_kind == "unclear" and self.repository_input_retry_count >= 3
        )
        if self.repository_input_limit_exceeded:
            project_summary = "The Repository input remains unclear after three correction attempts. The target Repository could not be determined."
            print(project_summary)
            print("GitHub was not accessed, and no Issue or Release analysis was performed.")
            return {"project_summary": project_summary}

        overview = get_github_project_overview(selected["owner"], selected["repository"])
        if not overview["found"]:
            project_summary = (
                f"Repository {selected['owner']}/{selected['repository']} was not found on GitHub. "
                "This is a Repository-not-found result, not a conclusion about network, authentication, rate-limit, or service failure."
            )
            print(project_summary)
            return {"project_summary": project_summary}

        project_summary = self._project_summary(overview)
        print("\nPROJECT OVERVIEW\n" + project_summary)
        issue_choice = self._ask_yes_no(
            input("Would you like an analysis of recently updated open Issues? "),
            "Would the user like an analysis of recently updated open Issues?",
        )
        issue_result: dict[str, object] | None = None
        if issue_choice == "yes":
            issue_result = self._analyze_issues(selected)

        release_choice = self._ask_yes_no(
            input("Would you like guidance about the latest official Release? "),
            "Would the user like guidance about the latest official Release?",
        )
        release_advice: dict[str, object] | None = None
        if release_choice == "yes":
            print(
                "Enter either 'overview' or 'asset_match;operating_system;architecture;package_preference'. "
                "Use operating_system windows/macos/linux/other, architecture x64/arm64/unknown, "
                "and package_preference installer/portable/archive/any."
            )
            release_request = self._parse_release_request(input("Release request: "))
            release_advice = self._release_advice(selected, release_request)

        result: dict[str, object] = {"project_summary": project_summary}
        if issue_result is not None:
            result["issue_analysis_result"] = issue_result
        if release_advice is not None:
            result["release_advice"] = release_advice
        print("\nFINAL RESULT\n" + json.dumps(result, ensure_ascii=False, indent=2))
        return result


def main() -> dict[str, object] | None:
    """Initialize and run the terminal Agent."""
    agent = GitHubProjectAssistant()
    try:
        return agent.run()
    except (EOFError, KeyboardInterrupt):
        print("\nExecution stopped before the requested interaction completed.")
    except Exception as exc:
        print(f"Execution failed: {exc}")
    return None


if __name__ == "__main__":
    main()
