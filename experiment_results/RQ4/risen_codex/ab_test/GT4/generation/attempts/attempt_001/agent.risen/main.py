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

REQUIRED_TEXT_FIELDS = (
    "test_name",
    "hypothesis",
    "variant_change",
    "primary_metric",
    "guardrail_information",
)
REQUIRED_NUMBER_FIELDS = (
    "control_sample_size",
    "control_successes",
    "variant_sample_size",
    "variant_successes",
    "duration_days",
    "control_traffic_share",
    "variant_traffic_share",
)


class AgentConfigurationError(RuntimeError):
    """Raised when required runtime model configuration is unavailable."""


def _read_dotenv() -> dict[str, str]:
    """Read simple KEY=VALUE entries from the current directory's .env only."""
    dotenv_path = Path.cwd() / ".env"
    if not dotenv_path.is_file():
        return {}

    values: dict[str, str] = {}
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key] = value
    return values


def _runtime_setting(name: str, dotenv: dict[str, str]) -> str | None:
    value = os.environ.get(name)
    if value is not None and value.strip():
        return value.strip()
    value = dotenv.get(name)
    return value.strip() if value and value.strip() else None


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("The language model returned invalid JSON.") from exc
    if not isinstance(value, dict):
        raise ValueError("The language model response must be a JSON object.")
    return value


def _number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number.")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{field_name} must be finite.")
    return converted


def _validate_and_normalize_experiment(data: dict[str, Any]) -> dict[str, Any]:
    missing = [
        field
        for field in (*REQUIRED_TEXT_FIELDS, *REQUIRED_NUMBER_FIELDS)
        if field not in data or data[field] is None
    ]
    if missing:
        raise ValueError(
            "The provided A/B test information is missing required fields: "
            + ", ".join(missing)
            + "."
        )

    normalized: dict[str, Any] = {}
    for field in REQUIRED_TEXT_FIELDS:
        if not isinstance(data[field], str) or not data[field].strip():
            raise ValueError(f"{field} must be non-empty text explicitly provided by the user.")
        normalized[field] = data[field].strip()

    for field in REQUIRED_NUMBER_FIELDS:
        normalized[field] = _number(data[field], field)

    for field in (
        "control_sample_size",
        "control_successes",
        "variant_sample_size",
        "variant_successes",
    ):
        if not normalized[field].is_integer():
            raise ValueError(f"{field} must be a whole number.")
        normalized[field] = int(normalized[field])

    if "minimum_detectable_effect" in data and data["minimum_detectable_effect"] is not None:
        normalized["minimum_detectable_effect"] = _number(
            data["minimum_detectable_effect"], "minimum_detectable_effect"
        )
    return normalized


def calculate_ab_test_statistics(experiment_data: dict[str, Any]) -> dict[str, Any]:
    """Calculate deterministic statistics for one aggregated binary A/B test."""
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
    statistically_significant = p_value < SIGNIFICANCE_ALPHA

    difference_se = math.sqrt(
        control_rate * (1.0 - control_rate) / n_control
        + variant_rate * (1.0 - variant_rate) / n_variant
    )
    confidence_interval_lower = absolute_difference - Z_95 * difference_se
    confidence_interval_upper = absolute_difference + Z_95 * difference_se

    mde = experiment_data.get("minimum_detectable_effect")
    if mde is None:
        power_status = "unavailable"
    else:
        mde = abs(float(mde))
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
    chi_square = (
        ((n_control - expected_control) ** 2) / expected_control
        + ((n_variant - expected_variant) ** 2) / expected_variant
    )
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
        "sample_ratio_mismatch": srm_p_value < SRM_ALPHA,
    }
    if relative_lift is not None:
        result["relative_lift"] = relative_lift
    return result


