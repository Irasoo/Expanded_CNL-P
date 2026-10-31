from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Any


SIGNIFICANCE_ALPHA = 0.05
SRM_ALPHA = 0.01
Z_95 = 1.959963984540054
Z_POWER_80 = 0.8416212335729143


def _load_dotenv() -> None:
    """Load simple KEY=VALUE entries without overwriting process variables."""
    dotenv_path = Path.cwd() / ".env"
    if not dotenv_path.is_file():
        return

    try:
        lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"Unable to read .env: {exc}") from exc

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
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def _create_client_and_model() -> tuple[Any, str]:
    _load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("BASE_URL")
    model = os.environ.get("CNLP_REFERENCE_LLM_MODEL") or os.environ.get(
        "OPENAI_MODEL"
    )

    missing = []
    if not api_key:
        missing.append("OPENAI_API_KEY")
    if not base_url:
        missing.append("BASE_URL")
    if not model:
        missing.append("CNLP_REFERENCE_LLM_MODEL 或 OPENAI_MODEL")
    if missing:
        raise RuntimeError(
            "缺少运行时模型配置：" + ", ".join(missing) + "。"
            "请在当前进程环境变量或当前目录的 .env 中设置。"
        )

    from openai import OpenAI

    return OpenAI(api_key=api_key, base_url=base_url), model


def _call_json(
    client: Any,
    model: str,
    system_prompt: str,
    user_prompt: str,
    schema_name: str,
    schema: dict[str, Any],
) -> dict[str, Any]:
    try:
        response = client.responses.create(
            model=model,
            reasoning={"effort": "high"},
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
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
        raise RuntimeError(f"运行时语言模型调用失败：{exc}") from exc

    output_text = getattr(response, "output_text", None)
    if not output_text:
        raise RuntimeError("运行时语言模型未返回可解析的文本结果。")
    try:
        result = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("运行时语言模型返回的结果不是合法 JSON。") from exc
    if not isinstance(result, dict):
        raise RuntimeError("运行时语言模型返回的 JSON 顶层结构不是对象。")
    return result


def _number(value: Any, field_name: str, *, integer: bool = False) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"字段 {field_name} 必须是数字。")
    if not math.isfinite(float(value)):
        raise ValueError(f"字段 {field_name} 必须是有限数字。")
    if integer:
        if float(value) != int(value):
            raise ValueError(f"字段 {field_name} 必须是整数。")
        return int(value)
    return float(value)


def _validate_experiment_data(data: dict[str, Any]) -> dict[str, Any]:
    required_text = (
        "test_name",
        "hypothesis",
        "variant_change",
        "primary_metric",
        "guardrail_information",
    )
    for field_name in required_text:
        value = data.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"无法从输入中提取必填文本字段：{field_name}。")

    validated: dict[str, Any] = {
        field_name: data[field_name].strip() for field_name in required_text
    }
    integer_fields = (
        "control_sample_size",
        "control_successes",
        "variant_sample_size",
        "variant_successes",
    )
    for field_name in integer_fields:
        validated[field_name] = _number(data.get(field_name), field_name, integer=True)

    for field_name in ("duration_days", "control_traffic_share", "variant_traffic_share"):
        validated[field_name] = _number(data.get(field_name), field_name)

    mde = data.get("minimum_detectable_effect")
    validated["minimum_detectable_effect"] = (
        None if mde is None else _number(mde, "minimum_detectable_effect")
    )

    if validated["control_sample_size"] <= 0 or validated["variant_sample_size"] <= 0:
        raise ValueError("Control 和 Variant 样本量必须大于零。")
    if not 0 <= validated["control_successes"] <= validated["control_sample_size"]:
        raise ValueError("Control successes 必须在 0 和 Control sample size 之间。")
    if not 0 <= validated["variant_successes"] <= validated["variant_sample_size"]:
        raise ValueError("Variant successes 必须在 0 和 Variant sample size 之间。")
    if validated["duration_days"] < 0:
        raise ValueError("duration_days 不能为负数。")
    control_share = validated["control_traffic_share"]
    variant_share = validated["variant_traffic_share"]
    if control_share <= 0 or variant_share <= 0:
        raise ValueError("Traffic shares 必须大于零。")
    if not math.isclose(control_share + variant_share, 1.0, abs_tol=1e-6):
        raise ValueError("Control 和 Variant traffic shares 必须加总为 1.0。")
    if validated["minimum_detectable_effect"] is not None and validated[
        "minimum_detectable_effect"
    ] <= 0:
        raise ValueError("minimum_detectable_effect 必须大于零。")
    return validated


