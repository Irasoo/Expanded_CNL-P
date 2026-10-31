"""Terminal agent for drafting grounded internal communications.

This module implements the workers defined in the accompanying CNL-P script.
It intentionally has no runtime dependency on the source CNL-P or reference
files used to generate it.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from openai import OpenAI


CommunicationType = Literal["three_p", "newsletter", "faq", "general", "unknown"]


@dataclass(frozen=True)
class GeneralCommsRequest:
    """The structured request required by the GeneralCommsWriter worker."""

    target_audience: str
    purpose: str
    tone: str
    format_requirement: str

    def as_dict(self) -> dict[str, str]:
        return {
            "target_audience": self.target_audience,
            "purpose": self.purpose,
            "tone": self.tone,
            "format_requirement": self.format_requirement,
        }


def _load_dotenv() -> None:
    """Load unset environment variables from a local .env file, if present."""
    dotenv_path = Path(".env")
    if not dotenv_path.is_file():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key.startswith("export "):
            key = key[7:].strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def _create_client() -> tuple[OpenAI, str]:
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
            "Neither CNLP_REFERENCE_LLM_MODEL nor OPENAI_MODEL is configured."
        )
    return OpenAI(api_key=api_key, base_url=base_url.rstrip("/")), model


def _ask_model(prompt: str, empty_message: str) -> str:
    client, model = _create_client()
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    result = str(response.output_text or "").strip()
    if not result:
        raise RuntimeError(empty_message)
    return result


def _parse_json_response(response: str, error_message: str) -> Any:
    candidate = response.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\s*```$", "", candidate)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise RuntimeError(error_message) from exc


def determine_communication_type(selection: str) -> CommunicationType:
    prompt = f"""
You are an internal communications intake assistant. Classify the user's
communication-type selection into exactly one allowed value.

Allowed values:
- three_p: a team update organized as Progress, Plans, and Problems
- newsletter: a broad internal company newsletter
- faq: an internal question-and-answer communication
- general: any other internal communication
- unknown: the selection cannot be mapped with confidence

Return only a JSON object with this schema: {{"communication_type": "one allowed value"}}.
Do not infer a type from materials that merely mention a format; classify only
the user's stated selection.

User selection:
{selection}
""".strip()
    parsed = _parse_json_response(
        _ask_model(prompt, "The LLM returned an empty communication type."),
        "The LLM returned an invalid communication type response.",
    )
    value = parsed.get("communication_type") if isinstance(parsed, dict) else None
    if value in {"three_p", "newsletter", "faq", "general", "unknown"}:
        return value
    return "unknown"


def parse_general_comms_request(user_input: str) -> GeneralCommsRequest:
    prompt = f"""
Extract the four required requirements for a company-internal communication
from the user's single intake response. The user may use prose, labels, or a
structured format. Preserve their stated meaning; do not invent missing
requirements. For an absent field, use the exact text "Not specified".

Return only valid JSON with exactly these string fields:
{{
  "target_audience": "...",
  "purpose": "...",
  "tone": "...",
  "format_requirement": "..."
}}

User intake response:
{user_input}
""".strip()
    parsed = _parse_json_response(
        _ask_model(prompt, "The LLM returned an empty general request."),
        "The LLM returned an invalid general request response.",
    )
    if not isinstance(parsed, dict):
        raise RuntimeError("The LLM did not return a general request object.")
    fields = ("target_audience", "purpose", "tone", "format_requirement")
    if any(not isinstance(parsed.get(field), str) for field in fields):
        raise RuntimeError("The LLM returned an incomplete general request.")
    return GeneralCommsRequest(**{field: parsed[field].strip() or "Not specified" for field in fields})


def draft_three_p(team_name: str, source_materials: str) -> str:
    prompt = f"""
You are responsible for drafting company-internal communications for company
members. Draft an internal 3P team update for {team_name}.

Use only the supplied source materials. Do not invent facts, dates, owners,
metrics, commitments, or risks. Organize the result into exactly these three
clearly labelled sections: Progress, Plans, and Problems. Consolidate repeated
items, preserve important details, and write concise professional prose. If a
section has no supported content, state that no corresponding update was
provided.

Source materials:
{source_materials}

Return only the final 3P update.
""".strip()
    return _ask_model(prompt, "The LLM returned an empty 3P update.")


def draft_company_newsletter(source_materials: str) -> str:
    prompt = f"""
You are responsible for drafting company-internal communications for company
members. Create a concise company-internal newsletter from the supplied
materials.

Use only supported facts. Remove duplicates and near-duplicates. Prioritize
updates with broad employee relevance, important achievements, upcoming events,
operational changes, and actionable reminders; omit overly narrow details that
do not help the wider audience. Group related items under clear thematic
headings and make the result easy to scan. If enough useful material is
available, select roughly 20 to 25 items; otherwise include only the supported
useful items without padding or invention.

Source materials:
{source_materials}

