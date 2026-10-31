from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - reported clearly when the agent runs
    OpenAI = None  # type: ignore[assignment,misc]


SIGNIFICANCE_ALPHA = 0.05
SRM_ALPHA = 0.01
Z_95 = 1.959963984540054
Z_POWER_80 = 0.8416212335729143

REQUIRED_TEXT_FIELDS = (
    "test_name",
    "hypothesis",
    "variant_change",
    "primary_metric",
    "guardrail_information",
)
REQUIRED_NUMERIC_FIELDS = (
    "control_sample_size",
    "control_successes",
    "variant_sample_size",
    "variant_successes",
    "duration_days",
    "control_traffic_share",
    "variant_traffic_share",
)


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries without overriding process variables."""

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
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _as_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return number


def _as_positive_integer(value: Any, field_name: str) -> int:
    number = _as_number(value, field_name)
    if not number.is_integer():
        raise ValueError(f"{field_name} must be an integer.")
    integer = int(number)
    if integer <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")
    return integer


def _normalize_percentage_number(value: Any, field_name: str) -> float:
    number = _as_number(value, field_name)
    # The extraction prompt asks for proportions. This also accepts a model
    # response that retained a percentage scale, while leaving proportions
    # unchanged.
    if abs(number) > 1.0:
        number /= 100.0
    return number


def _parse_json_response(response_text: str, purpose: str) -> dict[str, Any]:
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"The model returned invalid JSON for {purpose}.") from exc
    if not isinstance(result, dict):
        raise ValueError(f"The model returned a non-object for {purpose}.")
    return result


def _response_text(response: Any, purpose: str) -> str:
    text = getattr(response, "output_text", None)
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"The model returned no usable text for {purpose}.")
    return text


class LLMService:
    def __init__(self) -> None:
        _load_dotenv()
        if OpenAI is None:
            raise RuntimeError(
                "The official OpenAI Python client is required. "
                "Install the 'openai' package before running the agent."
            )

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
            raise RuntimeError(
                "Missing runtime model configuration: " + ", ".join(missing)
            )

        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def _complete(self, instructions: str, user_input: str, purpose: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            reasoning={"effort": "high"},
            instructions=instructions,
            input=user_input,
        )
        return _response_text(response, purpose)

    def extract_experiment_data(self, raw_information: str) -> dict[str, Any]:
        instructions = """
You extract structured data from one user's complete aggregated binary-conversion
A/B test description. Return JSON only, with exactly these possible keys:
test_name, hypothesis, variant_change, primary_metric, guardrail_information,
control_sample_size, control_successes, variant_sample_size, variant_successes,
duration_days, control_traffic_share, variant_traffic_share,
minimum_detectable_effect.

The five text fields and all required numeric fields are required. Use null only
when the optional minimum_detectable_effect was not explicitly provided. Never
invent, infer, or fill in a fact that the user did not state. Sample sizes and
successes are counts. Convert traffic percentages to proportions and convert a
percentage-point minimum detectable effect to a proportion (for example, a
percentage point value of 1 becomes 0.01). Keep the user's meaning for names,
hypothesis, tested change, primary metric, and guardrail information. The
traffic shares must describe the stated Control and Variant allocation.
""".strip()
        extracted = _parse_json_response(
            self._complete(instructions, raw_information, "experiment extraction"),
            "experiment extraction",
        )
        return _validate_experiment_data(extracted)

    def assess_guardrail(self, experiment_data: dict[str, Any]) -> bool:
        instructions = """
Assess whether the guardrail information explicitly reports a meaningful negative
effect. Return JSON only in this shape: {"guardrail_concern": true_or_false}.

Set true only when the supplied guardrail text explicitly reports meaningful
degradation, a breached guardrail threshold, or another important negative
effect. Set false when no such effect is explicitly reported, including when
the information is absent, neutral, positive, or too vague to establish a
meaningful concern. Do not invent thresholds, compare numbers yourself, or
infer a negative effect from a small numerical difference. Use only the supplied
guardrail information.
""".strip()
        payload = {"guardrail_information": experiment_data["guardrail_information"]}
        result = _parse_json_response(
            self._complete(
                instructions,
                json.dumps(payload, ensure_ascii=False),
                "guardrail assessment",
            ),
            "guardrail assessment",
        )
        concern = result.get("guardrail_concern")
        if not isinstance(concern, bool):
            raise ValueError("The model returned an invalid guardrail assessment.")
        return concern

    def generate_final_analysis(
        self,
        experiment_data: dict[str, Any],
        statistical_result: dict[str, Any],
        guardrail_concern: bool,
        analysis_outcome: str,
        recommendation: str,
    ) -> str:
        instructions = """
Write a concise final A/B test analysis for the product manager. Use the same
language as the supplied experiment text. Ground every statement in the input
or the deterministic statistical result. Do not recalculate or alter any
statistics, invent business facts, invent guardrail thresholds, or claim that
an experiment is mature or immature based on duration alone.

