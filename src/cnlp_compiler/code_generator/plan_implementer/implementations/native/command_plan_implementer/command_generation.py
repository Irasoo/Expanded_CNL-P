"""Shared Native Command function generation and validation support."""

from __future__ import annotations

import ast
import json
from collections import Counter

from ......schema import ModelConfig, VariableNode
from ......utils import (
    LLMclient,
    OpenaiClient,
    create_prompt_section,
    extract_single_json_from_text,
)


try:
    from ......prompts.code_generator_plan_implementer_shared import (
        CALL_API_COMMAND_RUNTIME_CONTRACT,
        COMMAND_LLM_COMPLETE_CONTRACT,
        COMMAND_RUNTIME_BASE_CONTRACT,
        COMMAND_VARIABLE_READ_CONTRACT,
        COMMAND_VARIABLE_WRITE_CONTRACT,
    )
except ImportError:  # Supports legacy top-level package imports.
    from prompts.code_generator_plan_implementer_shared import (
        CALL_API_COMMAND_RUNTIME_CONTRACT,
        COMMAND_LLM_COMPLETE_CONTRACT,
        COMMAND_RUNTIME_BASE_CONTRACT,
        COMMAND_VARIABLE_READ_CONTRACT,
        COMMAND_VARIABLE_WRITE_CONTRACT,
    )


def compose_runtime_contract(*parts: str) -> str:
    """Compose only the runtime interfaces required by one Command."""
    return "\n\n".join(
        part.strip() for part in (COMMAND_RUNTIME_BASE_CONTRACT, *parts) if part.strip()
    )


def create_model_client(model_config: ModelConfig) -> LLMclient:
    return OpenaiClient(
        model_config["api_key"],
        model_config["model_name"],
        "",
        model_config["base_url"],
    )


def select_related_variables(
    variable_names: list[str],
    variables: list[VariableNode],
) -> list[VariableNode]:
    variable_table = {variable["variable_name"]: variable for variable in variables}
    missing_names = [
        variable_name
        for variable_name in dict.fromkeys(variable_names)
        if variable_name not in variable_table
    ]
    if missing_names:
        raise ValueError(
            "Command Plan references unknown variables: " f"{missing_names}."
        )

    return [
        variable_table[variable_name] for variable_name in dict.fromkeys(variable_names)
    ]


def json_text(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        default=str,
    )


def request_function_code(
    *,
    prompt: str,
    function_name: str,
    llm_client: LLMclient,
    required_calls: set[str],
    forbidden_calls: set[str],
    minimum_call_counts: dict[str, int] | None = None,
    allowed_written_variables: set[str] | None = None,
    max_validation_retries: int = 2,
) -> str:
    """Request one Command function and retry only invalid model output.

    Transport and model-service exceptions are deliberately not swallowed:
    those are compilation-infrastructure failures. A retry is used only when
    the service returned text but that text violates the generated-function
    contract, such as explanatory prose, invalid Python, a wrong signature,
    or missing required runtime calls.
    """
    if max_validation_retries < 0:
        raise ValueError("max_validation_retries cannot be negative.")

    current_prompt = prompt
    last_validation_error: ValueError | None = None
    for attempt_index in range(max_validation_retries + 1):
        response = llm_client.complete(
            [create_prompt_section("user", current_prompt)]
        )
        try:
            return validate_function_code_response(
                response=response,
                function_name=function_name,
                required_calls=required_calls,
                forbidden_calls=forbidden_calls,
                minimum_call_counts=minimum_call_counts,
                allowed_written_variables=allowed_written_variables,
            )
        except ValueError as exc:
            last_validation_error = exc
            if attempt_index >= max_validation_retries:
                raise
            current_prompt = (
                f"{prompt}\n\n"
                "【上一版输出未通过编译器校验】\n"
                f"{exc}\n"
                "请重新生成，并继续严格遵守以上全部要求。只返回一个有效JSON对象，"
                "且只能包含function_code字段："
                '{"function_code": "<完整的Python函数源码>"}。'
                "function_code必须是经过正确JSON转义的字符串。不要输出Markdown、"
                "解释、道歉或任何其他字段。"
            )

    # The loop always returns or raises. This guard keeps the control-flow
    # contract explicit for static analyzers.
    raise RuntimeError(
        "Command generation ended without a result."
    ) from last_validation_error


