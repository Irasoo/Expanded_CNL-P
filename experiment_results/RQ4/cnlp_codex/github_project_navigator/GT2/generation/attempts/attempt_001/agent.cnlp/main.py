"""CNL-P generated terminal Agent for read-only GitHub project guidance."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from openai import OpenAI

from github_api import (
    get_github_issue_information,
    get_github_project_overview,
    get_github_release,
    parse_github_repository_input,
)


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries without overriding process environment."""
    path = ".env"
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return
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


PERSONA_CONTEXT = """You are GitHubProjectAssistant, a cautious and evidence-based assistant for GitHub project information, Issue risks, and Release compatibility.

Role and responsibility: confirm the target Repository; summarize repository metadata and README content; analyze recent open Issues; and provide either a latest Release overview or Asset compatibility guidance.
Audience: developers and software users who can provide a complete GitHub Repository URL or explicit owner/repository identifier. Use clear English and distinguish repository facts, limited Issue-sample analysis, Release summaries, and compatibility guidance.
Concepts: a Repository is uniquely identified by owner and repository; an Issue insight must concern repeated, confirmed, and unresolved concerns from recently updated open Issues; a Release is the latest official version published through GitHub Releases; a Release Asset is uploaded by maintainers; GitHub's source zip/tar archives are automatically generated source archives.
Constraints: never guess a repository; use only an explicit URL or owner/repository identifier; read GitHub information only; never create, modify, close, or comment on GitHub resources; never download, write, install, extract, or execute release files; never judge quality from stars or open Issue count alone; do not generalize from one report; state the actual Issue sample size and limitations; analyze only the latest official public Release; execution failures such as network, rate limit, authentication, service, and malformed-response errors are not business states.
"""


class AgentExecutionError(RuntimeError):
    """An execution/configuration failure, distinct from a business branch."""


class RuntimeLLM:
    def __init__(self) -> None:
        _load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        base_url = os.getenv("BASE_URL", "").strip()
        model = (
            os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip()
            or os.getenv("OPENAI_MODEL", "").strip()
        )
        if not api_key:
            raise AgentExecutionError(
                "OPENAI_API_KEY is not configured in .env or the current environment."
            )
        if not model:
            raise AgentExecutionError(
                "Set CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL in .env or the current environment."
            )
        client_args: dict[str, str] = {"api_key": api_key}
        if base_url:
            client_args["base_url"] = base_url
        self.client = OpenAI(**client_args)
        self.model = model

    def json_call(self, instruction: str, payload: Any) -> dict[str, Any]:
        request = (
            f"{PERSONA_CONTEXT}\n\n{instruction}\n\n"
            "Return only a valid JSON object. Do not use Markdown fences.\n"
            "Input data follows:\n"
            f"{json.dumps(payload, ensure_ascii=True, indent=2)}"
        )
        try:
            response = self.client.responses.create(
                model=self.model,
                reasoning={"effort": "high"},
                input=[
                    {"role": "system", "content": PERSONA_CONTEXT},
                    {"role": "user", "content": request},
                ],
                text={"format": {"type": "json_object"}},
            )
        except Exception as exc:
            raise AgentExecutionError(
                f"Runtime language-model call failed: {type(exc).__name__}: {exc}"
            ) from exc
        raw = getattr(response, "output_text", "")
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise AgentExecutionError(
                "Runtime language-model returned malformed JSON."
            ) from exc
        if not isinstance(value, dict):
            raise AgentExecutionError("Runtime language-model returned a non-object JSON value.")
        return value


def _text(value: Any) -> str:
    return value if isinstance(value, str) else str(value or "")


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(item) for item in value]


def _yes_no(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"yes", "no"}:
        raise ValueError("Please answer exactly yes or no for this INPUT Command.")
    return normalized


def classify_repository_input(value: str) -> str:
    try:
        parse_github_repository_input(value)
    except (TypeError, ValueError):
        return "unclear"
    return "repository_url" if "://" in value.strip() else "repository_name"


