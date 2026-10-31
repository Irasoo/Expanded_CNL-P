"""Terminal-only GitHub project assistant generated from the supplied CNL-P script.

The program only reads public GitHub metadata.  It never downloads, creates,
installs, extracts, or executes release files.
"""

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


LOGGER = logging.getLogger("github_project_assistant")

PERSONA_AND_CONSTRAINTS = """
You are a cautious, evidence-based assistant for GitHub project information,
recent Issue risks, and Release compatibility. Your audience is developers and
software users. Write clear English. Treat only the supplied repository data as
evidence. Do not infer project quality from stars or open Issue counts. Never
describe a single user report as a general problem. State the actual Issue
sample scope and its limitations. Release guidance covers only the latest
official public release. Source ZIP and source TAR archives are source code,
not directly installable software by default. The assistant is read-only and
must never suggest that it created, downloaded, installed, extracted, or
executed a file.
""".strip()


def load_dotenv_if_present() -> None:
    """Load simple KEY=VALUE entries without requiring an extra dependency."""
    dotenv_path = ".env"
    if not os.path.isfile(dotenv_path):
        return
    with open(dotenv_path, "r", encoding="utf-8") as dotenv_file:
        for raw_line in dotenv_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key or key in os.environ:
                continue
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            os.environ[key] = value


class LanguageModel:
    """Small Responses API wrapper with the required runtime configuration."""

    def __init__(self) -> None:
        load_dotenv_if_present()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        base_url = os.getenv("BASE_URL", "").strip()
        model = (
            os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip()
            or os.getenv("OPENAI_MODEL", "").strip()
        )
        missing = [
            name
            for name, value in (
                ("OPENAI_API_KEY", api_key),
                ("BASE_URL", base_url),
                ("CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL", model),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Language-model configuration is missing: " + ", ".join(missing) + "."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("The 'openai' package is required to run this Agent.") from exc
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def text(self, task: str, data: Any) -> str:
        response = self.client.responses.create(
            model=self.model,
            instructions=PERSONA_AND_CONSTRAINTS,
            input=(
                task
                + "\n\nUse the following supplied data only:\n"
                + json.dumps(data, ensure_ascii=False)
            ),
            reasoning={"effort": "high"},
        )
        output = getattr(response, "output_text", "")
        if not isinstance(output, str) or not output.strip():
            raise RuntimeError("The language model returned no usable text.")
        return output.strip()

    def json(self, task: str, data: Any) -> dict[str, Any]:
        output = self.text(
            task
            + " Return exactly one JSON object and no Markdown code fence or surrounding prose.",
            data,
        )
        try:
            value = json.loads(output)
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


def classify_repository_input(project_input: str) -> str:
    """Classify solely by whether the explicit identifier can be safely parsed."""
    try:
        parse_github_repository_input(project_input)
    except (TypeError, ValueError):
        return "unclear"
    return "repository_url" if "://" in project_input.strip() else "repository_name"


def github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "cnlp-github-project-assistant",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def get_github_project_overview(owner: str, repository: str) -> dict[str, Any]:
    owner_value, repository_value = str(owner).strip(), str(repository).strip()
    valid_component = re.compile(r"^[A-Za-z0-9_.-]+$")
    if not owner_value or not repository_value or not valid_component.fullmatch(owner_value) or not valid_component.fullmatch(repository_value):
        raise ValueError("Invalid GitHub owner or repository name.")

    def not_found_result() -> dict[str, Any]:
        return {"found": False, "full_name": "", "repository_url": "", "description": "", "readme": "", "license": "", "primary_language": "", "topics": [], "stars": 0, "forks": 0, "open_issues": 0, "archived": False, "updated_at": ""}

    api_url = f"https://api.github.com/repos/{quote(owner_value, safe='')}/{quote(repository_value, safe='')}"
    try:
        with urlopen(Request(api_url, headers=github_headers(), method="GET"), timeout=30) as response:
            metadata = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return not_found_result()
        raise RuntimeError(f"GitHub repository lookup returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GitHub repository metadata could not be read: {type(exc).__name__}: {exc}") from exc
    if not isinstance(metadata, dict):
        raise RuntimeError("GitHub returned malformed repository metadata.")

    readme = ""
    readme_headers = github_headers()
    readme_headers["Accept"] = "application/vnd.github.raw+json"
    try:
        with urlopen(Request(api_url + "/readme", headers=readme_headers, method="GET"), timeout=30) as response:
            readme = response.read(50001).decode("utf-8", errors="replace")[:50000]
    except HTTPError as exc:
        if exc.code != 404:
            raise RuntimeError(f"GitHub README lookup returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"GitHub README could not be read: {type(exc).__name__}: {exc}") from exc

    license_data = metadata.get("license")
    topics = metadata.get("topics")
    return {
        "found": True,
        "full_name": str(metadata.get("full_name") or ""),
        "repository_url": str(metadata.get("html_url") or ""),
        "description": str(metadata.get("description") or ""),
        "readme": readme,
        "license": str(license_data.get("spdx_id") or license_data.get("name") or "") if isinstance(license_data, dict) else "",
        "primary_language": str(metadata.get("language") or ""),
        "topics": [str(item) for item in topics if isinstance(item, str)] if isinstance(topics, list) else [],
        "stars": int(metadata.get("stargazers_count") or 0),
        "forks": int(metadata.get("forks_count") or 0),
        "open_issues": int(metadata.get("open_issues_count") or 0),
        "archived": bool(metadata.get("archived", False)),
        "updated_at": str(metadata.get("updated_at") or ""),
    }


def get_github_issue_information(owner: str, repository: str) -> dict[str, Any]:
    if not str(owner).strip() or not str(repository).strip():
        raise ValueError("GitHub owner and repository are required.")
    url = (
        f"https://api.github.com/repos/{quote(str(owner).strip(), safe='')}/{quote(str(repository).strip(), safe='')}/issues?"
        + urlencode({"state": "open", "sort": "updated", "direction": "desc", "per_page": 100, "page": 1})
    )
    try:
        with urlopen(Request(url, headers=github_headers(), method="GET"), timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"GitHub Issue lookup returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GitHub Issues could not be read: {type(exc).__name__}: {exc}") from exc
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
            f"URL: {item.get('html_url') or ''}", f"State: {item.get('state') or ''}",
            f"Updated at: {item.get('updated_at') or ''}", f"Comments: {int(item.get('comments') or 0)}",
            f"Labels: {', '.join(labels) if labels else 'none'}", f"Body: {str(item.get('body') or '')[:4000]}",
        ]))
    return {"analyzed_issue_count": len(issues), "issues": issues}


