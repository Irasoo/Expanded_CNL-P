from __future__ import annotations

import ast
import copy
import json
import re
from collections.abc import Callable, Iterator
from collections import Counter
from typing import Any

from .....schema import ModelConfig, WorkflowStep, WorkflowStructure
from .....utils import LLMclient, OpenaiClient, create_prompt_section
from ...schema import GeneratedFile
from .schema import CommandFunctionNames, PredicateNamingTable


try:
    from .....prompts.code_generator_plan_implementer_native import MAIN_IMPLEMENTATION_PROMPT
except ImportError:  # Supports legacy top-level package imports.
    from prompts.code_generator_plan_implementer_native import MAIN_IMPLEMENTATION_PROMPT


class MainImplementer:

    def __init__(self, llm_client: LLMclient | None = None) -> None:
        self._llm_client = llm_client

    def implement(
        self,
        *,
        cnlp_script: str,
        workflow_structure: WorkflowStructure,
        binding_table: dict[str, Any],
        command_function_names: CommandFunctionNames,
        predicate_naming_table: PredicateNamingTable,
        model_config: ModelConfig,
    ) -> GeneratedFile:
        normalized_workflow = _prepare_generation_inputs(
            workflow_structure=workflow_structure,
            binding_table=binding_table,
            command_function_names=command_function_names,
            predicate_naming_table=predicate_naming_table,
        )
        prompt = (
            MAIN_IMPLEMENTATION_PROMPT
            .replace("CNL_P_SCRIPT", cnlp_script)
            .replace(
                "WORKFLOW_STRUCTURE_JSON",
                _json_text(normalized_workflow),
            )
            .replace(
                "BINDING_TABLE_JSON",
                _json_text(binding_table),
            )
            .replace(
                "COMMAND_FUNCTION_NAMES_JSON",
                _json_text(command_function_names),
            )
            .replace(
                "PREDICATE_NAMING_TABLE_JSON",
                _json_text(predicate_naming_table),
            )
        )
        response = self._get_llm_client(model_config).complete(
            [create_prompt_section("user", prompt)]
        )
        content = _extract_python_code(response)
        _validate_main_code(
            content=content,
            command_function_names=command_function_names,
            predicate_naming_table=predicate_naming_table,
            binding_table=binding_table,
        )

        return {
            "relative_path": "main.py",
            "content": content,
            "write_type": "rewrite",
        }

    def _get_llm_client(self, model_config: ModelConfig) -> LLMclient:
        # TODO(Codex-work-review): The user doubts this legacy LLM-backed Main
        # implementation because it creates OpenaiClient directly instead of
        # using utils.get_model_response(). That utility currently reads model
        # settings from environment variables, while this path receives the
        # compiler's ModelConfig. Reconfirm which configuration source should
        # be authoritative before treating this legacy path as final.
        if self._llm_client is None:
            self._llm_client = OpenaiClient(
                model_config["api_key"],
                model_config["model_name"],
                "",
                model_config["base_url"],
            )
        return self._llm_client


def _prepare_generation_inputs(
    *,
    workflow_structure: WorkflowStructure,
    binding_table: dict[str, Any],
    command_function_names: CommandFunctionNames,
    predicate_naming_table: PredicateNamingTable,
) -> WorkflowStructure:
    normalized_workflow = copy.deepcopy(workflow_structure)
    workflow_commands = _collect_workflow_commands(normalized_workflow)
    if (
        len(command_function_names) != len(set(command_function_names))
        or set(command_function_names) != set(workflow_commands)
    ):
        raise ValueError(
            "CommandFunctionNames do not match Workflow Structure: "
            f"functions={command_function_names}, "
            f"workflow={workflow_commands}."
        )

    workflow_predicate_paths = _collect_workflow_predicate_paths(
        normalized_workflow
    )
    if set(predicate_naming_table) != workflow_predicate_paths:
        raise ValueError(
            "PredicateNamingTable paths do not match Workflow Structure: "
            f"table={sorted(predicate_naming_table)}, "
            f"workflow={sorted(workflow_predicate_paths)}."
        )
    predicate_names = list(predicate_naming_table.values())
    if len(predicate_names) != len(set(predicate_names)):
        raise ValueError(
            "PredicateNamingTable contains duplicated function names."
        )

    _align_main_decision_indices(
        workflow_structure=normalized_workflow,
        binding_table=binding_table,
    )
    _validate_flow_bindings(
        workflow_structure=normalized_workflow,
        binding_table=binding_table,
    )
    return normalized_workflow


