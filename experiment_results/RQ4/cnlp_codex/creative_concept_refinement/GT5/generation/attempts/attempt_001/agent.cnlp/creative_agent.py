from __future__ import annotations

import json
import os
from typing import Any, TypedDict

from dotenv import load_dotenv
from openai import OpenAI


QUALITY_THRESHOLD = 8.0
MAX_REFINEMENTS = 2
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


class CreativeBrief(TypedDict):
    brand: str
    product: str
    target_audience: str
    objective: str
    key_product_benefit: str
    channels: str
    budget: str
    constraints: str


class CreativeEvaluation(TypedDict):
    originality_score: float
    strategic_fit_score: float
    audience_impact_score: float
    executability_score: float
    overall_score: float
    weak_criteria: list[str]
    evaluation_reasons: str
    refinement_suggestions: str


class CreativeResult(TypedDict):
    creative_concept: str
    evaluation: CreativeEvaluation
    refinement_count: int
    quality_threshold_met: bool


AGENT_CONTEXT = """
You are CreativeDirectorAssistant, a creative director assistant responsible
for generating, evaluating, and improving marketing creative concepts for
brand, marketing, and creative professionals.

Treat the user's creative brief as the only source of brand and product facts.
Never invent product capabilities, budgets, resources, objectives, audiences,
partnerships, technologies, research findings, or other facts absent from the
brief. Keep the product or brand meaningful to the central idea. Make outputs
specific enough for professional review, while using language appropriate for
the language and level of detail in the user's brief.
""".strip()


class RuntimeLLM:
    def __init__(self) -> None:
        load_dotenv()

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        base_url = os.getenv("BASE_URL", "").strip()
        model = (
            os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip()
            or os.getenv("OPENAI_MODEL", "").strip()
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
                "Missing required runtime configuration: " + ", ".join(missing)
            )

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def complete(self, instruction: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            reasoning={"effort": "high"},
            input=f"{AGENT_CONTEXT}\n\n{instruction}",
        )
        output_text = response.output_text.strip()
        if not output_text:
            raise ValueError("The language model returned an empty response.")
        return output_text


def _extract_first_json_object(text: str) -> str:
    """Return the first balanced JSON object while preserving quoted text."""
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
    """Remove commas before JSON closers, never altering quoted content."""
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


def collect_creative_brief(llm: RuntimeLLM) -> CreativeBrief:
    print(
        "Provide one complete creative brief in a single response. Include the "
        "brand, product, target audience, marketing objective, key product "
        "benefit, intended channels, budget, and constraints."
    )
    raw_input = input("> ").strip()
    if not raw_input:
        raise ValueError("The creative brief cannot be empty.")

    prompt = f"""
Convert the user's single creative-brief response into the exact JSON shape
below. Extract only information actually supplied by the user. Do not infer or
invent missing facts. Preserve the user's language. A statement that there is
no budget limit or no additional constraint is valid information and should be
represented faithfully. For any field the user did not supply, use null.

Return one valid JSON object only, without Markdown:
{{
  "brand": "text or null",
  "product": "text or null",
  "target_audience": "text or null",
  "objective": "text or null",
  "key_product_benefit": "text or null",
  "channels": "text or null",
  "budget": "text or null",
  "constraints": "text or null"
}}

USER RESPONSE:
{raw_input}
"""
    parsed = _parse_json_object(llm.complete(prompt), "creative brief extraction")

    brief: dict[str, str] = {}
    missing: list[str] = []
    for field in BRIEF_FIELDS:
        value = parsed.get(field)
        if not isinstance(value, str) or not value.strip():
            missing.append(field)
        else:
            brief[field] = value.strip()

    if missing:
        raise ValueError(
            "The single creative-brief response was incomplete. Missing fields: "
            + ", ".join(missing)
        )
    return brief  # type: ignore[return-value]


