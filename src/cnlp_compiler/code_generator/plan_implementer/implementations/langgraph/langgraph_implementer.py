from __future__ import annotations

import ast
import copy
import re
from collections.abc import Iterator
from typing import Any

from ....reference_code_catalog import ReferenceCodeCatalog
from .....schema import create_empty_static_attributes
from ...schema import GeneratedFile, ImplementationContext
from ...type_converter import TypeConverter
from ..native.command_plan_implementer import CommandPlanImplementer
from ..native.deterministic_config_implementer import (
    DeterministicConfigImplementer,
)
from ..native.predicate_plan_implementer import PredicatePlanImplementer
from ..native.schema import (
    CommandImplementationResult,
    PredicateImplementationResult,
    TypeImplementationResult,
)
from ..native.static_code_generator import StaticCodeGenerator
from .call_worker_command_implementer import (
    LangGraphCallWorkerCommandPlanImplementer,
)
from .workflow_implementer import WorkflowGraphImplementer


class LangGraphImplementer:
    """Generate a LangGraph project from the implementation-neutral Plan."""

    def __init__(
        self,
        *,
        reference_code_catalog: ReferenceCodeCatalog,
        static_code_generator: StaticCodeGenerator | None = None,
        config_implementer: DeterministicConfigImplementer | None = None,
        command_plan_implementer: CommandPlanImplementer | None = None,
        predicate_plan_implementer: PredicatePlanImplementer | None = None,
        workflow_implementer: WorkflowGraphImplementer | None = None,
    ) -> None:
        self.reference_code_catalog = reference_code_catalog
        self.static_code_generator = static_code_generator or StaticCodeGenerator()
        self.config_implementer = (
            config_implementer or DeterministicConfigImplementer()
        )
        self.command_plan_implementer = (
            command_plan_implementer
            or CommandPlanImplementer(
                call_worker_command_implementer=(
                    LangGraphCallWorkerCommandPlanImplementer()
                )
            )
        )
        self.predicate_plan_implementer = (
            predicate_plan_implementer or PredicatePlanImplementer()
        )
        self.workflow_implementer = workflow_implementer or WorkflowGraphImplementer()

    def generate(
        self,
        context: ImplementationContext,
    ) -> Iterator[GeneratedFile]:
        print(
            "[Compiler][Implementation][LangGraph] Static files...",
            flush=True,
        )
        yield from self.static_code_generator.generate_static_code()

        print(
            "[Compiler][Implementation][LangGraph] schema.py...",
            flush=True,
        )
        type_result = self._implement_types(context)
        yield type_result["generated_file"]
        print(
            "[Compiler][Implementation][LangGraph] config.py...",
            flush=True,
        )
        yield self.config_implementer.implement(
            static_attributes=context["static_attributes"],
            variables=context["variables"],
            model_config=context["model_config"],
            type_result=type_result,
        )

        prepared = _prepare_workers(context)
        print(
            "[Compiler][Implementation][LangGraph] commands.py...",
            flush=True,
        )
        command_result = self._implement_commands(
            context,
            prepared["command_plans"],
        )
        yield command_result["generated_file"]

        print(
            "[Compiler][Implementation][LangGraph] predicates.py...",
            flush=True,
        )
        predicate_result = self._implement_predicates(
            context,
            prepared["predicate_plans"],
        )
        yield predicate_result["generated_file"]

        print(
            "[Compiler][Implementation][LangGraph] workflow.py and main.py...",
            flush=True,
        )
        yield from self.workflow_implementer.implement(
            entry_worker=context["implementation_plan"]["entry_worker"],
            workflow_structures=prepared["workflow_structures"],
            binding_tables=prepared["binding_tables"],
            command_names_by_worker=prepared["command_names_by_worker"],
            predicate_naming_table=predicate_result["predicate_naming_table"],
        )

    def _implement_commands(
        self,
        context: ImplementationContext,
        command_plans: list,
    ) -> CommandImplementationResult:
        return self.command_plan_implementer.implement(
            command_plans=command_plans,
            static_attributes=context.get(
                "static_attributes",
                create_empty_static_attributes(),
            ),
            variables=context["variables"],
            python_schema_code_table=context["python_schema_code_table"],
            python_schema_dependency_table=context["python_schema_dependency_table"],
            model_config=context["model_config"],
            reference_code_catalog=self.reference_code_catalog,
        )

    def _implement_predicates(
        self,
        context: ImplementationContext,
        predicate_plans: list,
    ) -> PredicateImplementationResult:
        return self.predicate_plan_implementer.implement(
            predicate_plans=predicate_plans,
            variables=context["variables"],
            python_schema_code_table=context["python_schema_code_table"],
            python_schema_dependency_table=context["python_schema_dependency_table"],
            model_config=context["model_config"],
        )

    @staticmethod
    def _implement_types(
        context: ImplementationContext,
    ) -> TypeImplementationResult:
        python_type_code = context["python_type_code"]
        declared_type_names = [
            cnlp_type["type_name"] for cnlp_type in context["cnlp_types"]
        ]
        config_type_result = TypeConverter.convert_config_variable_types(
            variables=context["variables"],
            declared_type_names=declared_type_names,
            occupied_type_names=_python_type_names(python_type_code),
        )
        complete_python_type_code = "".join(
            (
                python_type_code,
                config_type_result["inline_python_type_code"],
            )
        )
        return {
            "generated_file": {
                "relative_path": "schema.py",
                "content": (
                    f"\n{complete_python_type_code}"
                    if complete_python_type_code
                    else ""
                ),
                "write_type": "append",
            },
            "python_type_code": complete_python_type_code,
            "declared_type_names": declared_type_names,
            "variable_type_expression_table": config_type_result[
                "variable_type_expression_table"
            ],
            "config_schema_import_names": config_type_result[
                "schema_import_names"
            ],
            "config_typing_import_names": config_type_result[
                "typing_import_names"
            ],
        }


