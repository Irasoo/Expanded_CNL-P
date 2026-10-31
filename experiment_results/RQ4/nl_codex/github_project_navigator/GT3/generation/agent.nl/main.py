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

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - reported clearly when a model call is needed
    OpenAI = None  # type: ignore[assignment,misc]


INPUT_KINDS = {"repository_url", "repository_name", "unclear"}
OPERATING_SYSTEMS = {"windows", "macos", "linux", "other"}
ARCHITECTURES = {"x64", "arm64", "unknown"}
PACKAGE_PREFERENCES = {"installer", "portable", "archive", "any"}


def _read_dotenv() -> dict[str, str]:
    """Read simple KEY=VALUE entries from the project's local .env file."""
    values: dict[str, str] = {}
    env_path = Path(".env")
    if not env_path.is_file():
        return values
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"Could not read .env: {exc}") from exc
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _config_value(name: str, dotenv: dict[str, str]) -> str:
    return os.getenv(name, dotenv.get(name, "")).strip()


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


def classify_repository_input(project_input: str) -> str:
    try:
        parse_github_repository_input(project_input)
    except ValueError:
        return "unclear"
    return "repository_url" if "://" in project_input.strip() else "repository_name"


class GitHubReader:
    """Read public GitHub JSON and README content without performing file operations."""

    def __init__(self) -> None:
        token = os.getenv("GITHUB_TOKEN", "").strip()
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "cnlp-github-project-assistant",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _get_json(self, url: str, not_found_ok: bool = False) -> Any:
        try:
            request = Request(url, headers=self.headers, method="GET")
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if not_found_ok and exc.code == 404:
                return None
            raise RuntimeError(f"GitHub request returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"GitHub request failed: {type(exc).__name__}: {exc}") from exc

    @staticmethod
    def _path(owner: str, repository: str) -> str:
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
        return f"https://api.github.com/repos/{quote(owner_value, safe='')}/{quote(repository_value, safe='')}"

    def get_project_overview(self, owner: str, repository: str) -> dict[str, Any]:
        base_url = self._path(owner, repository)
        metadata = self._get_json(base_url, not_found_ok=True)
        if metadata is None:
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
        if not isinstance(metadata, dict):
            raise RuntimeError("GitHub returned malformed repository metadata.")

        readme_headers = dict(self.headers)
        readme_headers["Accept"] = "application/vnd.github.raw+json"
        try:
            request = Request(base_url + "/readme", headers=readme_headers, method="GET")
            with urlopen(request, timeout=30) as response:
                readme = response.read(50001).decode("utf-8", errors="replace")
                readme = readme[:50000]
        except HTTPError as exc:
            if exc.code == 404:
                readme = ""
            else:
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

    def get_issue_information(self, owner: str, repository: str) -> dict[str, Any]:
        base_url = self._path(owner, repository) + "/issues?" + urlencode(
            {"state": "open", "sort": "updated", "direction": "desc", "per_page": 100, "page": 1}
        )
        payload = self._get_json(base_url)
        if not isinstance(payload, list):
            raise RuntimeError("GitHub returned malformed Issue data.")
        issues: list[str] = []
        for item in payload:
            if not isinstance(item, dict) or "pull_request" in item:
                continue
            raw_labels = item.get("labels", [])
            labels = [
                str(label["name"])
                for label in raw_labels
                if isinstance(label, dict) and label.get("name")
            ] if isinstance(raw_labels, list) else []
            issues.append(
                "\n".join(
                    [
                        f"#{int(item.get('number') or 0)}: {str(item.get('title') or '')}",
                        f"URL: {item.get('html_url') or ''}",
                        f"State: {item.get('state') or ''}",
                        f"Updated at: {item.get('updated_at') or ''}",
                        f"Comments: {int(item.get('comments') or 0)}",
                        f"Labels: {', '.join(labels) if labels else 'none'}",
                        f"Body: {str(item.get('body') or '')[:4000]}",
                    ]
                )
            )
        return {"analyzed_issue_count": len(issues), "issues": issues}

    def get_release(self, owner: str, repository: str) -> dict[str, Any]:
        selected = self._get_json(self._path(owner, repository) + "/releases/latest")
        if not isinstance(selected, dict):
            raise RuntimeError("GitHub returned malformed Release data.")
        raw_assets = selected.get("assets", [])
        assets = [
            {
                "name": str(asset.get("name") or ""),
                "download_url": str(asset.get("browser_download_url") or ""),
                "size": int(asset.get("size") or 0),
                "digest": str(asset.get("digest") or ""),
            }
            for asset in raw_assets
            if isinstance(asset, dict)
        ] if isinstance(raw_assets, list) else []
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
        dotenv = _read_dotenv()
        api_key = _config_value("OPENAI_API_KEY", dotenv)
        base_url = _config_value("BASE_URL", dotenv)
        model = _config_value("CNLP_REFERENCE_LLM_MODEL", dotenv) or _config_value("OPENAI_MODEL", dotenv)
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured in .env or the environment.")
        if not model:
            raise RuntimeError("CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL must be configured.")
        if OpenAI is None:
            raise RuntimeError("The official OpenAI Python Client is not installed.")
        client_args: dict[str, str] = {"api_key": api_key}
        if base_url:
            client_args["base_url"] = base_url
        self.client = OpenAI(**client_args)
        self.model = model

    def text(self, system: str, user: str) -> str:
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                reasoning={"effort": "high"},
            )
        except Exception as exc:
            raise RuntimeError(f"Language model call failed: {type(exc).__name__}: {exc}") from exc
        output = getattr(response, "output_text", None)
        if isinstance(output, str) and output.strip():
            return output.strip()
        raise RuntimeError("Language model returned an empty response.")

    def json(self, system: str, user: str) -> dict[str, Any]:
        raw = self.text(system, user)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            value = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Language model returned invalid JSON.") from exc
        if not isinstance(value, dict):
            raise RuntimeError("Language model JSON result must be an object.")
        return value


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError(f"Language model field {field} must be a list of text values.")
    return value


