from __future__ import annotations

import json
import os
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen


DEFAULT_PROJECT_SUMMARY = (
    "No project summary is available because the target Repository was not resolved."
)
GITHUB_API_VERSION = "2022-11-28"


def load_dotenv() -> None:
    """Load simple KEY=VALUE entries from the local .env without overwriting env vars."""
    env_path = os.path.join(os.getcwd(), ".env")
    try:
        with open(env_path, "r", encoding="utf-8") as env_file:
            lines = env_file.readlines()
    except FileNotFoundError:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
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
    """Classify only explicit URL or owner/repository inputs; never infer a project."""
    try:
        parse_github_repository_input(project_input)
    except ValueError:
        return "unclear"
    return "repository_url" if "://" in project_input.strip() else "repository_name"


def github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "cnlp-github-project-assistant",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_json_request(url: str, *, accept: str | None = None) -> Any:
    headers = github_headers()
    if accept:
        headers["Accept"] = accept
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError:
        raise
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"GitHub data could not be read: {type(exc).__name__}: {exc}"
        ) from exc


def get_github_project_overview(owner: str, repository: str) -> dict[str, object]:
    """Read repository metadata and README. A public 404 is found=false."""
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

    def not_found() -> dict[str, object]:
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

    base_url = (
        "https://api.github.com/repos/"
        f"{quote(owner_value, safe='')}/{quote(repository_value, safe='')}"
    )
    try:
        metadata = github_json_request(base_url)
    except HTTPError as exc:
        if exc.code == 404:
            return not_found()
        raise RuntimeError(f"GitHub repository lookup returned HTTP {exc.code}.") from exc
    if not isinstance(metadata, dict):
        raise RuntimeError("GitHub returned malformed repository metadata.")

    readme = ""
    try:
        request = Request(
            base_url + "/readme",
            headers={**github_headers(), "Accept": "application/vnd.github.raw+json"},
            method="GET",
        )
        with urlopen(request, timeout=30) as response:
            readme = response.read(50001).decode("utf-8", errors="replace")
            if len(readme) > 50000:
                readme = readme[:50000]
    except HTTPError as exc:
        if exc.code != 404:
            raise RuntimeError(f"GitHub README lookup returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            f"GitHub README could not be read: {type(exc).__name__}: {exc}"
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
        "forks": int(metadata.get("forks") or 0),
        "open_issues": int(metadata.get("open_issues_count") or 0),
        "archived": bool(metadata.get("archived", False)),
        "updated_at": str(metadata.get("updated_at") or ""),
    }


def get_github_issue_information(owner: str, repository: str) -> dict[str, object]:
    """Read the first page of recently updated open Issues, excluding pull requests."""
    if not str(owner).strip() or not str(repository).strip():
        raise ValueError("GitHub owner and repository are required.")
    url = (
        "https://api.github.com/repos/"
        f"{quote(str(owner).strip(), safe='')}/{quote(str(repository).strip(), safe='')}"
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
        payload = github_json_request(url)
    except HTTPError as exc:
        raise RuntimeError(f"GitHub Issue lookup returned HTTP {exc.code}.") from exc
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
    """Read only the latest official public Release and maintainer-uploaded asset metadata."""
    if not str(owner).strip() or not str(repository).strip():
        raise ValueError("GitHub owner and repository are required.")
    url = (
        "https://api.github.com/repos/"
        f"{quote(str(owner).strip(), safe='')}/{quote(str(repository).strip(), safe='')}"
        "/releases/latest"
    )
    try:
        selected = github_json_request(url)
    except HTTPError as exc:
        raise RuntimeError(f"GitHub Release lookup returned HTTP {exc.code}.") from exc
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


class RuntimeLLM:
    def __init__(self) -> None:
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured in .env or the current environment."
            )
        model = (
            os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip()
            or os.getenv("OPENAI_MODEL", "").strip()
        )
        if not model:
            raise RuntimeError(
                "No model is configured: set CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL."
            )

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The official OpenAI Python Client is required; install the openai package."
            ) from exc

        client_args: dict[str, str] = {"api_key": api_key}
        base_url = os.getenv("BASE_URL", "").strip()
        if base_url:
            client_args["base_url"] = base_url
        self.client = OpenAI(**client_args)
        self.model = model

    def json(self, instruction: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.responses.create(
            model=self.model,
            reasoning={"effort": "high"},
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are an evidence-based GitHub project assistant. "
                        "Return only a valid JSON object matching the requested keys. "
                        "Use only supplied evidence and do not invent facts."
                    ),
                },
                {
                    "role": "user",
                    "content": instruction + "\n\nEVIDENCE:\n" + json.dumps(
                        payload, ensure_ascii=False
                    ),
                },
            ],
            text={"format": {"type": "json_object"}},
        )
        raw = getattr(response, "output_text", "")
        if not raw:
            raise RuntimeError("The language model returned an empty response.")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("The language model returned invalid JSON.") from exc
        if not isinstance(value, dict):
            raise RuntimeError("The language model returned a JSON value that is not an object.")
        return value


