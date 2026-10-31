from __future__ import annotations

"""Terminal GitHub project assistant.

The program deliberately performs only read requests against GitHub.  It never
downloads release files; release assets are represented by the metadata GitHub
returns for them.
"""

import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen


PROJECT_SUMMARY_DEFAULT = (
    "No project summary is available because the target Repository was not resolved."
)


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries from .env without requiring a dependency."""
    path = os.path.join(os.getcwd(), ".env")
    try:
        with open(path, "r", encoding="utf-8") as env_file:
            lines = env_file.readlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
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


def _github_json(url: str, *, not_found_is_empty: bool = False) -> Any:
    try:
        request = Request(url, headers=_github_headers(), method="GET")
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if not_found_is_empty and exc.code == 404:
            return None
        raise RuntimeError(f"GitHub request returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GitHub data could not be read: {type(exc).__name__}: {exc}") from exc


def _validate_github_components(owner: str, repository: str) -> tuple[str, str]:
    owner_value, repository_value = str(owner).strip(), str(repository).strip()
    valid = re.compile(r"^[A-Za-z0-9_.-]+$")
    if not owner_value or not repository_value or not valid.fullmatch(owner_value) or not valid.fullmatch(repository_value):
        raise ValueError("Invalid GitHub owner or repository name.")
    return owner_value, repository_value


def get_github_project_overview(owner: str, repository: str) -> dict[str, object]:
    owner_value, repository_value = _validate_github_components(owner, repository)
    base = "https://api.github.com/repos/" + quote(owner_value, safe="") + "/" + quote(repository_value, safe="")
    empty = {
        "found": False, "full_name": "", "repository_url": "", "description": "",
        "readme": "", "license": "", "primary_language": "", "topics": [],
        "stars": 0, "forks": 0, "open_issues": 0, "archived": False, "updated_at": "",
    }
    metadata = _github_json(base, not_found_is_empty=True)
    if metadata is None:
        return empty
    if not isinstance(metadata, dict):
        raise RuntimeError("GitHub returned malformed repository metadata.")

    readme = ""
    readme_headers = _github_headers()
    readme_headers["Accept"] = "application/vnd.github.raw+json"
    try:
        request = Request(base + "/readme", headers=readme_headers, method="GET")
        with urlopen(request, timeout=30) as response:
            readme = response.read(50001).decode("utf-8", errors="replace")[:50000]
    except HTTPError as exc:
        if exc.code != 404:
            raise RuntimeError(f"GitHub README lookup returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"GitHub README could not be read: {type(exc).__name__}: {exc}") from exc

    license_data = metadata.get("license")
    license_name = ""
    if isinstance(license_data, dict):
        license_name = str(license_data.get("spdx_id") or license_data.get("name") or "")
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
    owner_value, repository_value = _validate_github_components(owner, repository)
    url = (
        "https://api.github.com/repos/" + quote(owner_value, safe="") + "/" + quote(repository_value, safe="")
        + "/issues?" + urlencode({"state": "open", "sort": "updated", "direction": "desc", "per_page": 100, "page": 1})
    )
    payload = _github_json(url)
    if not isinstance(payload, list):
        raise RuntimeError("GitHub returned malformed Issue data.")
    issues: list[str] = []
    for item in payload:
        if not isinstance(item, dict) or "pull_request" in item:
            continue
        raw_labels = item.get("labels", [])
        labels = [str(label["name"]) for label in raw_labels if isinstance(label, dict) and label.get("name")] if isinstance(raw_labels, list) else []
        issues.append("\n".join([
            f"#{int(item.get('number') or 0)}: {str(item.get('title') or '')}",
            f"URL: {item.get('html_url') or ''}",
            f"State: {item.get('state') or ''}",
            f"Updated at: {item.get('updated_at') or ''}",
            f"Comments: {int(item.get('comments') or 0)}",
            f"Labels: {', '.join(labels) if labels else 'none'}",
            f"Body: {str(item.get('body') or '')[:4000]}",
        ]))
    return {"analyzed_issue_count": len(issues), "issues": issues}


def get_github_release(owner: str, repository: str) -> dict[str, object]:
    owner_value, repository_value = _validate_github_components(owner, repository)
    url = "https://api.github.com/repos/" + quote(owner_value, safe="") + "/" + quote(repository_value, safe="") + "/releases/latest"
    selected = _github_json(url)
    if not isinstance(selected, dict):
        raise RuntimeError("GitHub returned malformed Release data.")
    raw_assets = selected.get("assets", [])
    assets = []
    if isinstance(raw_assets, list):
        for asset in raw_assets:
            if isinstance(asset, dict):
                assets.append({
                    "name": str(asset.get("name") or ""),
                    "download_url": str(asset.get("browser_download_url") or ""),
                    "size": int(asset.get("size") or 0),
                    "digest": str(asset.get("digest") or ""),
                })
    return {
        "version": str(selected.get("tag_name") or ""),
        "release_name": str(selected.get("name") or ""),
        "release_notes": str(selected.get("body") or "")[:50000],
        "published_at": str(selected.get("published_at") or ""),
        "assets": assets,
        "source_zip_url": str(selected.get("zipball_url") or ""),
        "source_tar_url": str(selected.get("tarball_url") or ""),
    }


def _llm_client() -> tuple[Any, str]:
    _load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = (os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip() or os.getenv("OPENAI_MODEL", "").strip())
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured in .env or the environment.")
    if not model:
        raise RuntimeError("CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL must be configured in .env or the environment.")
    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url=os.getenv("BASE_URL", "").strip() or None), model


def _response_text(response: Any) -> str:
    value = getattr(response, "output_text", None)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise RuntimeError("The language model returned no text.")


def ask_text(instruction: str, data: Any) -> str:
    client, model = _llm_client()
    response = client.responses.create(
        model=model,
        reasoning={"effort": "high"},
        input=[
            {"role": "system", "content": [{"type": "input_text", "text": instruction}]},
            {"role": "user", "content": [{"type": "input_text", "text": json.dumps(data, ensure_ascii=False)}]},
        ],
    )
    return _response_text(response)


def ask_json(instruction: str, data: Any) -> dict[str, Any]:
    raw = ask_text(instruction + " Return only one valid JSON object, with no Markdown fences.", data)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The language model returned invalid JSON.") from exc
    if not isinstance(value, dict):
        raise RuntimeError("The language model returned a JSON value that was not an object.")
    return value


def interpret_yes_no(answer: str, question_context: str) -> str:
    result = ask_json(
        "Interpret the user's one answer to this yes/no question. Return {\"choice\": \"yes\"} or {\"choice\": \"no\"}. Resolve ordinary natural-language affirmations and refusals; do not ask a follow-up. Question: " + question_context,
        {"answer": answer},
    )
    choice = result.get("choice")
    if choice not in {"yes", "no"}:
        raise RuntimeError("The language model did not return a valid yes/no choice.")
    return choice


def build_project_summary(overview: dict[str, object]) -> str:
    return ask_text(
        "You are GitHubProjectAssistant. Write a clear English project overview from the supplied public facts. Cover project name, purpose, core capabilities, typical use cases, intended users, primary technology, execution or installation entry points, license, maintenance status, and important README limitations. Distinguish facts from reasonable interpretation. Do not merely copy the README, and do not judge quality from Stars or open Issue count alone. Do not claim actions not represented in the data.",
        overview,
    )


def analyze_issues(issue_information: dict[str, object]) -> dict[str, object]:
    result = ask_json(
        "Analyze this limited sample of recently updated open GitHub Issues. Distinguish repeated concerns, isolated user reports, maintainer-confirmed problems, and unresolved reports. Select a small representative set using issue numbers/titles. Return exactly these JSON fields: analyzed_issue_count (number), common_problems (array of strings), confirmed_problems (array of strings), unresolved_problems (array of strings), representative_issues (array of strings), limitations (array of strings). Never call one user report a general problem. Explicitly state what this limited sample cannot establish. Preserve the supplied count.",
        issue_information,
    )
    if result.get("analyzed_issue_count") != issue_information.get("analyzed_issue_count"):
        raise RuntimeError("The Issue analysis count did not match the retrieved sample.")
    for key in ("common_problems", "confirmed_problems", "unresolved_problems", "representative_issues", "limitations"):
        if not isinstance(result.get(key), list) or not all(isinstance(x, str) for x in result[key]):
            raise RuntimeError(f"The Issue analysis field {key} is malformed.")
    return result


def parse_release_request(answer: str) -> dict[str, str]:
    parts = [part.strip() for part in answer.strip().split(";")]
    if parts == ["overview"]:
        return {"analysis_mode": "overview"}
    if len(parts) != 4 or parts[0] != "asset_match":
        raise ValueError("ReleaseRequest must be 'overview' or 'asset_match;operating_system;architecture;package_preference'.")
    if parts[1] not in {"windows", "macos", "linux", "other"}:
        raise ValueError("Operating system must be windows, macos, linux, or other.")
    if parts[2] not in {"x64", "arm64", "unknown"}:
        raise ValueError("Architecture must be x64, arm64, or unknown.")
    if parts[3] not in {"installer", "portable", "archive", "any"}:
        raise ValueError("Package preference must be installer, portable, archive, or any.")
    return {"analysis_mode": "asset_match", "operating_system": parts[1], "architecture": parts[2], "package_preference": parts[3]}


def _is_source_archive(name: str) -> bool:
    lowered = name.lower()
    return lowered in {"source code.zip", "source code.tar.gz", "source.zip", "source.tar.gz"} or "source code" in lowered


def select_asset(release: dict[str, object], request: dict[str, str]) -> dict[str, object]:
    assets = [asset for asset in release.get("assets", []) if isinstance(asset, dict) and not _is_source_archive(str(asset.get("name", "")))]
    if not assets:
        return {"found": False, "reason": "The latest Release has no maintainer-uploaded non-source assets to match."}
    result = ask_json(
        "Select the most suitable maintainer-uploaded Release asset for the user's exact platform preferences. Do not select source archives, and do not infer compatibility when the filename and metadata do not support it. Return {\"found\": true/false, \"asset_name\": string or null, \"reason\": string}. If no candidate is a defensible match, use found=false. Candidate names must be copied exactly.",
        {"release": release, "request": request, "eligible_assets": assets},
    )
    found = result.get("found")
    name = result.get("asset_name")
    if not isinstance(found, bool) or (found and not isinstance(name, str)):
        raise RuntimeError("The asset selection response is malformed.")
    if found:
        matching = [asset for asset in assets if asset.get("name") == name]
        if not matching:
            raise RuntimeError("The language model selected an asset that was not returned by GitHub.")
        return {"found": True, "reason": str(result.get("reason") or ""), "asset": matching[0]}
    return {"found": False, "reason": str(result.get("reason") or "No compatible asset was identified.")}


def advise_release(release: dict[str, object], request: dict[str, str]) -> dict[str, object]:
    if request["analysis_mode"] == "overview":
        summary = ask_text(
            "Create a concise English overview of the latest official GitHub Release. Include version, name, publication time, key Release Notes, and Asset count. Explicitly say that no file operation was performed. Do not invent missing facts.",
            release,
        )
        return {
            "status": "overview", "version": str(release["version"]), "summary": summary,
            "acquisition_url": "", "integrity_guidance": "No file was downloaded or acquired.",
            "limitations": ["This is metadata for the latest official Release only; no file operation was performed."],
        }

    selection = select_asset(release, request)
    if not selection["found"]:
        return {
            "status": "no_match", "version": str(release["version"]),
            "summary": "No suitable maintainer-uploaded asset was identified for the requested preferences.",
            "acquisition_url": "", "integrity_guidance": str(selection["reason"]),
            "limitations": ["No file was downloaded, created, installed, extracted, or executed.", "Automatically generated source archives were excluded as installable assets."],
        }

    asset = selection["asset"]
    generated = ask_text(
        "Write English Release asset compatibility guidance using only the supplied facts. Include the exact asset name, byte size, URL, digest (or say it is unavailable), the compatibility rationale, and user-side verification guidance. Explicitly state that no file was downloaded, created, installed, extracted, or executed. Do not claim that a filename proves compatibility.",
        {"release": release, "request": request, "selection_reason": selection["reason"], "asset": asset},
    )
    return {
        "status": "recommended", "version": str(release["version"]), "summary": generated,
        "acquisition_url": str(asset.get("download_url") or ""),
        "integrity_guidance": f"Digest reported by GitHub: {asset.get('digest') or 'unavailable'}. Verify the downloaded file against it on your side before use.",
        "limitations": ["Compatibility is inferred from release metadata and naming; verify it in the project's documentation.", "No file was downloaded, created, installed, extracted, or executed."],
        "asset": asset,
    }


def _print_json_section(title: str, value: Any) -> None:
    print(f"\n{title}")
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> dict[str, object] | None:
    """Run ProjectNavigator and return the final result object."""
    project_summary = PROJECT_SUMMARY_DEFAULT
    issue_analysis_result: dict[str, object] | None = None
    release_advice: dict[str, object] | None = None
    repository_input_retry_count = 0

    try:
        print("I need a complete GitHub Repository URL or an explicit owner/repository identifier.")
        print("I can summarize public project information, analyze recent open Issues, and provide Release guidance without downloading files.")
        project_input = input("Repository: ")
        input_kind = classify_project_input(project_input)
        while input_kind == "unclear" and repository_input_retry_count < 3:
            print("The current input does not uniquely identify a Repository.")
            print("Please enter a complete GitHub Repository URL or an explicit owner/repository identifier.")
            project_input = input("Repository: ")
            repository_input_retry_count += 1
            input_kind = classify_project_input(project_input)

        limit_exceeded = input_kind == "unclear" and repository_input_retry_count >= 3
        if limit_exceeded:
            project_summary = (
                "The Repository input remains unclear after three correction attempts. "
                "The target Repository could not be determined."
            )
            _print_json_section("Project summary", project_summary)
            print("GitHub was not accessed, and no Issue or Release analysis was performed.")
            return {"project_summary": project_summary}

        selected_repository = parse_github_repository_input(project_input)
        project_overview = get_github_project_overview(selected_repository["owner"], selected_repository["repository"])
        if not project_overview["found"]:
            project_summary = (
                f"The Repository {selected_repository['owner']}/{selected_repository['repository']} was not found on GitHub. "
                "This is a Repository-not-found result, not a network, authentication, rate-limit, or service diagnosis."
            )
            _print_json_section("Project summary", project_summary)
            return {"project_summary": project_summary}

        project_summary = build_project_summary(project_overview)
        _print_json_section("Project summary", project_summary)
        issue_choice = interpret_yes_no(input("Analyze recently updated open Issues? (yes/no): "), "Do you want an analysis of recently updated open Issues?")
        if issue_choice == "yes":
            issue_information = get_github_issue_information(selected_repository["owner"], selected_repository["repository"])
            issue_analysis_result = analyze_issues(issue_information)

        release_choice = interpret_yes_no(input("Would you like guidance about the latest official Release? (yes/no): "), "Do you want guidance about the latest official Release?")
        if release_choice == "yes":
            print("Enter 'overview' or 'asset_match;operating_system;architecture;package_preference'.")
            print("Use operating_system: windows, macos, linux, other; architecture: x64, arm64, unknown; package_preference: installer, portable, archive, any.")
            release_request = parse_release_request(input("Release request: "))
            release_information = get_github_release(selected_repository["owner"], selected_repository["repository"])
            release_advice = advise_release(release_information, release_request)

        final_result: dict[str, object] = {"project_summary": project_summary}
        if issue_analysis_result is not None:
            final_result["issue_analysis_result"] = issue_analysis_result
        if release_advice is not None:
            final_result["release_advice"] = release_advice
        _print_json_section("Final result", final_result)
        return final_result
    except (RuntimeError, ValueError) as exc:
        print(f"Execution failure: {exc}")
        return None


if __name__ == "__main__":
    main()