def _format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} bytes"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size / (1024 * 1024):.1f} MiB"


class GitHubProjectAssistant:
    def __init__(self) -> None:
        self.github = GitHubReader()
        self.state: dict[str, Any] = {
            "project_input": "",
            "input_kind": "unclear",
            "repository_input_retry_count": 0,
            "repository_input_limit_exceeded": False,
            "selected_repository": None,
            "project_overview": None,
            "repository_found": False,
            "project_summary": "No project summary is available because the target Repository was not resolved.",
            "issue_analysis_choice": "no",
            "issue_information": None,
            "issue_analysis_result": None,
            "release_analysis_choice": "no",
            "release_request": None,
            "release_information": None,
            "asset_selection": None,
            "release_advice": None,
        }

    def _ask_yes_no(self, model: LanguageModel, question: str, answer: str) -> str:
        result = model.json(
            "Classify the user's answer as exactly yes or no. Use the intended meaning, not keyword matching. Return only JSON of the form {\"choice\":\"yes\"} or {\"choice\":\"no\"}.",
            f"Question: {question}\nUser answer: {answer}",
        )
        choice = result.get("choice")
        if choice not in {"yes", "no"}:
            raise RuntimeError("Language model returned an invalid yes/no choice.")
        return choice

    def _create_project_summary(self, model: LanguageModel, overview: dict[str, Any]) -> str:
        facts = json.dumps(overview, ensure_ascii=False)
        return model.text(
            "You are the project overview writer for GitHubProjectAssistant. Write clear English based only on the supplied public repository facts and README. Do not invent capabilities, entry points, users, or limitations. Do not judge quality from stars or open Issue count. Distinguish facts from cautious inferences.",
            "Create a concise project summary covering the project name, purpose, core capabilities, typical use cases, intended users, primary technology, execution or installation entry points, license, maintenance status, and important README limitations. Repository facts and README follow:\n" + facts,
        )

    def _analyze_issues(self, model: LanguageModel, issue_information: dict[str, Any]) -> dict[str, Any]:
        count = int(issue_information["analyzed_issue_count"])
        issues = issue_information["issues"]
        if count == 0:
            return {
                "analyzed_issue_count": 0,
                "common_problems": [],
                "confirmed_problems": [],
                "unresolved_problems": [],
                "representative_issues": [],
                "limitations": ["No recently updated open Issues were available in the analyzed sample."],
            }
        result = model.json(
            "You are IssueAnalyzer. Analyze only the supplied limited sample of recently updated open GitHub Issues. Never turn one user report into a general project problem. Separate repeated concerns, isolated reports, maintainer-confirmed problems, and unresolved reports. Return JSON with exactly these fields: analyzed_issue_count (number), common_problems (list of text), confirmed_problems (list of text), unresolved_problems (list of text), representative_issues (list of text), limitations (list of text). Representative issues must identify issue numbers or titles. State sample limitations explicitly.",
            "The sample count is " + str(count) + ". Issues:\n" + json.dumps(issues, ensure_ascii=False),
        )
        if int(result.get("analyzed_issue_count", -1)) != count:
            raise RuntimeError("Language model Issue analysis count does not match the fetched sample.")
        return {
            "analyzed_issue_count": count,
            "common_problems": _string_list(result.get("common_problems"), "common_problems"),
            "confirmed_problems": _string_list(result.get("confirmed_problems"), "confirmed_problems"),
            "unresolved_problems": _string_list(result.get("unresolved_problems"), "unresolved_problems"),
            "representative_issues": _string_list(result.get("representative_issues"), "representative_issues"),
            "limitations": _string_list(result.get("limitations"), "limitations"),
        }

    @staticmethod
    def _is_source_archive(asset: dict[str, Any], release: dict[str, Any]) -> bool:
        name = str(asset.get("name") or "").lower()
        url = str(asset.get("download_url") or "")
        if url in {release.get("source_zip_url"), release.get("source_tar_url")}:
            return True
        return bool(re.search(r"(?:^|[._-])source(?:[._-]|$)|source[._-]?code", name)) and name.endswith((".zip", ".tar", ".tar.gz", ".tgz"))

    def _select_asset(self, model: LanguageModel, release: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
        candidates = [
            asset for asset in release["assets"]
            if not self._is_source_archive(asset, release)
        ]
        if not candidates:
            return {"found": False, "reason": "The latest Release has no eligible maintainer-uploaded asset for matching."}
        prompt = {
            "operating_system": request.get("operating_system"),
            "architecture": request.get("architecture"),
            "package_preference": request.get("package_preference"),
            "candidates": [{"index": i, **asset} for i, asset in enumerate(candidates)],
        }
        result = model.json(
            "You are ReleaseAdvisor selecting one maintainer-uploaded Release asset. Infer compatibility from asset names and metadata, respecting operating system, architecture, and package preference. Never select a source-code archive. Return exactly {\"selected_index\": number or null, \"reason\": text}. Use null when no candidate is a defensible match.",
            json.dumps(prompt, ensure_ascii=False),
        )
        selected_index = result.get("selected_index")
        reason = result.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise RuntimeError("Language model returned no asset-selection reason.")
        if selected_index is None:
            return {"found": False, "reason": reason}
        if not isinstance(selected_index, int) or not 0 <= selected_index < len(candidates):
            raise RuntimeError("Language model returned an invalid asset index.")
        return {"found": True, "reason": reason, "asset": candidates[selected_index]}

    def _release_advice(self, model: LanguageModel, release: dict[str, Any], request: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
        version = release["version"]
        if request["analysis_mode"] == "overview":
            summary = model.text(
                "You are ReleaseAdvisor. Summarize only the supplied latest official GitHub Release metadata. Include the version, release name, publication time, key release-note points, and asset count. Never imply that a file was downloaded or installed.",
                json.dumps(release, ensure_ascii=False),
            )
            return {
                "status": "overview",
                "version": version,
                "summary": summary,
                "acquisition_url": "",
                "integrity_guidance": "No file operation was performed. Consult the official Release page before obtaining anything.",
                "limitations": ["This is metadata and release-note guidance only; no asset was inspected locally."],
            }

        if selection["found"]:
            asset = selection["asset"]
            summary = (
                f"The latest Release {version} has a potentially compatible asset: {asset['name']} "
                f"({ _format_bytes(int(asset['size'])) }). Compatibility rationale: {selection['reason']}"
            )
            digest = asset.get("digest") or "No digest was published in the GitHub asset metadata."
            integrity = (
                f"Before using the asset, obtain it yourself from {asset['download_url']} and verify its published digest "
                f"({digest}) with a local trusted hashing tool. Confirm the downloaded bytes and platform match your intent."
            )
            limitations = [
                "Compatibility was inferred from Release asset metadata and naming; the asset was not downloaded or tested locally.",
                "The GitHub-provided source archives were excluded from installable-asset matching.",
            ]
            return {
                "status": "recommended",
                "version": version,
                "summary": summary,
                "acquisition_url": asset["download_url"],
                "integrity_guidance": integrity,
                "limitations": limitations,
                "asset": asset,
            }

        return {
            "status": "no_match",
            "version": version,
            "summary": f"No suitable maintainer-uploaded asset was identified for the requested preferences. {selection['reason']}",
            "acquisition_url": "",
            "integrity_guidance": "No file operation was performed. Do not treat a Source code zip or Source code tar archive as directly installable software by default.",
            "limitations": [
                "No compatible asset could be established from the latest Release metadata.",
                "The Release was not downloaded, and no local compatibility test was performed.",
            ],
        }

    def _parse_release_request(self, model: LanguageModel, answer: str) -> dict[str, Any]:
        result = model.json(
            "Parse the user's ReleaseRequest. The valid exact forms are overview, or asset_match;operating_system;architecture;package_preference. Return JSON with analysis_mode and, only for asset_match, operating_system, architecture, and package_preference. Do not invent missing values.",
            "User's exact answer: " + answer,
        )
        mode = result.get("analysis_mode")
        if mode not in {"overview", "asset_match"}:
            raise RuntimeError("ReleaseRequest analysis_mode must be overview or asset_match.")
        if mode == "overview":
            return {"analysis_mode": "overview"}
        fields = {
            "operating_system": result.get("operating_system"),
            "architecture": result.get("architecture"),
            "package_preference": result.get("package_preference"),
        }
        if fields["operating_system"] not in OPERATING_SYSTEMS:
            raise RuntimeError("ReleaseRequest operating_system is invalid.")
        if fields["architecture"] not in ARCHITECTURES:
            raise RuntimeError("ReleaseRequest architecture is invalid.")
        if fields["package_preference"] not in PACKAGE_PREFERENCES:
            raise RuntimeError("ReleaseRequest package_preference is invalid.")
        return {"analysis_mode": "asset_match", **fields}

    def run(self) -> dict[str, Any]:
        print("GitHubProjectAssistant requires a complete GitHub Repository URL or an explicit owner/repository identifier.")
        print("It can summarize public project information, analyze recent open Issues, and provide Release guidance without downloading files.")
        self.state["project_input"] = input("Enter the GitHub Repository URL or owner/repository: ")
        self.state["input_kind"] = classify_repository_input(self.state["project_input"])

        while self.state["input_kind"] == "unclear" and self.state["repository_input_retry_count"] < 3:
            print("That input does not uniquely identify a Repository. Please provide a complete GitHub Repository URL or explicit owner/repository identifier.")
            self.state["project_input"] = input("Enter the corrected Repository input: ")
            self.state["repository_input_retry_count"] += 1
            self.state["input_kind"] = classify_repository_input(self.state["project_input"])
        self.state["repository_input_limit_exceeded"] = (
            self.state["input_kind"] == "unclear" and self.state["repository_input_retry_count"] >= 3
        )

        if self.state["repository_input_limit_exceeded"]:
            diagnostic = "The Repository input remains unclear after three correction attempts."
            self.state["project_summary"] = (
                "The target Repository could not be determined. GitHub was not accessed, and no Issue or Release analysis was performed."
            )
            print(diagnostic)
            print(self.state["project_summary"])
            return {"project_summary": self.state["project_summary"]}

        self.state["selected_repository"] = parse_github_repository_input(self.state["project_input"])
        selected = self.state["selected_repository"]
        self.state["project_overview"] = self.github.get_project_overview(selected["owner"], selected["repository"])
        overview = self.state["project_overview"]
        self.state["repository_found"] = bool(overview["found"])

        if not self.state["repository_found"]:
            self.state["project_summary"] = (
                f"The explicitly identified Repository {selected['repository_url']} was not found on GitHub. "
                "It was not reinterpreted as a network, authentication, rate-limit, or service failure."
            )
            print(self.state["project_summary"])
            return {"project_summary": self.state["project_summary"]}

        model = LanguageModel()
        self.state["project_summary"] = self._create_project_summary(model, overview)
        print("\nProject summary:\n" + self.state["project_summary"])

        issue_answer = input("Would you like an analysis of recently updated open Issues? ")
        self.state["issue_analysis_choice"] = self._ask_yes_no(
            model, "Would you like an analysis of recently updated open Issues?", issue_answer
        )
        if self.state["issue_analysis_choice"] == "yes":
            self.state["issue_information"] = self.github.get_issue_information(selected["owner"], selected["repository"])
            self.state["issue_analysis_result"] = self._analyze_issues(model, self.state["issue_information"])

        release_answer = input("Would you like guidance about the latest official Release? ")
        self.state["release_analysis_choice"] = self._ask_yes_no(
            model, "Would you like guidance about the latest official Release?", release_answer
        )
        if self.state["release_analysis_choice"] == "yes":
            request_answer = input(
                "Enter ReleaseRequest as exactly 'overview' or 'asset_match;operating_system;architecture;package_preference': "
            )
            self.state["release_request"] = self._parse_release_request(model, request_answer)
            self.state["release_information"] = self.github.get_release(selected["owner"], selected["repository"])
            release = self.state["release_information"]
            if self.state["release_request"]["analysis_mode"] == "asset_match":
                self.state["asset_selection"] = self._select_asset(model, release, self.state["release_request"])
            else:
                self.state["asset_selection"] = None
            self.state["release_advice"] = self._release_advice(
                model, release, self.state["release_request"], self.state["asset_selection"] or {"found": False, "reason": "Overview requested."}
            )

        print("\nFinal result:")
        print("Project summary:\n" + self.state["project_summary"])
        if self.state["issue_analysis_choice"] == "yes":
            print("\nIssue analysis:\n" + json.dumps(self.state["issue_analysis_result"], ensure_ascii=False, indent=2))
        if self.state["release_analysis_choice"] == "yes":
            print("\nRelease advice:\n" + json.dumps(self.state["release_advice"], ensure_ascii=False, indent=2))
        result = {"project_summary": self.state["project_summary"]}
        if self.state["issue_analysis_result"] is not None:
            result["issue_analysis_result"] = self.state["issue_analysis_result"]
        if self.state["release_advice"] is not None:
            result["release_advice"] = self.state["release_advice"]
        return result


def main() -> dict[str, Any]:
    try:
        return GitHubProjectAssistant().run()
    except (EOFError, KeyboardInterrupt):
        print("Execution stopped before the requested interaction was completed.")
        return {"error": "Execution stopped before the requested interaction was completed."}
    except Exception as exc:
        message = f"Execution failed: {type(exc).__name__}: {exc}"
        print(message)
        return {"error": message}


if __name__ == "__main__":
    main()
