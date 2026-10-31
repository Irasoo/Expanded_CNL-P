from __future__ import annotations

from cnlp_compiler.code_generator.reference_code_catalog import (
    register_function,
)


@register_function(
    description=(
        "Generate a factually grounded and clearly structured team update "
        "with Progress, Plans, and Problems sections from the user-provided "
        "team name and source materials."
    )
)
def draft_three_p(
    team_name: str,
    source_materials: str,
) -> str:
    import os

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

    client_options: dict[str, str] = {"api_key": api_key}
    if base_url:
        client_options["base_url"] = base_url.rstrip("/")
    client = OpenAI(**client_options)
    response = client.responses.create(model=model, input=prompt)
    result = str(response.output_text or "").strip()
    if not result:
        raise RuntimeError("The LLM returned an empty 3P update.")
    return result


@register_function(
    description=(
        "Generate a company-internal newsletter from recent company "
        "materials by removing duplicate content, prioritizing important "
        "information with broad relevance, and organizing it by theme."
    )
)
def draft_company_newsletter(source_materials: str) -> str:
    import os

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

    client_options: dict[str, str] = {"api_key": api_key}
    if base_url:
        client_options["base_url"] = base_url.rstrip("/")
    client = OpenAI(**client_options)
    response = client.responses.create(model=model, input=prompt)
    result = str(response.output_text or "").strip()
    if not result:
        raise RuntimeError("The LLM returned an empty newsletter.")
    return result


@register_function(
    description=(
        "Generate a factually grounded internal FAQ from employee questions "
        "and confirmed supporting materials, merging duplicate questions "
        "and clearly identifying answers with insufficient information."
    )
)
def draft_faq(request: str) -> str:
    import os

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

    client_options: dict[str, str] = {"api_key": api_key}
    if base_url:
        client_options["base_url"] = base_url.rstrip("/")
    client = OpenAI(**client_options)
    response = client.responses.create(model=model, input=prompt)
    result = str(response.output_text or "").strip()
    if not result:
        raise RuntimeError("The LLM returned an empty FAQ.")
    return result


@register_function(
    description=(
        "Generate an internal communication from structured communication "
        "requirements and source materials that follows the requested target "
        "audience, purpose, tone, and format."
    )
)
def draft_general_comms(request: dict, source_materials: str) -> str:
    import json
    import os

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

    client_options: dict[str, str] = {"api_key": api_key}
    if base_url:
        client_options["base_url"] = base_url.rstrip("/")
    client = OpenAI(**client_options)
    response = client.responses.create(model=model, input=prompt)
    result = str(response.output_text or "").strip()
    if not result:
        raise RuntimeError("The LLM returned an empty internal communication.")
    return result