def _collect_workflow_commands(
    workflow_structure: WorkflowStructure,
) -> list[str]:
    commands: list[str] = []
    for flow in _all_flows(workflow_structure):
        for step in _walk_steps(flow["steps"]):
            if step["step_type"] == "command":
                commands.append(step["command_name"])
    if len(commands) != len(set(commands)):
        raise ValueError(
            "Workflow Structure contains duplicated Command positions."
        )
    return commands


def _collect_workflow_predicate_paths(
    workflow_structure: WorkflowStructure,
) -> set[str]:
    predicate_paths: set[str] = set()
    for flow in _all_flows(workflow_structure):
        if flow["predicate_path"] is not None:
            predicate_paths.add(
                _canonical_path(flow["predicate_path"])
            )
        for step in _walk_steps(flow["steps"]):
            step_type = step["step_type"]
            if step_type == "if":
                for branch in step["branches"]:
                    if branch["predicate_path"] is not None:
                        predicate_paths.add(
                            _canonical_path(branch["predicate_path"])
                        )
            elif step_type in {"while", "for"}:
                predicate_paths.add(
                    _canonical_path(step["predicate_path"])
                )
    return predicate_paths


def _align_main_decision_indices(
    *,
    workflow_structure: WorkflowStructure,
    binding_table: dict[str, Any],
) -> None:
    raw_table = binding_table.get("decision_path_table")
    if not isinstance(raw_table, dict):
        raise ValueError(
            "Flow Binding Table must contain decision_path_table."
        )

    decisions_by_path = {
        _canonical_path(step["block_path"]): step
        for step in _walk_steps(
            workflow_structure["main_flow"]["steps"]
        )
        if step["step_type"] in {"if", "while", "for"}
    }
    normalized_table: dict[int, str] = {}
    for raw_index, raw_path in raw_table.items():
        decision_index = _coerce_positive_index(
            raw_index,
            field_name="decision_path_table key",
        )
        if not isinstance(raw_path, str) or not raw_path:
            raise ValueError(
                "decision_path_table values must be non-empty paths."
            )
        if decision_index in normalized_table:
            raise ValueError(
                f"Duplicated Decision index: {decision_index}."
            )
        normalized_table[decision_index] = raw_path

    if set(normalized_table.values()) != set(decisions_by_path):
        raise ValueError(
            "decision_path_table does not match Main Flow Decisions: "
            f"table={sorted(normalized_table.values())}, "
            f"workflow={sorted(decisions_by_path)}."
        )

    for decision_index, block_path in normalized_table.items():
        decisions_by_path[block_path]["decision_index"] = decision_index


def _validate_flow_bindings(
    *,
    workflow_structure: WorkflowStructure,
    binding_table: dict[str, Any],
) -> None:
    alternative_bindings = binding_table.get("alternative_flows")
    exception_bindings = binding_table.get("exception_flows")
    if not isinstance(alternative_bindings, list):
        raise ValueError(
            "Flow Binding Table alternative_flows must be a list."
        )
    if not isinstance(exception_bindings, list):
        raise ValueError(
            "Flow Binding Table exception_flows must be a list."
        )

    expected_alternatives = [
        flow["flow_name"]
        for flow in workflow_structure["alternative_flows"]
    ]
    expected_exceptions = [
        flow["flow_name"]
        for flow in workflow_structure["exception_flows"]
    ]
    if [
        binding.get("flow_name")
        for binding in alternative_bindings
        if isinstance(binding, dict)
    ] != expected_alternatives:
        raise ValueError(
            "Alternative Flow bindings do not match Workflow Structure "
            "declaration order."
        )
    if [
        binding.get("flow_name")
        for binding in exception_bindings
        if isinstance(binding, dict)
    ] != expected_exceptions:
        raise ValueError(
            "Exception Flow bindings do not match Workflow Structure "
            "declaration order."
        )

    main_command_indices = {
        step["command_index"]
        for step in _walk_steps(
            workflow_structure["main_flow"]["steps"]
        )
        if step["step_type"] == "command"
    }
    main_decision_indices = {
        step["decision_index"]
        for step in _walk_steps(
            workflow_structure["main_flow"]["steps"]
        )
        if step["step_type"] in {"if", "while", "for"}
    }

    for binding in exception_bindings:
        _validate_binding_record(
            binding=binding,
            main_command_indices=main_command_indices,
            main_decision_indices=main_decision_indices,
            requires_go_back=False,
        )
    for binding in alternative_bindings:
        _validate_binding_record(
            binding=binding,
            main_command_indices=main_command_indices,
            main_decision_indices=main_decision_indices,
            requires_go_back=True,
        )