def require_text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise RuntimeError(f"The language model omitted text field {field}.")
    return value.strip()


def require_string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError(f"The language model returned invalid list field {field}.")
    return [item.strip() for item in value if item.strip()]


def interpret_yes_no(llm: RuntimeLLM, answer: str) -> str:
    result = llm.json(
        "Classify the user's answer as exactly yes or no. Return {\"choice\": \"yes\"} or {\"choice\": \"no\"}.",
        {"user_answer": answer},
    )
    choice = result.get("choice")
    if choice not in {"yes", "no"}:
        raise RuntimeError("The language model could not classify the answer as yes or no.")
    return choice


def create_project_summary(llm: RuntimeLLM, overview: dict[str, object]) -> str:
    result = llm.json(
        """
Create a clear English PROJECT_OVERVIEW as one plain-text field named project_summary.
Cover the project name, purpose, core capabilities, typical use cases, intended users,
primary technology, execution or installation entry points, license, maintenance status,
and important README limitations. Distinguish repository facts from cautious inferences.
Do not judge quality from stars or open issue count alone. Do not merely copy the README.
""",
        {"repository_overview": overview},
    )
    return require_text(result.get("project_summary"), "project_summary")


def analyze_issues(llm: RuntimeLLM, issue_information: dict[str, object]) -> dict[str, object]:
    result = llm.json(
        """
Analyze the supplied limited sample of recently updated open GitHub Issues. Return exactly
these keys: common_problems, confirmed_problems, unresolved_problems, representative_issues,
limitations. Each must be a list of strings. Distinguish repeated concerns, isolated reports,
maintainer-confirmed problems, and unresolved reports. Select only a small representative set.
Never describe one user report as a general project problem. State in limitations what this
sample cannot establish, including that pull requests were excluded and the scope is limited.
Do not include a fabricated issue count; the caller supplies that count separately.
""",
        issue_information,
    )
    return {
        "analyzed_issue_count": int(issue_information.get("analyzed_issue_count") or 0),
        "common_problems": require_string_list(result.get("common_problems"), "common_problems"),
        "confirmed_problems": require_string_list(
            result.get("confirmed_problems"), "confirmed_problems"
        ),
        "unresolved_problems": require_string_list(
            result.get("unresolved_problems"), "unresolved_problems"
        ),
        "representative_issues": require_string_list(
            result.get("representative_issues"), "representative_issues"
        ),
        "limitations": require_string_list(result.get("limitations"), "limitations"),
    }


def parse_release_request(answer: str) -> dict[str, str]:
    value = answer.strip()
    if value == "overview":
        return {"analysis_mode": "overview"}
    parts = value.split(";")
    if len(parts) != 4 or parts[0] != "asset_match":
        raise ValueError(
            "Release request must be overview or "
            "asset_match;operating_system;architecture;package_preference."
        )
    operating_system, architecture, package_preference = parts[1:]
    if operating_system not in {"windows", "macos", "linux", "other"}:
        raise ValueError("Operating system must be windows, macos, linux, or other.")
    if architecture not in {"x64", "arm64", "unknown"}:
        raise ValueError("Architecture must be x64, arm64, or unknown.")
    if package_preference not in {"installer", "portable", "archive", "any"}:
        raise ValueError("Package preference must be installer, portable, archive, or any.")
    return {
        "analysis_mode": "asset_match",
        "operating_system": operating_system,
        "architecture": architecture,
        "package_preference": package_preference,
    }


def is_source_archive(name: str) -> bool:
    lowered = name.strip().lower()
    return lowered in {"source code.zip", "source code.tar.gz", "source code.tar"}


def select_release_asset(
    llm: RuntimeLLM,
    release_information: dict[str, object],
    release_request: dict[str, str],
) -> tuple[dict[str, object] | None, str]:
    assets = [
        asset
        for asset in release_information.get("assets", [])
        if isinstance(asset, dict)
        and asset.get("name")
        and not is_source_archive(str(asset.get("name")))
    ]
    if not assets:
        return None, "The latest Release has no maintainer-uploaded asset eligible for matching."

    result = llm.json(
        """
Select the most suitable maintainer-uploaded Release Asset for the requested platform.
Automatically generated Source code zip/tar archives have already been excluded and must
never be selected. Return exactly selected_name (a supplied asset name or null) and reason.
Select null when the supplied metadata does not support a defensible match; do not guess.
""",
        {"release_request": release_request, "eligible_assets": assets},
    )
    selected_name = result.get("selected_name")
    reason = require_text(result.get("reason"), "reason")
    if selected_name is None:
        return None, reason
    if not isinstance(selected_name, str):
        raise RuntimeError("The language model returned an invalid selected asset name.")
    selected = next((asset for asset in assets if asset.get("name") == selected_name), None)
    if selected is None:
        raise RuntimeError("The language model selected an asset not present in the Release.")
    return selected, reason


def create_release_overview(
    llm: RuntimeLLM, release_information: dict[str, object], repository_url: str
) -> dict[str, object]:
    result = llm.json(
        """
Create a concise English overview of the latest official GitHub Release. Return summary and
integrity_guidance as text fields. Include its version, name, publication time, key Release
Notes, and asset count. State that no file operation was performed. Use only supplied evidence.
""",
        {"release_information": release_information},
    )
    return {
        "status": "overview",
        "version": str(release_information.get("version") or ""),
        "summary": require_text(result.get("summary"), "summary"),
        "acquisition_url": repository_url.rstrip("/") + "/releases/latest",
        "integrity_guidance": require_text(
            result.get("integrity_guidance"), "integrity_guidance"
        ),
        "limitations": [
            "No Release file was downloaded, created, installed, extracted, or executed.",
            "The overview covers only the latest official public Release.",
        ],
    }


def create_asset_advice(
    llm: RuntimeLLM,
    release_information: dict[str, object],
    release_request: dict[str, str],
    selected: dict[str, object] | None,
    selection_reason: str,
    repository_url: str,
) -> dict[str, object]:
    payload = {
        "release_information": release_information,
        "release_request": release_request,
        "selected_asset": selected,
        "selection_reason": selection_reason,
    }
    result = llm.json(
        """
Write Release asset compatibility guidance. Return summary, acquisition_url, and
integrity_guidance as text fields. Explain the compatibility rationale and user-side
verification guidance. Mention that no file was downloaded, created, installed, extracted,
or executed. Do not claim an asset is compatible beyond the supplied name and request.
""",
        payload,
    )
    advice: dict[str, object] = {
        "status": "recommended" if selected else "no_match",
        "version": str(release_information.get("version") or ""),
        "summary": require_text(result.get("summary"), "summary"),
        "acquisition_url": repository_url.rstrip("/") + "/releases/latest",
        "integrity_guidance": require_text(
            result.get("integrity_guidance"), "integrity_guidance"
        ),
        "limitations": [
            "Only the latest official public Release was analyzed.",
            "Asset compatibility is inferred from published metadata and the requested preferences.",
            "No Release file was downloaded, created, installed, extracted, or executed.",
        ],
    }
    if selected:
        advice["asset"] = selected
    return advice


