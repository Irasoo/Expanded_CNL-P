from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI


CREATIVE_BRIEF_FIELDS = (
    "brand",
    "product",
    "target_audience",
    "objective",
    "key_product_benefit",
    "channels",
    "budget",
    "constraints",
)

PERSONA = (
    "You are a creative director assistant responsible for generating, "
    "evaluating, and improving marketing creative concepts. Your role is to "
    "generate an initial concept from the user's creative brief, use the "
    "standardized evaluation results to judge its quality, and refine weak "
    "dimensions without discarding strong dimensions. Do not invent brand "
    "facts, product capabilities, budgets, resources, objectives, audiences, "
    "partnerships, technologies, or research findings absent from the brief."
)

AUDIENCE = (
    "The audience is brand, marketing, and creative professionals who need "
    "to develop and improve an advertising or marketing concept. They need a "
    "complete creative concept, its standardized evaluation, the number of "
    "refinements performed, and a clear quality-threshold status."
)

CONCEPTS = (
    "Creative concept means the central marketing idea and its principal "
    "execution for a particular brand, product, audience, and objective. "
    "Creative evaluation uses originality, strategic fit, audience impact, "
    "and executability. A refinement targets the weakest dimensions while "
    "preserving strong dimensions and the original brief. The quality "
    "threshold is a weighted overall score of at least 8.0."
)

CONSTRAINTS = (
    "Ground every creative claim and execution detail in the supplied brief. "
    "Use the same fixed evaluation framework for every evaluation. Stop when "
    "the weighted score reaches 8.0. Refine at most two times. Prioritize the "
    "weakest criteria, preserve useful high-scoring properties, and never "
    "violate the original brief merely to obtain a higher score."
)


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries from the project-local .env if present."""
    env_path = Path(".env")
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
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
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def _required_setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"缺少运行时配置 {name}。请在 .env 或当前进程环境变量中设置它。"
        )
    return value


def _runtime_config() -> tuple[OpenAI, str]:
    _load_dotenv()
    api_key = _required_setting("OPENAI_API_KEY")
    base_url = _required_setting("BASE_URL")
    model = (
        os.environ.get("CNLP_REFERENCE_LLM_MODEL", "").strip()
        or os.environ.get("OPENAI_MODEL", "").strip()
    )
    if not model:
        raise RuntimeError(
            "缺少模型配置。请设置 CNLP_REFERENCE_LLM_MODEL 或 OPENAI_MODEL。"
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
    """Repair commas before closing JSON delimiters without changing strings."""
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
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{operation} 返回了无效 JSON: {cleaned}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{operation} 必须返回 JSON 对象。")
    return value


def _parse_creative_brief(raw_input: str, client: OpenAI, model: str) -> dict[str, str]:
    prompt = f"""
{PERSONA}

Convert the user's one-time creative brief input into exactly one strict JSON
object with these text fields:
{json.dumps(list(CREATIVE_BRIEF_FIELDS), ensure_ascii=False)}

{CONSTRAINTS}
Do not infer or invent missing facts. If a field is not supplied, use an empty
string for that field; the application will reject incomplete briefs. Preserve
the user's meaning and details. Return only the JSON object, with no Markdown.

USER'S CREATIVE BRIEF INPUT:
{raw_input}
"""
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    parsed = _parse_json_response(response.output_text, "creative brief parser")
    brief: dict[str, str] = {}
    for field in CREATIVE_BRIEF_FIELDS:
        value = parsed.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"创意简报缺少必填字段 {field}。请在一次输入中提供完整简报。"
            )
        brief[field] = value.strip()
    return brief


def _generate_initial_concept(
    creative_brief: dict[str, str], client: OpenAI, model: str
) -> str:
    prompt = f"""
{PERSONA}

{AUDIENCE}

{CONCEPTS}

{CONSTRAINTS}

Generate one complete and specific initial marketing creative concept from
the creative brief below. Clearly describe the core idea, principal
execution, brand or product role, and how the idea serves the target audience
and marketing objective. Stay grounded in the brief and return only the
concept text, not an evaluation or a list of alternatives.

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
        raise ValueError("initial concept generation returned an empty concept.")
    return concept


