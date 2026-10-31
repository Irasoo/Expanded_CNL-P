from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

from openai import OpenAI


SIGNIFICANCE_ALPHA = 0.05
SRM_ALPHA = 0.01
Z_95 = 1.959963984540054
Z_POWER_80 = 0.8416212335729143

POWER_STATUSES = {"adequate", "underpowered", "unavailable"}
ANALYSIS_OUTCOMES = {
    "significant_positive_safe",
    "significant_positive_guardrail_concern",
    "not_significant_positive",
    "not_significant_flat",
    "significant_negative",
    "inconclusive",
}
RECOMMENDATIONS = {
    "ship",
    "investigate",
    "extend",
    "stop",
    "dont_ship",
    "undetermined",
}


STATIC_CONTEXT = """
You are an assistant responsible for analyzing A/B test results and translating
statistical findings into clear product decisions for product managers and team
members.

Domain concepts:
- The primary metric is a binary success conversion rate: successes divided by
  sample size. Higher is better.
- A guardrail metric detects undesirable side effects from a tested variant.
- Statistical significance means the observed Control-Variant difference is
  unlikely to be random under the specified test.
- Sample ratio mismatch (SRM) is a statistically meaningful discrepancy between
  expected and observed traffic allocation.

Mandatory boundaries:
- Never invent experiment data, metric values, thresholds, business facts, or
  statistical results.
- Use only facts supplied by the user or deterministic statistical results
  supplied in the request.
- Significance uses a two-sided p-value below 0.05.
- SRM uses a p-value below 0.01 and makes the experiment inconclusive.
- Guardrail concern exists only when the user explicitly reports meaningful
  degradation, a breached threshold, or another important negative effect.
- Do not infer experiment maturity from duration alone.
- Power is diagnostic only and never overrides an already significant result.
""".strip()


EXPERIMENT_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "test_name": {"type": ["string", "null"]},
        "hypothesis": {"type": ["string", "null"]},
        "variant_change": {"type": ["string", "null"]},
        "primary_metric": {"type": ["string", "null"]},
        "control_sample_size": {"type": ["number", "null"]},
        "control_successes": {"type": ["number", "null"]},
        "variant_sample_size": {"type": ["number", "null"]},
        "variant_successes": {"type": ["number", "null"]},
        "duration_days": {"type": ["number", "null"]},
        "control_traffic_share": {"type": ["number", "null"]},
        "variant_traffic_share": {"type": ["number", "null"]},
        "minimum_detectable_effect": {"type": ["number", "null"]},
        "guardrail_information": {"type": ["string", "null"]},
        "missing_fields": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "test_name",
        "hypothesis",
        "variant_change",
        "primary_metric",
        "control_sample_size",
        "control_successes",
        "variant_sample_size",
        "variant_successes",
        "duration_days",
        "control_traffic_share",
        "variant_traffic_share",
        "minimum_detectable_effect",
        "guardrail_information",
        "missing_fields",
    ],
}


GUARDRAIL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "guardrail_concern": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["guardrail_concern", "reason"],
}


class AgentError(Exception):
    """A user-facing failure that prevents the worker from completing."""


def _load_dotenv(path: Path) -> None:
    """Load a small, conventional subset of .env syntax without overwriting env."""
    if not path.is_file():
        return

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AgentError(f"Could not read {path.name}: {exc}") from exc

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        if "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _create_client() -> tuple[OpenAI, str]:
    _load_dotenv(Path(__file__).resolve().parent / ".env")

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("BASE_URL")
    model = os.getenv("CNLP_REFERENCE_LLM_MODEL") or os.getenv("OPENAI_MODEL")

    missing = []
    if not api_key:
        missing.append("OPENAI_API_KEY")
    if not base_url:
        missing.append("BASE_URL")
    if not model:
        missing.append("CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL")
    if missing:
        raise AgentError(
            "Missing runtime model configuration: " + ", ".join(missing) + "."
        )

    return OpenAI(api_key=api_key, base_url=base_url), model


