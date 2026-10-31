from __future__ import annotations

import json
import math
import os
from typing import Any

from openai import OpenAI


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


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries without requiring an extra dependency."""
    dotenv_path = os.path.join(os.getcwd(), ".env")
    if not os.path.isfile(dotenv_path):
        return
    with open(dotenv_path, "r", encoding="utf-8") as dotenv_file:
        for raw_line in dotenv_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key, value)


def _configuration() -> tuple[str, str | None, str]:
    _load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("BASE_URL")
    model = os.environ.get("CNLP_REFERENCE_LLM_MODEL") or os.environ.get(
        "OPENAI_MODEL"
    )
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured in the environment or .env."
        )
    if not model:
        raise RuntimeError(
            "CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL must be configured "
            "in the environment or .env."
        )
    return api_key, base_url, model


def _json_from_response(response: Any) -> Any:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return json.loads(output_text)

    # This fallback supports clients or test doubles that expose only output
    # content items while keeping the production path on the Responses API.
    chunks: list[str] = []
    for output_item in getattr(response, "output", []) or []:
        for content in getattr(output_item, "content", []) or []:
            text_value = getattr(content, "text", None)
            if isinstance(text_value, str):
                chunks.append(text_value)
            elif isinstance(text_value, dict) and isinstance(
                text_value.get("value"), str
            ):
                chunks.append(text_value["value"])
    if not chunks:
        raise ValueError("The language model returned no usable JSON content.")
    return json.loads("".join(chunks))


def _call_json_model(
    client: OpenAI,
    model: str,
    instructions: str,
    user_content: str,
) -> dict[str, Any]:
    response = client.responses.create(
        model=model,
        reasoning={"effort": "high"},
        instructions=instructions,
        input=user_content,
        text={"format": {"type": "json_object"}},
    )
    parsed = _json_from_response(response)
    if not isinstance(parsed, dict):
        raise ValueError("The language model response must be a JSON object.")
    return parsed


def _extract_experiment_data(
    client: OpenAI, model: str, raw_information: str
) -> dict[str, Any]:
    instructions = """
