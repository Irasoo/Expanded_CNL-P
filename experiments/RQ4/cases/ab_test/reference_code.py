from cnlp_compiler.code_generator.reference_code_catalog import (
    register_function,
)


@register_function(
    description=(
        "Calculate deterministic statistical results for a binary-conversion "
        "A/B test, including conversion rates, absolute difference, relative "
        "lift when defined, two-sided p-value, 95% confidence interval, "
        "sample-size adequacy, and sample ratio mismatch."
    )
)
def calculate_ab_test_statistics(experiment_data: dict) -> dict:
    """
    Calculate deterministic statistics for one binary-conversion A/B test.

    Statistical conventions:
        significance alpha = 0.05, two-sided
        confidence level = 95%
        target power = 0.80
        SRM alpha = 0.01

    Sample-size adequacy uses the standard balanced two-group normal
    approximation. For intentionally non-50/50 experiments, power_status
    is returned as unavailable.
    """

    import math

    SIGNIFICANCE_ALPHA = 0.05
    SRM_ALPHA = 0.01

    Z_95 = 1.959963984540054
    Z_POWER_80 = 0.8416212335729143

    # Read and validate the aggregated experiment input.
    n_control = int(experiment_data["control_sample_size"])
    x_control = int(experiment_data["control_successes"])

    n_variant = int(experiment_data["variant_sample_size"])
    x_variant = int(experiment_data["variant_successes"])

    control_share = float(experiment_data["control_traffic_share"])
    variant_share = float(experiment_data["variant_traffic_share"])

    if n_control <= 0 or n_variant <= 0:
        raise ValueError(
            "Control and Variant sample sizes must be greater than zero."
        )

    if x_control < 0 or x_control > n_control:
        raise ValueError(
            "Control successes must be between 0 and the Control sample size."
        )

    if x_variant < 0 or x_variant > n_variant:
        raise ValueError(
            "Variant successes must be between 0 and the Variant sample size."
        )

    if control_share <= 0 or variant_share <= 0:
        raise ValueError("Traffic shares must be greater than zero.")

    if not math.isclose(
        control_share + variant_share,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-6,
    ):
        raise ValueError(
            "Control and Variant traffic shares must sum to 1.0."
        )

    # Calculate conversion rates and observed effect.
    control_rate = x_control / n_control
    variant_rate = x_variant / n_variant
    absolute_difference = variant_rate - control_rate

    if control_rate == 0:
        relative_lift = None
    else:
        relative_lift = absolute_difference / control_rate

    # Two-sided two-proportion z-test.
    pooled_rate = (
        (x_control + x_variant)
        / (n_control + n_variant)
    )

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

    statistically_significant = p_value < SIGNIFICANCE_ALPHA

    # Unpooled 95% confidence interval for Variant minus Control.
    difference_standard_error = math.sqrt(
        (
            control_rate
            * (1.0 - control_rate)
            / n_control
        )
        +
        (
            variant_rate
            * (1.0 - variant_rate)
            / n_variant
        )
    )

    confidence_interval_lower = (
        absolute_difference
        - Z_95 * difference_standard_error
    )
    confidence_interval_upper = (
        absolute_difference
        + Z_95 * difference_standard_error
    )

    # Sample-size adequacy is diagnostic and never overrides significance.
    minimum_detectable_effect = experiment_data.get(
        "minimum_detectable_effect"
    )

    if minimum_detectable_effect is None:
        power_status = "unavailable"
    else:
        mde = abs(float(minimum_detectable_effect))

        if mde <= 0:
            raise ValueError(
                "Minimum detectable effect must be greater than zero."
            )

        balanced_design = (
            math.isclose(
                control_share,
                0.5,
                rel_tol=0.0,
                abs_tol=1e-6,
            )
            and math.isclose(
                variant_share,
                0.5,
                rel_tol=0.0,
                abs_tol=1e-6,
            )
        )
        expected_variant_rate = control_rate + mde

        if not balanced_design or expected_variant_rate >= 1.0:
            power_status = "unavailable"
        else:
            average_rate = (
                control_rate + expected_variant_rate
            ) / 2.0

            numerator = (
                Z_95
                * math.sqrt(
                    2.0
                    * average_rate
                    * (1.0 - average_rate)
                )
                +
                Z_POWER_80
                * math.sqrt(
                    control_rate
                    * (1.0 - control_rate)
                    +
                    expected_variant_rate
                    * (1.0 - expected_variant_rate)
                )
            ) ** 2

            required_sample_per_group = numerator / (mde ** 2)

            if (
                n_control >= required_sample_per_group
                and n_variant >= required_sample_per_group
            ):
                power_status = "adequate"
            else:
                power_status = "underpowered"

    # Chi-square goodness-of-fit test for sample ratio mismatch.
    total_sample_size = n_control + n_variant
    expected_control = total_sample_size * control_share
    expected_variant = total_sample_size * variant_share

    chi_square_statistic = (
        ((n_control - expected_control) ** 2) / expected_control
        + ((n_variant - expected_variant) ** 2) / expected_variant
    )
    srm_p_value = math.erfc(
        math.sqrt(chi_square_statistic / 2.0)
    )
    sample_ratio_mismatch = srm_p_value < SRM_ALPHA

    result = {
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