Return only the final newsletter.
""".strip()
    return _ask_model(prompt, "The LLM returned an empty newsletter.")


def draft_faq(request: str) -> str:
    prompt = f"""
You are responsible for drafting company-internal communications for company
members. Create an internal FAQ from the request and supporting information
below.

Identify the employee questions, merge duplicates or questions with the same
intent, and organize them in a clear question-and-answer format. Every answer
must be grounded only in the supplied confirmed information. Do not infer or
invent policy decisions, dates, amounts, eligibility rules, or commitments. If
the available information does not support an answer, explicitly say that the
information is insufficient and identify what still requires clarification.

FAQ request and supporting information:
{request}

Return only the final FAQ.
""".strip()
    return _ask_model(prompt, "The LLM returned an empty FAQ.")


def draft_general_comms(request: GeneralCommsRequest, source_materials: str) -> str:
    prompt = f"""
You are responsible for drafting company-internal communications for company
members. Draft a general internal communication using the specified
communication requirements and source materials.

Follow the requested target audience, purpose, tone, and format requirement.
Use only facts supported by the source materials. Do not invent dates, impacts,
actions, owners, or commitments. Preserve all material instructions that the
target audience needs, and return a polished ready-to-send communication.

Communication requirements:
{json.dumps(request.as_dict(), ensure_ascii=False, indent=2)}

Source materials:
{source_materials}

Return only the final communication.
""".strip()
    return _ask_model(prompt, "The LLM returned an empty internal communication.")


class InternalCommsAgent:
    """Stateful implementation of the dispatcher and its four CNL-P workers."""

    def __init__(self, input_fn: Callable[[str], str] = input, output_fn: Callable[[str], None] = print) -> None:
        self._input = input_fn
        self._output = output_fn
        self.communication_type: CommunicationType = "unknown"
        self.team_name = ""
        self.three_p_materials = ""
        self.newsletter_materials = ""
        self.faq_request = ""
        self.general_comms_request: GeneralCommsRequest | None = None
        self.general_comms_materials = ""
        self.final_communication = ""

    def _read_once(self, prompt: str) -> str:
        return self._input(f"{prompt}\n> ")

    def run(self) -> str | None:
        # Dispatcher COMMAND-1
        selection = self._read_once(
            "Select the internal communication type to generate: three_p, newsletter, faq, or general."
        )
        self.communication_type = determine_communication_type(selection)

        # Dispatcher exception flow: it terminates this worker without an output.
        if self.communication_type == "unknown":
            logging.getLogger(__name__).warning(
                "The internal communication type selected by the user cannot be recognized."
            )
            self._output(
                "The selected communication type cannot be recognized. Supported types are: three_p, newsletter, faq, and general."
            )
            return None

        if self.communication_type == "three_p":
            self.final_communication = self._run_three_p_writer()
        elif self.communication_type == "newsletter":
            self.final_communication = self._run_newsletter_writer()
        elif self.communication_type == "faq":
            self.final_communication = self._run_faq_writer()
        else:
            self.final_communication = self._run_general_comms_writer()
        return self.final_communication

    def _display_final(self) -> None:
        self._output("\n" + self.final_communication)

    def _run_three_p_writer(self) -> str:
        self.three_p_materials = self._read_once(
            "Provide the team update materials to organize into a 3P update."
        )
        self.team_name = self._read_once("Provide the name of the team covered by this 3P update.")
        result = draft_three_p(self.team_name, self.three_p_materials)
        self.final_communication = result
        self._display_final()
        return result

    def _run_newsletter_writer(self) -> str:
        self.newsletter_materials = self._read_once(
            "Provide announcements, developments, team updates, milestones, meeting summaries, public reports, or other materials for the company newsletter."
        )
        result = draft_company_newsletter(self.newsletter_materials)
        self.final_communication = result
        self._display_final()
        return result

    def _run_faq_writer(self) -> str:
        self.faq_request = self._read_once(
            "Provide the internal FAQ request, including questions to answer and any relevant reference materials."
        )
        result = draft_faq(self.faq_request)
        self.final_communication = result
        self._display_final()
        return result

    def _run_general_comms_writer(self) -> str:
        request_input = self._read_once(
            "Provide the target audience, communication purpose, desired tone, and format requirement for this internal communication."
        )
        self.general_comms_request = parse_general_comms_request(request_input)
        self.general_comms_materials = self._read_once(
            "Provide announcements, background information, project updates, meeting content, reference text, or other materials for this communication."
        )
        result = draft_general_comms(self.general_comms_request, self.general_comms_materials)
        self.final_communication = result
        self._display_final()
        return result


def main() -> str | None:
    """Initialize the agent, execute its entry worker, and return its final result."""
    agent = InternalCommsAgent()
    try:
        return agent.run()
    except (RuntimeError, OSError) as exc:
        print(f"Error: {exc}")
        return None


if __name__ == "__main__":
    main()
