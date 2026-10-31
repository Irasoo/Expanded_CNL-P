from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen


PERSONA = (
    "You are a cautious and evidence-based assistant for GitHub project "
    "information, Issue risks, and Release compatibility. Confirm the target "
    "Repository, summarize public metadata and README content, analyze recent "
    "open Issues, and provide either a latest Release overview or asset "
    "compatibility guidance. Do not guess repositories or modify GitHub."
)
AUDIENCE = (
    "The users are developers and software users. They can provide a complete "
    "GitHub Repository URL or an explicit owner/repository identifier. Use clear "
    "English and distinguish repository facts, limited Issue-sample analysis, "
    "Release summaries, and asset compatibility guidance."
)
CONCEPTS = (
    "Repository means a project uniquely identified by owner and repository. "
    "Issue insight means repeated, confirmed, and unresolved concerns from "
    "recently updated open Issues. A Release is the latest official public "
    "GitHub Release. A Release Asset is maintainer-uploaded; GitHub-generated "
    "source archives are not installable software by default."
)
CONSTRAINTS = (
    "Require an explicit repository; never infer one from a vague description. "
    "Read GitHub only. Never download, create, overwrite, move, extract, "
    "install, or execute Release files. Do not judge quality from Stars or open "
    "Issue count alone. Do not generalize one Issue into a project-wide problem. "
    "State the actual Issue sample size and scope. Network, authentication, "
    "rate-limit, service, and malformed-response failures are execution failures."
)


def load_local_env() -> None:
    """Load simple KEY=VALUE entries without adding a dotenv dependency."""
    path = ".env"
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
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


class ExecutionFailure(RuntimeError):
    pass


