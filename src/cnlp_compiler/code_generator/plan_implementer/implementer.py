from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from ...schema import (
    CNLPTypeIR,
    ImplementationPlan,
    ModelConfig,
    StaticAttributes,
    VariableNode,
    WorkflowStructure,
    create_empty_static_attributes,
)
from .implementations import create_default_implementation_registry
from ..reference_code_catalog import ReferenceCodeCatalog
from .registry import ImplementationRegistry
from .schema import (
    GeneratedFile,
    ImplementationContext,
)
from .type_converter import TypeConverter


class PlanImplementer:
    """The only public entry point for turning a plan into generated files."""

    def __init__(
        self,
        *,
        type_converter: TypeConverter | None = None,
        reference_code_catalog: ReferenceCodeCatalog | None = None,
        implementation_registry: ImplementationRegistry | None = None,
    ) -> None:
        self.type_converter = type_converter or TypeConverter()
        self.reference_code_catalog = (
            reference_code_catalog
            if reference_code_catalog is not None
            else ReferenceCodeCatalog()
        )

        self.implementation_registry = (
            implementation_registry
            or create_default_implementation_registry(
                reference_code_catalog=self.reference_code_catalog,
            )
        )

    def implement(
        self,
        *,
        target_implementation: str,
        cnlp_script: str,
        implementation_plan: ImplementationPlan,
        static_attributes: StaticAttributes | None = None,
        variables: Sequence[VariableNode],
        cnlp_types: Sequence[CNLPTypeIR],
        workflow_structures: dict[str, WorkflowStructure],
        binding_table: dict[str, Any],
        model_config: ModelConfig,
    ) -> Iterator[GeneratedFile]:
        generator = self.implementation_registry.get(
            target_implementation
        )
        normalized_cnlp_types = list(cnlp_types)
        converted_types = self.type_converter.convert_with_schema_index(
            normalized_cnlp_types
        )

        context = ImplementationContext(
            cnlp_script=cnlp_script,
            implementation_plan=implementation_plan,
            static_attributes=(
                static_attributes or create_empty_static_attributes()
            ),
            variables=list(variables),
            cnlp_types=normalized_cnlp_types,
            python_type_code=converted_types["python_type_code"],
            python_schema_code_table=converted_types[
                "schema_code_table"
            ],
            python_schema_dependency_table=converted_types[
                "schema_dependency_table"
            ],
            workflow_structures=workflow_structures,
            binding_table=binding_table,
            model_config=model_config,
        )
        yield from generator.generate(context)