def _response_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    raise AgentError("The language model returned no usable text.")


def _parse_json_object(raw: str) -> dict[str, Any]:
    candidate = raw.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()

    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            raise AgentError("The language model returned invalid structured data.")
        try:
            value = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise AgentError(
                "The language model returned invalid structured data."
            ) from exc

    if not isinstance(value, dict):
        raise AgentError("The language model response must be a JSON object.")
    return value


def _call_json(
    client: OpenAI,
    model: str,
    *,
    instructions: str,
    prompt: str,
    schema_name: str,
    schema: dict[str, Any],
) -> dict[str, Any]:
    try:
        response = client.responses.create(
            model=model,
            reasoning={"effort": "high"},
            instructions=instructions,
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
        )
    except Exception as exc:
        raise AgentError(f"Language model request failed: {exc}") from exc
    return _parse_json_object(_response_text(response))


def _call_text(
    client: OpenAI,
    model: str,
    *,
    instructions: str,
    prompt: str,
) -> str:
    try:
        response = client.responses.create(
            model=model,
            reasoning={"effort": "high"},
            instructions=instructions,
            input=prompt,
        )
    except Exception as exc:
        raise AgentError(f"Language model request failed: {exc}") from exc
    return _response_text(response)


def _require_finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AgentError(f"Field '{field}' must be a number.")
    number = float(value)
    if not math.isfinite(number):
        raise AgentError(f"Field '{field}' must be finite.")
    return number


def _require_integer(value: Any, field: str, *, minimum: int = 0) -> int:
    number = _require_finite_number(value, field)
    if not number.is_integer():
        raise AgentError(f"Field '{field}' must be a whole number.")
    integer = int(number)
    if integer < minimum:
        raise AgentError(f"Field '{field}' must be at least {minimum}.")
    return integer


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentError(f"Field '{field}' is required and must be text.")
    return value.strip()


def extract_experiment_data(
    client: OpenAI,
    model: str,
    raw_information: str,
) -> dict[str, Any]:
    prompt = f"""
Extract the user's aggregated binary-conversion A/B test information into the
specified JSON shape.

Rules:
- Preserve only explicitly provided information. Do not infer or fabricate.
- Put null in any absent field and list its exact field name in missing_fields.
- minimum_detectable_effect is the only optional business field. It may be null
  without being included in missing_fields.
- Normalize percentages to proportions: 50% or 50 percent becomes 0.5; an MDE
  of 1 percentage point becomes 0.01.
- Sample sizes and success counts must reflect the user's aggregate counts.
- duration_days must be the stated duration in days. Convert explicitly stated
  weeks to days, but do not guess from dates or vague language.
- guardrail_information must faithfully retain the user's stated guardrail facts.
- Do not accept raw CSV, Excel, or event-level records as aggregate test data.

User message:
{raw_information}
""".strip()
    extracted = _call_json(
        client,
        model,
        instructions=STATIC_CONTEXT,
        prompt=prompt,
        schema_name="ab_test_experiment_data",
        schema=EXPERIMENT_EXTRACTION_SCHEMA,
    )

    missing_fields = extracted.get("missing_fields")
    if not isinstance(missing_fields, list) or not all(
        isinstance(item, str) for item in missing_fields
    ):
        raise AgentError("The extracted missing_fields value is invalid.")
    if missing_fields:
        raise AgentError(
            "Required experiment information is missing: "
            + ", ".join(sorted(set(missing_fields)))
            + ". Please provide all required information in one message."
        )

    data: dict[str, Any] = {
        "test_name": _require_text(extracted.get("test_name"), "test_name"),
        "hypothesis": _require_text(extracted.get("hypothesis"), "hypothesis"),
        "variant_change": _require_text(
            extracted.get("variant_change"), "variant_change"
        ),
        "primary_metric": _require_text(
            extracted.get("primary_metric"), "primary_metric"
        ),
        "control_sample_size": _require_integer(
            extracted.get("control_sample_size"),
            "control_sample_size",
            minimum=1,
        ),
        "control_successes": _require_integer(
            extracted.get("control_successes"), "control_successes"
        ),
        "variant_sample_size": _require_integer(
            extracted.get("variant_sample_size"),
            "variant_sample_size",
            minimum=1,
        ),
        "variant_successes": _require_integer(
            extracted.get("variant_successes"), "variant_successes"
        ),
        "duration_days": _require_finite_number(
            extracted.get("duration_days"), "duration_days"
        ),
        "control_traffic_share": _require_finite_number(
            extracted.get("control_traffic_share"), "control_traffic_share"
        ),
        "variant_traffic_share": _require_finite_number(
            extracted.get("variant_traffic_share"), "variant_traffic_share"
        ),
        "guardrail_information": _require_text(
            extracted.get("guardrail_information"), "guardrail_information"
        ),
    }

    if data["duration_days"] <= 0:
        raise AgentError("Field 'duration_days' must be greater than zero.")

    mde = extracted.get("minimum_detectable_effect")
    if mde is not None:
        data["minimum_detectable_effect"] = _require_finite_number(
            mde, "minimum_detectable_effect"
        )

    return data