def _validate_binding_record(
    *,
    binding: Any,
    main_command_indices: set[int],
    main_decision_indices: set[int],
    requires_go_back: bool,
) -> None:
    if not isinstance(binding, dict):
        raise ValueError("Each Flow binding must be an object.")
    trigger_is = binding.get("trigger_is")
    if not isinstance(trigger_is, list) or not trigger_is:
        raise ValueError(
            "Each Flow binding requires a non-empty trigger_is list."
        )
    for trigger in trigger_is:
        if (
            not isinstance(trigger, dict)
            or trigger.get("index_type") != "command"
        ):
            raise ValueError(
                "Flow trigger_is entries must reference commands."
            )
        command_index = _coerce_positive_index(
            trigger.get("index"),
            field_name="trigger command index",
        )
        if command_index not in main_command_indices:
            raise ValueError(
                f"Flow trigger references unknown command{command_index}."
            )

    go_back_to = binding.get("go_back_to")
    if not requires_go_back:
        if go_back_to is not None:
            raise ValueError(
                "Exception Flow binding must not contain go_back_to."
            )
        return
    if not isinstance(go_back_to, dict):
        raise ValueError(
            "Alternative Flow binding requires go_back_to."
        )

    index_type = go_back_to.get("index_type")
    target_index = _coerce_positive_index(
        go_back_to.get("index"),
        field_name="go_back_to index",
    )
    if (
        index_type == "command"
        and target_index in main_command_indices
    ):
        return
    if (
        index_type == "decision"
        and target_index in main_decision_indices
    ):
        return
    raise ValueError(
        f"Invalid Alternative Flow go_back_to: {go_back_to!r}."
    )


def _all_flows(
    workflow_structure: WorkflowStructure,
) -> list[dict[str, Any]]:
    return [
        workflow_structure["main_flow"],
        *workflow_structure["alternative_flows"],
        *workflow_structure["exception_flows"],
    ]


def _walk_steps(
    steps: list[WorkflowStep],
) -> Iterator[WorkflowStep]:
    for step in steps:
        yield step
        if step["step_type"] == "if":
            for branch in step["branches"]:
                yield from _walk_steps(branch["steps"])
        elif step["step_type"] in {"while", "for"}:
            yield from _walk_steps(step["body_steps"])


def _canonical_path(path: list[str]) -> str:
    if (
        not path
        or any(
            not isinstance(part, str) or not part
            for part in path
        )
    ):
        raise ValueError(
            "Workflow paths must contain non-empty strings."
        )
    return ".".join(path)


def _coerce_positive_index(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} cannot be boolean.")
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdigit() and int(value) > 0:
        return int(value)
    raise ValueError(f"Invalid {field_name}: {value!r}.")


def _json_text(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        default=str,
    )


