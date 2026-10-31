from __future__ import annotations

import json
import logging
import os
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from openai import OpenAI


LOGGER = logging.getLogger("github_project_assistant")

STATIC_CONTEXT = """
You are GitHubProjectAssistant, a cautious, evidence-based assistant for public
GitHub project information, Issue risks, and Release compatibility.

Audience: developers and software users who can identify a repository by a
complete GitHub URL or owner/repository name. Write clear English and separate
repository facts, limited Issue-sample analysis, Release summaries, and Asset
compatibility guidance.

Non-negotiable constraints:
- Use only the explicitly identified repository. Never guess a repository.
- GitHub access is read-only. Never propose or claim a GitHub modification.
- Never download, create, overwrite, move, install, extract, or execute files.
- Do not judge project quality from Stars or open Issue count alone.
- Do not turn one user report into a general project problem.
- State the actual number and scope of Issues analyzed.
- Treat source zip/tar archives as source archives, not installable software by
  default.
- Release work concerns only the latest official public Release.
- Do not invent facts, confirmations, compatibility, checksums, or URLs.
""".strip()


class LLMRuntime:
    """Lazy OpenAI Responses API client used by semantic CNL-P commands."""

    def __init__(self) -> None:
        self._client: OpenAI | None = None
        self._model = ""

    def _initialize(self) -> None:
        if self._client is not None:
            return

        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        base_url = os.getenv("BASE_URL", "").strip()
        model = (
            os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip()
            or os.getenv("OPENAI_MODEL", "").strip()
        )
        missing = []
        if not api_key:
            missing.append("OPENAI_API_KEY")
        if not base_url:
            missing.append("BASE_URL")
        if not model:
            missing.append("CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL")
        if missing:
            raise RuntimeError(
                "Missing runtime model configuration: " + ", ".join(missing)
            )

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def request_json(
        self,
        *,
        task: str,
        payload: object,
        schema_name: str,
        schema: dict[str, object],
        max_output_tokens: int = 5000,
    ) -> dict[str, Any]:
        self._initialize()
        assert self._client is not None

        response = self._client.responses.create(
            model=self._model,
            reasoning={"effort": "high"},
            instructions=STATIC_CONTEXT + "\n\n" + task,
            input=json.dumps(payload, ensure_ascii=False),
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
            max_output_tokens=max_output_tokens,
        )
        output_text = response.output_text.strip()
        if not output_text:
            raise RuntimeError("The language model returned an empty response.")
        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("The language model returned invalid JSON.") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("The language model returned a non-object result.")
        return parsed


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
    except ValueError:
        return "unclear"
    return "repository_url" if "://" in project_input.strip() else "repository_name"


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "cnlp-github-project-assistant",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def get_github_project_overview(owner: str, repository: str) -> dict[str, object]:
    """Read repository metadata and README from the GitHub REST API."""
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

    def not_found_result() -> dict[str, object]:
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

    headers = _github_headers()
    repository_api_url = (
        "https://api.github.com/repos/"
        f"{quote(owner_value, safe='')}/{quote(repository_value, safe='')}"
    )
    try:
        request = Request(repository_api_url, headers=headers, method="GET")
        with urlopen(request, timeout=30) as response:
            metadata = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return not_found_result()
        raise RuntimeError(
            f"GitHub repository lookup returned HTTP {exc.code}."
        ) from exc
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "GitHub repository metadata could not be read: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(metadata, dict):
        raise RuntimeError("GitHub returned malformed repository metadata.")

    readme = ""
    readme_headers = dict(headers)
    readme_headers["Accept"] = "application/vnd.github.raw+json"
    try:
        request = Request(
            repository_api_url + "/readme", headers=readme_headers, method="GET"
        )
        with urlopen(request, timeout=30) as response:
            readme = response.read(50001).decode("utf-8", errors="replace")
            if len(readme) > 50000:
                readme = readme[:50000]
    except HTTPError as exc:
        if exc.code != 404:
            raise RuntimeError(
                f"GitHub README lookup returned HTTP {exc.code}."
            ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
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
    """Read recently updated open Issues for the Issue analysis."""
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
    try:
        request = Request(url, headers=_github_headers(), method="GET")
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"GitHub Issue lookup returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "GitHub Issues could not be read: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(payload, list):
        raise RuntimeError("GitHub returned malformed Issue data.")

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
    """Read the latest official public Release and its Asset metadata."""
    owner_value = str(owner).strip()
    repository_value = str(repository).strip()
    if not owner_value or not repository_value:
        raise ValueError("GitHub owner and repository are required.")

    base_url = (
        "https://api.github.com/repos/"
        f"{quote(owner_value, safe='')}/{quote(repository_value, safe='')}"
        "/releases"
    )
    try:
        request = Request(base_url + "/latest", headers=_github_headers(), method="GET")
        with urlopen(request, timeout=30) as response:
            selected = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"GitHub Release lookup returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "GitHub Release data could not be read: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    if not isinstance(selected, dict):
        raise RuntimeError("GitHub returned malformed Release data.")

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


TEXT_RESULT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
    "additionalProperties": False,
}

