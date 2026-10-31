from __future__ import annotations

import json
import time
from typing import Any

from ..node_visitor import NodeVisitor
from ..schema import (
    CNLPTypeIR,
    CommandNode,
    ConditionNode,
    ImplementationPlan,
    ModelConfig,
    StaticAttributes,
    VariableNode,
    WorkerNode,
    WorkflowStructure,
)
from .implementation_planner import ImplementationPlanner
from .plan_implementer import PlanImplementer
from .reference_code_catalog import ReferenceCodeCatalog
from .virtual_file_system import VirtualFileSystem


class CodeGenerator:
    """Plan and implement generated files in a virtual file system."""

    IMPLEMENTATION_PLAN_PATH = "implementation_plan.json"

    def __init__(
        self,
        config: dict[str, Any],
        *,
        implementation_planner: ImplementationPlanner | None = None,
        plan_implementer: PlanImplementer | None = None,
        reference_code_catalog: ReferenceCodeCatalog | None = None,
        virtual_file_system: VirtualFileSystem | None = None,
    ):
        self.config = config
        supplied_implementer_catalog = (
            getattr(
                plan_implementer,
                "reference_code_catalog",
                None,
            )
            if plan_implementer is not None
            else None
        )
        shared_reference_code_catalog = (
            reference_code_catalog
            if reference_code_catalog is not None
            else (
                supplied_implementer_catalog
                if supplied_implementer_catalog is not None
                else ReferenceCodeCatalog()
            )
        )
        self.implementation_planner = (
            implementation_planner
            or ImplementationPlanner(
                reference_code_catalog=shared_reference_code_catalog,
            )
        )
        self.plan_implementer = (
            plan_implementer
            or PlanImplementer(
                reference_code_catalog=shared_reference_code_catalog,
            )
        )
        self.virtual_file_system = (
            virtual_file_system or VirtualFileSystem()
        )

    def generate(
        self,
        cnlp_script: str,
        cnlp_ast: dict[str, Any],
        binding_table: dict[str, Any],
        model_config: ModelConfig,
        target_implementation: str,
    ) -> VirtualFileSystem:
        """Generate one target implementation into a virtual file system."""
        implementation_plan = self.plan(
            cnlp_script=cnlp_script,
            cnlp_ast=cnlp_ast,
        )
        variables = NodeVisitor.find_all_variables(cnlp_ast)
        static_attributes = NodeVisitor.find_static_attributes(cnlp_ast)
        cnlp_types = NodeVisitor.find_all_types(cnlp_ast)
        workflow_structures = NodeVisitor.find_workflow_structures(cnlp_ast)
        implementation_started_at = time.monotonic()
        print(
            "[Compiler][Stage 4/4][Implementation] Started; "
            f"target={target_implementation}.",
            flush=True,
        )
        virtual_file_system = self._implement(
            target_implementation=target_implementation,
            cnlp_script=cnlp_script,
            implementation_plan=implementation_plan,
            static_attributes=static_attributes,
            variables=variables,
            cnlp_types=cnlp_types,
            workflow_structures=workflow_structures,
            binding_table=binding_table,
            model_config=model_config,
        )
        print(
            "[Compiler][Stage 4/4][Implementation] Completed in "
            f"{time.monotonic() - implementation_started_at:.2f}s.",
            flush=True,
        )
        return virtual_file_system

    def plan(
        self,
        *,
        cnlp_script: str,
        cnlp_ast: dict[str, Any],
    ) -> ImplementationPlan:
        """Create the implementation-independent Plan without generating files."""
        (
            workers,
            commands_by_worker,
            conditions_by_worker,
            variables,
        ) = self._extract_planning_nodes(cnlp_ast)
        command_count = sum(len(items) for items in commands_by_worker.values())
        condition_count = sum(
            len(items) for items in conditions_by_worker.values()
        )
        print(
            "[Compiler][Stage 3/4][Planning] Input contains "
            f"{len(workers)} Worker(s), {command_count} Command(s), "
            f"{condition_count} Predicate(s), and {len(variables)} Variable(s).",
            flush=True,
        )
        static_attributes = NodeVisitor.find_static_attributes(cnlp_ast)
        cnlp_types = NodeVisitor.find_all_types(cnlp_ast)
        planning_started_at = time.monotonic()
        print("[Compiler][Stage 3/4][Planning] Started.", flush=True)
        implementation_plan = self._plan(
            cnlp_script=cnlp_script,
            workers=workers,
            commands_by_worker=commands_by_worker,
            conditions_by_worker=conditions_by_worker,
            variables=variables,
            cnlp_types=cnlp_types,
            static_attributes=static_attributes,
        )
        print(
            "[Compiler][Stage 3/4][Planning] Completed in "
            f"{time.monotonic() - planning_started_at:.2f}s.",
            flush=True,
        )
        return implementation_plan

    @staticmethod
    def _extract_planning_nodes(
        cnlp_ast: dict[str, Any],
    ) -> tuple[
        list[WorkerNode],
        dict[str, list[CommandNode]],
        dict[str, list[ConditionNode]],
        list[VariableNode],
    ]:
        return (
            NodeVisitor.find_all_workers(cnlp_ast),
            NodeVisitor.find_commands_by_worker(cnlp_ast),
            NodeVisitor.find_conditions_by_worker(cnlp_ast),
            NodeVisitor.find_all_variables(cnlp_ast),
        )

    def _plan(
        self,
        *,
        cnlp_script: str,
        workers: list[WorkerNode],
        commands_by_worker: dict[str, list[CommandNode]],
        conditions_by_worker: dict[str, list[ConditionNode]],
        variables: list[VariableNode],
        cnlp_types: list[CNLPTypeIR],
        static_attributes: StaticAttributes,
    ) -> ImplementationPlan:
        return self.implementation_planner.plan(
            cnlp_script=cnlp_script,
            workers=workers,
            commands_by_worker=commands_by_worker,
            conditions_by_worker=conditions_by_worker,
            variables=variables,
            cnlp_types=cnlp_types,
            static_attributes=static_attributes,
        )

    def _implement(
        self,
        *,
        target_implementation: str,
        cnlp_script: str,
        implementation_plan: ImplementationPlan,
        static_attributes: StaticAttributes,
        variables: list[VariableNode],
        cnlp_types: list[CNLPTypeIR],
        workflow_structures: dict[str, WorkflowStructure],
        binding_table: dict[str, Any],
        model_config: ModelConfig,
    ) -> VirtualFileSystem:
        self.virtual_file_system.reset()
        # Persist the exact Planner result before any concrete Implementer is
        # consumed. Native and LangGraph therefore receive and record the same
        # plan; the snapshot is not regenerated or inferred from their files.
        self.virtual_file_system.write(
            path=self.IMPLEMENTATION_PLAN_PATH,
            content=self._serialize_implementation_plan(
                implementation_plan
            ),
            type="rewrite",
        )
        print(
            "[Compiler][Implementation] Recorded "
            f"{self.IMPLEMENTATION_PLAN_PATH} (rewrite).",
            flush=True,
        )
        generated_files = self.plan_implementer.implement(
            target_implementation=target_implementation,
            cnlp_script=cnlp_script,
            implementation_plan=implementation_plan,
            static_attributes=static_attributes,
            variables=variables,
            cnlp_types=cnlp_types,
            workflow_structures=workflow_structures,
            binding_table=binding_table,
            model_config=model_config,
        )
        for generated_file in generated_files:
            self.virtual_file_system.write_generated_file(generated_file)
            print(
                "[Compiler][Implementation] Collected "
                f"{generated_file['relative_path']} "
                f"({generated_file['write_type']}).",
                flush=True,
            )
        print(
            "[Compiler][Implementation] All generated file chunks collected.",
            flush=True,
        )
        return self.virtual_file_system

    @staticmethod
    def _serialize_implementation_plan(
        implementation_plan: ImplementationPlan,
    ) -> str:
        """Serialize one Planner result without silently stringifying data."""
        try:
            return json.dumps(
                implementation_plan,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            ) + "\n"
        except (TypeError, ValueError) as exc:
            raise TypeError(
                "ImplementationPlan must contain only JSON-serializable "
                "data before code generation starts."
            ) from exc
