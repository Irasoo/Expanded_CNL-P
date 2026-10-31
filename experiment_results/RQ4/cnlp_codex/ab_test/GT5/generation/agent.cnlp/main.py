from __future__ import annotations

import json
import math
import os
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


AGENT_CONTEXT = """
You are ABTestAnalysisAssistant, responsible for analyzing aggregated binary-
conversion A/B tests and translating statistical findings into clear product
decisions for product managers and their teams.

Grounding and business rules:
- Never invent experiment data, metric values, thresholds, statistical results,
  guardrail effects, or business facts.
- The primary metric is successful conversions divided by sample size, and a
  higher value is better.
- Statistical significance uses a two-sided p-value below 0.05.
- Sample ratio mismatch (SRM) uses an SRM p-value below 0.01 and makes the
  experiment inconclusive.
- Guardrail concern exists only when the supplied guardrail information
  explicitly reports meaningful degradation, a breached threshold, or another
  important negative effect. Small numerical differences alone do not establish
  a concern unless the user explicitly characterizes them as meaningful or as a
  breach.
- Duration must be reported, but duration alone cannot establish whether the
  experiment is mature.
- Power status is diagnostic. Underpowered status does not override an already
  statistically significant result.
""".strip()


EXPERIMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "test_name": {"type": "string"},
        "hypothesis": {"type": "string"},
        "variant_change": {"type": "string"},
        "primary_metric": {"type": "string"},
        "control_sample_size": {"type": ["number", "null"]},
        "control_successes": {"type": ["number", "null"]},
        "variant_sample_size": {"type": ["number", "null"]},
        "variant_successes": {"type": ["number", "null"]},
        "duration_days": {"type": ["number", "null"]},
        "control_traffic_share": {"type": ["number", "null"]},
        "variant_traffic_share": {"type": ["number", "null"]},
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


class AgentError(RuntimeError):
    """An error that can be reported clearly to the terminal user."""


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE entries without overriding process variables."""
    if not path.is_file():
        return

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AgentError(f"Unable to read {path}: {exc}") from exc

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


class RuntimeLLM:
    def __init__(self) -> None:
        _load_dotenv()

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

        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def json_response(
        self,
        *,
        instructions: str,
        user_input: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            response = self.client.responses.create(
                model=self.model,
                reasoning={"effort": "high"},
                instructions=instructions,
                input=user_input,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "strict": True,
                        "schema": schema,
                    }
                },
            )
        except Exception as exc:
            raise AgentError(f"Runtime language-model call failed: {exc}") from exc

        output_text = getattr(response, "output_text", "")
        if not output_text or not output_text.strip():
            raise AgentError("Runtime language model returned an empty response.")

        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise AgentError("Runtime language model returned invalid JSON.") from exc
        if not isinstance(parsed, dict):
            raise AgentError("Runtime language model returned the wrong JSON value type.")
        return parsed

    def text_response(self, *, instructions: str, user_input: str) -> str:
        try:
            response = self.client.responses.create(
                model=self.model,
                reasoning={"effort": "high"},
                instructions=instructions,
                input=user_input,
            )
        except Exception as exc:
            raise AgentError(f"Runtime language-model call failed: {exc}") from exc

        output_text = getattr(response, "output_text", "")
        if not output_text or not output_text.strip():
            raise AgentError("Runtime language model returned an empty response.")
        return output_text.strip()


def _required_text(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AgentError(f"The supplied A/B test information is missing '{field}'.")
    return value.strip()


def _finite_number(data: dict[str, Any], field: str) -> float:
    value = data.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AgentError(f"'{field}' must be a number.")
    number = float(value)
    if not math.isfinite(number):
        raise AgentError(f"'{field}' must be finite.")
    return number


def _whole_number(data: dict[str, Any], field: str) -> int:
    number = _finite_number(data, field)
    if not number.is_integer():
        raise AgentError(f"'{field}' must be a whole number.")
    return int(number)


def extract_experiment_data(llm: RuntimeLLM, raw_information: str) -> dict[str, Any]:
    instructions = f"""
{AGENT_CONTEXT}

Extract the user's single-message A/B test description into the required JSON
object. Preserve only explicitly supplied information and do not calculate or
estimate missing values.

Normalization rules:
- Convert percentage traffic allocations to proportions: 50% becomes 0.5.
- Convert percentage-point or percentage-form minimum detectable effects to a
  numerical proportion: 1 percentage point becomes 0.01 and 5% becomes 0.05.
