from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI


class ConfigurationError(RuntimeError):
    """Raised when the runtime model configuration is incomplete."""


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries without requiring python-dotenv."""
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
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(
            f"Missing {name}. Set it in .env or the current process environment."
        )
    return value


class CreativeDirectorAssistant:
    """Runtime implementation of the CreativeDirectorAssistant CNL-P agent."""

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

    def __init__(self) -> None:
        _load_dotenv()
        api_key = _required_env("OPENAI_API_KEY")
        base_url = _required_env("BASE_URL")
        model = (
            os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip()
            or os.getenv("OPENAI_MODEL", "").strip()
        )
        if not model:
            raise ConfigurationError(
                "Missing CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL. "
                "Set one in .env or the current process environment."
            )

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.creative_brief: dict[str, str] | None = None
        self.current_concept = ""
        self.evaluation_result: dict[str, Any] | None = None
        self.refinement_count = 0
        self.final_result: dict[str, Any] | None = None

    def _respond(self, prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            reasoning={"effort": "high"},
        )
        output_text = response.output_text.strip()
        if not output_text:
            raise ValueError("The language model returned an empty response.")
        return output_text

    def _call_json(self, prompt: str, operation: str) -> dict[str, Any]:
        output_text = self._clean_json_text(self._respond(prompt))
        try:
            result = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{operation} returned invalid JSON: {output_text}"
            ) from exc
        if not isinstance(result, dict):
            raise ValueError(f"{operation} must return a JSON object.")
        return result

    @staticmethod
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
                    return text[start : index + 1]
        return text[start:]

    @staticmethod
    def _remove_trailing_commas(text: str) -> str:
        """Repair commas before closing JSON delimiters outside strings."""
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

    @classmethod
    def _clean_json_text(cls, output_text: str) -> str:
        output_text = output_text.strip()
        if output_text.startswith("```"):
            lines = output_text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            output_text = "\n".join(lines).strip()
        return cls._remove_trailing_commas(
            cls._extract_first_json_object(output_text)
        )

    @staticmethod
    def _validate_brief(brief: Any) -> dict[str, str]:
        if not isinstance(brief, dict):
            raise ValueError("creative_brief must be a dictionary.")
        missing = [
            field
            for field in CreativeDirectorAssistant.REQUIRED_BRIEF_FIELDS
            if field not in brief
        ]
        if missing:
            raise ValueError(
                "The creative brief is missing required fields: "
                + ", ".join(missing)
            )

        normalized: dict[str, str] = {}
        for field in CreativeDirectorAssistant.REQUIRED_BRIEF_FIELDS:
            value = brief[field]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"creative_brief.{field} must be non-empty text.")
            normalized[field] = value.strip()
        return normalized

    def _parse_brief(self, user_input: str) -> dict[str, str]:
        if not user_input.strip():
            raise ValueError("The creative brief input cannot be empty.")

        try:
            parsed = json.loads(user_input)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return self._validate_brief(parsed)

        prompt = f"""
You are extracting a complete marketing creative brief for a creative director
assistant. Understand the user's single response semantically. Return one
strict JSON object with exactly these string fields:
brand, product, target_audience, objective, key_product_benefit, channels,
budget, constraints.

Do not invent facts. Preserve the user's wording where possible. If the user
does not provide a field, use an empty string so the application can report the
missing information. Do not ask a follow-up question and do not add Markdown.

USER'S CREATIVE BRIEF:
{user_input}
"""
        return self._validate_brief(self._call_json(prompt, "brief extraction"))

    def _generate_initial_concept(self, brief: dict[str, str]) -> str:
        prompt = f"""
You are a creative director assistant responsible for generating a marketing
creative concept. Develop one complete and specific concept from the supplied
brief. Clearly describe the core idea, principal execution, brand or product
role, and how the idea serves the target audience and marketing objective.

Persona and boundaries:
- Do not invent brand facts, product capabilities, budgets, resources,
  objectives, audiences, partnerships, technologies, or research findings.
- Every creative claim and execution detail must be grounded in the brief.
- Keep the product meaningful to the central idea.

