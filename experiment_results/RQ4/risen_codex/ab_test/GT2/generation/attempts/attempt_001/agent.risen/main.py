from __future__ import annotations

import json
import math
import os
import sys
from typing import Any

from openai import OpenAI


SIGNIFICANCE_ALPHA = 0.05
SRM_ALPHA = 0.01
Z_95 = 1.959963984540054
Z_POWER_80 = 0.8416212335729143


def _load_local_dotenv() -> None:
    """Load simple KEY=VALUE entries from the project-local .env file."""
    dotenv_path = os.path.join(os.getcwd(), ".env")
    try:
        with open(dotenv_path, "r", encoding="utf-8") as dotenv_file:
            lines = dotenv_file.readlines()
    except FileNotFoundError:
        return

    for line in lines:
        entry = line.strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue
        key, value = entry.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _json_schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


EXPERIMENT_SCHEMA = _json_schema(
    {
        "test_name": {"type": ["string", "null"]},
        "hypothesis": {"type": ["string", "null"]},
        "variant_change": {"type": ["string", "null"]},
        "primary_metric": {"type": ["string", "null"]},
        "guardrail_information": {"type": ["string", "null"]},
        "control_sample_size": {"type": ["number", "null"]},
        "control_successes": {"type": ["number", "null"]},
        "variant_sample_size": {"type": ["number", "null"]},
        "variant_successes": {"type": ["number", "null"]},
        "duration_days": {"type": ["number", "null"]},
        "control_traffic_share": {"type": ["number", "null"]},
        "variant_traffic_share": {"type": ["number", "null"]},
        "minimum_detectable_effect": {"type": ["number", "null"]},
    }
)

