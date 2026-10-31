from __future__ import annotations

import json
import math
import os
import re
from typing import Any

from openai import OpenAI


def _load_dotenv() -> None:
    """Load a small .env file without overwriting process environment values."""
    path = os.path.join(os.getcwd(), ".env")
    try:
        with open(path, "r", encoding="utf-8") as env_file:
            lines = env_file.readlines()
    except FileNotFoundError:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if name and name not in os.environ:
            os.environ[name] = value


def _required_configuration() -> tuple[str, str, str]:
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
        raise RuntimeError("Missing runtime configuration: " + ", ".join(missing))
    return api_key, base_url, model


def _json_from_text(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        positions = [position for position in (cleaned.find("{"), cleaned.find("[")) if position >= 0]
        start = min(positions, default=-1)
        if start < 0:
            raise ValueError("The language model did not return valid JSON.")
        try:
            return json.JSONDecoder().raw_decode(cleaned[start:])[0]
        except json.JSONDecodeError as exc:
            raise ValueError("The language model returned malformed JSON.") from exc


def _as_number(value: Any, field: str, allow_none: bool = False) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a number.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number explicitly present in the input.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite.")
    return result


def calculate_ab_test_statistics(experiment_data: dict[str, Any]) -> dict[str, Any]:
    """Calculate the deterministic binary-conversion A/B test statistics."""
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
    ci_lower = absolute_difference - z_95 * difference_se
    ci_upper = absolute_difference + z_95 * difference_se

    mde = experiment_data.get("minimum_detectable_effect")
    if mde is None:
        power_status = "unavailable"
    else:
        mde = abs(float(mde))
        if mde <= 0:
            raise ValueError("Minimum detectable effect must be greater than zero.")
        balanced = math.isclose(control_share, 0.5, rel_tol=0.0, abs_tol=1e-6) and math.isclose(variant_share, 0.5, rel_tol=0.0, abs_tol=1e-6)
        expected_variant_rate = control_rate + mde
        if not balanced or expected_variant_rate >= 1.0:
            power_status = "unavailable"
        else:
            average_rate = (control_rate + expected_variant_rate) / 2.0
            numerator = (
                z_95 * math.sqrt(2.0 * average_rate * (1.0 - average_rate))
                + z_power_80 * math.sqrt(control_rate * (1.0 - control_rate) + expected_variant_rate * (1.0 - expected_variant_rate))
            ) ** 2
            required_per_group = numerator / (mde ** 2)
            power_status = "adequate" if n_control >= required_per_group and n_variant >= required_per_group else "underpowered"

    total = n_control + n_variant
    expected_control = total * control_share
    expected_variant = total * variant_share
    chi_square = ((n_control - expected_control) ** 2) / expected_control + ((n_variant - expected_variant) ** 2) / expected_variant
    srm_p_value = math.erfc(math.sqrt(chi_square / 2.0))

    result = {
        "control_conversion_rate": control_rate,
        "variant_conversion_rate": variant_rate,
        "absolute_difference": absolute_difference,
        "p_value": p_value,
        "confidence_interval_lower": ci_lower,
        "confidence_interval_upper": ci_upper,
        "statistically_significant": statistically_significant,
        "power_status": power_status,
        "sample_ratio_mismatch": srm_p_value < srm_alpha,
    }
    if relative_lift is not None:
        result["relative_lift"] = relative_lift
    return result


class ABTestAnalysisAssistant:
    def __init__(self) -> None:
        api_key, base_url, model = _required_configuration()
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def _ask_model(self, instructions: str, user_content: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=user_content,
            reasoning={"effort": "high"},
        )
        text = getattr(response, "output_text", None)
        if not text or not text.strip():
            raise RuntimeError("The language model returned an empty response.")
        return text.strip()

    def _extract_experiment_data(self, raw_information: str) -> dict[str, Any]:
        instructions = """You extract structured data from one user's A/B test description.
Return JSON only, with exactly these keys: test_name, hypothesis, variant_change,
primary_metric, guardrail_information, control_sample_size, control_successes,
variant_sample_size, variant_successes, duration_days, control_traffic_share,
variant_traffic_share, minimum_detectable_effect. Use null for any field not
explicitly supplied; never infer, calculate, or invent missing business facts.
The four counts and duration are numbers. Convert traffic percentages to
proportions (a percentage sign means divide by 100), and convert a stated
percentage-point MDE to a proportion; preserve an already proportional numeric
value. A traffic split must represent the two explicitly stated Control and
Variant shares. Keep guardrail_information as a faithful concise text extract,
or null if none was supplied."""
        parsed = _json_from_text(self._ask_model(instructions, raw_information))
        if not isinstance(parsed, dict):
            raise ValueError("The extracted experiment data is not a JSON object.")
        required_text = ["test_name", "hypothesis", "variant_change", "primary_metric", "guardrail_information"]
        required_numbers = ["control_sample_size", "control_successes", "variant_sample_size", "variant_successes", "duration_days", "control_traffic_share", "variant_traffic_share"]
        missing = [field for field in required_text + required_numbers if parsed.get(field) is None]
        if missing:
            raise ValueError("The user input is missing required fields: " + ", ".join(missing))
        for field in required_numbers:
            parsed[field] = _as_number(parsed[field], field)
        if parsed.get("minimum_detectable_effect") is not None:
            parsed["minimum_detectable_effect"] = _as_number(parsed["minimum_detectable_effect"], "minimum_detectable_effect", allow_none=True)
        for field in required_text:
            if not isinstance(parsed[field], str) or not parsed[field].strip():
                raise ValueError(f"{field} must be explicitly provided as text.")
            parsed[field] = parsed[field].strip()
        return parsed

    def _guardrail_concern(self, experiment_data: dict[str, Any]) -> bool:
        instructions = """Determine whether the supplied guardrail text explicitly reports meaningful
degradation, a breached guardrail threshold, or another important negative effect.
Return JSON only in the form {\"guardrail_concern\": true or false}. Use false
when the text is absent, neutral, positive, ambiguous, or merely reports a small
numeric difference without an explicit meaningful concern. Do not invent thresholds
or negative effects."""
        payload = json.dumps({"guardrail_information": experiment_data["guardrail_information"]}, ensure_ascii=False)
        parsed = _json_from_text(self._ask_model(instructions, payload))
        if not isinstance(parsed, dict) or not isinstance(parsed.get("guardrail_concern"), bool):
            raise ValueError("The language model returned an invalid guardrail assessment.")
        return parsed["guardrail_concern"]

    @staticmethod
    def _classify(statistics: dict[str, Any], guardrail_concern: bool) -> str:
        if statistics["sample_ratio_mismatch"]:
            return "inconclusive"
        if statistics["statistically_significant"] and statistics["absolute_difference"] < 0:
            return "significant_negative"
        if statistics["statistically_significant"] and statistics["absolute_difference"] > 0 and guardrail_concern:
            return "significant_positive_guardrail_concern"
        if statistics["statistically_significant"] and statistics["absolute_difference"] > 0:
            return "significant_positive_safe"
        if not statistics["statistically_significant"] and statistics["absolute_difference"] > 0:
            return "not_significant_positive"
        return "not_significant_flat"

    @staticmethod
    def _recommend(analysis_outcome: str) -> str:
        return {
            "significant_positive_safe": "ship",
            "significant_positive_guardrail_concern": "investigate",
            "not_significant_positive": "extend",
            "not_significant_flat": "stop",
            "significant_negative": "dont_ship",
        }.get(analysis_outcome, "undetermined")

    def _final_analysis(self, data: dict[str, Any], statistics: dict[str, Any], guardrail_concern: bool, recommendation: str) -> str:
        instructions = """Write a concise final A/B test analysis in plain text for a product manager.
Use only facts in the supplied JSON; do not invent thresholds, business facts, or
missing values. Include hypothesis, duration, both sample sizes, conversion rates,
absolute difference, relative lift when present, p-value, 95% confidence interval,
statistical significance, power status, sample-ratio mismatch, guardrail assessment,
the exact recommendation, reasoning, and practical next steps. Explain that power
status is diagnostic only and must not override significance. Mention if a metric
is unavailable. Do not output JSON or a preamble about being an AI."""
        payload = json.dumps({"experiment_data": data, "statistical_result": statistics, "guardrail_concern": guardrail_concern, "recommendation": recommendation}, ensure_ascii=False, indent=2)
        return self._ask_model(instructions, payload)

    def run(self) -> str:
        raw_information = input("请在一条消息中提供完整的 A/B 测试信息：")
        if not raw_information.strip():
            raise ValueError("A/B test information cannot be empty.")
        experiment_data = self._extract_experiment_data(raw_information)
        statistical_result = calculate_ab_test_statistics(experiment_data)
        guardrail_concern = self._guardrail_concern(experiment_data)
        analysis_outcome = self._classify(statistical_result, guardrail_concern)
        recommendation = self._recommend(analysis_outcome)
        return self._final_analysis(experiment_data, statistical_result, guardrail_concern, recommendation)


def main() -> str | None:
    try:
        result = ABTestAnalysisAssistant().run()
        print(result)
        return result
    except (ValueError, RuntimeError, KeyError, TypeError) as exc:
        message = f"A/B test analysis failed: {exc}"
        print(message)
        return None
    except Exception as exc:
        message = f"A/B test analysis failed due to an unexpected error: {exc}"
        print(message)
        return None


if __name__ == "__main__":
    main()
