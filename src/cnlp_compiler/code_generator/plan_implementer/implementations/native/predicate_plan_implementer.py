from __future__ import annotations

import ast
import json
import re

from .....schema import (
    ModelConfig,
    PredicateAnalysisPlan,
    VariableNode,
)
from .....utils import LLMclient, OpenaiClient, create_prompt_section
from ...type_converter import TypeConverter
from .schema import FunctionImplementation, PredicateImplementationResult
from .command_plan_implementer.command_generation import (
    extract_function_code_from_json_response,
    validate_runtime_llm_complete_calls,
)


PREDICATES_MODULE_HEADER = """\
from .model import AgentState
from .utils import OpenAIClient
"""


try:
    from .....prompts.code_generator_plan_implementer_shared import (
        PREDICATE_LLM_BASED_IMPLEMENTATION_PROMPT,
        PREDICATE_TRADITIONAL_IMPLEMENTATION_PROMPT,
    )
except ImportError:  # Supports legacy top-level package imports.
    from prompts.code_generator_plan_implementer_shared import (
        PREDICATE_LLM_BASED_IMPLEMENTATION_PROMPT,
        PREDICATE_TRADITIONAL_IMPLEMENTATION_PROMPT,
    )


class PredicatePlanImplementer:

    def __init__(
        self,
        llm_client: LLMclient | None = None,
        *,
        max_retries: int = 2,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative.")
        self._llm_client = llm_client
        self.max_retries = max_retries

    def implement(
        self,
        *,
        predicate_plans: list[PredicateAnalysisPlan],
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str] | None = None,
        python_schema_dependency_table: dict[str, list[str]] | None = None,
        model_config: ModelConfig,
    ) -> PredicateImplementationResult:
        predicates_file_content = PREDICATES_MODULE_HEADER.rstrip()
        predicate_naming_table: dict[str, str] = {}
        generated_function_names: set[str] = set()

        for predicate_index, predicate_plan in enumerate(
            predicate_plans,
            start=1,
        ):
            print(
                f"[Compiler][Implementation][Predicates] {predicate_index}/"
                f"{len(predicate_plans)} {predicate_plan['predicate_name']}: "
                "started.",
                flush=True,
            )
            function_implementation = self.implement_predicate(
                predicate_plan=predicate_plan,
                variables=variables,
                python_schema_code_table=(python_schema_code_table or {}),
                python_schema_dependency_table=(python_schema_dependency_table or {}),
                model_config=model_config,
            )
            condition_path = _canonical_condition_path(predicate_plan["condition_path"])
            function_name = function_implementation["function_name"]

            if condition_path in predicate_naming_table:
                raise ValueError(
                    "Predicate condition path is duplicated: " f"{condition_path!r}."
                )
            if function_name in generated_function_names:
                raise ValueError(
                    "Generated Predicate function name is duplicated: "
                    f"{function_name!r}."
                )

            predicates_file_content += (
                "\n\n\n" + function_implementation["function_code"].strip()
            )
            predicate_naming_table[condition_path] = function_name
            generated_function_names.add(function_name)
            print(
                f"[Compiler][Implementation][Predicates] {predicate_index}/"
                f"{len(predicate_plans)} {predicate_plan['predicate_name']}: "
                "completed.",
                flush=True,
            )

        predicates_file_content += "\n"
        compile(predicates_file_content, "predicates.py", "exec")

        return {
            "generated_file": {
                "relative_path": "predicates.py",
                "content": predicates_file_content,
                "write_type": "rewrite",
            },
            "predicate_naming_table": predicate_naming_table,
        }

    def implement_predicate(
        self,
        *,
        predicate_plan: PredicateAnalysisPlan,
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str] | None = None,
        python_schema_dependency_table: dict[str, list[str]] | None = None,
        model_config: ModelConfig,
    ) -> FunctionImplementation:
        function_name = _build_predicate_function_name(predicate_plan)
        related_variables = _select_related_variables(
            predicate_plan["required_variables"],
            variables,
        )
        related_python_schema_code = TypeConverter.render_related_variable_type_code(
            variables=related_variables,
            schema_code_table=python_schema_code_table or {},
            schema_dependency_table=(python_schema_dependency_table or {}),
        )
        prompt_template = (
            PREDICATE_LLM_BASED_IMPLEMENTATION_PROMPT
            if predicate_plan["llm_based_processing"]
            else PREDICATE_TRADITIONAL_IMPLEMENTATION_PROMPT
        )
        prompt = (
            prompt_template.replace(
                "PREDICATE_JSON",
                _json_text(_predicate_prompt_data(predicate_plan)),
            )
            .replace(
                "RELATED_VARIABLES_JSON",
                _json_text(_variable_prompt_data(related_variables)),
            )
            .replace(
                "RELATED_PYTHON_SCHEMA_CODE",
                related_python_schema_code.strip() or "None",
            )
            .replace(
                "PREDICATE_FUNCTION_NAME",
                function_name,
            )
        )
        function_code = self._request_valid_function_code(
            prompt=prompt,
            function_name=function_name,
            predicate_plan=predicate_plan,
            model_config=model_config,
        )

        return {
            "function_name": function_name,
            "function_code": function_code,
        }

    def _request_valid_function_code(
        self,
        *,
        prompt: str,
        function_name: str,
        predicate_plan: PredicateAnalysisPlan,
        model_config: ModelConfig,
    ) -> str:
        last_error: ValueError | None = None
        attempt_count = self.max_retries + 1
        for attempt_index in range(1, attempt_count + 1):
            if attempt_index > 1:
                print(
                    "[Compiler][Implementation][Predicates] "
                    f"{function_name}: retry {attempt_index}/{attempt_count} "
                    "after generated-code validation failed.",
                    flush=True,
                )
            current_prompt = prompt
            if last_error is not None:
                current_prompt += (
                    "\n\n【上一版代码未通过编译器校验】\n"
                    f"{last_error}\n"
                    "请重新生成，并继续严格遵守上述运行时与字段访问契约。只返回一个"
                    "有效JSON对象，且只能包含function_code字段："
                    '{"function_code": "<完整的Predicate函数源码>"}。'
                    "function_code必须是经过正确JSON转义的字符串。不要输出Markdown、"
                    "解释、道歉或任何其他字段。"
                )
            response = self._get_llm_client(model_config).complete(
                [create_prompt_section("user", current_prompt)]
            )
            try:
                function_code = extract_function_code_from_json_response(
                    response,
                    expected_function_name=function_name,
                )
                _validate_predicate_function(
                    function_code=function_code,
                    expected_function_name=function_name,
                    required_variables=predicate_plan["required_variables"],
                    llm_based_processing=predicate_plan["llm_based_processing"],
                )
                return function_code
            except ValueError as exc:
                last_error = exc
                print(
                    "[Compiler][Implementation][Predicates] "
                    f"{function_name}: validation failed on attempt "
                    f"{attempt_index}/{attempt_count}: {exc}",
                    flush=True,
                )

        raise ValueError(
            f"Failed to generate a valid Predicate {function_name!r} "
            f"after {self.max_retries + 1} attempts: {last_error}"
        )

    def _get_llm_client(self, model_config: ModelConfig) -> LLMclient:
        if self._llm_client is None:
            self._llm_client = OpenaiClient(
                model_config["api_key"],
                model_config["model_name"],
                "",
                model_config["base_url"],
            )
        return self._llm_client