You are the data extraction component of ABTestAnalyzer. Extract only facts
explicitly stated in the user's A/B test description. Return one JSON object
with exactly these fields:
test_name, hypothesis, variant_change, primary_metric,
control_sample_size, control_successes, variant_sample_size,
variant_successes, duration_days, control_traffic_share,
variant_traffic_share, minimum_detectable_effect, guardrail_information.
The first five named text fields and guardrail_information must be strings.
The sample, duration, and traffic fields must be numbers. The optional
minimum_detectable_effect must be a number or null. Convert percentages to
proportions for traffic shares and MDE: 50 percent is 0.5 and 1 percentage
point is 0.01. A relative MDE stated as a percent should be converted to a
proportion only when the user clearly means a relative proportion; preserve
the explicit meaning in guardrail_information or the closest available text.
Do not calculate conversion rates or fill missing facts. If a required fact
is missing or ambiguous, use null so the caller can ask for a complete input
without inventing data. For guardrail_information, preserve the user's
meaning and wording rather than interpreting whether it is a concern.
""".strip()
    data = _call_json_model(client, model, instructions, raw_information)
    required_text = [
        "test_name",
        "hypothesis",
        "variant_change",
        "primary_metric",
        "guardrail_information",
    ]
    required_numbers = [
        "control_sample_size",
        "control_successes",
        "variant_sample_size",
        "variant_successes",
        "duration_days",
        "control_traffic_share",
        "variant_traffic_share",
    ]
    missing = [
        field
        for field in required_text + required_numbers
        if data.get(field) is None
    ]
    if missing:
        raise ValueError(
            "The model could not extract required experiment fields: "
            + ", ".join(missing)
            + ". Please provide all requested fields in one message."
        )

    normalized: dict[str, Any] = {}
    for field in required_text:
        if not isinstance(data[field], str):
            raise ValueError(f"Extracted field {field} must be text.")
        normalized[field] = data[field]
    for field in required_numbers:
        value = data[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Extracted field {field} must be a number.")
        if not math.isfinite(float(value)):
            raise ValueError(f"Extracted field {field} must be finite.")
        normalized[field] = value

    mde = data.get("minimum_detectable_effect")
    if mde is not None:
        if isinstance(mde, bool) or not isinstance(mde, (int, float)):
            raise ValueError("Extracted minimum_detectable_effect must be a number.")
        if not math.isfinite(float(mde)):
            raise ValueError("Extracted minimum_detectable_effect must be finite.")
        normalized["minimum_detectable_effect"] = mde
    return normalized


def calculate_ab_test_statistics(experiment_data: dict[str, Any]) -> dict[str, Any]:
    """Calculate deterministic statistics for one binary-conversion test."""
    significance_alpha = 0.05
    srm_alpha = 0.01
    z_95 = 1.959963984540054
    z_power_80 = 0.8416212335729143

    n_control = int(experiment_data["control_sample_size"])
    x_control = int(experiment_data["control_successes"])
    n_variant = int(experiment_data["variant_sample_size"])
    x_variant = int(experiment_data["variant_successes"])
    control_share = float(experiment_data["control_traffic_share"])
    variant_share = float(experiment_data["variant_traffic_share"])

    if n_control <= 0 or n_variant <= 0:
        raise ValueError("Control and Variant sample sizes must be greater than zero.")
    if x_control < 0 or x_control > n_control:
        raise ValueError("Control successes must be between 0 and the Control sample size.")
    if x_variant < 0 or x_variant > n_variant:
        raise ValueError("Variant successes must be between 0 and the Variant sample size.")
    if control_share <= 0 or variant_share <= 0:
        raise ValueError("Traffic shares must be greater than zero.")
    if not math.isclose(control_share + variant_share, 1.0, rel_tol=0.0, abs_tol=1e-6):
        raise ValueError("Control and Variant traffic shares must sum to 1.0.")

    control_rate = x_control / n_control
    variant_rate = x_variant / n_variant
    absolute_difference = variant_rate - control_rate
    relative_lift = None if control_rate == 0 else absolute_difference / control_rate

    pooled_rate = (x_control + x_variant) / (n_control + n_variant)
    pooled_se = math.sqrt(
        pooled_rate * (1.0 - pooled_rate) * ((1.0 / n_control) + (1.0 / n_variant))
    )
    if pooled_se == 0:
        p_value = 1.0
    else:
        z_score = absolute_difference / pooled_se
        p_value = math.erfc(abs(z_score) / math.sqrt(2.0))
    statistically_significant = p_value < significance_alpha

    difference_se = math.sqrt(
        control_rate * (1.0 - control_rate) / n_control
        + variant_rate * (1.0 - variant_rate) / n_variant
    )
    confidence_interval_lower = absolute_difference - z_95 * difference_se
    confidence_interval_upper = absolute_difference + z_95 * difference_se

    mde = experiment_data.get("minimum_detectable_effect")
    if mde is None:
        power_status = "unavailable"
    else:
        mde = abs(float(mde))
        if mde <= 0:
            raise ValueError("Minimum detectable effect must be greater than zero.")
        balanced_design = math.isclose(control_share, 0.5, abs_tol=1e-6) and math.isclose(
            variant_share, 0.5, abs_tol=1e-6
        )
        expected_variant_rate = control_rate + mde
        if not balanced_design or expected_variant_rate >= 1.0:
            power_status = "unavailable"
        else:
            average_rate = (control_rate + expected_variant_rate) / 2.0
            numerator = (
                z_95 * math.sqrt(2.0 * average_rate * (1.0 - average_rate))
                + z_power_80
                * math.sqrt(
                    control_rate * (1.0 - control_rate)
                    + expected_variant_rate * (1.0 - expected_variant_rate)
                )
            ) ** 2
            required_sample_per_group = numerator / (mde**2)
            power_status = (
                "adequate"
                if n_control >= required_sample_per_group
                and n_variant >= required_sample_per_group
                else "underpowered"
            )

    total_sample_size = n_control + n_variant
    expected_control = total_sample_size * control_share
    expected_variant = total_sample_size * variant_share
    chi_square = (
        ((n_control - expected_control) ** 2) / expected_control
        + ((n_variant - expected_variant) ** 2) / expected_variant
    )
    srm_p_value = math.erfc(math.sqrt(chi_square / 2.0))
    sample_ratio_mismatch = srm_p_value < srm_alpha

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


def _assess_guardrail(
    client: OpenAI, model: str, guardrail_information: str
) -> bool:
    instructions = """