def _extract_python_code(response: str) -> str:
    content = response.strip()
    fenced_match = re.fullmatch(
        r"```(?:python)?\s*\n(?P<code>.*)\n```",
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced_match is not None:
        content = fenced_match.group("code").strip()
    if not content:
        raise ValueError("LLM returned empty main.py content.")
    return f"{content}\n"


def _validate_main_code(
    *,
    content: str,
    command_function_names: CommandFunctionNames,
    predicate_naming_table: PredicateNamingTable,
    binding_table: dict[str, Any],
) -> None:
    try:
        syntax_tree = ast.parse(content, filename="main.py")
    except SyntaxError as exc:
        raise ValueError("LLM returned invalid Python for main.py.") from exc

    main_functions = [
        node
        for node in syntax_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    ]
    other_functions = [
        node.name
        for node in syntax_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not (
            isinstance(node, ast.FunctionDef)
            and node.name == "main"
        )
    ]
    top_level_classes = [
        node.name
        for node in syntax_tree.body
        if isinstance(node, ast.ClassDef)
    ]
    if len(main_functions) != 1 or other_functions or top_level_classes:
        raise ValueError(
            "Generated main.py must define only one function named main "
            "and no classes."
        )

    main_function = main_functions[0]
    _validate_main_signature(main_function)
    _validate_required_imports(
        syntax_tree=syntax_tree,
        command_function_names=command_function_names,
        predicate_function_names=list(
            predicate_naming_table.values()
        ),
    )
    _validate_no_top_level_runtime_instances(syntax_tree)

    calls = [
        _get_callable_name(node.func)
        for node in ast.walk(main_function)
        if isinstance(node, ast.Call)
    ]
    call_counts = Counter(
        called_name
        for called_name in calls
        if called_name is not None
    )
    for command_name in command_function_names:
        if call_counts[command_name] != 1:
            raise ValueError(
                "Each Command function must have exactly one source call "
                f"in main(): {command_name!r} has "
                f"{call_counts[command_name]}."
            )

    expected_predicate_counts = _expected_predicate_call_counts(
        predicate_naming_table=predicate_naming_table,
        binding_table=binding_table,
    )
    for predicate_name, minimum_count in expected_predicate_counts.items():
        if call_counts[predicate_name] < minimum_count:
            raise ValueError(
                "Predicate function is not called at every required "
                f"control location: {predicate_name!r} expected at least "
                f"{minimum_count}, received {call_counts[predicate_name]}."
            )

    forbidden_calls = {
        "llm_client.complete",
        "state.get_variable_value",
        "state.get_variable_values",
        "state.revise_variable_value",
        "eval",
        "exec",
        "getattr",
        "globals",
        "__import__",
        "main",
    }
    used_forbidden_calls = sorted(
        forbidden_calls & set(call_counts)
    )
    if used_forbidden_calls:
        raise ValueError(
            "Generated main.py contains forbidden calls: "
            f"{used_forbidden_calls}."
        )

    if call_counts["AgentState"] != 1:
        raise ValueError(
            "main() must initialize AgentState exactly once."
        )
    if call_counts["OpenAIClient"] != 1:
        raise ValueError(
            "main() must initialize OpenAIClient exactly once."
        )
    _validate_runtime_initialization(main_function)
    if not any(
        isinstance(node, ast.While)
        for node in ast.walk(main_function)
    ) or not any(
        isinstance(node, ast.Match)
        for node in ast.walk(main_function)
    ):
        raise ValueError(
            "main() must use a while plus match/case PC dispatcher."
        )
    if not any(
        isinstance(node, ast.Return)
        and isinstance(node.value, ast.Name)
        and node.value.id == "state"
        for node in ast.walk(main_function)
    ):
        raise ValueError("main() must return state.")


def _validate_main_signature(main_function: ast.FunctionDef) -> None:
    if (
        main_function.args.posonlyargs
        or main_function.args.args
        or main_function.args.vararg is not None
        or main_function.args.kwarg is not None
        or [
            argument.arg
            for argument in main_function.args.kwonlyargs
        ] != ["state", "llm_client"]
        or len(main_function.args.kw_defaults) != 2
        or any(
            not isinstance(default, ast.Constant)
            or default.value is not None
            for default in main_function.args.kw_defaults
        )
    ):
        raise ValueError(
            "main() must accept only keyword arguments "
            "state=None and llm_client=None."
        )
    if (
        not isinstance(main_function.returns, ast.Name)
        or main_function.returns.id != "AgentState"
    ):
        raise ValueError("main() must declare -> AgentState.")


def _validate_runtime_initialization(
    main_function: ast.FunctionDef,
) -> None:
    if not _has_none_guarded_constructor(
        main_function=main_function,
        variable_name="state",
        constructor_name="AgentState",
        argument_validator=lambda argument: (
            isinstance(argument, ast.Name)
            and argument.id == "AGENT_CONFIG"
        ),
    ):
        raise ValueError(
            "main() must initialize state with "
            "AgentState(AGENT_CONFIG) only when state is None."
        )
    if not _has_none_guarded_constructor(
        main_function=main_function,
        variable_name="llm_client",
        constructor_name="OpenAIClient",
        argument_validator=_is_model_config_subscript,
    ):
        raise ValueError(
            "main() must initialize llm_client with "
            "OpenAIClient(AGENT_CONFIG['model_config']) only when "
            "llm_client is None."
        )


def _has_none_guarded_constructor(
    *,
    main_function: ast.FunctionDef,
    variable_name: str,
    constructor_name: str,
    argument_validator: Callable[[ast.expr], bool],
) -> bool:
    for node in ast.walk(main_function):
        if not isinstance(node, ast.If) or not _is_none_guard(
            node.test,
            variable_name,
        ):
            continue
        for statement in node.body:
            if (
                not isinstance(statement, ast.Assign)
                or len(statement.targets) != 1
                or not isinstance(statement.targets[0], ast.Name)
                or statement.targets[0].id != variable_name
                or not isinstance(statement.value, ast.Call)
                or _get_callable_name(statement.value.func)
                != constructor_name
                or len(statement.value.args) != 1
                or statement.value.keywords
            ):
                continue
            if argument_validator(statement.value.args[0]):
                return True
    return False


def _is_none_guard(test: ast.expr, variable_name: str) -> bool:
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == variable_name
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Is)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value is None
    )