ISSUE_ANALYSIS_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "analyzed_issue_count": {"type": "integer", "minimum": 0},
        "common_problems": {"type": "array", "items": {"type": "string"}},
        "confirmed_problems": {"type": "array", "items": {"type": "string"}},
        "unresolved_problems": {"type": "array", "items": {"type": "string"}},
        "representative_issues": {"type": "array", "items": {"type": "string"}},
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "analyzed_issue_count",
        "common_problems",
        "confirmed_problems",
        "unresolved_problems",
        "representative_issues",
        "limitations",
    ],
    "additionalProperties": False,
}

RELEASE_ASSET_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "download_url": {"type": "string"},
        "size": {"type": "integer", "minimum": 0},
        "digest": {"type": "string"},
    },
    "required": ["name", "download_url", "size", "digest"],
    "additionalProperties": False,
}

ASSET_SELECTION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "asset": {"anyOf": [RELEASE_ASSET_SCHEMA, {"type": "null"}]},
        "reason": {"type": "string"},
    },
    "required": ["found", "asset", "reason"],
    "additionalProperties": False,
}

RELEASE_ADVICE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["overview", "recommended", "no_match"]},
        "version": {"type": "string"},
        "asset": {"anyOf": [RELEASE_ASSET_SCHEMA, {"type": "null"}]},
        "summary": {"type": "string"},
        "acquisition_url": {"type": "string"},
        "integrity_guidance": {"type": "string"},
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "status",
        "version",
        "asset",
        "summary",
        "acquisition_url",
        "integrity_guidance",
        "limitations",
    ],
    "additionalProperties": False,
}


def normalize_yes_no(llm: LLMRuntime, answer: str, question_context: str) -> str:
    result = llm.request_json(
        task=(
            "Interpret the user's answer to a yes/no terminal question. Return yes only "
            "when the user affirmatively requests the offered analysis; return no when "
            "they decline. Do not infer consent from ambiguity."
        ),
        payload={"question": question_context, "answer": answer},
        schema_name="yes_no_choice",
        schema={
            "type": "object",
            "properties": {"choice": {"type": "string", "enum": ["yes", "no"]}},
            "required": ["choice"],
            "additionalProperties": False,
        },
        max_output_tokens=200,
    )
    return str(result["choice"])


def parse_release_request(value: str) -> dict[str, str]:
    stripped = value.strip()
    if stripped == "overview":
        return {"analysis_mode": "overview"}
    parts = [part.strip() for part in stripped.split(";")]
    if len(parts) != 4 or parts[0] != "asset_match":
        raise ValueError(
            "Release request must be 'overview' or "
            "'asset_match;operating_system;architecture;package_preference'."
        )
    operating_system, architecture, package_preference = parts[1:]
    if operating_system not in {"windows", "macos", "linux", "other"}:
        raise ValueError("Invalid operating_system in ReleaseRequest.")
    if architecture not in {"x64", "arm64", "unknown"}:
        raise ValueError("Invalid architecture in ReleaseRequest.")
    if package_preference not in {"installer", "portable", "archive", "any"}:
        raise ValueError("Invalid package_preference in ReleaseRequest.")
    return {
        "analysis_mode": "asset_match",
        "operating_system": operating_system,
        "architecture": architecture,
        "package_preference": package_preference,
    }


def create_project_summary(llm: LLMRuntime, overview: dict[str, object]) -> str:
    result = llm.request_json(
        task=(
            "Using only the supplied repository metadata and README, write a concise but "
            "substantive project overview. Explain the project name, purpose, core "
            "capabilities, typical use cases, intended users, primary technology, execution "
            "or installation entry points, license, maintenance status, and important README "
            "limitations. Distinguish absent information from known facts. Do not merely copy "
            "the README and do not judge quality from Stars or open Issue count alone."
        ),
        payload=overview,
        schema_name="project_summary",
        schema=TEXT_RESULT_SCHEMA,
        max_output_tokens=3500,
    )
    return str(result["text"])