def _build_predicate_function_name(
    predicate_plan: PredicateAnalysisPlan,
) -> str:
    condition_path = predicate_plan["condition_path"]
    _canonical_condition_path(condition_path)

    function_path = (
        condition_path[1:] if condition_path[0] == "worker" else condition_path
    )
    normalized_parts = [
        re.sub(r"[^0-9A-Za-z_]+", "_", path_part).strip("_")
        for path_part in function_path
    ]
    if not normalized_parts or any(not part for part in normalized_parts):
        raise ValueError(
            f"Predicate condition path cannot form a function name: "
            f"{condition_path!r}."
        )

    return (
        "predicate_"
        + "_".join(normalized_parts)
        + f"_{predicate_plan['predicate_index']}"
    )


def _canonical_condition_path(condition_path: list[str]) -> str:
    if not condition_path or any(
        not isinstance(path_part, str) or not path_part for path_part in condition_path
    ):
        raise ValueError("Predicate condition_path must contain non-empty strings.")
    return ".".join(condition_path)


def _select_related_variables(
    variable_names: list[str],
    variables: list[VariableNode],
) -> list[VariableNode]:
    variable_table = {variable["variable_name"]: variable for variable in variables}
    unique_variable_names = list(dict.fromkeys(variable_names))
    missing_names = [
        variable_name
        for variable_name in unique_variable_names
        if variable_name not in variable_table
    ]
    if missing_names:
        raise ValueError(
            "Predicate Plan references unknown variables: " f"{missing_names}."
        )
    return [variable_table[variable_name] for variable_name in unique_variable_names]