GUARDRAIL_SCHEMA = _json_schema(
    {
        "guardrail_concern": {"type": "boolean"},
        "evidence": {"type": "string"},
    }
)


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
    pooled_standard_error = math.sqrt(
        pooled_rate * (1.0 - pooled_rate) * ((1.0 / n_control) + (1.0 / n_variant))
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
        balanced_design = math.isclose(control_share, 0.5, rel_tol=0.0, abs_tol=1e-6) and math.isclose(
            variant_share, 0.5, rel_tol=0.0, abs_tol=1e-6
        )
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
            power_status = (
                "adequate"
                if n_control >= required_sample_per_group and n_variant >= required_sample_per_group
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


class ABTestAnalysisAssistant:
    def __init__(self) -> None:
        _load_local_dotenv()
        api_key = os.environ.get("OPENAI_API_KEY")
        model = os.environ.get("CNLP_REFERENCE_LLM_MODEL") or os.environ.get("OPENAI_MODEL")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured in the environment or local .env file.")
        if not model:
            raise RuntimeError(
                "No model configured. Set CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL in the environment or local .env file."
            )
        base_url = os.environ.get("BASE_URL")
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)
        self.model = model

    def _call_json(self, instructions: str, payload: dict[str, Any], name: str, schema: dict[str, Any]) -> dict[str, Any]:
        response = self.client.responses.create(
            model=self.model,
            reasoning={"effort": "high"},
            instructions=instructions,
            input=json.dumps(payload, ensure_ascii=False),
            text={
                "format": {
                    "type": "json_schema",
                    "name": name,
                    "strict": True,
                    "schema": schema,
                }
            },
        )
        raw = getattr(response, "output_text", None)
        if not raw:
            raise RuntimeError("The language model returned an empty structured response.")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("The language model returned invalid JSON.") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("The language model returned an unexpected structured response.")
        return parsed

    def _call_text(self, instructions: str, payload: dict[str, Any]) -> str:
        response = self.client.responses.create(
            model=self.model,
            reasoning={"effort": "high"},
            instructions=instructions,
            input=json.dumps(payload, ensure_ascii=False),
        )
        text = getattr(response, "output_text", None)
        if not text or not text.strip():
            raise RuntimeError("The language model returned an empty final analysis.")
        return text.strip()

    def extract_experiment_data(self, raw_information: str) -> dict[str, Any]:
        instructions = """
Extract structured data from the user's complete A/B test description.
Return only facts explicitly present in the user text. Do not infer, estimate, or invent values.
The test is an aggregated binary-conversion experiment. Required fields that are absent must be null.
Convert traffic percentages to proportions (50 percent -> 0.5). Convert a minimum detectable effect
expressed in percentage points to a proportion (1 percentage point -> 0.01). Keep metric and guardrail
descriptions faithful to the user. Sample sizes and successes must be numeric counts, and duration_days
must be numeric. Do not calculate conversion rates or any statistical result here.
"""
        return self._call_json(
            instructions,
            {"raw_ab_test_information": raw_information},
            "ab_test_experiment_data",
            EXPERIMENT_SCHEMA,
        )

    def inspect_guardrail(self, raw_information: str, experiment_data: dict[str, Any]) -> dict[str, Any]:
        instructions = """
Determine whether the user's A/B test information explicitly reports a meaningful negative guardrail effect.
Set guardrail_concern true only for explicit meaningful degradation, an explicitly breached guardrail
threshold, or another explicitly stated important negative effect. Set it false when no such effect is
explicitly reported. Do not infer a concern from a small numerical difference, and do not invent a threshold.
The evidence must be a brief faithful quote or paraphrase from the user; use an empty string when concern is false.
"""
        return self._call_json(
            instructions,
            {
                "raw_ab_test_information": raw_information,
                "guardrail_information": experiment_data["guardrail_information"],
            },
            "guardrail_assessment",
            GUARDRAIL_SCHEMA,
        )

    def generate_final_analysis(
        self,
        experiment_data: dict[str, Any],
        statistical_result: dict[str, Any],
        guardrail_concern: bool,
        recommendation: str,
        guardrail_evidence: str,
    ) -> str:
        instructions = """
Write a concise final A/B test analysis for a product manager in Chinese.
Use only the supplied experiment data and deterministic statistical result. Do not invent business facts,
thresholds, maturity claims, or missing values. Include: hypothesis, duration, both sample sizes, both
conversion rates, absolute difference, relative lift when present, p-value, 95% confidence interval,
statistical significance, power status, sample-ratio mismatch, guardrail assessment, recommendation,
reasoning, and next steps. Explain that power status is diagnostic and cannot override significance.
Use the exact recommendation value supplied. If a value is unavailable, say it is unavailable. Keep the
response readable and compact with short labeled paragraphs or bullets.
"""
        return self._call_text(
            instructions,
            {
                "experiment_data": experiment_data,
                "statistical_result": statistical_result,
                "guardrail_concern": guardrail_concern,
                "guardrail_evidence": guardrail_evidence,
                "recommendation": recommendation,
            },
        )

    def run(self) -> str:
        raw_information = input(
            "请一次性提供完整的 A/B 测试信息（测试名称、假设、变更、主指标、Control/Variant 样本量与成功数、时长、流量分配、可选 MDE、护栏信息）：\n> "
        ).strip()
        if not raw_information:
            raise ValueError("必须提供完整的 A/B 测试信息。")

        experiment_data = self.extract_experiment_data(raw_information)
        experiment_data = _normalize_and_validate_experiment_data(experiment_data)
        statistical_result = calculate_ab_test_statistics(experiment_data)

        guardrail_result = self.inspect_guardrail(raw_information, experiment_data)
        guardrail_concern = bool(guardrail_result["guardrail_concern"])

        difference = statistical_result["absolute_difference"]
        significant = statistical_result["statistically_significant"]
        if statistical_result["sample_ratio_mismatch"]:
            analysis_outcome = "inconclusive"
        elif significant and difference < 0:
            analysis_outcome = "significant_negative"
        elif significant and difference > 0 and guardrail_concern:
            analysis_outcome = "significant_positive_guardrail_concern"
        elif significant and difference > 0:
            analysis_outcome = "significant_positive_safe"
        elif not significant and difference > 0:
            analysis_outcome = "not_significant_positive"
        else:
            analysis_outcome = "not_significant_flat"

        recommendation_by_outcome = {
            "significant_positive_safe": "ship",
            "significant_positive_guardrail_concern": "investigate",
            "not_significant_positive": "extend",
            "not_significant_flat": "stop",
            "significant_negative": "dont_ship",
            "inconclusive": "undetermined",
        }
        recommendation = recommendation_by_outcome[analysis_outcome]
        final_analysis = self.generate_final_analysis(
            experiment_data,
            statistical_result,
            guardrail_concern,
            recommendation,
            str(guardrail_result.get("evidence", "")),
        )
        print("\n" + final_analysis)
        return final_analysis


def _normalize_and_validate_experiment_data(data: dict[str, Any]) -> dict[str, Any]:
    required_text_fields = (
        "test_name",
        "hypothesis",
        "variant_change",
        "primary_metric",
        "guardrail_information",
    )
    required_number_fields = (
        "control_sample_size",
        "control_successes",
        "variant_sample_size",
        "variant_successes",
        "duration_days",
        "control_traffic_share",
        "variant_traffic_share",
    )

    for field in required_text_fields:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"缺少必需的文本字段：{field}。")
        data[field] = value.strip()

    for field in required_number_fields:
        value = data.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"缺少或无法解析必需的数值字段：{field}。")
        data[field] = float(value)

    for field in ("control_sample_size", "control_successes", "variant_sample_size", "variant_successes"):
        if not data[field].is_integer():
            raise ValueError(f"字段 {field} 必须是整数。")
        data[field] = int(data[field])

    for field in ("control_traffic_share", "variant_traffic_share"):
        value = data[field]
        if value > 1.0 and value <= 100.0:
            data[field] = value / 100.0
        if not 0.0 < data[field] <= 1.0:
            raise ValueError(f"字段 {field} 必须是 0 到 1 之间的流量比例。")

    if data["duration_days"] < 0:
        raise ValueError("duration_days 不能为负数。")

    mde = data.get("minimum_detectable_effect")
    if mde is not None:
        if isinstance(mde, bool) or not isinstance(mde, (int, float)) or not math.isfinite(float(mde)):
            raise ValueError("minimum_detectable_effect 必须是数值。")
        mde = float(mde)
        if mde > 1.0 and mde <= 100.0:
            mde /= 100.0
        data["minimum_detectable_effect"] = mde

    return data


def main() -> str | None:
    try:
        assistant = ABTestAnalysisAssistant()
        return assistant.run()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消 A/B 测试分析。", file=sys.stderr)
    except Exception as exc:
        print(f"分析失败：{exc}", file=sys.stderr)
    return None


if __name__ == "__main__":
    main()
