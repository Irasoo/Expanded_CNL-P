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


def _load_local_env() -> None:
    """Load simple KEY=VALUE entries without overriding process variables."""
    candidates = [Path.cwd() / ".env", Path(__file__).resolve().parent / ".env"]
    seen: set[Path] = set()
    for path in candidates:
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            if key:
                os.environ.setdefault(key, value)


class CreativeDirectorAssistant:
    """Terminal agent for generating and iteratively improving a creative concept."""

    def __init__(self) -> None:
        _load_local_env()
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required in the environment or current .env file."
            )

        model = (
            os.environ.get("CNLP_REFERENCE_LLM_MODEL", "").strip()
            or os.environ.get("OPENAI_MODEL", "").strip()
        )
        if not model:
            raise RuntimeError(
                "Set CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL in the environment or .env file."
            )

        base_url = os.environ.get("BASE_URL", "").strip()
        client_args: dict[str, str] = {"api_key": api_key}
        if base_url:
            client_args["base_url"] = base_url
        self.client = OpenAI(**client_args)
        self.model = model

    def _complete(self, prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            reasoning={"effort": "high"},
        )
        output_text = getattr(response, "output_text", "")
        if not isinstance(output_text, str) or not output_text.strip():
            raise ValueError("The language model returned an empty response.")
        return output_text.strip()

    def parse_creative_brief(self, user_input: str) -> dict[str, str]:
        prompt = f"""
You are interpreting one user's complete creative brief for a marketing concept.
Extract exactly these required text fields and return one valid JSON object only:
{json.dumps(REQUIRED_BRIEF_FIELDS)}

Do not invent facts. Preserve the user's meaning and wording where possible.
Every field must be a non-empty string. The channels, budget, and constraints
fields may contain several items as one text value.

USER'S SINGLE BRIEF:
{user_input}
"""
        result = self._parse_json_object(self._complete(prompt), "creative brief")
        if not isinstance(result, dict):
            raise ValueError("The creative brief response must be a JSON object.")

        brief: dict[str, str] = {}
        missing: list[str] = []
        for field in REQUIRED_BRIEF_FIELDS:
            value = result.get(field)
            if not isinstance(value, str) or not value.strip():
                missing.append(field)
            else:
                brief[field] = value.strip()
        if missing:
            raise ValueError(
                "The single brief input did not provide valid values for: "
                + ", ".join(missing)
                + "."
            )
        return brief

    def generate_initial_concept(self, creative_brief: dict[str, str]) -> str:
        prompt = f"""
You are CreativeConceptDeveloper, creating an initial advertising or marketing
creative concept from the supplied brief.

Generate one complete and specific concept. Clearly describe the core idea,
principal execution, the brand or product's role, and how the idea serves the
target audience and marketing objective. Ground every claim and execution
detail in the brief. Do not invent product capabilities, resources,
partnerships, research, technologies, or facts. Keep the concept practical for
the stated channels, budget, and constraints.

Return only the concept text, with no JSON, score, alternatives, or process
commentary.

CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}
"""
        concept = self._complete(prompt).strip()
        if not concept:
            raise ValueError("Initial concept generation returned an empty concept.")
        return concept

    def evaluate_creative_concept(
        self, creative_brief: dict[str, str], creative_concept: str
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
- Give refinement directions that address weak criteria while preserving useful strengths.

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
        result = self._parse_json_object(
            self._complete(prompt), "creative evaluation"
        )
        if not isinstance(result, dict):
            raise ValueError("The evaluation response must be a JSON object.")

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
            if not 1 <= score <= 10:
                raise ValueError(f"{field} must be between 1 and 10, received {score}.")
            scores[field] = score

        evaluation_reasons = str(result.get("evaluation_reasons", "")).strip()
        refinement_suggestions = str(
            result.get("refinement_suggestions", "")
        ).strip()
        if not evaluation_reasons:
            raise ValueError("Evaluation result must contain evaluation_reasons.")
        if not refinement_suggestions:
            raise ValueError(
                "Evaluation result must contain refinement_suggestions."
            )

        overall_score = round(
            scores["originality_score"] * 0.30
            + scores["strategic_fit_score"] * 0.30
            + scores["audience_impact_score"] * 0.20
            + scores["executability_score"] * 0.20,
            2,
        )
        criteria = {
            "originality": scores["originality_score"],
            "strategic_fit": scores["strategic_fit_score"],
            "audience_impact": scores["audience_impact_score"],
            "executability": scores["executability_score"],
        }
        minimum_score = min(criteria.values())
        weak_criteria = [
            criterion
            for criterion, score in criteria.items()
            if score == minimum_score
        ]
        return {
            **scores,
            "overall_score": overall_score,
            "weak_criteria": weak_criteria,
            "evaluation_reasons": evaluation_reasons,
            "refinement_suggestions": refinement_suggestions,
        }

    def refine_creative_concept(
        self,
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
        revised_concept = self._complete(prompt).strip()
        if not revised_concept:
            raise ValueError("Refinement returned an empty creative concept.")
        return revised_concept

    @staticmethod
    def _parse_json_object(text: str, result_name: str) -> Any:
        output_text = text.strip()
        if output_text.startswith("```"):
            lines = output_text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            output_text = "\n".join(lines).strip()

        output_text = CreativeDirectorAssistant._extract_first_json_object(output_text)
        output_text = CreativeDirectorAssistant._remove_trailing_commas(output_text)
        try:
            return json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{result_name} returned invalid JSON: {output_text}"
            ) from exc

    @staticmethod
    def _extract_first_json_object(text: str) -> str:
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

    @staticmethod
    def _remove_trailing_commas(text: str) -> str:
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

    def run(self) -> dict[str, Any]:
        print(
            "Provide one complete creative brief in a single response, including "
            "brand, product, target audience, objective, key product benefit, "
            "channels, budget, and constraints."
        )
        user_input = sys.stdin.readline()
        if not user_input.strip():
            raise ValueError("The creative brief input cannot be empty.")

        creative_brief = self.parse_creative_brief(user_input.strip())
        current_concept = self.generate_initial_concept(creative_brief)
        evaluation_result = self.evaluate_creative_concept(
            creative_brief, current_concept
        )
        refinement_count = 0

        while evaluation_result["overall_score"] < 8.0 and refinement_count < 2:
            current_concept = self.refine_creative_concept(
                creative_brief, current_concept, evaluation_result
            )
            refinement_count += 1
            evaluation_result = self.evaluate_creative_concept(
                creative_brief, current_concept
            )

        return {
            "creative_concept": current_concept,
            "evaluation": evaluation_result,
            "refinement_count": refinement_count,
            "quality_threshold_met": evaluation_result["overall_score"] >= 8.0,
        }


def main() -> dict[str, Any] | None:
    try:
        result = CreativeDirectorAssistant().run()
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"Error: {exc}")
        return None

    print("\n=== Final Creative Concept ===")
    print(result["creative_concept"])
    print("\n=== Evaluation ===")
    print(json.dumps(result["evaluation"], ensure_ascii=False, indent=2))
    print(f"\n=== Refinements ===\n{result['refinement_count']}")
    if result["quality_threshold_met"]:
        print("\n=== Quality Threshold ===\nMet (overall score is at least 8.0).")
    else:
        print(
            "\n=== Quality Threshold ===\n"
            "Not met; the two-refinement limit was reached."
        )
    return result


if __name__ == "__main__":
    main()
