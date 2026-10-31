from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, cast

from dotenv import load_dotenv
from openai import OpenAI


CommunicationType = Literal["three_p", "newsletter", "faq", "general", "unknown"]
SUPPORTED_COMMUNICATION_TYPES = {"three_p", "newsletter", "faq", "general"}

AGENT_CONTEXT = """
You are an assistant responsible for drafting company-internal communications
for company members who need team updates, company newsletters, FAQs, or other
internal communications.

Domain definitions:
- A three_p update has the sections Progress, Plans, and Problems.
- A newsletter serves a broad internal audience and selects, organizes, and
  summarizes important company updates.
- An FAQ organizes employee concerns or matters requiring clarification into
  questions and answers.
- A general communication is any other internal communication.

Always use only facts supplied by the user. Never invent company facts,
project status, personnel decisions, organizational information, dates,
metrics, owners, impacts, policies, or commitments. Keep drafts clear,
concise, professional, and appropriate for the requested audience and format.
""".strip()


@dataclass(frozen=True)
class GeneralCommsRequest:
    target_audience: str
    purpose: str
    tone: str
    format_requirement: str


@dataclass
class AgentState:
    communication_type: CommunicationType = "unknown"
    team_name: str = ""
    three_p_materials: str = ""
    newsletter_materials: str = ""
    faq_request: str = ""
    general_comms_request: GeneralCommsRequest | None = None
    general_comms_materials: str = ""
    final_communication: str | None = None


class RuntimeLLM:
    def __init__(self) -> None:
        load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        base_url = os.getenv("BASE_URL", "").strip()
        model = (
            os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip()
            or os.getenv("OPENAI_MODEL", "").strip()
        )

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured in .env or the process environment."
            )
        if not model:
            raise RuntimeError(
                "Neither CNLP_REFERENCE_LLM_MODEL nor OPENAI_MODEL is configured "
                "in .env or the process environment."
            )

        client_options: dict[str, str] = {"api_key": api_key}
        if base_url:
            client_options["base_url"] = base_url.rstrip("/")

        self.client = OpenAI(**client_options)
        self.model = model

    def complete(self, prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            reasoning={"effort": "high"},
            instructions=AGENT_CONTEXT,
            input=prompt,
        )
        result = str(response.output_text or "").strip()
        if not result:
            raise RuntimeError("The runtime language model returned an empty response.")
        return result


def _read_once(prompt: str) -> str:
    print(prompt)
    return input("> ")


def _parse_json_object(value: str, description: str) -> dict[str, Any]:
    cleaned = value.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3:
            cleaned = "\n".join(lines[1:-1]).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"The runtime language model returned invalid JSON for {description}."
        ) from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(
            f"The runtime language model did not return an object for {description}."
        )
    return parsed


def determine_communication_type(llm: RuntimeLLM, user_selection: str) -> CommunicationType:
    prompt = f"""
Map the user's requested internal communication type to exactly one supported
value:
- three_p: a Progress, Plans, and Problems team update
- newsletter: a broad company-internal newsletter
- faq: internal questions and answers
- general: another kind of internal communication
- unknown: the request cannot be confidently mapped to any of the four types

Interpret the user's language semantically, including ordinary synonyms and
descriptions. Do not infer a choice if the input is ambiguous, unrelated, or
empty. Return only one lowercase value from this list:
three_p, newsletter, faq, general, unknown

User selection:
{user_selection}
""".strip()
    result = llm.complete(prompt).strip().lower()
    if result in SUPPORTED_COMMUNICATION_TYPES or result == "unknown":
        return cast(CommunicationType, result)
    logging.error("Communication type classifier returned an invalid value: %r", result)
    return "unknown"


def extract_general_request(llm: RuntimeLLM, user_response: str) -> GeneralCommsRequest:
    prompt = f"""
Extract the communication requirements from the user's single response. Return
only a JSON object with exactly these string fields:
{{
  "target_audience": "...",
  "purpose": "...",
  "tone": "...",
  "format_requirement": "..."
}}

Preserve the user's meaning and wording where practical. Do not infer or invent
missing requirements; use an empty string for a field that was not provided.

User response:
{user_response}
""".strip()
    parsed = _parse_json_object(llm.complete(prompt), "general communication requirements")
    expected_fields = {
        "target_audience",
        "purpose",
        "tone",
        "format_requirement",
    }
    if set(parsed) != expected_fields:
        raise RuntimeError(
            "The runtime language model returned the wrong fields for general "
            "communication requirements."
        )
    if not all(isinstance(parsed[field], str) for field in expected_fields):
        raise RuntimeError(
            "Every general communication requirement returned by the runtime "
            "language model must be text."
        )
    return GeneralCommsRequest(
        target_audience=parsed["target_audience"].strip(),
        purpose=parsed["purpose"].strip(),
        tone=parsed["tone"].strip(),
        format_requirement=parsed["format_requirement"].strip(),
    )


