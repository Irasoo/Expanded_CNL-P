from __future__ import annotations

import json
import os
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

def _read_dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = os.path.join(os.getcwd(), ".env")
    try:
        with open(env_path, "r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                    value = value[1:-1]
                values[key] = value
    except FileNotFoundError:
        pass
    return values


def _setting(name: str, dotenv: dict[str, str]) -> str:
    return os.environ.get(name, dotenv.get(name, "")).strip()


def parse_github_repository_input(project_input: str) -> dict[str, str]:
    """Convert one explicit GitHub repository URL or owner/repository to canonical fields."""
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


class GitHubClient:
    def __init__(self) -> None:
        dotenv = _read_dotenv()
        self.token = _setting("GITHUB_TOKEN", dotenv)
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "cnlp-github-project-assistant",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def _get_json(self, url: str, context: str) -> Any:
        try:
            request = Request(url, headers=self.headers, method="GET")
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"GitHub {context} lookup returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"GitHub {context} could not be read: {type(exc).__name__}: {exc}"
            ) from exc

    def get_project_overview(self, owner: str, repository: str) -> dict[str, object]:
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

        empty = {
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
            metadata = self._get_json(base_url, "repository metadata")
        except RuntimeError as exc:
            if "HTTP 404" in str(exc):
                return empty
            raise
        if not isinstance(metadata, dict):
            raise RuntimeError("GitHub returned malformed repository metadata.")

        readme = ""
        readme_headers = dict(self.headers)
        readme_headers["Accept"] = "application/vnd.github.raw+json"
        try:
            request = Request(base_url + "/readme", headers=readme_headers, method="GET")
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

    def get_issue_information(self, owner: str, repository: str) -> dict[str, object]:
        if not str(owner).strip() or not str(repository).strip():
            raise ValueError("GitHub owner and repository are required.")
        url = (
            "https://api.github.com/repos/"
            f"{quote(str(owner).strip(), safe='')}/{quote(str(repository).strip(), safe='')}"
            "/issues?"
            + urlencode({
                "state": "open", "sort": "updated", "direction": "desc",
                "per_page": 100, "page": 1,
            })
        )
        payload = self._get_json(url, "Issue")
        if not isinstance(payload, list):
            raise RuntimeError("GitHub returned malformed Issue data.")
        issues: list[str] = []
        for item in payload:
            if not isinstance(item, dict) or "pull_request" in item:
                continue
            raw_labels = item.get("labels", [])
            labels = (
                [str(label["name"]) for label in raw_labels
                 if isinstance(label, dict) and label.get("name")]
                if isinstance(raw_labels, list) else []
            )
            body = str(item.get("body") or "")[:4000]
            issues.append("\n".join([
                f"#{int(item.get('number') or 0)}: {str(item.get('title') or '')}",
                f"URL: {item.get('html_url') or ''}",
                f"State: {item.get('state') or ''}",
                f"Updated at: {item.get('updated_at') or ''}",
                f"Comments: {int(item.get('comments') or 0)}",
                f"Labels: {', '.join(labels) if labels else 'none'}",
                f"Body: {body}",
            ]))
        return {"analyzed_issue_count": len(issues), "issues": issues}

    def get_release(self, owner: str, repository: str) -> dict[str, object]:
        if not str(owner).strip() or not str(repository).strip():
            raise ValueError("GitHub owner and repository are required.")
        url = (
            "https://api.github.com/repos/"
            f"{quote(str(owner).strip(), safe='')}/{quote(str(repository).strip(), safe='')}"
            "/releases/latest"
        )
        selected = self._get_json(url, "Release")
        if not isinstance(selected, dict):
            raise RuntimeError("GitHub returned malformed Release data.")
        raw_assets = selected.get("assets", [])
        assets = (
            [{
                "name": str(asset.get("name") or ""),
                "download_url": str(asset.get("browser_download_url") or ""),
                "size": int(asset.get("size") or 0),
                "digest": str(asset.get("digest") or ""),
            } for asset in raw_assets if isinstance(asset, dict)]
            if isinstance(raw_assets, list) else []
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


class LanguageModel:
    def __init__(self) -> None:
        from openai import OpenAI

        dotenv = _read_dotenv()
        api_key = _setting("OPENAI_API_KEY", dotenv)
        base_url = _setting("BASE_URL", dotenv)
        model = _setting("CNLP_REFERENCE_LLM_MODEL", dotenv) or _setting("OPENAI_MODEL", dotenv)
        missing = [name for name, value in {
            "OPENAI_API_KEY": api_key,
            "BASE_URL": base_url,
            "CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL": model,
        }.items() if not value]
        if missing:
            raise RuntimeError("Missing runtime model configuration: " + ", ".join(missing) + ".")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def json_response(self, system: str, user: str) -> dict[str, Any]:
        try:
            response = self.client.responses.create(
                model=self.model,
                reasoning={"effort": "high"},
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                text={"format": {"type": "json_object"}},
            )
            raw = response.output_text
        except Exception as exc:
            raise RuntimeError(
                f"Runtime language-model call failed: {type(exc).__name__}: {exc}"
            ) from exc
        if not isinstance(raw, str) or not raw.strip():
            raise RuntimeError("Runtime language model returned an empty response.")
        cleaned = raw.strip()
        if cleaned.startswith("\`\`\`"):
            cleaned = re.sub(
                r"^\`\`\`(?:json)?\s*|\s*\`\`\`$", "", cleaned, flags=re.IGNORECASE
            )
        try:
            value = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Runtime language model returned malformed JSON.") from exc
        if not isinstance(value, dict):
            raise RuntimeError("Runtime language model returned a JSON value instead of an object.")
        return value


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise RuntimeError(f"Model response field '{field}' must be text.")
    return value


def _require_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError(f"Model response field '{field}' must be a list of text.")
    return value


def interpret_yes_no(model: LanguageModel, answer: str) -> str:
    result = model.json_response(
        """Interpret the user's answer to a yes-or-no question. Understand ordinary natural-language answers,
including concise answers in English or another language. Return only JSON with exactly one field:
{"choice":"yes"} or {"choice":"no"}. Do not infer a choice from missing information.""",
        answer,
    )
    choice = result.get("choice")
    if choice not in {"yes", "no"}:
        raise RuntimeError("The language model did not return a valid yes/no choice.")
    return choice


def create_project_summary(model: LanguageModel, overview: dict[str, object]) -> str:
    result = model.json_response(
        """You are ProjectNavigator. Write a clear, evidence-based English project overview from the supplied
public GitHub data. Cover project name, purpose, core capabilities, typical use cases, intended users,
primary technology, execution or installation entry points, license, maintenance status, and important
README limitations. Synthesize rather than copy the README. Do not judge quality from stars or open issue
count alone. Return JSON exactly as {"project_summary":"..."}. Do not invent facts.""",
        json.dumps(overview, ensure_ascii=False),
    )
    return _require_text(result.get("project_summary"), "project_summary")


def analyze_issues(model: LanguageModel, issue_information: dict[str, object]) -> dict[str, object]:
    result = model.json_response(
        """You are the independent IssueAnalyzer. Analyze only the supplied recently updated open Issue sample.
Distinguish repeated concerns from isolated reports, maintainer-confirmed problems, and unresolved reports.
Select a small representative set using issue numbers or concise titles. State the exact analyzed count and
what this limited sample cannot establish. Never describe one report as a general project problem. Return
JSON with exactly these fields: analyzed_issue_count (number), common_problems (text list),
confirmed_problems (text list), unresolved_problems (text list), representative_issues (text list),
limitations (text list). Use only evidence in the input.""",
        json.dumps(issue_information, ensure_ascii=False),
    )
    count = result.get("analyzed_issue_count")
    if not isinstance(count, int) or isinstance(count, bool):
        raise RuntimeError("Model response field 'analyzed_issue_count' must be a number.")
    if count != issue_information["analyzed_issue_count"]:
        raise RuntimeError("Issue analysis count does not match the retrieved Issue sample.")
    return {
        "analyzed_issue_count": count,
        "common_problems": _require_list(result.get("common_problems"), "common_problems"),
        "confirmed_problems": _require_list(result.get("confirmed_problems"), "confirmed_problems"),
        "unresolved_problems": _require_list(result.get("unresolved_problems"), "unresolved_problems"),
        "representative_issues": _require_list(result.get("representative_issues"), "representative_issues"),
        "limitations": _require_list(result.get("limitations"), "limitations"),
    }


def parse_release_request(answer: str) -> dict[str, str]:
    value = answer.strip()
    if value == "overview":
        return {"analysis_mode": "overview"}
    fields = value.split(";")
    if len(fields) != 4 or fields[0] != "asset_match":
        raise ValueError("Release request must be 'overview' or the exact four-field asset_match format.")
    operating_system, architecture, package_preference = fields[1:]
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


def select_asset(model: LanguageModel, release: dict[str, object], request: dict[str, str]) -> dict[str, object]:
    result = model.json_response(
        """You are the independent ReleaseAdvisor asset selector. Choose the most suitable maintainer-uploaded
release asset for the exact platform preferences, or choose no asset. Automatically generated GitHub source
archives are not installable assets by default and are not in the candidate list. Return JSON exactly as
{"found":true,"asset_name":"exact candidate name","reason":"..."} or
{"found":false,"asset_name":null,"reason":"..."}. Never invent an asset name.""",
        json.dumps({"release": release, "request": request}, ensure_ascii=False),
    )
    found = result.get("found")
    reason = _require_text(result.get("reason"), "reason")
    asset_name = result.get("asset_name")
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        raise RuntimeError("Release assets are malformed.")
    by_name = {item.get("name"): item for item in assets if isinstance(item, dict)}
    if found is True:
        if not isinstance(asset_name, str) or asset_name not in by_name:
            raise RuntimeError("Model selected an Asset that was not returned by GitHub.")
        return {"found": True, "reason": reason, "asset": by_name[asset_name]}
    if found is False:
        return {"found": False, "reason": reason}
    raise RuntimeError("Model response field 'found' must be boolean.")


def create_release_advice(
    model: LanguageModel,
    release: dict[str, object],
    request: dict[str, str],
    selection: dict[str, object] | None,
) -> dict[str, object]:
    overview_mode = request["analysis_mode"] == "overview"
    system = """You are the independent ReleaseAdvisor. Write clear English release guidance from only the supplied
latest official GitHub Release data. Do not download, create, install, extract, or execute any file. For
overview mode set status to 'overview'. For asset matching, set status to 'recommended' only when the
selection found an exact maintainer-uploaded Asset; otherwise set 'no_match'. Include version, summary,
acquisition_url, integrity_guidance, and limitations. Include the exact asset object only when recommended.
Return JSON with fields status, version, summary, acquisition_url, integrity_guidance, limitations (text list),
and optional asset with name, download_url, digest, size. Source archives must not be presented as directly
installable software by default."""
    result = model.json_response(system, json.dumps({
        "release": release, "request": request, "asset_selection": selection,
    }, ensure_ascii=False))
    status = result.get("status")
    expected = "overview" if overview_mode else (
        "recommended" if selection and selection.get("found") else "no_match"
    )
    if status != expected:
        raise RuntimeError(f"Model response status must be '{expected}'.")
    advice: dict[str, object] = {
        "status": status,
        "version": _require_text(result.get("version"), "version"),
        "summary": _require_text(result.get("summary"), "summary"),
        "acquisition_url": _require_text(result.get("acquisition_url"), "acquisition_url"),
        "integrity_guidance": _require_text(result.get("integrity_guidance"), "integrity_guidance"),
        "limitations": _require_list(result.get("limitations"), "limitations"),
    }
    if status == "recommended":
        selected_asset = selection.get("asset") if selection else None
        returned_asset = result.get("asset")
        if not isinstance(selected_asset, dict) or not isinstance(returned_asset, dict):
            raise RuntimeError("Recommended Release advice must include the selected Asset.")
        if returned_asset.get("name") != selected_asset.get("name"):
            raise RuntimeError("Release advice Asset does not match the selected Asset.")
        advice["asset"] = selected_asset
    return advice


def _print_json(label: str, value: object) -> None:
    print(f"\n{label}")
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> dict[str, object]:
    project_input = ""
    input_kind = "unclear"
    repository_input_retry_count = 0
    repository_input_limit_exceeded = False
    selected_repository: dict[str, str] | None = None
    project_overview: dict[str, object] | None = None
    project_summary = "No project summary is available because the target Repository was not resolved."
    issue_analysis_choice = "no"
    release_analysis_choice = "no"
    issue_analysis_result: dict[str, object] | None = None
    release_advice: dict[str, object] | None = None

    print("GitHubProjectAssistant")
    print(
        "I need a complete GitHub Repository URL or an explicit owner/repository identifier. "
        "I can summarize public project information, analyze recent open Issues, and provide "
        "Release guidance without downloading files."
    )
    project_input = input("Enter the GitHub Repository URL or owner/repository: ")
    try:
        parse_github_repository_input(project_input)
        input_kind = "repository_url" if "://" in project_input.strip() else "repository_name"
    except ValueError:
        input_kind = "unclear"

    while input_kind == "unclear" and repository_input_retry_count < 3:
        print("The current input does not uniquely identify a Repository.")
        project_input = input(
            "Enter a complete GitHub Repository URL or an explicit owner/repository identifier: "
        )
        repository_input_retry_count += 1
        try:
            parse_github_repository_input(project_input)
            input_kind = "repository_url" if "://" in project_input.strip() else "repository_name"
        except ValueError:
            input_kind = "unclear"

    repository_input_limit_exceeded = input_kind == "unclear" and repository_input_retry_count >= 3
    if repository_input_limit_exceeded:
        diagnostic = "The Repository input remains unclear after three correction attempts."
        project_summary = "The target Repository could not be determined. " + diagnostic
        print(diagnostic)
        print(project_summary)
        print("GitHub was not accessed, and no Issue or Release analysis was performed.")
        return {"project_summary": project_summary}

    selected_repository = parse_github_repository_input(project_input)
    github = GitHubClient()
    project_overview = github.get_project_overview(
        selected_repository["owner"], selected_repository["repository"]
    )
    repository_found = bool(project_overview["found"])
    if not repository_found:
        project_summary = (
            f"The explicitly identified Repository {selected_repository['owner']}/"
            f"{selected_repository['repository']} was not found on GitHub."
        )
        print(project_summary)
        return {"project_summary": project_summary}

    model = LanguageModel()
    project_summary = create_project_summary(model, project_overview)
    print(project_summary)

    issue_analysis_choice = interpret_yes_no(
        model,
        input("Would you like an analysis of recently updated open Issues? "),
    )
    if issue_analysis_choice == "yes":
        issue_information = github.get_issue_information(
            selected_repository["owner"], selected_repository["repository"]
        )
        issue_analysis_result = analyze_issues(model, issue_information)

    release_analysis_choice = interpret_yes_no(
        model,
        input("Would you like guidance about the latest official Release? "),
    )
    if release_analysis_choice == "yes":
        release_request = parse_release_request(input(
            "Enter 'overview' or 'asset_match;operating_system;architecture;package_preference': "
        ))
        release_information = github.get_release(
            selected_repository["owner"], selected_repository["repository"]
        )
        asset_selection = None
        if release_request["analysis_mode"] == "asset_match":
            asset_selection = select_asset(model, release_information, release_request)
        release_advice = create_release_advice(
            model, release_information, release_request, asset_selection
        )

    print("\nFinal result")
    print(project_summary)
    if issue_analysis_choice == "yes" and issue_analysis_result is not None:
        _print_json("Issue analysis", issue_analysis_result)
    if release_analysis_choice == "yes" and release_advice is not None:
        _print_json("Release guidance", release_advice)
    result: dict[str, object] = {"project_summary": project_summary}
    if issue_analysis_result is not None:
        result["issue_analysis_result"] = issue_analysis_result
    if release_advice is not None:
        result["release_advice"] = release_advice
    return result


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as exc:
        print(f"Execution failure: {exc}", file=sys.stdout)
