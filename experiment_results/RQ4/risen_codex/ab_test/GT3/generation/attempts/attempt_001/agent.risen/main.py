"""Terminal A/B test analysis agent.

The agent deliberately keeps statistical calculations local and deterministic.  The
language model is used only for the natural-language parts of the workflow:
extracting the user's semi-structured description, judging an explicitly stated
guardrail concern, and writing the final explanation.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any


def _read_dotenv() -> dict[str, str]:
    """Read the small set of configuration values from .env, if it exists."""

    values: dict[str, str] = {}
    dotenv_path = Path.cwd() / ".env"
    if not dotenv_path.is_file():
        return values

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def _setting(name: str, dotenv: dict[str, str]) -> str | None:
    """Environment variables take precedence over values in the local .env."""

    return os.environ.get(name) or dotenv.get(name)


def _make_client() -> tuple[Any, str]:
    """Create the official OpenAI client and resolve the required model name."""

    # Import at runtime so importing this module remains side-effect free and does
    # not require credentials.  The production path still uses the official client.
    from openai import OpenAI

    dotenv = _read_dotenv()
    api_key = _setting("OPENAI_API_KEY", dotenv)
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. Set it in .env or the environment."
        )

    model = _setting("CNLP_REFERENCE_LLM_MODEL", dotenv) or _setting(
        "OPENAI_MODEL", dotenv
    )
    if not model:
        raise RuntimeError(
            "No language model configured. Set CNLP_REFERENCE_LLM_MODEL or "
            "OPENAI_MODEL in .env or the environment."
        )

    base_url = _setting("BASE_URL", dotenv)
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url), model
    return OpenAI(api_key=api_key), model


def _ask_model(client: Any, model: str, prompt: str) -> str:
    """Make one high-reasoning Responses API call and return its text output."""

    response = client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "high"},
    )
    answer = getattr(response, "output_text", None)
    if not answer or not answer.strip():
        raise RuntimeError("The language model returned an empty response.")
    return answer.strip()


def _parse_json_object(text: str) -> dict[str, Any]:
    """Parse JSON even if a model wrapped it in a markdown code fence."""

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
        raise ValueError("Could not parse the structured model response as JSON.") from exc
    if not isinstance(value, dict):
        raise ValueError("The structured model response must be a JSON object.")
    return value


def _extract_experiment_data(client: Any, model: str, raw_information: str) -> dict[str, Any]:
    prompt = f"""
You extract one aggregated binary-conversion A/B experiment from the user's exact
semi-structured text below. Return JSON only, with exactly these keys:
test_name, hypothesis, variant_change, primary_metric, guardrail_information,
control_sample_size, control_successes, variant_sample_size, variant_successes,
duration_days, control_traffic_share, variant_traffic_share, and optionally
minimum_detectable_effect.

Rules:
- Preserve only facts explicitly provided by the user. Never guess or fill in a
  missing value. If any required field is absent or genuinely unclear, use null.
- Text fields remain text. Numeric fields are JSON numbers.
- Convert traffic percentages to proportions (50 percent is 0.5).
- Convert a percentage-point minimum detectable effect to a proportion (1
  percentage point is 0.01). A relative percentage MDE must retain its stated
  meaning; do not silently reinterpret it.
- This is aggregated data, not event-level data. Do not calculate any statistic.
- Keep the complete guardrail statement in guardrail_information.

User information:
{raw_information}
"""
    extracted = _parse_json_object(_ask_model(client, model, prompt))
    return _validate_and_normalize_extraction(extracted)


def _as_number(data: dict[str, Any], key: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Extracted field '{key}' must be a number.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Extracted field '{key}' must be finite.")
    return result


def _validate_and_normalize_extraction(data: dict[str, Any]) -> dict[str, Any]:
    required_text = (
        "test_name",
        "hypothesis",
        "variant_change",
        "primary_metric",
        "guardrail_information",
    )
    required_numbers = (
        "control_sample_size",
        "control_successes",
        "variant_sample_size",
        "variant_successes",
        "duration_days",
        "control_traffic_share",
        "variant_traffic_share",
    )

    for key in required_text:
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(
                f"The user information did not provide required field '{key}'."
            )

    normalized = dict(data)
    for key in required_numbers:
        normalized[key] = _as_number(data, key)

    # This is a defensive normalization for a model that emits the source
    # percentage despite the extraction instruction. Values already in [0, 1]
    # are left untouched.
    for key in ("control_traffic_share", "variant_traffic_share"):
        if normalized[key] > 1:
            normalized[key] /= 100.0

    if "minimum_detectable_effect" in data and data["minimum_detectable_effect"] is not None:
        normalized["minimum_detectable_effect"] = _as_number(
            data, "minimum_detectable_effect"
        )
        if normalized["minimum_detectable_effect"] > 1:
            normalized["minimum_detectable_effect"] /= 100.0
    else:
        normalized.pop("minimum_detectable_effect", None)

    for key in (
        "control_sample_size",
        "control_successes",
        "variant_sample_size",
        "variant_successes",
    ):
        number = normalized[key]
        if not number.is_integer():
            raise ValueError(f"Extracted field '{key}' must be a whole number.")
        normalized[key] = int(number)

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

    difference_standard_error = math.sqrt(
        control_rate * (1.0 - control_rate) / n_control
        + variant_rate * (1.0 - variant_rate) / n_variant
    )

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
        "confidence_interval_lower": absolute_difference - z_95 * difference_standard_error,
        "confidence_interval_upper": absolute_difference + z_95 * difference_standard_error,
        "statistically_significant": p_value < significance_alpha,
        "power_status": power_status,
        "sample_ratio_mismatch": srm_p_value < srm_alpha,
    }
    if relative_lift is not None:
        result["relative_lift"] = relative_lift
    return result


def _judge_guardrail(client: Any, model: str, guardrail_information: str) -> bool:
    prompt = f"""