- Sample sizes and success counts are counts, not rates.
- If minimum detectable effect is not supplied, return null.
- Keep guardrail_information as a faithful concise representation of what the
  user actually said. If the user explicitly says there were no guardrails or
  no guardrail issue, preserve that statement.
- Do not substitute defaults for any required field. When a required field is
  absent, return an empty string for required text or null for a numeric field;
  downstream validation will report the missing information.
""".strip()

    extracted = llm.json_response(
        instructions=instructions,
        user_input=raw_information,
        schema_name="ab_test_experiment_data",
        schema=EXPERIMENT_SCHEMA,
    )

    normalized: dict[str, Any] = {
        "test_name": _required_text(extracted, "test_name"),
        "hypothesis": _required_text(extracted, "hypothesis"),
        "variant_change": _required_text(extracted, "variant_change"),
        "primary_metric": _required_text(extracted, "primary_metric"),
        "control_sample_size": _whole_number(extracted, "control_sample_size"),
        "control_successes": _whole_number(extracted, "control_successes"),
        "variant_sample_size": _whole_number(extracted, "variant_sample_size"),
        "variant_successes": _whole_number(extracted, "variant_successes"),
        "duration_days": _finite_number(extracted, "duration_days"),
        "control_traffic_share": _finite_number(extracted, "control_traffic_share"),
        "variant_traffic_share": _finite_number(extracted, "variant_traffic_share"),
        "guardrail_information": _required_text(extracted, "guardrail_information"),
    }

    mde = extracted.get("minimum_detectable_effect")
    if mde is not None:
        normalized["minimum_detectable_effect"] = _finite_number(
            extracted, "minimum_detectable_effect"
        )

    if normalized["duration_days"] < 0:
        raise AgentError("'duration_days' must not be negative.")

    return normalized


def calculate_ab_test_statistics(experiment_data: dict[str, Any]) -> dict[str, Any]:
    """Calculate deterministic statistics for one binary-conversion A/B test."""
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
        raise AgentError("Control and Variant sample sizes must be greater than zero.")
    if x_control < 0 or x_control > n_control:
        raise AgentError(
            "Control successes must be between 0 and the Control sample size."
        )
    if x_variant < 0 or x_variant > n_variant:
        raise AgentError(
            "Variant successes must be between 0 and the Variant sample size."
        )
    if control_share <= 0 or variant_share <= 0:
        raise AgentError("Traffic shares must be greater than zero.")
    if not math.isclose(
        control_share + variant_share, 1.0, rel_tol=0.0, abs_tol=1e-6
    ):
        raise AgentError("Control and Variant traffic shares must sum to 1.0.")

    control_rate = x_control / n_control
    variant_rate = x_variant / n_variant
    absolute_difference = variant_rate - control_rate
    relative_lift = (
        None if control_rate == 0 else absolute_difference / control_rate
    )

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
    statistically_significant = p_value < significance_alpha

    difference_standard_error = math.sqrt(
        (control_rate * (1.0 - control_rate) / n_control)
        + (variant_rate * (1.0 - variant_rate) / n_variant)
    )
    confidence_interval_lower = absolute_difference - z_95 * difference_standard_error
    confidence_interval_upper = absolute_difference + z_95 * difference_standard_error

    minimum_detectable_effect = experiment_data.get("minimum_detectable_effect")
    if minimum_detectable_effect is None:
        power_status = "unavailable"
    else:
        mde = abs(float(minimum_detectable_effect))
        if mde <= 0:
            raise AgentError("Minimum detectable effect must be greater than zero.")

        balanced_design = math.isclose(
            control_share, 0.5, rel_tol=0.0, abs_tol=1e-6
        ) and math.isclose(variant_share, 0.5, rel_tol=0.0, abs_tol=1e-6)
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

    if result["power_status"] not in POWER_STATUSES:
        raise AgentError("The statistics calculation produced an invalid power status.")
    return result


def assess_guardrail_concern(
    llm: RuntimeLLM, experiment_data: dict[str, Any]
) -> bool:
    instructions = f"""
{AGENT_CONTEXT}

