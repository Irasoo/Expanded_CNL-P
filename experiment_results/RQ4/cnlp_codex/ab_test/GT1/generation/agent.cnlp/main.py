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


def _load_local_env() -> None:
    """Load simple KEY=VALUE entries from the current directory's .env."""
    env_path = Path.cwd() / ".env"
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def _runtime_configuration() -> tuple[str, str, str]:
    _load_local_env()
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("BASE_URL")
    model = (
        os.environ.get("CNLP_REFERENCE_LLM_MODEL")
        or os.environ.get("OPENAI_MODEL")
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
            "Missing runtime model configuration: " + ", ".join(missing)
        )
    return api_key, base_url, model


def _json_schema_response(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    schema_name: str,
    schema: dict[str, Any],
) -> dict[str, Any]:
    response = client.responses.create(
        model=model,
        reasoning={"effort": "high"},
        input=[
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
    )
    output = response.output_text
    if not output or not output.strip():
        raise RuntimeError("The language model returned an empty structured result.")
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The language model returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("The language model returned a non-object result.")
    return parsed


def _text_response(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    response = client.responses.create(
        model=model,
        reasoning={"effort": "high"},
        input=[
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            },
        ],
    )
    output = response.output_text
    if not output or not output.strip():
        raise RuntimeError("The language model returned an empty analysis.")
    return output.strip()


EXPERIMENT_DATA_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "test_name": {"type": "string"},
        "hypothesis": {"type": "string"},
        "variant_change": {"type": "string"},
        "primary_metric": {"type": "string"},
        "control_sample_size": {"type": "number"},
        "control_successes": {"type": "number"},
        "variant_sample_size": {"type": "number"},
        "variant_successes": {"type": "number"},
        "duration_days": {"type": "number"},
        "control_traffic_share": {"type": "number"},
        "variant_traffic_share": {"type": "number"},
        "minimum_detectable_effect": {"type": ["number", "null"]},
        "guardrail_information": {"type": "string"},
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
    ],
}

GUARDRAIL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"guardrail_concern": {"type": "boolean"}},
    "required": ["guardrail_concern"],
}


def _extract_experiment_data(
    client: OpenAI, model: str, raw_information: str
) -> dict[str, Any]:
    system_prompt = """You extract aggregated binary-conversion A/B test data.

You are operating as an A/B test analysis assistant for product managers. Preserve
only facts explicitly present in the user's message. Never infer, invent, or fill
missing experiment facts. The input scope is aggregated counts and metadata, not
raw CSV, Excel, or event-level records.

Return the exact fields in the JSON schema. Traffic allocation must be a numerical
proportion between 0 and 1: normalize percentages and ratios such as 50/50. A
minimum detectable effect must also be a numerical proportion; one percentage point
is 0.01. Interpret the MDE according to the units stated by the user and do not
silently invent one. If the user did not provide an MDE, return null. Keep the
guardrail information as a faithful concise description, including an explicit
statement that none was reported when that is what the user said. Required missing
facts must remain empty strings or null as allowed by the schema so validation can
report the omission; do not manufacture values.

The primary metric is a binary conversion rate: successes divided by sample size,
where higher is better. Sample sizes and success counts must be numeric counts.
"""
    user_prompt = (
        "Extract the experiment data from this single user message. Do not ask a "
        "follow-up question and do not add facts:\n\n" + raw_information
    )
    return _json_schema_response(
        client,
        model,
        system_prompt,
        user_prompt,
        "ab_test_experiment_data",
        EXPERIMENT_DATA_SCHEMA,
    )


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _normalize_and_validate_experiment_data(
    data: dict[str, Any]
) -> dict[str, Any]:
    required_text = (
        "test_name",
        "hypothesis",
        "variant_change",
        "primary_metric",
        "guardrail_information",
    )
    for field in required_text:
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError(
                f"Required experiment information is missing: {field}."
            )

    count_fields = (
        "control_sample_size",
        "control_successes",
        "variant_sample_size",
        "variant_successes",
    )
    for field in count_fields:
        value = data.get(field)
        if not _is_number(value) or not math.isfinite(float(value)):
            raise ValueError(f"{field} must be a finite numeric count.")
        if int(value) != value:
            raise ValueError(f"{field} must be a whole-number count.")
        data[field] = int(value)

    duration = data.get("duration_days")
    if not _is_number(duration) or not math.isfinite(float(duration)):
        raise ValueError("duration_days must be a finite number.")
    if float(duration) < 0:
        raise ValueError("duration_days must not be negative.")
    data["duration_days"] = float(duration)

    for field in ("control_traffic_share", "variant_traffic_share"):
        value = data.get(field)
        if not _is_number(value) or not math.isfinite(float(value)):
            raise ValueError(f"{field} must be a finite numerical proportion.")
        if not 0 < float(value) < 1:
            raise ValueError(f"{field} must be greater than 0 and less than 1.")
        data[field] = float(value)

    mde = data.get("minimum_detectable_effect")
    if mde is not None:
        if not _is_number(mde) or not math.isfinite(float(mde)):
            raise ValueError("minimum_detectable_effect must be numeric when provided.")
        data["minimum_detectable_effect"] = float(mde)

    if not math.isclose(
        data["control_traffic_share"] + data["variant_traffic_share"],
        1.0,
        rel_tol=0.0,
        abs_tol=1e-6,
    ):
        raise ValueError("Control and Variant traffic shares must sum to 1.0.")
    if data["control_sample_size"] <= 0 or data["variant_sample_size"] <= 0:
        raise ValueError("Control and Variant sample sizes must be greater than zero.")
    if not 0 <= data["control_successes"] <= data["control_sample_size"]:
        raise ValueError(
            "Control successes must be between 0 and the Control sample size."
        )
    if not 0 <= data["variant_successes"] <= data["variant_sample_size"]:
        raise ValueError(
            "Variant successes must be between 0 and the Variant sample size."
        )
    return data