def calculate_ab_test_statistics(experiment_data: dict[str, Any]) -> dict[str, Any]:
    """Calculate deterministic binary-conversion A/B test statistics."""
    n_control = int(experiment_data["control_sample_size"])
    x_control = int(experiment_data["control_successes"])
    n_variant = int(experiment_data["variant_sample_size"])
    x_variant = int(experiment_data["variant_successes"])
    control_share = float(experiment_data["control_traffic_share"])
    variant_share = float(experiment_data["variant_traffic_share"])

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
    confidence_interval_lower = absolute_difference - Z_95 * difference_standard_error
    confidence_interval_upper = absolute_difference + Z_95 * difference_standard_error

    mde = experiment_data.get("minimum_detectable_effect")
    if mde is None:
        power_status = "unavailable"
    else:
        balanced_design = math.isclose(control_share, 0.5, abs_tol=1e-6) and math.isclose(
            variant_share, 0.5, abs_tol=1e-6
        )
        expected_variant_rate = control_rate + abs(float(mde))
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
            required_sample_per_group = numerator / (float(mde) ** 2)
            power_status = (
                "adequate"
                if n_control >= required_sample_per_group
                and n_variant >= required_sample_per_group
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
        "statistically_significant": p_value < SIGNIFICANCE_ALPHA,
        "power_status": power_status,
        "sample_ratio_mismatch": srm_p_value < SRM_ALPHA,
    }
    if relative_lift is not None:
        result["relative_lift"] = relative_lift
    return result


def _extract_experiment_data(client: Any, model: str, raw_information: str) -> dict[str, Any]:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
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
        },
        "required": [
            "test_name",
            "hypothesis",
            "variant_change",
            "primary_metric",
            "guardrail_information",
            "control_sample_size",
            "control_successes",
            "variant_sample_size",
            "variant_successes",
            "duration_days",
            "control_traffic_share",
            "variant_traffic_share",
            "minimum_detectable_effect",
        ],
    }
    system_prompt = (
        "你是 ABTestAnalysisAssistant 的数据抽取模块。只从用户原文提取信息，"
        "不要补充、猜测或改写事实。交通分配和 MDE 必须归一化为比例："
        "50 percent traffic 是 0.5，1 percentage point MDE 是 0.01。"
        "若字段未提供，返回 null。保留 guardrail_information 的完整语义信息。"
        "只返回符合 JSON schema 的对象。"
    )
    result = _call_json(
        client,
        model,
        system_prompt,
        raw_information,
        "ab_test_experiment_data",
        schema,
    )
    return _validate_experiment_data(result)


def _assess_guardrail(client: Any, model: str, guardrail_information: str) -> bool:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"guardrail_concern": {"type": "boolean"}},
        "required": ["guardrail_concern"],
    }
    system_prompt = (
        "你负责判断 A/B 测试 guardrail 信息。仅当原文明确报告了有意义的下降、"
        "guardrail 阈值被突破、或其他重要负面影响时返回 true；否则返回 false。"
        "不要从小数值差异、缺少信息或自行发明阈值推断 concern。只返回 JSON。"
    )
    result = _call_json(
        client,
        model,
        system_prompt,
        guardrail_information,
        "guardrail_assessment",
        schema,
    )
    if not isinstance(result.get("guardrail_concern"), bool):
        raise RuntimeError("guardrail 语义判断返回了无效布尔值。")
    return result["guardrail_concern"]