def _issue_batch_analysis(
    llm: LLMRuntime, issues: list[str], batch_number: int, batch_count: int
) -> dict[str, Any]:
    result = llm.request_json(
        task=(
            "Analyze this batch of recently updated open Issues as evidence notes for a "
            "later full-sample synthesis. Distinguish repeated concerns, isolated reports, "
            "maintainer-confirmed problems, and unresolved reports. Confirmation requires "
            "explicit evidence in the supplied Issue text; labels alone may be weak evidence. "
            "Use Issue numbers and URLs in representative_issues. State batch limitations."
        ),
        payload={
            "batch_number": batch_number,
            "batch_count": batch_count,
            "issue_count": len(issues),
            "issues": issues,
        },
        schema_name="issue_batch_analysis",
        schema=ISSUE_ANALYSIS_SCHEMA,
        max_output_tokens=4000,
    )
    result["analyzed_issue_count"] = len(issues)
    return result


def analyze_issue_information(
    llm: LLMRuntime, issue_information: dict[str, object]
) -> dict[str, Any]:
    raw_issues = issue_information.get("issues", [])
    if not isinstance(raw_issues, list) or not all(isinstance(item, str) for item in raw_issues):
        raise RuntimeError("Issue information has an invalid issues list.")
    issues = list(raw_issues)
    expected_count = int(issue_information.get("analyzed_issue_count", 0))
    if expected_count != len(issues):
        raise RuntimeError("Issue information count does not match its Issue list.")

    batch_size = 12
    batches = [issues[index : index + batch_size] for index in range(0, len(issues), batch_size)]
    if not batches:
        batches = [[]]
    partials = [
        _issue_batch_analysis(llm, batch, index + 1, len(batches))
        for index, batch in enumerate(batches)
    ]
    result = llm.request_json(
        task=(
            "Synthesize the batch analyses into one evidence-based analysis of the entire "
            "recently updated open-Issue sample. Repetition must be supported across supplied "
            "evidence; one report remains isolated. Separate repeated concerns, explicitly "
            "maintainer-confirmed problems, and unresolved reports. Select only a small set "
            "of representative Issues. The analyzed_issue_count must equal the supplied exact "
            "count. Limitations must say this is a recent open-Issue sample and cannot establish "
            "overall project quality, prevalence among all users, or the state of closed Issues."
        ),
        payload={"exact_analyzed_issue_count": expected_count, "batch_analyses": partials},
        schema_name="issue_analysis_result",
        schema=ISSUE_ANALYSIS_SCHEMA,
        max_output_tokens=5000,
    )
    result["analyzed_issue_count"] = expected_count
    return result


def select_release_asset(
    llm: LLMRuntime,
    release_request: dict[str, str],
    release_information: dict[str, object],
) -> dict[str, Any]:
    result = llm.request_json(
        task=(
            "Select the single most suitable maintainer-uploaded Release Asset for the exact "
            "operating system, architecture, and package preference. Infer compatibility only "
            "from Asset names and supplied metadata, explain uncertainty, and return no match "
            "when compatibility is not adequately supported. Never select source_zip_url or "
            "source_tar_url, and never treat generated source archives as installable software "
            "by default. If found, copy the selected Asset fields exactly."
        ),
        payload={"release_request": release_request, "release_information": release_information},
        schema_name="asset_selection",
        schema=ASSET_SELECTION_SCHEMA,
        max_output_tokens=1800,
    )
    found = bool(result.get("found"))
    selected = result.get("asset")
    assets = release_information.get("assets", [])
    if not isinstance(assets, list):
        raise RuntimeError("Release information has an invalid Asset list.")
    if found:
        if not isinstance(selected, dict):
            raise RuntimeError("Asset selection marked found without an Asset.")
        canonical = next(
            (
                asset
                for asset in assets
                if isinstance(asset, dict)
                and asset.get("name") == selected.get("name")
                and asset.get("download_url") == selected.get("download_url")
            ),
            None,
        )
        if canonical is None:
            raise RuntimeError("The language model selected an Asset not present in the Release.")
        result["asset"] = canonical
    else:
        result.pop("asset", None)
    return result