def calculate_ab_test_statistics(experiment_data: dict[str, Any]) -> dict[str, Any]:
    """Calculate deterministic statistics for one binary-conversion A/B test."""
    n_control = int(experiment_data["control_sample_size"])
    x_control = int(experiment_data["control_successes"])
    n_variant = int(experiment_data["variant_sample_size"])
    x_variant = int(experiment_data["variant_successes"])
    control_share = float(experiment_data["control_traffic_share"])
    variant_share = float(experiment_data["variant_traffic_share"])

    if n_control <= 0 or n_variant <= 0:
        raise ValueError("Control and Variant sample sizes must be greater than zero.")
    if x_control < 0 or x_control > n_control:
        raise ValueError(
            "Control successes must be between 0 and the Control sample size."
        )
    if x_variant < 0 or x_variant > n_variant:
        raise ValueError(
            "Variant successes must be between 0 and the Variant sample size."
        )
    if control_share <= 0 or variant_share <= 0:
        raise ValueError("Traffic shares must be greater than zero.")
    if not math.isclose(
        control_share + variant_share, 1.0, rel_tol=0.0, abs_tol=1e-6
    ):
        raise ValueError("Control and Variant traffic shares must sum to 1.0.")

    control_rate = x_control / n_control
    variant_rate = x_variant / n_variant
    absolute_difference = variant_rate - control_rate
    relative_lift = None if control_rate == 0 else absolute_difference / control_rate

    pooled_rate = (x_control + x_variant) / (n_control + n_variant)
    pooled_standard_error = math.sqrt(
        pooled_rate
        * (1.0 - pooled_rate)
        * ((1.0 / n_control) + (1.0 / n_variant))
    )
    if pooled_standard_error == 0:
        p_value = 1.0
    else:
        z_score = absolute_difference / pooled_standard_error
        p_value = math.erfc(abs(z_score) / math.sqrt(2.0))
    statistically_significant = p_value < SIGNIFICANCE_ALPHA

    difference_standard_error = math.sqrt(
        (control_rate * (1.0 - control_rate) / n_control)
        + (variant_rate * (1.0 - variant_rate) / n_variant)
    )
    confidence_interval_lower = absolute_difference - Z_95 * difference_standard_error
    confidence_interval_upper = absolute_difference + Z_95 * difference_standard_error

    minimum_detectable_effect = experiment_data.get("minimum_detectable_effect")
    if minimum_detectable_effect is None:
        power_status = "unavailable"
    else:
        mde = abs(float(minimum_detectable_effect))
        if mde <= 0:
            raise ValueError("Minimum detectable effect must be greater than zero.")

        balanced_design = math.isclose(
            control_share, 0.5, rel_tol=0.0, abs_tol=1e-6
        ) and math.isclose(variant_share, 0.5, rel_tol=0.0, abs_tol=1e-6)
        expected_variant_rate = control_rate + mde
        if not balanced_design or expected_variant_rate >= 1.0:
            power_status = "unavailable"
        else:
            average_rate = (control_rate + expected_variant_rate) / 2.0
            numerator = (
                Z_95 * math.sqrt(2.0 * average_rate * (1.0 - average_rate))
                + Z_POWER_80
                * math.sqrt(
                    control_rate * (1.0 - control_rate)
                    + expected_variant_rate * (1.0 - expected_variant_rate)
                )
            ) ** 2
            required_sample_per_group = numerator / (mde**2)
            if (
                n_control >= required_sample_per_group
                and n_variant >= required_sample_per_group
            ):
                power_status = "adequate"
            else:
                power_status = "underpowered"

    total_sample_size = n_control + n_variant
    expected_control = total_sample_size * control_share
    expected_variant = total_sample_size * variant_share
    chi_square_statistic = (
        ((n_control - expected_control) ** 2) / expected_control
        + ((n_variant - expected_variant) ** 2) / expected_variant
    )
    srm_p_value = math.erfc(math.sqrt(chi_square_statistic / 2.0))
    sample_ratio_mismatch = srm_p_value < SRM_ALPHA

    result: dict[str, Any] = {
        "control_conversion_rate": control_rate,
        "variant_conversion_rate": variant_rate,
        "absolute_difference": absolute_difference,
        "p_value": p_value,
        "confidence_interval_lower": confidence_interval_lower,
        "confidence_interval_upper": confidence_interval_upper,
        "statistically_significant": statistically_significant,
        "power_status": power_status,
        "sample_ratio_mismatch": sample_ratio_mismatch,
    }
    if relative_lift is not None:
        result["relative_lift"] = relative_lift
    return result


