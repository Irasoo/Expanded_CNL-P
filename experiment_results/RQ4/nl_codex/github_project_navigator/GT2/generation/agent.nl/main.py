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


NO_PROJECT_SUMMARY = (
    "No project summary is available because the target Repository was not resolved."
)
INPUT_KINDS = {"repository_url", "repository_name", "unclear"}
OPERATING_SYSTEMS = {"windows", "macos", "linux", "other"}
ARCHITECTURES = {"x64", "arm64", "unknown"}
PACKAGE_PREFERENCES = {"installer", "portable", "archive", "any"}


def _load_local_env() -> None:
    """Load simple KEY=VALUE entries from the current directory's .env."""
    env_path = Path.cwd() / ".env"
    if not env_path.is_file():
        return
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"The local .env file could not be read: {exc}") from exc
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


class RuntimeConfig:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    @classmethod
    def from_environment(cls) -> "RuntimeConfig":
        _load_local_env()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        base_url = os.getenv("BASE_URL", "").strip()
        model = (
            os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip()
            or os.getenv("OPENAI_MODEL", "").strip()
        )
        missing = []
        if not api_key:
            missing.append("OPENAI_API_KEY")
        if not base_url:
            missing.append("BASE_URL")
        if not model:
            missing.append("CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL")
        if missing:
            raise RuntimeError(
                "Runtime language-model configuration is missing: "
                + ", ".join(missing)
                + ". Set these values in .env or the process environment."
            )
        return cls(api_key, base_url, model)


class LanguageModel:
    """Small wrapper for the required official OpenAI Responses API client."""

    def __init__(self) -> None:
        self.config = RuntimeConfig.from_environment()
        from openai import OpenAI

        self.client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
        )

    def _request(self, instruction: str) -> str:
        response = self.client.responses.create(
            model=self.config.model,
            reasoning={"effort": "high"},
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are an evidence-based GitHub project assistant. "
                        "Follow the requested output contract exactly. Do not invent "
                        "facts that are absent from the supplied GitHub data."
                    ),
                },
                {"role": "user", "content": instruction},
            ],
        )
        output = getattr(response, "output_text", "")
        if not isinstance(output, str) or not output.strip():
            raise RuntimeError("The language model returned an empty response.")
        return output.strip()

    def json(self, instruction: str) -> dict[str, Any]:
        raw = self._request(instruction)
        candidate = raw.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate).strip()
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", candidate, flags=re.DOTALL)
            if not match:
                raise RuntimeError("The language model returned invalid JSON.") from None
            try:
                value = json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                raise RuntimeError("The language model returned invalid JSON.") from exc
        if not isinstance(value, dict):
            raise RuntimeError("The language model returned a JSON value with the wrong type.")
        return value


def _text(value: Any) -> str:
    return value if isinstance(value, str) else str(value or "")


def _number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("GitHub returned a malformed numeric field.") from exc


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


def _github_json(url: str, *, accept: str | None = None) -> Any:
    headers = _github_headers()
    if accept:
        headers["Accept"] = accept
    try:
        request = Request(url, headers=headers, method="GET")
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError:
        raise
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GitHub data could not be read: {type(exc).__name__}: {exc}") from exc


