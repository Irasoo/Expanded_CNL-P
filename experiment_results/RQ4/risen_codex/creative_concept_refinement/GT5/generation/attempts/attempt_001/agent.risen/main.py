from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI


REQUIRED_BRIEF_FIELDS = (
    "brand",
    "product",
    "target_audience",
    "objective",
    "key_product_benefit",
    "channels",
    "budget",
    "constraints",
)


def _read_dotenv_value(name: str) -> str | None:
    """Read one value from the current directory's .env when env is unset."""
    environment_value = os.environ.get(name)
    if environment_value is not None and environment_value.strip():
        return environment_value.strip()

    dotenv_path = Path.cwd() / ".env"
    if not dotenv_path.is_file():
        return None

    try:
        lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"Unable to read .env: {exc}") from exc

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        key, separator, value = stripped.partition("=")
        if separator and key.strip() == name:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value.strip() or None
    return None


def _runtime_client() -> tuple[OpenAI, str]:
    api_key = _read_dotenv_value("OPENAI_API_KEY")
    base_url = _read_dotenv_value("BASE_URL")
    model = _read_dotenv_value("CNLP_REFERENCE_LLM_MODEL")
    if model is None:
        model = _read_dotenv_value("OPENAI_MODEL")

    missing = []
    if not api_key:
        missing.append("OPENAI_API_KEY")
    if not base_url:
        missing.append("BASE_URL")
    if not model:
        missing.append("CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL")
    if missing:
        raise RuntimeError(
            "Missing runtime configuration: " + ", ".join(missing) + ". "
            "Set these values in the current directory's .env or environment."
        )

    return OpenAI(api_key=api_key, base_url=base_url), model


def _call_model(client: OpenAI, model: str, prompt: str) -> str:
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    output_text = getattr(response, "output_text", "").strip()
    if not output_text:
        raise ValueError("The language model returned an empty response.")
    return output_text


def _extract_first_json_object(text: str) -> str:
    """Extract the first balanced JSON object while respecting quoted strings."""
    start = text.find("{")
    if start < 0:
        return text

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        character = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue

        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return text[start:]


def _remove_trailing_commas(text: str) -> str:
    """Repair trailing commas outside strings without changing string content."""
    characters: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        character = text[index]
        if in_string:
            characters.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue

        if character == '"':
            in_string = True
            characters.append(character)
        elif character == ",":
            next_index = index + 1
            while next_index < len(text) and text[next_index].isspace():
                next_index += 1
            if next_index < len(text) and text[next_index] in "}]":
                index += 1
                continue
            characters.append(character)
        else:
            characters.append(character)
        index += 1
    return "".join(characters)


def _parse_json_response(output_text: str, operation: str) -> dict[str, Any]:
    cleaned = output_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    cleaned = _remove_trailing_commas(_extract_first_json_object(cleaned))
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{operation} returned invalid JSON: {cleaned}") from exc
    if not isinstance(result, dict):
        raise ValueError(f"{operation} must return a JSON object.")
    return result


def _parse_creative_brief(client: OpenAI, model: str, answer: str) -> dict[str, str]:
    prompt = f"""
You are extracting a CreativeBrief from one user's answer.

The required fields are exactly: brand, product, target_audience, objective,
key_product_benefit, channels, budget, and constraints. Return one valid JSON
object only, with exactly those fields and string values. Interpret the answer
semantically, preserving the user's meaning. Do not invent missing facts. If a
field is not supplied, use an empty string for that field so the caller can
report the incomplete brief.

USER'S SINGLE ANSWER:
{answer}
"""
    result = _parse_json_response(_call_model(client, model, prompt), "brief extraction")
    brief: dict[str, str] = {}
    for field in REQUIRED_BRIEF_FIELDS:
        value = result.get(field, "")
        if not isinstance(value, str):
            value = str(value)
        brief[field] = value.strip()

    missing = [field for field in REQUIRED_BRIEF_FIELDS if not brief[field]]
    if missing:
        raise ValueError(
            "The creative brief is incomplete; missing fields: " + ", ".join(missing)
        )
    return brief


def generate_creative_concept(
    client: OpenAI, model: str, creative_brief: dict[str, str]
) -> str:
    prompt = f"""
You are a creative director developing an advertising or marketing concept.
Generate one complete and specific marketing creative concept from the supplied
brief. Clearly describe the core idea, principal execution, the brand or
product's role, and how the idea serves the target audience and objective.
Ground every claim and execution detail in the brief. Do not invent brand
facts, product capabilities, budgets, resources, partnerships, technologies,
or research findings. Return only the concept as clear prose, not JSON and not
a list of alternatives.

CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}
"""
    concept = _call_model(client, model, prompt)
    if not concept:
        raise ValueError("Initial concept generation returned an empty concept.")
    return concept


