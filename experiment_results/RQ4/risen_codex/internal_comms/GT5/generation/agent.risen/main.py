"""Terminal agent for drafting company-internal communications."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


SUPPORTED_TYPES = ("three_p", "newsletter", "faq", "general")


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries from the project's local .env file."""
    dotenv_path = Path.cwd() / ".env"
    if not dotenv_path.is_file():
        return

    try:
        lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _runtime_config() -> tuple[str, str, str]:
    _load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = (
        os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
    )
    base_url = os.getenv("BASE_URL", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    if not model:
        raise RuntimeError(
            "Neither CNLP_REFERENCE_LLM_MODEL nor OPENAI_MODEL is configured."
        )
    return api_key, model, base_url


def _call_llm(prompt: str) -> str:
    """Call the configured model and require a non-empty text result."""
    from openai import OpenAI

    api_key, model, base_url = _runtime_config()
    client_options: dict[str, str] = {"api_key": api_key}
    if base_url:
        client_options["base_url"] = base_url.rstrip("/")
    client = OpenAI(**client_options)
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    result = str(response.output_text or "").strip()
    if not result:
        raise RuntimeError("The LLM returned an empty response.")
    return result


def _interpret_communication_type(selection: str) -> str:
    prompt = f"""
Determine which supported internal communication type the user selected.

    The allowed output values are exactly: three_p, newsletter, faq, general,
    unknown. Map the user's meaning to one of the first four values when it clearly
requests that type. If it does not clearly map to one of them, return unknown.
Return only one allowed value and no explanation.

User selection:
{selection}
""".strip()
    result = _call_llm(prompt).strip().lower()
    if result in ("three_p", "newsletter", "faq", "general", "unknown"):
        return result
    return "unknown"


def _interpret_general_request(answer: str) -> dict[str, str]:
    prompt = f"""
Interpret the user's single answer as a GeneralCommsRequest.

Extract exactly these four required text fields: target_audience,
purpose, tone, and format_requirement. Preserve the user's meaning and do not
invent missing details. Return only a valid JSON object with exactly those four
string keys. If a field is not specified, use an empty string for that field.

User answer:
{answer}
""".strip()
    result = _call_llm(prompt)
    try:
        parsed: Any = json.loads(result)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The LLM returned an invalid general communication request.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("The LLM returned an invalid general communication request.")

    fields = ("target_audience", "purpose", "tone", "format_requirement")
    request: dict[str, str] = {}
    for field in fields:
        value = parsed.get(field, "")
        if not isinstance(value, str):
            value = str(value)
        request[field] = value
    return request


def draft_three_p(team_name: str, source_materials: str) -> str:
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
    result = _call_llm(prompt)
    if not result:
        raise RuntimeError("The LLM returned an empty 3P update.")
    return result


def draft_company_newsletter(source_materials: str) -> str:
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
    result = _call_llm(prompt)
    if not result:
        raise RuntimeError("The LLM returned an empty newsletter.")
    return result


def draft_faq(request: str) -> str:
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
    result = _call_llm(prompt)
    if not result:
        raise RuntimeError("The LLM returned an empty FAQ.")
    return result


def draft_general_comms(request: dict[str, str], source_materials: str) -> str:
    prompt = f"""
Draft a general internal communication using the specified communication
requirements and source materials.

Follow the requested target audience, purpose, tone, and format requirement.
Use only facts supported by the source materials. Do not invent dates, impacts,
actions, owners, or commitments. Preserve all material instructions that the
target audience needs, and return a polished ready-to-send communication.

Communication requirements:
{json.dumps(request, ensure_ascii=False, indent=2)}

Source materials:
{source_materials}

Return only the final communication.
""".strip()
    result = _call_llm(prompt)
    if not result:
        raise RuntimeError("The LLM returned an empty internal communication.")
    return result


class InternalCommsAssistant:
    """Stateful implementation of the dispatcher and its four workers."""

    def __init__(self) -> None:
        self.communication_type = "unknown"
        self.team_name = ""
        self.three_p_materials = ""
        self.newsletter_materials = ""
        self.faq_request = ""
        self.general_comms_request: dict[str, str] = {
            "target_audience": "",
            "purpose": "",
            "tone": "",
            "format_requirement": "",
        }
        self.general_comms_materials = ""
        self.final_communication = ""

    def run(self) -> str:
        selection = input(
            "Select an internal communication type (three_p, newsletter, faq, or general): "
        )
        self.communication_type = _interpret_communication_type(selection)
        if self.communication_type == "unknown":
            diagnostic = "The internal communication type selected by the user cannot be recognized."
            print(diagnostic)
            print("Currently supported types are: three_p, newsletter, faq, and general.")
            return diagnostic

        if self.communication_type == "three_p":
            self.final_communication = self._write_three_p()
        elif self.communication_type == "newsletter":
            self.final_communication = self._write_newsletter()
        elif self.communication_type == "faq":
            self.final_communication = self._write_faq()
        else:
            self.final_communication = self._write_general()
        print(self.final_communication)
        return self.final_communication

    def _write_three_p(self) -> str:
        self.three_p_materials = input(
            "Provide the team update materials to organize into a 3P update: "
        )
        self.team_name = input("Provide the name of the team covered by this 3P update: ")
        return draft_three_p(self.team_name, self.three_p_materials)

    def _write_newsletter(self) -> str:
        self.newsletter_materials = input(
            "Provide announcements, developments, team updates, milestones, meeting summaries, public reports, or other newsletter materials: "
        )
        return draft_company_newsletter(self.newsletter_materials)

    def _write_faq(self) -> str:
        self.faq_request = input(
            "Provide the internal FAQ request, including questions and relevant reference materials: "
        )
        return draft_faq(self.faq_request)

    def _write_general(self) -> str:
        request_answer = input(
            "Provide the target audience, communication purpose, desired tone, and format requirement: "
        )
        self.general_comms_request = _interpret_general_request(request_answer)
        self.general_comms_materials = input(
            "Provide the announcements, background information, project updates, meeting content, reference text, or other relevant materials: "
        )
        return draft_general_comms(
            self.general_comms_request,
            self.general_comms_materials,
        )


def main() -> str:
    """Initialize the assistant, run the dispatcher, and return its result."""
    assistant = InternalCommsAssistant()
    try:
        return assistant.run()
    except (RuntimeError, ValueError) as exc:
        message = f"Unable to complete the internal communication draft: {exc}"
        print(message)
        return message


if __name__ == "__main__":
    main()
