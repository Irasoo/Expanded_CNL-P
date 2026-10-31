from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI


REQUIRED_BRIEF_FIELDS = [
    "brand",
    "product",
    "target_audience",
    "objective",
    "key_product_benefit",
    "channels",
    "budget",
    "constraints",
]


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries without overriding process variables."""
    dotenv_path = Path.cwd() / ".env"
    if not dotenv_path.is_file():
        return

    try:
        lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key] = value


def _configuration() -> tuple[OpenAI, str]:
    _load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("BASE_URL")
    model = os.getenv("CNLP_REFERENCE_LLM_MODEL") or os.getenv("OPENAI_MODEL")

    missing = []
    if not api_key:
        missing.append("OPENAI_API_KEY")
    if not base_url:
        missing.append("BASE_URL")
    if not model:
        missing.append("CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL")
    if missing:
        raise RuntimeError(
            "Missing runtime language-model configuration: " + ", ".join(missing)
        )

    return OpenAI(api_key=api_key, base_url=base_url), model


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
    """Repair commas before JSON closing tokens without changing string content."""
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


def _parse_creative_brief(client: OpenAI, model: str, user_input: str) -> dict[str, str]:
    prompt = f"""
Interpret the user's single creative-brief response into the required schema.
Extract only information supplied by the user. Do not invent, infer, or fill in
missing facts. Every field must be text; for channels, preserve the user's
description as text. If a field is absent, use an empty string.

Return one valid JSON object only, with exactly these fields:
{json.dumps(REQUIRED_BRIEF_FIELDS, ensure_ascii=False)}

USER'S CREATIVE BRIEF:
{user_input}
"""
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    result = _parse_json_response(response.output_text, "creative brief parsing")
    brief = {field: str(result.get(field, "")).strip() for field in REQUIRED_BRIEF_FIELDS}
    if any(not value for value in brief.values()):
        missing = [field for field, value in brief.items() if not value]
        raise ValueError(
            "The creative brief is missing required field(s): " + ", ".join(missing)
        )
    return brief


def _generate_initial_concept(
    client: OpenAI, model: str, creative_brief: dict[str, str]
) -> str:
    prompt = f"""
You are CreativeConceptDeveloper, a creative director assistant.

Generate one complete and specific marketing creative concept from the supplied
creative brief. Clearly describe the core idea, principal execution, brand or
product role, and how the idea serves the target audience and marketing
objective. Ground every claim and execution detail in the brief. Do not invent
brand facts, product capabilities, budgets, resources, objectives, audiences,
partnerships, technologies, or research findings. Respect the channels, budget,
and constraints. Return only the concept, with no preface or alternatives.

CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}
"""
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    concept = response.output_text.strip()
    if not concept:
        raise ValueError("Initial concept generation returned an empty concept.")
    return concept


SCORING_RUBRIC = """
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
- Give refinement directions that address weak criteria while preserving
  useful strengths.

Return one valid JSON object only. Do not add Markdown fences or other text.
Use strict JSON syntax and integer scores from 1 to 10. Do not calculate the
weighted overall score; Python will calculate it deterministically.

Return exactly these fields:
{
  "originality_score": 1,
  "strategic_fit_score": 1,
  "audience_impact_score": 1,
  "executability_score": 1,
  "evaluation_reasons": "Explain the major reasons for the four scores.",
  "refinement_suggestions": "Give concrete directions for improving the weakest aspects while preserving strengths."
}
"""


def evaluate_creative_concept(
    client: OpenAI,
    model: str,
    creative_brief: dict[str, str],
    creative_concept: str,
) -> dict[str, Any]:
    if not isinstance(creative_brief, dict):
        raise ValueError("creative_brief must be a dictionary.")
    if not isinstance(creative_concept, str) or not creative_concept.strip():
        raise ValueError("creative_concept must be a non-empty string.")

    prompt = f"""
{SCORING_RUBRIC}

CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}

CURRENT CREATIVE CONCEPT:
{creative_concept}

