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


class AgentConfigurationError(RuntimeError):
    """Raised when the runtime model configuration is incomplete."""


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE entries without requiring an extra dependency."""
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _runtime_client() -> tuple[OpenAI, str]:
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
        raise AgentConfigurationError(
            "Missing required runtime model configuration: " + ", ".join(missing)
        )

    return OpenAI(api_key=api_key, base_url=base_url), model


def _json_from_model(text: str) -> dict[str, Any]:
    """Extract and parse the first balanced JSON object from model output."""
    output = text.strip()
    if output.startswith("```"):
        lines = output.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        output = "\n".join(lines).strip()

    start = output.find("{")
    if start >= 0:
        depth = 0
        in_string = False
        escaped = False
        end = None
        for index in range(start, len(output)):
            character = output[index]
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
                    end = index + 1
                    break
        output = output[start:end] if end is not None else output[start:]

    # Repair only commas outside quoted strings, matching the reference behavior.
    repaired: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(output):
        character = output[index]
        if in_string:
            repaired.append(character)
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
            repaired.append(character)
            index += 1
            continue
        if character == ",":
            next_index = index + 1
            while next_index < len(output) and output[next_index].isspace():
                next_index += 1
            if next_index < len(output) and output[next_index] in "}]":
                index += 1
                continue
        repaired.append(character)
        index += 1

    try:
        parsed = json.loads("".join(repaired))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model returned invalid JSON: {output}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Model JSON response must be an object.")
    return parsed


def _call(client: OpenAI, model: str, prompt: str) -> str:
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    output = response.output_text.strip()
    if not output:
        raise ValueError("The language model returned an empty response.")
    return output


def parse_creative_brief(client: OpenAI, model: str, user_answer: str) -> dict[str, str]:
    if not user_answer.strip():
        raise ValueError("The creative brief cannot be empty.")

    prompt = f"""
You are extracting a complete creative brief from one user's answer.

Extract only facts explicitly supplied by the user. Do not invent, infer, or
fill in missing facts. Return one valid JSON object only, with exactly these
string fields:
{json.dumps(REQUIRED_BRIEF_FIELDS, ensure_ascii=False)}

If a required field is absent, use an empty string. Keep the user's wording
where useful. The channels field may contain a comma-separated description,
and all fields must still be JSON strings.

USER'S SINGLE ANSWER:
{user_answer}
"""
    parsed = _json_from_model(_call(client, model, prompt))
    brief: dict[str, str] = {}
    for field in REQUIRED_BRIEF_FIELDS:
        value = parsed.get(field, "")
        if not isinstance(value, str):
            raise ValueError(f"Creative brief field {field} must be text.")
        brief[field] = value.strip()

    missing = [field for field, value in brief.items() if not value]
    if missing:
        raise ValueError(
            "The single creative brief answer is missing required fields: "
            + ", ".join(missing)
        )
    return brief


CONCEPT_METHODOLOGY = """
You are a creative director developing an advertising or marketing concept.

Create one complete, specific creative concept grounded strictly in the
creative brief. Do not invent brand facts, product capabilities, budgets,
resources, objectives, audiences, partnerships, technologies, or research
findings. The concept must clearly describe:
- the core idea and memorable mechanism;
- the principal execution for the requested channels;
- the role of the brand or product;
- how it serves the target audience and marketing objective;
- how it respects the budget and constraints.

Return only the concept itself, not JSON, scores, alternatives, or commentary
about this instruction.
"""


def generate_initial_concept(
    client: OpenAI, model: str, creative_brief: dict[str, str]
) -> str:
    prompt = f"""
{CONCEPT_METHODOLOGY}

CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}

Write the initial marketing creative concept now.
"""
    concept = _call(client, model, prompt)
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
    result = _json_from_model(_call(client, model, prompt))
    required_scores = (
        "originality_score",
        "strategic_fit_score",
        "audience_impact_score",
        "executability_score",
    )
    scores: dict[str, float] = {}
    for key in required_scores:
        if key not in result:
            raise ValueError(f"Missing score in evaluation result: {key}")
        try:
            score = float(result[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be numeric.") from exc
        if not 1 <= score <= 10 or not score.is_integer():
            raise ValueError(f"{key} must be an integer between 1 and 10.")
        scores[key] = int(score)

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

    reasons = str(result.get("evaluation_reasons", "")).strip()
    suggestions = str(result.get("refinement_suggestions", "")).strip()
    if not reasons:
        raise ValueError("Evaluation result must contain evaluation_reasons.")
    if not suggestions:
        raise ValueError(
            "Evaluation result must contain refinement_suggestions."
        )

    return {
        **scores,
        "overall_score": round(overall_score, 2),
        "weak_criteria": weak_criteria,
        "evaluation_reasons": reasons,
        "refinement_suggestions": suggestions,
    }


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
    revised = _call(client, model, prompt)
    if not revised:
        raise ValueError("refine_creative_concept returned an empty concept.")
    return revised


class CreativeDirectorAssistant:
    """Runs the single-brief, evaluate-and-refine creative workflow."""

    def __init__(self) -> None:
        self.client, self.model = _runtime_client()
        self.creative_brief: dict[str, str] | None = None
        self.current_concept = ""
        self.evaluation_result: dict[str, Any] | None = None
        self.refinement_count = 0

    def run(self) -> dict[str, Any]:
        print(
            "Provide one complete creative brief with brand, product, "
            "target audience, objective, key product benefit, channels, "
            "budget, and constraints."
        )
        user_answer = input("> ")
        self.creative_brief = parse_creative_brief(
            self.client, self.model, user_answer
        )
        self.current_concept = generate_initial_concept(
            self.client, self.model, self.creative_brief
        )
        self.evaluation_result = evaluate_creative_concept(
            self.client, self.model, self.creative_brief, self.current_concept
        )

        while (
            self.evaluation_result["overall_score"] < 8.0
            and self.refinement_count < 2
        ):
            self.current_concept = refine_creative_concept(
                self.client,
                self.model,
                self.creative_brief,
                self.current_concept,
                self.evaluation_result,
            )
            self.refinement_count += 1
            self.evaluation_result = evaluate_creative_concept(
                self.client, self.model, self.creative_brief, self.current_concept
            )

        assert self.evaluation_result is not None
        final_result = {
            "creative_concept": self.current_concept,
            "evaluation": self.evaluation_result,
            "refinement_count": self.refinement_count,
            "quality_threshold_met": self.evaluation_result["overall_score"] >= 8.0,
        }
        self._present(final_result)
        return final_result

    @staticmethod
    def _present(final_result: dict[str, Any]) -> None:
        evaluation = final_result["evaluation"]
        print("\n=== Final Creative Concept ===")
        print(final_result["creative_concept"])
        print("\n=== Evaluation ===")
        print(json.dumps(evaluation, ensure_ascii=False, indent=2))
        print(f"\n=== Refinements ===\n{final_result['refinement_count']}")
        status = (
            "met"
            if final_result["quality_threshold_met"]
            else "not met; the two-refinement limit was reached"
        )
        print(f"\n=== Quality Threshold (overall >= 8.0) ===\n{status}")


def main() -> dict[str, Any] | None:
    try:
        return CreativeDirectorAssistant().run()
    except (AgentConfigurationError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return None


if __name__ == "__main__":
    main()
