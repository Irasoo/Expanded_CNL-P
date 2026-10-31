from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
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


@dataclass(frozen=True)
class RuntimeConfig:
    api_key: str
    base_url: str
    model: str


class ConfigurationError(RuntimeError):
    """Raised when the runtime model configuration is incomplete."""


class AgentExecutionError(RuntimeError):
    """Raised when a CNL-P command cannot complete without inventing data."""


def _read_local_dotenv() -> dict[str, str]:
    """Read only the optional .env file in the current agent directory."""
    env_path = Path(".env")
    if not env_path.is_file():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[name] = value
    return values


def _runtime_config() -> RuntimeConfig:
    dotenv = _read_local_dotenv()

    def setting(name: str) -> str | None:
        value = os.environ.get(name)
        if value is not None and value.strip():
            return value.strip()
        value = dotenv.get(name)
        return value.strip() if value and value.strip() else None

    api_key = setting("OPENAI_API_KEY")
    base_url = setting("BASE_URL")
    model = setting("CNLP_REFERENCE_LLM_MODEL") or setting("OPENAI_MODEL")

    missing = []
    if not api_key:
        missing.append("OPENAI_API_KEY")
    if not base_url:
        missing.append("BASE_URL")
    if not model:
        missing.append("CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL")
    if missing:
        raise ConfigurationError(
            "Missing runtime model configuration: " + ", ".join(missing)
        )
    return RuntimeConfig(api_key=api_key, base_url=base_url, model=model)