def _json_text(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        default=str,
    )


def _predicate_prompt_data(
    predicate_plan: PredicateAnalysisPlan,
) -> dict[str, object]:
    return {
        "description": predicate_plan["description"],
        "required_variables": predicate_plan["required_variables"],
    }


def _variable_prompt_data(
    variables: list[VariableNode],
) -> list[dict[str, object]]:
    return [
        {
            "variable_name": variable["variable_name"],
            "description": variable["description"],
        }
        for variable in variables
    ]


def _validate_predicate_function(
    *,
    function_code: str,
    expected_function_name: str,
    required_variables: list[str],
    llm_based_processing: bool,
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
            "Generated Predicate code must contain exactly one " "top-level function."
        )

    function_node = syntax_tree.body[0]
    _validate_predicate_signature(
        function_node=function_node,
        expected_function_name=expected_function_name,
    )
    _validate_predicate_calls(
        function_node=function_node,
        llm_based_processing=llm_based_processing,
    )
    _validate_predicate_variable_reads(
        function_node=function_node,
        required_variables=required_variables,
    )
    _validate_state_value_attribute_reads(function_node)

    _validate_predicate_returns(function_node)


def _validate_predicate_signature(
    *,
    function_node: ast.FunctionDef,
    expected_function_name: str,
) -> None:
    if function_node.name != expected_function_name:
        raise ValueError(
            "Generated Predicate function name does not match its Plan: "
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
            "Generated Predicate function must accept exactly " "(state, llm_client)."
        )
    if (
        not isinstance(function_node.returns, ast.Name)
        or function_node.returns.id != "bool"
    ):
        raise ValueError("Generated Predicate function must declare -> bool.")


def _validate_predicate_calls(
    *,
    function_node: ast.FunctionDef,
    llm_based_processing: bool,
) -> None:
    calls = [node for node in ast.walk(function_node) if isinstance(node, ast.Call)]
    validate_runtime_llm_complete_calls(function_node)
    called_names = [
        called_name
        for call in calls
        if (called_name := _get_callable_name(call.func)) is not None
    ]
    forbidden_calls = {
        "display",
        "input",
        "llm_client.complete_call_api",
        "state.revise_variable_value",
        "AgentState",
        "OpenAIClient",
    }
    unexpected_calls = sorted(
        called_name
        for called_name in called_names
        if (called_name in forbidden_calls or called_name.startswith("state.record_"))
    )
    if unexpected_calls:
        raise ValueError(
            "Generated Predicate function contains forbidden calls: "
            f"{unexpected_calls}."
        )

    model_calls = [
        call for call in calls if _get_callable_name(call.func) == "llm_client.complete"
    ]
    if llm_based_processing:
        if len(model_calls) != 1:
            raise ValueError(
                "LLM-based Predicate must call llm_client.complete " "exactly once."
            )
        keyword_table = {
            keyword.arg: keyword.value
            for keyword in model_calls[0].keywords
            if keyword.arg is not None
        }
        return_bool = keyword_table.get("return_bool")
        if not isinstance(return_bool, ast.Constant) or return_bool.value is not True:
            raise ValueError(
                "LLM-based Predicate must call complete() with " "return_bool=True."
            )
        if "written_variable" in keyword_table:
            raise ValueError("Predicate must not pass written_variable to complete().")
    elif model_calls:
        raise ValueError("Traditional Predicate must not call llm_client.complete.")


