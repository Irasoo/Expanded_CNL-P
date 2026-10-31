from __future__ import annotations

import json
import math
import os
from typing import Any


def _load_env_file() -> None:
    """Load simple KEY=VALUE entries from the local .env, without overwriting env."""
    path = os.path.join(os.getcwd(), ".env")
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value


def _model_settings() -> tuple[str, str]:
    _load_env_file()
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
        raise RuntimeError("Missing runtime model configuration: " + ", ".join(missing))
    return api_key, model


def _client() -> tuple[Any, str]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The official OpenAI Python Client is required: pip install openai") from exc
    api_key, model = _model_settings()
    return OpenAI(api_key=api_key, base_url=os.environ["BASE_URL"]), model


def _json_model_call(instruction: str) -> dict[str, Any]:
    client, model = _client()
    response = client.responses.create(
        model=model,
        reasoning={"effort": "high"},
        input=instruction,
        text={"format": {"type": "json_object"}},
    )
    text = getattr(response, "output_text", None)
    if not text:
        raise RuntimeError("The language model returned no structured output.")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The language model returned invalid JSON.") from exc
    if not isinstance(value, dict):
        raise RuntimeError("The language model returned an unexpected JSON value.")
    return value


def _text_model_call(instruction: str) -> str:
    client, model = _client()
    response = client.responses.create(
        model=model,
        reasoning={"effort": "high"},
        input=instruction,
    )
    text = getattr(response, "output_text", None)
    if not text or not text.strip():
        raise RuntimeError("The language model returned no final analysis.")
    return text.strip()


def calculate_ab_test_statistics(experiment_data: dict[str, Any]) -> dict[str, Any]:
    """Reference deterministic calculations for an aggregated binary A/B test."""
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
    pooled_se = math.sqrt(pooled_rate * (1.0 - pooled_rate) * ((1.0 / n_control) + (1.0 / n_variant)))
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
        balanced = math.isclose(control_share, 0.5, abs_tol=1e-6) and math.isclose(variant_share, 0.5, abs_tol=1e-6)
        expected_variant_rate = control_rate + mde
        if not balanced or expected_variant_rate >= 1.0:
            power_status = "unavailable"
        else:
            average_rate = (control_rate + expected_variant_rate) / 2.0
            numerator = (
                z_95 * math.sqrt(2.0 * average_rate * (1.0 - average_rate))
                + z_power_80 * math.sqrt(
                    control_rate * (1.0 - control_rate)
                    + expected_variant_rate * (1.0 - expected_variant_rate)
                )
            ) ** 2
            required = numerator / (mde ** 2)
            power_status = "adequate" if n_control >= required and n_variant >= required else "underpowered"

    total = n_control + n_variant
    expected_control = total * control_share
    expected_variant = total * variant_share
    chi_square = ((n_control - expected_control) ** 2) / expected_control + ((n_variant - expected_variant) ** 2) / expected_variant
    srm_p_value = math.erfc(math.sqrt(chi_square / 2.0))
    result: dict[str, Any] = {
        "control_conversion_rate": control_rate,
        "variant_conversion_rate": variant_rate,
        "absolute_difference": absolute_difference,
        "p_value": p_value,
        "confidence_interval_lower": confidence_interval_lower,
        "confidence_interval_upper": confidence_interval_upper,
        "statistically_significant": statistically_significant,
        "power_status": power_status,
        "sample_ratio_mismatch": srm_p_value < srm_alpha,
    }
    if relative_lift is not None:
        result["relative_lift"] = relative_lift
    return result


def _extract_experiment(raw: str) -> dict[str, Any]:
    prompt = f"""You are the data extraction component of ABTestAnalysisAssistant.
Extract only facts explicitly present in the user's A/B test description below. Return JSON only.
Required text fields: test_name, hypothesis, variant_change, primary_metric, guardrail_information.
Required numeric fields: control_sample_size, control_successes, variant_sample_size, variant_successes,
duration_days, control_traffic_share, variant_traffic_share. Optional numeric field:
minimum_detectable_effect.
Normalize percentages to proportions: 50 percent traffic is 0.5; a 1 percentage-point MDE is 0.01.
Do not infer missing values, invent guardrail thresholds, or use raw event records. If any required fact
is absent or ambiguous, return {{"error": "..."}} explaining exactly what is missing. Numbers must be JSON numbers.

User description:
{raw}
"""
    value = _json_model_call(prompt)
    if "error" in value:
        raise ValueError(str(value["error"]))
    required = [
        "test_name", "hypothesis", "variant_change", "primary_metric", "guardrail_information",
        "control_sample_size", "control_successes", "variant_sample_size", "variant_successes",
        "duration_days", "control_traffic_share", "variant_traffic_share",
    ]
    missing = [field for field in required if field not in value]
    if missing:
        raise ValueError("The extracted experiment data is missing: " + ", ".join(missing))
    return value


