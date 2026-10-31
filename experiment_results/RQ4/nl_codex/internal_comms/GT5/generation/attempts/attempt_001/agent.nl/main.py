"""Terminal-based internal communications drafting agent."""

from __future__ import annotations

import json
import os
import sys
from typing import Any


COMMUNICATION_TYPES = {"three_p", "newsletter", "faq", "general"}


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries without overriding process variables."""
    try:
        with open(".env", "r", encoding="utf-8") as dotenv_file:
            lines = dotenv_file.readlines()
    except FileNotFoundError:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


class _LanguageModel:
    def __init__(self) -> None:
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

        from openai import OpenAI

        client_options: dict[str, str] = {"api_key": api_key}
        if base_url:
            client_options["base_url"] = base_url.rstrip("/")
        self.client = OpenAI(**client_options)
        self.model = model

    def complete(self, prompt: str, empty_message: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            reasoning={"effort": "high"},
        )
        result = str(response.output_text or "").strip()
        if not result:
            raise RuntimeError(empty_message)
        return result

    def complete_json(self, prompt: str, empty_message: str) -> dict[str, Any]:
        result = self.complete(prompt, empty_message)
        candidate = result.strip()
        if candidate.startswith("```"):
            candidate = candidate.strip("`").strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise RuntimeError("The LLM returned invalid JSON.") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("The LLM returned a JSON value instead of an object.")
        return parsed


class InternalCommsAssistant:
    """Dispatches one terminal request to the appropriate communication worker."""

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
        self._llm: _LanguageModel | None = None

    @property
    def llm(self) -> _LanguageModel:
        if self._llm is None:
            self._llm = _LanguageModel()
        return self._llm

    @staticmethod
    def _ask(prompt: str) -> str:
        print(prompt)
        return input()

    def _recognize_type(self, answer: str) -> str:
        prompt = f"""
Interpret the user's selection of an internal communication type.

The only permitted output values are exactly: three_p, newsletter, faq,
general, or unknown. Map the user's answer to one of the four supported types
when its meaning clearly requests that type. Use unknown when it is ambiguous,
unsupported, or does not select one of those four types. Return only a JSON
object with this shape: {{"communication_type": "..."}}.

User selection:
{answer}
""".strip()
        parsed = self.llm.complete_json(
            prompt, "The LLM returned an empty communication type selection."
        )
        value = parsed.get("communication_type")
        if not isinstance(value, str) or value not in COMMUNICATION_TYPES | {"unknown"}:
            raise RuntimeError("The LLM returned an invalid communication type.")
        return value

    def run(self) -> str:
        selection = self._ask(
            "Select the internal communication type to generate "
            "(three_p, newsletter, faq, or general):"
        )
        self.communication_type = self._recognize_type(selection)

        if self.communication_type == "unknown":
            self.final_communication = (
                "The internal communication type selected by the user cannot be recognized."
            )
            print(self.final_communication)
            print(
                "Currently supported types are: three_p, newsletter, faq, and general."
            )
            return self.final_communication

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
        self.three_p_materials = self._ask(
            "Provide the team update materials to organize into a 3P update:"
        )
        self.team_name = self._ask(
            "Provide the name of the team covered by this 3P update:"
        )
        prompt = f"""
Draft an internal 3P team update for {self.team_name}.

Use only the supplied source materials. Do not invent facts, dates, owners,
metrics, commitments, or risks. Organize the result into exactly these three
clearly labelled sections: Progress, Plans, and Problems. Consolidate repeated
items, preserve important details, and write concise professional prose. If a
section has no supported content, state that no corresponding update was
provided.

Source materials:
{self.three_p_materials}

Return only the final 3P update.
""".strip()
        return self.llm.complete(prompt, "The LLM returned an empty 3P update.")

    def _write_newsletter(self) -> str:
        self.newsletter_materials = self._ask(
            "Provide announcements, important developments, team updates, "
            "milestones, meeting summaries, public reports, or other relevant "
            "materials to organize into a company newsletter:"
        )
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
{self.newsletter_materials}

Return only the final newsletter.
""".strip()
        return self.llm.complete(prompt, "The LLM returned an empty newsletter.")

    def _write_faq(self) -> str:
        self.faq_request = self._ask(
            "Provide the internal FAQ request, including the questions to answer "
            "and any relevant reference materials:"
        )
        prompt = f"""
Create an internal FAQ from the request and supporting information below.

Identify the employee questions, merge duplicates or questions with the same
intent, and organize them in a clear question-and-answer format. Every answer
must be grounded only in the supplied confirmed information. Do not infer or
invent policy decisions, dates, amounts, eligibility rules, or commitments. If
the available information does not support an answer, explicitly say that the
information is insufficient and identify what still requires clarification.

FAQ request and supporting information:
{self.faq_request}

Return only the final FAQ.
""".strip()
        return self.llm.complete(prompt, "The LLM returned an empty FAQ.")

    def _write_general(self) -> str:
        request_answer = self._ask(
            "Provide the target audience, communication purpose, desired tone, "
            "and format requirement for this internal communication in one answer:"
        )
        self.general_comms_request = self._parse_general_request(request_answer)
        self.general_comms_materials = self._ask(
            "Provide the announcements, background information, project updates, "
            "meeting content, reference text, or other relevant materials to use "
            "when drafting this internal communication:"
        )
        prompt = f"""
Draft a general internal communication using the specified communication
requirements and source materials.

Follow the requested target audience, purpose, tone, and format requirement.
Use only facts supported by the source materials. Do not invent dates, impacts,
actions, owners, or commitments. Preserve all material instructions that the
target audience needs, and return a polished ready-to-send communication.

Communication requirements:
{json.dumps(self.general_comms_request, ensure_ascii=False, indent=2)}

Source materials:
{self.general_comms_materials}

Return only the final communication.
""".strip()
        return self.llm.complete(
            prompt, "The LLM returned an empty internal communication."
        )

    def _parse_general_request(self, answer: str) -> dict[str, str]:
        prompt = f"""
Extract the four required fields from the user's single answer about a general
internal communication. Return only a JSON object with exactly these string
fields: target_audience, purpose, tone, and format_requirement. Preserve the
user's meaning and do not invent missing requirements; use an empty string for
any field the user did not provide.

User answer:
{answer}
""".strip()
        parsed = self.llm.complete_json(
            prompt, "The LLM returned an empty general communication request."
        )
        fields = ("target_audience", "purpose", "tone", "format_requirement")
        request: dict[str, str] = {}
        for field in fields:
            value = parsed.get(field, "")
            if not isinstance(value, str):
                raise RuntimeError(
                    f"The LLM returned a non-text value for {field}."
                )
            request[field] = value
        return request


def main() -> str:
    """Initialize the agent, run the dispatcher, and return its result."""
    return InternalCommsAssistant().run()


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("Input was interrupted.", file=sys.stderr)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