def get_github_project_overview(owner: str, repository: str) -> dict[str, Any]:
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
    base = "https://api.github.com/repos/" + quote(owner_value, safe="") + "/" + quote(repository_value, safe="")
    try:
        metadata = _github_json(base)
    except HTTPError as exc:
        if exc.code == 404:
            return empty
        raise RuntimeError(f"GitHub repository lookup returned HTTP {exc.code}.") from exc
    if not isinstance(metadata, dict):
        raise RuntimeError("GitHub returned malformed repository metadata.")

    readme = ""
    try:
        request = Request(
            base + "/readme",
            headers=_github_headers() | {"Accept": "application/vnd.github.raw+json"},
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
        raise RuntimeError(f"GitHub README could not be read: {type(exc).__name__}: {exc}") from exc

    license_data = metadata.get("license")
    license_name = (
        _text(license_data.get("spdx_id") or license_data.get("name"))
        if isinstance(license_data, dict)
        else ""
    )
    raw_topics = metadata.get("topics")
    topics = [item for item in raw_topics if isinstance(item, str)] if isinstance(raw_topics, list) else []
    return {
        "found": True,
        "full_name": _text(metadata.get("full_name")),
        "repository_url": _text(metadata.get("html_url")),
        "description": _text(metadata.get("description")),
        "readme": readme,
        "license": license_name,
        "primary_language": _text(metadata.get("language")),
        "topics": topics,
        "stars": _number(metadata.get("stargazers_count")),
        "forks": _number(metadata.get("forks_count")),
        "open_issues": _number(metadata.get("open_issues_count")),
        "archived": bool(metadata.get("archived", False)),
        "updated_at": _text(metadata.get("updated_at")),
    }


def get_github_issue_information(owner: str, repository: str) -> dict[str, Any]:
    if not str(owner).strip() or not str(repository).strip():
        raise ValueError("GitHub owner and repository are required.")
    url = (
        "https://api.github.com/repos/"
        + quote(str(owner).strip(), safe="")
        + "/"
        + quote(str(repository).strip(), safe="")
        + "/issues?"
        + urlencode({"state": "open", "sort": "updated", "direction": "desc", "per_page": 100, "page": 1})
    )
    try:
        payload = _github_json(url)
    except HTTPError as exc:
        raise RuntimeError(f"GitHub Issue lookup returned HTTP {exc.code}.") from exc
    if not isinstance(payload, list):
        raise RuntimeError("GitHub returned malformed Issue data.")
    issues = []
    for item in payload:
        if not isinstance(item, dict) or "pull_request" in item:
            continue
        raw_labels = item.get("labels", [])
        labels = [
            _text(label.get("name"))
            for label in raw_labels
            if isinstance(label, dict) and label.get("name")
        ] if isinstance(raw_labels, list) else []
        issues.append(
            "\n".join(
                [
                    f"#{_number(item.get('number'))}: {_text(item.get('title'))}",
                    f"URL: {_text(item.get('html_url'))}",
                    f"State: {_text(item.get('state'))}",
                    f"Updated at: {_text(item.get('updated_at'))}",
                    f"Comments: {_number(item.get('comments'))}",
                    f"Labels: {', '.join(labels) if labels else 'none'}",
                    f"Body: {_text(item.get('body'))[:4000]}",
                ]
            )
        )
    return {"analyzed_issue_count": len(issues), "issues": issues}


def get_github_release(owner: str, repository: str) -> dict[str, Any]:
    if not str(owner).strip() or not str(repository).strip():
        raise ValueError("GitHub owner and repository are required.")
    base = (
        "https://api.github.com/repos/"
        + quote(str(owner).strip(), safe="")
        + "/"
        + quote(str(repository).strip(), safe="")
        + "/releases/latest"
    )
    try:
        selected = _github_json(base)
    except HTTPError as exc:
        raise RuntimeError(f"GitHub Release lookup returned HTTP {exc.code}.") from exc
    if not isinstance(selected, dict):
        raise RuntimeError("GitHub returned malformed Release data.")
    raw_assets = selected.get("assets", [])
    assets = [
        {
            "name": _text(asset.get("name")),
            "download_url": _text(asset.get("browser_download_url")),
            "size": _number(asset.get("size")),
            "digest": _text(asset.get("digest")),
        }
        for asset in raw_assets
        if isinstance(asset, dict)
    ] if isinstance(raw_assets, list) else []
    return {
        "version": _text(selected.get("tag_name")),
        "release_name": _text(selected.get("name")),
        "release_notes": _text(selected.get("body"))[:50000],
        "published_at": _text(selected.get("published_at")),
        "assets": assets,
        "source_zip_url": _text(selected.get("zipball_url")),
        "source_tar_url": _text(selected.get("tarball_url")),
    }


def _require_string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError(f"The language model returned an invalid {field} field.")
    return value


class GitHubProjectAssistant:
    def __init__(self) -> None:
        self.project_input = ""
        self.input_kind = "unclear"
        self.repository_input_retry_count = 0
        self.repository_input_limit_exceeded = False
        self.selected_repository: dict[str, str] | None = None
        self.project_overview: dict[str, Any] | None = None
        self.repository_found = False
        self.project_summary = NO_PROJECT_SUMMARY
        self.issue_analysis_choice = "no"
        self.issue_information: dict[str, Any] | None = None
        self.issue_analysis_result: dict[str, Any] | None = None
        self.release_analysis_choice = "no"
        self.release_request: dict[str, str] | None = None
        self.release_information: dict[str, Any] | None = None
        self.asset_selection: dict[str, Any] | None = None
        self.release_advice: dict[str, Any] | None = None
        self._language_model: LanguageModel | None = None

    @property
    def language_model(self) -> LanguageModel:
        if self._language_model is None:
            self._language_model = LanguageModel()
        return self._language_model

    @staticmethod
    def _ask(prompt: str) -> str:
        print(prompt)
        try:
            return input("> ").strip()
        except EOFError as exc:
            raise RuntimeError("Standard input ended before the requested answer was received.") from exc

    def _interpret_yes_no(self, answer: str, context: str) -> str:
        result = self.language_model.json(
            "Interpret the user's single answer for this question. Return only JSON "
            '{"choice":"yes"} or {"choice":"no"}. Do not infer a choice from missing '
            f"information. Question context: {context}\nUser answer: {answer}"
        )
        choice = result.get("choice")
        if choice not in {"yes", "no"}:
            raise RuntimeError("The language model returned an invalid yes/no interpretation.")
        return choice

    def _summarize_project(self) -> str:
        assert self.project_overview is not None
        result = self.language_model.json(
            "Create a clear English project overview from the supplied public GitHub data. "
            "Return only JSON with one string field named summary. Explain project name, "
            "purpose, core capabilities, typical use cases, intended users, primary "
            "technology, execution or installation entry points, license, maintenance "
            "status, and important README limitations. Do not merely copy the README. "
            "Do not judge quality from stars or open issue count alone.\n\n"
            + json.dumps(self.project_overview, ensure_ascii=False)
        )
        summary = result.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise RuntimeError("The language model returned an invalid project summary.")
        return summary.strip()

    def _analyze_issues(self) -> dict[str, Any]:
        assert self.selected_repository is not None
        self.issue_information = get_github_issue_information(
            self.selected_repository["owner"], self.selected_repository["repository"]
        )
        result = self.language_model.json(
            "Analyze the recently updated open GitHub Issues supplied below. Return only "
            "JSON with these fields: analyzed_issue_count (number), common_problems "
            "(list of strings), confirmed_problems (list of strings), unresolved_problems "
            "(list of strings), representative_issues (list of strings), and limitations "
            "(list of strings). Distinguish repeated concerns, isolated reports, "
            "maintainer-confirmed problems, and unresolved reports. Select a small set of "
            "representative Issues. Never describe one user report as a general project "
            "problem. State the actual sample scope and what it cannot establish. Use only "
            "the supplied data.\n\n"
            + json.dumps(self.issue_information, ensure_ascii=False)
        )
        lists = [
            "common_problems",
            "confirmed_problems",
            "unresolved_problems",
            "representative_issues",
            "limitations",
        ]
        for field in lists:
            result[field] = _require_string_list(result.get(field), field)
        try:
            count = int(result.get("analyzed_issue_count"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("The language model returned an invalid Issue count.") from exc
        if count != self.issue_information["analyzed_issue_count"]:
            raise RuntimeError("The language model changed the Issue sample count.")
        result["analyzed_issue_count"] = count
        return result

    @staticmethod
    def _parse_release_request(value: str) -> dict[str, str]:
        if value == "overview":
            return {"analysis_mode": "overview"}
        parts = value.split(";")
        if (
            len(parts) != 4
            or parts[0] != "asset_match"
            or parts[1] not in OPERATING_SYSTEMS
            or parts[2] not in ARCHITECTURES
            or parts[3] not in PACKAGE_PREFERENCES
        ):
            raise RuntimeError(
                "Invalid ReleaseRequest. Use exactly 'overview' or "
                "'asset_match;operating_system;architecture;package_preference'."
            )
        return {
            "analysis_mode": "asset_match",
            "operating_system": parts[1],
            "architecture": parts[2],
            "package_preference": parts[3],
        }

    def _select_asset(self) -> dict[str, Any]:
        assert self.release_information is not None
        assert self.release_request is not None
        assets = self.release_information["assets"]
        result = self.language_model.json(
            "Select the most suitable maintainer-uploaded Release Asset for the stated "
            "preferences. Return only JSON with found (boolean), asset_index (number or "
            "null), and reason (string). Never select GitHub's automatically generated "
            "source_zip_url or source_tar_url as installable software by default. Use "
            "only the listed assets and do not invent compatibility. A package is a match "
            "only when its filename and available evidence support the requested platform, "
            "architecture, and package preference.\nPreferences:\n"
            + json.dumps(self.release_request, ensure_ascii=False)
            + "\nAssets:\n"
            + json.dumps(assets, ensure_ascii=False)
        )
        found = result.get("found")
        reason = result.get("reason")
        index = result.get("asset_index")
        if not isinstance(found, bool) or not isinstance(reason, str):
            raise RuntimeError("The language model returned invalid AssetSelection data.")
        if found:
            if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(assets):
                raise RuntimeError("The language model selected an invalid Release Asset.")
            asset = assets[index]
            return {"found": True, "reason": reason, "asset": asset}
        return {"found": False, "reason": reason}

    def _release_advice_for_overview(self) -> dict[str, Any]:
        assert self.release_information is not None
        result = self.language_model.json(
            "Write a concise English overview of the latest official GitHub Release. "
            "Return only JSON with summary (string), integrity_guidance (string), and "
            "limitations (list of strings). Include version, release name, publication "
            "time, key Release Notes, and Asset count. Do not claim any file was obtained. "
            "Use only supplied metadata.\n\n"
            + json.dumps(self.release_information, ensure_ascii=False)
        )
        return {
            "status": "overview",
            "version": self.release_information["version"],
            "summary": self._checked_string(result, "summary")
            + " No file operation was performed.",
            "acquisition_url": self._latest_release_url(),
            "integrity_guidance": self._checked_string(result, "integrity_guidance"),
            "limitations": _require_string_list(result.get("limitations"), "limitations"),
        }

    def _release_advice_for_asset(self) -> dict[str, Any]:
        assert self.release_information is not None
        assert self.release_request is not None
        self.asset_selection = self._select_asset()
        asset = self.asset_selection.get("asset")
        if asset is None:
            return {
                "status": "no_match",
                "version": self.release_information["version"],
                "summary": (
                    "No compatible maintainer-uploaded Release Asset was identified. "
                    + self.asset_selection["reason"]
                    + " No file was downloaded, created, installed, extracted, or executed."
                ),
                "acquisition_url": self._latest_release_url(),
                "integrity_guidance": "Do not treat the automatically generated source archives as installable software by default.",
                "limitations": [
                    "Compatibility was assessed only from the latest Release metadata and listed Asset names.",
                    "No file was downloaded or inspected.",
                ],
            }
        result = self.language_model.json(
            "Create English Release Asset guidance. Return only JSON with summary (string), "
            "integrity_guidance (string), and limitations (list of strings). Include the "
            "asset name, size, URL, digest, compatibility rationale, and user-side "
            "verification guidance. Do not say the file was downloaded, installed, "
            "extracted, or executed. Use only the supplied data.\n\nRequest:\n"
            + json.dumps(self.release_request, ensure_ascii=False)
            + "\nRelease:\n"
            + json.dumps(self.release_information, ensure_ascii=False)
            + "\nSelected Asset:\n"
            + json.dumps(asset, ensure_ascii=False)
            + "\nSelection reason:\n"
            + self.asset_selection["reason"]
        )
        return {
            "status": "recommended",
            "version": self.release_information["version"],
            "summary": self._checked_string(result, "summary")
            + " No file was downloaded, created, installed, extracted, or executed.",
            "acquisition_url": asset["download_url"],
            "integrity_guidance": self._checked_string(result, "integrity_guidance"),
            "limitations": _require_string_list(result.get("limitations"), "limitations"),
            "asset": asset,
        }

    @staticmethod
    def _checked_string(value: dict[str, Any], field: str) -> str:
        result = value.get(field)
        if not isinstance(result, str) or not result.strip():
            raise RuntimeError(f"The language model returned an invalid {field} field.")
        return result.strip()

    def _latest_release_url(self) -> str:
        assert self.selected_repository is not None
        return (
            f"https://github.com/{self.selected_repository['owner']}/"
            f"{self.selected_repository['repository']}/releases/latest"
        )

    def run(self) -> dict[str, Any]:
        print(
            "GitHubProjectAssistant requires a complete GitHub Repository URL or an "
            "explicit owner/repository identifier. It can summarize public project "
            "information, analyze recent open Issues, and provide Release guidance "
            "without downloading files."
        )
        self.project_input = self._ask(
            "Enter a complete GitHub Repository URL or an explicit owner/repository identifier."
        )
        self.input_kind = classify_repository_input(self.project_input)
        while self.input_kind == "unclear" and self.repository_input_retry_count < 3:
            self.project_input = self._ask(
                "The current input does not uniquely identify a Repository. Enter a complete "
                "GitHub Repository URL or an explicit owner/repository identifier."
            )
            self.repository_input_retry_count += 1
            self.input_kind = classify_repository_input(self.project_input)
        self.repository_input_limit_exceeded = (
            self.input_kind == "unclear" and self.repository_input_retry_count >= 3
        )
        if self.repository_input_limit_exceeded:
            self.project_summary = "The Repository input remains unclear after three correction attempts."
            print(self.project_summary)
            print("GitHub was not accessed, and no Issue or Release analysis was performed.")
            return {"project_summary": self.project_summary}

        self.selected_repository = parse_github_repository_input(self.project_input)
        self.project_overview = get_github_project_overview(
            self.selected_repository["owner"], self.selected_repository["repository"]
        )
        self.repository_found = bool(self.project_overview["found"])
        if not self.repository_found:
            self.project_summary = (
                f"The explicitly identified Repository "
                f"{self.selected_repository['owner']}/{self.selected_repository['repository']} "
                "was not found on GitHub. This is a repository-not-found result, not a "
                "network, authentication, rate-limit, or service diagnosis."
            )
            print(self.project_summary)
            return {"project_summary": self.project_summary}

        self.project_summary = self._summarize_project()
        print("\nProject summary:\n" + self.project_summary)
        self.issue_analysis_choice = self._interpret_yes_no(
            self._ask("Do you want an analysis of recently updated open Issues? Answer in one response."),
            "whether to analyze recently updated open Issues",
        )
        if self.issue_analysis_choice == "yes":
            self.issue_analysis_result = self._analyze_issues()
            print("\nIssue analysis:\n" + json.dumps(self.issue_analysis_result, indent=2, ensure_ascii=False))

        self.release_analysis_choice = self._interpret_yes_no(
            self._ask("Do you want guidance about the latest official Release? Answer in one response."),
            "whether to provide guidance about the latest official Release",
        )
        if self.release_analysis_choice == "yes":
            request_text = self._ask(
                "Enter either 'overview' or "
                "'asset_match;operating_system;architecture;package_preference'. "
                "Use windows/macos/linux/other, x64/arm64/unknown, and "
                "installer/portable/archive/any for the latter format."
            )
            self.release_request = self._parse_release_request(request_text)
            self.release_information = get_github_release(
                self.selected_repository["owner"], self.selected_repository["repository"]
            )
            if self.release_request["analysis_mode"] == "overview":
                self.release_advice = self._release_advice_for_overview()
            else:
                self.release_advice = self._release_advice_for_asset()
            print("\nRelease advice:\n" + json.dumps(self.release_advice, indent=2, ensure_ascii=False))

        final_result: dict[str, Any] = {"project_summary": self.project_summary}
        if self.issue_analysis_choice == "yes":
            final_result["issue_analysis_result"] = self.issue_analysis_result
        if self.release_analysis_choice == "yes":
            final_result["release_advice"] = self.release_advice
        print("\nFinal result:\n" + json.dumps(final_result, indent=2, ensure_ascii=False))
        return final_result


def main() -> dict[str, Any]:
    """Initialize the Agent, run the terminal workflow, and return its result."""
    try:
        return GitHubProjectAssistant().run()
    except Exception as exc:
        message = f"Execution failure: {exc}"
        print(message, file=sys.stderr)
        return {"error": message}


if __name__ == "__main__":
    main()
