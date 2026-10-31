from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI


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
    """Load simple KEY=VALUE entries without overwriting process variables."""
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
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _runtime_config() -> tuple[OpenAI, str]:
    _load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("BASE_URL")
    model = os.environ.get("CNLP_REFERENCE_LLM_MODEL") or os.environ.get(
        "OPENAI_MODEL"
    )
    missing = [
        name
        for name, value in (
            ("OPENAI_API_KEY", api_key),
            ("BASE_URL", base_url),
            ("CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL", model),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing runtime model configuration: " + ", ".join(missing)
        )

    return OpenAI(api_key=api_key, base_url=base_url), model


def _call_model(prompt: str) -> str:
    client, model = _runtime_config()
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    output = getattr(response, "output_text", "")
    if not isinstance(output, str) or not output.strip():
        raise ValueError("The language model returned an empty response.")
    return output.strip()


def _extract_first_json_object(text: str) -> str:
    """Return the first balanced JSON object while respecting quoted strings."""
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
    """Repair commas before closing JSON delimiters outside quoted strings."""
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
        elif character == ",":
            next_index = index + 1
            while next_index < len(text) and text[next_index].isspace():
                next_index += 1
            if next_index < len(text) and text[next_index] in "}]":
                index += 1
                continue

        characters.append(character)
        index += 1
    return "".join(characters)


def _parse_json_object(output_text: str, operation: str) -> dict[str, Any]:
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


def _validate_brief(brief: Any) -> dict[str, str]:
    if not isinstance(brief, dict):
        raise ValueError("creative_brief must be a structured object.")
    normalized: dict[str, str] = {}
    for field in BRIEF_FIELDS:
        value = brief.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"creative_brief.{field} must be non-empty text.")
        normalized[field] = value.strip()
    return normalized


def parse_creative_brief(user_input: str) -> dict[str, str]:
    if not isinstance(user_input, str) or not user_input.strip():
        raise ValueError("A complete creative brief is required.")

    # Structured input is accepted directly; free-form input is semantically parsed.
    try:
        candidate = json.loads(user_input)
    except json.JSONDecodeError:
        candidate = None
    if isinstance(candidate, dict):
        return _validate_brief(candidate)

    prompt = f"""
You are the intake component of a creative director assistant.

Extract one complete creative brief from the user's single response below.
Understand natural language; do not guess or invent missing facts. Every field
must preserve the user's meaning. If a requested field is absent or genuinely
unclear, return an empty string for that field so the application can report it.

Return exactly one strict JSON object with these string fields:
{json.dumps(BRIEF_FIELDS)}

USER RESPONSE:
{user_input}
"""
    brief = _parse_json_object(_call_model(prompt), "creative brief extraction")
    return _validate_brief(brief)


def generate_creative_concept(creative_brief: dict[str, str]) -> str:
    brief = _validate_brief(creative_brief)
    prompt = f"""
You are a creative director assistant responsible for generating a marketing
creative concept. The persona, audience, concepts, and constraints below are
binding.

PERSONA
- Generate a strategically useful concept grounded in the user's brief.
- Do not invent brand facts, product capabilities, budgets, resources,
  objectives, audiences, partnerships, technologies, or research findings.

AUDIENCE
- The user is a brand, marketing, or creative professional.
- Provide enough operational detail for a professional to evaluate the idea.

CONCEPT DEFINITIONS
- A creative concept is the central marketing idea and its principal execution
  for this brand, product, audience, and objective.
- The product or brand must have a meaningful role in the central mechanism.

CONSTRAINTS
- Ground every claim and execution detail in the brief.
- Respect the channels, budget, and explicit constraints exactly as stated.
- Describe one complete, specific concept, not a list of alternatives.

The concept must clearly describe: the core idea, principal execution, brand or
product role, target-audience connection, and objective connection.

CREATIVE BRIEF:
{json.dumps(brief, ensure_ascii=False, indent=2)}
"""
    concept = _call_model(prompt).strip()
    if not concept:
        raise ValueError("Initial concept generation returned an empty concept.")
    return concept