class RuntimeLLM:
    """Official OpenAI client wrapper used by semantic CNL-P commands."""

    def __init__(self, config: RuntimeConfig):
        self.model = config.model
        self.client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    def ask(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            reasoning={"effort": "high"},
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        output_text = getattr(response, "output_text", None)
        if not output_text:
            raise AgentExecutionError("The runtime language model returned no text.")
        return str(output_text).strip()

    def ask_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        text = self.ask(system_prompt, user_prompt)
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            value = json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start < 0 or end <= start:
                raise AgentExecutionError(
                    "The runtime language model did not return valid JSON."
                )
            try:
                value = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError as exc:
                raise AgentExecutionError(
                    "The runtime language model did not return valid JSON."
                ) from exc
        if not isinstance(value, dict):
            raise AgentExecutionError("The runtime language model returned a JSON value instead of an object.")
        return value


STATIC_CONTEXT = """You are an assistant responsible for analyzing A/B test results and translating statistical findings into clear product decisions.

Persona:
- Validate experiments using statistical results.
- Assess explicitly provided guardrail information.
- Recommend whether the tested variant should be shipped, investigated, extended, stopped, rejected, or left undetermined.

Audience: product managers or team members evaluating an A/B test. Use precise but accessible language.

Domain concepts:
- Primary metric: binary success conversion rate, successful conversions divided by sample size; higher is better.
- Guardrail metric: a metric used to detect undesirable side effects of the variant.
- Statistical significance: evidence that the Control-Variant difference is unlikely to be random variation under the statistical test.
- Sample ratio mismatch: a statistically meaningful discrepancy between expected and observed sample allocation.

Hard constraints:
- Ground every experiment fact and business interpretation in user-provided information or returned statistical results.
- The input is aggregated binary-conversion data, not raw CSV, Excel, or event-level records.
- Do not invent data, metric values, thresholds, business facts, or missing fields.
- Statistical calculations are performed by the deterministic calculation function, not by you.
- A two-sided p-value below 0.05 is significant.
- An SRM p-value below 0.01 is an SRM and makes the experiment inconclusive.
- Power status is diagnostic only and cannot override an already significant result.
- Guardrail concern exists only when the user explicitly reports meaningful degradation, a breached threshold, or another important negative effect.
- Duration must be reported, but maturity cannot be inferred from duration alone.
"""


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise AgentExecutionError(f"{field} must be numeric.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise AgentExecutionError(f"{field} must be numeric.") from exc
    if not math.isfinite(result):
        raise AgentExecutionError(f"{field} must be finite.")
    return result


def _integer(value: Any, field: str) -> int:
    number = _number(value, field)
    if not number.is_integer():
        raise AgentExecutionError(f"{field} must be a whole number.")
    return int(number)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise AgentExecutionError(f"{field} must be text.")
    return value.strip()


def _proportion(value: Any, field: str) -> float:
    result = _number(value, field)
    # The model is instructed to emit proportions, but accepting a numeric
    # percentage here makes normalization robust for natural-language input.
    if result > 1:
        result /= 100.0
    return result


def _normalize_experiment_data(raw: dict[str, Any]) -> dict[str, Any]:
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
    ]
    required_proportions = ["control_traffic_share", "variant_traffic_share"]

    for field in required_text + required_numbers + required_proportions:
        if field not in raw or raw[field] is None:
            raise AgentExecutionError(
                f"The user input does not contain the required field: {field}."
            )

    result: dict[str, Any] = {
        field: _text(raw[field], field) for field in required_text
    }
    result.update(
        {
            field: _integer(raw[field], field) for field in required_numbers
        }
    )
    result.update(
        {
            field: _proportion(raw[field], field)
            for field in required_proportions
        }
    )

    if "minimum_detectable_effect" in raw and raw["minimum_detectable_effect"] is not None:
        result["minimum_detectable_effect"] = _proportion(
            raw["minimum_detectable_effect"], "minimum_detectable_effect"
        )

    if result["control_traffic_share"] <= 0 or result["variant_traffic_share"] <= 0:
        raise AgentExecutionError("Traffic shares must be greater than zero.")
    if not math.isclose(
        result["control_traffic_share"] + result["variant_traffic_share"],
        1.0,
        rel_tol=0.0,
        abs_tol=1e-6,
    ):
        raise AgentExecutionError("Control and Variant traffic shares must sum to 100 percent.")
    return result


def calculate_ab_test_statistics(experiment_data: dict[str, Any]) -> dict[str, Any]:
    """Calculate the deterministic statistics specified by the reference code."""
    significance_alpha = 0.05
    srm_alpha = 0.01
    z_95 = 1.959963984540054
    z_power_80 = 0.8416212335729143

    n_control = _integer(experiment_data["control_sample_size"], "control_sample_size")
    x_control = _integer(experiment_data["control_successes"], "control_successes")
    n_variant = _integer(experiment_data["variant_sample_size"], "variant_sample_size")
    x_variant = _integer(experiment_data["variant_successes"], "variant_successes")
    control_share = _number(experiment_data["control_traffic_share"], "control_traffic_share")
    variant_share = _number(experiment_data["variant_traffic_share"], "variant_traffic_share")

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
        mde = abs(_number(minimum_detectable_effect, "minimum_detectable_effect"))
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


class ABTestAnalyzer:
    """Worker implementing the Main Flow of the CNL-P script."""

    def __init__(self, llm: RuntimeLLM):
        self.llm = llm

    def _extract_experiment_data(self, raw_information: str) -> dict[str, Any]:
        schema = {
            "test_name": "text",
            "hypothesis": "text",
            "variant_change": "text",
            "primary_metric": "text",
            "control_sample_size": "whole number",
            "control_successes": "whole number",
            "variant_sample_size": "whole number",
            "variant_successes": "whole number",
            "duration_days": "number",
            "control_traffic_share": "proportion from 0 to 1",
            "variant_traffic_share": "proportion from 0 to 1",
            "minimum_detectable_effect": "optional proportion from 0 to 1",
            "guardrail_information": "text, empty only when no guardrail information was provided",
        }
        prompt = (
            "Extract the aggregated binary-conversion A/B test data from the user's one message. "
            "Return JSON only with exactly these keys and types:\n"
            + json.dumps(schema, indent=2)
            + "\nUse null or omit the optional minimum_detectable_effect when it was not explicitly provided. "
            "Convert percentages to proportions: 50 percent is 0.5 and 1 percentage point is 0.01. "
            "Do not infer, calculate, or fill in any field that the user did not state. "
            "The required guardrail_information field may be an empty string when the user gave none."
        )
        extracted = self.llm.ask_json(
            STATIC_CONTEXT + "\nYou are performing the structured extraction command.",
            prompt + "\n\nUser message:\n" + raw_information,
        )
        return _normalize_experiment_data(extracted)

    def _inspect_guardrail(self, experiment_data: dict[str, Any]) -> bool:
        prompt = (
            "Inspect only the user-provided guardrail_information in this JSON. "
            "Return JSON only in the form {\"guardrail_concern\": true} or false. "
            "Set true only if the text explicitly reports meaningful degradation, a breached "
            "guardrail threshold, or another important negative effect. Small numerical differences "
            "without an explicit concern are false. Never infer a threshold or negative effect.\n\n"
            "Experiment data:\n"
            + json.dumps(experiment_data, ensure_ascii=True, indent=2)
        )
        value = self.llm.ask_json(
            STATIC_CONTEXT + "\nYou are performing the guardrail inspection command.",
            prompt,
        ).get("guardrail_concern")
        if not isinstance(value, bool):
            raise AgentExecutionError("Guardrail inspection did not return a boolean.")
        return value

    @staticmethod
    def _classify(statistics: dict[str, Any], guardrail_concern: bool) -> str:
        # This is the exact mutually exclusive order defined by COMMAND-5.
        if statistics["sample_ratio_mismatch"] is True:
            return "inconclusive"
        if statistics["statistically_significant"] is True and statistics["absolute_difference"] < 0:
            return "significant_negative"
        if (
            statistics["statistically_significant"] is True
            and statistics["absolute_difference"] > 0
            and guardrail_concern
        ):
            return "significant_positive_guardrail_concern"
        if statistics["statistically_significant"] is True and statistics["absolute_difference"] > 0:
            return "significant_positive_safe"
        if statistics["statistically_significant"] is False and statistics["absolute_difference"] > 0:
            return "not_significant_positive"
        return "not_significant_flat"

    @staticmethod
    def _recommend(outcome: str) -> str:
        return {
            "significant_positive_safe": "ship",
            "significant_positive_guardrail_concern": "investigate",
            "not_significant_positive": "extend",
            "not_significant_flat": "stop",
            "significant_negative": "dont_ship",
            "inconclusive": "undetermined",
        }[outcome]

    def _generate_analysis(
        self,
        experiment_data: dict[str, Any],
        statistics: dict[str, Any],
        guardrail_concern: bool,
        recommendation: str,
    ) -> str:
        prompt = (
            "Write the final concise A/B test analysis for product managers. Use only the supplied JSON. "
            "Include the hypothesis, duration, Control and Variant sample sizes, conversion rates, "
            "absolute difference, relative lift when available, p-value, 95% confidence interval, "
            "statistical significance, power status, sample ratio mismatch, guardrail assessment, "
            "recommendation, reasoning, and concrete next steps. Clearly distinguish proportions from "
            "percentages. Do not invent missing facts or thresholds. Report duration without claiming "
            "that it proves experiment maturity. Power status is supporting diagnostic information and "
            "must not override statistical significance. The recommendation value is authoritative.\n\n"
            "Experiment data:\n"
            + json.dumps(experiment_data, ensure_ascii=True, indent=2)
            + "\n\nStatistical result:\n"
            + json.dumps(statistics, ensure_ascii=True, indent=2)
            + "\n\nGuardrail concern: "
            + json.dumps(guardrail_concern)
            + "\nRecommendation: "
            + recommendation
        )
        analysis = self.llm.ask(
            STATIC_CONTEXT + "\nYou are performing the final analysis generation command.",
            prompt,
        )
        if not analysis:
            raise AgentExecutionError("The final analysis was empty.")
        return analysis

    def run(self) -> str:
        # COMMAND-1: exactly one input read for this execution.
        print(
            "Provide the complete A/B test information in one message, including the test name, "
            "hypothesis, tested change, primary metric, Control and Variant sample sizes and successes, "
            "duration, traffic split, optional minimum detectable effect, and guardrail information."
        )
        raw_information = input()

        experiment_data = self._extract_experiment_data(raw_information)
        statistical_result = calculate_ab_test_statistics(experiment_data)
        guardrail_concern = self._inspect_guardrail(experiment_data)
        analysis_outcome = self._classify(statistical_result, guardrail_concern)
        if analysis_outcome not in ANALYSIS_OUTCOMES:
            raise AgentExecutionError("Invalid analysis outcome.")
        recommendation = self._recommend(analysis_outcome)
        if recommendation not in RECOMMENDATIONS:
            raise AgentExecutionError("Invalid recommendation.")
        final_analysis = self._generate_analysis(
            experiment_data,
            statistical_result,
            guardrail_concern,
            recommendation,
        )
        print(final_analysis)
        return final_analysis


class ABTestAnalysisAssistant:
    """Agent initialized from the CNL-P definition."""

    def __init__(self):
        self.llm = RuntimeLLM(_runtime_config())
        self.worker = ABTestAnalyzer(self.llm)

    def run(self) -> str:
        return self.worker.run()


def main() -> str | None:
    """Initialize the Agent, execute its entry Worker, and return its result."""
    try:
        agent = ABTestAnalysisAssistant()
        return agent.run()
    except (ConfigurationError, AgentExecutionError, ValueError, KeyError) as exc:
        print(f"Agent execution error: {exc}")
        return None


if __name__ == "__main__":
    main()
