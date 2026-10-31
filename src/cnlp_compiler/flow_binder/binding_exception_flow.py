from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

try:
    from ..utils import extract_single_json_from_text
except ImportError:  # Supports legacy top-level ``flow_binder`` imports.
    from utils import extract_single_json_from_text

__all__ = ["bind_exception_flow"]


try:
    from ..prompts.flow_binder import EXCEPTION_FLOW_SYSTEM_PROMPT as _SYSTEM_PROMPT
except ImportError:  # Supports legacy top-level package imports.
    from prompts.flow_binder import EXCEPTION_FLOW_SYSTEM_PROMPT as _SYSTEM_PROMPT


def bind_exception_flow(
    *,
    main_flow: dict[str, Any],
    exception_flow: dict[str, Any],
    command_indices: set[int],
    max_retries: int = 2,
    model_response: Callable[[list[dict[str, str]]], str] | None = None,
) -> list[dict[str, Any]]:
    """
    Bind one exception flow to main_flow.

    This is the only public entry point of this module.
    """
    if not isinstance(main_flow, dict):
        raise TypeError("main_flow must be a JSON object.")
    if not isinstance(exception_flow, dict):
        raise TypeError("exception_flow must be a JSON object.")
    if max_retries < 0:
        raise ValueError("max_retries must be non-negative.")

    user_input = _build_user_input(
        main_flow=main_flow,
        exception_flow=exception_flow,
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
            )
        except (TypeError, ValueError) as exc:
            last_error = str(exc)

    raise ValueError(
        "Failed to obtain a valid exception-flow binding. "
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
        # Do not erase a transient request failure by wrapping it as a generic
        # ValueError. RQ4 retries infrastructure failures, but it deliberately
        # does not retry invalid model output or invalid Flow bindings.
        try:
            from ..utils.llm import RetryableLLMRequestError
        except ImportError:
            from utils.llm import RetryableLLMRequestError
        if isinstance(exc, RetryableLLMRequestError):
            raise
        raise ValueError(
            "Exception-flow binding request failed: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if parsed is None:
        raise ValueError("The model response did not contain valid JSON.")

    return parsed


def _validate_binding(
    value: Any,
    *,
    command_indices: set[int],
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError(
            "Exception-flow trigger_is must be a non-empty JSON array."
        )

    normalized: list[dict[str, Any]] = []
    seen_indices: set[int] = set()

    for item in value:
        reference = _validate_source_reference(
            item,
            command_indices=command_indices,
        )
        index = reference["index"]

        if index not in seen_indices:
            normalized.append(reference)
            seen_indices.add(index)

    return normalized


def _validate_source_reference(
    value: Any,
    *,
    command_indices: set[int],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("A source reference must be a JSON object.")

    if set(value) != {"index_type", "index"}:
        raise ValueError(
            "Each source reference must contain exactly index_type and index."
        )

    if value["index_type"] != "command":
        raise ValueError(
            "Exception-flow trigger_is can only reference commands."
        )

    index = _coerce_index(value["index"])
    if index not in command_indices:
        raise ValueError(
            f"command{index} does not exist in main_flow."
        )

    return {
        "index_type": "command",
        "index": index,
    }


def _build_user_input(
    *,
    main_flow: dict[str, Any],
    exception_flow: dict[str, Any],
) -> str:
    sections = [
        "Decision-Indexed main_flow "
        "(authoritative workflow structure and indices):\n"
        f"```json\n"
        f"{json.dumps(main_flow, indent=4, ensure_ascii=False)}\n"
        "```"
    ]
    sections.append(
        "Target exception_flow:\n"
        f"```json\n"
        f"{json.dumps(exception_flow, indent=4, ensure_ascii=False)}\n"
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
