from __future__ import annotations


def evaluate_creative_concept(
    creative_brief: dict,
    creative_concept: str
) -> dict:

    import json
    import os

    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["BASE_URL"],
    )
    model = os.environ["OPENAI_MODEL"]

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

    response = client.responses.create(
        model=model,
        input=prompt
    )

    output_text = response.output_text.strip()

    if output_text.startswith("```"):
        lines = output_text.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        output_text = "\n".join(lines).strip()

    def extract_first_json_object(text: str) -> str:
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

    def remove_trailing_commas(text: str) -> str:
        """Repair commas immediately before `}` or `]`, but never inside strings."""
        characters = []
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

    output_text = extract_first_json_object(output_text)
    output_text = remove_trailing_commas(output_text)

    try:
        result = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"evaluate_creative_concept returned invalid JSON: {output_text}"
        ) from exc

    required_scores = [
        "originality_score",
        "strategic_fit_score",
        "audience_impact_score",
        "executability_score",
    ]

    normalized_scores = {}

    for key in required_scores:
        if key not in result:
            raise ValueError(f"Missing score in evaluation result: {key}")

        try:
            score = float(result[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be numeric.") from exc

        if score < 1 or score > 10:
            raise ValueError(
                f"{key} must be between 1 and 10, received {score}."
            )

        normalized_scores[key] = score

    # Deterministic weighted score from the four-criterion framework.
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
    creative_brief: dict,
    current_concept: str,
    evaluation: dict
) -> str:

    import json
    import os

    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["BASE_URL"],
    )
    model = os.environ["OPENAI_MODEL"]

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

    response = client.responses.create(
        model=model,
        input=prompt
    )

    revised_concept = response.output_text.strip()

    if not revised_concept:
        raise ValueError(
            "refine_creative_concept returned an empty creative concept."
        )

    return revised_concept