def evaluate_creative_concept(
    client: OpenAI,
    model: str,
    creative_brief: dict[str, str],
    creative_concept: str,
) -> dict[str, Any]:
    scoring_rubric = """
You are evaluating an advertising or marketing creative concept.

Use the four criteria below. Score each criterion from 1 to 10. Be
constructive and realistic: a strong, clearly branded, relevant, and workable
concept may receive an 8. Scores of 9-10 are reserved for unusually strong
work, but the concept does not need to be an international award winner to
reach the workflow threshold.

1. ORIGINALITY - weight 0.30
1-3: Generic category advertising or a familiar idea with little distinction.
4-5: A recognizable approach with a modest twist.
6-7: Clearly differentiated and meaningfully connected to the product or brand.
8: A strong, memorable, product-specific idea.
9-10: An exceptionally distinctive idea with rare creative strength.

2. STRATEGIC FIT - weight 0.30
1-3: Misses the audience, objective, product benefit, or explicit constraints.
4-5: Generally relevant but only partly answers the brief.
6-7: Clearly addresses the audience, objective, and product benefit.
8: Solves the brief strongly and gives the product a central role.
9-10: Finds an unusually powerful and precise way to solve the brief.

3. AUDIENCE IMPACT - weight 0.20
1-3: Confusing, emotionally flat, or easy to ignore.
4-5: Understandable but only mildly interesting.
6-7: Clear, engaging, and likely to earn attention from the target audience.
8: Immediately understandable with a memorable emotional or behavioral hook.
9-10: Exceptionally compelling and likely to inspire sustained response.

4. EXECUTABILITY - weight 0.20
1-3: Conflicts with the budget, channels, resources, or constraints.
4-5: Possible but complex, risky, or insufficiently clear.
6-7: Practical, understandable, and adaptable to the requested channels.
8: Simple to execute, easy to communicate, and readily reusable.
9-10: Delivers exceptional impact with unusually efficient execution.

Apply these rules:
- Ground every judgment in the supplied brief and current concept.
- Do not invent budgets, capabilities, partnerships, research, or resources.
- Reward useful simplicity and a meaningful product or brand role.
- Reduce Strategic Fit or Executability when explicit constraints are ignored.
- Use the full scale and explain the most important strengths and weaknesses.
- Give refinement directions that address weak criteria while preserving useful
  strengths.

Return one valid JSON object only, with exactly these fields:
originality_score, strategic_fit_score, audience_impact_score,
executability_score, evaluation_reasons, refinement_suggestions.
Use integer scores from 1 to 10. Do not calculate the weighted overall score;
Python will calculate it deterministically. weak_criteria and overall_score
are calculated by Python and must not be returned.
"""
    prompt = f"""
{scoring_rubric}

CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}

CURRENT CREATIVE CONCEPT:
{creative_concept}

Evaluate the concept strictly according to the rubric.
"""
    result = _parse_json_response(
        _call_model(client, model, prompt), "creative evaluation"
    )

    score_fields = (
        "originality_score",
        "strategic_fit_score",
        "audience_impact_score",
        "executability_score",
    )
    scores: dict[str, float] = {}
    for field in score_fields:
        if field not in result:
            raise ValueError(f"Missing score in evaluation result: {field}")
        try:
            score = float(result[field])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be numeric.") from exc
        if not 1 <= score <= 10:
            raise ValueError(f"{field} must be between 1 and 10, received {score}.")
        scores[field] = score

    reasons = str(result.get("evaluation_reasons", "")).strip()
    suggestions = str(result.get("refinement_suggestions", "")).strip()
    if not reasons:
        raise ValueError("Evaluation result must contain evaluation_reasons.")
    if not suggestions:
        raise ValueError("Evaluation result must contain refinement_suggestions.")

    criteria = {
        "originality": scores["originality_score"],
        "strategic_fit": scores["strategic_fit_score"],
        "audience_impact": scores["audience_impact_score"],
        "executability": scores["executability_score"],
    }
    overall_score = (
        scores["originality_score"] * 0.30
        + scores["strategic_fit_score"] * 0.30
        + scores["audience_impact_score"] * 0.20
        + scores["executability_score"] * 0.20
    )
    minimum_score = min(criteria.values())
    weak_criteria = [
        criterion for criterion, score in criteria.items() if score == minimum_score
    ]

    return {
        **scores,
        "overall_score": round(overall_score, 2),
        "weak_criteria": weak_criteria,
        "evaluation_reasons": reasons,
        "refinement_suggestions": suggestions,
    }


