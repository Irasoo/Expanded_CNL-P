from __future__ import annotations

import json
import os
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen


def _load_dotenv() -> dict[str, str]:
    """Load simple KEY=VALUE entries from the .env in the current directory."""
    values: dict[str, str] = {}
    path = os.path.join(os.getcwd(), ".env")
    try:
        with open(path, "r", encoding="utf-8") as stream:
            lines = stream.readlines()
    except FileNotFoundError:
        return values

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def _setting(name: str, dotenv: dict[str, str]) -> str:
    return os.getenv(name, dotenv.get(name, "")).strip()


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
    """Read repository metadata and README; a public 404 is a business result."""
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

    api_url = (
        "https://api.github.com/repos/"
        f"{quote(owner_value, safe='')}/{quote(repository_value, safe='')}"
    )
    try:
        request = Request(api_url, headers=_github_headers(), method="GET")
        with urlopen(request, timeout=30) as response:
            metadata = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return _not_found_overview()
        raise RuntimeError(f"GitHub repository lookup returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "GitHub repository metadata could not be read: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(metadata, dict):
        raise RuntimeError("GitHub returned malformed repository metadata.")

    readme = ""
    readme_headers = _github_headers()
    readme_headers["Accept"] = "application/vnd.github.raw+json"
    try:
        request = Request(api_url + "/readme", headers=readme_headers, method="GET")
        with urlopen(request, timeout=30) as response:
            readme = response.read(50001).decode("utf-8", errors="replace")
            readme = readme[:50000]
    except HTTPError as exc:
        if exc.code != 404:
            raise RuntimeError(f"GitHub README lookup returned HTTP {exc.code}.") from exc
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
    """Read the first page of recently updated open Issues, excluding pull requests."""
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
    """Read the latest official public Release and maintainer-uploaded assets."""
    owner_value = str(owner).strip()
    repository_value = str(repository).strip()
    if not owner_value or not repository_value:
        raise ValueError("GitHub owner and repository are required.")

    url = (
        "https://api.github.com/repos/"
        f"{quote(owner_value, safe='')}/{quote(repository_value, safe='')}/releases/latest"
    )
    try:
        request = Request(url, headers=_github_headers(), method="GET")
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


def _model_config() -> tuple[Any, str]:
    from openai import OpenAI

    dotenv = _load_dotenv()
    api_key = _setting("OPENAI_API_KEY", dotenv)
    base_url = _setting("BASE_URL", dotenv)
    model = _setting("CNLP_REFERENCE_LLM_MODEL", dotenv) or _setting(
        "OPENAI_MODEL", dotenv
    )
    missing = [name for name, value in (("OPENAI_API_KEY", api_key), ("BASE_URL", base_url)) if not value]
    if missing:
        raise RuntimeError(
            "Missing required runtime model configuration: " + ", ".join(missing) + "."
        )
    if not model:
        raise RuntimeError(
            "Missing runtime model configuration: set CNLP_REFERENCE_LLM_MODEL "
            "or OPENAI_MODEL."
        )
    return OpenAI(api_key=api_key, base_url=base_url), model


def _call_json(system_prompt: str, user_prompt: str, name: str, schema: dict[str, Any]) -> dict[str, Any]:
    client, model = _model_config()
    try:
        response = client.responses.create(
            model=model,
            reasoning={"effort": "high"},
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
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
    except Exception as exc:
        raise RuntimeError(f"Runtime language-model call failed: {type(exc).__name__}: {exc}") from exc

    raw = getattr(response, "output_text", "")
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeError("Runtime language model returned empty output.")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Runtime language model returned invalid JSON.") from exc
    if not isinstance(value, dict):
        raise RuntimeError("Runtime language model returned a non-object result.")
    return value


def _object_schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required if required is not None else list(properties),
        "additionalProperties": False,
    }


def _string_array_schema() -> dict[str, Any]:
    return {"type": "array", "items": {"type": "string"}}


def _classify_yes_no(answer: str, question_context: str) -> str:
    value = _call_json(
        "You interpret a user's natural-language answer. Return only the requested JSON. "
        "Choose yes when the user agrees to the described action and no when the user declines. "
        "Do not infer agreement from unrelated text.",
        f"Question context: {question_context}\nUser answer: {answer}",
        "yes_no_choice",
        _object_schema({"choice": {"type": "string", "enum": ["yes", "no"]}}),
    )
    choice = value.get("choice")
    if choice not in {"yes", "no"}:
        raise RuntimeError("Language model returned an invalid yes/no choice.")
    return choice


def _build_project_summary(overview: dict[str, object]) -> str:
    result = _call_json(
        "You are GitHubProjectAssistant's ProjectNavigator. Write a clear English project "
        "overview from the supplied public GitHub facts. Do not merely copy the README. "
        "Cover project name, purpose, core capabilities, typical use cases, intended users, "
        "primary technology, execution or installation entry points, license, maintenance "
        "status, and important README limitations. Do not judge quality from stars or open "
        "Issue count alone. Distinguish facts from limitations and say when a field is unknown.",
        json.dumps(overview, ensure_ascii=False),
        "project_summary",
        _object_schema({"summary": {"type": "string"}}),
    )
    summary = result.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise RuntimeError("Language model returned an empty project summary.")
    return summary.strip()


def _analyze_issues(issue_information: dict[str, object]) -> dict[str, object]:
    expected_count = issue_information["analyzed_issue_count"]
    result = _call_json(
        "You are an independent IssueAnalyzer for GitHubProjectAssistant. Analyze only the "
        "limited sample of recently updated open Issues supplied by the user. Separate repeated "
        "concerns from isolated reports, and confirmed maintainer problems from unresolved "
        "reports. Never call one report a general project problem. Select a small representative "
        "set. State the exact sample size and limitations, including what this sample cannot establish. "
        "Return concise English strings in every array. Keep representative issue strings tied to "
        "the supplied issue numbers and URLs.",
        "The issue_information JSON is:\n" + json.dumps(issue_information, ensure_ascii=False),
        "issue_analysis",
        _object_schema(
            {
                "analyzed_issue_count": {"type": "integer", "minimum": 0},
                "common_problems": _string_array_schema(),
                "confirmed_problems": _string_array_schema(),
                "unresolved_problems": _string_array_schema(),
                "representative_issues": _string_array_schema(),
                "limitations": _string_array_schema(),
            }
        ),
    )
    required_keys = {
        "analyzed_issue_count",
        "common_problems",
        "confirmed_problems",
        "unresolved_problems",
        "representative_issues",
        "limitations",
    }
    if set(result) != required_keys or result["analyzed_issue_count"] != expected_count:
        raise RuntimeError("Language model returned an invalid Issue analysis result.")
    if any(not isinstance(result[key], list) or any(not isinstance(item, str) for item in result[key]) for key in required_keys - {"analyzed_issue_count"}):
        raise RuntimeError("Language model returned invalid Issue analysis fields.")
    return result


def _release_asset_schema(nullable: bool = False) -> dict[str, Any]:
    asset = _object_schema(
        {
            "name": {"type": "string"},
            "download_url": {"type": "string"},
            "size": {"type": "integer", "minimum": 0},
            "digest": {"type": "string"},
        }
    )
    return {"anyOf": [asset, {"type": "null"}]} if nullable else asset


def _select_asset(release: dict[str, object], request: dict[str, str]) -> dict[str, object]:
    result = _call_json(
        "You are selecting a Release asset for a user. Use semantic understanding of asset names "
        "and the stated platform and package preference. Select only an exact asset object from "
        "the supplied assets. Automatically generated GitHub source zip and source tar archives "
        "are not installable assets by default and must be excluded. If no suitable asset exists, "
        "set found false, asset null, and explain the evidence-based reason. Do not invent compatibility.",
        "Release request:\n" + json.dumps(request, ensure_ascii=False) + "\nRelease information:\n" + json.dumps(release, ensure_ascii=False),
        "asset_selection",
        _object_schema(
            {
                "found": {"type": "boolean"},
                "reason": {"type": "string"},
                "asset": _release_asset_schema(nullable=True),
            }
        ),
    )
    if set(result) != {"found", "reason", "asset"} or not isinstance(result.get("found"), bool) or not isinstance(result.get("reason"), str):
        raise RuntimeError("Language model returned an invalid asset selection.")
    selected = result.get("asset")
    assets = release.get("assets", [])
    if result["found"]:
        if not isinstance(selected, dict) or selected not in assets:
            raise RuntimeError("Language model selected an asset that was not supplied by GitHub.")
        result["asset"] = selected
    else:
        result["asset"] = None
    return result


def _build_release_advice(
    release: dict[str, object], request: dict[str, str], selection: dict[str, object]
) -> dict[str, object]:
    result = _call_json(
        "You are an independent ReleaseAdvisor. Give no-download guidance for only the latest "
        "official public GitHub Release supplied here. For overview, include version, name, "
        "publication time, key release-note points, and asset count. For a matching asset, "
        "include its exact name, byte size, URL, digest, compatibility rationale, and user-side "
        "verification guidance. For no match, explain why. Never recommend source archives as "
        "directly installable software by default. Explicitly state that no file was downloaded, "
        "created, installed, extracted, or executed. Return concise English text fields.",
        "Release request:\n" + json.dumps(request, ensure_ascii=False) + "\nAsset selection:\n" + json.dumps(selection, ensure_ascii=False) + "\nRelease information:\n" + json.dumps(release, ensure_ascii=False),
        "release_advice",
        _object_schema(
            {
                "status": {"type": "string", "enum": ["overview", "recommended", "no_match"]},
                "version": {"type": "string"},
                "summary": {"type": "string"},
                "acquisition_url": {"type": "string"},
                "integrity_guidance": {"type": "string"},
                "limitations": _string_array_schema(),
                "asset": _release_asset_schema(nullable=True),
            }
        ),
    )
    required = {"status", "version", "summary", "acquisition_url", "integrity_guidance", "limitations", "asset"}
    if set(result) != required or result.get("status") not in {"overview", "recommended", "no_match"}:
        raise RuntimeError("Language model returned an invalid Release advice result.")
    if not all(isinstance(result[key], str) for key in {"version", "summary", "acquisition_url", "integrity_guidance"}):
        raise RuntimeError("Language model returned invalid Release advice text fields.")
    if not isinstance(result["limitations"], list) or any(not isinstance(item, str) for item in result["limitations"]):
        raise RuntimeError("Language model returned invalid Release limitations.")

    expected_status = "overview" if request["analysis_mode"] == "overview" else (
        "recommended" if selection["found"] else "no_match"
    )
    if result["status"] != expected_status:
        raise RuntimeError("Language model returned a Release status inconsistent with the selection.")
    if expected_status == "recommended":
        if not isinstance(result["asset"], dict) or result["asset"] != selection["asset"]:
            raise RuntimeError("Language model returned a Release asset inconsistent with the selection.")
    else:
        result["asset"] = None
    return result


def _parse_release_request(answer: str) -> dict[str, str]:
    value = answer.strip()
    if value == "overview":
        return {"analysis_mode": "overview"}
    parts = value.split(";")
    if len(parts) != 4 or parts[0] != "asset_match":
        raise ValueError(
            "Invalid ReleaseRequest. Use overview or "
            "asset_match;operating_system;architecture;package_preference."
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


def _print_issue_analysis(value: dict[str, object]) -> None:
    print("\nRecently Updated Open Issues")
    print(f"Analyzed issue sample: {value['analyzed_issue_count']}")
    for label, key in (
        ("Common problems", "common_problems"),
        ("Maintainer-confirmed problems", "confirmed_problems"),
        ("Unresolved problems", "unresolved_problems"),
        ("Representative issues", "representative_issues"),
        ("Limitations", "limitations"),
    ):
        print(f"{label}:")
        items = value[key]
        if items:
            for item in items:
                print(f"- {item}")
        else:
            print("- None identified in the analyzed sample.")


def _print_release_advice(value: dict[str, object]) -> None:
    print("\nLatest Official Release")
    print(f"Status: {value['status']}")
    print(f"Version: {value['version']}")
    print(value["summary"])
    print(f"Acquisition URL: {value['acquisition_url'] or 'None'}")
    print(f"Integrity guidance: {value['integrity_guidance']}")
    if value.get("asset"):
        asset = value["asset"]
        print(
            "Selected asset: "
            f"{asset['name']} ({asset['size']} bytes), {asset['download_url']}"
        )
        print(f"Digest: {asset['digest'] or 'Not supplied by GitHub.'}")
    print("Limitations:")
    for item in value["limitations"]:
        print(f"- {item}")


class GitHubProjectAssistant:
    def __init__(self) -> None:
        self.project_input = ""
        self.input_kind = "unclear"
        self.repository_input_retry_count = 0
        self.repository_input_limit_exceeded = False
        self.selected_repository: dict[str, str] | None = None
        self.project_overview: dict[str, object] | None = None
        self.repository_found = False
        self.project_summary = (
            "No project summary is available because the target Repository was not resolved."
        )
        self.issue_analysis_choice = "no"
        self.issue_information: dict[str, object] | None = None
        self.issue_analysis_result: dict[str, object] | None = None
        self.release_analysis_choice = "no"
        self.release_request: dict[str, str] | None = None
        self.release_information: dict[str, object] | None = None
        self.asset_selection: dict[str, object] | None = None
        self.release_advice: dict[str, object] | None = None

    def _classify_project_input(self) -> str:
        try:
            parse_github_repository_input(self.project_input)
        except (TypeError, ValueError):
            return "unclear"
        return "repository_url" if "://" in self.project_input.strip() else "repository_name"

    def run(self) -> dict[str, object]:
        print("GitHubProjectAssistant")
        print(
            "I can inspect an explicitly identified GitHub Repository, summarize its public "
            "information, analyze recently updated open Issues, and provide latest Release "
            "guidance without downloading files. Please provide a complete GitHub Repository "
            "URL or an explicit owner/repository identifier."
        )
        self.project_input = input("Repository: ")
        self.input_kind = self._classify_project_input()

        while self.input_kind == "unclear" and self.repository_input_retry_count < 3:
            print(
                "The current input does not uniquely identify a Repository. Please enter a "
                "complete GitHub Repository URL or an explicit owner/repository identifier."
            )
            self.project_input = input("Repository: ")
            self.repository_input_retry_count += 1
            self.input_kind = self._classify_project_input()

        self.repository_input_limit_exceeded = (
            self.input_kind == "unclear" and self.repository_input_retry_count >= 3
        )
        if self.repository_input_limit_exceeded:
            print("The Repository input remains unclear after three correction attempts.")
            self.project_summary = (
                "The target Repository could not be determined after three correction attempts. "
                "GitHub was not accessed, and no Issue or Release analysis was performed."
            )
            print(self.project_summary)
            return {"project_summary": self.project_summary}

        self.selected_repository = parse_github_repository_input(self.project_input)
        self.project_overview = get_github_project_overview(
            self.selected_repository["owner"], self.selected_repository["repository"]
        )
        self.repository_found = bool(self.project_overview["found"])
        if not self.repository_found:
            self.project_summary = (
                f"The explicitly identified Repository {self.selected_repository['owner']}/"
                f"{self.selected_repository['repository']} was not found on GitHub. "
                "This is a Repository-not-found result, not a network or authentication diagnosis."
            )
            print(self.project_summary)
            return {"project_summary": self.project_summary}

        self.project_summary = _build_project_summary(self.project_overview)
        print("\nProject Overview")
        print(self.project_summary)

        issue_answer = input("Would you like an analysis of recently updated open Issues? ")
        self.issue_analysis_choice = _classify_yes_no(
            issue_answer, "whether the user wants recently updated open Issues analyzed"
        )
        if self.issue_analysis_choice == "yes":
            self.issue_information = get_github_issue_information(
                self.selected_repository["owner"], self.selected_repository["repository"]
            )
            self.issue_analysis_result = _analyze_issues(self.issue_information)

        release_answer = input("Would you like guidance about the latest official Release? ")
        self.release_analysis_choice = _classify_yes_no(
            release_answer, "whether the user wants guidance about the latest official Release"
        )
        if self.release_analysis_choice == "yes":
            release_format = input(
                "Enter overview or asset_match;operating_system;architecture;package_preference: "
            )
            self.release_request = _parse_release_request(release_format)
            self.release_information = get_github_release(
                self.selected_repository["owner"], self.selected_repository["repository"]
            )
            if self.release_request["analysis_mode"] == "asset_match":
                self.asset_selection = _select_asset(self.release_information, self.release_request)
            else:
                self.asset_selection = {"found": False, "reason": "Overview mode does not select an asset.", "asset": None}
            self.release_advice = _build_release_advice(
                self.release_information, self.release_request, self.asset_selection
            )

        print("\nFinal Result")
        print(self.project_summary)
        if self.issue_analysis_choice == "yes" and self.issue_analysis_result is not None:
            _print_issue_analysis(self.issue_analysis_result)
        if self.release_analysis_choice == "yes" and self.release_advice is not None:
            _print_release_advice(self.release_advice)
        result: dict[str, object] = {"project_summary": self.project_summary}
        if self.issue_analysis_result is not None:
            result["issue_analysis_result"] = self.issue_analysis_result
        if self.release_advice is not None:
            result["release_advice"] = self.release_advice
        return result


def main() -> dict[str, object]:
    """Initialize GitHubProjectAssistant, execute its terminal workflow, and return its result."""
    try:
        return GitHubProjectAssistant().run()
    except (EOFError, KeyboardInterrupt):
        print("\nThe terminal interaction was cancelled.", file=sys.stderr)
        return {"error": "The terminal interaction was cancelled."}
    except Exception as exc:
        print(f"Execution failed: {exc}", file=sys.stderr)
        return {"error": str(exc)}


if __name__ == "__main__":
    main()
