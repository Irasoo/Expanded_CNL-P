from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

from openai import OpenAI


DEFAULT_PROJECT_SUMMARY = (
    "No project summary is available because the target Repository was not resolved."
)


class AgentExecutionError(RuntimeError):
    """An external service, configuration, or response prevented execution."""


def load_dotenv(path: str = ".env") -> None:
    """Load simple KEY=VALUE entries without overriding process environment."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except FileNotFoundError:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


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


def classify_project_input(project_input: str) -> str:
    try:
        parse_github_repository_input(project_input)
    except (TypeError, ValueError):
        return "unclear"
    return "repository_url" if "://" in project_input.strip() else "repository_name"


def _github_headers() -> dict[str, str]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "cnlp-github-project-assistant",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _read_json(url: str, headers: dict[str, str], operation: str) -> Any:
    try:
        request = Request(url, headers=headers, method="GET")
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise AgentExecutionError(f"{operation} returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise AgentExecutionError(
            f"{operation} could not be read: {type(exc).__name__}: {exc}"
        ) from exc


def _not_found_overview() -> dict[str, object]:
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


def get_github_project_overview(owner: str, repository: str) -> dict[str, object]:
    """Read public repository metadata and README; a public 404 means not found."""
    owner_value = str(owner).strip()
    repository_value = str(repository).strip()
    valid_component = re.compile(r"^[A-Za-z0-9_.-]+$")
    if (
        not owner_value
        or not repository_value
        or not valid_component.fullmatch(owner_value)
        or not valid_component.fullmatch(repository_value)
    ):
        raise ValueError("Invalid GitHub owner or repository name.")

    base_url = (
        "https://api.github.com/repos/"
        f"{quote(owner_value, safe='')}/{quote(repository_value, safe='')}"
    )
    headers = _github_headers()
    try:
        request = Request(base_url, headers=headers, method="GET")
        with urlopen(request, timeout=30) as response:
            metadata = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return _not_found_overview()
        raise AgentExecutionError(
            f"GitHub repository lookup returned HTTP {exc.code}."
        ) from exc
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise AgentExecutionError(
            "GitHub repository metadata could not be read: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(metadata, dict):
        raise AgentExecutionError("GitHub returned malformed repository metadata.")

    readme = ""
    readme_headers = dict(headers)
    readme_headers["Accept"] = "application/vnd.github.raw+json"
    try:
        request = Request(base_url + "/readme", headers=readme_headers, method="GET")
        with urlopen(request, timeout=30) as response:
            readme = response.read(50001).decode("utf-8", errors="replace")
            if len(readme) > 50000:
                readme = readme[:50000]
    except HTTPError as exc:
        if exc.code != 404:
            raise AgentExecutionError(
                f"GitHub README lookup returned HTTP {exc.code}."
            ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise AgentExecutionError(
            "GitHub README could not be read: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    license_data = metadata.get("license")
    license_name = (
        str(license_data.get("spdx_id") or license_data.get("name") or "")
        if isinstance(license_data, dict)
        else ""
    )
    raw_topics = metadata.get("topics")
    topics = (
        [str(item) for item in raw_topics if isinstance(item, str)]
        if isinstance(raw_topics, list)
        else []
    )
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
    """Read up to 100 recently updated open Issues, excluding pull requests."""
    owner_value = str(owner).strip()
    repository_value = str(repository).strip()
    if not owner_value or not repository_value:
        raise ValueError("GitHub owner and repository are required.")

    url = (
        "https://api.github.com/repos/"
        f"{quote(owner_value, safe='')}/{quote(repository_value, safe='')}"
        "/issues?"
        + urlencode(
            {
                "state": "open",
                "sort": "updated",
                "direction": "desc",
                "per_page": 100,
                "page": 1,
            }
        )
    )
    payload = _read_json(url, _github_headers(), "GitHub Issues")
    if not isinstance(payload, list):
        raise AgentExecutionError("GitHub returned malformed Issue data.")

    issues: list[str] = []
    for item in payload:
        if not isinstance(item, dict) or "pull_request" in item:
            continue
        raw_labels = item.get("labels", [])
        labels = (
            [
                str(label["name"])
                for label in raw_labels
                if isinstance(label, dict) and label.get("name")
            ]
            if isinstance(raw_labels, list)
            else []
        )
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
    """Read the latest official public Release and maintainer-uploaded asset metadata."""
    owner_value = str(owner).strip()
    repository_value = str(repository).strip()
    if not owner_value or not repository_value:
        raise ValueError("GitHub owner and repository are required.")

    base_url = (
        "https://api.github.com/repos/"
        f"{quote(owner_value, safe='')}/{quote(repository_value, safe='')}"
        "/releases/latest"
    )
    selected = _read_json(base_url, _github_headers(), "GitHub Release lookup")
    if not isinstance(selected, dict):
        raise AgentExecutionError("GitHub returned malformed Release data.")

    raw_assets = selected.get("assets", [])
    assets = (
        [
            {
                "name": str(asset.get("name") or ""),
                "download_url": str(asset.get("browser_download_url") or ""),
                "size": int(asset.get("size") or 0),
                "digest": str(asset.get("digest") or ""),
            }
            for asset in raw_assets
            if isinstance(asset, dict)
        ]
        if isinstance(raw_assets, list)
        else []
    )
    return {
        "version": str(selected.get("tag_name") or ""),
        "release_name": str(selected.get("name") or ""),
        "release_notes": str(selected.get("body") or "")[:50000],
        "published_at": str(selected.get("published_at") or ""),
        "assets": assets,
        "source_zip_url": str(selected.get("zipball_url") or ""),
        "source_tar_url": str(selected.get("tarball_url") or ""),
    }


@dataclass
class LLMService:
    client: OpenAI
    model: str

    @classmethod
    def from_environment(cls) -> "LLMService":
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        base_url = os.getenv("BASE_URL", "").strip()
        model = os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip() or os.getenv(
            "OPENAI_MODEL", ""
        ).strip()
        if not api_key:
            raise AgentExecutionError("OPENAI_API_KEY is not configured.")
        if not base_url:
            raise AgentExecutionError("BASE_URL is not configured.")
        if not model:
            raise AgentExecutionError(
                "No LLM model is configured; set CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL."
            )
        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
        except Exception as exc:
            raise AgentExecutionError(
                f"The OpenAI client could not be initialized: {type(exc).__name__}: {exc}"
            ) from exc
        return cls(client=client, model=model)

    def json_call(
        self,
        name: str,
        schema: dict[str, Any],
        system_prompt: str,
        user_payload: Any,
    ) -> dict[str, Any]:
        try:
            response = self.client.responses.create(
                model=self.model,
                reasoning={"effort": "high"},
                input=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(user_payload, ensure_ascii=False),
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": name,
                        "strict": True,
                        "schema": schema,
                    }
                },
            )
            raw = response.output_text
            parsed = json.loads(raw)
        except Exception as exc:
            raise AgentExecutionError(
                f"Runtime language-model operation '{name}' failed: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise AgentExecutionError(f"Language-model operation '{name}' returned non-object JSON.")
        return parsed


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def interpret_yes_no(llm: LLMService, answer: str) -> str:
    result = llm.json_call(
        "yes_no_interpretation",
        {
            "type": "object",
            "properties": {"choice": {"type": "string", "enum": ["yes", "no"]}},
            "required": ["choice"],
            "additionalProperties": False,
        },
        (
            "Interpret the user's single natural-language answer to a yes/no question. "
            "Return yes only when the user clearly agrees; return no when the user "
            "declines or does not clearly agree. Do not infer missing facts."
        ),
        {"answer": answer},
    )
    choice = result.get("choice")
    if choice not in {"yes", "no"}:
        raise AgentExecutionError("The language model returned an invalid yes/no choice.")
    return choice


def create_project_summary(llm: LLMService, overview: dict[str, object]) -> str:
    result = llm.json_call(
        "project_overview_summary",
        {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
            "additionalProperties": False,
        },
        (
            "Write a clear English project overview from the supplied public GitHub facts. "
            "Cover project name, purpose, core capabilities, typical use cases, intended "
            "users, primary technology, execution or installation entry points, license, "
            "maintenance status, and important README limitations. Synthesize rather than "
            "copying the README. Never judge project quality from star count or open Issue "
            "count alone. If a fact is absent, say it is not stated."
        ),
        overview,
    )
    summary = result.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise AgentExecutionError("The project summary was empty or malformed.")
    return summary.strip()


def analyze_issues(llm: LLMService, issue_information: dict[str, object]) -> dict[str, object]:
    result = llm.json_call(
        "issue_analysis",
        {
            "type": "object",
            "properties": {
                "common_problems": {"type": "array", "items": {"type": "string"}},
                "confirmed_problems": {"type": "array", "items": {"type": "string"}},
                "unresolved_problems": {"type": "array", "items": {"type": "string"}},
                "representative_issues": {"type": "array", "items": {"type": "string"}},
                "limitations": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "common_problems",
                "confirmed_problems",
                "unresolved_problems",
                "representative_issues",
                "limitations",
            ],
            "additionalProperties": False,
        },
        (
            "Analyze only the supplied, recently updated open Issue sample. Distinguish "
            "repeated concerns from isolated reports, maintainer-confirmed problems from "
            "unconfirmed reports, and unresolved reports. Select a small set of representative "
            "Issues using their numbers or URLs. Never describe one report as a general project "
            "problem. Explicitly state in limitations what this limited sample cannot establish, "
            "including that it does not represent all users or closed Issues. Return concise English."
        ),
        issue_information,
    )
    count = issue_information.get("analyzed_issue_count")
    return {
        "analyzed_issue_count": int(count) if isinstance(count, (int, float)) else 0,
        "common_problems": _string_list(result.get("common_problems")),
        "confirmed_problems": _string_list(result.get("confirmed_problems")),
        "unresolved_problems": _string_list(result.get("unresolved_problems")),
        "representative_issues": _string_list(result.get("representative_issues")),
        "limitations": _string_list(result.get("limitations")),
    }


def parse_release_request(answer: str) -> dict[str, object]:
    value = answer.strip()
    if value == "overview":
        return {"analysis_mode": "overview"}
    parts = value.split(";")
    if len(parts) != 4 or parts[0] != "asset_match":
        raise AgentExecutionError(
            "Invalid ReleaseRequest. Use 'overview' or "
            "'asset_match;operating_system;architecture;package_preference'."
        )
    operating_system, architecture, package_preference = parts[1:]
    if operating_system not in {"windows", "macos", "linux", "other"}:
        raise AgentExecutionError("Invalid ReleaseRequest operating_system.")
    if architecture not in {"x64", "arm64", "unknown"}:
        raise AgentExecutionError("Invalid ReleaseRequest architecture.")
    if package_preference not in {"installer", "portable", "archive", "any"}:
        raise AgentExecutionError("Invalid ReleaseRequest package_preference.")
    return {
        "analysis_mode": "asset_match",
        "operating_system": operating_system,
        "architecture": architecture,
        "package_preference": package_preference,
    }


def _asset_is_source_archive(asset: dict[str, object]) -> bool:
    name = str(asset.get("name") or "").lower()
    return name in {"source.zip", "source.tar.gz", "source.tar"} or name.startswith(
        "source."
    )


def select_asset(
    llm: LLMService,
    release_information: dict[str, object],
    release_request: dict[str, object],
) -> dict[str, object]:
    assets = release_information.get("assets")
    if not isinstance(assets, list):
        assets = []
    usable_assets = [asset for asset in assets if isinstance(asset, dict)]
    result = llm.json_call(
        "release_asset_selection",
        {
            "type": "object",
            "properties": {
                "asset_index": {
                    "anyOf": [{"type": "integer"}, {"type": "null"}]
                },
                "reason": {"type": "string"},
            },
            "required": ["asset_index", "reason"],
            "additionalProperties": False,
        },
        (
            "Select the most suitable uploaded GitHub Release asset for the requested platform, "
            "architecture, and package preference. Use zero-based asset_index from the provided "
            "list, or null if no reliable match exists. Do not select source code archives or "
            "anything that is only an automatically generated source archive. Do not infer an "
            "unsupported platform. Explain the compatibility reasoning concisely."
        ),
        {"request": release_request, "assets": usable_assets},
    )
    index = result.get("asset_index")
    reason = result.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = "No compatibility reason was provided."
    if index is None:
        return {"found": False, "reason": reason.strip()}
    if not isinstance(index, int) or index < 0 or index >= len(usable_assets):
        raise AgentExecutionError("The language model returned an invalid Release asset index.")
    asset = usable_assets[index]
    if _asset_is_source_archive(asset):
        return {
            "found": False,
            "reason": "The proposed item is an automatically generated source archive, not a directly installable asset.",
        }
    return {"found": True, "reason": reason.strip(), "asset": asset}


def create_release_advice(
    llm: LLMService,
    release_information: dict[str, object],
    release_request: dict[str, object],
    asset_selection: dict[str, object] | None,
) -> dict[str, object]:
    if release_request["analysis_mode"] == "overview":
        result = llm.json_call(
            "release_overview",
            {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
                "additionalProperties": False,
            },
            (
                "Summarize the latest official GitHub Release in clear English. Include version, "
                "name, publication time, key Release Notes, and asset count. Do not claim to have "
                "downloaded or inspected files."
            ),
            release_information,
        )
        summary = str(result.get("summary") or "").strip()
        if not summary:
            raise AgentExecutionError("The Release overview was empty or malformed.")
        return {
            "status": "overview",
            "version": str(release_information.get("version") or ""),
            "summary": summary,
            "acquisition_url": "",
            "integrity_guidance": "No file operation was performed.",
            "limitations": [
                "Release files were not downloaded or inspected; the overview is based on GitHub metadata and notes."
            ],
        }

    selection = asset_selection or {"found": False, "reason": "No selection was made."}
    found = bool(selection.get("found"))
    asset = selection.get("asset") if isinstance(selection.get("asset"), dict) else None
    if found and asset is not None:
        name = str(asset.get("name") or "the selected asset")
        size = int(asset.get("size") or 0)
        digest = str(asset.get("digest") or "")
        integrity = (
            f"Verify the downloaded file's SHA-256 digest against {digest}."
            if digest
            else "GitHub did not provide a digest for this asset; verify the publisher and download URL before use."
        )
        result = llm.json_call(
            "release_asset_guidance",
            {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
                "additionalProperties": False,
            },
            (
                "Write concise English no-download guidance for the selected GitHub Release asset. "
                "Include its name, byte size, URL, digest, compatibility rationale, and user-side "
                "verification guidance. Explicitly state that no file was downloaded, created, "
                "installed, extracted, or executed. Do not instruct this Agent to perform those actions."
            ),
            {
                "release": release_information,
                "request": release_request,
                "selection": selection,
            },
        )
        summary = str(result.get("summary") or "").strip()
        if not summary:
            raise AgentExecutionError("The Release asset guidance was empty or malformed.")
        return {
            "status": "recommended",
            "version": str(release_information.get("version") or ""),
            "summary": summary,
            "acquisition_url": str(asset.get("download_url") or ""),
            "integrity_guidance": integrity,
            "limitations": [
                "Compatibility is inferred from asset metadata and the requested preferences; the file was not downloaded or inspected.",
            ],
            "asset": asset,
        }

    return {
        "status": "no_match",
        "version": str(release_information.get("version") or ""),
        "summary": (
            "No matching maintainer-uploaded Release asset was identified. "
            + str(selection.get("reason") or "The available assets did not provide a reliable match.")
        ),
        "acquisition_url": "",
        "integrity_guidance": "No file operation was performed.",
        "limitations": [
            "Source code zip and tar archives are not presented as directly installable software.",
            "No file was downloaded, created, installed, extracted, or executed.",
        ],
    }


class GitHubProjectAssistant:
    """Terminal-only coordinator for repository, Issue, and Release analysis."""

    def __init__(self) -> None:
        self.repository_input_retry_count = 0
        self.repository_input_limit_exceeded = False
        self.project_input = ""
        self.input_kind = "unclear"
        self.selected_repository: dict[str, str] | None = None
        self.project_overview: dict[str, object] | None = None
        self.repository_found = False
        self.project_summary = DEFAULT_PROJECT_SUMMARY
        self.issue_analysis_choice = "no"
        self.issue_information: dict[str, object] | None = None
        self.issue_analysis_result: dict[str, object] | None = None
        self.release_analysis_choice = "no"
        self.release_request: dict[str, object] | None = None
        self.release_information: dict[str, object] | None = None
        self.asset_selection: dict[str, object] | None = None
        self.release_advice: dict[str, object] | None = None
        self._llm: LLMService | None = None

    def llm(self) -> LLMService:
        if self._llm is None:
            self._llm = LLMService.from_environment()
        return self._llm

    def run(self) -> dict[str, object]:
        print(
            "GitHubProjectAssistant requires a complete GitHub Repository URL or an explicit "
            "owner/repository identifier. It can summarize public project information, analyze "
            "recent open Issues, and provide Release guidance without downloading files."
        )
        self.project_input = input("Enter a GitHub Repository URL or owner/repository: ")
        self.input_kind = classify_project_input(self.project_input)

        while self.input_kind == "unclear" and self.repository_input_retry_count < 3:
            print(
                "The current input does not uniquely identify a Repository. Please provide a "
                "complete GitHub Repository URL or an explicit owner/repository identifier."
            )
            self.project_input = input("Enter a GitHub Repository URL or owner/repository: ")
            self.repository_input_retry_count += 1
            self.input_kind = classify_project_input(self.project_input)

        self.repository_input_limit_exceeded = (
            self.input_kind == "unclear" and self.repository_input_retry_count >= 3
        )
        if self.repository_input_limit_exceeded:
            diagnostic = "The Repository input remains unclear after three correction attempts."
            self.project_summary = (
                "The target Repository could not be determined. "
                "GitHub was not accessed, and no Issue or Release analysis was performed."
            )
            print(f"Diagnostic: {diagnostic}")
            print(self.project_summary)
            return {"project_summary": self.project_summary}

        try:
            self.selected_repository = parse_github_repository_input(self.project_input)
            self.project_overview = get_github_project_overview(
                self.selected_repository["owner"], self.selected_repository["repository"]
            )
        except (ValueError, AgentExecutionError):
            raise

        self.repository_found = bool(self.project_overview.get("found"))
        if not self.repository_found:
            self.project_summary = (
                f"The explicitly identified Repository "
                f"{self.selected_repository['owner']}/{self.selected_repository['repository']} "
                "was not found on GitHub. This is a Repository-not-found result; it is not "
                "being interpreted as a network, authentication, rate-limit, or service failure."
            )
            print(self.project_summary)
            return {"project_summary": self.project_summary}

        self.project_summary = create_project_summary(self.llm(), self.project_overview)
        print("\nProject summary:\n" + self.project_summary)

        self.issue_analysis_choice = interpret_yes_no(
            self.llm(), input("Would you like an analysis of recently updated open Issues? ")
        )
        if self.issue_analysis_choice == "yes":
            self.issue_information = get_github_issue_information(
                self.selected_repository["owner"], self.selected_repository["repository"]
            )
            self.issue_analysis_result = analyze_issues(self.llm(), self.issue_information)

        self.release_analysis_choice = interpret_yes_no(
            self.llm(), input("Would you like guidance about the latest official Release? ")
        )
        if self.release_analysis_choice == "yes":
            self.release_request = parse_release_request(
                input(
                    "Enter 'overview' or "
                    "'asset_match;operating_system;architecture;package_preference': "
                )
            )
            self.release_information = get_github_release(
                self.selected_repository["owner"], self.selected_repository["repository"]
            )
            if self.release_request["analysis_mode"] == "asset_match":
                self.asset_selection = select_asset(
                    self.llm(), self.release_information, self.release_request
                )
            self.release_advice = create_release_advice(
                self.llm(),
                self.release_information,
                self.release_request,
                self.asset_selection,
            )

        final_result: dict[str, object] = {"project_summary": self.project_summary}
        if self.issue_analysis_choice == "yes" and self.issue_analysis_result is not None:
            final_result["issue_analysis_result"] = self.issue_analysis_result
        if self.release_analysis_choice == "yes" and self.release_advice is not None:
            final_result["release_advice"] = self.release_advice

        print("\nFinal result:")
        print(json.dumps(final_result, ensure_ascii=False, indent=2))
        return final_result


def main() -> dict[str, object]:
    """Initialize and execute GitHubProjectAssistant through terminal interaction."""
    load_dotenv()
    assistant = GitHubProjectAssistant()
    try:
        return assistant.run()
    except (AgentExecutionError, ValueError) as exc:
        message = f"Execution failed: {exc}"
        print(message, file=sys.stderr)
        return {"error": str(exc)}


if __name__ == "__main__":
    main()