Evaluate the concept strictly according to the rubric.
"""
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    result = _parse_json_response(response.output_text, "creative evaluation")

    score_fields = [
        "originality_score",
        "strategic_fit_score",
        "audience_impact_score",
        "executability_score",
    ]
    scores: dict[str, float] = {}
    for field in score_fields:
        if field not in result:
            raise ValueError(f"Missing score in evaluation result: {field}")
        try:
            score = float(result[field])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be numeric.") from exc
        if score < 1 or score > 10 or not score.is_integer():
            raise ValueError(f"{field} must be an integer between 1 and 10.")
        scores[field] = score

    evaluation_reasons = str(result.get("evaluation_reasons", "")).strip()
    refinement_suggestions = str(result.get("refinement_suggestions", "")).strip()
    if not evaluation_reasons:
        raise ValueError("Evaluation result must contain evaluation_reasons.")
    if not refinement_suggestions:
        raise ValueError("Evaluation result must contain refinement_suggestions.")

    criteria = {
        "originality": scores["originality_score"],
        "strategic_fit": scores["strategic_fit_score"],
        "audience_impact": scores["audience_impact_score"],
        "executability": scores["executability_score"],
    }
    minimum_score = min(criteria.values())
    overall_score = (
        scores["originality_score"] * 0.30
        + scores["strategic_fit_score"] * 0.30
        + scores["audience_impact_score"] * 0.20
        + scores["executability_score"] * 0.20
    )
    return {
        **scores,
        "overall_score": round(overall_score, 2),
        "weak_criteria": [
            criterion for criterion, score in criteria.items() if score == minimum_score
        ],
        "evaluation_reasons": evaluation_reasons,
        "refinement_suggestions": refinement_suggestions,
    }


def refine_creative_concept(
    client: OpenAI,
    model: str,
    creative_brief: dict[str, str],
    current_concept: str,
    evaluation: dict[str, Any],
) -> str:
    if not isinstance(creative_brief, dict):
        raise ValueError("creative_brief must be a dictionary.")
    if not isinstance(current_concept, str) or not current_concept.strip():
        raise ValueError("current_concept must be a non-empty string.")
    if not isinstance(evaluation, dict):
        raise ValueError("evaluation must be a dictionary.")
    weak_criteria = evaluation.get("weak_criteria", [])
    if not isinstance(weak_criteria, list):
        raise ValueError("evaluation.weak_criteria must be a list.")

    methodology = """
You are revising an existing advertising or marketing creative concept.

Use the current evaluation diagnostically. Improve the weakest criteria while
preserving useful strengths and remaining faithful to the original brief.
Do not replace the concept with an unrelated idea unless its central mechanism
is the diagnosed problem.

Focused strategies:
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

The revised concept must clearly describe the core idea, main execution,
product or brand role, and connection to the target audience and objective.
Return only the revised creative concept.
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
{json.dumps(weak_criteria, ensure_ascii=False)}

Revise the current concept according to the methodology. Keep it recognizably
derived from the current concept unless its central mechanism is the primary
diagnosed problem.
"""
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    revised_concept = response.output_text.strip()
    if not revised_concept:
        raise ValueError("Concept refinement returned an empty creative concept.")
    return revised_concept


def _print_result(final_result: dict[str, Any]) -> None:
    evaluation = final_result["evaluation"]
    print("\n=== Final Creative Concept ===")
    print(final_result["creative_concept"])
    print("\n=== Evaluation ===")
    print(f"Originality: {evaluation['originality_score']:.0f}/10")
    print(f"Strategic fit: {evaluation['strategic_fit_score']:.0f}/10")
    print(f"Audience impact: {evaluation['audience_impact_score']:.0f}/10")
    print(f"Executability: {evaluation['executability_score']:.0f}/10")
    print(f"Overall score: {evaluation['overall_score']:.2f}/10")
    print("Weak criteria: " + ", ".join(evaluation["weak_criteria"]))
    print("Reasons: " + evaluation["evaluation_reasons"])
    print("Refinement suggestions: " + evaluation["refinement_suggestions"])
    print(f"\n=== Refinements Performed ===\n{final_result['refinement_count']}")
    status = "Yes" if final_result["quality_threshold_met"] else "No"
    print(f"\n=== Quality Threshold Met (8.0) ===\n{status}")
    if not final_result["quality_threshold_met"]:
        print("The two-refinement limit was reached without satisfying the quality threshold.")
    print("\n=== Result JSON ===")
    print(json.dumps(final_result, ensure_ascii=False, indent=2))


def main() -> dict[str, Any]:
    """Run the one-brief creative concept development workflow."""
    try:
        client, model = _configuration()
        print(
            "Provide one complete creative brief with brand, product, target audience, "
            "objective, key product benefit, channels, budget, and constraints:"
        )
        user_input = sys.stdin.readline()
        if user_input == "":
            raise ValueError("No creative brief was provided.")
        creative_brief = _parse_creative_brief(client, model, user_input.strip())
        current_concept = _generate_initial_concept(client, model, creative_brief)
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
        _print_result(final_result)
        return final_result
    except Exception as exc:
        print(f"Agent execution failed: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