def _validate_predicate_returns(
    function_node: ast.FunctionDef,
) -> None:
    nested_functions = [
        node
        for node in ast.walk(function_node)
        if node is not function_node
        and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if nested_functions:
        raise ValueError("Generated Predicate must not contain helper functions.")

    known_boolean_names: set[str] = set()
    assignments = [
        node
        for node in ast.walk(function_node)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
    ]
    changed = True
    while changed:
        changed = False
        for assignment in assignments:
            if isinstance(assignment, ast.Assign):
                value = assignment.value
                targets = assignment.targets
            else:
                value = assignment.value
                targets = [assignment.target]
            if value is None or not _is_boolean_expression(
                value,
                known_boolean_names,
            ):
                continue

            for target in targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id not in known_boolean_names
                ):
                    known_boolean_names.add(target.id)
                    changed = True

    returns = [node for node in ast.walk(function_node) if isinstance(node, ast.Return)]
    if not returns or any(
        return_node.value is None
        or not _is_boolean_expression(
            return_node.value,
            known_boolean_names,
        )
        for return_node in returns
    ):
        raise ValueError(
            "Every generated Predicate return must be statically known "
            "to produce a Python bool."
        )


def _is_boolean_expression(
    expression: ast.expr,
    known_boolean_names: set[str],
) -> bool:
    if isinstance(expression, ast.Constant) and isinstance(expression.value, bool):
        return True
    if isinstance(expression, (ast.Compare, ast.UnaryOp)):
        return not isinstance(expression, ast.UnaryOp) or isinstance(
            expression.op, ast.Not
        )
    if isinstance(expression, ast.BoolOp):
        return all(
            _is_boolean_expression(value, known_boolean_names)
            for value in expression.values
        )
    if isinstance(expression, ast.IfExp):
        return _is_boolean_expression(
            expression.body, known_boolean_names
        ) and _is_boolean_expression(
            expression.orelse,
            known_boolean_names,
        )
    if isinstance(expression, ast.Name) and expression.id in known_boolean_names:
        return True
    if isinstance(expression, ast.Call):
        called_name = _get_callable_name(expression.func)
        return called_name in {
            "bool",
            "all",
            "any",
            "isinstance",
            "issubclass",
            "llm_client.complete",
        }
    return False


def _validate_predicate_variable_reads(
    *,
    function_node: ast.FunctionDef,
    required_variables: list[str],
) -> None:
    read_variables: list[str] = []
    multi_value_call_ids: set[int] = set()
    for node in ast.walk(function_node):
        if not isinstance(node, ast.Call):
            continue

        called_name = _get_callable_name(node.func)
        if called_name == "state.get_variable_value":
            if (
                len(node.args) != 1
                or not isinstance(node.args[0], ast.Constant)
                or not isinstance(node.args[0].value, str)
            ):
                raise ValueError(
                    "Predicate variable reads must use a literal variable " "name."
                )
            read_variables.append(node.args[0].value)

        if called_name == "state.get_variable_values":
            multi_value_call_ids.add(id(node))
            if len(node.args) != 1 or not isinstance(
                node.args[0],
                (ast.List, ast.Tuple),
            ):
                raise ValueError(
                    "Predicate multi-variable reads must use a literal " "name list."
                )
            for element in node.args[0].elts:
                if not isinstance(element, ast.Constant) or not isinstance(
                    element.value, str
                ):
                    raise ValueError(
                        "Predicate multi-variable reads must use literal "
                        "variable names."
                    )
                read_variables.append(element.value)

    valid_multi_value_call_ids: set[int] = set()
    for assignment in ast.walk(function_node):
        if not isinstance(assignment, (ast.Assign, ast.AnnAssign)):
            continue
        value = assignment.value
        if (
            not isinstance(value, ast.Call)
            or _get_callable_name(value.func) != "state.get_variable_values"
        ):
            continue
        if isinstance(assignment, ast.Assign):
            valid_target = len(assignment.targets) == 1 and isinstance(
                assignment.targets[0], ast.Name
            )
        else:
            valid_target = isinstance(assignment.target, ast.Name)
        if valid_target:
            valid_multi_value_call_ids.add(id(value))

    invalid_multi_value_calls = multi_value_call_ids - valid_multi_value_call_ids
    if invalid_multi_value_calls:
        raise ValueError(
            "state.get_variable_values() returns a dictionary and must be "
            "assigned to one local name before values are selected by "
            "their variable-name keys; tuple unpacking is forbidden."
        )

    expected_variables = set(required_variables)
    actual_variables = set(read_variables)
    missing_variables = sorted(expected_variables - actual_variables)
    unexpected_variables = sorted(actual_variables - expected_variables)
    if missing_variables or unexpected_variables:
        raise ValueError(
            "Generated Predicate variable reads do not match "
            "required_variables: "
            f"missing={missing_variables}, "
            f"unexpected={unexpected_variables}."
        )