def generate_initial_concept(
    llm: RuntimeLLM, creative_brief: CreativeBrief
) -> str:
    prompt = f"""
Generate one complete and specific initial marketing creative concept from the
brief below. Clearly describe:
- the core idea and memorable creative mechanism;
- the principal execution across the requested channels;
- the brand or product's essential role;
- how the idea serves the target audience and marketing objective; and
- how the execution respects the stated budget and constraints.

Remain fully grounded in the brief. Do not invent facts, capabilities,
resources, partners, evidence, or claims. Return only the complete concept,
not alternatives, scores, or process commentary. Write in the user's language.

CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}
"""
    concept = llm.complete(prompt).strip()
    if not concept:
        raise ValueError("Initial concept generation returned an empty concept.")
    return concept


def evaluate_creative_concept(
    llm: RuntimeLLM,
    creative_brief: CreativeBrief,
    creative_concept: str,
) -> CreativeEvaluation:
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

Return one valid JSON object only. Do not add Markdown fences, explanations,
or text before or after the object. Use integer scores from 1 to 10. Do not
calculate the weighted overall score; Python will calculate it deterministically.

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

Evaluate the concept strictly according to the rubric. Write the explanatory
text in the user's language.
"""
    result = _parse_json_object(llm.complete(prompt), "evaluate_creative_concept")

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
        value = result[key]
        if isinstance(value, bool):
            raise ValueError(f"{key} must be numeric.")
        try:
            score = float(value)
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
        criterion for criterion, score in four_criteria.items() if score == minimum_score
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
    llm: RuntimeLLM,
    creative_brief: CreativeBrief,
    current_concept: str,
    evaluation: CreativeEvaluation,
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
Write in the user's language.
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
    revised_concept = llm.complete(prompt).strip()
    if not revised_concept:
        raise ValueError("refine_creative_concept returned an empty concept.")
    return revised_concept


def display_result(final_result: CreativeResult) -> None:
    evaluation = final_result["evaluation"]
    print("\n=== Final Creative Concept ===")
    print(final_result["creative_concept"])
    print("\n=== Standardized Evaluation ===")
    print(f"Originality:      {evaluation['originality_score']:.1f}/10")
    print(f"Strategic fit:    {evaluation['strategic_fit_score']:.1f}/10")
    print(f"Audience impact:  {evaluation['audience_impact_score']:.1f}/10")
    print(f"Executability:    {evaluation['executability_score']:.1f}/10")
    print(f"Weighted overall: {evaluation['overall_score']:.2f}/10")
    print("Weak criteria:    " + ", ".join(evaluation["weak_criteria"]))
    print("\nEvaluation reasons:")
    print(evaluation["evaluation_reasons"])
    print("\nRefinement suggestions:")
    print(evaluation["refinement_suggestions"])
    print("\n=== Workflow Status ===")
    print(f"Refinements performed: {final_result['refinement_count']}")
    if final_result["quality_threshold_met"]:
        print(f"Quality threshold reached: yes (>= {QUALITY_THRESHOLD:.1f})")
    else:
        print(
            "Quality threshold reached: no "
            f"(two-refinement limit reached below {QUALITY_THRESHOLD:.1f})"
        )


def creative_concept_developer(llm: RuntimeLLM) -> CreativeResult:
    creative_brief = collect_creative_brief(llm)
    current_concept = generate_initial_concept(llm, creative_brief)
    evaluation_result = evaluate_creative_concept(
        llm, creative_brief, current_concept
    )
    refinement_count = 0

    while (
        evaluation_result["overall_score"] < QUALITY_THRESHOLD
        and refinement_count < MAX_REFINEMENTS
    ):
        current_concept = refine_creative_concept(
            llm, creative_brief, current_concept, evaluation_result
        )
        refinement_count += 1
        evaluation_result = evaluate_creative_concept(
            llm, creative_brief, current_concept
        )

    final_result: CreativeResult = {
        "creative_concept": current_concept,
        "evaluation": evaluation_result,
        "refinement_count": refinement_count,
        "quality_threshold_met": (
            evaluation_result["overall_score"] >= QUALITY_THRESHOLD
        ),
    }
    display_result(final_result)
    return final_result


def run_agent() -> CreativeResult:
    llm = RuntimeLLM()
    return creative_concept_developer(llm)