class ABTestAnalysisAssistant:
    def __init__(self) -> None:
        dotenv = _read_dotenv()
        api_key = _runtime_setting("OPENAI_API_KEY", dotenv)
        if not api_key:
            raise AgentConfigurationError(
                "OPENAI_API_KEY is not configured in the environment or current .env file."
            )
        model = _runtime_setting("CNLP_REFERENCE_LLM_MODEL", dotenv) or _runtime_setting(
            "OPENAI_MODEL", dotenv
        )
        if not model:
            raise AgentConfigurationError(
                "Set CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL in the environment or current .env file."
            )
        base_url = _runtime_setting("BASE_URL", dotenv)
        client_options: dict[str, str] = {"api_key": api_key}
        if base_url:
            client_options["base_url"] = base_url
        self.client = OpenAI(**client_options)
        self.model = model

    def _ask_model(self, instructions: str, user_content: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            reasoning={"effort": "high"},
            instructions=instructions,
            input=user_content,
        )
        output = getattr(response, "output_text", None)
        if not output or not output.strip():
            raise RuntimeError("The language model returned an empty response.")
        return output.strip()

    def extract_experiment_data(self, raw_information: str) -> dict[str, Any]:
        instructions = """
You extract structured data from one user's complete A/B test description. Return ONLY
one valid JSON object, with no markdown. Use exactly these required keys:
test_name, hypothesis, variant_change, primary_metric, guardrail_information,
control_sample_size, control_successes, variant_sample_size, variant_successes,
duration_days, control_traffic_share, variant_traffic_share.
Include minimum_detectable_effect only when explicitly provided.

Do not infer or fill missing facts. Text values must be faithful to the user's words.
Numbers must be JSON numbers. Normalize traffic percentages to proportions (50 percent
becomes 0.5), and normalize an explicitly stated percentage-point MDE to a proportion
(1 percentage point becomes 0.01). A relative MDE written as a percent is also a
proportion (5% becomes 0.05). Keep conversion counts and sample sizes as whole numbers.
Preserve guardrail_information only when the user explicitly supplied it. If any
required field is absent, omit that key so the caller can report the missing field;
never invent a placeholder or a value. Do not decide guardrail concern here.
""".strip()
        raw = self._ask_model(instructions, raw_information)
        return _validate_and_normalize_experiment(_parse_json_object(raw))

    def assess_guardrail(self, guardrail_information: str) -> bool:
        instructions = """
Assess only the guardrail statement supplied by the user. Return ONLY a JSON object
of the form {"guardrail_concern": true} or {"guardrail_concern": false}.
Set true only if the statement explicitly reports meaningful degradation, a breached
guardrail threshold, or another important negative effect. Set false when it reports
no issue, is neutral/unclear, or merely gives a small numerical difference without an
explicit threshold or meaningful-negative statement. Never invent a threshold or effect.
""".strip()
        result = _parse_json_object(self._ask_model(instructions, guardrail_information))
        value = result.get("guardrail_concern")
        if not isinstance(value, bool):
            raise ValueError("The guardrail assessment returned a non-boolean value.")
        return value

    @staticmethod
    def classify(statistics: dict[str, Any], guardrail_concern: bool) -> tuple[str, str]:
        if statistics["sample_ratio_mismatch"]:
            outcome = "inconclusive"
        elif statistics["statistically_significant"] and statistics["absolute_difference"] < 0:
            outcome = "significant_negative"
        elif (
            statistics["statistically_significant"]
            and statistics["absolute_difference"] > 0
            and guardrail_concern
        ):
            outcome = "significant_positive_guardrail_concern"
        elif statistics["statistically_significant"] and statistics["absolute_difference"] > 0:
            outcome = "significant_positive_safe"
        elif not statistics["statistically_significant"] and statistics["absolute_difference"] > 0:
            outcome = "not_significant_positive"
        else:
            outcome = "not_significant_flat"

        recommendation_by_outcome = {
            "significant_positive_safe": "ship",
            "significant_positive_guardrail_concern": "investigate",
            "not_significant_positive": "extend",
            "not_significant_flat": "stop",
            "significant_negative": "dont_ship",
            "inconclusive": "undetermined",
        }
        return outcome, recommendation_by_outcome[outcome]

    def generate_final_analysis(
        self,
        experiment_data: dict[str, Any],
        statistics: dict[str, Any],
        guardrail_concern: bool,
        analysis_outcome: str,
        recommendation: str,
    ) -> str:
        instructions = """
Write a concise final A/B test analysis for a product manager. Use ONLY facts in the
JSON supplied by the caller; do not add business facts, thresholds, or interpretations
not supported by it. Include: hypothesis, duration, both sample sizes, both conversion
rates, absolute difference, relative lift when present, p-value, 95% confidence
interval, statistical significance, power status, sample-ratio mismatch, guardrail
assessment, recommendation, reasoning, and next steps. Explain that power status is
diagnostic and does not override statistical significance. Explain sample-ratio
mismatch as making the experiment inconclusive when true. Keep the response readable
with short labeled paragraphs or bullets. Use the recommendation exactly as provided.
""".strip()
        payload = {
            "experiment_data": experiment_data,
            "statistical_result": statistics,
            "guardrail_concern": guardrail_concern,
            "analysis_outcome": analysis_outcome,
            "recommendation": recommendation,
        }
        return self._ask_model(instructions, json.dumps(payload, ensure_ascii=False, sort_keys=True))

    def run(self) -> str:
        raw_information = input(
            "请在一条消息中提供完整的 A/B 测试信息（测试名称、假设、改动、主指标、"
            "Control/Variant 样本量与成功数、持续天数、流量分配、可选 MDE 和 guardrail 信息）：\n> "
        )
        if not raw_information.strip():
            raise ValueError("A/B test information cannot be empty.")

        experiment_data = self.extract_experiment_data(raw_information)
        statistical_result = calculate_ab_test_statistics(experiment_data)
        guardrail_concern = self.assess_guardrail(experiment_data["guardrail_information"])
        analysis_outcome, recommendation = self.classify(
            statistical_result, guardrail_concern
        )
        return self.generate_final_analysis(
            experiment_data,
            statistical_result,
            guardrail_concern,
            analysis_outcome,
            recommendation,
        )


def main() -> str | None:
    """Initialize the assistant, run one analysis, print it, and return it."""
    try:
        final_analysis = ABTestAnalysisAssistant().run()
    except (AgentConfigurationError, ValueError, RuntimeError) as exc:
        print(f"无法完成 A/B 测试分析：{exc}")
        return None
    except Exception as exc:
        print(f"无法完成 A/B 测试分析：运行时发生错误（{exc}）。")
        return None

    print("\n" + final_analysis)
    return final_analysis


if __name__ == "__main__":
    main()