def create_release_overview(
    llm: LLMRuntime,
    selected_repository: dict[str, str],
    release_information: dict[str, object],
) -> dict[str, Any]:
    result = llm.request_json(
        task=(
            "Create an overview of the latest official Release. Include version, Release name, "
            "publication time, key Release Notes, and maintainer-uploaded Asset count. Set status "
            "to overview. Do not recommend an Asset. Explicitly state that no file operation was "
            "performed. Use the supplied latest_release_page as acquisition_url."
        ),
        payload={
            "release_information": release_information,
            "latest_release_page": selected_repository["repository_url"] + "/releases/latest",
        },
        schema_name="release_overview",
        schema=RELEASE_ADVICE_SCHEMA,
        max_output_tokens=3500,
    )
    result["status"] = "overview"
    result["version"] = str(release_information.get("version", ""))
    result.pop("asset", None)
    return result


def create_asset_release_advice(
    llm: LLMRuntime,
    selected_repository: dict[str, str],
    release_information: dict[str, object],
    asset_selection: dict[str, Any],
) -> dict[str, Any]:
    found = bool(asset_selection.get("found"))
    result = llm.request_json(
        task=(
            "Create no-download Release guidance from the exact selection. If a matching Asset "
            "was found, set status recommended and include its name, byte size, URL, digest, "
            "compatibility rationale, and user-side integrity verification guidance. If no Asset "
            "matched, set status no_match and explain the evidence gap without recommending a "
            "source archive as installable software. Explicitly state that no file was downloaded, "
            "created, installed, extracted, or executed. Do not invent a digest or signature."
        ),
        payload={
            "release_information": release_information,
            "asset_selection": asset_selection,
            "latest_release_page": selected_repository["repository_url"] + "/releases/latest",
        },
        schema_name="release_asset_advice",
        schema=RELEASE_ADVICE_SCHEMA,
        max_output_tokens=3500,
    )
    result["status"] = "recommended" if found else "no_match"
    result["version"] = str(release_information.get("version", ""))
    if found:
        result["asset"] = asset_selection["asset"]
        result["acquisition_url"] = str(asset_selection["asset"]["download_url"])
    else:
        result.pop("asset", None)
        result["acquisition_url"] = selected_repository["repository_url"] + "/releases/latest"
    return result


def display_issue_analysis(result: dict[str, Any]) -> None:
    print("\nRecent open Issue analysis")
    print(f"Analyzed Issues: {result['analyzed_issue_count']}")
    for label, key in (
        ("Repeated concerns", "common_problems"),
        ("Maintainer-confirmed problems", "confirmed_problems"),
        ("Unresolved reports", "unresolved_problems"),
        ("Representative Issues", "representative_issues"),
        ("Limitations", "limitations"),
    ):
        print(f"\n{label}:")
        values = result.get(key, [])
        if values:
            for value in values:
                print(f"- {value}")
        else:
            print("- None established from the analyzed sample.")


def display_release_advice(result: dict[str, Any]) -> None:
    print("\nLatest Release guidance")
    print(f"Status: {result['status']}")
    print(f"Version: {result['version']}")
    print(result["summary"])
    asset = result.get("asset")
    if isinstance(asset, dict):
        print(f"Asset: {asset['name']}")
        print(f"Size: {asset['size']} bytes")
        print(f"Digest: {asset['digest'] or 'Not provided by GitHub'}")
    print(f"Acquisition URL: {result['acquisition_url']}")
    print(f"Integrity guidance: {result['integrity_guidance']}")
    if result.get("limitations"):
        print("Limitations:")
        for limitation in result["limitations"]:
            print(f"- {limitation}")


class IssueAnalyzer:
    def __init__(self, llm: LLMRuntime) -> None:
        self.llm = llm

    def run(self, selected_repository: dict[str, str]) -> dict[str, Any]:
        issue_information = get_github_issue_information(
            selected_repository["owner"], selected_repository["repository"]
        )
        return analyze_issue_information(self.llm, issue_information)


class ReleaseAdvisor:
    def __init__(self, llm: LLMRuntime) -> None:
        self.llm = llm

    def run(
        self,
        selected_repository: dict[str, str],
        release_request: dict[str, str],
    ) -> dict[str, Any]:
        release_information = get_github_release(
            selected_repository["owner"], selected_repository["repository"]
        )
        if release_request["analysis_mode"] == "overview":
            return create_release_overview(
                self.llm, selected_repository, release_information
            )

        asset_selection = select_release_asset(
            self.llm, release_request, release_information
        )
        return create_asset_release_advice(
            self.llm, selected_repository, release_information, asset_selection
        )