def evaluate_creative_concept(
    creative_brief: dict[str, str], creative_concept: str
) -> dict[str, Any]:
    import math

    brief = _validate_brief(creative_brief)
    if not isinstance(creative_concept, str) or not creative_concept.strip():
        raise ValueError("creative_concept must be a non-empty string.")

    scoring_rubric = """
You are evaluating an advertising or marketing creative concept.

Use the four criteria below. Score each criterion from 1 to 10. Be constructive
and realistic: a strong, clearly branded, relevant, and workable concept may
receive an 8. Scores of 9-10 are reserved for unusually strong work.

1. ORIGINALITY, weight 0.30: 1-3 generic; 4-5 familiar with a modest twist;
6-7 clearly differentiated and product-connected; 8 strong and memorable;
9-10 exceptionally distinctive.
2. STRATEGIC FIT, weight 0.30: judge audience, objective, product benefit,
channels, budget, and explicit constraints. 8 solves the brief strongly and
gives the product a central role; 9-10 is unusually precise.
3. AUDIENCE IMPACT, weight 0.20: judge clarity, attention, emotional or
behavioral hook, memorability, and likely response from the stated audience.
4. EXECUTABILITY, weight 0.20: judge practicality for the stated budget,
channels, resources, and constraints; reward simple, reusable execution.

Apply these rules:
- Ground every judgment in the supplied brief and current concept.
- Do not invent budgets, capabilities, partnerships, research, or resources.
- Use the full scale and explain the most important strengths and weaknesses.
- Give refinement directions that address weak criteria while preserving useful
  strengths.

Return one valid JSON object only, with integer scores and exactly these fields:
{
  "originality_score": 1,
  "strategic_fit_score": 1,
  "audience_impact_score": 1,
  "executability_score": 1,
  "evaluation_reasons": "Explain the major reasons for the four scores.",
  "refinement_suggestions": "Give concrete directions for improving the weakest aspects while preserving strengths."
}
Do not calculate the weighted overall score.
"""
    prompt = f"""
{scoring_rubric}

CREATIVE BRIEF:
{json.dumps(brief, ensure_ascii=False, indent=2)}

CURRENT CREATIVE CONCEPT:
{creative_concept}

Evaluate the concept strictly according to the rubric.
"""
    result = _parse_json_object(_call_model(prompt), "evaluate_creative_concept")
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
        value = result[field]
        if isinstance(value, bool):
            raise ValueError(f"{field} must be an integer from 1 to 10.")
        try:
            score = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be numeric.") from exc
        if not math.isfinite(score) or score < 1 or score > 10 or not score.is_integer():
            raise ValueError(f"{field} must be an integer from 1 to 10.")
        scores[field] = int(score)

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
    overall_score = round(
        scores["originality_score"] * 0.30
        + scores["strategic_fit_score"] * 0.30
        + scores["audience_impact_score"] * 0.20
        + scores["executability_score"] * 0.20,
        2,
    )
    minimum_score = min(criteria.values())
    weak_criteria = [
        criterion for criterion, score in criteria.items() if score == minimum_score
    ]
    return {
        "originality_score": scores["originality_score"],
        "strategic_fit_score": scores["strategic_fit_score"],
        "audience_impact_score": scores["audience_impact_score"],
        "executability_score": scores["executability_score"],
        "overall_score": overall_score,
        "weak_criteria": weak_criteria,
        "evaluation_reasons": reasons,
        "refinement_suggestions": suggestions,
    }


