"""Shared variable selection and LLM-decision parsing for analyzers."""

from __future__ import annotations

import json
from typing import Any

from ...schema import VariableNode
from ...utils import extract_single_json_from_text


def select_variables(
    variable_names: list[str],
    variables: list[VariableNode],
) -> list[VariableNode]:
    selected_names = set(variable_names)
    return [
        variable
        for variable in variables
        if variable["variable_name"] in selected_names
    ]


def parse_boolean_decision(
    *,
    response: str,
    expected_keys: tuple[str, ...],
    controlling_key: str | None = None,
) -> dict[str, bool]:
    return validate_boolean_decision(
        parse_json_object_response(response),
        expected_keys=expected_keys,
        controlling_key=controlling_key,
    )


def parse_json_object_response(response: str) -> dict[str, Any]:
    if not isinstance(response, str):
        raise ValueError("The LLM response must be a JSON string.")

    try:
        decision = json.loads(response)
    except json.JSONDecodeError:
        try:
            decision = extract_single_json_from_text(response)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"The LLM response contains invalid JSON: {response!r}"
            ) from exc

    if not isinstance(decision, dict):
        raise ValueError(
            f"The LLM response does not contain a JSON object: {response!r}"
        )

    return decision


def parse_json_array_response(response: str) -> list[Any]:
    """Parse a model response whose top-level JSON value must be an array."""
    if not isinstance(response, str):
        raise ValueError("The LLM response must be a JSON string.")

    try:
        decision = json.loads(response)
    except json.JSONDecodeError:
        try:
            decision = extract_single_json_from_text(response)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"The LLM response contains invalid JSON: {response!r}"
            ) from exc

    if not isinstance(decision, list):
        raise ValueError(
            f"The LLM response does not contain a JSON array: {response!r}"
        )

    return decision


def validate_boolean_decision(
    decision: Any,
    *,
    expected_keys: tuple[str, ...],
    controlling_key: str | None = None,
) -> dict[str, bool]:
    if not isinstance(decision, dict):
        raise ValueError("The LLM decision must be a JSON object.")

    if set(decision) != set(expected_keys):
        raise ValueError(
            "The LLM response must contain exactly these fields: "
            f"{list(expected_keys)!r}; received: {list(decision)!r}"
        )

    for key in expected_keys:
        if type(decision[key]) is not bool:
            raise ValueError(
                f"The LLM response field {key!r} must be a boolean."
            )

    if (
        controlling_key is not None
        and not decision[controlling_key]
        and decision["llm_based"]
    ):
        raise ValueError(
            f"When {controlling_key}=false, llm_based must be false."
        )

    return {key: decision[key] for key in expected_keys}