def _validate_state_value_attribute_reads(
    function_node: ast.FunctionDef,
) -> None:
    """Reject object-style field reads on values obtained from AgentState."""
    state_value_names: set[str] = set()
    multi_value_container_names: set[str] = set()
    assignments = [
        node
        for node in ast.walk(function_node)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
    ]

    changed = True
    while changed:
        changed = False
        for assignment in assignments:
            if isinstance(assignment, ast.Assign):
                targets = assignment.targets
                value = assignment.value
            else:
                targets = [assignment.target]
                value = assignment.value
            if value is None:
                continue

            target_names = {
                target.id for target in targets if isinstance(target, ast.Name)
            }
            call_names = {
                called_name
                for node in ast.walk(value)
                if isinstance(node, ast.Call)
                and (called_name := _get_callable_name(node.func)) is not None
            }
            if "state.get_variable_values" in call_names:
                new_names = target_names - multi_value_container_names
                if new_names:
                    multi_value_container_names.update(new_names)
                    changed = True

            derives_state_value = (
                "state.get_variable_value" in call_names
                or any(
                    isinstance(node, ast.Subscript)
                    and isinstance(node.value, ast.Name)
                    and node.value.id in multi_value_container_names
                    for node in ast.walk(value)
                )
                or any(
                    isinstance(node, ast.Name) and node.id in state_value_names
                    for node in ast.walk(value)
                )
            )
            if derives_state_value:
                new_names = target_names - state_value_names
                if new_names:
                    state_value_names.update(new_names)
                    changed = True

    call_function_nodes = {
        id(node.func) for node in ast.walk(function_node) if isinstance(node, ast.Call)
    }
    invalid_attributes = sorted(
        {
            node.attr
            for node in ast.walk(function_node)
            if isinstance(node, ast.Attribute)
            and _attribute_root_name(node) in state_value_names
            and id(node) not in call_function_nodes
        }
    )
    if invalid_attributes:
        raise ValueError(
            "Generated Predicate must use dictionary subscripting for "
            "fields of values read from AgentState; invalid attributes: "
            f"{invalid_attributes}."
        )

    invalid_stringifications = [
        node
        for node in ast.walk(function_node)
        if isinstance(node, ast.Call)
        and _get_callable_name(node.func) == "str"
        and any(
            (
                isinstance(child, ast.Call)
                and _get_callable_name(child.func)
                in {
                    "state.get_variable_value",
                    "state.get_variable_values",
                }
            )
            or (isinstance(child, ast.Name) and child.id in state_value_names)
            for argument in node.args
            for child in ast.walk(argument)
        )
    ]
    if invalid_stringifications:
        raise ValueError(
            "Generated Predicate must compare original AgentState values; "
            "do not convert them to str before field access or comparison."
        )


def _attribute_root_name(node: ast.Attribute) -> str | None:
    value: ast.expr = node
    while isinstance(value, ast.Attribute):
        value = value.value
    return value.id if isinstance(value, ast.Name) else None


def _get_callable_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent_name = _get_callable_name(node.value)
        if parent_name is None:
            return node.attr
        return f"{parent_name}.{node.attr}"
    return None
