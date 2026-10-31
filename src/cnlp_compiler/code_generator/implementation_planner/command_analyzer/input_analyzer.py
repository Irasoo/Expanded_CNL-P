"""
Input Command：
    （1）要从State中获取那些变量（不关心怎么获取）
    （2）是否需要动态生成“请求语句”，如果要，是借助Traditional Program生成，还是应该借助LLM动态生成？（不关心到底如何使用Traditional Program使用和LLM到底应该怎么生成）
    （3）至于请求语句应该怎么给外界，应该由具体代码实现时指定的Implement Version来决定，此处不应该决定
    （4）如何或许外界输入，这个也和（3）一样
    （5）是否需要处理用户输入，如果要的话，应该选择那种方式（2）中处理
    （6）如何更新State（包括Variable，History）

    实际分析得到的数据结构：
    {
        "required_variables": [...],
        "request_generation": {
            "dynamic": bool,
            "llm_based": bool
        },
        "raw_input_processing": {
            "needed": bool,
            "llm_based": bool
        },
        "written_variable": "..."
    }
    required_variables与written_variable中只有变量名，应该直接通过编码获取。
    request_generation.dynamic为False时，其llm_based固定为False。
    raw_input_processing.needed为False时，其llm_based固定为False。

    History：
    记录assistant最终展示给用户的请求内容，以及user的raw_input。
"""

import json

from ....schema import (
    CommandNode,
    InputCommandAnalysisPlan,
    VariableNode,
)
from ....utils import (
    LLMclient,
    PromptSection,
    create_llm_client,
    create_prompt_section,
)
from ...plan_implementer.type_converter import TypeConverter
from ..analysis_support import (
    parse_json_array_response,
    select_variables,
    validate_boolean_decision,
)


try:
    from ....prompts.code_generator_implementation_planner_command_analyzer import REQUEST_INPUT_COMMAND_ANALYSIS_PROMPT
except ImportError:  # Supports legacy top-level package imports.
    from prompts.code_generator_implementation_planner_command_analyzer import REQUEST_INPUT_COMMAND_ANALYSIS_PROMPT

class InputCommandAnalyzer:

    def __init__(self, llm_client: LLMclient | None = None):
        self._llm_client = llm_client

    def analyze_all(
        self,
        *,
        commands: list[CommandNode],
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str] | None = None,
        python_schema_dependency_table: (
            dict[str, list[str]] | None
        ) = None,
    ) -> list[InputCommandAnalysisPlan]:
        """Analyze every supplied Request Input Command in one request."""
        if not commands:
            return []

        for command in commands:
            if command["written_variable"] is None:
                raise ValueError(
                    "Request Input Command must write exactly one variable."
                )

        response = self._get_llm_client().complete(
            self._build_prompt(
                commands=commands,
                variables=variables,
                python_schema_code_table=python_schema_code_table,
                python_schema_dependency_table=(
                    python_schema_dependency_table or {}
                ),
            )
        )
        analyses = self._parse_analyses(
            response=response,
            expected_count=len(commands),
        )

        return [
            {
                "command_name": command["command_name"],
                "command_index": command["command_index"],
                "command_type": "request_input",
                "description": command["description"],
                "required_variables": command["required_variables"],
                "request_generation": analysis["request_generation"],
                "raw_input_processing": analysis["raw_input_processing"],
                "written_variable": command["written_variable"],
                "write_operation": command["write_operation"],
            }
            for command, analysis in zip(commands, analyses, strict=True)
        ]

    def analyze(
        self,
        *,
        command: CommandNode,
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str] | None = None,
        python_schema_dependency_table: (
            dict[str, list[str]] | None
        ) = None,
    ) -> InputCommandAnalysisPlan:
        """Compatibility wrapper for isolated single-Command analysis."""
        return self.analyze_all(
            commands=[command],
            variables=variables,
            python_schema_code_table=python_schema_code_table,
            python_schema_dependency_table=python_schema_dependency_table,
        )[0]

    def _get_llm_client(self) -> LLMclient:
        if self._llm_client is None:
            self._llm_client = create_llm_client()
        return self._llm_client

    @staticmethod
    def _build_prompt(
        *,
        commands: list[CommandNode],
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str] | None,
        python_schema_dependency_table: dict[str, list[str]],
    ) -> list[PromptSection]:
        related_variable_names = [
            variable_name
            for command in commands
            for variable_name in (
                list(command["required_variables"])
                + (
                    [command["written_variable"]]
                    if command["written_variable"] is not None
                    else []
                )
            )
        ]
        related_variables = select_variables(
            related_variable_names,
            variables,
        )
        related_python_schema_code = (
            TypeConverter.render_related_variable_type_code(
                variables=related_variables,
                schema_code_table=python_schema_code_table,
                schema_dependency_table=(python_schema_dependency_table or {}),
            )
            if python_schema_code_table is not None
            else ""
        )

        content = (
            REQUEST_INPUT_COMMAND_ANALYSIS_PROMPT
            .replace(
                "{{COMMANDS_JSON}}",
                json.dumps(
                    [
                        InputCommandAnalyzer._command_prompt_data(command)
                        for command in commands
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            .replace(
                "{{VARIABLES_JSON}}",
                json.dumps(
                    InputCommandAnalyzer._variable_prompt_data(related_variables),
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            .replace(
                "{{RELATED_PYTHON_SCHEMA_CODE}}",
                related_python_schema_code.strip() or "None",
            )
        )
        return [create_prompt_section("user", content)]

    @staticmethod
    def _command_prompt_data(command: CommandNode) -> dict[str, object]:
        return {
            "description": command["description"],
            "required_variables": command["required_variables"],
            "written_variable": command["written_variable"],
            "write_operation": command["write_operation"],
        }

    @staticmethod
    def _variable_prompt_data(
        variables: list[VariableNode],
    ) -> list[dict[str, object]]:
        return [
            {
                "variable_name": variable["variable_name"],
                "description": variable["description"],
            }
            for variable in variables
        ]

    @staticmethod
    def _parse_analyses(
        *,
        response: str,
        expected_count: int,
    ) -> list[dict[str, dict[str, bool]]]:
        results = parse_json_array_response(response)
        if len(results) != expected_count:
            raise ValueError(
                "The Input Command analysis count does not match the "
                "input Command count."
            )

        expected_keys = {
            "request_generation",
            "raw_input_processing",
        }
        analyses: list[dict[str, dict[str, bool]]] = []
        for result in results:
            if not isinstance(result, dict) or set(result) != expected_keys:
                received_fields = (
                    list(result) if isinstance(result, dict) else result
                )
                raise ValueError(
                    "Each Input Command analysis must contain exactly these "
                    f"fields: {sorted(expected_keys)!r}; received: "
                    f"{received_fields!r}."
                )

            analyses.append(
                {
                    "request_generation": validate_boolean_decision(
                        result["request_generation"],
                        expected_keys=("dynamic", "llm_based"),
                        controlling_key="dynamic",
                    ),
                    "raw_input_processing": validate_boolean_decision(
                        result["raw_input_processing"],
                        expected_keys=("needed", "llm_based"),
                        controlling_key="needed",
                    ),
                }
            )
        return analyses
