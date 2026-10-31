from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


class CommunicationType(str, Enum):
    THREE_P = "three_p"
    NEWSLETTER = "newsletter"
    FAQ = "faq"
    GENERAL = "general"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class GeneralCommsRequest:
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


@dataclass
class AgentState:
    communication_type: CommunicationType = CommunicationType.UNKNOWN
    team_name: str = ""
    three_p_materials: str = ""
    newsletter_materials: str = ""
    faq_request: str = ""
    general_comms_request: GeneralCommsRequest | None = None
    general_comms_materials: str = ""
    final_communication: str | None = None


STATIC_INSTRUCTIONS = """
You are an assistant responsible for drafting company-internal communications
for company members who need clear, concise drafts. Never invent company facts,
project status, personnel decisions, organizational information, dates, owners,
metrics, commitments, risks, policies, amounts, eligibility rules, or impacts
that are absent from the user's information.

Domain definitions:
- A three_p update has clearly distinguished Progress, Plans, and Problems.
- A company newsletter selects, organizes, and summarizes important updates for
  a broad internal audience, prioritizing broad impact and reducing narrow,
  repetitive detail.
- An FAQ organizes employee concerns into questions and grounded answers and
  explicitly identifies insufficient information.
- A general communication follows the user's audience, purpose, tone, and format.
""".strip()


class RuntimeLLM:
    def __init__(self, client: OpenAI, model: str) -> None:
        self.client = client
        self.model = model

    @classmethod
    def from_environment(cls) -> "RuntimeLLM":
        load_dotenv(override=False)
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        base_url = os.getenv("BASE_URL", "").strip()
        model = (
            os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip()
            or os.getenv("OPENAI_MODEL", "").strip()
        )

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured in .env or the environment."
            )
        if not model:
            raise RuntimeError(
                "Neither CNLP_REFERENCE_LLM_MODEL nor OPENAI_MODEL is configured "
                "in .env or the environment."
            )

        client_options: dict[str, str] = {"api_key": api_key}
        if base_url:
            client_options["base_url"] = base_url.rstrip("/")
        return cls(OpenAI(**client_options), model)

    def complete(self, prompt: str, *, empty_result_error: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": STATIC_INSTRUCTIONS},
                {"role": "user", "content": prompt},
            ],
            reasoning={"effort": "high"},
        )
        result = str(response.output_text or "").strip()
        if not result:
            raise RuntimeError(empty_result_error)
        return result

    def classify_communication_type(self, user_selection: str) -> CommunicationType:
        prompt = f"""
Map the user's requested internal communication type to exactly one supported
value: three_p, newsletter, faq, general, or unknown.

Use three_p for a 3P / Progress-Plans-Problems team update. Use newsletter for a
company-internal newsletter. Use faq for a questions-and-answers communication.
Use general only when the user clearly requests another kind of internal
communication. Use unknown when the selection is blank, ambiguous, unrelated,
or cannot be recognized. Do not infer a type from unsupported assumptions.

User selection:
{user_selection}

Return JSON only in this exact shape:
{{"communication_type": "three_p|newsletter|faq|general|unknown"}}
""".strip()
        raw = self.complete(
            prompt,
            empty_result_error="The LLM returned an empty communication type.",
        )
        try:
            value = _parse_json_object(raw)["communication_type"]
            return CommunicationType(value)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return CommunicationType.UNKNOWN

    def parse_general_request(self, user_request: str) -> GeneralCommsRequest:
        prompt = f"""
Extract the four requested communication requirements from the user's single
response. Preserve the user's meaning and wording where practical. Do not
invent missing requirements; use an empty string for a field that was not
provided.

User response:
{user_request}

Return JSON only with four string fields in this exact shape:
{{
  "target_audience": "...",
  "purpose": "...",
  "tone": "...",
  "format_requirement": "..."
}}
""".strip()
        raw = self.complete(
            prompt,
            empty_result_error="The LLM returned an empty general request.",
        )
        try:
            data = _parse_json_object(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "The LLM returned an invalid general communication request."
            ) from exc

        field_names = (
            "target_audience",
            "purpose",
            "tone",
            "format_requirement",
        )
        if any(not isinstance(data.get(name), str) for name in field_names):
            raise RuntimeError(
                "The LLM returned an invalid general communication request."
            )
        return GeneralCommsRequest(**{name: data[name].strip() for name in field_names})

    def draft_three_p(self, team_name: str, source_materials: str) -> str:
        prompt = f"""
Draft an internal 3P team update for {team_name}.

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
        return self.complete(
            prompt, empty_result_error="The LLM returned an empty 3P update."
        )

    def draft_company_newsletter(self, source_materials: str) -> str:
        prompt = f"""
