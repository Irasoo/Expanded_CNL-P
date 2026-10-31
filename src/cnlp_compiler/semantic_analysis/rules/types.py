from __future__ import annotations

from ..context import RuleContext
from ..diagnostic import SemanticDiagnostic
from ..facts import CommandFact, format_path


class APITypeRule:
    """ICLR tasks 006-008: resolvable, argument, and response types."""

    rule_id = "ICLR-SEM-API-TYPES"

    def check(self, context: RuleContext) -> list[SemanticDiagnostic]:
        diagnostics: list[SemanticDiagnostic] = []
        invalid_value_sources: set[tuple[str, str]] = set()
        for command in context.facts.commands:
            if command.command_type != "call_api" or command.api_name is None:
                continue
            api = context.environment.apis.get(command.api_name)
            if api is None:
                continue
            state = context.flow.command_states.get(command.path, {})

            for argument in command.arguments:
                expected_type = api.parameters.get(argument.parameter_name)
                variable_name = argument.variable_name
                if expected_type is None or variable_name is None:
                    continue
                variable = state.get(variable_name)
                if variable is None:
                    # Variable-flow diagnostics own missing declarations.
                    continue
                if (command.worker_name, variable_name) in invalid_value_sources:
                    # The incompatible API response that produced this value
                    # is the root diagnostic; do not report downstream uses as
                    # independent argument errors.
                    continue
                if not context.types.exists(expected_type):
                    diagnostics.append(
                        self._missing_type(command, expected_type)
                    )
                    continue
                if variable.is_global:
                    global_variable = context.environment.global_variables.get(variable_name)
                    if global_variable is None:
                        continue
                    problems = context.types.validate_value(
                        global_variable.value,
                        expected_type,
                    )
                    if problems:
                        diagnostics.append(
                            self._diagnostic(
                                command,
                                "ICLR-SEM-007",
                                (
                                    f"API parameter '{argument.parameter_name}' "
                                    f"receives incompatible global variable "
                                    f"'{variable_name}': {'; '.join(problems)}"
                                ),
                            )
                        )
                    continue

                actual_type = variable.type_name
                if not context.types.exists(actual_type):
                    diagnostics.append(self._missing_type(command, actual_type))
                elif not context.types.compatible(actual_type, expected_type):
                    diagnostics.append(
                        self._diagnostic(
                            command,
                            "ICLR-SEM-007",
                            (
                                f"API parameter '{argument.parameter_name}' "
                                f"expects '{expected_type}', but variable "
                                f"'{variable_name}' has type '{actual_type}'."
                            ),
                        )
                    )

            if (
                api.return_type is None
                or not command.has_response
                or command.path in context.flow.global_conflict_commands
            ):
                continue
            response_type = command.write_type_name
            if response_type is None:
                continue
            missing_types = [
                type_name
                for type_name in (api.return_type, response_type)
                if not context.types.exists(type_name)
            ]
            if missing_types:
                diagnostics.append(self._missing_type(command, missing_types[0]))
                if command.write_name is not None:
                    invalid_value_sources.add(
                        (command.worker_name, command.write_name)
                    )
            elif not context.types.compatible(api.return_type, response_type):
                diagnostics.append(
                    self._diagnostic(
                        command,
                        "ICLR-SEM-008",
                        (
                            f"API '{api.name}' returns '{api.return_type}', "
                            f"but RESPONSE '{command.write_name}' is declared "
                            f"as '{response_type}'."
                        ),
                    )
                )
                if command.write_name is not None:
                    invalid_value_sources.add(
                        (command.worker_name, command.write_name)
                    )
        return diagnostics

    def _missing_type(
        self,
        command: CommandFact,
        type_name: str,
    ) -> SemanticDiagnostic:
        return self._diagnostic(
            command,
            "ICLR-SEM-006",
            f"Type '{type_name}' cannot be found in DEFINE_TYPES or Schema.",
        )

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


__all__ = ["APITypeRule"]