def _classify(statistical_result: dict[str, Any], guardrail_concern: bool) -> tuple[str, str]:
    if statistical_result["sample_ratio_mismatch"]:
        outcome = "inconclusive"
    elif (
        statistical_result["statistically_significant"]
        and statistical_result["absolute_difference"] < 0
    ):
        outcome = "significant_negative"
    elif (
        statistical_result["statistically_significant"]
        and statistical_result["absolute_difference"] > 0
        and guardrail_concern
    ):
        outcome = "significant_positive_guardrail_concern"
    elif (
        statistical_result["statistically_significant"]
        and statistical_result["absolute_difference"] > 0
    ):
        outcome = "significant_positive_safe"
    elif (
        not statistical_result["statistically_significant"]
        and statistical_result["absolute_difference"] > 0
    ):
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


def _generate_final_analysis(
    client: Any,
    model: str,
    experiment_data: dict[str, Any],
    statistical_result: dict[str, Any],
    guardrail_concern: bool,
    analysis_outcome: str,
    recommendation: str,
) -> str:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"final_analysis": {"type": "string"}},
        "required": ["final_analysis"],
    }
    payload = {
        "experiment_data": experiment_data,
        "statistical_result": statistical_result,
        "guardrail_concern": guardrail_concern,
        "analysis_outcome": analysis_outcome,
        "recommendation": recommendation,
    }
    system_prompt = (
        "你是 ABTestAnalysisAssistant。根据给定的实验数据和确定性统计结果，"
        "生成简洁但完整的 A/B 测试分析。必须包含：hypothesis、duration、两组样本量、"
        "conversion rates、absolute difference、可用时的 relative lift、p-value、"
        "confidence interval、statistical significance、power status、sample ratio mismatch、"
        "guardrail assessment、recommendation、reasoning 和 next steps。"
        "只能使用提供的数据和结果，不得创造业务事实、阈值或统计数字。"
        "power status 只能作为限制或辅助信息，不能覆盖统计显著性。"
        "明确说明推荐结论。使用清晰的纯文本或 Markdown，使用输入中的语言。只返回 JSON。"
    )
    result = _call_json(
        client,
        model,
        system_prompt,
        json.dumps(payload, ensure_ascii=False, indent=2),
        "ab_test_final_analysis",
        schema,
    )
    final_analysis = result.get("final_analysis")
    if not isinstance(final_analysis, str) or not final_analysis.strip():
        raise RuntimeError("最终分析生成结果为空。")
    return final_analysis.strip()


def main() -> str | None:
    print(
        "请在一条消息中提供完整的 A/B 测试信息：测试名称、假设、测试变更、"
        "primary metric、Control/Variant 样本量与成功数、实验时长、流量分配、"
        "可选的 minimum detectable effect，以及 guardrail 信息。"
    )
    try:
        raw_information = input("> ").strip()
    except EOFError:
        print("错误：未读取到 A/B 测试信息。")
        return None
    if not raw_information:
        print("错误：A/B 测试信息不能为空。")
        return None

    try:
        client, model = _create_client_and_model()
        experiment_data = _extract_experiment_data(client, model, raw_information)
        statistical_result = calculate_ab_test_statistics(experiment_data)
        guardrail_concern = _assess_guardrail(
            client, model, experiment_data["guardrail_information"]
        )
        analysis_outcome, recommendation = _classify(
            statistical_result, guardrail_concern
        )
        final_analysis = _generate_final_analysis(
            client,
            model,
            experiment_data,
            statistical_result,
            guardrail_concern,
            analysis_outcome,
            recommendation,
        )
    except (RuntimeError, ValueError, KeyError, ZeroDivisionError) as exc:
        print(f"错误：{exc}")
        return None

    print("\n" + final_analysis)
    return final_analysis


if __name__ == "__main__":
    main()
