"""CreativeDirectorAssistant: a terminal-driven creative concept workflow."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


BRIEF_FIELDS = (
    "brand",
    "product",
    "target_audience",
    "objective",
    "key_product_benefit",
    "channels",
    "budget",
    "constraints",
)


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries without requiring an extra dependency."""
    dotenv_path = Path.cwd() / ".env"
    if not dotenv_path.is_file():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _client_and_model() -> tuple[Any, str]:
    _load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("BASE_URL")
    model = os.environ.get("CNLP_REFERENCE_LLM_MODEL") or os.environ.get(
        "OPENAI_MODEL"
    )
    missing = []
    if not api_key:
        missing.append("OPENAI_API_KEY")
    if not base_url:
        missing.append("BASE_URL")
    if not model:
        missing.append("CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL")
    if missing:
        raise RuntimeError(
            "Missing runtime model configuration: " + ", ".join(missing)
        )

    from openai import OpenAI

    return OpenAI(api_key=api_key, base_url=base_url), model


def _response_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("The language model returned no usable text.")
    return text.strip()


def _first_json_object(text: str) -> str:
    """Extract the first balanced JSON object, respecting quoted strings."""
    start = text.find("{")
    if start < 0:
        return text
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return text[start:]


def _remove_trailing_commas(text: str) -> str:
    characters: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            characters.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            characters.append(char)
        elif char == ",":
            next_index = index + 1
            while next_index < len(text) and text[next_index].isspace():
                next_index += 1
            if next_index < len(text) and text[next_index] in "}]":
                index += 1
                continue
            characters.append(char)
        else:
            characters.append(char)
        index += 1
    return "".join(characters)


