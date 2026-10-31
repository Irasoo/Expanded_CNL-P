"""Terminal agent for drafting internal company communications."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


SUPPORTED_TYPES = ("three_p", "newsletter", "faq", "general")
UNKNOWN_TYPE = "unknown"
TYPE_SELECTION_PROMPT = """Classify the user's requested internal communication type.

Return exactly one JSON object with one key, communication_type. Its value must
be exactly one of: three_p, newsletter, faq, general, unknown. Use three_p for
a 3P team update, newsletter for a company newsletter, faq for an internal FAQ,
and general for another internal communication. Use unknown when the selection
is ambiguous or cannot be mapped to one of those four types.

User selection:
"""

GENERAL_REQUEST_PROMPT = """Extract the requirements for a general internal communication from the user's
single answer. Return exactly one JSON object with exactly these four string
keys: target_audience, purpose, tone, format_requirement. Preserve the user's
meaning. If a field was not specified, use an empty string for that field.

User answer:
"""


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries without overriding process environment."""

    dotenv_path = Path.cwd() / ".env"
    if not dotenv_path.is_file():
        return

    try:
        lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


class InternalCommsAgent:
    """Coordinates the dispatcher and the communication-specific writers."""

    def __init__(self) -> None:
        _load_dotenv()
        self.communication_type = UNKNOWN_TYPE
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

    @staticmethod
    def _read_input(prompt: str) -> str:
        print(prompt)
        return input().strip()

    @staticmethod
    def _client_and_model() -> tuple[Any, str]:
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

        from openai import OpenAI

        client_options: dict[str, str] = {"api_key": api_key}
        if base_url:
            client_options["base_url"] = base_url.rstrip("/")
        return OpenAI(**client_options), model

    @classmethod
    def _complete(cls, prompt: str) -> str:
        client, model = cls._client_and_model()
        response = client.responses.create(
            model=model,
            input=prompt,
            reasoning={"effort": "high"},
        )
        result = str(response.output_text or "").strip()
        if not result:
            raise RuntimeError("The LLM returned an empty response.")
        return result

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        candidate = raw.strip()
        if candidate.startswith("```"):
            lines = candidate.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            candidate = "\n".join(lines).strip()
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise RuntimeError("The LLM returned invalid JSON.") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("The LLM returned a JSON value that is not an object.")
        return parsed

    def _classify_selection(self, selection: str) -> str:
        raw = self._complete(TYPE_SELECTION_PROMPT + selection)
        parsed = self._parse_json_object(raw)
        value = parsed.get("communication_type")
        if value not in (*SUPPORTED_TYPES, UNKNOWN_TYPE):
            return UNKNOWN_TYPE
        return value

    def _extract_general_request(self, answer: str) -> dict[str, str]:
        raw = self._complete(GENERAL_REQUEST_PROMPT + answer)
        parsed = self._parse_json_object(raw)
        fields = ("target_audience", "purpose", "tone", "format_requirement")
        request: dict[str, str] = {}
        for field in fields:
            value = parsed.get(field, "")
            request[field] = value if isinstance(value, str) else str(value)
        return request

    def dispatch(self) -> str | None:
        selection = self._read_input(
            "Select the internal communication type to generate "
            "(three_p, newsletter, faq, or general):"
        )
        self.communication_type = self._classify_selection(selection)

        if self.communication_type == UNKNOWN_TYPE:
            diagnostic = (
                "The internal communication type selected by the user cannot be recognized."
            )
            print(diagnostic)
            print(
                "Supported types are: three_p, newsletter, faq, and general."
            )
            return None

        if self.communication_type == "three_p":
            self.final_communication = self.write_three_p()
        elif self.communication_type == "newsletter":
            self.final_communication = self.write_newsletter()
        elif self.communication_type == "faq":
            self.final_communication = self.write_faq()
        else:
            self.final_communication = self.write_general_comms()
        return self.final_communication

    def write_three_p(self) -> str:
        self.three_p_materials = self._read_input(
            "Provide the team update materials to organize into a 3P update:"
        )
        self.team_name = self._read_input(
            "Provide the name of the team covered by this 3P update:"
        )
        result = draft_three_p(self.team_name, self.three_p_materials)
        print(result)
        return result

    def write_newsletter(self) -> str:
        self.newsletter_materials = self._read_input(
            "Provide announcements, important developments, team updates, milestones, "
            "meeting summaries, public reports, or other relevant materials for the newsletter:"
        )
        result = draft_company_newsletter(self.newsletter_materials)
        print(result)
        return result

    def write_faq(self) -> str:
        self.faq_request = self._read_input(
            "Provide the internal FAQ request, including the questions to answer "
            "and any relevant reference materials:"
        )
        result = draft_faq(self.faq_request)
        print(result)
        return result

    def write_general_comms(self) -> str:
        requirements = self._read_input(
            "Provide the target audience, communication purpose, desired tone, "
            "and format requirement for this internal communication:"
        )
        self.general_comms_request = _normalize_general_request(
            self._extract_general_request(requirements)
        )
        self.general_comms_materials = self._read_input(
            "Provide the announcements, background information, project updates, "
            "meeting content, reference text, or other relevant materials to use:"
        )
        result = draft_general_comms(
            self.general_comms_request, self.general_comms_materials
        )
        print(result)
        return result


def _normalize_general_request(request: dict[str, str]) -> dict[str, str]:
    fields = ("target_audience", "purpose", "tone", "format_requirement")
    return {field: str(request.get(field, "")).strip() for field in fields}


def _draft(prompt: str, empty_error: str) -> str:
    result = InternalCommsAgent._complete(prompt)
    if not result:
        raise RuntimeError(empty_error)
    return result


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
    return _draft(prompt, "The LLM returned an empty 3P update.")


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
    return _draft(prompt, "The LLM returned an empty newsletter.")


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
    return _draft(prompt, "The LLM returned an empty FAQ.")


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
    return _draft(prompt, "The LLM returned an empty internal communication.")


def main() -> str | None:
    """Initialize the agent, run the dispatcher, and return its result."""

    agent = InternalCommsAgent()
    try:
        return agent.dispatch()
    except (EOFError, KeyboardInterrupt):
        print("Input was interrupted.")
    except Exception as exc:
        print(f"Error: {exc}")
    return None


if __name__ == "__main__":
    main()