def parse_release_request(value: str) -> dict[str, Any]:
    normalized = value.strip()
    if normalized == "overview":
        return {"analysis_mode": "overview"}
    fields = [part.strip() for part in normalized.split(";")]
    if len(fields) != 4 or fields[0] != "asset_match":
        raise ValueError(
            "ReleaseRequest must be overview or asset_match;operating_system;architecture;package_preference."
        )
    allowed = [
        {"windows", "macos", "linux", "other"},
        {"x64", "arm64", "unknown"},
        {"installer", "portable", "archive", "any"},
    ]
    if any(item not in allowed[index] for index, item in enumerate(fields[1:])):
        raise ValueError(
            "ReleaseRequest contains an invalid operating system, architecture, or package preference."
        )
    return {
        "analysis_mode": "asset_match",
        "operating_system": fields[1],
        "architecture": fields[2],
        "package_preference": fields[3],
    }


def _format_size(size: Any) -> str:
    try:
        number = int(size)
    except (TypeError, ValueError):
        number = 0
    if number < 1024:
        return f"{number} bytes"
    if number < 1024 * 1024:
        return f"{number / 1024:.1f} KiB"
    if number < 1024 * 1024 * 1024:
        return f"{number / (1024 * 1024):.1f} MiB"
    return f"{number / (1024 * 1024 * 1024):.2f} GiB"


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


class IssueAnalyzer:
    def __init__(self, llm: RuntimeLLM) -> None:
        self.llm = llm
        self.issue_information: dict[str, Any] = {}

    def run(self, selected_repository: dict[str, str]) -> dict[str, Any]:
        information = get_github_issue_information(
            selected_repository["owner"], selected_repository["repository"]
        )
        self.issue_information = information
        result = self.llm.json_call(
            "Analyze the recently updated open Issue sample. Return keys "
            "analyzed_issue_count (integer), common_problems (string array), "
            "confirmed_problems (string array), unresolved_problems (string array), "
            "representative_issues (string array), and limitations (string array). "
            "Distinguish repeated concerns from isolated reports, and only call a "
            "problem confirmed when the supplied evidence supports that wording. "
            "Mention the actual sample size and its scope in limitations.",
            information,
        )
        result["analyzed_issue_count"] = int(information.get("analyzed_issue_count", 0))
        for key in (
            "common_problems",
            "confirmed_problems",
            "unresolved_problems",
            "representative_issues",
            "limitations",
        ):
            result[key] = _string_list(result.get(key))
        return result