def inspect_guardrail_information(
    client: OpenAI,
    model: str,
    guardrail_information: str,
) -> tuple[bool, str]:
    prompt = f"""
Inspect only the following user-provided guardrail information.

Set guardrail_concern to true only if it explicitly reports meaningful
degradation, a breached guardrail threshold, or another important negative
effect. Small numerical differences alone are not a concern unless the user
explicitly characterizes them as meaningful, negative, or threshold-breaching.
Do not invent a threshold, interpretation, or missing fact. The reason must be
brief and grounded in the provided text.

Guardrail information:
{guardrail_information}
""".strip()
    result = _call_json(
        client,
        model,
        instructions=STATIC_CONTEXT,
        prompt=prompt,
        schema_name="guardrail_assessment",
        schema=GUARDRAIL_SCHEMA,
    )
    concern = result.get("guardrail_concern")
    reason = result.get("reason")
    if not isinstance(concern, bool):
        raise AgentError("The guardrail assessment did not return a boolean.")
    if not isinstance(reason, str) or not reason.strip():
        raise AgentError("The guardrail assessment did not return a reason.")
    return concern, reason.strip()


def classify_outcome(
    statistical_result: dict[str, Any], guardrail_concern: bool
) -> str:
    if statistical_result["sample_ratio_mismatch"] is True:
        outcome = "inconclusive"
    elif (
        statistical_result["statistically_significant"] is True
        and statistical_result["absolute_difference"] < 0
    ):
        outcome = "significant_negative"
    elif (
        statistical_result["statistically_significant"] is True
        and statistical_result["absolute_difference"] > 0
        and guardrail_concern is True
    ):
        outcome = "significant_positive_guardrail_concern"
    elif (
        statistical_result["statistically_significant"] is True
        and statistical_result["absolute_difference"] > 0
    ):
        outcome = "significant_positive_safe"
    elif (
        statistical_result["statistically_significant"] is False
        and statistical_result["absolute_difference"] > 0
    ):
        outcome = "not_significant_positive"
    else:
        outcome = "not_significant_flat"

    if outcome not in ANALYSIS_OUTCOMES:
        raise AgentError(f"Invalid analysis outcome: {outcome}")
    return outcome