def refine_creative_concept(
    creative_brief: dict[str, str], current_concept: str, evaluation: dict[str, Any]
) -> str:
    brief = _validate_brief(creative_brief)
    if not isinstance(current_concept, str) or not current_concept.strip():
        raise ValueError("current_concept must be a non-empty string.")
    if not isinstance(evaluation, dict):
        raise ValueError("evaluation must be a dictionary.")
    weak_criteria = evaluation.get("weak_criteria", [])
    if not isinstance(weak_criteria, list) or not all(
        isinstance(item, str) for item in weak_criteria
    ):
        raise ValueError("evaluation.weak_criteria must be a list of text values.")

    refinement_methodology = """
You are revising an existing advertising or marketing creative concept.

Use the current evaluation diagnostically. Improve the weakest criteria while
preserving useful strengths and remaining faithful to the original brief. Do
not replace the concept with an unrelated idea unless its central mechanism is
the diagnosed problem.

Focused strategies:
- Originality: replace generic category conventions with a distinctive
  product-, brand-, audience-, or context-specific mechanism.
- Strategic Fit: strengthen the connection to audience, objective, benefit,
  channels, budget, and explicit constraints.
- Audience Impact: sharpen the opening hook, emotional or behavioral payoff,
  clarity, and memorability.
- Executability: simplify unnecessary elements, fit the stated budget and
  channels, and make execution practical and repeatable.

Rules:
- Preserve strong parts of the current concept.
- Do not invent product capabilities, budgets, partners, celebrities,
  technologies, research, or market facts absent from the brief.
- Do not solve a weakness merely by adding more messages or mechanics.
- Keep the product or brand meaningful to the central idea.
- Return one complete revised concept, not alternatives or commentary.

The revised concept must clearly describe the core idea, main execution,
product or brand role, and connection to the audience and objective.
"""
    prompt = f"""
{refinement_methodology}

ORIGINAL CREATIVE BRIEF:
{json.dumps(brief, ensure_ascii=False, indent=2)}

CURRENT CREATIVE CONCEPT:
{current_concept}

CURRENT EVALUATION:
{json.dumps(evaluation, ensure_ascii=False, indent=2)}

PRIMARY WEAK CRITERIA:
{json.dumps(weak_criteria, ensure_ascii=False)}

Revise the current concept according to the methodology above. Keep it
recognizably derived from the current concept unless the diagnosed central
mechanism itself is the problem.
"""
    revised = _call_model(prompt).strip()
    if not revised:
        raise ValueError("refine_creative_concept returned an empty concept.")
    return revised


def _construct_result(
    current_concept: str, evaluation: dict[str, Any], refinement_count: int
) -> dict[str, Any]:
    met = evaluation["overall_score"] >= 8.0
    return {
        "creative_concept": current_concept,
        "evaluation": evaluation,
        "refinement_count": refinement_count,
        "quality_threshold_met": met,
    }


def _display_result(final_result: dict[str, Any]) -> None:
    evaluation = final_result["evaluation"]
    print("\n=== Final Creative Concept ===")
    print(final_result["creative_concept"])
    print("\n=== Evaluation ===")
    print(f"Originality: {evaluation['originality_score']}/10")
    print(f"Strategic fit: {evaluation['strategic_fit_score']}/10")
    print(f"Audience impact: {evaluation['audience_impact_score']}/10")
    print(f"Executability: {evaluation['executability_score']}/10")
    print(f"Weighted overall score: {evaluation['overall_score']:.2f}/10")
    print(f"Weak criteria: {', '.join(evaluation['weak_criteria']) or 'None'}")
    print(f"Reasons: {evaluation['evaluation_reasons']}")
    print(f"Refinement suggestions: {evaluation['refinement_suggestions']}")
    print("\n=== Workflow Status ===")
    print(f"Refinements performed: {final_result['refinement_count']}")
    print(
        "Quality threshold met: "
        + ("Yes" if final_result["quality_threshold_met"] else "No")
    )


def run_agent() -> dict[str, Any]:
    print(
        "Provide one complete creative brief containing the brand, product, "
        "target audience, objective, key product benefit, channels, budget, "
        "and constraints. You may enter JSON or natural language."
    )
    user_input = sys.stdin.readline()
    if user_input == "":
        raise ValueError("No creative brief was provided.")

    # Main Flow: INPUT, initial COMMAND, API evaluation, bounded refinement loop.
    creative_brief = parse_creative_brief(user_input)
    current_concept = generate_creative_concept(creative_brief)
    evaluation_result = evaluate_creative_concept(creative_brief, current_concept)
    refinement_count = 0

    while evaluation_result["overall_score"] < 8.0 and refinement_count < 2:
        current_concept = refine_creative_concept(
            creative_brief, current_concept, evaluation_result
        )
        refinement_count += 1
        evaluation_result = evaluate_creative_concept(creative_brief, current_concept)

    final_result = _construct_result(
        current_concept, evaluation_result, refinement_count
    )
    _display_result(final_result)
    return final_result


def main() -> dict[str, Any] | None:
    try:
        return run_agent()
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"Agent error: {exc}", file=sys.stderr)
        return None


if __name__ == "__main__":
    main()
