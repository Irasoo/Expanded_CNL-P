from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
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

QUALITY_THRESHOLD = 8.0
MAX_REFINEMENTS = 2

AGENT_GOVERNANCE = """
You are CreativeDirectorAssistant, a creative director assistant responsible
for generating, evaluating, and improving marketing creative concepts for
brand, marketing, and creative professionals.

The creative concept is the central marketing idea and its principal
execution for the supplied brand, product, audience, and objective. Evaluation
uses originality, strategic fit, audience impact, and executability. A
refinement must target the weakest dimensions while preserving useful strong
dimensions and remaining faithful to the original brief.

Mandatory boundaries:
- Ground every creative claim and execution detail in the user's brief.
- Do not invent brand facts, product capabilities, budgets, resources,
  objectives, audiences, partnerships, technologies, or research findings.
- Preserve the original brief even when a change might otherwise improve a
  score.
- Use language appropriate for brand, marketing, and creative professionals.
- Respond in the primary language used by the user in the creative brief.
""".strip()


@dataclass(frozen=True)
class RuntimeConfig:
    api_key: str
    base_url: str
    model: str

    @classmethod
    def from_environment(cls) -> "RuntimeConfig":
        load_dotenv(Path(__file__).resolve().with_name(".env"), override=False)

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
                "Missing runtime configuration: " + ", ".join(missing) + ". "
                "Set the values in the process environment or in .env next "
                "to main.py."
            )

        return cls(api_key=api_key, base_url=base_url, model=model)


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
            elif character == chr(92):
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
    """Repair commas before a closing object or array outside strings."""
    characters: List[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        character = text[index]
        if in_string:
            characters.append(character)
            if escaped:
                escaped = False
            elif character == chr(92):
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


def _parse_json_object(output_text: str, operation: str) -> Dict[str, Any]:
    cleaned = output_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    cleaned = _extract_first_json_object(cleaned)
    cleaned = _remove_trailing_commas(cleaned)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{operation} returned invalid JSON: {cleaned}"
        ) from exc

    if not isinstance(result, dict):
        raise ValueError(f"{operation} must return a JSON object.")
    return result


class CreativeDirectorAssistant:
    def __init__(self, config: RuntimeConfig) -> None:
        self._client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )
        self._model = config.model

    def _call_model(self, prompt: str) -> str:
        response = self._client.responses.create(
            model=self._model,
            input=prompt,
            reasoning={"effort": "high"},
        )
        output_text = response.output_text.strip()
        if not output_text:
            raise ValueError("The language model returned an empty response.")
        return output_text

    def collect_creative_brief(self) -> Dict[str, str]:
        print(
            "Provide one complete creative brief containing the brand, "
            "product, target audience, marketing objective, key product "
            "benefit, intended channels, budget, and other constraints."
        )
        print("You may answer in natural language or as a JSON object.")
        raw_input = input("> ")

        if not raw_input.strip():
            raise ValueError("The creative brief cannot be empty.")

        prompt = f"""
{AGENT_GOVERNANCE}

Convert the user's single creative-brief response into one strict JSON object.
Extract only information explicitly supplied by the user. Do not infer or
invent missing brand facts, capabilities, audiences, objectives, channels,
budgets, constraints, or benefits. Use an empty string for a field that was
not supplied. Preserve meaningful detail rather than over-summarizing it.

Return exactly these eight string fields and no others:
{{
  "brand": "",
  "product": "",
  "target_audience": "",
  "objective": "",
  "key_product_benefit": "",
  "channels": "",
  "budget": "",
  "constraints": ""
}}

Return valid JSON only, without Markdown fences or commentary.

USER RESPONSE:
{raw_input}
"""
        parsed = _parse_json_object(
            self._call_model(prompt),
            "creative brief extraction",
        )

        creative_brief: Dict[str, str] = {}
        for field in BRIEF_FIELDS:
            value = parsed.get(field, "")
            if not isinstance(value, str):
                raise ValueError(
                    f"Creative brief field {field!r} must be text."
                )
            creative_brief[field] = value.strip()

        missing = [field for field in BRIEF_FIELDS if not creative_brief[field]]
        if missing:
            raise ValueError(
                "The single creative-brief response was incomplete. Missing: "
                + ", ".join(missing)
                + ". Run the agent again and include all eight fields in one "
                "response."
            )

        return creative_brief

    def generate_initial_concept(self, creative_brief: Dict[str, str]) -> str:
        prompt = f"""
{AGENT_GOVERNANCE}

Generate one complete and specific initial marketing creative concept from the
creative brief below. Clearly describe:
- the core idea;
- the principal execution;
- the meaningful role of the brand or product; and
- how the idea serves the target audience and marketing objective.

Make the concept concrete enough to evaluate and execute across the supplied
channels and budget. Do not add facts or resources absent from the brief.
Return only the complete concept, without evaluation scores or process notes.

CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}
"""
        concept = self._call_model(prompt).strip()
        if not concept:
            raise ValueError("Initial concept generation returned empty text.")
        return concept

    def evaluate_creative_concept(
        self,
        creative_brief: Dict[str, str],
        creative_concept: str,
    ) -> Dict[str, Any]:
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
or text before or after the object. Use strict JSON syntax: field names and
string values must use double quotes, and there must be no trailing comma
before a closing object or array.

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
{AGENT_GOVERNANCE}