def get_github_release(owner: str, repository: str) -> dict[str, Any]:
    if not str(owner).strip() or not str(repository).strip():
        raise ValueError("GitHub owner and repository are required.")
    url = f"https://api.github.com/repos/{quote(str(owner).strip(), safe='')}/{quote(str(repository).strip(), safe='')}/releases/latest"
    try:
        with urlopen(Request(url, headers=github_headers(), method="GET"), timeout=30) as response:
            selected = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"GitHub Release lookup returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GitHub Release data could not be read: {type(exc).__name__}: {exc}") from exc
    if not isinstance(selected, dict):
        raise RuntimeError("GitHub returned malformed Release data.")
    raw_assets = selected.get("assets", [])
    assets = [{"name": str(asset.get("name") or ""), "download_url": str(asset.get("browser_download_url") or ""), "size": int(asset.get("size") or 0), "digest": str(asset.get("digest") or "")} for asset in raw_assets if isinstance(asset, dict)] if isinstance(raw_assets, list) else []
    return {"version": str(selected.get("tag_name") or ""), "release_name": str(selected.get("name") or ""), "release_notes": str(selected.get("body") or "")[:50000], "published_at": str(selected.get("published_at") or ""), "assets": assets, "source_zip_url": str(selected.get("zipball_url") or ""), "source_tar_url": str(selected.get("tarball_url") or "")}


def read_input(prompt: str) -> str:
    print(prompt)
    try:
        return input("> ")
    except EOFError as exc:
        raise RuntimeError("Input ended before the requested answer was provided.") from exc


def normalize_yes_no(model: LanguageModel, answer: str, question: str) -> str:
    result = model.json(
        "Interpret the user's single response to this yes/no question: " + question
        + ". Determine whether it clearly means yes or no. Return {\"choice\": \"yes\"} or {\"choice\": \"no\"}. If it is not clear, return {\"choice\": \"invalid\"}.",
        {"user_response": answer},
    )
    choice = result.get("choice")
    if choice not in {"yes", "no"}:
        raise ValueError("The response did not clearly answer yes or no.")
    return choice


def parse_release_request(value: str) -> dict[str, str]:
    parts = value.strip().split(";")
    if parts == ["overview"]:
        return {"analysis_mode": "overview"}
    if len(parts) != 4 or parts[0] != "asset_match":
        raise ValueError("Release request must be 'overview' or exactly 'asset_match;operating_system;architecture;package_preference'.")
    operating_system, architecture, package_preference = parts[1:]
    if operating_system not in {"windows", "macos", "linux", "other"} or architecture not in {"x64", "arm64", "unknown"} or package_preference not in {"installer", "portable", "archive", "any"}:
        raise ValueError("Release request contains an unsupported platform, architecture, or package preference.")
    return {"analysis_mode": "asset_match", "operating_system": operating_system, "architecture": architecture, "package_preference": package_preference}