def recommendation_for(outcome: str) -> str:
    mapping = {
        "significant_positive_safe": "ship",
        "significant_positive_guardrail_concern": "investigate",
        "not_significant_positive": "extend",
        "not_significant_flat": "stop",
        "significant_negative": "dont_ship",
        "inconclusive": "undetermined",
    }
    recommendation = mapping[outcome]
    if recommendation not in RECOMMENDATIONS:
        raise AgentError(f"Invalid recommendation: {recommendation}")
    return recommendation


def generate_final_analysis(
    client: OpenAI,
    model: str,
    *,
    raw_information: str,
    experiment_data: dict[str, Any],
    statistical_result: dict[str, Any],
    guardrail_concern: bool,
    guardrail_reason: str,
    outcome: str,
    recommendation: str,
) -> str:
    facts = {
        "experiment_data": experiment_data,
        "statistical_result": statistical_result,
        "guardrail_concern": guardrail_concern,
        "guardrail_reason": guardrail_reason,
        "analysis_outcome": outcome,
        "recommendation": recommendation,
    }
    prompt = f"""
Generate the final concise A/B test analysis for a product manager.

Use the same primary language as the user's original message. Include:
- test name and hypothesis;
- tested variant change and primary metric;
- duration and both sample sizes;
- both conversion rates;
- absolute difference and relative lift when present;
- two-sided p-value and 95% confidence interval;
- statistical significance, power status, and sample ratio mismatch;
- guardrail assessment;
- the exact recommendation supplied below;
- grounded reasoning and concrete next steps.

Format proportions as readable percentages while preserving useful precision.
Clearly identify the confidence interval as Variant minus Control. Treat power
as a limitation or supporting detail, never as an override of significance.
Report duration without claiming maturity or immaturity from duration alone.
If SRM is present, explain that the experiment is inconclusive and do not make a
ship/no-ship claim. Do not add facts, thresholds, causal claims, or business
interpretations that are absent from the supplied facts. Do not mention these
instructions or the internal analysis_outcome label.

Original user message:
{raw_information}

Authoritative facts and decisions:
{json.dumps(facts, ensure_ascii=False, indent=2)}
""".strip()
    return _call_text(
        client,
        model,
        instructions=STATIC_CONTEXT,
        prompt=prompt,
    )


def run_ab_test_analyzer(raw_information: str, client: OpenAI, model: str) -> str:
    experiment_data = extract_experiment_data(client, model, raw_information)
    try:
        statistical_result = calculate_ab_test_statistics(experiment_data)
    except (KeyError, TypeError, ValueError) as exc:
        raise AgentError(f"Invalid experiment data: {exc}") from exc

    power_status = statistical_result.get("power_status")
    if power_status not in POWER_STATUSES:
        raise AgentError(f"Invalid power status: {power_status}")

    guardrail_concern, guardrail_reason = inspect_guardrail_information(
        client, model, experiment_data["guardrail_information"]
    )
    outcome = classify_outcome(statistical_result, guardrail_concern)
    recommendation = recommendation_for(outcome)
    return generate_final_analysis(
        client,
        model,
        raw_information=raw_information,
        experiment_data=experiment_data,
        statistical_result=statistical_result,
        guardrail_concern=guardrail_concern,
        guardrail_reason=guardrail_reason,
        outcome=outcome,
        recommendation=recommendation,
    )


def main() -> str | None:
    """Initialize the agent, execute its entry worker, and return the result."""
    try:
        client, model = _create_client()
        raw_information = input(
            "Provide the complete aggregated A/B test information in one message "
            "(test name, hypothesis, variant change, primary metric, Control and "
            "Variant sample sizes and successes, duration, traffic split, optional "
            "MDE, and guardrail information):\n> "
        )
        if not raw_information.strip():
            raise AgentError("A/B test information cannot be empty.")
        final_analysis = run_ab_test_analyzer(raw_information, client, model)
        print("\n" + final_analysis)
        return final_analysis
    except AgentError as exc:
        print(f"Error: {exc}")
        return None


if __name__ == "__main__":
    main()