def _python_type_names(source: str) -> list[str]:
    """Collect names already emitted into schema.py for collision avoidance."""
    if not source.strip():
        return []
    syntax_tree = ast.parse(source, filename="generated_cnlp_types.py")
    names: list[str] = []
    for node in syntax_tree.body:
        if isinstance(node, ast.ClassDef):
            names.append(node.name)
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
        ):
            names.append(node.target.id)
    return names


def _prepare_workers(context: ImplementationContext) -> dict[str, Any]:
    all_command_plans = []
    all_predicate_plans = []
    command_names_by_worker = {}
    workflow_structures = {}
    binding_tables = {}
    predicate_index = 1

    for worker_name, worker_plan in context["implementation_plan"]["workers"].items():
        prefix = _python_slug(worker_name)
        commands = copy.deepcopy(worker_plan["commands"])
        for command in commands:
            command["command_name"] = f"{prefix}__{command['command_name']}"
        all_command_plans.extend(commands)
        command_names_by_worker[worker_name] = [
            command["command_name"] for command in commands
        ]

        predicates = copy.deepcopy(worker_plan["predicates"])
        for predicate in predicates:
            predicate["predicate_index"] = predicate_index
            predicate["predicate_name"] = f"predicate{predicate_index}"
            predicate["condition_path"] = _qualify_path(
                predicate["condition_path"],
                worker_name,
            )
            predicate_index += 1
        all_predicate_plans.extend(predicates)

        workflow = copy.deepcopy(context["workflow_structures"][worker_name])
        _qualify_workflow(
            workflow,
            worker_name=worker_name,
            command_prefix=prefix,
        )
        workflow_structures[worker_name] = workflow

        binding = copy.deepcopy(context["binding_table"][worker_name])
        _qualify_binding_paths(binding, worker_name)
        binding_tables[worker_name] = binding

    return {
        "command_plans": all_command_plans,
        "predicate_plans": all_predicate_plans,
        "command_names_by_worker": command_names_by_worker,
        "workflow_structures": workflow_structures,
        "binding_tables": binding_tables,
    }


def _python_slug(name: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_").lower()
    if not slug:
        raise ValueError(f"Worker name cannot form a Python name: {name!r}.")
    return f"w_{slug}" if slug[0].isdigit() else slug


def _qualify_path(path: list[str], worker_name: str) -> list[str]:
    if path and path[0] == "worker":
        return ["workers", worker_name, *path[1:]]
    return path


def _qualify_workflow(
    value: Any,
    *,
    worker_name: str,
    command_prefix: str,
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "command_name" and isinstance(child, str):
                value[key] = f"{command_prefix}__{child}"
            elif key.endswith("_path") and isinstance(child, list):
                value[key] = _qualify_path(child, worker_name)
            else:
                _qualify_workflow(
                    child,
                    worker_name=worker_name,
                    command_prefix=command_prefix,
                )
    elif isinstance(value, list):
        for child in value:
            _qualify_workflow(
                child,
                worker_name=worker_name,
                command_prefix=command_prefix,
            )


def _qualify_binding_paths(value: Any, worker_name: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"main_flow_path", "flow_path"} and isinstance(child, str):
                value[key] = _qualify_dot_path(child, worker_name)
            elif key == "decision_path_table" and isinstance(child, dict):
                for index, path in child.items():
                    if isinstance(path, str):
                        child[index] = _qualify_dot_path(path, worker_name)
            else:
                _qualify_binding_paths(child, worker_name)
    elif isinstance(value, list):
        for child in value:
            _qualify_binding_paths(child, worker_name)


def _qualify_dot_path(path: str, worker_name: str) -> str:
    if path.startswith("workers."):
        return path
    if path == "worker":
        return f"workers.{worker_name}"
    if path.startswith("worker."):
        return f"workers.{worker_name}.{path[len('worker.'):]}"
    return f"workers.{worker_name}.{path}"
