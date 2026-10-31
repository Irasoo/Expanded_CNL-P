"""Terminal creative-director agent.

The agent deliberately keeps the workflow in this module so it can be run as
``python main.py`` or imported and invoked through ``main()``.
"""

from __future__ import annotations

import json
import os
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


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries without overwriting process variables."""
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


def _runtime_config() -> tuple[str, str, str]:
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
    return api_key, base_url, model


def _client() -> tuple[OpenAI, str]:
    api_key, base_url, model = _runtime_config()
    return OpenAI(api_key=api_key, base_url=base_url), model


def _extract_first_json_object(text: str) -> str:
    """Extract the first balanced JSON object while respecting quoted text."""
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
    """Repair trailing commas outside strings in otherwise JSON-like output."""
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
            if next_index >= len(text) or text[next_index] not in "}]":
                characters.append(character)
        else:
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


def _ask_model(prompt: str) -> str:
    client, model = _client()
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    output_text = getattr(response, "output_text", "")
    if not isinstance(output_text, str) or not output_text.strip():
        raise ValueError("The language model returned an empty response.")
    return output_text.strip()


def parse_creative_brief(user_input: str) -> dict[str, str]:
    if not isinstance(user_input, str) or not user_input.strip():
        raise ValueError("The creative brief input must not be empty.")

    prompt = f"""
You extract a complete CreativeBrief from one user's natural-language answer.
Return one valid JSON object only, with exactly these text fields:
{json.dumps(REQUIRED_BRIEF_FIELDS)}

Interpret the answer semantically. Preserve the user's meaning and wording
where useful. Do not invent facts. If a required field is absent, return an
empty string for that field. The fields channels, budget, and constraints are
still required; represent a stated absence or no restriction explicitly in
their text value, but do not infer it when the user did not say so.

USER ANSWER:
{user_input}
"""
    result = _parse_json_object(_ask_model(prompt), "CreativeBrief extraction")
    brief: dict[str, str] = {}
    for field in REQUIRED_BRIEF_FIELDS:
        value = result.get(field)
        if not isinstance(value, str):
            raise ValueError(f"CreativeBrief field {field} must be text.")
        brief[field] = value.strip()

    missing = [field for field, value in brief.items() if not value]
    if missing:
        raise ValueError(
            "The single creative brief answer did not provide required fields: "
            + ", ".join(missing)
        )
    return brief


def generate_creative_concept(creative_brief: dict[str, str]) -> str:
    prompt = f"""
You are CreativeConceptDeveloper. Generate a complete and specific marketing
creative concept from the supplied brief.

Clearly describe the core idea, principal execution, brand or product role,
and how the idea serves the target audience and marketing objective. Ground
every claim and execution detail in the brief. Do not invent brand facts,
product capabilities, budgets, resources, objectives, audiences, partnerships,
technologies, or research findings. Respect the channels, budget, and all
constraints. Return one complete concept, not alternatives, scores, or JSON.

CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}
"""
    concept = _ask_model(prompt).strip()
    if not concept:
        raise ValueError("Initial creative concept was empty.")
    return concept


def evaluate_creative_concept(
    creative_brief: dict[str, str], creative_concept: str
) -> dict[str, Any]:
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
- Give refinement directions that address weak criteria while preserving
  useful strengths.

Return one valid JSON object only. Do not add Markdown fences or extra text.
Use integer scores from 1 to 10. Do not calculate the weighted overall score;
Python will calculate it deterministically.

Return exactly:
{{
  "originality_score": 1,
  "strategic_fit_score": 1,
  "audience_impact_score": 1,
  "executability_score": 1,
  "evaluation_reasons": "Explain the major reasons for the four scores.",
  "refinement_suggestions": "Give concrete directions for improving the weakest aspects while preserving strengths."
}}
"""
    prompt = f"""
{scoring_rubric}

CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}

CURRENT CREATIVE CONCEPT:
{creative_concept}

Evaluate the concept strictly according to the rubric.
"""
    result = _parse_json_object(_ask_model(prompt), "evaluate_creative_concept")
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
            raise ValueError(f"{field} must be numeric.")
        try:
            score = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be numeric.") from exc
        if not score.is_integer() or score < 1 or score > 10:
            raise ValueError(f"{field} must be an integer from 1 to 10.")
        scores[field] = int(score)

    reasons = str(result.get("evaluation_reasons", "")).strip()
    suggestions = str(result.get("refinement_suggestions", "")).strip()
    if not reasons:
        raise ValueError("Evaluation result must contain evaluation_reasons.")
    if not suggestions:
        raise ValueError(
            "Evaluation result must contain refinement_suggestions."
        )

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
    creative_brief: dict[str, str], current_concept: str, evaluation: dict[str, Any]
) -> str:
    if not isinstance(creative_brief, dict):
        raise ValueError("creative_brief must be a dictionary.")
    if not isinstance(current_concept, str) or not current_concept.strip():
        raise ValueError("current_concept must be a non-empty string.")
    if not isinstance(evaluation, dict):
        raise ValueError("evaluation must be a dictionary.")
    weak_criteria = evaluation.get("weak_criteria", [])
    if not isinstance(weak_criteria, list) or not all(
        isinstance(item, str) for item in weak_criteria
    ):
        raise ValueError("evaluation.weak_criteria must be a list of text.")

    methodology = """
You are revising an existing advertising or marketing creative concept.
Improve the weakest criteria in the current evaluation while preserving useful
strengths and remaining faithful to the original brief. Do not replace the
concept with an unrelated idea unless its central mechanism is the diagnosed
problem.

Focused strategies:
- Originality: replace generic conventions with a distinctive product-, brand-,
  audience-, or context-specific mechanism.
- Strategic Fit: strengthen the connection to the audience, objective, benefit,
  channels, budget, and explicit constraints.
- Audience Impact: sharpen the opening hook, emotional or behavioral payoff,
  clarity, and memorability.
- Executability: simplify unnecessary elements, fit the budget and channels,
  and make the execution practical and repeatable.

Rules:
- Preserve strong parts of the current concept.
- Do not invent capabilities, budgets, partners, celebrities, technologies,
  research, or market facts absent from the brief.
- Do not solve a weakness merely by adding more messages or mechanics.
- Keep the product or brand meaningful to the central idea.
- Return one complete revised concept, not alternatives.
- Return ONLY the revised concept: no scores, JSON, or process explanation.

The revised concept must clearly describe the core idea, main execution,
product or brand role, and connection to the audience and objective.
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

Revise the current concept according to the methodology above. Keep it
recognizably derived from the current concept unless its central mechanism is
the primary diagnosed problem.
"""
    revised = _ask_model(prompt).strip()
    if not revised:
        raise ValueError("refine_creative_concept returned an empty concept.")
    return revised


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


def main() -> dict[str, Any]:
    """Run CreativeConceptDeveloper and return the final structured result."""
    print(
        "Provide one complete creative brief containing the brand, product, "
        "target audience, marketing objective, key product benefit, channels, "
        "budget, and other constraints."
    )
    user_input = input("> ")
    creative_brief = parse_creative_brief(user_input)
    current_concept = generate_creative_concept(creative_brief)
    evaluation_result = evaluate_creative_concept(
        creative_brief, current_concept
    )
    refinement_count = 0

    while evaluation_result["overall_score"] < 8.0 and refinement_count < 2:
        current_concept = refine_creative_concept(
            creative_brief, current_concept, evaluation_result
        )
        refinement_count += 1
        evaluation_result = evaluate_creative_concept(
            creative_brief, current_concept
        )

    final_result = {
        "creative_concept": current_concept,
        "evaluation": evaluation_result,
        "refinement_count": refinement_count,
        "quality_threshold_met": evaluation_result["overall_score"] >= 8.0,
    }
    _present_result(final_result)
    return final_result


if __name__ == "__main__":
    main()