Determine whether the following user-provided guardrail information explicitly
reports a meaningful negative effect, a breached guardrail threshold, or another
important degradation caused by the variant.

Return JSON only in the form {{"guardrail_concern": true}} or
{{"guardrail_concern": false}}. Use true only for an explicit report. Do not
infer a concern from a small numerical difference, an unstated threshold, a
missing value, or a generic statement that merely names a guardrail metric.

Guardrail information:
{guardrail_information}
"""
    result = _parse_json_object(_ask_model(client, model, prompt))
    value = result.get("guardrail_concern")
    if not isinstance(value, bool):
        raise ValueError("The guardrail judgment did not contain a boolean result.")
    return value


def _classify(statistical_result: dict[str, Any], guardrail_concern: bool) -> str:
    if statistical_result["sample_ratio_mismatch"]:
        return "inconclusive"
    difference = statistical_result["absolute_difference"]
    significant = statistical_result["statistically_significant"]
    if significant and difference < 0:
        return "significant_negative"
    if significant and difference > 0 and guardrail_concern:
        return "significant_positive_guardrail_concern"
    if significant and difference > 0:
        return "significant_positive_safe"
    if not significant and difference > 0:
        return "not_significant_positive"
    return "not_significant_flat"


def _recommend(outcome: str) -> str:
    return {
        "significant_positive_safe": "ship",
        "significant_positive_guardrail_concern": "investigate",
        "not_significant_positive": "extend",
        "not_significant_flat": "stop",
        "significant_negative": "dont_ship",
        "inconclusive": "undetermined",
    }.get(outcome, "undetermined")


def _generate_final_analysis(
    client: Any,
    model: str,
    experiment_data: dict[str, Any],
    statistical_result: dict[str, Any],
    guardrail_concern: bool,
    analysis_outcome: str,
    recommendation: str,
) -> str:
    prompt = f"""
Write a concise final A/B test analysis for a product manager. Use only the facts
in the JSON below; do not invent business context, thresholds, maturity claims,
or values. Clearly label or naturally include: hypothesis, duration, control and
variant sample sizes, conversion rates, absolute difference, relative lift when
present, p-value, 95% confidence interval, statistical significance, power
status, sample-ratio mismatch, guardrail assessment, recommendation, reasoning,
and next steps. Explain that power status is diagnostic and must not override
statistical significance. Report percentages with enough precision for clarity,
but retain the underlying supplied/calculated values. The recommendation and
outcome fields are authoritative: do not choose a different recommendation.

Experiment data:
{json.dumps(experiment_data, ensure_ascii=False, sort_keys=True)}

Statistical result:
{json.dumps(statistical_result, ensure_ascii=False, sort_keys=True)}

Guardrail concern: {json.dumps(guardrail_concern)}
Analysis outcome: {analysis_outcome}
Recommendation: {recommendation}
"""
    return _ask_model(client, model, prompt)


class ABTestAnalyzer:
    """Coordinate the required extraction, analysis, and recommendation steps."""

    def __init__(self) -> None:
        self.client, self.model = _make_client()

    def run(self) -> str | None:
        print(
            "Please provide the complete aggregated A/B test information in one message, "
            "including test name, hypothesis, tested change, primary metric, Control "
            "and Variant sample sizes and successes, duration, traffic split, optional "
            "minimum detectable effect, and guardrail information."
        )
        try:
            raw_information = input("> ").strip()
        except EOFError:
            print("No A/B test information was provided.")
            return None
        if not raw_information:
            print("No A/B test information was provided.")
            return None

        client = self.client
        model = self.model
        experiment_data = _extract_experiment_data(client, model, raw_information)
        statistical_result = calculate_ab_test_statistics(experiment_data)
        guardrail_concern = _judge_guardrail(
            client, model, experiment_data["guardrail_information"]
        )
        analysis_outcome = _classify(statistical_result, guardrail_concern)
        recommendation = _recommend(analysis_outcome)
        final_analysis = _generate_final_analysis(
            client,
            model,
            experiment_data,
            statistical_result,
            guardrail_concern,
            analysis_outcome,
            recommendation,
        )
        print(final_analysis)
        return final_analysis


def main() -> str | None:
    """Initialize the agent, run the terminal workflow, and return its result."""

    try:
        agent = ABTestAnalyzer()
        return agent.run()
    except (RuntimeError, ValueError, KeyError, TypeError) as exc:
        print(f"Unable to complete the A/B test analysis: {exc}")
        return None


if __name__ == "__main__":
    main()
