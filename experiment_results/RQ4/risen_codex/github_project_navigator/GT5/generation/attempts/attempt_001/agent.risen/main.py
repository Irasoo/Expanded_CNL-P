from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

from openai import OpenAI


APP_NAME = "GitHubProjectAssistant"
GITHUB_API_VERSION = "2026-03-10"
DEFAULT_PROJECT_SUMMARY = (
    "No project summary is available because the target Repository was not resolved."
)


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries without overwriting process variables."""
    env_path = Path.cwd() / ".env"
    if not env_path.is_file():
        return
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"The .env file could not be read: {exc}") from exc
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
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


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "cnlp-github-project-assistant",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _read_json(url: str, *, headers: dict[str, str], error_prefix: str) -> Any:
    try:
        request = Request(url, headers=headers, method="GET")
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"{error_prefix} returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"{error_prefix} could not be read: {type(exc).__name__}: {exc}"
        ) from exc


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

    empty_result = {
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
        metadata = _read_json(
            repository_api_url,
            headers=headers,
            error_prefix="GitHub repository lookup",
        )
    except RuntimeError as exc:
        if "returned HTTP 404" in str(exc):
            return empty_result
        raise
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
        "forks": int(metadata.get("forks_count") or 0),
        "open_issues": int(metadata.get("open_issues_count") or 0),
        "archived": bool(metadata.get("archived", False)),
        "updated_at": str(metadata.get("updated_at") or ""),
    }


def get_github_issue_information(owner: str, repository: str) -> dict[str, object]:
    """Read recently updated open Issues, excluding Pull Requests."""
    owner_value = str(owner).strip()
    repository_value = str(repository).strip()
    if not owner_value or not repository_value:
        raise ValueError("GitHub owner and repository are required.")
    url = (
        "https://api.github.com/repos/"
        f"{quote(owner_value, safe='')}/{quote(repository_value, safe='')}/issues?"
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
    payload = _read_json(
        url, headers=_github_headers(), error_prefix="GitHub Issues lookup"
    )
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
    """Read the latest official public Release and maintainer-uploaded assets."""
    owner_value = str(owner).strip()
    repository_value = str(repository).strip()
    if not owner_value or not repository_value:
        raise ValueError("GitHub owner and repository are required.")
    url = (
        "https://api.github.com/repos/"
        f"{quote(owner_value, safe='')}/{quote(repository_value, safe='')}"
        "/releases/latest"
    )
    selected = _read_json(
        url, headers=_github_headers(), error_prefix="GitHub Release lookup"
    )
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
        "assets": list(assets),
        "source_zip_url": str(selected.get("zipball_url") or ""),
        "source_tar_url": str(selected.get("tarball_url") or ""),
    }


def _model_configuration() -> tuple[OpenAI, str]:
    _load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured in the environment or .env file."
        )
    model = (
        os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
    )
    if not model:
        raise RuntimeError(
            "No language model is configured: set CNLP_REFERENCE_LLM_MODEL "
            "or OPENAI_MODEL."
        )
    base_url = os.getenv("BASE_URL", "").strip()
    client_args: dict[str, str] = {"api_key": api_key}
    if base_url:
        client_args["base_url"] = base_url
    return OpenAI(**client_args), model


def _response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text_value = getattr(content, "text", None)
            if isinstance(text_value, str):
                parts.append(text_value)
    result = "\n".join(parts).strip()
    if not result:
        raise RuntimeError("The language model returned an empty response.")
    return result


def _call_model(instruction: str) -> str:
    client, model = _model_configuration()
    try:
        response = client.responses.create(
            model=model,
            reasoning={"effort": "high"},
            input=instruction,
        )
    except Exception as exc:
        raise RuntimeError(f"Language model execution failed: {exc}") from exc
    return _response_text(response)


def _call_model_json(instruction: str) -> dict[str, Any]:
    raw = _call_model(
        instruction
        + "\nReturn only one valid JSON object. Do not use Markdown fences."
    )
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate).strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"The language model returned invalid JSON: {raw}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("The language model returned a JSON value other than an object.")
    return value


def _as_text_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError(f"The language model returned an invalid {field} field.")
    return value


def _interpret_yes_no(answer: str, question_context: str) -> str:
    result = _call_model_json(
        "Interpret the user's single answer for this yes/no question. "
        "Understand natural language, but never infer missing intent. "
        "Return exactly {\"choice\":\"yes\"} or {\"choice\":\"no\"}; "
        "if ambiguous, choose no.\n"
        f"Question: {question_context}\nUser answer: {answer}"
    )
    choice = result.get("choice")
    if choice not in {"yes", "no"}:
        raise RuntimeError("The language model returned an invalid yes/no choice.")
    return str(choice)


def _summarize_project(overview: dict[str, object]) -> str:
    prompt = (
        "You are GitHubProjectAssistant. Write a clear English project summary from "
        "the supplied public GitHub facts. Distinguish facts from cautious inferences. "
        "Cover project name, purpose, core capabilities, typical use cases, intended "
        "users, primary technology, execution or installation entry points, license, "
        "maintenance status, and important README limitations. Do not merely copy the "
        "README, do not judge quality from stars or open issue count alone, and do not "
        "invent details. Mention when a field is unavailable.\n\n"
        + json.dumps(overview, ensure_ascii=True, indent=2)
    )
    return _call_model(prompt)


def _analyze_issues(issue_information: dict[str, object]) -> dict[str, object]:
    count = issue_information.get("analyzed_issue_count")
    issues = issue_information.get("issues")
    if not isinstance(count, int) or not isinstance(issues, list):
        raise RuntimeError("GitHub Issue information has an invalid shape.")
    prompt = (
        "Analyze this limited sample of recently updated open GitHub Issues. "
        "Return JSON with exactly these fields: analyzed_issue_count (number), "
        "common_problems (array of strings), confirmed_problems (array of strings), "
        "unresolved_problems (array of strings), representative_issues (array of "
        "strings), limitations (array of strings). Distinguish repeated concerns, "
        "isolated user reports, maintainer-confirmed problems, and unresolved reports. "
        "Select a small representative set using issue numbers and concise evidence. "
        "State what this sample cannot establish. Never generalize one user report, "
        "and never claim that open issue count alone measures project quality. "
        "Use only supplied data and preserve the exact analyzed count.\n\n"
        + json.dumps(issue_information, ensure_ascii=True, indent=2)
    )
    result = _call_model_json(prompt)
    if result.get("analyzed_issue_count") != count:
        raise RuntimeError("The language model changed the analyzed Issue count.")
    for field in (
        "common_problems",
        "confirmed_problems",
        "unresolved_problems",
        "representative_issues",
        "limitations",
    ):
        _as_text_list(result.get(field), field)
    return result


def _parse_release_request(answer: str) -> dict[str, str]:
    value = answer.strip()
    if value == "overview":
        return {"analysis_mode": "overview"}
    parts = value.split(";")
    if len(parts) != 4 or parts[0] != "asset_match":
        raise ValueError(
            "Release request must be 'overview' or "
            "'asset_match;operating_system;architecture;package_preference'."
        )
    operating_system, architecture, package_preference = parts[1:]
    if operating_system not in {"windows", "macos", "linux", "other"}:
        raise ValueError("Operating system must be windows, macos, linux, or other.")
    if architecture not in {"x64", "arm64", "unknown"}:
        raise ValueError("Architecture must be x64, arm64, or unknown.")
    if package_preference not in {"installer", "portable", "archive", "any"}:
        raise ValueError(
            "Package preference must be installer, portable, archive, or any."
        )
    return {
        "analysis_mode": "asset_match",
        "operating_system": operating_system,
        "architecture": architecture,
        "package_preference": package_preference,
    }


def _is_source_like_asset(name: str) -> bool:
    normalized = re.sub(r"[_-]+", " ", name.lower())
    return (
        "source code" in normalized
        or "source archive" in normalized
        or normalized.startswith("source.")
    )


def _release_overview(release: dict[str, object]) -> dict[str, object]:
    prompt = (
        "Create a concise English overview of the supplied latest official GitHub "
        "Release. Include its version, name, publication time, and key Release Notes. "
        "Do not invent or overstate changes.\n\n"
        + json.dumps(release, ensure_ascii=True, indent=2)
    )
    summary = _call_model(prompt)
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        raise RuntimeError("Release assets have an invalid shape.")
    return {
        "status": "overview",
        "version": str(release.get("version") or ""),
        "summary": f"{summary}\nAsset count: {len(assets)}.",
        "acquisition_url": str(release.get("source_zip_url") or ""),
        "integrity_guidance": "No file operation was performed.",
        "limitations": [
            "This is metadata and Release Notes guidance only; no Release file was downloaded."
        ],
    }


def _select_asset(
    release: dict[str, object], release_request: dict[str, str]
) -> dict[str, object]:
    raw_assets = release.get("assets", [])
    if not isinstance(raw_assets, list):
        raise RuntimeError("Release assets have an invalid shape.")
    assets = [
        asset
        for asset in raw_assets
        if isinstance(asset, dict)
        and all(key in asset for key in ("name", "download_url", "size", "digest"))
        and not _is_source_like_asset(str(asset.get("name") or ""))
    ]
    prompt = (
        "Select the most suitable maintainer-uploaded GitHub Release Asset for the "
        "user's preferences. Consider operating system, processor architecture, and "
        "package preference from asset names and metadata. Do not guess compatibility "
        "when evidence is insufficient. Automatically generated Source code zip/tar "
        "archives are not installable Assets and are excluded. Return exactly a JSON "
        "object with selected_asset_name (string or null) and reason (string). The "
        "selected name must exactly match one supplied asset name.\n"
        f"Preferences: {json.dumps(release_request, ensure_ascii=True)}\n"
        f"Assets: {json.dumps(assets, ensure_ascii=True, indent=2)}"
    )
    selection = _call_model_json(prompt)
    selected_name = selection.get("selected_asset_name")
    reason = selection.get("reason")
    if selected_name is not None and not isinstance(selected_name, str):
        raise RuntimeError("The language model returned an invalid selected Asset.")
    if not isinstance(reason, str):
        raise RuntimeError("The language model returned an invalid Asset reason.")
    selected = next(
        (asset for asset in assets if asset.get("name") == selected_name), None
    )
    return {"found": selected is not None, "reason": reason, "asset": selected}


def _release_asset_advice(
    release: dict[str, object], release_request: dict[str, str]
) -> dict[str, object]:
    selection = _select_asset(release, release_request)
    limitations = [
        "Compatibility is inferred from maintainer-provided metadata and the asset name; verify it on the user's system.",
        "No file was downloaded, created, installed, extracted, or executed.",
    ]
    if not selection["found"]:
        return {
            "status": "no_match",
            "version": str(release.get("version") or ""),
            "summary": (
                "No compatible maintainer-uploaded Asset was identified for the requested "
                f"preferences. Reason: {selection['reason']}"
            ),
            "acquisition_url": "",
            "integrity_guidance": "Do not download an Asset based on this result.",
            "limitations": limitations,
        }
    asset = selection["asset"]
    if not isinstance(asset, dict):
        raise RuntimeError("Asset selection returned an invalid Asset object.")
    digest = str(asset.get("digest") or "")
    integrity = (
        f"Verify the downloaded file's digest against {digest}."
        if digest
        else "GitHub did not provide an asset digest; use the publisher's independent verification guidance if available."
    )
    return {
        "status": "recommended",
        "version": str(release.get("version") or ""),
        "summary": (
            f"Recommended Asset: {asset.get('name')}. Size: {int(asset.get('size') or 0)} bytes. "
            f"Compatibility rationale: {selection['reason']}"
        ),
        "acquisition_url": str(asset.get("download_url") or ""),
        "integrity_guidance": integrity,
        "limitations": limitations,
        "asset": asset,
    }


def _release_advice(
    selected_repository: dict[str, str], release_request: dict[str, str]
) -> dict[str, object]:
    release_information = get_github_release(
        selected_repository["owner"], selected_repository["repository"]
    )
    if release_request["analysis_mode"] == "overview":
        return _release_overview(release_information)
    return _release_asset_advice(release_information, release_request)


def _print_project_summary(summary: str) -> None:
    print("\nProject summary")
    print(summary)


def _ask(prompt: str) -> str:
    print(prompt)
    return input("> ").strip()


def main() -> dict[str, object]:
    """Run ProjectNavigator and return the final result object."""
    project_summary = DEFAULT_PROJECT_SUMMARY
    issue_analysis_result: dict[str, object] | None = None
    release_advice: dict[str, object] | None = None
    repository_input_retry_count = 0
    repository_input_limit_exceeded = False

    try:
        print(
            f"{APP_NAME} requires either a complete GitHub Repository URL or an explicit "
            "owner/repository identifier. It can summarize public project information, "
            "analyze recent open Issues, and provide Release guidance without downloading files."
        )
        project_input = _ask(
            "Enter a complete GitHub Repository URL or an explicit owner/repository identifier:"
        )

        def classify(value: str) -> str:
            try:
                parse_github_repository_input(value)
            except (TypeError, ValueError):
                return "unclear"
            return "repository_url" if "://" in value else "repository_name"

        input_kind = classify(project_input)
        while input_kind == "unclear" and repository_input_retry_count < 3:
            project_input = _ask(
                "The current input does not uniquely identify a Repository. Enter a complete "
                "GitHub Repository URL or an explicit owner/repository identifier:"
            )
            repository_input_retry_count += 1
            input_kind = classify(project_input)

        repository_input_limit_exceeded = (
            input_kind == "unclear" and repository_input_retry_count >= 3
        )
        if repository_input_limit_exceeded:
            project_summary = (
                "The Repository input remains unclear after three correction attempts. "
                "The target Repository could not be determined."
            )
            _print_project_summary(project_summary)
            print("GitHub was not accessed, and no Issue or Release analysis was performed.")
            return {"project_summary": project_summary}

        selected_repository = parse_github_repository_input(project_input)
        project_overview = get_github_project_overview(
            selected_repository["owner"], selected_repository["repository"]
        )
        repository_found = bool(project_overview["found"])
        if not repository_found:
            project_summary = (
                f"Repository {selected_repository['owner']}/{selected_repository['repository']} "
                "was not found on GitHub. This is a Repository-not-found result; it is not "
                "being reinterpreted as a network, authentication, rate-limit, or service failure."
            )
            _print_project_summary(project_summary)
            return {"project_summary": project_summary}

        project_summary = _summarize_project(project_overview)
        _print_project_summary(project_summary)
        issue_choice = _interpret_yes_no(
            _ask("Would you like an analysis of recently updated open Issues?"),
            "Would the user like an analysis of recently updated open Issues?",
        )
        if issue_choice == "yes":
            issue_information = get_github_issue_information(
                selected_repository["owner"], selected_repository["repository"]
            )
            issue_analysis_result = _analyze_issues(issue_information)

        release_choice = _interpret_yes_no(
            _ask("Would you like guidance about the latest official Release?"),
            "Would the user like guidance about the latest official Release?",
        )
        if release_choice == "yes":
            release_answer = _ask(
                "Enter exactly 'overview' or 'asset_match;operating_system;architecture;package_preference'. "
                "For example: asset_match;linux;x64;any"
            )
            release_request = _parse_release_request(release_answer)
            release_advice = _release_advice(selected_repository, release_request)

        result: dict[str, object] = {"project_summary": project_summary}
        if issue_analysis_result is not None:
            result["issue_analysis_result"] = issue_analysis_result
        if release_advice is not None:
            result["release_advice"] = release_advice
        print("\nFinal result")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    except (EOFError, KeyboardInterrupt):
        print("\nExecution stopped before the requested workflow completed.")
        return {"error": "Interactive input ended before completion."}
    except Exception as exc:
        print(f"Execution failed: {exc}", file=sys.stderr)
        return {"error": str(exc)}


if __name__ == "__main__":
    main()