class ProjectNavigator:
    def __init__(self) -> None:
        self.llm = LLMRuntime()
        self.issue_analyzer = IssueAnalyzer(self.llm)
        self.release_advisor = ReleaseAdvisor(self.llm)

    def run(self) -> dict[str, Any]:
        project_summary = (
            "No project summary is available because the target Repository was not resolved."
        )
        issue_analysis_result: dict[str, Any] | None = None
        release_advice: dict[str, Any] | None = None

        print(
            "This assistant requires a complete GitHub Repository URL or an explicit "
            "owner/repository identifier. It can summarize public project information, "
            "analyze recently updated open Issues, and provide latest Release guidance "
            "without downloading files."
        )
        project_input = input("Repository URL or owner/repository: ")
        input_kind = classify_project_input(project_input)
        repository_input_retry_count = 0

        while input_kind == "unclear" and repository_input_retry_count < 3:
            project_input = input(
                "The current input does not uniquely identify one GitHub Repository. "
                "Enter a complete GitHub Repository URL or owner/repository: "
            )
            repository_input_retry_count += 1
            input_kind = classify_project_input(project_input)

        repository_input_limit_exceeded = (
            input_kind == "unclear" and repository_input_retry_count >= 3
        )
        if repository_input_limit_exceeded:
            LOGGER.warning(
                "The Repository input remains unclear after three correction attempts"
            )
            project_summary = (
                "The target Repository could not be determined after three correction "
                "attempts. GitHub was not accessed, and no Issue or Release analysis was "
                "performed."
            )
            print(project_summary)
            return {"project_summary": project_summary}

        selected_repository = parse_github_repository_input(project_input)
        project_overview = get_github_project_overview(
            selected_repository["owner"], selected_repository["repository"]
        )
        repository_found = bool(project_overview["found"])

        if not repository_found:
            project_summary = (
                f"The explicitly identified Repository "
                f"{selected_repository['owner']}/{selected_repository['repository']} was not "
                "found through the public GitHub repository endpoint. This result is only a "
                "Repository-not-found state; network, authentication, rate-limit, service, "
                "and malformed-response failures are reported separately as execution errors."
            )
            print(project_summary)
            return {"project_summary": project_summary}

        project_summary = create_project_summary(self.llm, project_overview)
        print("\nProject overview")
        print(project_summary)

        issue_answer = input(
            "\nDo you want an analysis of recently updated open Issues? "
        )
        issue_analysis_choice = normalize_yes_no(
            self.llm,
            issue_answer,
            "Whether to analyze recently updated open Issues",
        )
        if issue_analysis_choice == "yes":
            issue_analysis_result = self.issue_analyzer.run(selected_repository)

        release_answer = input(
            "\nDo you want guidance about the latest official Release? "
        )
        release_analysis_choice = normalize_yes_no(
            self.llm,
            release_answer,
            "Whether to provide guidance about the latest official Release",
        )
        if release_analysis_choice == "yes":
            request_value = input(
                "Enter 'overview' or exactly "
                "'asset_match;operating_system;architecture;package_preference'. "
                "OS: windows|macos|linux|other; architecture: x64|arm64|unknown; "
                "preference: installer|portable|archive|any: "
            )
            release_request = parse_release_request(request_value)
            release_advice = self.release_advisor.run(
                selected_repository, release_request
            )

        print("\nFinal result")
        print("\nProject overview")
        print(project_summary)
        if issue_analysis_choice == "yes" and issue_analysis_result is not None:
            display_issue_analysis(issue_analysis_result)
        if release_analysis_choice == "yes" and release_advice is not None:
            display_release_advice(release_advice)

        result: dict[str, Any] = {"project_summary": project_summary}
        if issue_analysis_result is not None:
            result["issue_analysis_result"] = issue_analysis_result
        if release_advice is not None:
            result["release_advice"] = release_advice
        return result


def main() -> dict[str, Any]:
    """Initialize the Agent, execute the entry Worker, and return its outputs."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    agent = ProjectNavigator()
    try:
        return agent.run()
    except (EOFError, KeyboardInterrupt):
        print("\nExecution cancelled before the Worker completed.", file=sys.stderr)
        raise
    except Exception as exc:
        print(f"Execution failed: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
