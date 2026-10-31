from __future__ import annotations

import re

from ......schema import CallWorkerCommandAnalysisPlan
from ..schema import FunctionImplementation


class CallWorkerCommandPlanImplementer:
    """Generate a direct call to another generated Worker module."""

    def implement(
        self,
        *,
        command_plan: CallWorkerCommandAnalysisPlan,
    ) -> FunctionImplementation:
        function_name = command_plan["command_name"]
        target_name = command_plan["target_worker_name"]
        target_runner = f"run_{_python_slug(target_name)}"
        lines = [
            f"def {function_name}(state: AgentState, llm_client: OpenAIClient) -> None:",
            "    def read_path(variable_path: str):",
            "        parts = variable_path.split('.')",
            "        value = state.get_variable_value(parts[0])",
            "        for part in parts[1:]:",
            "            value = value[part]",
            "        return value",
        ]

        for argument in command_plan["arguments"]:
            lines.extend(
                [
                    "    state.revise_variable_value(",
                    f"        {argument['parameter_name']!r},",
                    f"        read_path({argument['argument_name']!r}),",
                    "        'SET',",
                    "    )",
                ]
            )

        lines.extend(
            [
                f"    from .main import {target_runner}",
                f"    {target_runner}(state=state, llm_client=llm_client)",
            ]
        )

        response = command_plan["response"]
        if response is not None:
            output_names = [
                output["variable_name"]
                for output in command_plan["target_outputs"]
            ]
            if len(output_names) == 1:
                lines.append(
                    f"    result = state.get_variable_value({output_names[0]!r})"
                )
            else:
                lines.append("    result = {")
                for output_name in output_names:
                    lines.append(
                        f"        {output_name!r}: state.get_variable_value({output_name!r}),"
                    )
                lines.append("    }")
            _append_response_write(
                lines,
                variable_path=response["variable_name"],
                write_operation=command_plan["write_operation"] or "SET",
            )

        return {
            "function_name": function_name,
            "function_code": "\n".join(lines),
        }


def _append_response_write(
    lines: list[str],
    *,
    variable_path: str,
    write_operation: str,
) -> None:
    root_name, separator, nested_path = variable_path.partition(".")
    if not separator:
        lines.extend(
            [
                "    state.revise_variable_value(",
                f"        {root_name!r}, result, {write_operation!r},",
                "    )",
            ]
        )
        return

    path_parts = nested_path.split(".")
    lines.extend(
        [
            f"    updated_root = dict(state.get_variable_value({root_name!r}))",
            "    current = updated_root",
        ]
    )
    for part in path_parts[:-1]:
        lines.extend(
            [
                f"    nested = dict(current[{part!r}])",
                f"    current[{part!r}] = nested",
                "    current = nested",
            ]
        )
    leaf = path_parts[-1]
    if write_operation == "APPEND":
        lines.extend(
            [
                f"    updated_items = list(current[{leaf!r}])",
                "    updated_items.append(result)",
                f"    current[{leaf!r}] = updated_items",
            ]
        )
    else:
        lines.append(f"    current[{leaf!r}] = result")
    lines.extend(
        [
            "    state.revise_variable_value(",
            f"        {root_name!r}, updated_root, 'SET',",
            "    )",
        ]
    )


def _python_slug(name: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_").lower()
    if not slug:
        raise ValueError(f"Worker name cannot form a module name: {name!r}.")
    if slug[0].isdigit():
        slug = f"w_{slug}"
    return slug