def print_result(label: str, value: Any) -> None:
    print(f"\n{label}")
    if isinstance(value, str):
        print(value)
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2))


def project_navigator() -> dict[str, object]:
    project_summary = DEFAULT_PROJECT_SUMMARY
    issue_analysis_result: dict[str, object] | None = None
    release_advice: dict[str, object] | None = None

    print(
        "GitHubProjectAssistant requires a complete GitHub Repository URL or an explicit "
        "owner/repository identifier. It can summarize public project information, analyze "
        "recent open Issues, and provide Release guidance without downloading files."
    )
    project_input = input("Enter a GitHub Repository URL or owner/repository: ")
    input_kind = classify_project_input(project_input)
    retry_count = 0
    while input_kind == "unclear" and retry_count < 3:
        print(
            "The current input does not uniquely identify a Repository. Please provide a "
            "complete GitHub Repository URL or an explicit owner/repository identifier."
        )
        project_input = input("Enter a GitHub Repository URL or owner/repository: ")
        retry_count += 1
        input_kind = classify_project_input(project_input)

    limit_exceeded = input_kind == "unclear" and retry_count >= 3
    if limit_exceeded:
        project_summary = "The Repository input remains unclear after three correction attempts."
        print_result("Project summary", project_summary)
        print("GitHub was not accessed; no Issue or Release analysis was performed.")
        return {"project_summary": project_summary}

    selected_repository = parse_github_repository_input(project_input)
    project_overview = get_github_project_overview(
        selected_repository["owner"], selected_repository["repository"]
    )
    repository_found = bool(project_overview.get("found"))
    if not repository_found:
        project_summary = (
            f"The explicitly identified Repository "
            f"{selected_repository['owner']}/{selected_repository['repository']} "
            "was not found on GitHub. This is a Repository-not-found result, not a "
            "network, authentication, rate-limit, or service diagnosis."
        )
        print_result("Project summary", project_summary)
        return {"project_summary": project_summary}

    llm = RuntimeLLM()
    project_summary = create_project_summary(llm, project_overview)
    print_result("Project summary", project_summary)

    issue_choice = interpret_yes_no(
        llm, input("Do you want an analysis of recently updated open Issues? (yes/no): ")
    )
    if issue_choice == "yes":
        issue_information = get_github_issue_information(
            selected_repository["owner"], selected_repository["repository"]
        )
        issue_analysis_result = analyze_issues(llm, issue_information)

    release_choice = interpret_yes_no(
        llm, input("Do you want guidance about the latest official Release? (yes/no): ")
    )
    if release_choice == "yes":
        release_request = parse_release_request(
            input(
                "Enter overview or asset_match;operating_system;architecture;package_preference "
                "(use the exact permitted values): "
            )
        )
        release_information = get_github_release(
            selected_repository["owner"], selected_repository["repository"]
        )
        if release_request["analysis_mode"] == "overview":
            release_advice = create_release_overview(
                llm, release_information, selected_repository["repository_url"]
            )
        else:
            selected, reason = select_release_asset(llm, release_information, release_request)
            release_advice = create_asset_advice(
                llm,
                release_information,
                release_request,
                selected,
                reason,
                selected_repository["repository_url"],
            )

    result: dict[str, object] = {"project_summary": project_summary}
    if issue_choice == "yes" and issue_analysis_result is not None:
        result["issue_analysis_result"] = issue_analysis_result
    if release_choice == "yes" and release_advice is not None:
        result["release_advice"] = release_advice
    print_result("Final result", result)
    return result


def main() -> dict[str, object] | None:
    try:
        return project_navigator()
    except (EOFError, KeyboardInterrupt):
        print("\nExecution ended before the requested interaction was complete.", file=sys.stderr)
    except Exception as exc:
        print(f"Execution failed: {exc}", file=sys.stderr)
    return None


if __name__ == "__main__":
    main()
