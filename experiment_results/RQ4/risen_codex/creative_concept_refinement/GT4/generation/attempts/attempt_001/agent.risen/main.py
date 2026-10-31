from __future__ import annotations

import json
import os
import sys
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
    """Load simple KEY=VALUE entries from the agent's local .env file."""
    env_path = Path.cwd() / ".env"
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
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def _runtime_client() -> tuple[Any, str]:
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
            "缺少运行时模型配置：" + ", ".join(missing) +
            "。请在当前目录的 .env 或进程环境变量中设置。"
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "未安装官方 OpenAI Python Client，请先安装 openai。"
        ) from exc

    return OpenAI(api_key=api_key, base_url=base_url), model


def _ask(client: Any, model: str, prompt: str) -> str:
    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    output = getattr(response, "output_text", "")
    if not isinstance(output, str) or not output.strip():
        raise ValueError("运行时模型返回了空结果。")
    return output.strip()


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
                return text[start:index + 1]
    return text[start:]


def _remove_trailing_commas(text: str) -> str:
    """Repair commas before a closing JSON object/array, outside strings."""
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


def _parse_json_object(output: str, operation: str) -> dict[str, Any]:
    cleaned = output.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    cleaned = _remove_trailing_commas(_extract_first_json_object(cleaned))
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{operation} 返回了无效 JSON：{cleaned}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{operation} 必须返回 JSON 对象。")
    return parsed


def _parse_creative_brief(client: Any, model: str, user_answer: str) -> dict[str, str]:
    prompt = f"""
You are extracting a complete CreativeBrief from one user's answer.
Return one strict JSON object with exactly these text fields:
brand, product, target_audience, objective, key_product_benefit, channels,
budget, constraints.

Interpret the answer semantically. Preserve the user's meaning and wording as
much as possible. Do not invent facts or fill missing information. Every field
must be a non-empty string; if any required field is absent, return an empty
string for that field so the caller can report the incomplete brief.
Return JSON only, with no Markdown or commentary.

USER'S SINGLE ANSWER:
{user_answer}
"""
    parsed = _parse_json_object(_ask(client, model, prompt), "creative brief extraction")
    brief: dict[str, str] = {}
    missing = []
    for field in BRIEF_FIELDS:
        value = parsed.get(field)
        if not isinstance(value, str) or not value.strip():
            missing.append(field)
        else:
            brief[field] = value.strip()
    if missing:
        raise ValueError(
            "一次输入中的 creative brief 不完整，缺少或未能识别字段：" +
            ", ".join(missing)
        )
    return brief


def _generate_concept(client: Any, model: str, brief: dict[str, str]) -> str:
    prompt = f"""
You are CreativeConceptDeveloper, a senior creative director.
Generate one complete, specific marketing creative concept from the supplied
brief. Clearly describe the core idea, principal execution, brand or product
role, and how the idea serves the target audience and marketing objective.
Make it practical for the stated channels, budget, and constraints.

Do not invent brand facts, product capabilities, budgets, resources,
partnerships, technologies, research findings, or objectives absent from the
brief. Every claim and execution detail must be grounded in the brief.
Return only the concept prose, not JSON, scores, alternatives, or commentary
about this instruction.

CREATIVE BRIEF:
{json.dumps(brief, ensure_ascii=False, indent=2)}
"""
    concept = _ask(client, model, prompt)
    if not concept:
        raise ValueError("初始 creative concept 为空。")
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
or text before or after the object. Use strict JSON syntax.
Return exactly these fields:
originality_score, strategic_fit_score, audience_impact_score,
executability_score, evaluation_reasons, refinement_suggestions.
Scores must be integers from 1 to 10. Python will calculate the weighted
overall score deterministically.
"""


def evaluate_creative_concept(
    client: Any, model: str, creative_brief: dict[str, str], creative_concept: str
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
    result = _parse_json_object(_ask(client, model, prompt), "creative evaluation")
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
        if score < 1 or score > 10:
            raise ValueError(f"{field} must be between 1 and 10, received {score}.")
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
    client: Any,
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
    revised_concept = _ask(client, model, prompt)
    if not revised_concept:
        raise ValueError("refine_creative_concept returned an empty creative concept.")
    return revised_concept


def _present(final_result: dict[str, Any]) -> None:
    print("\n=== FINAL CREATIVE CONCEPT ===")
    print(final_result["creative_concept"])
    print("\n=== EVALUATION ===")
    print(json.dumps(final_result["evaluation"], ensure_ascii=False, indent=2))
    print(f"\n=== REFINEMENTS ===\n{final_result['refinement_count']}")
    if final_result["quality_threshold_met"]:
        status = "质量阈值已达到（weighted overall score >= 8.0）。"
    else:
        status = "两次 refinement 后仍未达到质量阈值（weighted overall score < 8.0）。"
    print(f"\n=== QUALITY THRESHOLD ===\n{status}")


def main() -> dict[str, Any]:
    """Run CreativeDirectorAssistant and return its final structured result."""
    client, model = _runtime_client()
    user_answer = input(
        "请一次性提供完整 creative brief（品牌、产品、目标受众、营销目标、"
        "核心产品利益、渠道、预算和其他约束）：\n> "
    ).strip()
    if not user_answer:
        raise ValueError("creative brief 不能为空。")

    creative_brief = _parse_creative_brief(client, model, user_answer)
    current_concept = _generate_concept(client, model, creative_brief)
    refinement_count = 0
    evaluation_result = evaluate_creative_concept(
        client, model, creative_brief, current_concept
    )

    while evaluation_result["overall_score"] < 8.0 and refinement_count < 2:
        current_concept = refine_creative_concept(
            client, model, creative_brief, current_concept, evaluation_result
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
    _present(final_result)
    return final_result


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, EOFError) as exc:
        print(f"执行失败：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
