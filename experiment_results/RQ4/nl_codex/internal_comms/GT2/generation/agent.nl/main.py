from __future__ import annotations

import json
import os


SUPPORTED_TYPES = {"three_p", "newsletter", "faq", "general"}


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _client():
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = (os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip()
             or os.getenv("OPENAI_MODEL", "").strip())
    base_url = os.getenv("BASE_URL", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    if not model:
        raise RuntimeError("Neither CNLP_REFERENCE_LLM_MODEL nor OPENAI_MODEL is configured.")
    options = {"api_key": api_key}
    if base_url:
        options["base_url"] = base_url.rstrip("/")
    return OpenAI(**options), model


def _ask_llm(prompt: str) -> str:
    client, model = _client()
    response = client.responses.create(
        model=model, input=prompt, reasoning={"effort": "high"}
    )
    result = str(response.output_text or "").strip()
    if not result:
        raise RuntimeError("The language model returned an empty result.")
    return result


def draft_three_p(team_name: str, source_materials: str) -> str:
    return _ask_llm(f"""
Draft an internal 3P team update for {team_name}.
Use only the supplied source materials. Do not invent facts, dates, owners,
metrics, commitments, or risks. Organize the result into exactly these three
clearly labelled sections: Progress, Plans, and Problems. Consolidate repeated
items and write concise professional prose. If a section has no supported
content, state that no corresponding update was provided.

Source materials:
{source_materials}

Return only the final 3P update.
""".strip())


def draft_company_newsletter(source_materials: str) -> str:
    return _ask_llm(f"""
Create a concise company-internal newsletter from the supplied materials.
Use only supported facts. Remove duplicates and near-duplicates. Prioritize
updates with broad employee relevance, achievements, upcoming events,
operational changes, and actionable reminders; omit overly narrow details.
Group related items under clear thematic headings. If enough useful material is
available, select roughly 20 to 25 items; otherwise include only supported
useful items without padding or invention.

Source materials:
{source_materials}

Return only the final newsletter.
""".strip())


def draft_faq(request: str) -> str:
    return _ask_llm(f"""
Create an internal FAQ from the request and supporting information below.
Identify employee questions, merge duplicates, and organize a clear
question-and-answer format. Every answer must use only confirmed information.
Do not infer or invent policy decisions, dates, amounts, eligibility rules, or
commitments. If information is insufficient, explicitly say so and identify
what requires clarification.

FAQ request and supporting information:
{request}

Return only the final FAQ.
""".strip())


def draft_general_comms(request: dict[str, str], source_materials: str) -> str:
    return _ask_llm(f"""
Draft a general internal communication using these requirements and materials.
Follow the target audience, purpose, tone, and format requirement. Use only
facts supported by the source materials. Do not invent dates, impacts, actions,
owners, or commitments. Preserve all instructions the audience needs.

Communication requirements:
{json.dumps(request, ensure_ascii=False, indent=2)}

Source materials:
{source_materials}

Return only the final communication.
""".strip())


def _interpret_type(answer: str) -> str:
    raw = _ask_llm(f"""
Classify the user's requested internal communication type. Return exactly one
JSON object with the key communication_type and one value from: three_p,
newsletter, faq, general, unknown. Map clear natural-language equivalents;
use unknown when it cannot be recognized. User selection:
{answer}
""".strip())
    try:
        value = json.loads(raw).get("communication_type", "unknown")
    except (json.JSONDecodeError, AttributeError):
        value = "unknown"
    return value if value in SUPPORTED_TYPES else "unknown"


def _parse_general_request(answer: str) -> dict[str, str]:
    raw = _ask_llm(f"""
Extract the four required fields from this single user answer. Return exactly
JSON with string values for target_audience, purpose, tone, and
format_requirement. Do not invent missing information; use an empty string.
User answer:
{answer}
""".strip())
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Could not interpret the general communication requirements.") from exc
    return {field: str(data.get(field, "")).strip() for field in
            ("target_audience", "purpose", "tone", "format_requirement")}


def _input(prompt: str) -> str:
    print(prompt)
    return input().strip()


def main() -> str:
    _load_dotenv()
    selected = _input("Select communication type (three_p, newsletter, faq, or general):")
    communication_type = _interpret_type(selected)
    if communication_type == "unknown":
        message = "The internal communication type selected by the user cannot be recognized."
        print(message)
        print("Currently supported types are: three_p, newsletter, faq, and general.")
        return message

    if communication_type == "three_p":
        materials = _input("Provide the team update materials to organize into a 3P update:")
        team_name = _input("Provide the name of the team covered by this 3P update:")
        result = draft_three_p(team_name, materials)
    elif communication_type == "newsletter":
        materials = _input("Provide announcements, developments, updates, milestones, summaries, reports, or other newsletter materials:")
        result = draft_company_newsletter(materials)
    elif communication_type == "faq":
        request = _input("Provide the internal FAQ request, including questions and relevant reference materials:")
        result = draft_faq(request)
    else:
        request = _parse_general_request(_input("Provide target audience, purpose, desired tone, and format requirement in one answer:"))
        materials = _input("Provide the announcements, background, updates, meeting content, or other drafting materials:")
        result = draft_general_comms(request, materials)
    print(result)
    return result


if __name__ == "__main__":
    main()