def project_summary(model: LanguageModel, overview: dict[str, Any]) -> str:
    return model.text(
        "Create a concise project overview. Cover project name, purpose, core capabilities, typical use cases, intended users, primary technology, execution or installation entry points when documented, license, maintenance status, and important README limitations. Do not merely copy the README. Do not use stars or open Issue count to judge quality.",
        overview,
    )


def not_found_summary(model: LanguageModel, repository: dict[str, str]) -> str:
    return model.text(
        "Explain that this explicitly identified GitHub repository was not found. Do not reinterpret the missing repository as an authentication, network, rate-limit, or service failure.",
        repository,
    )


def analyze_issues(model: LanguageModel, issue_information: dict[str, Any]) -> dict[str, Any]:
    result = model.json(
        "Analyze the recent open Issue sample. Return an object with these fields only: analyzed_issue_count (integer), common_problems (array of strings), confirmed_problems (array of strings), unresolved_problems (array of strings), representative_issues (array of strings), limitations (array of strings). Set analyzed_issue_count exactly to the supplied count. Distinguish repeated concerns from isolated reports. Describe a problem as maintainer-confirmed only with evidence in the supplied Issues. Select a small set of representatives containing Issue numbers and URLs. Clearly state that this limited, recently-updated open-Issue sample cannot establish all project problems.",
        issue_information,
    )
    expected = issue_information["analyzed_issue_count"]
    if result.get("analyzed_issue_count") != expected:
        raise RuntimeError("Issue analysis returned an incorrect analyzed_issue_count.")
    fields = ["common_problems", "confirmed_problems", "unresolved_problems", "representative_issues", "limitations"]
    if any(not isinstance(result.get(field), list) or not all(isinstance(item, str) for item in result[field]) for field in fields):
        raise RuntimeError("Issue analysis returned malformed fields.")
    return {"analyzed_issue_count": expected, **{field: result[field] for field in fields}}


def select_asset(model: LanguageModel, release: dict[str, Any], request: dict[str, str]) -> dict[str, Any]:
    result = model.json(
        "Choose the most suitable maintainer-uploaded release asset for the preferences. Assets provided are maintainer-uploaded; source archive URLs are intentionally excluded and must not be suggested as installable software. Return {\"found\": boolean, \"asset_name\": string or null, \"reason\": string}. Set found true only if asset_name is exactly one supplied asset name and the filename/metadata provides a defensible compatibility match. Prefer no match when the evidence is insufficient.",
        {"release_assets": release["assets"], "request": request},
    )
    found, name, reason = result.get("found"), result.get("asset_name"), result.get("reason")
    if not isinstance(found, bool) or not isinstance(reason, str):
        raise RuntimeError("Asset selection returned malformed fields.")
    assets_by_name = {asset["name"]: asset for asset in release["assets"]}
    if found:
        if not isinstance(name, str) or name not in assets_by_name:
            raise RuntimeError("Asset selection chose an asset not supplied by the Release.")
        return {"found": True, "asset": assets_by_name[name], "reason": reason}
    return {"found": False, "reason": reason}


def release_advice_for_overview(model: LanguageModel, release: dict[str, Any]) -> dict[str, Any]:
    summary = model.text(
        "Create a latest official Release overview including version, release name, publication time, key Release Notes, and Asset count. Explicitly state that no file operation was performed.",
        release,
    )
    if "no file" not in summary.lower():
        summary += "\n\nNo file operation was performed."
    return {"status": "overview", "version": release["version"], "summary": summary, "acquisition_url": "", "integrity_guidance": "Review the maintainer-provided release metadata and any published checksums before obtaining an asset yourself.", "limitations": ["Only the latest official public Release was analyzed.", "No file was downloaded, created, installed, extracted, or executed."]}


def release_advice_for_match(model: LanguageModel, selection: dict[str, Any], release: dict[str, Any], request: dict[str, str]) -> dict[str, Any]:
    text = model.text(
        "Create compatibility guidance from the selected asset result. If an asset is found, include its exact name, byte size, URL, digest when available, and the compatibility rationale. If no asset is found, explain why. Give user-side verification guidance. Explicitly state that no file was downloaded, created, installed, extracted, or executed.",
        {"selection": selection, "release": release, "request": request},
    )
    no_operations = "No file was downloaded, created, installed, extracted, or executed."
    if "no file" not in text.lower():
        text += "\n\n" + no_operations
    if selection["found"]:
        asset = selection["asset"]
        return {"status": "recommended", "version": release["version"], "asset": asset, "summary": text, "acquisition_url": asset["download_url"], "integrity_guidance": "Before obtaining it yourself, compare the published digest/checksum with the downloaded file using a local checksum tool; a missing digest means independent verification information was not supplied here.", "limitations": ["Compatibility is inferred from published asset metadata and filename conventions.", "Only the latest official public Release was analyzed.", no_operations]}
    return {"status": "no_match", "version": release["version"], "summary": text, "acquisition_url": "", "integrity_guidance": "Do not treat source ZIP or source TAR archives as directly installable software by default. Consult the project documentation before choosing an alternative.", "limitations": ["No maintainer-uploaded asset could be defensibly matched to the supplied preferences.", "Only the latest official public Release was analyzed.", no_operations]}