def calculate_ab_test_statistics(experiment_data: dict[str, Any]) -> dict[str, Any]:
    """Calculate deterministic binary-conversion A/B test statistics."""
    n_control = int(experiment_data["control_sample_size"])
    x_control = int(experiment_data["control_successes"])
    n_variant = int(experiment_data["variant_sample_size"])
    x_variant = int(experiment_data["variant_successes"])
    control_share = float(experiment_data["control_traffic_share"])
    variant_share = float(experiment_data["variant_traffic_share"])

    control_rate = x_control / n_control
    variant_rate = x_variant / n_variant
    absolute_difference = variant_rate - control_rate
    relative_lift = (
        None
        if control_rate == 0
        else absolute_difference / control_rate
    )

    pooled_rate = (x_control + x_variant) / (n_control + n_variant)
    pooled_standard_error = math.sqrt(
        pooled_rate * (1.0 - pooled_rate)
        * ((1.0 / n_control) + (1.0 / n_variant))
    )
    if pooled_standard_error == 0:
        p_value = 1.0
    else:
        z_score = absolute_difference / pooled_standard_error
        p_value = math.erfc(abs(z_score) / math.sqrt(2.0))
    statistically_significant = p_value < SIGNIFICANCE_ALPHA

    difference_standard_error = math.sqrt(
        control_rate * (1.0 - control_rate) / n_control
        + variant_rate * (1.0 - variant_rate) / n_variant
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
        balanced_design = (
            math.isclose(control_share, 0.5, rel_tol=0.0, abs_tol=1e-6)
            and math.isclose(variant_share, 0.5, rel_tol=0.0, abs_tol=1e-6)
        )
        expected_variant_rate = control_rate + mde
        if not balanced_design or expected_variant_rate >= 1.0:
            power_status = "unavailable"
        else:
            average_rate = (control_rate + expected_variant_rate) / 2.0
            numerator = (
                Z_95 * math.sqrt(2.0 * average_rate * (1.0 - average_rate))
                + Z_POWER_80 * math.sqrt(
                    control_rate * (1.0 - control_rate)
                    + expected_variant_rate * (1.0 - expected_variant_rate)
                )
            ) ** 2
            required_sample_per_group = numerator / (mde ** 2)
            power_status = (
                "adequate"
                if (
                    n_control >= required_sample_per_group
                    and n_variant >= required_sample_per_group
                )
                else "underpowered"
            )

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


def _classify_guardrail(
    client: OpenAI, model: str, guardrail_information: str
) -> bool:
    system_prompt = """Determine whether the user's explicitly provided guardrail
information indicates a meaningful negative effect for an A/B test. Return true
only for an explicitly reported meaningful degradation, breached guardrail
threshold, or another important negative effect. Return false when no concern is
reported, when the information is neutral, or when a small numerical difference is
not explicitly characterized as meaningful. Do not invent thresholds, context, or
business facts. This is semantic interpretation, not keyword matching.
"""
    result = _json_schema_response(
        client,
        model,
        system_prompt,
        "Assess this guardrail information exactly as written:\n\n"
        + guardrail_information,
        "guardrail_assessment",
        GUARDRAIL_SCHEMA,
    )
    value = result.get("guardrail_concern")
    if not isinstance(value, bool):
        raise RuntimeError("The guardrail assessment was not a boolean.")
    return value


def _classify_outcome(statistics: dict[str, Any], guardrail_concern: bool) -> str:
    if statistics["sample_ratio_mismatch"]:
        return "inconclusive"
    if statistics["statistically_significant"] and statistics["absolute_difference"] < 0:
        return "significant_negative"
    if (
        statistics["statistically_significant"]
        and statistics["absolute_difference"] > 0
        and guardrail_concern
    ):
        return "significant_positive_guardrail_concern"
    if (
        statistics["statistically_significant"]
        and statistics["absolute_difference"] > 0
    ):
        return "significant_positive_safe"
    if (
        not statistics["statistically_significant"]
        and statistics["absolute_difference"] > 0
    ):
        return "not_significant_positive"
    return "not_significant_flat"


def _recommendation_for(outcome: str) -> str:
    recommendations = {
        "significant_positive_safe": "ship",
        "significant_positive_guardrail_concern": "investigate",
        "not_significant_positive": "extend",
        "not_significant_flat": "stop",
        "significant_negative": "dont_ship",
        "inconclusive": "undetermined",
    }
    return recommendations[outcome]


def _generate_final_analysis(
    client: OpenAI,
    model: str,
    experiment_data: dict[str, Any],
    statistical_result: dict[str, Any],
    guardrail_concern: bool,
    recommendation: str,
) -> str:
    system_prompt = """You are an A/B test analysis assistant for product managers.
Your role is to translate validated statistical results into a concise, clear
product decision. Use only facts in the supplied experiment data and statistical
result. Do not invent business context, thresholds, maturity claims, or missing
values. The primary metric is a binary conversion rate, with higher being better.
Explain technical results in plain language while preserving their meaning.

The statistical calculation is authoritative: its rates, lift, p-value, confidence
interval, significance, power status, and SRM result must not be recalculated or
changed. Statistical significance means two-sided p-value < 0.05. SRM is present
when its underlying test meets the 0.01 rule, as represented by the supplied boolean.
Power status is diagnostic only and must not override significance. Guardrail concern
is true only when explicitly reported by the user. The supplied recommendation is
authoritative and must be stated clearly.

Produce a concise report with these labeled sections: Experiment, Statistical
findings, Validity and guardrails, Recommendation, Reasoning, and Next steps.
Include the hypothesis, duration, sample sizes, conversion rates, absolute
difference, relative lift when present, p-value, confidence interval, statistical
significance, power status, sample ratio mismatch, guardrail assessment,
recommendation, reasoning, and next steps. Use percentages where that improves
readability, but make the units clear. For an unavailable relative lift, say it is
unavailable rather than fabricating one.
"""
    payload = json.dumps(
        {
            "experiment_data": experiment_data,
            "statistical_result": statistical_result,
            "guardrail_concern": guardrail_concern,
            "recommendation": recommendation,
        },
        ensure_ascii=False,
        indent=2,
    )
    return _text_response(
        client,
        model,
        system_prompt,
        "Generate the final analysis from this authoritative data:\n\n" + payload,
    )


class ABTestAnalyzer:
    def __init__(self) -> None:
        api_key, base_url, model = _runtime_configuration()
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def run(self) -> str:
        raw_ab_test_information = input(
            "Provide the complete aggregated A/B test information in one message, "
            "including test name, hypothesis, tested change, primary metric, "
            "Control and Variant sample sizes and successes, duration, traffic "
            "split, optional MDE, and guardrail information:\n> "
        )
        if not raw_ab_test_information.strip():
            raise ValueError("A/B test information cannot be empty.")

        experiment_data = _normalize_and_validate_experiment_data(
            _extract_experiment_data(self.client, self.model, raw_ab_test_information)
        )
        statistical_result = calculate_ab_test_statistics(experiment_data)
        guardrail_concern = _classify_guardrail(
            self.client,
            self.model,
            experiment_data["guardrail_information"],
        )
        analysis_outcome = _classify_outcome(
            statistical_result,
            guardrail_concern,
        )
        recommendation = _recommendation_for(analysis_outcome)
        final_analysis = _generate_final_analysis(
            self.client,
            self.model,
            experiment_data,
            statistical_result,
            guardrail_concern,
            recommendation,
        )
        print(final_analysis)
        return final_analysis


def main() -> str:
    """Initialize the agent, execute its entry Worker, and return its result."""
    try:
        return ABTestAnalyzer().run()
    except (EOFError, KeyboardInterrupt):
        message = "Input was interrupted before the A/B test analysis completed."
        print(message)
        return message
    except Exception as exc:
        message = f"Unable to complete the A/B test analysis: {exc}"
        print(message)
        return message


if __name__ == "__main__":
    main()