def _parse_json(text: str, operation: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    cleaned = _remove_trailing_commas(_first_json_object(cleaned))
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{operation} returned invalid JSON: {cleaned}") from exc
    if not isinstance(result, dict):
        raise ValueError(f"{operation} must return a JSON object.")
    return result


def _call_model(prompt: str) -> str:
    client, model = _client_and_model()
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    return _response_text(response)


def parse_creative_brief(answer: str) -> dict[str, str]:
    prompt = f"""
You are converting one user's complete creative brief into structured data.
Extract only information stated or clearly implied by the answer. Do not
invent facts. Every field is required and must be a concise text string. If a
field is not supplied, say so explicitly in that field rather than guessing.
Return one valid JSON object only with exactly these fields:
{json.dumps(BRIEF_FIELDS, ensure_ascii=False)}

USER'S SINGLE BRIEF ANSWER:
{answer}
"""
    result = _parse_json(_call_model(prompt), "creative brief parser")
    brief: dict[str, str] = {}
    for field in BRIEF_FIELDS:
        value = result.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Creative brief field '{field}' is missing or invalid.")
        brief[field] = value.strip()
    return brief


def generate_initial_concept(creative_brief: dict[str, str]) -> str:
    prompt = f"""
You are CreativeConceptDeveloper, a senior creative director.
Generate one complete, specific marketing creative concept from the supplied
brief. Clearly describe the core idea, principal execution, brand or product
role, and how the idea serves the target audience and marketing objective.
Ground every claim and execution detail in the brief. Do not invent product
capabilities, budgets, resources, partnerships, technologies, research,
audiences, or objectives. Respect the requested channels and constraints.
Return only the concept, not JSON, scores, alternatives, or commentary about
this instruction.

CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}
"""
    concept = _call_model(prompt).strip()
    if not concept:
        raise ValueError("Initial concept generation returned an empty concept.")
    return concept


def evaluate_creative_concept(
    creative_brief: dict[str, str], creative_concept: str
) -> dict[str, Any]:
    scoring_rubric = """
You are evaluating an advertising or marketing creative concept.

Score each criterion from 1 to 10 using the full scale. A strong, clearly
branded, relevant, workable concept may receive an 8; 9-10 are reserved for
unusually strong work.

1. ORIGINALITY — weight 0.30: distinctiveness and a meaningful product-specific
idea, from generic (1-3) through strong and memorable (8) to exceptional (9-10).
2. STRATEGIC FIT — weight 0.30: audience, objective, product benefit, channels,
budget, and constraints, from missed brief (1-3) through clear relevance (6-7)
to a precise, powerful solution (9-10).
3. AUDIENCE IMPACT — weight 0.20: clarity, attention, emotional or behavioral
hook, and memorability, from flat/confusing (1-3) to compelling (9-10).
4. EXECUTABILITY — weight 0.20: practical, repeatable execution that fits the
brief's budget, channels, and constraints, from infeasible (1-3) to efficient
and readily reusable (9-10).

Ground every judgment in the supplied brief and concept. Do not invent facts.
Explain the major strengths and weaknesses, and give concrete refinement
directions that address weak criteria while preserving useful strengths.
Return one strict JSON object only, with integer scores and exactly these
fields: originality_score, strategic_fit_score, audience_impact_score,
executability_score, evaluation_reasons, refinement_suggestions.
"""
    prompt = f"""
{scoring_rubric}

CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}

CURRENT CREATIVE CONCEPT:
{creative_concept}
"""
    result = _parse_json(_call_model(prompt), "creative evaluation")
    score_fields = (
        "originality_score",
        "strategic_fit_score",
        "audience_impact_score",
        "executability_score",
    )
    scores: dict[str, float] = {}
    for field in score_fields:
        value = result.get(field)
        if isinstance(value, bool):
            raise ValueError(f"{field} must be numeric.")
        try:
            score = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be numeric.") from exc
        if not 1 <= score <= 10:
            raise ValueError(f"{field} must be between 1 and 10, received {score}.")
        scores[field] = score

    reasons = str(result.get("evaluation_reasons", "")).strip()
    suggestions = str(result.get("refinement_suggestions", "")).strip()
    if not reasons or not suggestions:
        raise ValueError(
            "Evaluation must contain evaluation_reasons and refinement_suggestions."
        )

    criteria = {
        "originality": scores["originality_score"],
        "strategic_fit": scores["strategic_fit_score"],
        "audience_impact": scores["audience_impact_score"],
        "executability": scores["executability_score"],
    }
    overall = (
        scores["originality_score"] * 0.30
        + scores["strategic_fit_score"] * 0.30
        + scores["audience_impact_score"] * 0.20
        + scores["executability_score"] * 0.20
    )
    minimum = min(criteria.values())
    return {
        **scores,
        "overall_score": round(overall, 2),
        "weak_criteria": [name for name, score in criteria.items() if score == minimum],
        "evaluation_reasons": reasons,
        "refinement_suggestions": suggestions,
    }


def refine_creative_concept(
    creative_brief: dict[str, str], current_concept: str, evaluation: dict[str, Any]
) -> str:
    methodology = """
Revise the existing advertising or marketing concept once. Improve its weakest
criteria while preserving useful strengths and fidelity to the original brief.
For originality, use a more distinctive product-, brand-, audience-, or
context-specific mechanism. For strategic fit, strengthen the connection to
the audience, objective, benefit, channels, budget, and constraints. For
audience impact, sharpen the opening hook, clarity, emotional or behavioral
payoff, and memorability. For executability, simplify unnecessary elements and
make the execution practical, repeatable, and channel-appropriate.

Do not invent capabilities, budgets, partners, celebrities, technologies,
research, or market facts. Do not add messages merely to hide a weakness. Keep
the product or brand meaningful to the central idea. Return one complete
revised concept, not alternatives, scores, JSON, or process commentary.
"""
    prompt = f"""
{methodology}

ORIGINAL CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}

CURRENT CREATIVE CONCEPT:
{current_concept}

CURRENT EVALUATION:
{json.dumps(evaluation, ensure_ascii=False, indent=2)}

PRIMARY WEAK CRITERIA:
{json.dumps(evaluation["weak_criteria"], ensure_ascii=False)}
"""
    revised = _call_model(prompt).strip()
    if not revised:
        raise ValueError("Concept refinement returned an empty concept.")
    return revised


def _present(final_result: dict[str, Any]) -> None:
    print("\nFINAL CREATIVE CONCEPT\n")
    print(final_result["creative_concept"])
    print("\nEVALUATION\n")
    print(json.dumps(final_result["evaluation"], ensure_ascii=False, indent=2))
    print(f"\nREFINEMENTS: {final_result['refinement_count']}")
    if final_result["quality_threshold_met"]:
        print("QUALITY THRESHOLD: MET (overall score >= 8.0)")
    else:
        print(
            "QUALITY THRESHOLD: NOT MET; the two-refinement limit was reached "
            "without satisfying the threshold."
        )


def main() -> dict[str, Any]:
    """Run the complete CreativeDirectorAssistant workflow and return its result."""
    print(
        "Provide one complete creative brief containing the brand, product, "
        "target audience, objective, key product benefit, intended channels, "
        "budget, and other constraints."
    )
    try:
        answer = input("> ").strip()
    except EOFError as exc:
        raise ValueError("A complete creative brief is required.") from exc
    if not answer:
        raise ValueError("A complete creative brief is required.")

    creative_brief = parse_creative_brief(answer)
    current_concept = generate_initial_concept(creative_brief)
    evaluation_result = evaluate_creative_concept(creative_brief, current_concept)
    refinement_count = 0

    while evaluation_result["overall_score"] < 8.0 and refinement_count < 2:
        current_concept = refine_creative_concept(
            creative_brief, current_concept, evaluation_result
        )
        refinement_count += 1
        evaluation_result = evaluate_creative_concept(creative_brief, current_concept)

    final_result = {
        "creative_concept": current_concept,
        "evaluation": evaluation_result,
        "refinement_count": refinement_count,
        "quality_threshold_met": evaluation_result["overall_score"] >= 8.0,
    }
    _present(final_result)
    return final_result


if __name__ == "__main__":
    main()