def display_result(value: Any) -> None:
    if isinstance(value, str):
        print(value)
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2))


def project_navigator() -> dict[str, Any]:
    """Execute the ProjectNavigator entry Worker and return its declared outputs."""
    state: dict[str, Any] = {"repository_input_retry_count": 0, "repository_input_limit_exceeded": False, "repository_found": False, "project_summary": "No project summary is available because the target Repository was not resolved."}
    print("Provide a complete GitHub Repository URL or an explicit owner/repository identifier. I can summarize public project information, analyze recently updated open Issues, and provide latest Release guidance without downloading files.")
    state["project_input"] = read_input("Enter the GitHub Repository URL or owner/repository identifier:")
    state["input_kind"] = classify_repository_input(state["project_input"])

    # Alternative Flow: each pass below corresponds to one retry INPUT command.
    while state["input_kind"] == "unclear" and state["repository_input_retry_count"] < 3:
        state["project_input"] = read_input("That input does not uniquely identify a Repository. Enter a complete GitHub Repository URL or explicit owner/repository identifier:")
        state["repository_input_retry_count"] += 1
        state["input_kind"] = classify_repository_input(state["project_input"])
    state["repository_input_limit_exceeded"] = state["input_kind"] == "unclear" and state["repository_input_retry_count"] >= 3
    if state["repository_input_limit_exceeded"]:
        LOGGER.info("The Repository input remains unclear after three correction attempts")
        model = LanguageModel()
        state["project_summary"] = model.text("Create a brief termination explanation stating that the target Repository could not be determined. State that GitHub was not accessed and no Issue or Release analysis was performed.", {})
        display_result(state["project_summary"])
        return {"project_summary": state["project_summary"]}

    state["selected_repository"] = parse_github_repository_input(state["project_input"])
    state["project_overview"] = get_github_project_overview(**{key: state["selected_repository"][key] for key in ("owner", "repository")})
    state["repository_found"] = state["project_overview"]["found"]
    model = LanguageModel()
    if not state["repository_found"]:
        state["project_summary"] = not_found_summary(model, state["selected_repository"])
        display_result(state["project_summary"])
        return {"project_summary": state["project_summary"]}

    state["project_summary"] = project_summary(model, state["project_overview"])
    display_result(state["project_summary"])
    state["issue_analysis_choice"] = normalize_yes_no(model, read_input("Would you like an analysis of recently updated open Issues? (yes/no)"), "Would you like an analysis of recently updated open Issues?")
    if state["issue_analysis_choice"] == "yes":
        issue_information = get_github_issue_information(state["selected_repository"]["owner"], state["selected_repository"]["repository"])
        state["issue_analysis_result"] = analyze_issues(model, issue_information)

    state["release_analysis_choice"] = normalize_yes_no(model, read_input("Would you like guidance about the latest official Release? (yes/no)"), "Would you like guidance about the latest official Release?")
    if state["release_analysis_choice"] == "yes":
        state["release_request"] = parse_release_request(read_input("Enter 'overview' or exactly 'asset_match;operating_system;architecture;package_preference' (windows|macos|linux|other; x64|arm64|unknown; installer|portable|archive|any):"))
        release = get_github_release(state["selected_repository"]["owner"], state["selected_repository"]["repository"])
        if state["release_request"]["analysis_mode"] == "overview":
            state["release_advice"] = release_advice_for_overview(model, release)
        else:
            selection = select_asset(model, release, state["release_request"])
            state["release_advice"] = release_advice_for_match(model, selection, release, state["release_request"])

    print("\nFinal result:")
    display_result(state["project_summary"])
    if state["issue_analysis_choice"] == "yes":
        display_result(state["issue_analysis_result"])
    if state["release_analysis_choice"] == "yes":
        display_result(state["release_advice"])
    result = {"project_summary": state["project_summary"]}
    if "issue_analysis_result" in state:
        result["issue_analysis_result"] = state["issue_analysis_result"]
    if "release_advice" in state:
        result["release_advice"] = state["release_advice"]
    return result


def main() -> dict[str, Any]:
    """Initialize the Agent, execute its entry Worker, and return final results."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        return project_navigator()
    except Exception as exc:
        print(f"Execution failed: {exc}", file=sys.stdout)
        return {"error": str(exc)}


if __name__ == "__main__":
    main()
