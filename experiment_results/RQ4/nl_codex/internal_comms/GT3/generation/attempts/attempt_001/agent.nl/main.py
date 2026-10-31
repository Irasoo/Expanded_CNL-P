"""Terminal agent for drafting company-internal communications."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


SUPPORTED_TYPES = ("three_p", "newsletter", "faq", "general")


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries from the local .env when unset."""
    env_path = Path.cwd() / ".env"
    if not env_path.is_file():
        return

    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for line in lines:
        entry = line.strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue
        key, value = entry.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ[key] = value


def _configuration() -> tuple[str, str, str]:
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


def _client_and_model() -> tuple[Any, str]:
    from openai import OpenAI

    api_key, model, base_url = _configuration()
    client_options: dict[str, str] = {"api_key": api_key}
    if base_url:
        client_options["base_url"] = base_url.rstrip("/")
    return OpenAI(**client_options), model


def _ask_model(prompt: str) -> str:
    client, model = _client_and_model()
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    result = str(response.output_text or "").strip()
    if not result:
        raise RuntimeError("The LLM returned an empty response.")
    return result


def _json_from_model(text: str) -> Any:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("The LLM returned invalid JSON.") from None
        try:
            return json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            raise RuntimeError("The LLM returned invalid JSON.") from None


def _recognize_type(selection: str) -> str:
    prompt = f"""
Interpret the user's requested internal communication type.

Map the answer to exactly one of these values: three_p, newsletter, faq, or
general. Understand natural-language descriptions and equivalent expressions,
but do not guess when the answer does not clearly identify one of them. In
that case use unknown.

Return only a JSON object with exactly this shape:
{{"communication_type": "three_p|newsletter|faq|general|unknown"}}

User answer:
{selection}
""".strip()
    parsed = _json_from_model(_ask_model(prompt))
    value = parsed.get("communication_type") if isinstance(parsed, dict) else None
    if value not in SUPPORTED_TYPES and value != "unknown":
        raise RuntimeError("The LLM returned an unsupported communication type.")
    return value


def _parse_general_request(answer: str) -> dict[str, str]:
    prompt = f"""
Extract the general internal communication requirements from the user's single
answer. Identify the target audience, communication purpose, desired tone, and
format requirement. Preserve the user's meaning and do not invent missing
requirements. Every value must be text; use an empty string when a field was
not provided.

Return only a JSON object with exactly these four string fields:
{{
  "target_audience": "",
  "purpose": "",
  "tone": "",
  "format_requirement": ""
}}

User answer:
{answer}
""".strip()
    parsed = _json_from_model(_ask_model(prompt))
    if not isinstance(parsed, dict):
        raise RuntimeError("The LLM returned an invalid general communication request.")
    fields = ("target_audience", "purpose", "tone", "format_requirement")
    request: dict[str, str] = {}
    for field in fields:
        value = parsed.get(field)
        if not isinstance(value, str):
            raise RuntimeError(
                "The LLM returned an invalid general communication request."
            )
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
    result = _ask_model(prompt)
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
    result = _ask_model(prompt)
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
    result = _ask_model(prompt)
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
    result = _ask_model(prompt)
    if not result:
        raise RuntimeError("The LLM returned an empty internal communication.")
    return result


class InternalCommsAssistant:
    """Coordinates the single dispatcher and its communication workers."""

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
            "Select a communication type (three_p, newsletter, faq, or general): "
        )
        self.communication_type = _recognize_type(selection)

        if self.communication_type == "unknown":
            print("The internal communication type selected by the user cannot be recognized.")
            print("Currently supported types are: three_p, newsletter, faq, and general.")
            return self.final_communication

        if self.communication_type == "three_p":
            self.three_p_materials = input(
                "Provide the team update materials to organize into a 3P update: "
            )
            self.team_name = input(
                "Provide the name of the team covered by this 3P update: "
            )
            self.final_communication = draft_three_p(
                team_name=self.team_name,
                source_materials=self.three_p_materials,
            )
        elif self.communication_type == "newsletter":
            self.newsletter_materials = input(
                "Provide announcements, developments, updates, milestones, meeting summaries, reports, or other newsletter materials: "
            )
            self.final_communication = draft_company_newsletter(
                source_materials=self.newsletter_materials
            )
        elif self.communication_type == "faq":
            self.faq_request = input(
                "Provide the internal FAQ request, including questions and relevant reference materials: "
            )
            self.final_communication = draft_faq(request=self.faq_request)
        else:
            request_answer = input(
                "Provide the target audience, communication purpose, desired tone, and format requirement: "
            )
            self.general_comms_request = _parse_general_request(request_answer)
            self.general_comms_materials = input(
                "Provide announcements, background information, project updates, meeting content, reference text, or other relevant materials: "
            )
            self.final_communication = draft_general_comms(
                request=self.general_comms_request,
                source_materials=self.general_comms_materials,
            )

        print(self.final_communication)
        return self.final_communication


def main() -> str:
    """Initialize the assistant, run the dispatcher, and return its result."""
    assistant = InternalCommsAssistant()
    try:
        return assistant.run()
    except (RuntimeError, OSError, EOFError, KeyboardInterrupt) as exc:
        print(f"Unable to complete the internal communication draft: {exc}")
        return ""


if __name__ == "__main__":
    main()
