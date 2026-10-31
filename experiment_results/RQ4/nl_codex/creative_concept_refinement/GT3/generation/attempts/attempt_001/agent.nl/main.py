"""CreativeDirectorAssistant: terminal workflow for developing marketing concepts."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI


QUALITY_THRESHOLD = 8.0
MAX_REFINEMENTS = 2
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


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries without overriding the process environment."""
    env_path = Path(".env")
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
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key] = value


def _runtime_config() -> tuple[OpenAI, str]:
    _load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    base_url = os.environ.get("BASE_URL", "").strip()
    model = (
        os.environ.get("CNLP_REFERENCE_LLM_MODEL", "").strip()
        or os.environ.get("OPENAI_MODEL", "").strip()
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

    return OpenAI(api_key=api_key, base_url=base_url), model


def _model_text(client: OpenAI, model: str, prompt: str) -> str:
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    text = response.output_text.strip()
    if not text:
        raise ValueError("The language model returned an empty response.")
    return text


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
    """Repair commas before closing JSON delimiters, excluding quoted content."""
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


def _parse_json_object(text: str, operation: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].strip().startswith("```"):
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


def _parse_creative_brief(client: OpenAI, model: str, user_answer: str) -> dict[str, str]:
    prompt = f"""
You are structuring a user's complete creative brief for a marketing concept.
Extract exactly these eight required fields as a JSON object:
brand, product, target_audience, objective, key_product_benefit, channels,
budget, constraints. Every value must be a string. Preserve the user's meaning
and wording where practical. Do not invent brand facts, capabilities, budgets,
resources, objectives, audiences, partnerships, technologies, or research.
If a field is not supplied, return an empty string for that field. Do not ask a
follow-up question and do not infer a fact merely because it is common in the
category.

Return only valid JSON with exactly those field names.

USER'S SINGLE CREATIVE BRIEF ANSWER:
{user_answer}
"""
    result = _parse_json_object(
        _model_text(client, model, prompt), "creative brief extraction"
    )
    brief: dict[str, str] = {}
    for field in REQUIRED_BRIEF_FIELDS:
        value = result.get(field, "")
        if not isinstance(value, str):
            raise ValueError(f"Creative brief field {field} must be text.")
        brief[field] = value.strip()

    missing = [field for field, value in brief.items() if not value]
    if missing:
        raise ValueError(
            "The creative brief is incomplete; missing required fields: "
            + ", ".join(missing)
        )
    return brief


def _generate_initial_concept(client: OpenAI, model: str, creative_brief: dict[str, str]) -> str:
    prompt = f"""
You are CreativeConceptDeveloper, a senior creative director developing one
marketing creative concept from a supplied brief.

Create one complete and specific concept. Clearly describe the core idea, the
principal execution, the role of the brand or product, and how the idea serves
the target audience and marketing objective. Ground every claim and execution
detail in the brief. Do not invent brand facts, product capabilities, budgets,
resources, partnerships, technologies, research findings, or audience facts.
Respect the listed channels, budget, and constraints. Return only the concept,
with no JSON, scores, alternatives, or commentary about this instruction.

CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}
"""
    concept = _model_text(client, model, prompt)
    if not concept:
        raise ValueError("Initial concept generation returned an empty concept.")
    return concept


def evaluate_creative_concept(
    creative_brief: dict[str, str],
    creative_concept: str,
    *,
    client: OpenAI | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Evaluate a concept using the fixed four-criterion scoring framework."""
    if client is None or model is None:
        client, model = _runtime_config()
    if not isinstance(creative_brief, dict):
        raise ValueError("creative_brief must be a dictionary.")
    if not isinstance(creative_concept, str) or not creative_concept.strip():
        raise ValueError("creative_concept must be a non-empty string.")

    scoring_rubric = """
You are evaluating an advertising or marketing creative concept.

Use the four criteria below. Score each criterion from 1 to 10. Be
constructive and realistic: a strong, clearly branded, relevant, and workable
concept may receive an 8. Scores of 9-10 are reserved for unusually strong
work, but the concept does not need to be an international award winner to
reach the workflow threshold.

1. ORIGINALITY — weight 0.30
1-3: Generic category advertising or a familiar idea with little distinction.
4-5: A recognizable approach with a modest twist.
6-7: Clearly differentiated and meaningfully connected to the product or brand.
8: A strong, memorable, product-specific idea.
9-10: An exceptionally distinctive idea with rare creative strength.

2. STRATEGIC FIT — weight 0.30
1-3: Misses the audience, objective, product benefit, or explicit constraints.
4-5: Generally relevant but only partly answers the brief.
6-7: Clearly addresses the audience, objective, and product benefit.
8: Solves the brief strongly and gives the product a central role.
9-10: Finds an unusually powerful and precise way to solve the brief.

3. AUDIENCE IMPACT — weight 0.20
1-3: Confusing, emotionally flat, or easy to ignore.
4-5: Understandable but only mildly interesting.
6-7: Clear, engaging, and likely to earn attention from the target audience.
8: Immediately understandable with a memorable emotional or behavioral hook.
9-10: Exceptionally compelling and likely to inspire sustained response.

4. EXECUTABILITY — weight 0.20
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

Return one valid JSON object only. Do not add Markdown fences, explanations,
or text before or after the object. Use strict JSON syntax.

Return exactly:
{
  "originality_score": 1,
  "strategic_fit_score": 1,
  "audience_impact_score": 1,
  "executability_score": 1,
  "evaluation_reasons": "Explain the major reasons for the four scores.",
  "refinement_suggestions": "Give concrete directions for improving the weakest aspects while preserving strengths."
}
"""
    prompt = f"""
{scoring_rubric}

CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}

CURRENT CREATIVE CONCEPT:
{creative_concept}

Evaluate the concept strictly according to the rubric.
"""
    result = _parse_json_object(
        _model_text(client, model, prompt), "creative concept evaluation"
    )

    score_names = (
        "originality_score",
        "strategic_fit_score",
        "audience_impact_score",
        "executability_score",
    )
    normalized_scores: dict[str, float] = {}
    for key in score_names:
        if key not in result:
            raise ValueError(f"Missing score in evaluation result: {key}")
        try:
            score = float(result[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be numeric.") from exc
        if score < 1 or score > 10:
            raise ValueError(f"{key} must be between 1 and 10, received {score}.")
        normalized_scores[key] = score

    evaluation_reasons = str(result.get("evaluation_reasons", "")).strip()
    refinement_suggestions = str(result.get("refinement_suggestions", "")).strip()
    if not evaluation_reasons:
        raise ValueError("Evaluation result must contain evaluation_reasons.")
    if not refinement_suggestions:
        raise ValueError("Evaluation result must contain refinement_suggestions.")

    criteria = {
        "originality": normalized_scores["originality_score"],
        "strategic_fit": normalized_scores["strategic_fit_score"],
        "audience_impact": normalized_scores["audience_impact_score"],
        "executability": normalized_scores["executability_score"],
    }
    minimum_score = min(criteria.values())
    weak_criteria = [
        criterion for criterion, score in criteria.items() if score == minimum_score
    ]
    overall_score = (
        normalized_scores["originality_score"] * 0.30
        + normalized_scores["strategic_fit_score"] * 0.30
        + normalized_scores["audience_impact_score"] * 0.20
        + normalized_scores["executability_score"] * 0.20
    )
    return {
        "originality_score": normalized_scores["originality_score"],
        "strategic_fit_score": normalized_scores["strategic_fit_score"],
        "audience_impact_score": normalized_scores["audience_impact_score"],
        "executability_score": normalized_scores["executability_score"],
        "overall_score": round(overall_score, 2),
        "weak_criteria": weak_criteria,
        "evaluation_reasons": evaluation_reasons,
        "refinement_suggestions": refinement_suggestions,
    }


def refine_creative_concept(
    creative_brief: dict[str, str],
    current_concept: str,
    evaluation: dict[str, Any],
    *,
    client: OpenAI | None = None,
    model: str | None = None,
) -> str:
    if client is None or model is None:
        client, model = _runtime_config()
    if not isinstance(creative_brief, dict):
        raise ValueError("creative_brief must be a dictionary.")
    if not isinstance(current_concept, str) or not current_concept.strip():
        raise ValueError("current_concept must be a non-empty string.")
    if not isinstance(evaluation, dict):
        raise ValueError("evaluation must be a dictionary.")
    weak_criteria = evaluation.get("weak_criteria", [])
    if not isinstance(weak_criteria, list):
        raise ValueError("evaluation.weak_criteria must be a list.")

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

The revised concept must clearly describe the core idea, main execution,
product or brand role, and connection to the target audience and objective.
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
{json.dumps(weak_criteria, ensure_ascii=False)}

Revise the current concept according to the methodology above.
The revised concept must remain recognizably derived from the current concept
unless the current central mechanism itself is the primary diagnosed problem.
"""
    revised_concept = _model_text(client, model, prompt)
    if not revised_concept:
        raise ValueError("Refinement returned an empty creative concept.")
    return revised_concept


def _present_result(final_result: dict[str, Any]) -> None:
    print("\n=== Final Creative Concept ===")
    print(final_result["creative_concept"])
    print("\n=== Evaluation ===")
    print(json.dumps(final_result["evaluation"], ensure_ascii=False, indent=2))
    print("\n=== Refinements ===")
    print(final_result["refinement_count"])
    print("\n=== Quality Threshold ===")
    if final_result["quality_threshold_met"]:
        print("Met (weighted overall score is at least 8.0).")
    else:
        print("Not met; the two-refinement limit was reached.")


def main() -> dict[str, Any] | None:
    """Run the complete one-brief creative development workflow."""
    try:
        client, model = _runtime_config()
        print(
            "CreativeDirectorAssistant: provide one complete creative brief "
            "including brand, product, target audience, objective, key product "
            "benefit, channels, budget, and constraints."
        )
        user_answer = sys.stdin.readline()
        if not user_answer:
            raise ValueError("No creative brief was provided.")
        creative_brief = _parse_creative_brief(client, model, user_answer.strip())
        current_concept = _generate_initial_concept(client, model, creative_brief)
        evaluation_result = evaluate_creative_concept(
            creative_brief, current_concept, client=client, model=model
        )
        refinement_count = 0

        while (
            evaluation_result["overall_score"] < QUALITY_THRESHOLD
            and refinement_count < MAX_REFINEMENTS
        ):
            current_concept = refine_creative_concept(
                creative_brief,
                current_concept,
                evaluation_result,
                client=client,
                model=model,
            )
            refinement_count += 1
            evaluation_result = evaluate_creative_concept(
                creative_brief, current_concept, client=client, model=model
            )

        final_result = {
            "creative_concept": current_concept,
            "evaluation": evaluation_result,
            "refinement_count": refinement_count,
            "quality_threshold_met": evaluation_result["overall_score"]
            >= QUALITY_THRESHOLD,
        }
        _present_result(final_result)
        return final_result
    except Exception as exc:
        print(f"CreativeDirectorAssistant error: {exc}", file=sys.stderr)
        return None


if __name__ == "__main__":
    main()
