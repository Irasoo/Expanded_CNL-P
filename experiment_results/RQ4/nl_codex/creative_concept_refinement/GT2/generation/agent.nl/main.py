"""Terminal creative concept development agent.

The agent collects one free-form creative brief, develops a concept, evaluates
it against the fixed four-criterion framework, and refines it no more than two
times when necessary.
"""

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


SCORING_RUBRIC = """
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

Return one valid JSON object only. Do not add Markdown fences, explanations,
or text before or after the object. Use strict JSON syntax: field names and
string values must use double quotes, and there must be no trailing comma
before a closing `}` or `]`.

Use integer scores from 1 to 10. Do not calculate the weighted overall score;
Python will calculate it deterministically.

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


REFINEMENT_METHODOLOGY = """
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


CONCEPT_DEVELOPMENT_PROMPT = """
You are CreativeConceptDeveloper, a senior creative director.

Generate one complete and specific marketing creative concept from the supplied
brief. Clearly describe the core idea, principal execution, brand or product
role, and how the idea serves the target audience and marketing objective.
Ground every claim and execution detail in the brief. Do not invent brand
facts, product capabilities, budgets, resources, objectives, audiences,
partnerships, technologies, or research findings. Respect all channels, budget
information, and constraints. Return only the concept prose, with no JSON,
score, alternatives, or process explanation.
"""


BRIEF_INTERPRETATION_PROMPT = """
You are interpreting a user's creative brief for a marketing concept workflow.
Extract the eight required fields below from the single user response. Preserve
the user's meaning and wording where useful; do not invent missing facts. Every
field must be a non-empty string. When the user gives multiple channels or
constraints, summarize them in the corresponding string field. When a detail
is genuinely absent, use "Not specified in the brief" rather than guessing.

Return one strict JSON object only with exactly these string fields:
brand, product, target_audience, objective, key_product_benefit, channels,
budget, constraints

USER'S CREATIVE BRIEF:
"""


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries without requiring python-dotenv."""
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
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


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
            "Missing runtime configuration: " + ", ".join(missing)
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "The official OpenAI Python Client is required. Install the "
            "'openai' package before running the agent."
        ) from exc

    return OpenAI(api_key=api_key, base_url=base_url), model


def _response_text(response: Any, operation: str) -> str:
    output_text = getattr(response, "output_text", "")
    if not isinstance(output_text, str) or not output_text.strip():
        raise ValueError(f"{operation} returned an empty response.")
    return output_text.strip()


def _extract_first_json_object(text: str) -> str:
    """Return the first balanced JSON object, preserving quoted content."""
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
    """Repair commas immediately before `}` or `]`, never inside strings."""
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


def _require_text_fields(value: Any, fields: tuple[str, ...], context: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a dictionary.")
    normalized: dict[str, str] = {}
    for field in fields:
        raw = value.get(field)
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(f"{context}.{field} must be a non-empty string.")
        normalized[field] = raw.strip()
    return normalized


def interpret_creative_brief(user_answer: str) -> dict[str, str]:
    if not isinstance(user_answer, str) or not user_answer.strip():
        raise ValueError("A non-empty creative brief is required.")

    client, model = _client_and_model()
    response = client.responses.create(
        model=model,
        input=BRIEF_INTERPRETATION_PROMPT + "\n" + user_answer.strip(),
        reasoning={"effort": "high"},
    )
    parsed = _parse_json_object(
        _response_text(response, "Creative brief interpretation"),
        "Creative brief interpretation",
    )
    return _require_text_fields(parsed, BRIEF_FIELDS, "creative_brief")


def generate_initial_concept(creative_brief: dict[str, str]) -> str:
    creative_brief = _require_text_fields(
        creative_brief, BRIEF_FIELDS, "creative_brief"
    )
    client, model = _client_and_model()
    prompt = (
        CONCEPT_DEVELOPMENT_PROMPT
        + "\n\nCREATIVE BRIEF:\n"
        + json.dumps(creative_brief, ensure_ascii=False, indent=2)
    )
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    concept = _response_text(response, "Initial concept generation")
    if not concept:
        raise ValueError("Initial concept generation returned an empty concept.")
    return concept


def evaluate_creative_concept(
    creative_brief: dict[str, str], creative_concept: str
) -> dict[str, Any]:
    import math

    creative_brief = _require_text_fields(
        creative_brief, BRIEF_FIELDS, "creative_brief"
    )
    if not isinstance(creative_concept, str) or not creative_concept.strip():
        raise ValueError("creative_concept must be a non-empty string.")

    client, model = _client_and_model()
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
    result = _parse_json_object(
        _response_text(response, "evaluate_creative_concept"),
        "evaluate_creative_concept",
    )

    score_fields = (
        "originality_score",
        "strategic_fit_score",
        "audience_impact_score",
        "executability_score",
    )
    scores: dict[str, float] = {}
    for key in score_fields:
        if key not in result:
            raise ValueError(f"Missing score in evaluation result: {key}")
        try:
            score = float(result[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be numeric.") from exc
        if not math.isfinite(score) or score < 1 or score > 10:
            raise ValueError(f"{key} must be between 1 and 10, received {score}.")
        scores[key] = score

    reasons = result.get("evaluation_reasons")
    suggestions = result.get("refinement_suggestions")
    if not isinstance(reasons, str) or not reasons.strip():
        raise ValueError("Evaluation result must contain evaluation_reasons.")
    if not isinstance(suggestions, str) or not suggestions.strip():
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
        "evaluation_reasons": reasons.strip(),
        "refinement_suggestions": suggestions.strip(),
    }


def refine_creative_concept(
    creative_brief: dict[str, str], current_concept: str, evaluation: dict[str, Any]
) -> str:
    creative_brief = _require_text_fields(
        creative_brief, BRIEF_FIELDS, "creative_brief"
    )
    if not isinstance(current_concept, str) or not current_concept.strip():
        raise ValueError("current_concept must be a non-empty string.")
    if not isinstance(evaluation, dict):
        raise ValueError("evaluation must be a dictionary.")
    weak_criteria = evaluation.get("weak_criteria", [])
    if not isinstance(weak_criteria, list) or not all(
        isinstance(item, str) and item.strip() for item in weak_criteria
    ):
        raise ValueError("evaluation.weak_criteria must be a list of text values.")

    client, model = _client_and_model()
    prompt = f"""
{REFINEMENT_METHODOLOGY}

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
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    revised_concept = _response_text(response, "refine_creative_concept")
    if not revised_concept:
        raise ValueError("refine_creative_concept returned an empty creative concept.")
    return revised_concept