def validate_function_code_response(
    *,
    response: str,
    function_name: str,
    required_calls: set[str],
    forbidden_calls: set[str],
    minimum_call_counts: dict[str, int] | None = None,
    allowed_written_variables: set[str] | None = None,
) -> str:
    """Normalize and validate function code returned by any model route."""

    function_code = extract_function_code_from_json_response(
        response,
        expected_function_name=function_name,
    )
    _validate_function_code(
        function_code=function_code,
        expected_function_name=function_name,
    )
    _validate_function_calls(
        function_code=function_code,
        required_calls=required_calls,
        forbidden_calls=forbidden_calls,
        minimum_call_counts=minimum_call_counts or {},
        allowed_written_variables=allowed_written_variables,
    )
    return function_code


def extract_function_code_from_json_response(
    response: str,
    *,
    expected_function_name: str,
) -> str:
    """Extract one strictly shaped JSON payload from a model response."""
    try:
        payload = extract_single_json_from_text(response)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"LLM returned invalid JSON for {expected_function_name}."
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(
            f"LLM response for {expected_function_name} must contain one JSON object."
        )
    if set(payload) != {"function_code"}:
        raise ValueError(
            f"LLM JSON for {expected_function_name} must contain exactly the "
            "function_code key."
        )

    function_code = payload["function_code"]
    if not isinstance(function_code, str) or not function_code.strip():
        raise ValueError(
            f"LLM JSON function_code for {expected_function_name} must be a "
            "non-empty string."
        )
    return f"{function_code.strip()}\n"


def _validate_function_code(
    *,
    function_code: str,
    expected_function_name: str,
) -> None:
    try:
        syntax_tree = ast.parse(
            function_code,
            filename=f"{expected_function_name}.py",
        )
    except SyntaxError as exc:
        raise ValueError(
            f"LLM returned invalid Python for {expected_function_name}."
        ) from exc

    if len(syntax_tree.body) != 1 or not isinstance(
        syntax_tree.body[0], ast.FunctionDef
    ):
        raise ValueError(
            "Generated Command code must contain exactly one " "top-level function."
        )

    function_node = syntax_tree.body[0]
    if function_node.name != expected_function_name:
        raise ValueError(
            "Generated Command function name does not match its Plan: "
            f"expected {expected_function_name!r}, "
            f"received {function_node.name!r}."
        )

    positional_arguments = [
        argument.arg
        for argument in (function_node.args.posonlyargs + function_node.args.args)
    ]
    if (
        positional_arguments != ["state", "llm_client"]
        or function_node.args.vararg is not None
        or function_node.args.kwarg is not None
        or function_node.args.kwonlyargs
        or function_node.args.defaults
    ):
        raise ValueError(
            "Generated Command function must accept exactly " "(state, llm_client)."
        )


def _validate_function_calls(
    *,
    function_code: str,
    required_calls: set[str],
    forbidden_calls: set[str],
    minimum_call_counts: dict[str, int],
    allowed_written_variables: set[str] | None,
) -> None:
    syntax_tree = ast.parse(function_code)
    called_function_list = [
        called_name
        for node in ast.walk(syntax_tree)
        if isinstance(node, ast.Call)
        if (called_name := _get_callable_name(node.func)) is not None
    ]
    called_functions = set(called_function_list)
    call_counts = Counter(called_function_list)

    validate_runtime_llm_complete_calls(syntax_tree)
    validate_runtime_call_api_llm_calls(syntax_tree)
    validate_no_direct_llm_sdk_usage(syntax_tree)
    validate_history_record_calls(syntax_tree)
    validate_written_variable_targets(
        syntax_tree,
        allowed_written_variables=allowed_written_variables,
    )

    missing_calls = sorted(required_calls - called_functions)
    if missing_calls:
        raise ValueError(
            "Generated Command function is missing required calls: " f"{missing_calls}."
        )

    unexpected_calls = sorted(forbidden_calls & called_functions)
    if unexpected_calls:
        raise ValueError(
            "Generated Command function contains forbidden calls: "
            f"{unexpected_calls}."
        )

    insufficient_calls = {
        function_name: {
            "expected_at_least": minimum_count,
            "actual": call_counts[function_name],
        }
        for function_name, minimum_count in minimum_call_counts.items()
        if call_counts[function_name] < minimum_count
    }
    if insufficient_calls:
        raise ValueError(
            "Generated Command function does not call an interface "
            f"enough times: {insufficient_calls}."
        )