class ReleaseAdvisor:
    def __init__(self, llm: RuntimeLLM) -> None:
        self.llm = llm
        self.release_information: dict[str, Any] = {}
        self.asset_selection: dict[str, Any] = {}

    def _select_asset(
        self, release: dict[str, Any], release_request: dict[str, Any]
    ) -> dict[str, Any]:
        assets = [asset for asset in release.get("assets", []) if isinstance(asset, dict)]
        if not assets:
            return {
                "found": False,
                "reason": "The latest official Release has no maintainer-uploaded Assets.",
            }
        decision = self.llm.json_call(
            "Select the single most suitable maintainer-uploaded Release Asset for the "
            "requested operating system, processor architecture, and package preference. "
            "Return keys found (boolean), asset_name (string), asset_download_url (string), "
            "and reason (string). If compatibility is not supported by the supplied metadata, "
            "set found to false rather than guessing. The candidate list contains only GitHub "
            "Release Assets; never select or recommend automatically generated source zip/tar URLs.",
            {"request": release_request, "assets": assets},
        )
        found = decision.get("found")
        if not isinstance(found, bool):
            raise AgentExecutionError("Asset selection returned a non-boolean found value.")
        reason = _text(decision.get("reason"))
        if not found:
            return {
                "found": False,
                "reason": reason or "No compatible maintainer-uploaded Asset was identified.",
            }
        selected_name = _text(decision.get("asset_name"))
        selected_url = _text(decision.get("asset_download_url"))
        matches = [
            asset
            for asset in assets
            if _text(asset.get("name")) == selected_name
            and _text(asset.get("download_url")) == selected_url
        ]
        if len(matches) != 1:
            raise AgentExecutionError(
                "Asset selection did not identify exactly one supplied Release Asset."
            )
        return {
            "found": True,
            "asset": matches[0],
            "reason": reason or "The selected Asset matches the requested platform preferences.",
        }

    def run(
        self,
        selected_repository: dict[str, str],
        release_request: dict[str, Any],
    ) -> dict[str, Any]:
        release = get_github_release(
            selected_repository["owner"], selected_repository["repository"]
        )
        self.release_information = release
        if release_request["analysis_mode"] == "overview":
            generated = self.llm.json_call(
                "Create a concise latest Release overview. Return keys status, version, "
                "summary, acquisition_url, integrity_guidance, and limitations. Set "
                "status to overview. Include the Release name, publication time, key "
                "notes, and asset count. State explicitly that no file operation was performed. "
                "Do not invent missing facts.",
                release,
            )
            generated["status"] = "overview"
            generated["version"] = _text(generated.get("version") or release.get("version"))
            generated["summary"] = (
                _text(generated.get("summary")).rstrip()
                + "\n\nNo file was downloaded, created, installed, extracted, or executed."
            ).strip()
            generated["acquisition_url"] = ""
            generated["integrity_guidance"] = _text(generated.get("integrity_guidance"))
            generated["limitations"] = _string_list(generated.get("limitations"))
            return generated

        selection = self._select_asset(release, release_request)
        self.asset_selection = selection
        if selection.get("found"):
            selection_context: dict[str, Any] = {
                "release": release,
                "request": release_request,
                "selection": selection,
            }
        else:
            selection_context = {"release": release, "request": release_request, "selection": selection}
        generated = self.llm.json_call(
            "Create Release compatibility guidance from the supplied deterministic "
            "asset selection. Return keys status, version, summary, acquisition_url, "
            "integrity_guidance, and limitations. Use status recommended only when "
            "selection.found is true, otherwise no_match. For a recommendation include "
            "the exact asset name, size, URL, digest when present, and compatibility "
            "rationale. Explicitly state that no file was downloaded, created, installed, "
            "extracted, or executed. Never call GitHub source zip/tar URLs installable assets.",
            selection_context,
        )
        generated["status"] = "recommended" if selection.get("found") else "no_match"
        generated["version"] = _text(generated.get("version") or release.get("version"))
        generated_summary = _text(generated.get("summary") or selection.get("reason"))
        generated["integrity_guidance"] = _text(generated.get("integrity_guidance"))
        generated["limitations"] = _string_list(generated.get("limitations"))
        if selection.get("found"):
            asset = selection["asset"]
            digest = _text(asset.get("digest")) or "not supplied by GitHub"
            facts = (
                f"Recommended asset: {_text(asset.get('name'))}\n"
                f"Size: {_format_size(asset.get('size'))} ({int(asset.get('size') or 0)} bytes)\n"
                f"URL: {_text(asset.get('download_url'))}\n"
                f"Digest: {digest}"
            )
            generated["summary"] = (
                facts
                + "\n\n"
                + generated_summary.rstrip()
                + "\n\nNo file was downloaded, created, installed, extracted, or executed."
            ).strip()
            generated["acquisition_url"] = _text(asset.get("download_url"))
            generated["asset"] = asset
        else:
            generated["summary"] = (
                generated_summary.rstrip()
                + "\n\nNo file was downloaded, created, installed, extracted, or executed."
            ).strip()
            generated["acquisition_url"] = ""
        return generated


