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


def load_local_env() -> None:
    """Load simple KEY=VALUE entries from the local .env without overriding the process."""
    env_path = Path(".env")
    if not env_path.is_file():
        return
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"The local .env file could not be read: {exc}") from exc
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
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


def classify_repository_input(project_input: str) -> str:
    """Implement COMMAND-3 using the explicit repository grammar."""
    try:
        parse_github_repository_input(project_input)
    except (TypeError, ValueError):
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
        raise RuntimeError(f"GitHub repository lookup returned HTTP {exc.code}.") from exc
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
    """Read recently updated open Issues, excluding pull requests."""
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
    """Read the latest official public Release and maintainer-uploaded assets."""
    owner_value = str(owner).strip()
    repository_value = str(repository).strip()
    if not owner_value or not repository_value:
        raise ValueError("GitHub owner and repository are required.")

    base_url = (
        "https://api.github.com/repos/"
        f"{quote(owner_value, safe='')}/{quote(repository_value, safe='')}"
        "/releases/latest"
    )
    try:
        request = Request(base_url, headers=_github_headers(), method="GET")
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


def parse_yes_no(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"yes", "no"}:
        raise ValueError(f"{field_name} must be answered with yes or no.")
    return normalized


def parse_release_request(value: str) -> dict[str, object]:
    normalized = value.strip()
    if normalized == "overview":
        return {"analysis_mode": "overview"}
    parts = normalized.split(";")
    if len(parts) != 4 or parts[0] != "asset_match":
        raise ValueError(
            "ReleaseRequest must be overview or "
            "asset_match;operating_system;architecture;package_preference."
        )
    _, operating_system, architecture, package_preference = parts
    if operating_system not in {"windows", "macos", "linux", "other"}:
        raise ValueError("operating_system must be windows, macos, linux, or other.")
    if architecture not in {"x64", "arm64", "unknown"}:
        raise ValueError("architecture must be x64, arm64, or unknown.")
    if package_preference not in {"installer", "portable", "archive", "any"}:
        raise ValueError(
            "package_preference must be installer, portable, archive, or any."
        )
    return {
        "analysis_mode": "asset_match",
        "operating_system": operating_system,
        "architecture": architecture,
        "package_preference": package_preference,
    }


STATIC_CONTEXT = """
Persona: You are a cautious and evidence-based assistant for GitHub project
information, Issue risks, and Release compatibility. Confirm the target
Repository, distinguish facts from analysis, and do not guess.
Audience: Developers and software users who can provide a complete GitHub
Repository URL or explicit owner/repository identifier. Use clear English and
explain terminology enough for a technically capable user.
Concepts: A Repository is uniquely identified by owner and repository. An
Issue insight requires repeated, confirmed, and unresolved evidence from the
recent open Issue sample. A Release is the latest official public GitHub
Release. Release assets are maintainer-uploaded files; GitHub source archives
are not installable assets by default.
Constraints: Use read-only GitHub access. Never create or modify GitHub
resources. Never download, write, install, extract, or execute Release files.
Do not judge quality from Stars or open Issue count alone. Do not generalize
one report into a project-wide problem. State the actual Issue sample scope.
""".strip()


class LanguageModel:
    def __init__(self) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The official OpenAI Python Client is required for semantic commands."
            ) from exc

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        base_url = os.getenv("BASE_URL", "").strip()
        model = (
            os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip()
            or os.getenv("OPENAI_MODEL", "").strip()
        )
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is missing from the environment or local .env file."
            )
        if not base_url:
            raise RuntimeError(
                "BASE_URL is missing from the environment or local .env file."
            )
        if not model:
            raise RuntimeError(
                "Set CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL in the environment or local .env file."
            )
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def complete(self, instruction: str, json_output: bool = False) -> str:
        request: dict[str, Any] = {
            "model": self.model,
            "reasoning": {"effort": "high"},
            "input": [
                {"role": "system", "content": STATIC_CONTEXT},
                {"role": "user", "content": instruction},
            ],
        }
        if json_output:
            request["text"] = {"format": {"type": "json_object"}}
        try:
            response = self.client.responses.create(**request)
        except Exception as exc:
            raise RuntimeError(f"Language-model execution failed: {exc}") from exc
        text = getattr(response, "output_text", "")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("The language model returned an empty result.")
        return text.strip()

    def json_object(self, instruction: str) -> dict[str, Any]:
        raw = self.complete(instruction, json_output=True)
        candidate = raw.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate).strip()
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "The language model returned malformed JSON: " f"{exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("The language model returned a JSON value instead of an object.")
        return parsed