def validate_written_variable_targets(
    syntax_tree: ast.AST,
    *,
    allowed_written_variables: set[str] | None,
) -> None:
    """Reject placeholder or unrelated State targets in generated Commands."""
    if allowed_written_variables is None:
        return

    for node in ast.walk(syntax_tree):
        if not isinstance(node, ast.Call):
            continue
        called_name = _get_callable_name(node.func)

        target_node: ast.expr | None = None
        if called_name == "llm_client.complete":
            target_node = next(
                (
                    keyword.value
                    for keyword in node.keywords
                    if keyword.arg == "written_variable"
                ),
                None,
            )
            if target_node is None:
                continue
        elif called_name == "state.revise_variable_value":
            if node.args:
                target_node = node.args[0]
            else:
                target_node = next(
                    (
                        keyword.value
                        for keyword in node.keywords
                        if keyword.arg == "variable_name"
                    ),
                    None,
                )
            if target_node is None:
                raise ValueError(
                    "state.revise_variable_value must receive the Plan's "
                    "written variable name."
                )
        elif called_name == "state.record_call_api_command_history":
            target_node = next(
                (
                    keyword.value
                    for keyword in node.keywords
                    if keyword.arg == "written_variable"
                ),
                None,
            )
            if target_node is None:
                continue
            if isinstance(target_node, ast.Constant) and target_node.value is None:
                if allowed_written_variables:
                    raise ValueError(
                        "Call API History must record the Plan's actual "
                        "written variable."
                    )
                continue
        else:
            continue

        if not (
            isinstance(target_node, ast.Constant)
            and isinstance(target_node.value, str)
        ):
            raise ValueError(
                f"{called_name} must use the Plan's written variable as a "
                "direct string literal."
            )
        if target_node.value not in allowed_written_variables:
            raise ValueError(
                f"{called_name} targets {target_node.value!r}, but the "
                "Command Plan allows only "
                f"{sorted(allowed_written_variables)!r}."
            )


def validate_runtime_llm_complete_calls(syntax_tree: ast.AST) -> None:
    """Validate every generated call against OpenAIClient.complete().

    The runtime method uses keyword-only arguments. Checking only that a
    generated function mentions ``llm_client.complete`` allowed syntactically
    valid Agents to compile and then fail immediately at runtime. Keep this
    validation centralized so every Command type and Predicate follows the
    same interface contract.
    """
    allowed_keywords = {
        "state",
        "current_instruction",
        "written_variable",
        "return_bool",
    }
    for node in ast.walk(syntax_tree):
        if not isinstance(node, ast.Call):
            continue
        if _get_callable_name(node.func) != "llm_client.complete":
            continue
        if node.args:
            raise ValueError(
                "llm_client.complete accepts keyword-only arguments; "
                "generated code must not pass positional arguments."
            )
        if any(keyword.arg is None for keyword in node.keywords):
            raise ValueError(
                "Generated code must not pass **kwargs to "
                "llm_client.complete."
            )

        keyword_table = {keyword.arg: keyword.value for keyword in node.keywords}
        unknown_keywords = sorted(set(keyword_table) - allowed_keywords)
        if unknown_keywords:
            raise ValueError(
                "Generated code passes unsupported keywords to "
                f"llm_client.complete: {unknown_keywords}."
            )
        missing_keywords = sorted(
            {"state", "current_instruction"} - set(keyword_table)
        )
        if missing_keywords:
            raise ValueError(
                "Generated code must pass state and current_instruction "
                "to llm_client.complete; missing: "
                f"{missing_keywords}."
            )
        state_value = keyword_table["state"]
        if not isinstance(state_value, ast.Name) or state_value.id != "state":
            raise ValueError(
                "llm_client.complete must receive the current function's "
                "state through state=state."
            )
        if (
            "written_variable" in keyword_table
            and "return_bool" in keyword_table
        ):
            raise ValueError(
                "llm_client.complete cannot use written_variable and "
                "return_bool together."
            )