def draft_three_p(llm: RuntimeLLM, team_name: str, source_materials: str) -> str:
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
    return llm.complete(prompt)


def draft_company_newsletter(llm: RuntimeLLM, source_materials: str) -> str:
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
    return llm.complete(prompt)


def draft_faq(llm: RuntimeLLM, request: str) -> str:
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
    return llm.complete(prompt)


def draft_general_comms(
    llm: RuntimeLLM,
    request: GeneralCommsRequest,
    source_materials: str,
) -> str:
    prompt = f"""
Draft a general internal communication using the specified communication
requirements and source materials.

Follow the requested target audience, purpose, tone, and format requirement.
Use only facts supported by the source materials. Do not invent dates, impacts,
actions, owners, or commitments. Preserve all material instructions that the
target audience needs, and return a polished ready-to-send communication.

Communication requirements:
{json.dumps(asdict(request), ensure_ascii=False, indent=2)}

Source materials:
{source_materials}

Return only the final communication.
""".strip()
    return llm.complete(prompt)


class InternalCommsAssistant:
    def __init__(self, llm: RuntimeLLM) -> None:
        self.llm = llm
        self.state = AgentState()

    def run_three_p_writer(self) -> str:
        self.state.three_p_materials = _read_once(
            "Provide the team update materials to organize into a 3P update."
        )
        self.state.team_name = _read_once(
            "Provide the name of the team covered by this 3P update."
        )
        result = draft_three_p(
            self.llm,
            team_name=self.state.team_name,
            source_materials=self.state.three_p_materials,
        )
        self.state.final_communication = result
        print(result)
        return result

    def run_newsletter_writer(self) -> str:
        self.state.newsletter_materials = _read_once(
            "Provide announcements, important developments, team updates, "
            "milestones, meeting summaries, public reports, or other relevant "
            "materials to organize into a company newsletter."
        )
        result = draft_company_newsletter(
            self.llm, source_materials=self.state.newsletter_materials
        )
        self.state.final_communication = result
        print(result)
        return result

    def run_faq_writer(self) -> str:
        self.state.faq_request = _read_once(
            "Provide the internal FAQ request, including the questions to answer "
            "and any relevant reference materials."
        )
        result = draft_faq(self.llm, request=self.state.faq_request)
        self.state.final_communication = result
        print(result)
        return result

    def run_general_writer(self) -> str:
        raw_request = _read_once(
            "In one response, provide the target audience, communication purpose, "
            "desired tone, and format requirement for this internal communication."
        )
        self.state.general_comms_request = extract_general_request(
            self.llm, raw_request
        )
        self.state.general_comms_materials = _read_once(
            "Provide the announcements, background information, project updates, "
            "meeting content, reference text, or other relevant drafting materials."
        )
        result = draft_general_comms(
            self.llm,
            request=self.state.general_comms_request,
            source_materials=self.state.general_comms_materials,
        )
        self.state.final_communication = result
        print(result)
        return result

    def run_dispatcher(self) -> str | None:
        raw_selection = _read_once(
            "Select the internal communication type to generate: three_p, "
            "newsletter, faq, or general."
        )
        self.state.communication_type = determine_communication_type(
            self.llm, raw_selection
        )

        if self.state.communication_type == "unknown":
            logging.warning(
                "The internal communication type selected by the user cannot be "
                "recognized."
            )
            print(
                "The selected communication type cannot be recognized. Supported "
                "types are three_p, newsletter, faq, and general."
            )
            return None

        if self.state.communication_type == "three_p":
            return self.run_three_p_writer()
        if self.state.communication_type == "newsletter":
            return self.run_newsletter_writer()
        if self.state.communication_type == "faq":
            return self.run_faq_writer()
        return self.run_general_writer()


def main() -> str | None:
    """Initialize the agent, run its entry Worker, and return the final result."""
    agent = InternalCommsAssistant(RuntimeLLM())
    return agent.run_dispatcher()


if __name__ == "__main__":
    main()