class ProjectNavigator:
    def __init__(self, state: AgentState, llm_factory: Callable[[], RuntimeLLM]) -> None:
        self.state = state
        self.llm_factory = llm_factory

    @staticmethod
    def display(value: Any) -> None:
        if isinstance(value, str):
            print(value)
        else:
            print(json.dumps(value, ensure_ascii=False, indent=2))

    @staticmethod
    def read(prompt: str) -> str:
        return input(prompt + "\n> ")

    def _classify_and_retry(self) -> None:
        self.state.input_kind = classify_repository_input(self.state.project_input)
        while (
            self.state.input_kind == "unclear"
            and self.state.repository_input_retry_count < 3
        ):
            self.state.project_input = self.read(
                "The current input does not uniquely identify a Repository. "
                "Please enter a complete GitHub Repository URL or explicit owner/repository identifier."
            ).strip()
            self.state.repository_input_retry_count += 1
            self.state.input_kind = classify_repository_input(self.state.project_input)
        self.state.repository_input_limit_exceeded = (
            self.state.input_kind == "unclear"
            and self.state.repository_input_retry_count >= 3
        )

    def _create_project_summary(self) -> str:
        generated = self.llm_factory().json_call(
            "Use the repository metadata and README to explain the project name, "
            "purpose, core capabilities, typical use cases, intended users, primary "
            "technology, execution or installation entry points, license, maintenance "
            "status, and important README limitations. Return one key named summary. "
            "Do not merely copy the README. Do not infer quality from stars or open Issue count. "
            "Separate facts from cautious interpretation and do not invent absent details.",
            self.state.project_overview,
        )
        summary = _text(generated.get("summary"))
        if not summary:
            raise AgentExecutionError("Runtime language-model returned an empty project summary.")
        return summary

    def run(self) -> dict[str, Any]:
        self.display(
            "This Agent requires a complete GitHub Repository URL or explicit "
            "owner/repository identifier. It can summarize public project information, "
            "analyze recent open Issues, and provide Release guidance without downloading files."
        )
        self.state.project_input = self.read(
            "Enter a complete GitHub Repository URL or owner/repository identifier:"
        ).strip()
        self._classify_and_retry()

        if self.state.repository_input_limit_exceeded:
            print("[LOG] The Repository input remains unclear after three correction attempts.")
            self.state.project_summary = (
                "The target Repository could not be determined after three correction attempts. "
                "GitHub was not accessed, and no Issue or Release analysis was performed."
            )
            self.display(self.state.project_summary)
            return self._outputs()

        self.state.selected_repository = parse_github_repository_input(self.state.project_input)
        self.state.project_overview = get_github_project_overview(
            self.state.selected_repository["owner"], self.state.selected_repository["repository"]
        )
        self.state.repository_found = bool(self.state.project_overview.get("found"))

        if not self.state.repository_found:
            self.state.project_summary = (
                "The explicitly identified Repository "
                f"{self.state.selected_repository['owner']}/{self.state.selected_repository['repository']} "
                "was not found on GitHub. This is a repository-not-found result, not a network, "
                "authentication, rate-limit, or service failure."
            )
            self.display(self.state.project_summary)
            return self._outputs()

        self.state.project_summary = self._create_project_summary()
        self.display(self.state.project_summary)

        self.state.issue_analysis_choice = _yes_no(
            self.read("Would you like an analysis of recently updated open Issues? (yes/no)")
        )
        if self.state.issue_analysis_choice == "yes":
            issue_worker = IssueAnalyzer(self.llm_factory())
            self.state.issue_analysis_result = issue_worker.run(self.state.selected_repository)
            self.state.issue_information = issue_worker.issue_information

        self.state.release_analysis_choice = _yes_no(
            self.read("Would you like guidance about the latest official Release? (yes/no)")
        )
        if self.state.release_analysis_choice == "yes":
            self.state.release_request = parse_release_request(
                self.read(
                    "Enter overview, or asset_match;operating_system;architecture;package_preference "
                    "(for example: asset_match;linux;x64;any):"
                )
            )
            release_worker = ReleaseAdvisor(self.llm_factory())
            self.state.release_advice = release_worker.run(
                self.state.selected_repository, self.state.release_request
            )
            self.state.release_information = release_worker.release_information
            self.state.asset_selection = release_worker.asset_selection

        self.display("Final result")
        self.display(self.state.project_summary)
        if self.state.issue_analysis_choice == "yes":
            self.display(self.state.issue_analysis_result)
        if self.state.release_analysis_choice == "yes":
            self.display(self.state.release_advice)
        return self._outputs()

    def _outputs(self) -> dict[str, Any]:
        outputs: dict[str, Any] = {"project_summary": self.state.project_summary}
        if self.state.issue_analysis_result is not None:
            outputs["issue_analysis_result"] = self.state.issue_analysis_result
        if self.state.release_advice is not None:
            outputs["release_advice"] = self.state.release_advice
        return outputs


def main() -> dict[str, Any]:
    """Initialize the Agent, execute the entry Worker, and return its outputs."""
    state = AgentState()
    try:
        return ProjectNavigator(state, RuntimeLLM).run()
    except (AgentExecutionError, RuntimeError, ValueError, KeyError, EOFError) as exc:
        message = f"Agent execution failed: {exc}"
        print(message)
        return {"project_summary": state.project_summary, "error": message}


if __name__ == "__main__":
    main()