Decide only whether the guardrail information explicitly indicates a meaningful
negative effect. Return true only for an explicitly reported meaningful
degradation, breached guardrail threshold, or another important negative effect.
Do not infer a threshold, practical importance, or concern from a small numerical
difference by itself. Return false when no negative effect is explicitly stated,
when the information reports no concern, or when it is neutral/unknown.
""".strip()
    payload = json.dumps(
        {"guardrail_information": experiment_data["guardrail_information"]},
        ensure_ascii=False,
    )
    result = llm.json_response(
        instructions=instructions,
        user_input=payload,
        schema_name="guardrail_assessment",
        schema=GUARDRAIL_SCHEMA,
    )
    concern = result.get("guardrail_concern")
    if not isinstance(concern, bool):
        raise AgentError("Guardrail assessment returned an invalid boolean value.")
    return concern


def classify_outcome(
    statistical_result: dict[str, Any], guardrail_concern: bool
) -> str:
    significant = statistical_result["statistically_significant"]
    difference = statistical_result["absolute_difference"]

    if statistical_result["sample_ratio_mismatch"]:
        outcome = "inconclusive"
    elif significant and difference < 0:
        outcome = "significant_negative"
    elif significant and difference > 0 and guardrail_concern:
        outcome = "significant_positive_guardrail_concern"
    elif significant and difference > 0:
        outcome = "significant_positive_safe"
    elif not significant and difference > 0:
        outcome = "not_significant_positive"
    else:
        outcome = "not_significant_flat"

    if outcome not in ANALYSIS_OUTCOMES:
        raise AgentError("Outcome classification produced an invalid value.")
    return outcome


def recommendation_for(outcome: str) -> str:
    recommendation = {
        "significant_positive_safe": "ship",
        "significant_positive_guardrail_concern": "investigate",
        "not_significant_positive": "extend",
        "not_significant_flat": "stop",
        "significant_negative": "dont_ship",
        "inconclusive": "undetermined",
    }[outcome]
    if recommendation not in RECOMMENDATIONS:
        raise AgentError("Recommendation mapping produced an invalid value.")
    return recommendation


def generate_final_analysis(
    llm: RuntimeLLM,
    experiment_data: dict[str, Any],
    statistical_result: dict[str, Any],
    guardrail_concern: bool,
    recommendation: str,
) -> str:
    instructions = f"""
{AGENT_CONTEXT}

Write a concise, decision-ready A/B test analysis for a product manager. Use the
same natural language as the supplied experiment text when that language is
clear. Include all of the following:
- test name, hypothesis, tested variant change, and primary metric;
- duration, Control/Variant sample sizes, and success counts;
- Control and Variant conversion rates;
- absolute difference and relative lift when present;
- two-sided p-value and 95% confidence interval for Variant minus Control;
- statistical-significance status, power status, and SRM status;
- guardrail assessment;
- the exact supplied product recommendation, with grounded reasoning;
- concrete next steps consistent with that recommendation.

Format proportions as readable percentages while retaining enough precision to
avoid changing the result. Clearly state that the confidence interval is Variant
minus Control. Do not invent thresholds, business impact, experiment maturity,
or facts. Do not let underpowered status override statistical significance. If
SRM is present, explain that the result is inconclusive. The recommendation enum
"dont_ship" should be presented naturally as "do not ship" in prose.
""".strip()
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
    return llm.text_response(instructions=instructions, user_input=payload)


class ABTestAnalyzer:
    def __init__(self, llm: RuntimeLLM) -> None:
        self.llm = llm

    def run(self) -> str:
        print(
            "Provide the complete aggregated A/B test information in one message: "
            "test name, hypothesis, tested change, primary metric, Control sample "
            "size and successes, Variant sample size and successes, duration, "
            "traffic split, minimum detectable effect if available, and guardrail "
            "information."
        )
        raw_ab_test_information = input("> ")
        if not raw_ab_test_information.strip():
            raise AgentError("No A/B test information was provided.")

        experiment_data = extract_experiment_data(
            self.llm, raw_ab_test_information.strip()
        )
        statistical_result = calculate_ab_test_statistics(experiment_data)
        guardrail_concern = assess_guardrail_concern(self.llm, experiment_data)
        analysis_outcome = classify_outcome(statistical_result, guardrail_concern)
        recommendation = recommendation_for(analysis_outcome)
        final_analysis = generate_final_analysis(
            self.llm,
            experiment_data,
            statistical_result,
            guardrail_concern,
            recommendation,
        )
        print(final_analysis)
        return final_analysis


def main() -> str:
    """Initialize the agent, run its entry worker, and return the final result."""
    agent = ABTestAnalyzer(RuntimeLLM())
    return agent.run()


if __name__ == "__main__":
    try:
        main()
    except (AgentError, EOFError, KeyboardInterrupt) as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc
