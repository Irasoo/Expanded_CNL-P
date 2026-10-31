"""Terminal A/B test analysis agent generated from the CNL-P specification."""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI


class AgentError(RuntimeError):
    """An error that can be reported directly to the terminal user."""


def _load_dotenv() -> dict[str, str]:
    """Load simple KEY=VALUE entries from .env without requiring a dependency."""

    values: dict[str, str] = {}
    env_path = Path.cwd() / ".env"
    if not env_path.is_file():
        return values

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def _setting(name: str, dotenv: dict[str, str]) -> str | None:
    value = os.environ.get(name)
    if value is not None and value.strip():
        return value.strip()
    value = dotenv.get(name)
    return value.strip() if value and value.strip() else None


def _require_settings() -> tuple[str, str, str]:
    dotenv = _load_dotenv()
    api_key = _setting("OPENAI_API_KEY", dotenv)
    base_url = _setting("BASE_URL", dotenv)
    model = _setting("CNLP_REFERENCE_LLM_MODEL", dotenv) or _setting(
        "OPENAI_MODEL", dotenv
    )

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
    return api_key, base_url, model


def _json_from_model(text: str, purpose: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise AgentError(f"The model returned invalid JSON for {purpose}.") from exc
    if not isinstance(value, dict):
        raise AgentError(f"The model returned a non-object for {purpose}.")
    return value


def _model_text(client: OpenAI, model: str, instructions: str, user_input: str) -> str:
    try:
        response = client.responses.create(
            model=model,
            reasoning={"effort": "high"},
            instructions=instructions,
            input=user_input,
        )
    except Exception as exc:
        raise AgentError(f"Runtime language-model call failed: {exc}") from exc

    output = getattr(response, "output_text", None)
    if not isinstance(output, str) or not output.strip():
        raise AgentError("The runtime language model returned an empty result.")
    return output.strip()


def _number(value: Any, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AgentError(f"Extracted field {field} must be a number.")
    if not math.isfinite(float(value)):
        raise AgentError(f"Extracted field {field} must be finite.")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentError(f"Extracted field {field} must be non-empty text.")
    return value.strip()


def _validate_experiment_data(value: dict[str, Any]) -> dict[str, Any]:
    required_text = ("test_name", "hypothesis", "variant_change", "primary_metric")
    required_numbers = (
        "control_sample_size",
        "control_successes",
        "variant_sample_size",
        "variant_successes",
        "duration_days",
        "control_traffic_share",
        "variant_traffic_share",
    )
    result: dict[str, Any] = {}
    for field in required_text:
        result[field] = _text(value.get(field), field)
    for field in required_numbers:
        result[field] = _number(value.get(field), field)

    if "minimum_detectable_effect" in value and value["minimum_detectable_effect"] is not None:
        result["minimum_detectable_effect"] = _number(
            value["minimum_detectable_effect"], "minimum_detectable_effect"
        )
    result["guardrail_information"] = _text(
        value.get("guardrail_information"), "guardrail_information"
    )

    for field in (
        "control_sample_size",
        "control_successes",
        "variant_sample_size",
        "variant_successes",
    ):
        if float(result[field]).is_integer():
            result[field] = int(result[field])
        else:
            raise AgentError(f"Extracted field {field} must be an integer.")

    for field in ("duration_days", "control_traffic_share", "variant_traffic_share"):
        if result[field] < 0:
            raise AgentError(f"Extracted field {field} cannot be negative.")
    return result


def calculate_ab_test_statistics(experiment_data: dict[str, Any]) -> dict[str, Any]:
    """Calculate the deterministic statistics specified by the reference API."""

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
    pooled_standard_error = math.sqrt(
        pooled_rate * (1.0 - pooled_rate) * ((1.0 / n_control) + (1.0 / n_variant))
    )
    if pooled_standard_error == 0:
        p_value = 1.0
    else:
        z_score = absolute_difference / pooled_standard_error
        p_value = math.erfc(abs(z_score) / math.sqrt(2.0))
    statistically_significant = p_value < significance_alpha

    difference_standard_error = math.sqrt(
        control_rate * (1.0 - control_rate) / n_control
        + variant_rate * (1.0 - variant_rate) / n_variant
    )
    confidence_interval_lower = absolute_difference - z_95 * difference_standard_error
    confidence_interval_upper = absolute_difference + z_95 * difference_standard_error

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


PERSONA_CONTEXT = """You are an assistant responsible for analyzing A/B test results and translating statistical findings into clear product decisions. Your responsibility is to validate the experiment using statistical results, assess provided guardrail information, and recommend whether the tested variant should be shipped, investigated, extended, stopped, rejected, or left undetermined. Do not invent experimental data, metric values, statistical results, guardrail thresholds, or business facts absent from the user's information or deterministic calculation. The audience is product managers or team members evaluating an A/B test. Use concise, clear explanations. The primary metric is a binary success conversion rate (successful conversions divided by sample size), where higher is better. A guardrail metric detects undesirable side effects. Statistical significance means the observed difference is unlikely to be random variation under the specified test. A sample ratio mismatch is a statistically meaningful discrepancy between expected and observed allocation."""


class ABTestAnalyzer:
    """The CNL-P ABTestAnalyzer Worker and its execution state."""

    def __init__(self) -> None:
        api_key, base_url, model = _require_settings()
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.state: dict[str, Any] = {}

    def _extract_experiment_data(self, raw: str) -> dict[str, Any]:
        instructions = PERSONA_CONTEXT + """

Extract the user's complete aggregated binary-conversion A/B test information into one JSON object. Do not calculate rates or statistical results. Preserve only facts explicitly provided. Required keys are: test_name, hypothesis, variant_change, primary_metric, control_sample_size, control_successes, variant_sample_size, variant_successes, duration_days, control_traffic_share, variant_traffic_share, guardrail_information. The optional key is minimum_detectable_effect. Numeric percentages must be normalized to proportions: an allocation written as 50 percent is 0.5, and an MDE written as 1 percentage point is 0.01. Do not infer missing values; if a required fact is absent, return null for that field so validation can report it. Return JSON only.
"""
        payload = _model_text(self.client, self.model, instructions, raw)
        return _validate_experiment_data(_json_from_model(payload, "experiment extraction"))

    def _classify_guardrail(self, experiment_data: dict[str, Any]) -> bool:
        instructions = PERSONA_CONTEXT + """

Inspect only the user's guardrail_information field. Return JSON only in the form {"guardrail_concern": true_or_false}. Set true only if the user explicitly reports meaningful degradation, a breached guardrail threshold, or another important negative effect. Small numerical differences without an explicit meaningful concern do not qualify. Do not invent a threshold, interpret omitted information as a concern, or use the primary metric result for this decision.
"""
        payload = _model_text(
            self.client,
            self.model,
            instructions,
            json.dumps({"guardrail_information": experiment_data["guardrail_information"]}, ensure_ascii=False),
        )
        value = _json_from_model(payload, "guardrail assessment").get("guardrail_concern")
        if not isinstance(value, bool):
            raise AgentError("The model returned an invalid guardrail assessment.")
        return value

    @staticmethod
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
        if statistics["statistically_significant"] and statistics["absolute_difference"] > 0:
            return "significant_positive_safe"
        if not statistics["statistically_significant"] and statistics["absolute_difference"] > 0:
            return "not_significant_positive"
        return "not_significant_flat"

    @staticmethod
    def _recommendation(outcome: str) -> str:
        return {
            "significant_positive_safe": "ship",
            "significant_positive_guardrail_concern": "investigate",
            "not_significant_positive": "extend",
            "not_significant_flat": "stop",
            "significant_negative": "dont_ship",
            "inconclusive": "undetermined",
        }[outcome]

    def _generate_analysis(self) -> str:
        instructions = PERSONA_CONTEXT + """

Generate the final concise A/B test analysis as plain text, suitable for direct display to the user. Use only the supplied structured experiment data and deterministic statistical result. Include the hypothesis, duration, sample sizes, conversion rates, absolute difference, relative lift when available, p-value, 95% confidence interval, statistical significance, power status, sample ratio mismatch, guardrail assessment, recommendation, reasoning, and next steps. Mention that power status is diagnostic/supporting detail and must not override statistical significance. Report duration without inferring maturity from duration alone. Explain any unavailable value honestly. Do not add facts or thresholds not present in the supplied data. The recommendation must exactly reflect the supplied recommendation value.
"""
        input_data = {
            "experiment_data": self.state["experiment_data"],
            "statistical_result": self.state["statistical_result"],
            "guardrail_concern": self.state["guardrail_concern"],
            "recommendation": self.state["recommendation"],
        }
        return _model_text(
            self.client,
            self.model,
            instructions,
            json.dumps(input_data, ensure_ascii=False, indent=2),
        )

    def run(self) -> str:
        # COMMAND-1: one INPUT command, therefore exactly one terminal read.
        self.state["raw_ab_test_information"] = input(
            "Provide the complete A/B test information in one message, including "
            "test name, hypothesis, tested change, primary metric, Control and "
            "Variant sample sizes and successes, duration, traffic split, optional "
            "minimum detectable effect, and guardrail information:\n> "
        )

        # COMMAND-2 through COMMAND-5: normalize, calculate, assess, classify.
        self.state["experiment_data"] = self._extract_experiment_data(
            self.state["raw_ab_test_information"]
        )
        self.state["statistical_result"] = calculate_ab_test_statistics(
            self.state["experiment_data"]
        )
        self.state["guardrail_concern"] = self._classify_guardrail(
            self.state["experiment_data"]
        )
        self.state["analysis_outcome"] = self._classify_outcome(
            self.state["statistical_result"], self.state["guardrail_concern"]
        )
        self.state["recommendation"] = self._recommendation(
            self.state["analysis_outcome"]
        )

        # COMMAND-12 and COMMAND-13: generate and display the required output.
        self.state["final_analysis"] = self._generate_analysis()
        print("\n" + self.state["final_analysis"])
        return self.state["final_analysis"]


def main() -> str:
    """Initialize the Agent, execute its entry Worker, and return its result."""

    return ABTestAnalyzer().run()


if __name__ == "__main__":
    try:
        main()
    except (AgentError, ValueError, EOFError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
