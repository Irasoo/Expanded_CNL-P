from __future__ import annotations

from ..context import RuleContext
from ..diagnostic import SemanticDiagnostic
from ..facts import CommandFact, format_path


class APICallContractRule:
    """ICLR tasks 009-013: existence, parameters, and return handling."""

    rule_id = "ICLR-SEM-API-CONTRACT"

    def check(self, context: RuleContext) -> list[SemanticDiagnostic]:
        diagnostics: list[SemanticDiagnostic] = []
        for command in context.facts.commands:
            if command.command_type != "call_api" or command.api_name is None:
                continue
            api = context.environment.apis.get(command.api_name)
            if api is None:
                diagnostics.append(
                    self._diagnostic(
                        command,
                        "ICLR-SEM-009",
                        f"API '{command.api_name}' does not exist.",
                    )
                )
                continue

            supplied = {argument.parameter_name for argument in command.arguments}
            expected = set(api.parameters)
            extra = sorted(supplied - expected)
            missing = sorted(expected - supplied)
            if extra:
                diagnostics.append(
                    self._diagnostic(
                        command,
                        "ICLR-SEM-010",
                        f"Unexpected API parameters: {extra}.",
                    )
                )
            if missing:
                diagnostics.append(
                    self._diagnostic(
                        command,
                        "ICLR-SEM-011",
                        f"Missing API parameters: {missing}.",
                    )
                )
            if api.return_type is not None and not command.has_response:
                diagnostics.append(
                    self._diagnostic(
                        command,
                        "ICLR-SEM-012",
                        f"API '{api.name}' returns '{api.return_type}', but no RESPONSE is set.",
                    )
                )
            elif api.return_type is None and command.has_response:
                diagnostics.append(
                    self._diagnostic(
                        command,
                        "ICLR-SEM-013",
                        f"API '{api.name}' has no return value, but RESPONSE is set.",
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


__all__ = ["APICallContractRule"]
