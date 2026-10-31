from __future__ import annotations

from typing import Any

from .....schema import (
    ModelConfig,
    StaticAttributes,
    VariableNode,
)
from ...schema import GeneratedFile
from .schema import TypeImplementationResult


_ATTRIBUTE_SECTION_TITLES = (
    ("persona", "Persona"),
    ("audience", "Audience"),
    ("concepts", "Concepts"),
    ("constraints", "Constraints"),
)


class DeterministicConfigImplementer:
    """Generate config.py only from normalized compiler data."""

    def implement(
        self,
        *,
        static_attributes: StaticAttributes,
        variables: list[VariableNode],
        model_config: ModelConfig,
        type_result: TypeImplementationResult,
    ) -> GeneratedFile:
        self._validate_variable_type_table(
            variables=variables,
            type_result=type_result,
        )
        content = self._render_module(
            static_attributes=static_attributes,
            variables=variables,
            model_config=model_config,
            type_result=type_result,
        )
        compile(content, "config.py", "exec")
        return {
            "relative_path": "config.py",
            "content": content,
            "write_type": "rewrite",
        }

    def _render_module(
        self,
        *,
        static_attributes: StaticAttributes,
        variables: list[VariableNode],
        model_config: ModelConfig,
        type_result: TypeImplementationResult,
    ) -> str:
        sections: list[str] = []
        typing_import_names = type_result["config_typing_import_names"]
        if typing_import_names:
            sections.append(
                "from typing import " + ", ".join(typing_import_names)
            )

        schema_import_names = [
            "AgentConfig",
            "CNLPVariableInfo",
            "ModelConfig",
            *type_result["config_schema_import_names"],
        ]
        sections.append(self._render_schema_import(schema_import_names))

        agent_attributes = self._render_agent_attributes(static_attributes)
        sections.append(
            "AGENT_ATTRIBUTES: str = " + repr(agent_attributes)
        )
        sections.append(
            "MODEL_CONFIG: ModelConfig = {\n"
            f"    \"api_key\": {model_config['api_key']!r},\n"
            f"    \"model_name\": {model_config['model_name']!r},\n"
            f"    \"base_url\": {model_config['base_url']!r},\n"
            "}"
        )
        sections.append(
            self._render_variable_config(
                variables=variables,
                type_expressions=type_result[
                    "variable_type_expression_table"
                ],
            )
        )
        sections.append(
            "AGENT_CONFIG: AgentConfig = {\n"
            "    \"agent_attributes\": AGENT_ATTRIBUTES,\n"
            "    \"model_config\": MODEL_CONFIG,\n"
            "    \"variable_config\": VARIABLE_CONFIG,\n"
            "}"
        )
        return "\n\n\n".join(sections) + "\n"

    @staticmethod
    def _render_schema_import(names: list[str]) -> str:
        unique_names: list[str] = []
        for name in names:
            if name not in unique_names:
                unique_names.append(name)
        lines = ["from .schema import ("]
        lines.extend(f"    {name}," for name in unique_names)
        lines.append(")")
        return "\n".join(lines)

    @staticmethod
    def _render_agent_attributes(
        static_attributes: StaticAttributes,
    ) -> str:
        sections: list[str] = []
        for section_key, section_title in _ATTRIBUTE_SECTION_TITLES:
            attributes = static_attributes[section_key]
            if not attributes:
                continue
            lines = [f"{section_title}:"]
            lines.extend(
                f"- {name}: {description}"
                for name, description in attributes.items()
            )
            sections.append("\n".join(lines))
        return "\n\n".join(sections)

    def _render_variable_config(
        self,
        *,
        variables: list[VariableNode],
        type_expressions: dict[str, str],
    ) -> str:
        lines = ["VARIABLE_CONFIG: list[CNLPVariableInfo] = ["]
        for variable in variables:
            variable_name = variable["variable_name"]
            default_value = self._materialize_default_value(
                variable["default_value"]
            )
            lines.extend(
                [
                    "    {",
                    f"        \"variable_name\": {variable_name!r},",
                    (
                        "        \"value_type\": "
                        f"{type_expressions[variable_name]},"
                    ),
                    f"        \"default_value\": {default_value!r},",
                    "    },",
                ]
            )
        lines.append("]")
        return "\n".join(lines)

    @classmethod
    def _materialize_default_value(cls, value_ir: Any) -> Any:
        if value_ir is None:
            return None
        if not isinstance(value_ir, dict):
            raise TypeError("A CNL-P default value must use CNLPValueIR.")

        value_kind = value_ir.get("value_kind")
        raw_value = value_ir.get("value")
        if value_kind == "scalar":
            return raw_value
        if value_kind == "array":
            if not isinstance(raw_value, list):
                raise TypeError("A CNL-P array default must contain a list.")
            return [
                cls._materialize_default_value(element)
                for element in raw_value
            ]
        if value_kind != "structured":
            raise ValueError(
                f"Unsupported CNL-P default value kind: {value_kind!r}."
            )
        if not isinstance(raw_value, list):
            raise TypeError(
                "A CNL-P structured default must contain a list of fields."
            )

        result: dict[str, Any] = {}
        for element in raw_value:
            if not isinstance(element, dict):
                raise TypeError(
                    "A CNL-P structured default field must be an object."
                )
            key = element.get("key")
            if not isinstance(key, str) or not key:
                raise ValueError(
                    "A CNL-P structured default must name every field."
                )
            if key in result:
                raise ValueError(
                    f"CNL-P structured default repeats field {key!r}."
                )
            result[key] = cls._materialize_default_value(
                element.get("value")
            )
        return result

    @staticmethod
    def _validate_variable_type_table(
        *,
        variables: list[VariableNode],
        type_result: TypeImplementationResult,
    ) -> None:
        variable_names = [
            variable["variable_name"] for variable in variables
        ]
        if len(variable_names) != len(set(variable_names)):
            raise ValueError("CNL-P variable names must be unique.")
        type_names = set(
            type_result["variable_type_expression_table"]
        )
        if type_names != set(variable_names):
            raise ValueError(
                "Variable type table does not match the extracted Variables."
            )