def evaluate_creative_concept(
    creative_brief: dict[str, str], creative_concept: str, client: OpenAI, model: str
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

    prompt = f"""
{PERSONA}

{CONCEPTS}

{CONSTRAINTS}

{scoring_rubric}

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
    result = _parse_json_response(response.output_text, "evaluate_creative_concept")

    required_scores = (
        "originality_score",
        "strategic_fit_score",
        "audience_impact_score",
        "executability_score",
    )
    normalized_scores: dict[str, float] = {}
    for key in required_scores:
        if key not in result:
            raise ValueError(f"Missing score in evaluation result: {key}")
        try:
            score = float(result[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be numeric.") from exc
        if score < 1 or score > 10:
            raise ValueError(f"{key} must be between 1 and 10, received {score}.")
        normalized_scores[key] = score

    overall_score = (
        normalized_scores["originality_score"] * 0.30
        + normalized_scores["strategic_fit_score"] * 0.30
        + normalized_scores["audience_impact_score"] * 0.20
        + normalized_scores["executability_score"] * 0.20
    )
    four_criteria = {
        "originality": normalized_scores["originality_score"],
        "strategic_fit": normalized_scores["strategic_fit_score"],
        "audience_impact": normalized_scores["audience_impact_score"],
        "executability": normalized_scores["executability_score"],
    }
    minimum_score = min(four_criteria.values())
    weak_criteria = [
        criterion
        for criterion, score in four_criteria.items()
        if score == minimum_score
    ]
    evaluation_reasons = str(result.get("evaluation_reasons", "")).strip()
    refinement_suggestions = str(result.get("refinement_suggestions", "")).strip()
    if not evaluation_reasons:
        raise ValueError("Evaluation result must contain evaluation_reasons.")
    if not refinement_suggestions:
        raise ValueError("Evaluation result must contain refinement_suggestions.")

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
    client: OpenAI,
    model: str,
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
{PERSONA}

{CONCEPTS}

{CONSTRAINTS}

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
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    revised_concept = response.output_text.strip()
    if not revised_concept:
        raise ValueError("refine_creative_concept returned an empty concept.")
    return revised_concept


def _display_final_result(final_result: dict[str, Any]) -> None:
    evaluation = final_result["evaluation"]
    print("\n===== 最终创意概念 =====")
    print(final_result["creative_concept"])
    print("\n===== 创意评估 =====")
    print(f"原创性: {evaluation['originality_score']}/10")
    print(f"战略契合度: {evaluation['strategic_fit_score']}/10")
    print(f"受众影响力: {evaluation['audience_impact_score']}/10")
    print(f"可执行性: {evaluation['executability_score']}/10")
    print(f"加权总分: {evaluation['overall_score']}/10")
    print("弱项: " + ("、".join(evaluation["weak_criteria"]) or "无"))
    print(f"评估理由: {evaluation['evaluation_reasons']}")
    print(f"优化建议: {evaluation['refinement_suggestions']}")
    print(f"\n优化次数: {final_result['refinement_count']}")
    status = "已达到 8.0 质量阈值" if final_result["quality_threshold_met"] else "未达到 8.0 质量阈值，已达到两次优化上限"
    print(f"质量阈值状态: {status}")


class CreativeConceptDeveloper:
    """The CNL-P Worker that owns the main flow and its typed state."""

    def __init__(self, client: OpenAI, model: str) -> None:
        self.client = client
        self.model = model

    def run(self) -> dict[str, Any]:
        print(
            "请输入完整创意简报。一次输入中请包含 brand、product、target_audience、"
            "objective、key_product_benefit、channels、budget 和 constraints；"
            "可使用 JSON 或自然语言。"
        )
        raw_input = input("> ").strip()
        if not raw_input:
            raise ValueError("创意简报输入不能为空。")

        # COMMAND-1: the single INPUT command reads exactly once, then normalizes
        # the user's natural-language or JSON brief into the declared structure.
        creative_brief = _parse_creative_brief(raw_input, self.client, self.model)

        # COMMAND-2 and COMMAND-3: generate, then call the standardized API.
        current_concept = _generate_initial_concept(
            creative_brief, self.client, self.model
        )
        evaluation_result = evaluate_creative_concept(
            creative_brief, current_concept, self.client, self.model
        )
        refinement_count = 0

        # MAIN FLOW loop: the condition is rechecked after every evaluation.
        while evaluation_result["overall_score"] < 8.0 and refinement_count < 2:
            current_concept = refine_creative_concept(
                creative_brief,
                current_concept,
                evaluation_result,
                self.client,
                self.model,
            )
            refinement_count += 1
            evaluation_result = evaluate_creative_concept(
                creative_brief, current_concept, self.client, self.model
            )

        quality_threshold_met = evaluation_result["overall_score"] >= 8.0
        final_result = {
            "creative_concept": current_concept,
            "evaluation": evaluation_result,
            "refinement_count": refinement_count,
            "quality_threshold_met": quality_threshold_met,
        }
        _display_final_result(final_result)
        return final_result


class CreativeDirectorAssistant:
    def __init__(self) -> None:
        self.client, self.model = _runtime_config()
        self.worker = CreativeConceptDeveloper(self.client, self.model)

    def run(self) -> dict[str, Any]:
        return self.worker.run()


def main() -> dict[str, Any]:
    agent = CreativeDirectorAssistant()
    return agent.run()


if __name__ == "__main__":
    main()