Include: hypothesis; duration; Control and Variant sample sizes; conversion
rates; absolute difference; relative lift when present; p-value; 95% confidence
interval; statistical significance; power status; sample ratio mismatch;
guardrail assessment; recommendation; concise reasoning; and next steps.
Explain power status as diagnostic context only: it must not override statistical
significance. A sample ratio mismatch makes the experiment inconclusive. Use the
provided recommendation exactly. Return only the analysis text, with no JSON
wrapper and no discussion of these instructions.
""".strip()
        payload = {
            "experiment_data": experiment_data,
            "statistical_result": statistical_result,
            "guardrail_concern": guardrail_concern,
            "analysis_outcome": analysis_outcome,
            "recommendation": recommendation,
        }
        return self._complete(
            instructions,
            json.dumps(payload, ensure_ascii=False),
            "final analysis",
        ).strip()


def _validate_experiment_data(data: dict[str, Any]) -> dict[str, Any]:
    for field_name in REQUIRED_TEXT_FIELDS:
        value = data.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing required text field: {field_name}.")

    normalized: dict[str, Any] = {
        field_name: data[field_name].strip() for field_name in REQUIRED_TEXT_FIELDS
    }
    for field_name in REQUIRED_NUMERIC_FIELDS:
        if field_name in {
            "control_sample_size",
            "variant_sample_size",
        }:
            normalized[field_name] = _as_positive_integer(data.get(field_name), field_name)
        elif field_name in {"control_successes", "variant_successes"}:
            number = _as_number(data.get(field_name), field_name)
            if not number.is_integer() or number < 0:
                raise ValueError(f"{field_name} must be a non-negative integer.")
            normalized[field_name] = int(number)
        elif field_name in {"control_traffic_share", "variant_traffic_share"}:
            normalized[field_name] = _normalize_percentage_number(
                data.get(field_name), field_name
            )
        else:
            normalized[field_name] = _as_number(data.get(field_name), field_name)

    if "minimum_detectable_effect" in data and data["minimum_detectable_effect"] is not None:
        normalized["minimum_detectable_effect"] = _normalize_percentage_number(
            data["minimum_detectable_effect"], "minimum_detectable_effect"
        )

    if normalized["control_successes"] > normalized["control_sample_size"]:
        raise ValueError("Control successes must be between zero and the Control sample size.")
    if normalized["variant_successes"] > normalized["variant_sample_size"]:
        raise ValueError("Variant successes must be between zero and the Variant sample size.")
    if normalized["control_traffic_share"] <= 0 or normalized["variant_traffic_share"] <= 0:
        raise ValueError("Traffic shares must be greater than zero.")
    if not math.isclose(
        normalized["control_traffic_share"] + normalized["variant_traffic_share"],
        1.0,
        rel_tol=0.0,
        abs_tol=1e-6,
    ):
        raise ValueError("Control and Variant traffic shares must sum to 1.0.")
    return normalized


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


def _classify(statistical_result: dict[str, Any], guardrail_concern: bool) -> str:
    if statistical_result["sample_ratio_mismatch"]:
        return "inconclusive"
    if statistical_result["statistically_significant"] and statistical_result["absolute_difference"] < 0:
        return "significant_negative"
    if (
        statistical_result["statistically_significant"]
        and statistical_result["absolute_difference"] > 0
        and guardrail_concern
    ):
        return "significant_positive_guardrail_concern"
    if statistical_result["statistically_significant"] and statistical_result["absolute_difference"] > 0:
        return "significant_positive_safe"
    if not statistical_result["statistically_significant"] and statistical_result["absolute_difference"] > 0:
        return "not_significant_positive"
    return "not_significant_flat"


def _recommend(analysis_outcome: str) -> str:
    return {
        "significant_positive_safe": "ship",
        "significant_positive_guardrail_concern": "investigate",
        "not_significant_positive": "extend",
        "not_significant_flat": "stop",
        "significant_negative": "dont_ship",
        "inconclusive": "undetermined",
    }[analysis_outcome]


def main() -> str | None:
    """Run one complete terminal-based A/B test analysis."""

    try:
        raw_ab_test_information = input(
            "Provide the complete aggregated A/B test information in one message: "
        )
        if not raw_ab_test_information.strip():
            raise ValueError("A/B test information cannot be empty.")

        service = LLMService()
        experiment_data = service.extract_experiment_data(raw_ab_test_information)
        statistical_result = calculate_ab_test_statistics(experiment_data)
        guardrail_concern = service.assess_guardrail(experiment_data)
        analysis_outcome = _classify(statistical_result, guardrail_concern)
        recommendation = _recommend(analysis_outcome)
        final_analysis = service.generate_final_analysis(
            experiment_data,
            statistical_result,
            guardrail_concern,
            analysis_outcome,
            recommendation,
        )
        print(final_analysis)
        return final_analysis
    except Exception as exc:
        print(f"A/B test analysis failed: {exc}", file=sys.stderr)
        return None


if __name__ == "__main__":
    main()
