from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

try:
    from ..utils import (
        find_keys_by_pattern,
        get_value_by_path_without_copy,
    )
except ImportError:  # Supports legacy top-level ``flow_binder`` imports.
    from utils import (
        find_keys_by_pattern,
        get_value_by_path_without_copy,
    )
try:
    from ..node_visitor import NodeVisitor
except ImportError:  # Supports legacy top-level ``flow_binder`` imports.
    from node_visitor import NodeVisitor
from .binding_alternative_flow import bind_alternative_flow
from .binding_exception_flow import bind_exception_flow
from .decision_indexer import build_decision_indexed_worker_ast

__all__ = ["FlowBinder"]


class FlowBinder:
    """
    Build a standalone flow-binding table from a Worker AST.

    Existing Decision indices are preserved and missing ones are assigned by
    NodeVisitor. The normalized AST is authoritative for workflow structure
    and indices.
    """

    __slots__ = ("max_retries", "_model_response")

    def __init__(
        self,
        *,
        max_retries: int = 2,
        model_response: Callable[[list[dict[str, str]]], str] | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative.")

        self.max_retries = max_retries
        self._model_response = model_response

    def bind(
        self,
        decision_indexed_worker_ast: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Bind all alternative flows and exception flows to the main flow.

        Args:
            decision_indexed_worker_ast:
                A Worker AST. Existing decision_index values are preserved;
                missing values are assigned mechanically without mutation.
        Returns:
            A standalone flow-binding table. The input AST is not modified.
        """
        if not isinstance(decision_indexed_worker_ast, dict):
            raise TypeError(
                "decision_indexed_worker_ast must be a JSON object."
            )

        indexed_worker_ast = build_decision_indexed_worker_ast(
            decision_indexed_worker_ast
        )
        main_flow_path, main_flow = self._get_unique_main_flow(
            indexed_worker_ast
        )
        (
            command_indices,
            decision_indices,
            decision_path_table,
        ) = self._collect_main_flow_indices(
            main_flow,
            main_flow_path=main_flow_path,
        )

        if not command_indices:
            raise ValueError("No command index was found in main_flow.")

        binding_table: dict[str, Any] = {
            "main_flow_path": main_flow_path,

            # Map each Decision index used by go_back_to to the complete
            # Worker structural path of the corresponding block.
            "decision_path_table": decision_path_table,

            "alternative_flows": [],
            "exception_flows": [],
        }

        alternative_flow_paths = self._sort_flow_paths(
            find_keys_by_pattern(
                python_dict=indexed_worker_ast,
                name_pattern="alternative_flow",
            )
        )
        for flow_path in alternative_flow_paths:
            alternative_flow = get_value_by_path_without_copy(
                python_dict=indexed_worker_ast,
                key_path=flow_path,
            )
            if not isinstance(alternative_flow, dict):
                raise TypeError(
                    f"{flow_path} must be represented as a JSON object."
                )

            binding = bind_alternative_flow(
                main_flow=main_flow,
                alternative_flow=alternative_flow,
                command_indices=command_indices,
                decision_indices=decision_indices,
                max_retries=self.max_retries,
                model_response=self._model_response,
            )
            binding_table["alternative_flows"].append(
                {
                    "flow_name": self._flow_name_from_path(flow_path),
                    "flow_path": flow_path,
                    "trigger_is": binding["trigger_is"],
                    "go_back_to": binding["go_back_to"],
                }
            )

        exception_flow_paths = self._sort_flow_paths(
            find_keys_by_pattern(
                python_dict=indexed_worker_ast,
                name_pattern="exception_flow",
            )
        )
        for flow_path in exception_flow_paths:
            exception_flow = get_value_by_path_without_copy(
                python_dict=indexed_worker_ast,
                key_path=flow_path,
            )
            if not isinstance(exception_flow, dict):
                raise TypeError(
                    f"{flow_path} must be represented as a JSON object."
                )

            trigger_is = bind_exception_flow(
                main_flow=main_flow,
                exception_flow=exception_flow,
                command_indices=command_indices,
                max_retries=self.max_retries,
                model_response=self._model_response,
            )
            binding_table["exception_flows"].append(
                {
                    "flow_name": self._flow_name_from_path(flow_path),
                    "flow_path": flow_path,
                    "trigger_is": trigger_is,
                }
            )

        return binding_table

    def _get_unique_main_flow(
        self,
        worker_ast: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        main_flow_paths = find_keys_by_pattern(
            python_dict=worker_ast,
            name_pattern="main_flow",
        )

        if not main_flow_paths:
            raise ValueError("No main_flow was found in the Worker AST.")

        if len(main_flow_paths) > 1:
            raise ValueError(
                f"Expected one main_flow in a Worker AST, "
                f"but found {len(main_flow_paths)}."
            )

        main_flow_path = main_flow_paths[0]
        main_flow = get_value_by_path_without_copy(
            python_dict=worker_ast,
            key_path=main_flow_path,
        )

        if not isinstance(main_flow, dict):
            raise TypeError("main_flow must be represented as a JSON object.")

        return main_flow_path, main_flow

    def _collect_main_flow_indices(
        self,
        main_flow: dict[str, Any],
        *,
        main_flow_path: str,
    ) -> tuple[set[int], set[int], dict[int, str]]:
        command_indices: set[int] = set()
        decision_indices: set[int] = set()
        decision_path_table: dict[int, str] = {}

        def visit(value: Any, path: str) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    child_path = f"{path}.{key}" if path else key
                    command_match = re.fullmatch(r"command(\d+)", key)
                    if command_match:
                        command_index = int(command_match.group(1))
                        if command_index in command_indices:
                            raise ValueError(
                                f"Duplicate command index: {command_index}."
                            )
                        command_indices.add(command_index)

                    if key.startswith(
                        ("if_block", "while_block", "for_block")
                    ):
                        if not isinstance(child, dict):
                            raise TypeError(f"{key} must be a JSON object.")

                        if "decision_index" not in child:
                            raise ValueError(
                                f"{key} is missing decision_index in the "
                                "Decision-Indexed AST."
                            )

                        decision_index = self._coerce_index(
                            child["decision_index"]
                        )
                        if decision_index in decision_indices:
                            raise ValueError(
                                f"Duplicate decision index: {decision_index}."
                            )
                        decision_indices.add(decision_index)
                        decision_path_table[decision_index] = (
                            self._as_worker_path(child_path)
                        )

                    visit(child, child_path)

            elif isinstance(value, list):
                for index, item in enumerate(value):
                    visit(item, f"{path}.[{index}]")

        visit(main_flow, main_flow_path)
        return (
            command_indices,
            decision_indices,
            decision_path_table,
        )

    @staticmethod
    def _coerce_index(value: Any) -> int:
        if isinstance(value, bool):
            raise ValueError("Boolean values cannot be used as indices.")

        if isinstance(value, int):
            return value

        if isinstance(value, str):
            match = re.search(r"(\d+)$", value.strip())
            if match:
                return int(match.group(1))

        raise ValueError(f"Invalid index value: {value!r}.")

    @staticmethod
    def _flow_name_from_path(flow_path: str) -> str:
        return flow_path.rsplit(".", 1)[-1]

    @staticmethod
    def _as_worker_path(path: str) -> str:
        return path if path.startswith("worker.") else f"worker.{path}"

    @staticmethod
    def _sort_flow_paths(flow_paths: list[str]) -> list[str]:
        def sort_key(path: str) -> tuple[str, int]:
            name = path.rsplit(".", 1)[-1]
            match = re.search(r"(\d+)$", name)
            return name.rstrip("0123456789"), (
                int(match.group(1)) if match else -1
            )

        return sorted(flow_paths, key=sort_key)
