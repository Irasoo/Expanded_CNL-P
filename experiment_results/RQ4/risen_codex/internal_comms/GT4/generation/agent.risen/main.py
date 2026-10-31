"""Terminal agent for drafting internal company communications."""

from __future__ import annotations

import json
import os
from typing import Any


SUPPORTED_TYPES = ("three_p", "newsletter", "faq", "general")


def _load_dotenv() -> None:
    """Load simple KEY=VALUE pairs from .env without overwriting the process."""
    dotenv_path = os.path.join(os.getcwd(), ".env")
    try:
        with open(dotenv_path, "r", encoding="utf-8") as dotenv_file:
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
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _client_and_model() -> tuple[Any, str]:
    from openai import OpenAI

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

    client_options: dict[str, str] = {"api_key": api_key}
    if base_url:
        client_options["base_url"] = base_url.rstrip("/")
    return OpenAI(**client_options), model


def _complete(prompt: str, empty_message: str) -> str:
    client, model = _client_and_model()
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    result = str(response.output_text or "").strip()
    if not result:
        raise RuntimeError(empty_message)
    return result


def _recognize_type(selection: str) -> str:
    prompt = f"""
Determine which supported internal communication type the user's selection
requests. Return exactly one token and nothing else: three_p, newsletter, faq,
general, or unknown.

Map natural-language descriptions to the closest supported type. Use unknown
when the request cannot reasonably be mapped to one of the four supported
types. Do not treat this as a request to draft content.

User selection:
{selection}
""".strip()
    result = _complete(prompt, "The LLM returned an empty communication type.")
    normalized = result.strip().lower().strip("` \t\n.,:;\"'")
    return normalized if normalized in SUPPORTED_TYPES else "unknown"


def _parse_general_request(answer: str) -> dict[str, str]:
    prompt = f"""
Extract the four required fields from the user's internal communication
requirements. Return only a valid JSON object with exactly these string keys:
target_audience, purpose, tone, format_requirement.

Interpret the user's single answer semantically. Preserve the user's meaning;
do not invent missing values. If a required field is not specified, use an
empty string for that field. Each value must be a string.

User requirements:
{answer}
""".strip()
    raw = _complete(prompt, "The LLM returned empty general communication requirements.")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The LLM returned invalid general communication requirements.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("The LLM returned invalid general communication requirements.")
    request: dict[str, str] = {}
    for field in (
        "target_audience",
        "purpose",
        "tone",
        "format_requirement",
    ):
        value = parsed.get(field, "")
        request[field] = "" if value is None else str(value)
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
    return _complete(prompt, "The LLM returned an empty 3P update.")


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
    return _complete(prompt, "The LLM returned an empty newsletter.")


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
    return _complete(prompt, "The LLM returned an empty FAQ.")


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
    return _complete(prompt, "The LLM returned an empty internal communication.")


def _run_dispatcher() -> str | None:
    communication_type = "unknown"
    selection = input(
        "Select the internal communication type (three_p, newsletter, faq, or general): "
    )
    communication_type = _recognize_type(selection)

    if communication_type == "unknown":
        message = "The internal communication type selected by the user cannot be recognized."
        print(message)
        print("Currently supported types are: three_p, newsletter, faq, and general.")
        return message

    if communication_type == "three_p":
        three_p_materials = input(
            "Provide the team update materials to organize into a 3P update: "
        )
        team_name = input("Provide the name of the team covered by this 3P update: ")
        final_communication = draft_three_p(team_name, three_p_materials)
    elif communication_type == "newsletter":
        newsletter_materials = input(
            "Provide announcements, developments, updates, milestones, summaries, "
            "reports, or other newsletter materials: "
        )
        final_communication = draft_company_newsletter(newsletter_materials)
    elif communication_type == "faq":
        faq_request = input(
            "Provide the internal FAQ request, including questions and relevant reference materials: "
        )
        final_communication = draft_faq(faq_request)
    else:
        general_answer = input(
            "Provide the target audience, communication purpose, desired tone, and "
            "format requirement for this internal communication: "
        )
        general_comms_request = _parse_general_request(general_answer)
        general_comms_materials = input(
            "Provide the announcements, background information, project updates, "
            "meeting content, reference text, or other relevant materials: "
        )
        final_communication = draft_general_comms(
            general_comms_request, general_comms_materials
        )

    print(final_communication)
    return final_communication


def main() -> str | None:
    """Initialize and run InternalCommsAssistant, returning its final result."""
    _load_dotenv()
    return _run_dispatcher()


if __name__ == "__main__":
    main()
