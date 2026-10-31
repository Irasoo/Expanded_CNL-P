from __future__ import annotations

from ..context import RuleContext
from ..diagnostic import SemanticDiagnostic
from ..facts import CommandFact, format_path


class WorkerCallContractRule:
    """Validate explicit CALL contracts between Workers in one Agent."""

    rule_id = "TOSEM-SEM-WORKER-CALL-CONTRACT"

    def check(self, context: RuleContext) -> list[SemanticDiagnostic]:
        diagnostics: list[SemanticDiagnostic] = []
        for command in context.facts.commands:
            if command.command_type != "call_worker" or command.api_name is None:
                continue

            target_name = command.api_name
            declared_inputs = context.facts.worker_inputs.get(
                target_name,
                frozenset(),
            )
            required_inputs = context.facts.worker_required_inputs.get(
                target_name,
                frozenset(),
            )
            supplied_inputs = {
                argument.parameter_name for argument in command.arguments
            }

            extra = sorted(supplied_inputs - declared_inputs)
            missing = sorted(required_inputs - supplied_inputs)
            if extra:
                diagnostics.append(
                    self._diagnostic(
                        command,
                        "TOSEM-SEM-019",
                        (
                            f"CALL Worker '{target_name}' supplies undeclared "
                            f"INPUTS: {extra}."
                        ),
                    )
                )
            if missing:
                diagnostics.append(
                    self._diagnostic(
                        command,
                        "TOSEM-SEM-018",
                        (
                            f"CALL Worker '{target_name}' is missing required "
                            f"INPUTS: {missing}."
                        ),
                    )
                )

            declared_outputs = context.facts.worker_outputs.get(
                target_name,
                frozenset(),
            )
            if command.has_response and not declared_outputs:
                diagnostics.append(
                    self._diagnostic(
                        command,
                        "TOSEM-SEM-020",
                        (
                            f"CALL Worker '{target_name}' declares RESPONSE, "
                            "but the target Worker has no OUTPUTS."
                        ),
                    )
                )
        return diagnostics

    @staticmethod
    def _diagnostic(
        command: CommandFact,
        code: str,
        message: str,
    ) -> SemanticDiagnostic:
        return SemanticDiagnostic(
            code=code,
            message=message,
            path=format_path(command.path),
            worker_name=command.worker_name,
            command_name=command.name,
        )


__all__ = ["WorkerCallContractRule"]
