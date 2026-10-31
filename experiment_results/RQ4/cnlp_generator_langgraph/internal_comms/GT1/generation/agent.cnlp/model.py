from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from typing import Any, get_args, get_origin

from .schema import (
    AgentConfig,
    CNLPVariableInfo,
    HistoryRole,
    HistorySection,
    WriteOperation,
)
from .utils import validate_python_value


class VariableManagement:
    """Own all CNL-P variables for one Agent execution."""

    def __init__(
        self,
        variable_config: Iterable[CNLPVariableInfo],
    ) -> None:
        self._definitions: dict[str, CNLPVariableInfo] = {}
        self._values: dict[str, Any] = {}

        for definition in variable_config:
            variable_name = definition["variable_name"]
            if variable_name in self._definitions:
                raise ValueError(
                    f"Variable {variable_name!r} is declared more than once."
                )

            copied_definition = deepcopy(definition)
            default_value = copied_definition["default_value"]
            if default_value is not None:
                default_value = validate_python_value(
                    default_value,
                    copied_definition["value_type"],
                )

            self._definitions[variable_name] = copied_definition
            self._values[variable_name] = deepcopy(default_value)

    def get_variable_value(self, variable_name: str) -> Any:
        self._require_variable(variable_name)
        return self._values[variable_name]

    def get_variable_values(
        self,
        variable_names: Iterable[str],
    ) -> dict[str, Any]:
        return {
            variable_name: self.get_variable_value(variable_name)
            for variable_name in variable_names
        }

    def get_variable_type(self, variable_name: str) -> Any:
        self._require_variable(variable_name)
        return self._definitions[variable_name]["value_type"]

    def revise_variable_value(
        self,
        variable_name: str,
        new_value: Any,
        operation: WriteOperation,
    ) -> None:
        self._require_variable(variable_name)

        if operation == "SET":
            value_type = self._definitions[variable_name]["value_type"]
            self._values[variable_name] = validate_python_value(
                new_value,
                value_type,
            )
            return

        if operation == "APPEND":
            self._append_variable_value(variable_name, new_value)
            return

        raise ValueError(
            f"Unsupported variable write operation: {operation!r}."
        )

    def as_dict(self) -> dict[str, Any]:
        return deepcopy(self._values)

    def _append_variable_value(
        self,
        variable_name: str,
        new_value: Any,
    ) -> None:
        value_type = self._definitions[variable_name]["value_type"]
        if get_origin(value_type) is not list:
            raise TypeError(
                f"APPEND requires list variable {variable_name!r}."
            )

        item_type_arguments = get_args(value_type)
        item_type = (
            item_type_arguments[0]
            if item_type_arguments
            else Any
        )
        validated_item = validate_python_value(new_value, item_type)

        current_value = self._values[variable_name]
        if current_value is None:
            current_value = []
            self._values[variable_name] = current_value
        if not isinstance(current_value, list):
            raise TypeError(
                f"Variable {variable_name!r} does not contain a list."
            )
        current_value.append(validated_item)

    def _require_variable(self, variable_name: str) -> None:
        if variable_name not in self._definitions:
            raise KeyError(
                f"CNL-P variable {variable_name!r} is not declared."
            )


class HistoryManagement:
    """Record only Command-level semantic interaction."""

    def __init__(self, agent_attributes: str) -> None:
        self._history_sections: list[HistorySection] = []
        self._append_history_section(
            role="system",
            content=agent_attributes,
        )

    @property
    def history_sections(self) -> list[HistorySection]:
        return deepcopy(self._history_sections)

    def record_input_command_history(
        self,
        *,
        displayed_request: str,
        raw_user_input: str,
    ) -> None:
        self._append_history_section(
            role="assistant",
            content=displayed_request,
        )
        self._append_history_section(
            role="user",
            content=raw_user_input,
        )

    def record_general_command_history(
        self,
        *,
        summary: str,
    ) -> None:
        """Record one concise Assistant summary for a General Command."""
        self._append_history_section(
            role="assistant",
            content=summary,
        )

    def record_call_api_command_history(
        self,
        *,
        api_name: str,
        written_variable: str | None,
    ) -> None:
        """Record which CNL-P API ran and where its result was stored."""
        normalized_api_name = api_name.strip()
        if not normalized_api_name:
            raise ValueError("api_name cannot be empty.")

        if written_variable is None:
            summary = (
                f"Called API {normalized_api_name}; "
                "no CNL-P response variable was written."
            )
        else:
            normalized_variable_name = written_variable.strip()
            if not normalized_variable_name:
                raise ValueError("written_variable cannot be empty.")
            summary = (
                f"Called API {normalized_api_name}; the result was written "
                f"to variable {normalized_variable_name}."
            )

        self._append_history_section(
            role="assistant",
            content=summary,
        )

    def record_display_command_history(
        self,
        *,
        displayed_content: str,
    ) -> None:
        self._append_history_section(
            role="assistant",
            content=displayed_content,
        )

    def _append_history_section(
        self,
        *,
        role: HistoryRole,
        content: str,
    ) -> None:
        normalized_content = content.strip()
        if not normalized_content:
            return
        self._history_sections.append(
            {
                "role": role,
                "content": normalized_content,
            }
        )

class AgentState:
    """State and History shared by Commands and Predicates in one run."""

    def __init__(self, config: AgentConfig) -> None:
        self.variable_management = VariableManagement(
            config["variable_config"]
        )
        self.history_management = HistoryManagement(
            config["agent_attributes"]
        )

    def get_variable_value(self, variable_name: str) -> Any:
        return self.variable_management.get_variable_value(variable_name)

    def get_variable_values(
        self,
        variable_names: Iterable[str],
    ) -> dict[str, Any]:
        return self.variable_management.get_variable_values(variable_names)

    def get_variable_type(self, variable_name: str) -> Any:
        return self.variable_management.get_variable_type(variable_name)

    def revise_variable_value(
        self,
        variable_name: str,
        new_value: Any,
        operation: WriteOperation,
    ) -> None:
        self.variable_management.revise_variable_value(
            variable_name,
            new_value,
            operation,
        )

    @property
    def history(self) -> list[HistorySection]:
        return self.history_management.history_sections

    def record_input_command_history(
        self,
        *,
        displayed_request: str,
        raw_user_input: str,
    ) -> None:
        self.history_management.record_input_command_history(
            displayed_request=displayed_request,
            raw_user_input=raw_user_input,
        )

    def record_general_command_history(
        self,
        *,
        summary: str,
    ) -> None:
        self.history_management.record_general_command_history(
            summary=summary,
        )

    def record_call_api_command_history(
        self,
        *,
        api_name: str,
        written_variable: str | None,
    ) -> None:
        self.history_management.record_call_api_command_history(
            api_name=api_name,
            written_variable=written_variable,
        )

    def record_display_command_history(
        self,
        *,
        displayed_content: str,
    ) -> None:
        self.history_management.record_display_command_history(
            displayed_content=displayed_content,
        )
