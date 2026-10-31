from __future__ import annotations

import ast
import copy
import re
from collections.abc import Iterator

from ....reference_code_catalog import ReferenceCodeCatalog
from .....schema import create_empty_static_attributes
from ...schema import GeneratedFile, ImplementationContext
from ...type_converter import TypeConverter
from .command_plan_implementer import CommandPlanImplementer
from .config_implementer import ConfigImplementer
from .deterministic_config_implementer import (
    DeterministicConfigImplementer,
)
from .deterministic_main_implementer import DeterministicMainImplementer
from .main_implementer import MainImplementer
from .predicate_plan_implementer import PredicatePlanImplementer
from .schema import (
    CommandImplementationResult,
    PredicateImplementationResult,
    TypeImplementationResult,
)
from .static_code_generator import StaticCodeGenerator


class NativeImplementer:
    """Run Native generation stages in their required dependency order."""

    def __init__(
        self,
        *,
        reference_code_catalog: ReferenceCodeCatalog,
        static_code_generator: StaticCodeGenerator | None = None,
        use_llm_config_implementer: bool = False,
        deterministic_config_implementer: (
            DeterministicConfigImplementer | None
        ) = None,
        config_implementer: ConfigImplementer | None = None,
        command_plan_implementer: CommandPlanImplementer | None = None,
        predicate_plan_implementer: PredicatePlanImplementer | None = None,
        use_llm_main_implementer: bool = False,
        deterministic_main_implementer: DeterministicMainImplementer | None = None,
        main_implementer: MainImplementer | None = None,
    ) -> None:
        self.reference_code_catalog = reference_code_catalog
        self.static_code_generator = static_code_generator or StaticCodeGenerator()
        self.use_llm_config_implementer = use_llm_config_implementer
        self.deterministic_config_implementer = (
            deterministic_config_implementer
            or DeterministicConfigImplementer()
        )
        # Preserved compiler-time LLM implementation. The default Native path
        # no longer calls it; use_llm_config_implementer is the explicit
        # comparison switch.
        self.config_implementer = config_implementer or ConfigImplementer()
        self.command_plan_implementer = (
            command_plan_implementer or CommandPlanImplementer()
        )
        self.predicate_plan_implementer = (
            predicate_plan_implementer or PredicatePlanImplementer()
        )
        self.use_llm_main_implementer = use_llm_main_implementer
        self.deterministic_main_implementer = (
            deterministic_main_implementer or DeterministicMainImplementer()
        )
        self.main_implementer = main_implementer or MainImplementer()

    def generate(
        self,
        context: ImplementationContext,
    ) -> Iterator[GeneratedFile]:
        print("[Compiler][Implementation][Native] Static files...", flush=True)
        yield from self._generate_static_code()

        print("[Compiler][Implementation][Native] schema.py...", flush=True)
        type_result = self._implement_types(context)
        yield type_result["generated_file"]

        print("[Compiler][Implementation][Native] config.py...", flush=True)
        yield self._implement_config(context, type_result)

        prepared = self._prepare_workers(context)

        print("[Compiler][Implementation][Native] commands.py...", flush=True)
        command_result = self._implement_commands(
            context,
            prepared["command_plans"],
        )
        yield command_result["generated_file"]

        print("[Compiler][Implementation][Native] predicates.py...", flush=True)
        predicate_result = self._implement_predicates(
            context,
            prepared["predicate_plans"],
        )
        yield predicate_result["generated_file"]

        worker_modules = {}
        worker_names = list(context["implementation_plan"]["workers"])
        for worker_index, worker_name in enumerate(worker_names, start=1):
            print(
                f"[Compiler][Implementation][Native] Worker control "
                f"{worker_index}/{len(worker_names)} {worker_name}...",
                flush=True,
            )
            worker_modules[worker_name] = self._implement_worker_module(
                context=context,
                worker_name=worker_name,
                prepared=prepared,
                predicate_result=predicate_result,
            )
        print("[Compiler][Implementation][Native] main.py...", flush=True)
        yield self._combine_worker_modules(
            context=context,
            worker_modules=worker_modules,
            command_result=command_result,
            predicate_result=predicate_result,
        )

    def _generate_static_code(self) -> Iterator[GeneratedFile]:
        yield from self.static_code_generator.generate_static_code()

    def _implement_config(
        self,
        context: ImplementationContext,
        type_result: TypeImplementationResult,
    ) -> GeneratedFile:
        if not self.use_llm_config_implementer:
            return self.deterministic_config_implementer.implement(
                static_attributes=context["static_attributes"],
                variables=context["variables"],
                model_config=context["model_config"],
                type_result=type_result,
            )

        return self.config_implementer.implement(
            cnlp_script=context["cnlp_script"],
            variables=context["variables"],
            model_config=context["model_config"],
            type_result=type_result,
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

    def _implement_worker_module(
        self,
        *,
        context: ImplementationContext,
        worker_name: str,
        prepared: dict,
        predicate_result: PredicateImplementationResult,
    ) -> GeneratedFile:
        common_arguments = {
            "worker_name": worker_name,
            "workflow_structure": prepared["workflow_structures"][worker_name],
            "binding_table": prepared["binding_tables"][worker_name],
            "command_function_names": prepared["command_names_by_worker"][worker_name],
            "predicate_naming_table": {
                path: predicate_result["predicate_naming_table"][path]
                for path in prepared["predicate_paths_by_worker"][worker_name]
            },
        }
        if not self.use_llm_main_implementer:
            return self.deterministic_main_implementer.implement(
                **common_arguments,
            )

        # MainImplementer is the preserved compiler-time LLM implementation.
        # It predates worker_name in the interface, so pass only its original
        # inputs here.
        common_arguments.pop("worker_name")
        return self.main_implementer.implement(
            cnlp_script=context["cnlp_script"],
            model_config=context["model_config"],
            **common_arguments,
        )

    @staticmethod
    def _combine_worker_modules(
        *,
        context: ImplementationContext,
        worker_modules: dict[str, GeneratedFile],
        command_result: CommandImplementationResult,
        predicate_result: PredicateImplementationResult,
    ) -> GeneratedFile:
        entry_worker = context["implementation_plan"]["entry_worker"]
        command_import = _render_import(
            "commands",
            command_result["command_function_names"],
        )
        predicate_import = _render_import(
            "predicates",
            list(predicate_result["predicate_naming_table"].values()),
        )
        runner_sources = []
        for worker_name, generated_file in worker_modules.items():
            source = generated_file["content"]
            if not isinstance(source, str):
                raise TypeError("Generated Worker control code must be text.")
            syntax_tree = ast.parse(source, filename=f"{worker_name}.py")
            main_functions = [
                node
                for node in syntax_tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "main"
            ]
            if len(main_functions) != 1:
                raise ValueError(
                    f"Worker {worker_name!r} must generate exactly one main()."
                )
            runner = copy.deepcopy(main_functions[0])
            runner.name = f"run_{_python_slug(worker_name)}"
            ast.fix_missing_locations(runner)
            runner_sources.append(ast.unparse(runner))

        entry_runner = f"run_{_python_slug(entry_worker)}"
        content = f"""{command_import}
{predicate_import}
from .config import AGENT_CONFIG
from .model import AgentState
from .utils import OpenAIClient


{chr(10).join(runner_sources)}


def main(
    *,
    state: AgentState | None = None,
    llm_client: OpenAIClient | None = None,
) -> AgentState:
    if state is None:
        state = AgentState(AGENT_CONFIG)
    if llm_client is None:
        llm_client = OpenAIClient(AGENT_CONFIG["model_config"])
    return {entry_runner}(state=state, llm_client=llm_client)


if __name__ == "__main__":
    main()
"""
        compile(content, "main.py", "exec")
        return {
            "relative_path": "main.py",
            "content": content,
            "write_type": "rewrite",
        }

    @staticmethod
    def _prepare_workers(context: ImplementationContext) -> dict:
        """Qualify local symbols while retaining per-Worker routing tables."""
        all_command_plans = []
        all_predicate_plans = []
        command_names_by_worker = {}
        predicate_paths_by_worker = {}
        workflow_structures = {}
        binding_tables = {}
        predicate_index = 1

        for worker_name, worker_plan in context["implementation_plan"][
            "workers"
        ].items():
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
            predicate_paths_by_worker[worker_name] = [
                ".".join(predicate["condition_path"]) for predicate in predicates
            ]

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
            "predicate_paths_by_worker": predicate_paths_by_worker,
            "workflow_structures": workflow_structures,
            "binding_tables": binding_tables,
        }

    def _implement_types(
        self,
        context: ImplementationContext,
    ) -> TypeImplementationResult:
        python_type_code = context["python_type_code"]
        # Keep the converted code and declared names after yielding schema.py;
        # config.py consumes the same result when selecting type imports.

        # 在此之前，static code已经生成了一份默认的schema.py

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


def _python_slug(name: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_").lower()
    if not slug:
        raise ValueError(f"Worker name cannot form a Python name: {name!r}.")
    return f"w_{slug}" if slug[0].isdigit() else slug


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


def _render_import(module_name: str, names: list[str]) -> str:
    if not names:
        return ""
    lines = [f"from .{module_name} import ("]
    lines.extend(f"    {name}," for name in names)
    lines.append(")")
    return "\n".join(lines)


def _qualify_path(path: list[str], worker_name: str) -> list[str]:
    if path and path[0] == "worker":
        return ["workers", worker_name, *path[1:]]
    return path


def _qualify_workflow(
    value,
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


def _qualify_binding_paths(value, worker_name: str) -> None:
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
