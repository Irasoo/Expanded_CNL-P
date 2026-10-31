from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


SUPPORTED_TYPES = ("three_p", "newsletter", "faq", "general")


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries without overriding process variables."""
    dotenv_path = Path(".env")
    if not dotenv_path.is_file():
        return

    try:
        lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"Unable to read .env: {exc}") from exc

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise RuntimeError(f"Invalid .env entry on line {line_number}.")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise RuntimeError(f"Invalid .env entry on line {line_number}.")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _get_llm_client() -> tuple[Any, str]:
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
    return OpenAI(**client_options), model


def _complete(prompt: str, empty_error: str) -> str:
    client, model = _get_llm_client()
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    result = str(response.output_text or "").strip()
    if not result:
        raise RuntimeError(empty_error)
    return result


def _parse_json_object(raw_text: str, error_message: str) -> dict[str, Any]:
    candidate = raw_text.strip()
    if candidate.startswith("```") and candidate.endswith("```"):
        candidate = candidate[3:-3].strip()
        if candidate.lower().startswith("json"):
            candidate = candidate[4:].lstrip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise RuntimeError(error_message) from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(error_message)
    return parsed


def _ask_user(prompt: str) -> str:
    sys.stdout.write(prompt.rstrip() + "\n")
    sys.stdout.flush()
    answer = sys.stdin.readline()
    if answer == "":
        raise RuntimeError("No user input was received.")
    return answer.rstrip("\r\n")


def _recognize_communication_type(selection: str) -> str:
    prompt = f"""
Interpret the user's selection of an internal communication type.

The only permitted results are: three_p, newsletter, faq, general, or unknown.
Map the user's meaning to exactly one permitted type when it is clear. If the
selection cannot be mapped confidently to one of the four supported types,
return unknown. Do not use any facts beyond the selection itself.

User selection:
{selection}

Return only a JSON object with this exact shape:
{{"communication_type": "three_p|newsletter|faq|general|unknown"}}
""".strip()
    raw_result = _complete(
        prompt,
        "The LLM returned an empty communication type recognition result.",
    )
    parsed = _parse_json_object(
        raw_result,
        "The LLM returned an invalid communication type recognition result.",
    )
    communication_type = parsed.get("communication_type")
    if communication_type not in SUPPORTED_TYPES:
        return "unknown"
    return communication_type


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


def _parse_general_request(answer: str) -> dict[str, str]:
    prompt = f"""
Interpret one user's answer describing requirements for a general internal
communication. Extract these four required text fields:
target_audience, purpose, tone, and format_requirement.

Preserve the user's meaning and wording where practical. Do not invent values;
use an empty string for a field the user did not specify. Return only a JSON
object with exactly those four keys and string values.

User answer:
{answer}
""".strip()
    raw_result = _complete(
        prompt,
        "The LLM returned an empty General Communication requirement result.",
    )
    parsed = _parse_json_object(
        raw_result,
        "The LLM returned invalid General Communication requirements.",
    )
    request: dict[str, str] = {}
    for field in ("target_audience", "purpose", "tone", "format_requirement"):
        value = parsed.get(field, "")
        if isinstance(value, str):
            request[field] = value
        else:
            request[field] = str(value)
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
    return _complete(
        prompt,
        "The LLM returned an empty internal communication.",
    )


def _run_three_p() -> str:
    three_p_materials = _ask_user(
        "Provide the team update materials to organize into a 3P update:"
    )
    team_name = _ask_user("Provide the name of the team covered by this 3P update:")
    final_communication = draft_three_p(team_name, three_p_materials)
    print(final_communication)
    return final_communication


def _run_newsletter() -> str:
    newsletter_materials = _ask_user(
        "Provide announcements, important developments, team updates, milestones, "
        "meeting summaries, public reports, or other relevant materials to organize "
        "into a company newsletter:"
    )
    final_communication = draft_company_newsletter(newsletter_materials)
    print(final_communication)
    return final_communication


def _run_faq() -> str:
    faq_request = _ask_user(
        "Provide the internal FAQ request, including the questions to answer and "
        "any relevant reference materials:"
    )
    final_communication = draft_faq(faq_request)
    print(final_communication)
    return final_communication


def _run_general() -> str:
    request_answer = _ask_user(
        "Provide the target audience, communication purpose, desired tone, and "
        "format requirement for this internal communication:"
    )
    general_comms_request = _parse_general_request(request_answer)
    general_comms_materials = _ask_user(
        "Provide the announcements, background information, project updates, meeting "
        "content, reference text, or other relevant materials to use when drafting "
        "this internal communication:"
    )
    final_communication = draft_general_comms(
        general_comms_request,
        general_comms_materials,
    )
    print(final_communication)
    return final_communication


def main() -> str:
    """Run InternalCommsDispatcher and return the final communication."""
    selection = _ask_user(
        "Select the internal communication type to generate: three_p, newsletter, "
        "faq, or general:"
    )
    communication_type = _recognize_communication_type(selection)

    if communication_type == "unknown":
        diagnostic = "The internal communication type selected by the user cannot be recognized."
        print(diagnostic)
        print(
            "Supported types are: three_p, newsletter, faq, and general."
        )
        return diagnostic

    if communication_type == "three_p":
        return _run_three_p()
    if communication_type == "newsletter":
        return _run_newsletter()
    if communication_type == "faq":
        return _run_faq()
    return _run_general()


if __name__ == "__main__":
    main()