def _string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError(f"Language-model field {field_name} must be a string list.")
    return value


def _asset_is_source_archive(name: str) -> bool:
    lowered = name.lower()
    return (
        "source code" in lowered
        or lowered.startswith("source-")
        or lowered in {"source.zip", "source.tar", "source.tar.gz", "source.tgz"}
    )


class ProjectNavigator:
    def __init__(self) -> None:
        load_local_env()
        self.language_model: LanguageModel | None = None
        self.state: dict[str, Any] = {
            "repository_input_retry_count": 0,
            "repository_input_limit_exceeded": False,
            "repository_found": False,
            "project_summary": (
                "No project summary is available because the target Repository was not resolved."
            ),
        }

    def model(self) -> LanguageModel:
        if self.language_model is None:
            self.language_model = LanguageModel()
        return self.language_model

    def input_once(self, prompt: str) -> str:
        print(prompt)
        value = input("> ")
        return value

    def display(self, value: object) -> None:
        if isinstance(value, str):
            print(value)
        else:
            print(json.dumps(value, ensure_ascii=True, indent=2))

    def project_summary(self, overview: dict[str, object]) -> str:
        instruction = """
Using the repository facts below, write a concise but substantive project
overview in clear English. Explain the project name, purpose, core
capabilities, typical use cases, intended users, primary technology,
installation or execution entry points, license, maintenance status, and
important README limitations. Distinguish metadata facts from README-derived
claims. Do not merely copy the README. Do not use Stars or open Issue count as
a quality judgment. Do not invent details absent from the supplied data.

Repository facts (JSON):
""" + json.dumps(overview, ensure_ascii=False)
        return self.model().complete(instruction)

    def analyze_issues(self, issue_information: dict[str, object]) -> dict[str, object]:
        count = int(issue_information["analyzed_issue_count"])
        issues = issue_information["issues"]
        if not isinstance(issues, list):
            raise RuntimeError("Issue information has an invalid issues list.")
        if count == 0:
            return {
                "analyzed_issue_count": 0,
                "common_problems": [],
                "confirmed_problems": [],
                "unresolved_problems": [],
                "representative_issues": [],
                "limitations": [
                    "No recently updated open Issues were returned by GitHub, so no Issue pattern can be established."
                ],
            }
        issue_text = "\n\n--- ISSUE RECORD ---\n\n".join(str(item) for item in issues)
        instruction = """
Analyze the supplied recently updated open Issue sample. Return only a JSON
object with these keys, each a string list except analyzed_issue_count:
{
  "analyzed_issue_count": number,
  "common_problems": [],
  "confirmed_problems": [],
  "unresolved_problems": [],
  "representative_issues": [],
  "limitations": []
}
Use repeated evidence for common_problems. Put only maintainer-confirmed or
otherwise directly confirmed matters in confirmed_problems. Put unresolved
reports or still-open concerns in unresolved_problems. Mention isolated
reports as limitations rather than general problems. Select a small set of
representative Issue numbers and titles in representative_issues. The count
must equal the supplied number of Issue records. State the actual sample scope
and its limits in limitations. Never infer project quality from Issue count.

Supplied Issue count: """ + str(count) + "\n\nSupplied Issue records:\n" + issue_text
        result = self.model().json_object(instruction)
        normalized = {
            "analyzed_issue_count": count,
            "common_problems": _string_list(result.get("common_problems"), "common_problems"),
            "confirmed_problems": _string_list(
                result.get("confirmed_problems"), "confirmed_problems"
            ),
            "unresolved_problems": _string_list(
                result.get("unresolved_problems"), "unresolved_problems"
            ),
            "representative_issues": _string_list(
                result.get("representative_issues"), "representative_issues"
            ),
            "limitations": _string_list(result.get("limitations"), "limitations"),
        }
        return normalized

    def select_asset(
        self, release_information: dict[str, object], release_request: dict[str, object]
    ) -> dict[str, object]:
        assets = release_information.get("assets", [])
        if not isinstance(assets, list):
            raise RuntimeError("Release information has an invalid assets list.")
        if not assets:
            return {
                "found": False,
                "reason": "The latest official Release has no maintainer-uploaded assets.",
            }
        instruction = """
Select the most suitable maintainer-uploaded Release asset for the exact
platform preferences below. Return only this JSON object:
{"found": true or false, "asset_name": "exact asset name or empty", "reason": "explanation"}
Use filename and release context to assess operating system, architecture, and
package preference. Do not select GitHub source archives, and do not invent an
asset. If compatibility is not sufficiently supported, return found=false.
The asset_name must exactly match one supplied asset name.

Release request (JSON):
""" + json.dumps(release_request, ensure_ascii=False) + "\n\nRelease metadata and assets (JSON):\n" + json.dumps(
            release_information, ensure_ascii=False
        )
        result = self.model().json_object(instruction)
        found = result.get("found")
        asset_name = result.get("asset_name", "")
        reason = result.get("reason")
        if not isinstance(found, bool) or not isinstance(asset_name, str) or not isinstance(reason, str):
            raise RuntimeError("Language-model asset selection has invalid fields.")
        if not found:
            return {"found": False, "reason": reason}
        matching = [asset for asset in assets if isinstance(asset, dict) and asset.get("name") == asset_name]
        if not matching:
            raise RuntimeError("Language-model selected an asset not returned by GitHub.")
        asset = matching[0]
        if _asset_is_source_archive(str(asset.get("name") or "")):
            return {
                "found": False,
                "reason": "The proposed match is a source archive, which is not treated as an installable asset by default.",
            }
        return {"found": True, "asset": asset, "reason": reason}

    def release_advice_overview(self, release_information: dict[str, object]) -> dict[str, object]:
        assets = release_information.get("assets", [])
        asset_count = len(assets) if isinstance(assets, list) else 0
        instruction = """
Write a latest Release overview from the supplied metadata. Return only this
JSON object:
{"summary": "clear overview", "integrity_guidance": "user-side guidance", "limitations": ["..."]}
Include version, release name, publication time, key Release Notes, and the
asset count. Preserve uncertainty when Release Notes are empty. Explicitly
state that no file operation was performed. Do not recommend downloading.

Release metadata (JSON):
""" + json.dumps(release_information, ensure_ascii=False)
        result = self.model().json_object(instruction)
        summary = result.get("summary")
        integrity_guidance = result.get("integrity_guidance")
        limitations = _string_list(result.get("limitations"), "limitations")
        if not isinstance(summary, str) or not isinstance(integrity_guidance, str):
            raise RuntimeError("Language-model Release overview has invalid fields.")
        return {
            "status": "overview",
            "version": str(release_information.get("version") or ""),
            "release_name": str(release_information.get("release_name") or ""),
            "summary": summary,
            "acquisition_url": "",
            "integrity_guidance": integrity_guidance,
            "limitations": limitations,
        }

    def release_advice_asset(
        self,
        release_information: dict[str, object],
        release_request: dict[str, object],
        selection: dict[str, object],
    ) -> dict[str, object]:
        instruction = """
Create no-download Release guidance from the supplied Release metadata,
platform request, and asset selection. Return only this JSON object:
{"summary": "guidance", "integrity_guidance": "verification guidance", "limitations": ["..."]}
If found, provide the selected asset name, size, URL, digest, and compatibility
rationale. If no match was found, explain why. Include user-side verification
guidance and explicitly state that no file was downloaded, created, installed,
extracted, or executed. Do not tell the user to use a source archive as an
installer by default.

Release request (JSON):
""" + json.dumps(release_request, ensure_ascii=False) + "\n\nSelection (JSON):\n" + json.dumps(
            selection, ensure_ascii=False
        ) + "\n\nRelease metadata (JSON):\n" + json.dumps(release_information, ensure_ascii=False)
        result = self.model().json_object(instruction)
        summary = result.get("summary")
        integrity_guidance = result.get("integrity_guidance")
        limitations = _string_list(result.get("limitations"), "limitations")
        if not isinstance(summary, str) or not isinstance(integrity_guidance, str):
            raise RuntimeError("Language-model asset guidance has invalid fields.")
        found = bool(selection.get("found"))
        asset = selection.get("asset") if found else None
        return {
            "status": "recommended" if found else "no_match",
            "version": str(release_information.get("version") or ""),
            "asset": asset,
            "summary": summary,
            "acquisition_url": str(asset.get("download_url") or "") if isinstance(asset, dict) else "",
            "integrity_guidance": integrity_guidance,
            "limitations": limitations,
        }

    def run(self) -> dict[str, object]:
        print(
            "This Agent requires either a complete GitHub Repository URL or an explicit "
            "owner/repository identifier. It can summarize public project information, "
            "analyze recent open Issues, and provide Release guidance without downloading files."
        )
        self.state["project_input"] = self.input_once(
            "Enter a complete GitHub Repository URL or an explicit owner/repository identifier."
        )
        self.state["input_kind"] = classify_repository_input(self.state["project_input"])
        self.state["repository_input_limit_exceeded"] = False

        while (
            self.state["input_kind"] == "unclear"
            and self.state["repository_input_retry_count"] < 3
        ):
            self.state["project_input"] = self.input_once(
                "The current input does not uniquely identify a Repository. Enter a complete "
                "GitHub Repository URL or an explicit owner/repository identifier."
            )
            self.state["repository_input_retry_count"] += 1
            self.state["input_kind"] = classify_repository_input(self.state["project_input"])

        if self.state["input_kind"] == "unclear":
            self.state["repository_input_limit_exceeded"] = True
            print("LOG: The Repository input remains unclear after three correction attempts")
            self.state["project_summary"] = (
                "The target Repository could not be determined after three correction attempts. "
                "GitHub was not accessed, and no Issue or Release analysis was performed."
            )
            self.display(self.state["project_summary"])
            return self.final_outputs()

        self.state["selected_repository"] = parse_github_repository_input(
            self.state["project_input"]
        )
        self.state["project_overview"] = get_github_project_overview(
            self.state["selected_repository"]["owner"],
            self.state["selected_repository"]["repository"],
        )
        self.state["repository_found"] = bool(self.state["project_overview"]["found"])

        if not self.state["repository_found"]:
            repo = self.state["selected_repository"]
            self.state["project_summary"] = (
                f"The explicitly identified Repository {repo['owner']}/{repo['repository']} "
                "was not found by GitHub. This is a Repository-not-found result, not a "
                "network, authentication, rate-limit, or service failure."
            )
            self.display(self.state["project_summary"])
            return self.final_outputs()

        self.state["project_summary"] = self.project_summary(self.state["project_overview"])
        self.display(self.state["project_summary"])

        self.state["issue_analysis_choice"] = parse_yes_no(
            self.input_once("Do you want an analysis of recently updated open Issues? (yes/no)"),
            "Issue analysis choice",
        )
        if self.state["issue_analysis_choice"] == "yes":
            repository = self.state["selected_repository"]
            self.state["issue_information"] = get_github_issue_information(
                repository["owner"], repository["repository"]
            )
            self.state["issue_analysis_result"] = self.analyze_issues(
                self.state["issue_information"]
            )

        self.state["release_analysis_choice"] = parse_yes_no(
            self.input_once("Do you want guidance about the latest official Release? (yes/no)"),
            "Release analysis choice",
        )
        if self.state["release_analysis_choice"] == "yes":
            self.state["release_request"] = parse_release_request(
                self.input_once(
                    "Enter overview, or asset_match;operating_system;architecture;package_preference "
                    "using the exact allowed values."
                )
            )
            repository = self.state["selected_repository"]
            self.state["release_information"] = get_github_release(
                repository["owner"], repository["repository"]
            )
            if self.state["release_request"]["analysis_mode"] == "overview":
                self.state["release_advice"] = self.release_advice_overview(
                    self.state["release_information"]
                )
            else:
                self.state["asset_selection"] = self.select_asset(
                    self.state["release_information"], self.state["release_request"]
                )
                self.state["release_advice"] = self.release_advice_asset(
                    self.state["release_information"],
                    self.state["release_request"],
                    self.state["asset_selection"],
                )

        print("Final result:")
        self.display(self.state["project_summary"])
        if self.state.get("issue_analysis_choice") == "yes":
            self.display(self.state["issue_analysis_result"])
        if self.state.get("release_analysis_choice") == "yes":
            self.display(self.state["release_advice"])
        return self.final_outputs()

    def final_outputs(self) -> dict[str, object]:
        outputs: dict[str, object] = {
            "project_summary": self.state["project_summary"]
        }
        if "issue_analysis_result" in self.state:
            outputs["issue_analysis_result"] = self.state["issue_analysis_result"]
        if "release_advice" in self.state:
            outputs["release_advice"] = self.state["release_advice"]
        return outputs


def main() -> dict[str, object]:
    """Initialize the Agent, execute the ProjectNavigator Worker, and return its outputs."""
    try:
        return ProjectNavigator().run()
    except (KeyboardInterrupt, EOFError):
        print("Execution stopped before the Worker completed.", file=sys.stderr)
        return {"error": "Execution stopped before the Worker completed."}
    except Exception as exc:
        print(f"Execution failure: {exc}", file=sys.stderr)
        return {"error": str(exc)}


if __name__ == "__main__":
    main()
