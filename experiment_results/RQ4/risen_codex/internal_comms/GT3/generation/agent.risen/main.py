"""Terminal agent for drafting company-internal communications."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class InternalCommsAssistant:
    """Dispatch one user request to the appropriate internal-comms writer."""

    _COMMUNICATION_TYPES = ("three_p", "newsletter", "faq", "general")

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
        self.diagnostic_message = ""
        self._dotenv_values = self._read_dotenv()
        self._client: Any | None = None

    @staticmethod
    def _read_dotenv() -> dict[str, str]:
        """Read a local .env as a fallback without depending on extra packages."""

        values: dict[str, str] = {}
        dotenv_path = Path.cwd() / ".env"
        if not dotenv_path.is_file():
            return values

        try:
            lines = dotenv_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return values

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
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            elif " #" in value:
                value = value.split(" #", 1)[0].rstrip()
            if key:
                values[key] = value
        return values

    def _setting(self, name: str) -> str:
        return os.environ.get(name, "").strip() or self._dotenv_values.get(name, "").strip()

    def _get_client(self) -> tuple[Any, str]:
        if self._client is not None:
            return self._client

        api_key = self._setting("OPENAI_API_KEY")
        model = self._setting("CNLP_REFERENCE_LLM_MODEL") or self._setting("OPENAI_MODEL")
        base_url = self._setting("BASE_URL")
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
        self._client = OpenAI(**client_options)
        return self._client, model

    def _complete(self, prompt: str, empty_message: str) -> str:
        client, model = self._get_client()
        response = client.responses.create(
            model=model,
            input=prompt,
            reasoning={"effort": "high"},
        )
        result = str(getattr(response, "output_text", "") or "").strip()
        if not result:
            raise RuntimeError(empty_message)
        return result

    @staticmethod
    def _json_from_model(text: str) -> Any:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    pass
            start = cleaned.find("[")
            end = cleaned.rfind("]")
            if start >= 0 and end > start:
                try:
                    return json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    pass
        raise RuntimeError("The language model returned an invalid structured result.")

    def _ask(self, prompt: str) -> str:
        try:
            return input(prompt)
        except EOFError as exc:
            raise RuntimeError("No answer was received from standard input.") from exc

    def _classify_type(self, selection: str) -> str:
        prompt = f"""
Determine which supported internal communication type the user's selection requests.
The only permitted values are exactly: three_p, newsletter, faq, and general.
If the selection does not clearly request one of those four types, use unknown.
Understand the selection semantically, including natural-language descriptions, but
do not guess when it is ambiguous. Return only a JSON object with one key, type,
whose value is one of the five permitted values.

User selection:
{selection}
""".strip()
        result = self._json_from_model(
            self._complete(prompt, "The language model returned an empty communication type.")
        )
        selected = result.get("type") if isinstance(result, dict) else None
        if selected not in (*self._COMMUNICATION_TYPES, "unknown"):
            raise RuntimeError("The language model returned an unsupported communication type.")
        return selected

    def _parse_general_request(self, answer: str) -> dict[str, str]:
        prompt = f"""
Interpret the user's single answer as the requirements for a general internal
communication. Extract exactly these four text fields: target_audience, purpose,
tone, and format_requirement. Preserve the user's meaning and wording as much as
possible. Do not invent missing requirements; use an empty string for a field that
was not specified. Return only a JSON object containing all four keys with string
values.

User's answer:
{answer}
""".strip()
        result = self._json_from_model(
            self._complete(
                prompt,
                "The language model returned an empty general communication request.",
            )
        )
        if not isinstance(result, dict):
            raise RuntimeError("The language model returned an invalid general communication request.")
        fields = ("target_audience", "purpose", "tone", "format_requirement")
        parsed: dict[str, str] = {}
        for field in fields:
            value = result.get(field)
            if not isinstance(value, str):
                raise RuntimeError(
                    "The language model did not return all general communication fields as text."
                )
            parsed[field] = value
        return parsed

    def _three_p_writer(self) -> str:
        self.three_p_materials = self._ask(
            "Provide the team update materials to organize into a 3P update:\n> "
        )
        self.team_name = self._ask("Provide the name of the team covered by this 3P update:\n> ")
        return self._complete(
            f"""
Draft an internal 3P team update for {self.team_name}.

Use only the supplied source materials. Do not invent facts, dates, owners,
metrics, commitments, or risks. Organize the result into exactly these three
clearly labelled sections: Progress, Plans, and Problems. Consolidate repeated
items, preserve important details, and write concise professional prose. If a
section has no supported content, state that no corresponding update was provided.

Source materials:
{self.three_p_materials}

Return only the final 3P update.
""".strip(),
            "The LLM returned an empty 3P update.",
        )

    def _newsletter_writer(self) -> str:
        self.newsletter_materials = self._ask(
            "Provide announcements, important developments, team updates, milestones, "
            "meeting summaries, public reports, or other relevant materials for a company newsletter:\n> "
        )
        return self._complete(
            f"""
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
""".strip(),
            "The LLM returned an empty newsletter.",
        )

    def _faq_writer(self) -> str:
        self.faq_request = self._ask(
            "Provide the internal FAQ request, including the questions to answer and any relevant reference materials:\n> "
        )
        return self._complete(
            f"""
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
""".strip(),
            "The LLM returned an empty FAQ.",
        )

    def _general_comms_writer(self) -> str:
        requirements_answer = self._ask(
            "Provide the target audience, communication purpose, desired tone, and format requirement "
            "for this internal communication in one answer:\n> "
        )
        self.general_comms_request = self._parse_general_request(requirements_answer)
        self.general_comms_materials = self._ask(
            "Provide the announcements, background information, project updates, meeting content, "
            "reference text, or other relevant materials for the communication:\n> "
        )
        return self._complete(
            f"""
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
""".strip(),
            "The LLM returned an empty internal communication.",
        )

    def run(self) -> str:
        selection = self._ask(
            "Select the internal communication type to generate (three_p, newsletter, faq, or general):\n> "
        )
        self.communication_type = self._classify_type(selection)

        if self.communication_type == "unknown":
            self.diagnostic_message = (
                "The internal communication type selected by the user cannot be recognized."
            )
            print(self.diagnostic_message)
            print("Currently supported types are: three_p, newsletter, faq, and general.")
            return self.diagnostic_message

        if self.communication_type == "three_p":
            self.final_communication = self._three_p_writer()
        elif self.communication_type == "newsletter":
            self.final_communication = self._newsletter_writer()
        elif self.communication_type == "faq":
            self.final_communication = self._faq_writer()
        else:
            self.final_communication = self._general_comms_writer()

        print(self.final_communication)
        return self.final_communication


def main() -> str:
    """Initialize the assistant, run the dispatcher, and return its result."""

    assistant = InternalCommsAssistant()
    try:
        return assistant.run()
    except Exception as exc:
        message = f"Error: {exc}"
        print(message)
        return message


if __name__ == "__main__":
    main()
