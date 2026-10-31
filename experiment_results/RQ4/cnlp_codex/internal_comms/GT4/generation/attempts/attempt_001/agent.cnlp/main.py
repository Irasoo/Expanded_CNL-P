"""Terminal agent for drafting grounded internal communications."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


PERSONA_AND_CONSTRAINTS = """
You are an assistant responsible for drafting company-internal communications.
Your users are company members who need clear, concise drafts. Never invent
company facts, project status, personnel decisions, organizational information,
dates, owners, metrics, commitments, policy decisions, or risks that are not
present in the user-provided material. Follow the requested format precisely.
""".strip()


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries without requiring a third-party package."""
    env_path = Path.cwd() / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
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


def _client_and_model() -> tuple[Any, str]:
    _load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("BASE_URL", "").strip()
    model = os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip() or os.getenv("OPENAI_MODEL", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured in .env or the environment.")
    if not model:
        raise RuntimeError("Neither CNLP_REFERENCE_LLM_MODEL nor OPENAI_MODEL is configured.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The openai package is required. Install it with: pip install openai") from exc
    options: dict[str, str] = {"api_key": api_key}
    if base_url:
        options["base_url"] = base_url.rstrip("/")
    return OpenAI(**options), model


def _ask_model(prompt: str) -> str:
    client, model = _client_and_model()
    response = client.responses.create(
        model=model,
        instructions=PERSONA_AND_CONSTRAINTS,
        input=prompt,
        reasoning={"effort": "high"},
    )
    text = str(response.output_text or "").strip()
    if not text:
        raise RuntimeError("The language model returned an empty response.")
    return text


def _json_from_model(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        candidate = "\n".join(lines[1:-1]).strip() if len(lines) >= 3 else candidate
    try:
        decoded = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The language model returned invalid structured data.") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError("The language model returned structured data in the wrong shape.")
    return decoded


def determine_communication_type(selection: str) -> str:
    result = _ask_model(
        """Classify the user's requested internal communication type. Map it to
exactly one of: three_p, newsletter, faq, general, unknown.

three_p means an update organized as Progress, Plans, and Problems.
newsletter means a broad internal company newsletter.
faq means a question-and-answer internal communication.
general means another internal communication request.
unknown means the selection cannot reasonably be mapped to one of the four
supported types. Return only JSON: {\"communication_type\": \"...\"}.

User selection:
"""
        + selection
    )
    communication_type = _json_from_model(result).get("communication_type")
    if communication_type not in {"three_p", "newsletter", "faq", "general", "unknown"}:
        return "unknown"
    return communication_type


def parse_general_comms_request(raw_request: str) -> dict[str, str]:
    result = _ask_model(
        """Extract the requirements for a general internal communication from the
single user response below. Return only a JSON object with exactly these string
fields: target_audience, purpose, tone, format_requirement. Preserve the user's
meaning. When a field is not supplied, use an empty string; do not invent it.

User response:
"""
        + raw_request
    )
    parsed = _json_from_model(result)
    fields = ("target_audience", "purpose", "tone", "format_requirement")
    return {field: str(parsed.get(field, "")).strip() for field in fields}


def draft_three_p(team_name: str, source_materials: str) -> str:
    return _ask_model(
        f"""Draft an internal 3P team update for {team_name}.

Use only the supplied source materials. Do not invent facts, dates, owners,
metrics, commitments, or risks. Organize the result into exactly these three
clearly labelled sections: Progress, Plans, and Problems. Consolidate repeated
items, preserve important details, and write concise professional prose. If a
section has no supported content, state that no corresponding update was
provided.

Source materials:
{source_materials}

Return only the final 3P update."""
    )


def draft_company_newsletter(source_materials: str) -> str:
    return _ask_model(
        f"""Create a concise company-internal newsletter from the supplied materials.

Use only supported facts. Remove duplicates and near-duplicates. Prioritize
updates with broad employee relevance, important achievements, upcoming events,
operational changes, and actionable reminders; omit overly narrow details that
do not help the wider audience. Group related items under clear thematic headings.
Make the result easy to scan. If enough useful material is available, select roughly
20 to 25 items; otherwise include only supported useful items without padding.

Source materials:
{source_materials}

Return only the final newsletter."""
    )


def draft_faq(request: str) -> str:
    return _ask_model(
        f"""Create an internal FAQ from the request and supporting information below.

Identify employee questions, merge duplicates or questions with the same intent,
and organize them in a clear question-and-answer format. Every answer must be
grounded only in the supplied confirmed information. Do not infer or invent policy
decisions, dates, amounts, eligibility rules, or commitments. If the available
information does not support an answer, explicitly say that the information is
insufficient and identify what still requires clarification.

FAQ request and supporting information:
{request}

Return only the final FAQ."""
    )


def draft_general_comms(request: dict[str, str], source_materials: str) -> str:
    serialized_request = json.dumps(request, ensure_ascii=False, indent=2)
    return _ask_model(
        f"""Draft a general internal communication using the specified communication
requirements and source materials.

Follow the requested target audience, purpose, tone, and format requirement.
Use only facts supported by the source materials. Do not invent dates, impacts,
actions, owners, or commitments. Preserve all material instructions that the
target audience needs, and return a polished ready-to-send communication.

Communication requirements:
{serialized_request}

Source materials:
{source_materials}

Return only the final communication."""
    )


def _input(prompt: str) -> str:
    """Execute one CNL-P INPUT command with exactly one terminal read."""
    print(prompt)
    return input("> ").strip()


def three_p_writer() -> str:
    three_p_materials = _input("Provide the team update materials to organize into a 3P update:")
    team_name = _input("Provide the name of the team covered by this 3P update:")
    final_communication = draft_three_p(team_name, three_p_materials)
    print(final_communication)
    return final_communication


def newsletter_writer() -> str:
    newsletter_materials = _input(
        "Provide announcements, important developments, team updates, milestones, "
        "meeting summaries, public reports, or other relevant newsletter materials:"
    )
    final_communication = draft_company_newsletter(newsletter_materials)
    print(final_communication)
    return final_communication


def faq_writer() -> str:
    faq_request = _input(
        "Provide the internal FAQ request, including questions to answer and any "
        "relevant reference materials:"
    )
    final_communication = draft_faq(faq_request)
    print(final_communication)
    return final_communication


def general_comms_writer() -> str:
    raw_request = _input(
        "Provide the target audience, communication purpose, desired tone, and "
        "format requirement:"
    )
    general_comms_request = parse_general_comms_request(raw_request)
    general_comms_materials = _input(
        "Provide announcements, background information, project updates, meeting "
        "content, reference text, or other materials for this communication:"
    )
    final_communication = draft_general_comms(
        general_comms_request, general_comms_materials
    )
    print(final_communication)
    return final_communication


def internal_comms_dispatcher() -> str | None:
    communication_type = determine_communication_type(
        _input(
            "Select the internal communication type: three_p, newsletter, faq, "
            "or general:"
        )
    )
    if communication_type == "unknown":
        print(
            "The selected communication type cannot be recognized. Supported types "
            "are three_p, newsletter, faq, and general."
        )
        return None
    if communication_type == "three_p":
        return three_p_writer()
    if communication_type == "newsletter":
        return newsletter_writer()
    if communication_type == "faq":
        return faq_writer()
    return general_comms_writer()


def main() -> str | None:
    """Initialize the Agent, run its entry Worker, and return its final result."""
    try:
        return internal_comms_dispatcher()
    except (EOFError, KeyboardInterrupt):
        print("\nInput cancelled.")
        return None
    except Exception as exc:
        print(f"Unable to generate the internal communication: {exc}")
        return None


if __name__ == "__main__":
    main()