def _is_model_config_subscript(argument: ast.expr) -> bool:
    return (
        isinstance(argument, ast.Subscript)
        and isinstance(argument.value, ast.Name)
        and argument.value.id == "AGENT_CONFIG"
        and isinstance(argument.slice, ast.Constant)
        and argument.slice.value == "model_config"
    )


def _validate_required_imports(
    *,
    syntax_tree: ast.Module,
    command_function_names: list[str],
    predicate_function_names: list[str],
) -> None:
    relative_imports: dict[str, set[str]] = {}
    for node in syntax_tree.body:
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 1
            and node.module is not None
        ):
            relative_imports.setdefault(node.module, set()).update(
                alias.name for alias in node.names
            )

    required_imports = {
        "commands": set(command_function_names),
        "predicates": set(predicate_function_names),
        "config": {"AGENT_CONFIG"},
        "model": {"AgentState"},
        "utils": {"OpenAIClient"},
    }
    for module_name, imported_names in required_imports.items():
        missing_names = (
            imported_names - relative_imports.get(module_name, set())
        )
        if missing_names:
            raise ValueError(
                f"Generated main.py is missing imports from "
                f".{module_name}: {sorted(missing_names)}."
            )


def _validate_no_top_level_runtime_instances(
    syntax_tree: ast.Module,
) -> None:
    for node in syntax_tree.body:
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Call)
                and _get_callable_name(child.func)
                in {"AgentState", "OpenAIClient"}
            ):
                raise ValueError(
                    "AgentState and OpenAIClient must only be initialized "
                    "inside main()."
                )


def _expected_predicate_call_counts(
    *,
    predicate_naming_table: PredicateNamingTable,
    binding_table: dict[str, Any],
) -> dict[str, int]:
    expected_counts = {
        predicate_name: 1
        for predicate_name in predicate_naming_table.values()
    }
    bindings = [
        *binding_table["exception_flows"],
        *binding_table["alternative_flows"],
    ]
    for binding in bindings:
        flow_path = binding.get("flow_path")
        if not isinstance(flow_path, str):
            raise ValueError(
                "Each Flow binding requires a string flow_path."
            )
        canonical_flow_path = flow_path
        if canonical_flow_path not in predicate_naming_table:
            canonical_flow_path = (
                flow_path
                if flow_path.startswith("worker.")
                else f"worker.{flow_path}"
            )
        try:
            predicate_name = predicate_naming_table[
                canonical_flow_path
            ]
        except KeyError as exc:
            raise ValueError(
                f"Flow binding path {flow_path!r} has no Predicate."
            ) from exc
        expected_counts[predicate_name] = len(binding["trigger_is"])
    return expected_counts


def _get_callable_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent_name = _get_callable_name(node.value)
        if parent_name is None:
            return node.attr
        return f"{parent_name}.{node.attr}"
    return None
