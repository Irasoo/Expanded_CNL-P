from __future__ import annotations

from ..context import RuleContext
from ..diagnostic import SemanticDiagnostic
from ..facts import format_path


class GlobalReferenceRule:
    """ICLR tasks 001/002: Persona and Constraint references are global."""

    rule_id = "ICLR-SEM-GLOBAL-REFERENCE"

    def check(self, context: RuleContext) -> list[SemanticDiagnostic]:
        diagnostics: list[SemanticDiagnostic] = []
        sections = (
            (context.facts.persona_references, "ICLR-SEM-001", "Persona"),
            (context.facts.constraint_references, "ICLR-SEM-002", "Constraint"),
        )
        for references, code, section in sections:
            for reference in references:
                if reference.name in context.environment.global_variables:
                    continue
                diagnostics.append(
                    SemanticDiagnostic(
                        code=code,
                        message=(
                            f"{section} references global variable "
                            f"'{reference.name}', but that variable is not "
                            "provided by this instance."
                        ),
                        path=format_path(reference.path),
                    )
                )
        return diagnostics


class VariableFlowRule:
    """ICLR tasks 003/004/005/014 over inline temporary declarations."""

    rule_id = "ICLR-SEM-VARIABLE-FLOW"

    def check(self, context: RuleContext) -> list[SemanticDiagnostic]:
        return list(context.flow.diagnostics)


__all__ = ["GlobalReferenceRule", "VariableFlowRule"]