You assess guardrail information for ABTestAnalyzer. Return JSON exactly as
{"guardrail_concern": true} or {"guardrail_concern": false}. Set it true
only if the provided text explicitly reports meaningful degradation, a
breached guardrail threshold, or another important negative effect of the
variant. Set it false when no such concern is explicitly reported, including
when information is absent, neutral, vague, or describes only a small
difference without a stated threshold or meaningful negative effect. Do not
infer a concern from numbers alone and do not invent a threshold.
""".strip()
    result = _call_json_model(client, model, instructions, guardrail_information)
    value = result.get("guardrail_concern")
    if not isinstance(value, bool):
        raise ValueError("The language model returned an invalid guardrail assessment.")
    return value


def _classify(statistical_result: dict[str, Any], guardrail_concern: bool) -> str:
    if statistical_result["sample_ratio_mismatch"]:
        return "inconclusive"
    if (
        statistical_result["statistically_significant"]
        and statistical_result["absolute_difference"] < 0
    ):
        return "significant_negative"
    if (
        statistical_result["statistically_significant"]
        and statistical_result["absolute_difference"] > 0
        and guardrail_concern
    ):
        return "significant_positive_guardrail_concern"
    if (
        statistical_result["statistically_significant"]
        and statistical_result["absolute_difference"] > 0
    ):
        return "significant_positive_safe"
    if (
        not statistical_result["statistically_significant"]
        and statistical_result["absolute_difference"] > 0
    ):
        return "not_significant_positive"
    return "not_significant_flat"


def _recommendation(outcome: str) -> str:
    return {
        "significant_positive_safe": "ship",
        "significant_positive_guardrail_concern": "investigate",
        "not_significant_positive": "extend",
        "not_significant_flat": "stop",
        "significant_negative": "dont_ship",
        "inconclusive": "undetermined",
    }[outcome]


def _generate_final_analysis(
    client: OpenAI,
    model: str,
    experiment_data: dict[str, Any],
    statistical_result: dict[str, Any],
    guardrail_concern: bool,
    recommendation: str,
) -> str:
    instructions = """
You are ABTestAnalysisAssistant. Write a concise but complete A/B test
analysis for product managers. Use only facts in the supplied JSON. Do not
invent experimental data, metric values, statistical results, thresholds, or
business facts. Include the hypothesis, duration, sample sizes, conversion
rates, absolute difference, relative lift when present, p-value, 95% confidence
interval, statistical significance, power status, sample ratio mismatch,
guardrail assessment, recommendation, reasoning, and next steps. Explain
power status as diagnostic support or a limitation; it must not override
statistical significance. Make the recommendation exactly consistent with the
provided recommendation value. Clearly state when a value is unavailable.
Return plain text only, with compact headings or paragraphs and no JSON.
""".strip()
    payload = json.dumps(
        {
            "experiment_data": experiment_data,
            "statistical_result": statistical_result,
            "guardrail_concern": guardrail_concern,
            "recommendation": recommendation,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    response = client.responses.create(
        model=model,
        reasoning={"effort": "high"},
        instructions=instructions,
        input=payload,
    )
    output_text = getattr(response, "output_text", None)
    if not isinstance(output_text, str) or not output_text.strip():
        raise ValueError("The language model returned an empty final analysis.")
    return output_text.strip()


class ABTestAnalyzer:
    def __init__(self) -> None:
        api_key, base_url, model = _configuration()
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)
        self.model = model

    def run(self) -> str:
        print(
            "Please provide the complete A/B test information in one message, "
            "including test name, hypothesis, tested change, primary metric, "
            "Control and Variant sample sizes and successes, duration, traffic "
            "split, optional minimum detectable effect, and guardrail information."
        )
        raw_information = input()
        experiment_data = _extract_experiment_data(
            self.client, self.model, raw_information
        )
        statistical_result = calculate_ab_test_statistics(experiment_data)
        guardrail_concern = _assess_guardrail(
            self.client, self.model, experiment_data["guardrail_information"]
        )
        analysis_outcome = _classify(statistical_result, guardrail_concern)
        if analysis_outcome not in ANALYSIS_OUTCOMES:
            raise ValueError("Internal error: invalid analysis outcome.")
        recommendation = _recommendation(analysis_outcome)
        if recommendation not in RECOMMENDATIONS:
            raise ValueError("Internal error: invalid recommendation.")
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
    """Initialize ABTestAnalyzer, execute the required interaction, and return its result."""
    return ABTestAnalyzer().run()


if __name__ == "__main__":
    main()
