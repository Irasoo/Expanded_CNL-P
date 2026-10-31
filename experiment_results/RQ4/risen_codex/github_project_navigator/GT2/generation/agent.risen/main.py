from __future__ import annotations

"""GitHubProjectAssistant: a terminal-only, read-only GitHub project guide."""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries from .env without overwriting the process."""
    dotenv = Path(".env")
    if not dotenv.is_file():
        return
    try:
        lines = dotenv.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _llm_client() -> tuple[Any, str]:
    _load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("BASE_URL", "").strip()
    model = (
        os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
    )
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured in .env or the environment.")
    if not base_url:
        raise RuntimeError("BASE_URL is not configured in .env or the environment.")
    if not model:
        raise RuntimeError(
            "No model configured: set CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL."
        )
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "The official OpenAI Python Client is required; install the 'openai' package."
        ) from exc
    return OpenAI(api_key=api_key, base_url=base_url), model


def _ask_llm(instruction: str, schema_hint: str) -> dict[str, Any]:
    client, model = _llm_client()
    system = (
        "You are GitHubProjectAssistant, a cautious and evidence-based assistant. "
        "Use only the supplied GitHub data or user answer. Do not invent facts. "
        "Return exactly one valid JSON object and no Markdown. "
        + schema_hint
    )
    try:
        response = client.responses.create(
            model=model,
            reasoning={"effort": "high"},
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": instruction}],
                },
            ],
        )
    except Exception as exc:
        raise RuntimeError(f"Runtime language-model call failed: {type(exc).__name__}: {exc}") from exc
    try:
        content = response.output_text or ""
        if content.strip().startswith("```"):
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
        parsed = json.loads(content)
    except (AttributeError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("The language model returned malformed JSON.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("The language model returned a JSON value that was not an object.")
    return parsed


def parse_github_repository_input(project_input: str) -> dict[str, str]:
    """Parse exactly one explicit GitHub repository URL or owner/repository."""
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
        raise ValueError("GitHub Repository input must identify exactly one owner and repository.")
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


def _github_request(url: str, accept: str = "application/vnd.github+json", raw: bool = False) -> Any:
    _load_dotenv()
    token = os.getenv("GITHUB_TOKEN", "").strip()
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "cnlp-github-project-assistant",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        request = Request(url, headers=headers, method="GET")
        with urlopen(request, timeout=30) as response:
            body = response.read()
            if raw:
                return body.decode("utf-8", errors="replace")
            return json.loads(body.decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"GitHub request returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GitHub data could not be read: {type(exc).__name__}: {exc}") from exc


def _not_found_overview() -> dict[str, Any]:
    return {
        "found": False, "full_name": "", "repository_url": "", "description": "",
        "readme": "", "license": "", "primary_language": "", "topics": [],
        "stars": 0, "forks": 0, "open_issues": 0, "archived": False, "updated_at": "",
    }


def get_github_project_overview(owner: str, repository: str) -> dict[str, Any]:
    valid = re.compile(r"^[A-Za-z0-9_.-]+$")
    if not owner or not repository or not valid.fullmatch(owner) or not valid.fullmatch(repository):
        raise ValueError("Invalid GitHub owner or repository name.")
    base = f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repository, safe='')}"
    try:
        metadata = _github_request(base)
    except RuntimeError as exc:
        if "HTTP 404" in str(exc):
            return _not_found_overview()
        raise
    if not isinstance(metadata, dict):
        raise RuntimeError("GitHub returned malformed repository metadata.")
    readme = ""
    try:
        raw_readme = _github_request(base + "/readme", "application/vnd.github.raw+json", raw=True)
        if isinstance(raw_readme, str):
            readme = raw_readme[:50000]
    except RuntimeError as exc:
        if "HTTP 404" not in str(exc):
            raise RuntimeError(f"GitHub README could not be read: {exc}") from exc
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
        "forks": int(metadata.get("forks") or metadata.get("forks_count") or 0),
        "open_issues": int(metadata.get("open_issues_count") or 0),
        "archived": bool(metadata.get("archived", False)),
        "updated_at": str(metadata.get("updated_at") or ""),
    }


def get_github_issue_information(owner: str, repository: str) -> dict[str, Any]:
    url = (
        f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repository, safe='')}/issues?"
        + urlencode({"state": "open", "sort": "updated", "direction": "desc", "per_page": 100, "page": 1})
    )
    payload = _github_request(url)
    if not isinstance(payload, list):
        raise RuntimeError("GitHub returned malformed Issue data.")
    issues: list[str] = []
    for item in payload:
        if not isinstance(item, dict) or "pull_request" in item:
            continue
        labels = item.get("labels", [])
        label_names = [str(label["name"]) for label in labels if isinstance(label, dict) and label.get("name")] if isinstance(labels, list) else []
        body = str(item.get("body") or "")[:4000]
        issues.append("\n".join([
            f"#{int(item.get('number') or 0)}: {str(item.get('title') or '')}",
            f"URL: {item.get('html_url') or ''}", f"State: {item.get('state') or ''}",
            f"Updated at: {item.get('updated_at') or ''}", f"Comments: {int(item.get('comments') or 0)}",
            f"Labels: {', '.join(label_names) if label_names else 'none'}", f"Body: {body}",
        ]))
    return {"analyzed_issue_count": len(issues), "issues": issues}


def get_github_release(owner: str, repository: str) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repository, safe='')}/releases/latest"
    selected = _github_request(url)
    if not isinstance(selected, dict):
        raise RuntimeError("GitHub returned malformed Release data.")
    raw_assets = selected.get("assets", [])
    assets = [
        {"name": str(asset.get("name") or ""), "download_url": str(asset.get("browser_download_url") or ""),
         "size": int(asset.get("size") or 0), "digest": str(asset.get("digest") or "")}
        for asset in raw_assets if isinstance(asset, dict)
    ] if isinstance(raw_assets, list) else []
    return {
        "version": str(selected.get("tag_name") or ""), "release_name": str(selected.get("name") or ""),
        "release_notes": str(selected.get("body") or "")[:50000],
        "published_at": str(selected.get("published_at") or ""), "assets": assets,
        "source_zip_url": str(selected.get("zipball_url") or ""), "source_tar_url": str(selected.get("tarball_url") or ""),
    }


def _interpret_yes_no(answer: str, question: str) -> str:
    result = _ask_llm(
        f"Question asked: {question}\nUser's single answer: {answer!r}\nInterpret it as exactly 'yes' or 'no'.",
        "Return JSON with exactly one key: choice, whose value is either 'yes' or 'no'.",
    )
    choice = result.get("choice")
    if choice not in {"yes", "no"}:
        raise RuntimeError("The language model could not interpret the answer as yes or no.")
    return choice


def _project_summary(overview: dict[str, Any]) -> str:
    result = _ask_llm(
        "Create clear English project_summary from this public GitHub repository data. "
        "Cover project name, purpose, core capabilities, typical use cases, intended users, "
        "primary technology, execution or installation entry points, license, maintenance "
        "status, and important README limitations. Do not merely copy README and do not "
        "judge quality from Stars or open Issue count alone.\nDATA:\n" + json.dumps(overview, ensure_ascii=False),
        "Return JSON with exactly one key: project_summary (a concise English string).",
    )
    summary = result.get("project_summary")
    if not isinstance(summary, str) or not summary.strip():
        raise RuntimeError("The language model returned an empty project summary.")
    return summary.strip()


def _analyze_issues(issue_information: dict[str, Any]) -> dict[str, Any]:
    result = _ask_llm(
        "Analyze the supplied recently updated open GitHub Issues. Distinguish repeated "
        "concerns, isolated user reports, maintainer-confirmed problems, and unresolved "
        "reports. Select a small representative set. State what this limited sample cannot "
        "establish; never call one report a general problem.\nDATA:\n"
        + json.dumps(issue_information, ensure_ascii=False),
        "Return JSON with keys analyzed_issue_count (number), common_problems (list of strings), "
        "confirmed_problems (list of strings), unresolved_problems (list of strings), "
        "representative_issues (list of strings), and limitations (list of strings).",
    )
    expected = ["common_problems", "confirmed_problems", "unresolved_problems", "representative_issues", "limitations"]
    if not all(isinstance(result.get(key), list) and all(isinstance(x, str) for x in result[key]) for key in expected):
        raise RuntimeError("The language model returned an invalid Issue analysis.")
    result["analyzed_issue_count"] = issue_information["analyzed_issue_count"]
    return result


def _parse_release_request(answer: str) -> dict[str, str]:
    value = answer.strip()
    if value == "overview":
        return {"analysis_mode": "overview"}
    parts = value.split(";")
    if len(parts) != 4 or parts[0] != "asset_match":
        raise ValueError("Release request must be 'overview' or asset_match;operating_system;architecture;package_preference.")
    operating_system, architecture, package_preference = parts[1:]
    if operating_system not in {"windows", "macos", "linux", "other"}:
        raise ValueError("Operating system must be windows, macos, linux, or other.")
    if architecture not in {"x64", "arm64", "unknown"}:
        raise ValueError("Architecture must be x64, arm64, or unknown.")
    if package_preference not in {"installer", "portable", "archive", "any"}:
        raise ValueError("Package preference must be installer, portable, archive, or any.")
    return {"analysis_mode": "asset_match", "operating_system": operating_system, "architecture": architecture, "package_preference": package_preference}


def _release_advice(release: dict[str, Any], request: dict[str, str]) -> dict[str, Any]:
    if request["analysis_mode"] == "overview":
        result = _ask_llm(
            "Create an English overview of this latest official GitHub Release, including "
            "version, name, publication time, key Release Notes, and asset count.\nDATA:\n"
            + json.dumps(release, ensure_ascii=False),
            "Return JSON with status='overview', version, summary, acquisition_url, integrity_guidance "
            "as strings, and limitations as a list of strings. Explicitly say no file operation was performed.",
        )
        summary = result.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise RuntimeError("The language model returned an empty Release overview.")
        limitations = result.get("limitations", [])
        if not isinstance(limitations, list) or not all(isinstance(item, str) for item in limitations):
            raise RuntimeError("The language model returned invalid Release limitations.")
        result["status"] = "overview"
        result["version"] = release["version"]
        acquisition_url = result.get("acquisition_url", "")
        integrity_guidance = result.get("integrity_guidance", "")
        if not isinstance(acquisition_url, str) or not isinstance(integrity_guidance, str):
            raise RuntimeError("The language model returned invalid Release guidance fields.")
        if "No file operation was performed." not in summary:
            summary = summary.rstrip() + " No file operation was performed."
        result["summary"] = summary
        result["acquisition_url"] = acquisition_url
        result["integrity_guidance"] = integrity_guidance
        result["limitations"] = limitations
        return result

    result = _ask_llm(
        "Select the most suitable maintainer-uploaded Release Asset for these preferences. "
        "Never select automatically generated source code zipball or tarball as installable. "
        "Consider OS, architecture, and package preference from names and metadata, and be "
        "conservative when compatibility is not established.\nPREFERENCES:\n"
        + json.dumps(request, ensure_ascii=False) + "\nRELEASE:\n" + json.dumps(release, ensure_ascii=False),
        "Return JSON with found (boolean), reason (string), and asset (object or null). If asset is present, "
        "it must be one exact object from the supplied assets with name, download_url, size, and digest.",
    )
    asset = result.get("asset")
    valid_assets = release.get("assets", [])
    if result.get("found") and isinstance(asset, dict) and asset.get("name") in {a.get("name") for a in valid_assets}:
        selected = next(a for a in valid_assets if a.get("name") == asset.get("name"))
        return {
            "status": "recommended", "version": release["version"],
            "summary": f"Recommended asset: {selected['name']}. {result.get('reason', '')}",
            "acquisition_url": selected["download_url"],
            "integrity_guidance": f"Verify the downloaded file against its published digest: {selected['digest'] or 'No digest was published.'}",
            "limitations": ["No file was downloaded, created, installed, extracted, or executed."],
            "asset": selected,
        }
    return {
        "status": "no_match", "version": release["version"],
        "summary": str(result.get("reason") or "No compatible maintainer-uploaded asset was identified."),
        "acquisition_url": "", "integrity_guidance": "No asset can be verified because none was selected.",
        "limitations": ["No file was downloaded, created, installed, extracted, or executed."],
    }


def _show(label: str, value: Any) -> None:
    print(f"\n=== {label} ===")
    if isinstance(value, str):
        print(value)
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> dict[str, Any]:
    """Run ProjectNavigator and return its final structured result."""
    project_summary = "No project summary is available because the target Repository was not resolved."
    final: dict[str, Any] = {"project_summary": project_summary}
    try:
        print("GitHubProjectAssistant can summarize public project information, analyze recent open Issues, and provide Release guidance without downloading files.")
        print("Enter a complete GitHub Repository URL or an explicit owner/repository identifier.")
        project_input = input().strip()
        input_kind = classify_project_input(project_input)
        retry_count = 0
        while input_kind == "unclear" and retry_count < 3:
            print("The current input does not uniquely identify a Repository. Enter a complete GitHub Repository URL or an explicit owner/repository identifier.")
            project_input = input().strip()
            retry_count += 1
            input_kind = classify_project_input(project_input)
        limit_exceeded = input_kind == "unclear" and retry_count >= 3
        if limit_exceeded:
            project_summary = "The Repository input remains unclear after three correction attempts. The target Repository could not be determined."
            final = {"project_summary": project_summary}
            _show("Project summary", project_summary)
            print("GitHub was not accessed, and no Issue or Release analysis was performed.")
            return final

        selected = parse_github_repository_input(project_input)
        overview = get_github_project_overview(selected["owner"], selected["repository"])
        if not overview["found"]:
            project_summary = (
                f"Repository {selected['owner']}/{selected['repository']} was not found on GitHub. "
                "This is a Repository-not-found result, not a network, authentication, rate-limit, or service failure."
            )
            final = {"project_summary": project_summary}
            _show("Project summary", project_summary)
            return final

        project_summary = _project_summary(overview)
        final = {"project_summary": project_summary}
        _show("Project summary", project_summary)
        print("Would you like an analysis of recently updated open Issues? (yes/no)")
        issue_choice = _interpret_yes_no(input(), "Would you like an analysis of recently updated open Issues?")
        if issue_choice == "yes":
            issue_information = get_github_issue_information(selected["owner"], selected["repository"])
            final["issue_analysis_result"] = _analyze_issues(issue_information)
            _show("Issue analysis", final["issue_analysis_result"])

        print("Would you like guidance about the latest official Release? (yes/no)")
        release_choice = _interpret_yes_no(input(), "Would you like guidance about the latest official Release?")
        if release_choice == "yes":
            print("Enter either 'overview' or 'asset_match;operating_system;architecture;package_preference' exactly.\nFor asset_match, use OS windows/macos/linux/other, architecture x64/arm64/unknown, and preference installer/portable/archive/any.")
            release_request = _parse_release_request(input())
            release = get_github_release(selected["owner"], selected["repository"])
            final["release_advice"] = _release_advice(release, release_request)
            _show("Release advice", final["release_advice"])
        _show("Final result", final)
        return final
    except (EOFError, KeyboardInterrupt):
        raise RuntimeError("Terminal input ended before ProjectNavigator completed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Execution failure: {exc}", file=sys.stderr)
        raise SystemExit(1)