def validate_runtime_call_api_llm_calls(syntax_tree: ast.AST) -> None:
    """Validate the stateless Call API reference-logic LLM interface."""

    for node in ast.walk(syntax_tree):
        if not isinstance(node, ast.Call):
            continue
        if _get_callable_name(node.func) != "llm_client.complete_call_api":
            continue
        if len(node.args) != 1 or node.keywords:
            raise ValueError(
                "llm_client.complete_call_api must receive exactly one prompt "
                "positional argument and no State or other keywords."
            )


def validate_history_record_calls(syntax_tree: ast.AST) -> None:
    """Validate generated History calls against AgentState's public API.

    Merely checking that a generated function calls the expected method is
    insufficient: Python accepts arbitrary keyword names at parse time, so a
    generated Agent could pass compilation and fail only when it was run.
    Keep the exact keyword-only contracts here in sync with ``AgentState``.
    """
    expected_keywords_by_call = {
        "state.record_input_command_history": {
            "displayed_request",
            "raw_user_input",
        },
        "state.record_general_command_history": {"summary"},
        "state.record_call_api_command_history": {
            "api_name",
            "written_variable",
        },
        "state.record_display_command_history": {"displayed_content"},
    }

    for node in ast.walk(syntax_tree):
        if not isinstance(node, ast.Call):
            continue
        called_name = _get_callable_name(node.func)
        if called_name not in expected_keywords_by_call:
            continue

        if node.args:
            raise ValueError(
                f"{called_name} accepts keyword-only arguments; generated "
                "code must not pass positional arguments."
            )
        if any(keyword.arg is None for keyword in node.keywords):
            raise ValueError(
                f"Generated code must not pass **kwargs to {called_name}."
            )

        keyword_names = [keyword.arg for keyword in node.keywords]
        if len(keyword_names) != len(set(keyword_names)):
            raise ValueError(
                f"Generated code passes duplicate keywords to {called_name}."
            )

        expected_keywords = expected_keywords_by_call[called_name]
        actual_keywords = set(keyword_names)
        missing_keywords = sorted(expected_keywords - actual_keywords)
        unsupported_keywords = sorted(actual_keywords - expected_keywords)
        if missing_keywords or unsupported_keywords:
            raise ValueError(
                f"Generated code uses the wrong keyword arguments for "
                f"{called_name}; missing={missing_keywords}, "
                f"unsupported={unsupported_keywords}."
            )


def validate_no_direct_llm_sdk_usage(syntax_tree: ast.AST) -> None:
    """Require generated Commands to use the compiler-provided LLM client."""

    forbidden_module_roots = {
        "anthropic",
        "cohere",
        "google.generativeai",
        "openai",
    }
    forbidden_client_constructors = {
        "Anthropic",
        "AsyncAnthropic",
        "AsyncOpenAI",
        "OpenAI",
    }

    for node in ast.walk(syntax_tree):
        if isinstance(node, ast.Import):
            imported_modules = [alias.name for alias in node.names]
            if any(
                module_name == root or module_name.startswith(f"{root}.")
                for module_name in imported_modules
                for root in forbidden_module_roots
            ):
                raise ValueError(
                    "Generated Command code must not import an external LLM SDK; "
                    "use the provided llm_client.complete interface."
                )
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if any(
                module_name == root or module_name.startswith(f"{root}.")
                for root in forbidden_module_roots
            ):
                raise ValueError(
                    "Generated Command code must not import an external LLM SDK; "
                    "use the provided llm_client.complete interface."
                )
        elif isinstance(node, ast.Call):
            called_name = _get_callable_name(node.func)
            if (
                called_name is not None
                and called_name.rsplit(".", 1)[-1]
                in forbidden_client_constructors
            ):
                raise ValueError(
                    "Generated Command code must not create an external LLM "
                    "client; use the provided llm_client.complete interface."
                )


def _get_callable_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent_name = _get_callable_name(node.value)
        if parent_name is None:
            return node.attr
        return f"{parent_name}.{node.attr}"
    return None