class CreativeDirectorAssistant:
    """Coordinates the CreativeConceptDeveloper workflow."""

    def run(self) -> dict[str, Any]:
        print(
            "Please provide one complete creative brief containing the brand, "
            "product, target audience, objective, key product benefit, "
            "channels, budget, and constraints."
        )
        user_answer = input("> ")
        creative_brief = interpret_creative_brief(user_answer)
        current_concept = generate_initial_concept(creative_brief)
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
        if not final_result["quality_threshold_met"]:
            print(
                "The two-refinement limit was reached without satisfying the "
                "8.0 quality threshold."
            )
        self._present_result(final_result)
        return final_result

    @staticmethod
    def _present_result(final_result: dict[str, Any]) -> None:
        evaluation = final_result["evaluation"]
        print("\n=== Final Creative Concept ===")
        print(final_result["creative_concept"])
        print("\n=== Evaluation ===")
        print(json.dumps(evaluation, ensure_ascii=False, indent=2))
        print(f"\n=== Refinements ===\n{final_result['refinement_count']}")
        status = "met" if final_result["quality_threshold_met"] else "not met"
        print(f"\n=== Quality Threshold ===\n{status}")


def main() -> dict[str, Any]:
    """Initialize the agent, execute the workflow, and return its result."""
    try:
        return CreativeDirectorAssistant().run()
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"Agent error: {exc}")
        raise


if __name__ == "__main__":
    main()