def refine_creative_concept(
    client: OpenAI,
    model: str,
    creative_brief: dict[str, str],
    current_concept: str,
    evaluation: dict[str, Any],
) -> str:
    refinement_methodology = """
You are revising an existing advertising or marketing creative concept.

Use the current evaluation diagnostically. Improve the weakest criteria while
preserving useful strengths and remaining faithful to the original brief.
Do not replace the concept with an unrelated idea unless its central mechanism
is the diagnosed problem.

Use these focused strategies:
- Originality: replace generic category conventions with a more distinctive
  product-, brand-, audience-, or context-specific mechanism.
- Strategic Fit: strengthen the connection to the target audience, objective,
  product benefit, channels, and explicit constraints.
- Audience Impact: sharpen the opening hook, emotional or behavioral payoff,
  clarity, and memorability.
- Executability: simplify unnecessary elements, fit the available budget and
  channels, and make the execution practical and repeatable.

Rules:
- Preserve strong parts of the current concept.
- Do not invent product capabilities, budgets, partners, celebrities,
  technologies, research, or market facts absent from the brief.
- Do not solve a weakness merely by adding more messages or mechanics.
- Keep the product or brand meaningful to the central idea.
- Return one complete revised concept, not a list of alternatives.

Return ONLY the revised creative concept. Do not return scores, JSON,
evaluation commentary, or an explanation of the refinement process.
"""
    prompt = f"""
{refinement_methodology}

ORIGINAL CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}

CURRENT CREATIVE CONCEPT:
{current_concept}

CURRENT EVALUATION:
{json.dumps(evaluation, ensure_ascii=False, indent=2)}

PRIMARY WEAK CRITERIA:
{json.dumps(evaluation["weak_criteria"], ensure_ascii=False)}

Revise the current concept according to the methodology above. The revised
concept must clearly describe the core idea, main execution, product or brand
role, and connection to the target audience and objective. It must remain
recognizably derived from the current concept unless its central mechanism is
the primary diagnosed problem.
"""
    revised = _call_model(client, model, prompt)
    if not revised:
        raise ValueError("Concept refinement returned an empty creative concept.")
    return revised


def _print_final_result(final_result: dict[str, Any]) -> None:
    evaluation = final_result["evaluation"]
    print("\n=== FINAL CREATIVE CONCEPT ===")
    print(final_result["creative_concept"])
    print("\n=== EVALUATION ===")
    print(json.dumps(evaluation, ensure_ascii=False, indent=2))
    print("\n=== REFINEMENTS ===")
    print(final_result["refinement_count"])
    print("\n=== QUALITY THRESHOLD ===")
    if final_result["quality_threshold_met"]:
        print("met (overall score >= 8.0)")
    else:
        print("not met; the two-refinement limit was reached")
    print("\n=== RESULT JSON ===")
    print(json.dumps(final_result, ensure_ascii=False, indent=2))


def main() -> dict[str, Any] | None:
    """Run CreativeDirectorAssistant and return the final structured result."""
    try:
        client, model = _runtime_client()
        print(
            "Provide one complete creative brief containing brand, product, "
            "target audience, objective, key product benefit, channels, "
            "budget, and constraints."
        )
        answer = input("Creative brief: ").strip()
        if not answer:
            raise ValueError("A creative brief is required.")

        creative_brief = _parse_creative_brief(client, model, answer)
        current_concept = generate_creative_concept(client, model, creative_brief)
        evaluation_result = evaluate_creative_concept(
            client, model, creative_brief, current_concept
        )
        refinement_count = 0

        while evaluation_result["overall_score"] < 8.0 and refinement_count < 2:
            current_concept = refine_creative_concept(
                client,
                model,
                creative_brief,
                current_concept,
                evaluation_result,
            )
            refinement_count += 1
            evaluation_result = evaluate_creative_concept(
                client, model, creative_brief, current_concept
            )

        final_result = {
            "creative_concept": current_concept,
            "evaluation": evaluation_result,
            "refinement_count": refinement_count,
            "quality_threshold_met": evaluation_result["overall_score"] >= 8.0,
        }
        _print_final_result(final_result)
        return final_result
    except (EOFError, KeyboardInterrupt):
        print("\nExecution cancelled.", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return None


if __name__ == "__main__":
    main()
