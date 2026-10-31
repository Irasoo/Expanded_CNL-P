"""Terminal agent for drafting internal company communications."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


SUPPORTED_TYPES = ("three_p", "newsletter", "faq", "general")


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries without overriding process variables."""
    dotenv_path = os.path.join(os.getcwd(), ".env")
    try:
        with open(dotenv_path, "r", encoding="utf-8") as dotenv_file:
            lines = dotenv_file.readlines()
    except FileNotFoundError:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def _model_configuration() -> tuple[str, str, str]:
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
    """Call the configured model with the required high reasoning effort."""
    from openai import OpenAI

    api_key, model, base_url = _model_configuration()
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


def _parse_json_response(raw_response: str) -> Any:
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The LLM returned invalid structured data.") from exc


def classify_communication_type(selection: str) -> str:
    prompt = f"""
Classify the user's requested internal communication type.

Return exactly one lowercase value from this list and nothing else:
three_p, newsletter, faq, general, unknown

Interpret the user's natural-language answer. Map it to three_p for a 3P/team
update, newsletter for a company newsletter, faq for an FAQ, and general for
any other internal communication. Return unknown when the answer cannot be
recognized as one of those four types.

User selection:
{selection}
""".strip()
    result = _call_llm(prompt).strip().lower()
    result = result.strip("` \"'.,:;!\n")
    return result if result in (*SUPPORTED_TYPES, "unknown") else "unknown"


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


def interpret_general_request(answer: str) -> dict[str, str]:
    prompt = f"""
Interpret the user's single answer as the requirements for a general internal
communication. Extract these four text fields:
target_audience, purpose, tone, format_requirement.

Return only a valid JSON object with exactly those four string fields. Preserve
the user's meaning and do not invent missing requirements. If a field is not
specified, use an empty string for that field.

User's answer:
{answer}
""".strip()
    parsed = _parse_json_response(_call_llm(prompt))
    if not isinstance(parsed, dict):
        raise RuntimeError("The LLM did not return a general communication request object.")
    request: dict[str, str] = {}
    for key in ("target_audience", "purpose", "tone", "format_requirement"):
        value = parsed.get(key, "")
        if not isinstance(value, str):
            raise RuntimeError(
                f"The LLM returned a non-text value for general request field '{key}'."
            )
        request[key] = value
    return request


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


@dataclass
class AgentState:
    communication_type: str = "unknown"
    team_name: str = ""
    three_p_materials: str = ""
    newsletter_materials: str = ""
    faq_request: str = ""
    general_comms_request: dict[str, str] = field(
        default_factory=lambda: {
            "target_audience": "",
            "purpose": "",
            "tone": "",
            "format_requirement": "",
        }
    )
    general_comms_materials: str = ""
    final_communication: str = ""


class InternalCommsAssistant:
    """Dispatches one terminal session to the appropriate communication worker."""

    def __init__(self) -> None:
        self.state = AgentState()

    @staticmethod
    def _ask(prompt: str) -> str:
        print(prompt)
        try:
            return input("> ").strip()
        except EOFError as exc:
            raise RuntimeError("No terminal input was provided.") from exc

    def three_p_writer(self) -> str:
        self.state.three_p_materials = self._ask(
            "Provide the team update materials to organize into a 3P update."
        )
        self.state.team_name = self._ask(
            "Provide the name of the team covered by this 3P update."
        )
        result = draft_three_p(self.state.team_name, self.state.three_p_materials)
        self.state.final_communication = result
        print("\n" + result)
        return result

    def newsletter_writer(self) -> str:
        self.state.newsletter_materials = self._ask(
            "Provide announcements, important developments, team updates, milestones, "
            "meeting summaries, public reports, or other relevant materials to "
            "organize into a company newsletter."
        )
        result = draft_company_newsletter(self.state.newsletter_materials)
        self.state.final_communication = result
        print("\n" + result)
        return result

    def faq_writer(self) -> str:
        self.state.faq_request = self._ask(
            "Provide the internal FAQ request, including the questions to answer "
            "and any relevant reference materials."
        )
        result = draft_faq(self.state.faq_request)
        self.state.final_communication = result
        print("\n" + result)
        return result

    def general_comms_writer(self) -> str:
        answer = self._ask(
            "Provide the target audience, communication purpose, desired tone, and "
            "format requirement for this internal communication in one answer."
        )
        self.state.general_comms_request = interpret_general_request(answer)
        self.state.general_comms_materials = self._ask(
            "Provide the announcements, background information, project updates, "
            "meeting content, reference text, or other relevant materials to use "
            "when drafting this internal communication."
        )
        result = draft_general_comms(
            self.state.general_comms_request,
            self.state.general_comms_materials,
        )
        self.state.final_communication = result
        print("\n" + result)
        return result

    def dispatch(self) -> str:
        selection = self._ask(
            "Select the internal communication type to generate: "
            "three_p, newsletter, faq, or general."
        )
        self.state.communication_type = classify_communication_type(selection)

        if self.state.communication_type == "unknown":
            diagnostic_message = (
                "The internal communication type selected by the user cannot be recognized."
            )
            print(diagnostic_message)
            print(
                "The currently supported types are: three_p, newsletter, faq, and general."
            )
            return ""
        if self.state.communication_type == "three_p":
            return self.three_p_writer()
        if self.state.communication_type == "newsletter":
            return self.newsletter_writer()
        if self.state.communication_type == "faq":
            return self.faq_writer()
        return self.general_comms_writer()


def main() -> str:
    """Initialize the Agent, execute its entry process, and return its result."""
    assistant = InternalCommsAssistant()
    try:
        return assistant.dispatch()
    except Exception as exc:
        print(f"Agent execution failed: {exc}")
        return ""


if __name__ == "__main__":
    main()
