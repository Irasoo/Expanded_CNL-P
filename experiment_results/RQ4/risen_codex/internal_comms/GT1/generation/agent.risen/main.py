"""Terminal agent for drafting company-internal communications.

The business flow in this module follows the supplied specification.  The
input fixtures are not needed at runtime.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


SUPPORTED_TYPES = ("three_p", "newsletter", "faq", "general")
UNKNOWN_TYPE = "unknown"


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries from .env without adding a dependency.

    Existing process environment variables deliberately win over .env values.
    """

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


def _runtime_settings() -> tuple[str, str, str]:
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
    # Import the official client only when the agent actually needs the model.
    from openai import OpenAI

    api_key, model, base_url = _runtime_settings()
    client_options: dict[str, str] = {"api_key": api_key}
    if base_url:
        client_options["base_url"] = base_url.rstrip("/")
    return OpenAI(**client_options), model


def _response_text(prompt: str) -> str:
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


def _json_from_model(prompt: str, error_message: str) -> dict[str, Any]:
    raw = _response_text(prompt)
    candidates = [raw]
    if "```" in raw:
        candidates.append(raw.replace("```json", "").replace("```", "").strip())
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError(error_message)


def recognize_communication_type(selection: str) -> str:
    """Map the user's single selection to the specified closed vocabulary."""

    prompt = f"""
Interpret the user's single answer as a requested internal communication type.
Map it to exactly one of these values: three_p, newsletter, faq, general,
unknown.  Recognize clear natural-language equivalents, but use unknown when
the answer cannot be confidently mapped to one of the four supported types.
Return only a JSON object with the key communication_type and one of those exact
values.

User answer:
{selection}
""".strip()
    parsed = _json_from_model(
        prompt, "The LLM did not return a valid communication type."
    )
    value = parsed.get("communication_type")
    return value if value in SUPPORTED_TYPES else UNKNOWN_TYPE


def parse_general_request(answer: str) -> dict[str, str]:
    prompt = f"""
Interpret the user's single answer as the requirements for a general internal
communication. Extract exactly these required text fields: target_audience,
purpose, tone, and format_requirement. Preserve the user's meaning and do not
invent missing details; use an empty string for a field not specified. Return
only a JSON object with exactly those four keys, whose values are strings.

User answer:
{answer}
""".strip()
    parsed = _json_from_model(
        prompt, "The LLM did not return valid general communication requirements."
    )
    fields = (
        "target_audience",
        "purpose",
        "tone",
        "format_requirement",
    )
    return {field: str(parsed.get(field, "")) for field in fields}


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
    result = _response_text(prompt)
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
    return _response_text(prompt)


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
    return _response_text(prompt)


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
    return _response_text(prompt)


def _ask(prompt: str) -> str:
    print(prompt)
    return input().strip()


def _run_dispatcher() -> str | None:
    communication_type: str = UNKNOWN_TYPE
    final_communication = ""

    selection = _ask(
        "Select the internal communication type to generate (three_p, newsletter, faq, or general):"
    )
    communication_type = recognize_communication_type(selection)

    if communication_type == UNKNOWN_TYPE:
        diagnostic = "The internal communication type selected by the user cannot be recognized."
        print(diagnostic)
        print(
            "The selected communication type cannot be recognized. Currently supported types are: three_p, newsletter, faq, and general."
        )
        return None

    if communication_type == "three_p":
        three_p_materials = _ask(
            "Provide the team update materials to organize into a 3P update:"
        )
        team_name = _ask("Provide the name of the team covered by this 3P update:")
        final_communication = draft_three_p(team_name, three_p_materials)
    elif communication_type == "newsletter":
        newsletter_materials = _ask(
            "Provide announcements, important developments, team updates, milestones, meeting summaries, public reports, or other relevant materials for the company newsletter:"
        )
        final_communication = draft_company_newsletter(newsletter_materials)
    elif communication_type == "faq":
        faq_request = _ask(
            "Provide the internal FAQ request, including the questions to answer and any relevant reference materials:"
        )
        final_communication = draft_faq(faq_request)
    else:
        general_answer = _ask(
            "Provide the target audience, communication purpose, desired tone, and format requirement for this internal communication:"
        )
        general_comms_request = parse_general_request(general_answer)
        general_comms_materials = _ask(
            "Provide the announcements, background information, project updates, meeting content, reference text, or other relevant materials for this internal communication:"
        )
        final_communication = draft_general_comms(
            general_comms_request, general_comms_materials
        )

    print(final_communication)
    return final_communication


def main() -> str | None:
    """Initialize the agent, run the dispatcher, and return its result."""

    try:
        return _run_dispatcher()
    except (EOFError, KeyboardInterrupt):
        print("Input ended before the internal communication was completed.")
        return None
    except Exception as exc:
        print(f"Unable to generate the internal communication: {exc}")
        return None


if __name__ == "__main__":
    main()
