from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Literal, Protocol, TypedDict

from ...schema import (
    CNLPTypeIR,
    ImplementationPlan,
    ModelConfig,
    StaticAttributes,
    VariableNode,
    WorkflowStructure,
)


class GeneratedFile(TypedDict):
    """One virtual-file-system operation yielded by an implementation."""

    relative_path: str
    content: str | bytes
    write_type: Literal["rewrite", "append"]


class ImplementationContext(TypedDict):
    """Stable input supplied to a concrete implementation generator."""

    cnlp_script: str
    implementation_plan: ImplementationPlan

    # Normalized Persona, Audience, Concepts, and Constraints. This is
    # semantic context for code generation, not another Plan result.
    static_attributes: StaticAttributes
    variables: list[VariableNode]
    cnlp_types: list[CNLPTypeIR]

    # Complete generated Python types, used to materialize schema.py.
    python_type_code: str

    # Declared CNL-P type name -> generated Python declaration source.
    python_schema_code_table: dict[str, str]

    # Declared CNL-P type name -> declared types referenced by that schema.
    python_schema_dependency_table: dict[str, list[str]]

    # Worker symbol -> normalized control structure extracted mechanically.
    workflow_structures: dict[str, WorkflowStructure]

    # Worker symbol -> Alternative/Exception Flow binding table.
    binding_table: dict[str, Any]
    model_config: ModelConfig


class ImplementationGenerator(Protocol):
    def generate(
        self,
        context: ImplementationContext,
    ) -> Iterator[GeneratedFile]:
        ...
