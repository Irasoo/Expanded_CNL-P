from __future__ import annotations

from typing import Any

from llm_runtime import LLMRuntime


SUPPORTED_COMMUNICATION_TYPES = {"three_p", "newsletter", "faq", "general", "unknown"}


def classify_communication_type(llm: LLMRuntime, user_selection: str) -> str:
    prompt = f"""
Map the user's selection to exactly one internal communication type.

Allowed values:
- three_p: a Progress, Plans, and Problems team update
- newsletter: a company-internal newsletter
- faq: an internal questions-and-answers communication
- general: another internal communication format
- unknown: the selection cannot be confidently mapped to one of the four types

Interpret natural-language descriptions and common equivalent names. Do not
guess when the request is ambiguous or unrelated.

User selection:
{user_selection}

Return only a JSON object in this exact shape:
{{"communication_type": "three_p|newsletter|faq|general|unknown"}}
""".strip()
    payload = llm.complete_json(
        prompt,
        empty_result_error="The LLM returned an empty communication type classification.",
    )
    value = payload.get("communication_type")
    if not isinstance(value, str) or value not in SUPPORTED_COMMUNICATION_TYPES:
        raise RuntimeError("The LLM returned an invalid communication type.")
    return value


def parse_general_comms_request(llm: LLMRuntime, user_input: str) -> dict[str, str]:
    prompt = f"""
Extract the general internal communication requirements from the user's single
response. Do not add requirements the user did not provide. Each required
field must be a string; use an empty string when that field was not specified.

User response:
{user_input}

Return only a JSON object with exactly these fields:
{{
  "target_audience": "...",
  "purpose": "...",
  "tone": "...",
  "format_requirement": "..."
}}
""".strip()
    payload = llm.complete_json(
        prompt,
        empty_result_error="The LLM returned empty general communication requirements.",
    )
    expected_fields = (
        "target_audience",
        "purpose",
        "tone",
        "format_requirement",
    )
    result: dict[str, str] = {}
    for field in expected_fields:
        value: Any = payload.get(field)
        if not isinstance(value, str):
            raise RuntimeError(f"The extracted field {field!r} is not text.")
        result[field] = value.strip()
    return result


def draft_three_p(llm: LLMRuntime, team_name: str, source_materials: str) -> str:
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
    return llm.complete(prompt, empty_result_error="The LLM returned an empty 3P update.")


def draft_company_newsletter(llm: LLMRuntime, source_materials: str) -> str:
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
    return llm.complete(prompt, empty_result_error="The LLM returned an empty newsletter.")


def draft_faq(llm: LLMRuntime, request: str) -> str:
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
    return llm.complete(prompt, empty_result_error="The LLM returned an empty FAQ.")


def draft_general_comms(
    llm: LLMRuntime, request: dict[str, str], source_materials: str
) -> str:
    import json

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
    return llm.complete(
        prompt,
        empty_result_error="The LLM returned an empty internal communication.",
    )