Audience: brand, marketing, and creative professionals. Make the concept clear
enough to evaluate and execute, without assuming unstated resources.

Domain concepts: a creative concept is the central marketing idea and its
principal execution; it must connect the brand, product, audience, and objective.

CREATIVE BRIEF:
{json.dumps(brief, ensure_ascii=False, indent=2)}

Return only the complete creative concept in prose. Do not return alternatives,
scores, JSON, or commentary about this instruction.
"""
        concept = self._respond(prompt).strip()
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
{scoring_rubric}

CREATIVE BRIEF:
{json.dumps(creative_brief, ensure_ascii=False, indent=2)}

CURRENT CREATIVE CONCEPT:
{creative_concept}

Evaluate the concept strictly according to the rubric.
"""
        result = self._call_json(prompt, "evaluate_creative_concept")
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
            if not score.is_integer() or score < 1 or score > 10:
                raise ValueError(f"{key} must be an integer from 1 to 10.")
            normalized_scores[key] = int(score)

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
        refinement_suggestions = str(
            result.get("refinement_suggestions", "")
        ).strip()
        if not evaluation_reasons:
            raise ValueError("Evaluation result must contain evaluation_reasons.")
        if not refinement_suggestions:
            raise ValueError(
                "Evaluation result must contain refinement_suggestions."
            )

        return {
            **normalized_scores,
            "overall_score": round(overall_score, 2),
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
        revised_concept = self._respond(prompt).strip()
        if not revised_concept:
            raise ValueError(
                "refine_creative_concept returned an empty creative concept."
            )
        return revised_concept

    def run_worker(self, input_reader: Callable[[str], str] = input) -> dict[str, Any]:
        print(
            "请一次性提供完整的创意 brief，包含品牌、产品、目标受众、营销目标、"
            "核心产品利益、渠道、预算和其他约束。"
        )
        user_input = input_reader("Creative brief: ")
        self.creative_brief = self._parse_brief(user_input)

        self.current_concept = self._generate_initial_concept(self.creative_brief)
        self.evaluation_result = self.evaluate_creative_concept(
            self.creative_brief, self.current_concept
        )

        while (
            self.evaluation_result["overall_score"] < 8.0
            and self.refinement_count < 2
        ):
            self.current_concept = self.refine_creative_concept(
                self.creative_brief,
                self.current_concept,
                self.evaluation_result,
            )
            self.refinement_count += 1
            self.evaluation_result = self.evaluate_creative_concept(
                self.creative_brief, self.current_concept
            )

        quality_threshold_met = self.evaluation_result["overall_score"] >= 8.0
        self.final_result = {
            "creative_concept": self.current_concept,
            "evaluation": self.evaluation_result,
            "refinement_count": self.refinement_count,
            "quality_threshold_met": quality_threshold_met,
        }
        self._display_result(self.final_result)
        return self.final_result

    @staticmethod
    def _display_result(result: dict[str, Any]) -> None:
        evaluation = result["evaluation"]
        print("\n=== Final Creative Concept ===")
        print(result["creative_concept"])
        print("\n=== Evaluation ===")
        print(f"Originality: {evaluation['originality_score']}/10")
        print(f"Strategic fit: {evaluation['strategic_fit_score']}/10")
        print(f"Audience impact: {evaluation['audience_impact_score']}/10")
        print(f"Executability: {evaluation['executability_score']}/10")
        print(f"Overall score: {evaluation['overall_score']}/10")
        print("Weak criteria: " + ", ".join(evaluation["weak_criteria"]))
        print("Evaluation reasons: " + evaluation["evaluation_reasons"])
        print("Refinement suggestions: " + evaluation["refinement_suggestions"])
        print(f"\nRefinements performed: {result['refinement_count']}")
        status = "met" if result["quality_threshold_met"] else "not met"
        print(f"Quality threshold (8.0): {status}")


def main() -> dict[str, Any]:
    """Initialize the agent, execute its entry Worker, and return its result."""
    agent = CreativeDirectorAssistant()
    return agent.run_worker()


if __name__ == "__main__":
    main()
