from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

try:
    from ..utils import extract_single_json_from_text
except ImportError:  # Supports legacy top-level ``flow_binder`` imports.
    from utils import extract_single_json_from_text

__all__ = ["bind_alternative_flow"]


try:
    from ..prompts.flow_binder import ALTERNATIVE_FLOW_SYSTEM_PROMPT as _SYSTEM_PROMPT
except ImportError:  # Supports legacy top-level package imports.
    from prompts.flow_binder import ALTERNATIVE_FLOW_SYSTEM_PROMPT as _SYSTEM_PROMPT


def bind_alternative_flow(
    *,
    main_flow: dict[str, Any],
    alternative_flow: dict[str, Any],
    command_indices: set[int],
    decision_indices: set[int],
    max_retries: int = 2,
    model_response: Callable[[list[dict[str, str]]], str] | None = None,
) -> dict[str, Any]:
    """
    Bind one alternative flow to main_flow.

    This is the only public entry point of this module.
    """
    if not isinstance(main_flow, dict):
        raise TypeError("main_flow must be a JSON object.")
    if not isinstance(alternative_flow, dict):
        raise TypeError("alternative_flow must be a JSON object.")
    if max_retries < 0:
        raise ValueError("max_retries must be non-negative.")

    user_input = _build_user_input(
        main_flow=main_flow,
        alternative_flow=alternative_flow,
    )

    last_error: str | None = None
    for _ in range(max_retries + 1):
        try:
            result = _request_json(
                user_input=user_input,
                previous_error=last_error,
                model_response=model_response,
            )
            return _validate_binding(
                result,
                command_indices=command_indices,
                decision_indices=decision_indices,
            )
        except (TypeError, ValueError) as exc:
            last_error = str(exc)

    raise ValueError(
        "Failed to obtain a valid alternative-flow binding. "
        f"Last validation error: {last_error}"
    )


def _request_json(
    *,
    user_input: str,
    previous_error: str | None,
    model_response: Callable[[list[dict[str, str]]], str] | None,
) -> Any:
    if model_response is None:
        try:
            from ..utils.llm import (
                create_prompt_section,
                get_model_response,
            )
        except ImportError:
            from utils.llm import (
                create_prompt_section,
                get_model_response,
            )

        response_function = get_model_response
        make_section = create_prompt_section
    else:
        response_function = model_response

        def make_section(role: str, content: str) -> dict[str, str]:
            return {"role": role, "content": content}

    retry_input = user_input
    if previous_error:
        retry_input += (
            "\n\n上一轮输出未通过确定性校验：\n"
            f"{previous_error}\n"
            "请重新检查 AST 中真实存在的索引及其语义关系，并只输出合法 JSON。"
        )

    messages = [
        make_section(role="system", content=_SYSTEM_PROMPT),
        make_section(role="user", content=retry_input),
    ]

    try:
        raw_response = response_function(messages)
        parsed = extract_single_json_from_text(raw_response)
    except Exception as exc:
        # Preserve the structured transient-failure signal emitted by the LLM
        # client. RQ4 needs the original exception type to decide whether the
        # whole compilation may be retried. Model-output/validation failures
        # below remain ordinary ValueError compilation failures.
        try:
            from ..utils.llm import RetryableLLMRequestError
        except ImportError:
            from utils.llm import RetryableLLMRequestError
        if isinstance(exc, RetryableLLMRequestError):
            raise
        raise ValueError(
            "Alternative-flow binding request failed: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if parsed is None:
        raise ValueError("The model response did not contain valid JSON.")

    return parsed


def _validate_binding(
    value: Any,
    *,
    command_indices: set[int],
    decision_indices: set[int],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("Alternative-flow binding must be a JSON object.")

    if set(value) != {"trigger_is", "go_back_to"}:
        raise ValueError(
            "Alternative-flow binding must contain exactly "
            "trigger_is and go_back_to."
        )

    trigger_is = _validate_trigger_list(
        value["trigger_is"],
        command_indices=command_indices,
    )
    go_back_to = _validate_source_reference(
        value["go_back_to"],
        allowed_types={"command", "decision"},
        command_indices=command_indices,
        decision_indices=decision_indices,
    )

    return {
        "trigger_is": trigger_is,
        "go_back_to": go_back_to,
    }


def _validate_trigger_list(
    value: Any,
    *,
    command_indices: set[int],
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("trigger_is must be a non-empty JSON array.")

    normalized: list[dict[str, Any]] = []
    seen_indices: set[int] = set()

    for item in value:
        reference = _validate_source_reference(
            item,
            allowed_types={"command"},
            command_indices=command_indices,
            decision_indices=set(),
        )
        index = reference["index"]

        if index not in seen_indices:
            normalized.append(reference)
            seen_indices.add(index)

    return normalized


def _validate_source_reference(
    value: Any,
    *,
    allowed_types: set[str],
    command_indices: set[int],
    decision_indices: set[int],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("A source reference must be a JSON object.")

    if set(value) != {"index_type", "index"}:
        raise ValueError(
            "Each source reference must contain exactly index_type and index."
        )

    index_type = value["index_type"]
    if index_type not in allowed_types:
        raise ValueError(
            f"Unsupported index_type {index_type!r}; "
            f"expected one of {sorted(allowed_types)}."
        )

    index = _coerce_index(value["index"])
    valid_indices = (
        command_indices
        if index_type == "command"
        else decision_indices
    )

    if index not in valid_indices:
        raise ValueError(
            f"{index_type}{index} does not exist in main_flow."
        )

    return {
        "index_type": index_type,
        "index": index,
    }


def _build_user_input(
    *,
    main_flow: dict[str, Any],
    alternative_flow: dict[str, Any],
) -> str:
    sections = [
        "Decision-Indexed main_flow "
        "(authoritative workflow structure and indices):\n"
        f"```json\n"
        f"{json.dumps(main_flow, indent=4, ensure_ascii=False)}\n"
        "```"
    ]
    sections.append(
        "Target alternative_flow:\n"
        f"```json\n"
        f"{json.dumps(alternative_flow, indent=4, ensure_ascii=False)}\n"
        "```"
    )

    return "\n\n".join(sections)


def _coerce_index(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("Boolean values cannot be used as indices.")

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        match = re.search(r"(\d+)$", value.strip())
        if match:
            return int(match.group(1))

    raise ValueError(f"Invalid index value: {value!r}.")