def _assess_guardrail(experiment_data: dict[str, Any]) -> bool:
    prompt = f"""Assess the guardrail information in this structured A/B test data.
Return JSON only in the form {{"guardrail_concern": true_or_false}}.
Set true only if the user explicitly reports meaningful degradation, a breached threshold, or another
important negative effect. Small numerical differences without an explicitly meaningful interpretation
do not establish concern. Do not invent thresholds or negative effects. Do not use the primary metric
or statistical result to decide this field.

Data:
{json.dumps(experiment_data, ensure_ascii=False)}
"""
    value = _json_model_call(prompt)
    concern = value.get("guardrail_concern")
    if not isinstance(concern, bool):
        raise ValueError("The language model returned an invalid guardrail assessment.")
    return concern


def _classify(statistical_result: dict[str, Any], guardrail_concern: bool) -> tuple[str, str]:
    if statistical_result["sample_ratio_mismatch"]:
        outcome = "inconclusive"
    elif statistical_result["statistically_significant"] and statistical_result["absolute_difference"] < 0:
        outcome = "significant_negative"
    elif statistical_result["statistically_significant"] and statistical_result["absolute_difference"] > 0 and guardrail_concern:
        outcome = "significant_positive_guardrail_concern"
    elif statistical_result["statistically_significant"] and statistical_result["absolute_difference"] > 0:
        outcome = "significant_positive_safe"
    elif not statistical_result["statistically_significant"] and statistical_result["absolute_difference"] > 0:
        outcome = "not_significant_positive"
    else:
        outcome = "not_significant_flat"
    recommendations = {
        "significant_positive_safe": "ship",
        "significant_positive_guardrail_concern": "investigate",
        "not_significant_positive": "extend",
        "not_significant_flat": "stop",
        "significant_negative": "dont_ship",
        "inconclusive": "undetermined",
    }
    return outcome, recommendations[outcome]


def _generate_final_analysis(raw: str, experiment: dict[str, Any], stats: dict[str, Any], concern: bool, outcome: str, recommendation: str) -> str:
    prompt = f"""You are ABTestAnalysisAssistant. Write a concise, clear final A/B test analysis for a product manager.
Use only the supplied facts and deterministic statistical result. Do not invent business facts, thresholds,
or data. Include: hypothesis, duration, sample sizes, conversion rates, absolute difference, relative lift
when available, p-value, 95% confidence interval, significance, power status, sample-ratio mismatch,
guardrail assessment, recommendation, reasoning, and next steps. Explain that power status is diagnostic
and does not override statistical significance. The recommendation must be exactly the supplied value.
Use plain text with short labeled sections. Output only the analysis.

Original user information:
{raw}

Structured experiment data:
{json.dumps(experiment, ensure_ascii=False)}

Deterministic statistical result:
{json.dumps(stats, ensure_ascii=False)}

Guardrail concern: {str(concern).lower()}
Analysis outcome: {outcome}
Recommendation: {recommendation}
"""
    return _text_model_call(prompt)


def main():
    print("ABTestAnalysisAssistant: 请在一条消息中提供完整的 A/B 测试信息。")
    print("请包含测试名称、假设、变更、主指标、Control/Variant 样本量与成功数、时长、流量分配、可选 MDE 和护栏信息。")
    raw = input().strip()
    if not raw:
        raise ValueError("A/B test information cannot be empty.")

    experiment_data = _extract_experiment(raw)
    statistical_result = calculate_ab_test_statistics(experiment_data)
    guardrail_concern = _assess_guardrail(experiment_data)
    analysis_outcome, recommendation = _classify(statistical_result, guardrail_concern)
    final_analysis = _generate_final_analysis(
        raw, experiment_data, statistical_result, guardrail_concern, analysis_outcome, recommendation
    )
    print("\n" + final_analysis)
    return final_analysis


if __name__ == "__main__":
    main()