{scoring_rubric}

CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}

CURRENT CREATIVE CONCEPT:
{creative_concept}

Evaluate the concept strictly according to the rubric.
"""
        result = _parse_json_object(
            self._call_model(prompt),
            "evaluate_creative_concept",
        )

        required_scores = (
            "originality_score",
            "strategic_fit_score",
            "audience_impact_score",
            "executability_score",
        )
        normalized_scores: Dict[str, float] = {}

        for key in required_scores:
            if key not in result:
                raise ValueError(f"Missing score in evaluation result: {key}")
            if isinstance(result[key], bool):
                raise ValueError(f"{key} must be numeric.")
            try:
                score = float(result[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be numeric.") from exc
            if score < 1 or score > 10:
                raise ValueError(
                    f"{key} must be between 1 and 10, received {score}."
                )
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

        evaluation_reasons = str(
            result.get("evaluation_reasons", "")
        ).strip()
        refinement_suggestions = str(
            result.get("refinement_suggestions", "")
        ).strip()
        if not evaluation_reasons:
            raise ValueError(
                "Evaluation result must contain evaluation_reasons."
            )
        if not refinement_suggestions:
            raise ValueError(
                "Evaluation result must contain refinement_suggestions."
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
        self,
        creative_brief: Dict[str, str],
        current_concept: str,
        evaluation: Dict[str, Any],
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
{AGENT_GOVERNANCE}

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
        revised_concept = self._call_model(prompt).strip()
        if not revised_concept:
            raise ValueError(
                "refine_creative_concept returned an empty creative concept."
            )
        return revised_concept

    def run(self) -> Dict[str, Any]:
        creative_brief = self.collect_creative_brief()
        current_concept = self.generate_initial_concept(creative_brief)
        evaluation_result = self.evaluate_creative_concept(
            creative_brief,
            current_concept,
        )
        refinement_count = 0

        while (
            evaluation_result["overall_score"] < QUALITY_THRESHOLD
            and refinement_count < MAX_REFINEMENTS
        ):
            current_concept = self.refine_creative_concept(
                creative_brief,
                current_concept,
                evaluation_result,
            )
            refinement_count += 1
            evaluation_result = self.evaluate_creative_concept(
                creative_brief,
                current_concept,
            )

        final_result = {
            "creative_concept": current_concept,
            "evaluation": evaluation_result,
            "refinement_count": refinement_count,
            "quality_threshold_met": (
                evaluation_result["overall_score"] >= QUALITY_THRESHOLD
            ),
        }
        self.display_final_result(final_result)
        return final_result

    @staticmethod
    def display_final_result(final_result: Dict[str, Any]) -> None:
        evaluation = final_result["evaluation"]
        threshold_status = (
            "Reached (overall score is at least 8.0)"
            if final_result["quality_threshold_met"]
            else "Not reached (the two-refinement limit was reached)"
        )

        print("\n=== Final Creative Concept ===")
        print(final_result["creative_concept"])
        print("\n=== Standardized Evaluation ===")
        print(f"Originality:      {evaluation['originality_score']}/10")
        print(f"Strategic fit:    {evaluation['strategic_fit_score']}/10")
        print(f"Audience impact:  {evaluation['audience_impact_score']}/10")
        print(f"Executability:    {evaluation['executability_score']}/10")
        print(f"Weighted overall: {evaluation['overall_score']}/10")
        print("Weak criteria:    " + ", ".join(evaluation["weak_criteria"]))
        print("\nEvaluation reasons:")
        print(evaluation["evaluation_reasons"])
        print("\nRefinement suggestions:")
        print(evaluation["refinement_suggestions"])
        print("\n=== Refinement Summary ===")
        print(f"Refinements performed: {final_result['refinement_count']}")
        print(f"Quality threshold: {threshold_status}")


def main() -> Dict[str, Any]:
    config = RuntimeConfig.from_environment()
    agent = CreativeDirectorAssistant(config)
    return agent.run()


if __name__ == "__main__":
    main()