Create a concise company-internal newsletter from the supplied materials.

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
        return self.complete(
            prompt, empty_result_error="The LLM returned an empty newsletter."
        )

    def draft_faq(self, request: str) -> str:
        prompt = f"""
Create an internal FAQ from the request and supporting information below.

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
        return self.complete(prompt, empty_result_error="The LLM returned an empty FAQ.")

    def draft_general_comms(
        self, request: GeneralCommsRequest, source_materials: str
    ) -> str:
        prompt = f"""
Draft a general internal communication using the specified communication
requirements and source materials.

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
        return self.complete(
            prompt,
            empty_result_error="The LLM returned an empty internal communication.",
        )


class InternalCommsAgent:
    def __init__(self, llm: RuntimeLLM) -> None:
        self.llm = llm
        self.state = AgentState()

    @classmethod
    def from_environment(cls) -> "InternalCommsAgent":
        return cls(RuntimeLLM.from_environment())

    def run_dispatcher(self) -> str | None:
        selection = _input_once(
            "Select the internal communication type "
            "(three_p, newsletter, faq, or general): "
        )
        self.state.communication_type = self.llm.classify_communication_type(selection)

        # The unknown-type exception flow terminates this worker immediately.
        if self.state.communication_type is CommunicationType.UNKNOWN:
            _log("The internal communication type selected by the user cannot be recognized")
            print(
                "The selected communication type cannot be recognized. "
                "Supported types are three_p, newsletter, faq, and general."
            )
            return None

        if self.state.communication_type is CommunicationType.THREE_P:
            result = self._run_three_p_writer()
        elif self.state.communication_type is CommunicationType.NEWSLETTER:
            result = self._run_newsletter_writer()
        elif self.state.communication_type is CommunicationType.FAQ:
            result = self._run_faq_writer()
        else:
            result = self._run_general_comms_writer()

        self.state.final_communication = result
        return result

    def _run_three_p_writer(self) -> str:
        self.state.three_p_materials = _input_once(
            "Provide the source materials to organize into a 3P update: "
        )
        self.state.team_name = _input_once(
            "Provide the name of the team covered by this 3P update: "
        )
        result = self.llm.draft_three_p(
            team_name=self.state.team_name,
            source_materials=self.state.three_p_materials,
        )
        self.state.final_communication = result
        _display_result(result)
        return result

    def _run_newsletter_writer(self) -> str:
        self.state.newsletter_materials = _input_once(
            "Provide announcements, developments, team updates, milestones, meeting "
            "summaries, public reports, or other newsletter materials: "
        )
        result = self.llm.draft_company_newsletter(self.state.newsletter_materials)
        self.state.final_communication = result
        _display_result(result)
        return result

    def _run_faq_writer(self) -> str:
        self.state.faq_request = _input_once(
            "Provide the FAQ questions and any relevant supporting materials: "
        )
        result = self.llm.draft_faq(self.state.faq_request)
        self.state.final_communication = result
        _display_result(result)
        return result

    def _run_general_comms_writer(self) -> str:
        raw_request = _input_once(
            "In one response, provide the target audience, communication purpose, "
            "desired tone, and format requirement: "
        )
        self.state.general_comms_request = self.llm.parse_general_request(raw_request)
        self.state.general_comms_materials = _input_once(
            "Provide the announcements, background, project updates, meeting content, "
            "reference text, or other source materials: "
        )
        result = self.llm.draft_general_comms(
            self.state.general_comms_request,
            self.state.general_comms_materials,
        )
        self.state.final_communication = result
        _display_result(result)
        return result


def _input_once(prompt: str) -> str:
    """Execute one CNL-P INPUT command with exactly one stdin read."""
    return input(prompt)


def _display_result(result: str) -> None:
    print()
    print(result)


def _log(message: str) -> None:
    print(f"[diagnostic] {message}", file=sys.stderr)


def _parse_json_object(raw: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    start = raw.find("{")
    if start < 0:
        raise json.JSONDecodeError("No JSON object found", raw, 0)
    value, _ = decoder.raw_decode(raw[start:])
    if not isinstance(value, dict):
        raise json.JSONDecodeError("Expected a JSON object", raw, start)
    return value