class RuntimeLLM:
    def __init__(self) -> None:
        load_local_env()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        base_url = os.getenv("BASE_URL", "").strip()
        model = (
            os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip()
            or os.getenv("OPENAI_MODEL", "").strip()
        )
        if not api_key:
            raise ExecutionFailure(
                "OPENAI_API_KEY is not configured in .env or the environment."
            )
        if not model:
            raise ExecutionFailure(
                "CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL must be configured."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ExecutionFailure(
                "The official OpenAI Python Client is required: pip install openai."
            ) from exc
        client_args: dict[str, str] = {"api_key": api_key}
        if base_url:
            client_args["base_url"] = base_url
        self.client = OpenAI(**client_args)
        self.model = model

    def json(self, instruction: str, payload: Any) -> dict[str, Any]:
        prompt = (
            f"{PERSONA}\nAudience: {AUDIENCE}\nConcepts: {CONCEPTS}\n"
            f"Constraints: {CONSTRAINTS}\n\n{instruction}\n\nInput JSON:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
        try:
            response = self.client.responses.create(
                model=self.model,
                reasoning={"effort": "high"},
                input=prompt,
                text={"format": {"type": "json_object"}},
            )
            raw = response.output_text
            value = json.loads(raw)
        except Exception as exc:
            raise ExecutionFailure(
                f"Runtime language-model call failed: {type(exc).__name__}: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise ExecutionFailure("Runtime language model returned non-object JSON.")
        return value


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


def _read_json(url: str, *, headers: dict[str, str] | None = None) -> Any:
    try:
        request = Request(url, headers=headers or _github_headers(), method="GET")
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ExecutionFailure(f"GitHub request returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise ExecutionFailure(
            f"GitHub request failed: {type(exc).__name__}: {exc}"
        ) from exc


def parse_github_repository_input(project_input: str) -> dict[str, str]:
    """Convert exactly one explicit GitHub repository input to canonical fields."""
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
        raise ValueError("Input must identify exactly one owner and repository.")
    owner, repository = parts
    if repository.lower().endswith(".git"):
        repository = repository[:-4]
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", owner):
        raise ValueError("GitHub owner name is invalid.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", repository):
        raise ValueError("GitHub repository name is invalid.")
    return {
        "owner": owner,
        "repository": repository,
        "repository_url": f"https://github.com/{owner}/{repository}",
    }


def get_github_project_overview(owner: str, repository: str) -> dict[str, Any]:
    owner_value, repository_value = str(owner).strip(), str(repository).strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner_value or "") or not re.fullmatch(
        r"[A-Za-z0-9_.-]+", repository_value or ""
    ):
        raise ValueError("Invalid GitHub owner or repository name.")

    empty = {
        "found": False, "full_name": "", "repository_url": "", "description": "",
        "readme": "", "license": "", "primary_language": "", "topics": [],
        "stars": 0, "forks": 0, "open_issues": 0, "archived": False, "updated_at": "",
    }
    api_url = f"https://api.github.com/repos/{quote(owner_value)}/{quote(repository_value)}"
    headers = _github_headers()
    try:
        metadata = _read_json(api_url, headers=headers)
    except ExecutionFailure as exc:
        if "HTTP 404" in str(exc):
            return empty
        raise
    if not isinstance(metadata, dict):
        raise ExecutionFailure("GitHub returned malformed repository metadata.")
    readme_headers = dict(headers)
    readme_headers["Accept"] = "application/vnd.github.raw+json"
    readme = ""
    try:
        request = Request(api_url + "/readme", headers=readme_headers, method="GET")
        with urlopen(request, timeout=30) as response:
            readme = response.read(50001).decode("utf-8", errors="replace")[:50000]
    except HTTPError as exc:
        if exc.code != 404:
            raise ExecutionFailure(f"GitHub README lookup returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ExecutionFailure(f"GitHub README could not be read: {exc}") from exc
    license_data = metadata.get("license")
    license_name = (
        str(license_data.get("spdx_id") or license_data.get("name") or "")
        if isinstance(license_data, dict) else ""
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
        "forks": int(metadata.get("forks") or 0),
        "open_issues": int(metadata.get("open_issues_count") or 0),
        "archived": bool(metadata.get("archived", False)),
        "updated_at": str(metadata.get("updated_at") or ""),
    }


def get_github_issue_information(owner: str, repository: str) -> dict[str, Any]:
    if not str(owner).strip() or not str(repository).strip():
        raise ValueError("GitHub owner and repository are required.")
    url = (
        f"https://api.github.com/repos/{quote(str(owner).strip())}/{quote(str(repository).strip())}/issues?"
        + urlencode({"state": "open", "sort": "updated", "direction": "desc", "per_page": 100, "page": 1})
    )
    payload = _read_json(url)
    if not isinstance(payload, list):
        raise ExecutionFailure("GitHub returned malformed Issue data.")
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
    url = f"https://api.github.com/repos/{quote(str(owner).strip())}/{quote(str(repository).strip())}/releases/latest"
    selected = _read_json(url)
    if not isinstance(selected, dict):
        raise ExecutionFailure("GitHub returned malformed Release data.")
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


def _require_choice(value: Any, field_name: str, choices: set[str]) -> str:
    normalized = str(value).strip().lower()
    if normalized not in choices:
        raise ExecutionFailure(f"Model returned invalid {field_name}: {normalized!r}.")
    return normalized


def classify_repository_input(llm: RuntimeLLM, value: str) -> str:
    result = llm.json(
        "Classify the single user input as exactly one of repository_url, repository_name, unclear. "
        "A URL must be a complete GitHub repository URL. A repository_name must be an explicit "
        "owner/repository identifier. Do not guess. Return JSON {\"input_kind\": string}.",
        {"project_input": value},
    )
    return _require_choice(result.get("input_kind"), "input_kind", {"repository_url", "repository_name", "unclear"})


def parse_yes_no(llm: RuntimeLLM, value: str, question: str) -> str:
    result = llm.json(
        f"Interpret the one user answer to this question: {question!r}. Return JSON {{\"choice\": \"yes\" or \"no\"}}. "
        "If the answer is ambiguous, return neither by using \"unclear\".",
        {"answer": value},
    )
    return _require_choice(result.get("choice"), "choice", {"yes", "no"})


def make_project_summary(llm: RuntimeLLM, overview: dict[str, Any]) -> str:
    result = llm.json(
        "Write a clear English project overview from the supplied facts. Cover project name, purpose, "
        "core capabilities, typical use cases, intended users, primary technology, execution or "
        "installation entry points, license, maintenance status, and important README limitations. "
        "Do not merely copy README. Do not infer unsupported facts or judge quality from Stars/open Issue count. "
        "Return JSON {\"summary\": string}.",
        overview,
    )
    summary = result.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ExecutionFailure("Model returned an empty project summary.")
    return summary.strip()


def analyze_issues(llm: RuntimeLLM, info: dict[str, Any]) -> dict[str, Any]:
    result = llm.json(
        "Analyze only the supplied recently updated open Issue sample. Distinguish repeated concerns, "
        "isolated reports, maintainer-confirmed problems, and unresolved reports. Select a small set of "
        "representative Issues. Record the exact analyzed_issue_count from input, state limitations of this "
        "limited sample, and never turn one report into a general problem. Return JSON with exactly these "
        "fields: analyzed_issue_count number, common_problems list of strings, confirmed_problems list of "
        "strings, unresolved_problems list of strings, representative_issues list of strings, limitations list of strings.",
        info,
    )
    count = int(info.get("analyzed_issue_count") or 0)
    result["analyzed_issue_count"] = count
    for key in ("common_problems", "confirmed_problems", "unresolved_problems", "representative_issues", "limitations"):
        if not isinstance(result.get(key), list) or not all(isinstance(item, str) for item in result[key]):
            raise ExecutionFailure(f"Model returned malformed Issue analysis field: {key}.")
    return result


def parse_release_request(value: str) -> dict[str, Any]:
    raw = value.strip()
    if raw == "overview":
        return {"analysis_mode": "overview"}
    parts = raw.split(";")
    if len(parts) != 4:
        raise ValueError("ReleaseRequest must be overview or four semicolon-separated values.")
    mode, operating_system, architecture, package_preference = [part.strip().lower() for part in parts]
    if mode != "asset_match":
        raise ValueError("The asset_match format must start with asset_match.")
    if operating_system not in {"windows", "macos", "linux", "other"}:
        raise ValueError("Invalid operating_system in ReleaseRequest.")
    if architecture not in {"x64", "arm64", "unknown"}:
        raise ValueError("Invalid architecture in ReleaseRequest.")
    if package_preference not in {"installer", "portable", "archive", "any"}:
        raise ValueError("Invalid package_preference in ReleaseRequest.")
    return {"analysis_mode": mode, "operating_system": operating_system, "architecture": architecture, "package_preference": package_preference}


def select_asset(llm: RuntimeLLM, request: dict[str, Any], release: dict[str, Any]) -> dict[str, Any]:
    result = llm.json(
        "Select the most suitable maintainer-uploaded Release Asset for the exact platform preferences. "
        "Do not select source_zip_url/source_tar_url or describe them as installable. Consider filename "
        "signals, operating system, architecture, and package preference, but do not invent compatibility. "
        "Return JSON {\"found\": boolean, \"asset_name\": string, \"reason\": string}. asset_name must "
        "exactly match a supplied asset name when found, otherwise be empty.",
        {"release_request": request, "assets": release.get("assets", [])},
    )
    found = bool(result.get("found"))
    name = str(result.get("asset_name") or "")
    assets = release.get("assets", [])
    chosen = next((asset for asset in assets if isinstance(asset, dict) and asset.get("name") == name), None)
    if found and chosen is None:
        raise ExecutionFailure("Model selected an asset that was not in the Release response.")
    if not found:
        chosen = None
    return {"found": bool(chosen), "asset": chosen, "reason": str(result.get("reason") or "")}


def make_release_advice(llm: RuntimeLLM, request: dict[str, Any], release: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    if request["analysis_mode"] == "overview":
        result = llm.json(
            "Create an English overview of the latest official Release using only the facts supplied. Include "
            "version, name, publication time, key release notes, and asset count. State explicitly that no file "
            "operation was performed. Return JSON {\"summary\": string}.", release,
        )
        return {
            "status": "overview", "version": release["version"], "summary": str(result.get("summary") or ""),
            "acquisition_url": "", "integrity_guidance": "", "limitations": [],
        }
    asset = selection.get("asset")
    if asset:
        summary = (
            f"Recommended asset: {asset['name']} ({asset['size']} bytes). {selection['reason']} "
            f"Download URL: {asset['download_url']}."
        )
        integrity = (
            f"Verify the downloaded file against the Release digest before use: {asset['digest'] or 'GitHub provided no digest.'} "
            "Follow the project maintainer's verification instructions."
        )
        status = "recommended"
        acquisition_url = asset["download_url"]
    else:
        summary = f"No compatible maintainer-uploaded asset was identified. {selection['reason']}"
        integrity = "No asset was selected, so no file verification guidance can be provided."
        status = "no_match"
        acquisition_url = ""
    limitations = [
        "Compatibility was inferred from the Release asset metadata and filename signals only; verify the project's requirements.",
        "No file was downloaded, created, installed, extracted, or executed.",
    ]
    return {
        "status": status, "version": release["version"], "asset": asset, "summary": summary,
        "acquisition_url": acquisition_url, "integrity_guidance": integrity, "limitations": limitations,
    }


@dataclass
class AgentState:
    project_input: str = ""
    input_kind: str = "unclear"
    repository_input_retry_count: int = 0
    repository_input_limit_exceeded: bool = False
    selected_repository: dict[str, str] = field(default_factory=dict)
    project_overview: dict[str, Any] = field(default_factory=dict)
    repository_found: bool = False
    project_summary: str = "No project summary is available because the target Repository was not resolved."
    issue_analysis_choice: str = "no"
    issue_information: dict[str, Any] = field(default_factory=dict)
    issue_analysis_result: dict[str, Any] | None = None
    release_analysis_choice: str = "no"
    release_request: dict[str, Any] = field(default_factory=dict)
    release_information: dict[str, Any] = field(default_factory=dict)
    asset_selection: dict[str, Any] = field(default_factory=dict)
    release_advice: dict[str, Any] | None = None


class ProjectNavigator:
    def __init__(self, llm: RuntimeLLM, display: Callable[[str], None], read_input: Callable[[str], str]) -> None:
        self.llm, self.display, self.read_input = llm, display, read_input

    def run(self) -> AgentState:
        state = AgentState()
        self.display(
            "This assistant requires a complete GitHub Repository URL or an explicit owner/repository identifier. "
            "It can summarize public project information, analyze recent open Issues, and provide Release guidance "
            "without downloading files."
        )
        state.project_input = self.read_input("GitHub Repository URL or owner/repository: ")
        state.input_kind = classify_repository_input(self.llm, state.project_input)
        while state.input_kind == "unclear" and state.repository_input_retry_count < 3:
            state.project_input = self.read_input(
                "The input does not uniquely identify a Repository. Enter a complete GitHub Repository URL or owner/repository: "
            )
            state.repository_input_retry_count += 1
            state.input_kind = classify_repository_input(self.llm, state.project_input)
        state.repository_input_limit_exceeded = state.input_kind == "unclear" and state.repository_input_retry_count >= 3
        if state.repository_input_limit_exceeded:
            print("LOG: The Repository input remains unclear after three correction attempts", file=sys.stderr)
            state.project_summary = (
                "The target Repository could not be determined after three correction attempts. "
                "GitHub was not accessed, and no Issue or Release analysis was performed."
            )
            self.display(state.project_summary)
            return state
        state.selected_repository = parse_github_repository_input(state.project_input)
        state.project_overview = get_github_project_overview(
            state.selected_repository["owner"], state.selected_repository["repository"]
        )
        state.repository_found = bool(state.project_overview.get("found"))
        if not state.repository_found:
            state.project_summary = (
                f"The explicitly identified Repository {state.selected_repository['owner']}/{state.selected_repository['repository']} "
                "was not found on GitHub. This is a repository-not-found result, not a network, authentication, "
                "rate-limit, or service failure."
            )
            self.display(state.project_summary)
            return state
        state.project_summary = make_project_summary(self.llm, state.project_overview)
        self.display(state.project_summary)
        state.issue_analysis_choice = parse_yes_no(self.llm, self.read_input("Analyze recently updated open Issues? (yes/no): "), "whether to analyze Issues")
        if state.issue_analysis_choice == "yes":
            state.issue_information = get_github_issue_information(state.selected_repository["owner"], state.selected_repository["repository"])
            state.issue_analysis_result = analyze_issues(self.llm, state.issue_information)
        state.release_analysis_choice = parse_yes_no(self.llm, self.read_input("Provide guidance about the latest official Release? (yes/no): "), "whether to provide Release guidance")
        if state.release_analysis_choice == "yes":
            state.release_request = parse_release_request(self.read_input("Release request (overview or asset_match;operating_system;architecture;package_preference): "))
            state.release_information = get_github_release(state.selected_repository["owner"], state.selected_repository["repository"])
            state.asset_selection = select_asset(self.llm, state.release_request, state.release_information) if state.release_request["analysis_mode"] == "asset_match" else {}
            state.release_advice = make_release_advice(self.llm, state.release_request, state.release_information, state.asset_selection)
        self.display_final(state)
        return state

    def display_final(self, state: AgentState) -> None:
        self.display("\nFinal result\n" + state.project_summary)
        if state.issue_analysis_choice == "yes" and state.issue_analysis_result is not None:
            self.display(json.dumps(state.issue_analysis_result, ensure_ascii=False, indent=2))
        if state.release_analysis_choice == "yes" and state.release_advice is not None:
            self.display(json.dumps(state.release_advice, ensure_ascii=False, indent=2))


def main() -> AgentState:
    """Initialize the Agent, execute its entry Worker, and return final state."""
    try:
        llm = RuntimeLLM()
        worker = ProjectNavigator(llm, print, input)
        return worker.run()
    except (ExecutionFailure, ValueError) as exc:
        print(f"Execution failed: {exc}", file=sys.stderr)
        return AgentState(project_summary=f"Execution failed: {exc}")


if __name__ == "__main__":
    main()
