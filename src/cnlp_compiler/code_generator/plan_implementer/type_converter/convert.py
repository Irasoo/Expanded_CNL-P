from __future__ import annotations

import keyword
from collections.abc import Sequence
from typing import Any, TypedDict

from ....schema import (
    CNLPDataType,
    CNLPTypeIR,
    FieldOfCNLPStructType,
    VariableNode,
)


_PYTHON_TYPE_IMPORTS = (
    "from typing import Literal, TypeAlias\n"
    "from typing_extensions import NotRequired, TypedDict"
)


class PythonTypeConversionResult(TypedDict):
    """Complete Python type code plus its per-schema lookup tables."""

    # Complete source appended to the generated schema.py.
    python_type_code: str

    # CNL-P declared type name -> Python source for that declaration. Inline
    # TypedDict declarations owned by the type are included in the same value.
    schema_code_table: dict[str, str]

    # CNL-P declared type name -> other declared types referenced by it.
    schema_dependency_table: dict[str, list[str]]


class ConfigVariableTypeConversionResult(TypedDict):
    """Python types needed by deterministic config.py generation."""

    # Inline TypedDict declarations that must be appended to schema.py before
    # config.py imports the resulting type objects.
    inline_python_type_code: str

    # Variable name -> executable Python type expression used as value_type.
    variable_type_expression_table: dict[str, str]

    # Generated or declared names that config.py imports from schema.py.
    schema_import_names: list[str]

    # Names such as Literal that config.py imports from typing.
    typing_import_names: list[str]


class TypeConversionError(ValueError):
    """Raised when a CNL-P type IR cannot become valid Python type code."""


class TypeConverter:
    """Convert normalized CNL-P type declarations into Python type code."""

    _SIMPLE_TYPE_MAP = {
        "text": "str",
        "number": "int | float",
        "boolean": "bool",
    }

    def __init__(self) -> None:
        self._used_type_names: set[str] = set()

    def convert(self, cnlp_types: Sequence[CNLPTypeIR]) -> str:
        return self.convert_with_schema_index(cnlp_types)["python_type_code"]

    def convert_with_schema_index(
        self,
        cnlp_types: Sequence[CNLPTypeIR],
    ) -> PythonTypeConversionResult:
        """Convert types once and retain each declaration and dependency."""

        if isinstance(cnlp_types, (str, bytes)) or not isinstance(
            cnlp_types,
            Sequence,
        ):
            raise TypeError("cnlp_types must be a sequence of CNLPTypeIR objects.")
        if not cnlp_types:
            return {
                "python_type_code": "",
                "schema_code_table": {},
                "schema_dependency_table": {},
            }

        normalized_types = [
            self._validate_type_ir(type_ir, index)
            for index, type_ir in enumerate(cnlp_types)
        ]
        type_names = [type_ir["type_name"] for type_ir in normalized_types]
        duplicate_names = {
            type_name for type_name in type_names if type_names.count(type_name) > 1
        }
        if duplicate_names:
            duplicates = ", ".join(sorted(duplicate_names))
            raise TypeConversionError(
                f"Duplicate CNL-P type declarations: {duplicates}."
            )

        self._used_type_names = set(type_names)
        declaration_blocks: list[list[str]] = []
        schema_code_table: dict[str, str] = {}
        schema_dependency_table: dict[str, list[str]] = {}
        for type_ir in normalized_types:
            rendered_blocks = self._render_type(type_ir)
            declaration_blocks.extend(rendered_blocks)
            schema_code_table[type_ir["type_name"]] = self._join_declaration_blocks(
                rendered_blocks
            )
            schema_dependency_table[type_ir["type_name"]] = (
                self._collect_declared_type_names(type_ir["type_content"])
            )

        declaration_code = self._join_declaration_blocks(declaration_blocks)
        return {
            "python_type_code": (f"{_PYTHON_TYPE_IMPORTS}\n\n{declaration_code}\n"),
            "schema_code_table": schema_code_table,
            "schema_dependency_table": schema_dependency_table,
        }

    @classmethod
    def select_related_schema_code(
        cls,
        *,
        variables: Sequence[VariableNode],
        schema_code_table: dict[str, str],
        schema_dependency_table: dict[str, list[str]],
    ) -> str:
        """Return only schemas reached from the supplied variables."""

        root_schema_names: list[str] = []
        for variable in variables:
            for schema_name in cls._collect_declared_type_names(variable["data_type"]):
                if schema_name not in root_schema_names:
                    root_schema_names.append(schema_name)

        ordered_schema_names: list[str] = []
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(schema_name: str) -> None:
            if schema_name in visited or schema_name in visiting:
                return
            if schema_name not in schema_code_table:
                raise TypeConversionError(
                    "Related variable references undeclared CNL-P type "
                    f"{schema_name!r}."
                )

            visiting.add(schema_name)
            for dependency_name in schema_dependency_table.get(
                schema_name,
                [],
            ):
                visit(dependency_name)
            visiting.remove(schema_name)
            visited.add(schema_name)
            ordered_schema_names.append(schema_name)

        for root_schema_name in root_schema_names:
            visit(root_schema_name)

        if not ordered_schema_names:
            return ""

        declaration_code = "\n\n".join(
            schema_code_table[schema_name] for schema_name in ordered_schema_names
        )
        return f"{_PYTHON_TYPE_IMPORTS}\n\n{declaration_code}\n"

    @classmethod
    def render_related_variable_type_code(
        cls,
        *,
        variables: Sequence[VariableNode],
        schema_code_table: dict[str, str],
        schema_dependency_table: dict[str, list[str]],
    ) -> str:
        """Render complete Python types for the supplied runtime variables."""
        if not variables:
            return ""

        declared_schema_code = cls.select_related_schema_code(
            variables=variables,
            schema_code_table=schema_code_table,
            schema_dependency_table=schema_dependency_table,
        ).strip()

        converter = cls()
        converter._used_type_names = set(schema_code_table)
        inline_blocks: list[list[str]] = []
        variable_annotations = ["# Related CNL-P runtime variable types"]
        for variable in variables:
            variable_name = variable["variable_name"]
            converter._require_identifier(
                variable_name,
                "CNL-P variable",
            )
            annotation, nested_blocks = converter._render_annotation(
                variable["data_type"],
                suggested_inline_name=(
                    f"{converter._to_type_name(variable_name)}Value"
                ),
            )
            inline_blocks.extend(nested_blocks)
            variable_annotations.append(f"{variable_name}: {annotation}")

        sections = [
            declared_schema_code or _PYTHON_TYPE_IMPORTS,
        ]
        if inline_blocks:
            sections.append(converter._join_declaration_blocks(inline_blocks))
        sections.append("\n".join(variable_annotations))
        return "\n\n".join(sections).strip() + "\n"

    @classmethod
    def convert_config_variable_types(
        cls,
        *,
        variables: Sequence[VariableNode],
        declared_type_names: Sequence[str],
        occupied_type_names: Sequence[str] = (),
    ) -> ConfigVariableTypeConversionResult:
        """Prepare stable type expressions consumed by generated config.py.

        Declared CNL-P types are referenced by their real schema.py names.
        A Variable may also contain an inline structured type; in that case
        this method creates a stable TypedDict declaration which is appended
        to schema.py before config.py is generated.
        """
        if isinstance(variables, (str, bytes)) or not isinstance(
            variables,
            Sequence,
        ):
            raise TypeError("variables must be a sequence of VariableNode objects.")
        if isinstance(declared_type_names, (str, bytes)) or not isinstance(
            declared_type_names,
            Sequence,
        ):
            raise TypeError("declared_type_names must be a sequence of strings.")
        if isinstance(occupied_type_names, (str, bytes)) or not isinstance(
            occupied_type_names,
            Sequence,
        ):
            raise TypeError("occupied_type_names must be a sequence of strings.")

        normalized_declared_names: list[str] = []
        for declared_type_name in declared_type_names:
            cls._require_identifier(
                declared_type_name,
                "Declared CNL-P type",
            )
            if declared_type_name in normalized_declared_names:
                raise TypeConversionError(
                    "Duplicate declared CNL-P type name: "
                    f"{declared_type_name!r}."
                )
            normalized_declared_names.append(declared_type_name)

        normalized_occupied_names: set[str] = set(normalized_declared_names)
        for occupied_type_name in occupied_type_names:
            cls._require_identifier(
                occupied_type_name,
                "Generated Python type",
            )
            normalized_occupied_names.add(occupied_type_name)

        converter = cls()
        converter._used_type_names = normalized_occupied_names
        declared_name_set = set(normalized_declared_names)
        inline_blocks: list[list[str]] = []
        expression_table: dict[str, str] = {}
        schema_import_names: list[str] = []
        typing_import_names: list[str] = []

        for variable in variables:
            variable_name = variable["variable_name"]
            converter._require_identifier(variable_name, "CNL-P variable")
            if variable_name in expression_table:
                raise TypeConversionError(
                    f"Duplicate CNL-P variable name: {variable_name!r}."
                )

            referenced_declared_names = cls._collect_declared_type_names(
                variable["data_type"]
            )
            missing_names = [
                name
                for name in referenced_declared_names
                if name not in declared_name_set
            ]
            if missing_names:
                raise TypeConversionError(
                    f"Variable {variable_name!r} references undeclared "
                    f"CNL-P type(s): {missing_names}."
                )

            annotation, variable_inline_blocks = (
                converter._render_config_annotation(
                    variable["data_type"],
                    suggested_inline_name=(
                        f"{converter._to_type_name(variable_name)}Value"
                    ),
                )
            )
            expression_table[variable_name] = annotation
            inline_blocks.extend(variable_inline_blocks)

            for referenced_name in referenced_declared_names:
                if referenced_name not in schema_import_names:
                    schema_import_names.append(referenced_name)
            for inline_name in cls._declaration_names(variable_inline_blocks):
                if inline_name not in schema_import_names:
                    schema_import_names.append(inline_name)
            if "Literal[" in annotation and "Literal" not in typing_import_names:
                typing_import_names.append("Literal")

        inline_python_type_code = cls._join_declaration_blocks(
            inline_blocks
        )
        if inline_python_type_code:
            inline_python_type_code += "\n"

        return {
            "inline_python_type_code": inline_python_type_code,
            "variable_type_expression_table": expression_table,
            "schema_import_names": schema_import_names,
            "typing_import_names": typing_import_names,
        }

    @staticmethod
    def _join_declaration_blocks(
        declaration_blocks: Sequence[Sequence[str]],
    ) -> str:
        return "\n\n".join("\n".join(block) for block in declaration_blocks)

    @classmethod
    def _collect_declared_type_names(
        cls,
        data_type: CNLPDataType,
    ) -> list[str]:
        collected: list[str] = []

        def collect(current_type: CNLPDataType) -> None:
            if isinstance(current_type, list):
                for field in current_type:
                    collect(field["field_content"])
                return

            if not isinstance(current_type, dict):
                raise TypeConversionError(
                    f"Unsupported CNL-P data type: {current_type!r}."
                )

            variant = cls._variant_key(current_type)
            if variant == "declared_type_name":
                declared_name = current_type["declared_type_name"]
                if declared_name not in collected:
                    collected.append(declared_name)
                return
            if variant == "type_of_list_element":
                collect(current_type["type_of_list_element"])

        collect(data_type)
        return collected

    def convert_data_type(self, data_type: CNLPDataType) -> str:
        """Convert one CNL-P type into a compact Python matching type.

        This method is for reference-code search rather than schema source
        generation. Lists and structs deliberately become ``list`` and
        ``dict`` so matching does not depend on element or TypedDict details.
        """
        if isinstance(data_type, list):
            return "dict"
        if not isinstance(data_type, dict):
            raise TypeConversionError(f"Unsupported CNL-P data type: {data_type!r}.")

        variant = self._variant_key(data_type)
        if variant == "simple_type":
            simple_type = data_type["simple_type"]
            if not isinstance(simple_type, str):
                raise TypeError("CNL-P simple_type must be a string.")
            try:
                return self._SIMPLE_TYPE_MAP[simple_type.lower()]
            except KeyError as exc:
                raise TypeConversionError(
                    f"Unsupported CNL-P simple type '{simple_type}'."
                ) from exc

        if variant == "declared_type_name":
            declared_type_name = data_type["declared_type_name"]
            self._require_identifier(
                declared_type_name,
                "Declared type reference",
            )
            return declared_type_name

        if variant == "enum_elements":
            return "str"

        return "list"

    def _validate_type_ir(
        self,
        type_ir: CNLPTypeIR,
        index: int,
    ) -> CNLPTypeIR:
        if not isinstance(type_ir, dict):
            raise TypeError(
                f"CNL-P type at index {index} must be represented as an object."
            )

        type_name = type_ir.get("type_name")
        self._require_identifier(type_name, f"CNL-P type at index {index}")
        if "type_content" not in type_ir:
            raise TypeConversionError(
                f"CNL-P type '{type_name}' does not contain 'type_content'."
            )

        type_comment = type_ir.get("type_comment")
        if type_comment is not None and not isinstance(type_comment, str):
            raise TypeError(
                f"Comment for CNL-P type '{type_name}' must be a string or None."
            )

        return CNLPTypeIR(
            type_name=type_name,
            type_comment=type_comment,
            type_content=type_ir["type_content"],
        )

    def _render_type(self, type_ir: CNLPTypeIR) -> list[list[str]]:
        type_name = type_ir["type_name"]
        type_comment = type_ir.get("type_comment")
        type_content = type_ir["type_content"]

        if isinstance(type_content, list):
            return self._render_struct(
                type_name=type_name,
                fields=type_content,
                type_comment=type_comment,
            )

        if (
            isinstance(type_content, dict)
            and self._variant_key(type_content) == "enum_elements"
        ):
            return [
                [
                    *self._render_comment(type_comment),
                    (f"{type_name}: TypeAlias = " f"{self._render_enum(type_content)}"),
                ]
            ]

        annotation, nested_blocks = self._render_annotation(
            type_content,
            suggested_inline_name=f"{type_name}Value",
        )
        alias_block = [
            *self._render_comment(type_comment),
            f"{type_name}: TypeAlias = {annotation}",
        ]
        return [*nested_blocks, alias_block]

    def _render_struct(
        self,
        *,
        type_name: str,
        fields: list[FieldOfCNLPStructType],
        type_comment: str | None,
    ) -> list[list[str]]:
        nested_blocks: list[list[str]] = []
        lines = [
            *self._render_comment(type_comment),
            f"class {type_name}(TypedDict):",
        ]

        if not fields:
            lines.append("    pass")
            return [lines]

        seen_field_names: set[str] = set()
        for field_index, field in enumerate(fields):
            if not isinstance(field, dict):
                raise TypeError(
                    f"Field {field_index} of '{type_name}' must be an object."
                )

            field_name = field.get("field_name")
            self._require_identifier(
                field_name,
                f"Field {field_index} of '{type_name}'",
            )
            if field_name in seen_field_names:
                raise TypeConversionError(
                    f"Type '{type_name}' declares field '{field_name}' twice."
                )
            seen_field_names.add(field_name)

            if "field_content" not in field:
                raise TypeConversionError(
                    f"Field '{type_name}.{field_name}' does not contain "
                    "'field_content'."
                )

            is_optional = field.get("is_optional", False)
            if not isinstance(is_optional, bool):
                raise TypeError(
                    f"Optional marker for '{type_name}.{field_name}' "
                    "must be a boolean."
                )

            field_comment = field.get("field_comment")
            if field_comment is not None and not isinstance(field_comment, str):
                raise TypeError(
                    f"Comment for '{type_name}.{field_name}' "
                    "must be a string or None."
                )

            annotation, field_nested_blocks = self._render_annotation(
                field["field_content"],
                suggested_inline_name=(f"{type_name}{self._to_type_name(field_name)}"),
            )
            nested_blocks.extend(field_nested_blocks)
            if is_optional:
                annotation = f"NotRequired[{annotation}]"

            lines.extend(self._render_comment(field_comment, indentation="    "))
            lines.append(f"    {field_name}: {annotation}")

        return [*nested_blocks, lines]

    def _render_annotation(
        self,
        data_type: CNLPDataType,
        *,
        suggested_inline_name: str,
    ) -> tuple[str, list[list[str]]]:
        if isinstance(data_type, list):
            inline_name = self._allocate_inline_type_name(suggested_inline_name)
            nested_blocks = self._render_struct(
                type_name=inline_name,
                fields=data_type,
                type_comment=None,
            )
            return inline_name, nested_blocks

        if not isinstance(data_type, dict):
            raise TypeConversionError(f"Unsupported CNL-P data type: {data_type!r}.")

        variant = self._variant_key(data_type)
        if variant == "simple_type":
            simple_type = data_type["simple_type"]
            if not isinstance(simple_type, str):
                raise TypeError("CNL-P simple_type must be a string.")
            normalized = simple_type.lower()
            try:
                return self._SIMPLE_TYPE_MAP[normalized], []
            except KeyError as exc:
                raise TypeConversionError(
                    f"Unsupported CNL-P simple type '{simple_type}'."
                ) from exc

        if variant == "declared_type_name":
            declared_type_name = data_type["declared_type_name"]
            self._require_identifier(
                declared_type_name,
                "Declared type reference",
            )
            return repr(declared_type_name), []

        if variant == "enum_elements":
            return self._render_enum(data_type), []

        nesting_level = data_type.get("nesting_level")
        if (
            not isinstance(nesting_level, int)
            or isinstance(nesting_level, bool)
            or nesting_level < 1
        ):
            raise TypeConversionError(
                "CNL-P array nesting_level must be a positive integer."
            )

        element_annotation, nested_blocks = self._render_annotation(
            data_type["type_of_list_element"],
            suggested_inline_name=f"{suggested_inline_name}Item",
        )
        annotation = element_annotation
        for _ in range(nesting_level):
            annotation = f"list[{annotation}]"
        return annotation, nested_blocks

    def _render_config_annotation(
        self,
        data_type: CNLPDataType,
        *,
        suggested_inline_name: str,
    ) -> tuple[str, list[list[str]]]:
        """Render a type expression which config.py evaluates immediately."""
        if isinstance(data_type, list):
            inline_name = self._allocate_inline_type_name(
                suggested_inline_name
            )
            nested_blocks = self._render_struct(
                type_name=inline_name,
                fields=data_type,
                type_comment=None,
            )
            return inline_name, nested_blocks

        if not isinstance(data_type, dict):
            raise TypeConversionError(
                f"Unsupported CNL-P data type: {data_type!r}."
            )

        variant = self._variant_key(data_type)
        if variant == "simple_type":
            simple_type = data_type["simple_type"]
            if not isinstance(simple_type, str):
                raise TypeError("CNL-P simple_type must be a string.")
            try:
                return self._SIMPLE_TYPE_MAP[simple_type.lower()], []
            except KeyError as exc:
                raise TypeConversionError(
                    f"Unsupported CNL-P simple type '{simple_type}'."
                ) from exc

        if variant == "declared_type_name":
            declared_type_name = data_type["declared_type_name"]
            self._require_identifier(
                declared_type_name,
                "Declared type reference",
            )
            # config.py needs the actual imported Python type object. A quoted
            # forward reference would instead store an ordinary string.
            return declared_type_name, []

        if variant == "enum_elements":
            return self._render_enum(data_type), []

        nesting_level = data_type.get("nesting_level")
        if (
            not isinstance(nesting_level, int)
            or isinstance(nesting_level, bool)
            or nesting_level < 1
        ):
            raise TypeConversionError(
                "CNL-P array nesting_level must be a positive integer."
            )

        element_annotation, nested_blocks = self._render_config_annotation(
            data_type["type_of_list_element"],
            suggested_inline_name=f"{suggested_inline_name}Item",
        )
        annotation = element_annotation
        for _ in range(nesting_level):
            annotation = f"list[{annotation}]"
        return annotation, nested_blocks

    @staticmethod
    def _declaration_names(
        declaration_blocks: Sequence[Sequence[str]],
    ) -> list[str]:
        names: list[str] = []
        for block in declaration_blocks:
            for line in block:
                stripped = line.strip()
                if not stripped.startswith("class "):
                    continue
                name = stripped.removeprefix("class ").split("(", 1)[0]
                if name and name not in names:
                    names.append(name)
        return names

    def _render_enum(self, enum_type: dict[str, Any]) -> str:
        enum_elements = enum_type.get("enum_elements")
        if not isinstance(enum_elements, list) or not enum_elements:
            raise TypeConversionError(
                "CNL-P enum type must contain at least one element."
            )
        if not all(isinstance(element, str) for element in enum_elements):
            raise TypeError("Every CNL-P enum element must be a string.")

        rendered_elements = ", ".join(repr(element) for element in enum_elements)
        return f"Literal[{rendered_elements}]"

    def _allocate_inline_type_name(self, suggested_name: str) -> str:
        candidate = suggested_name
        suffix = 2
        while candidate in self._used_type_names:
            candidate = f"{suggested_name}{suffix}"
            suffix += 1
        self._used_type_names.add(candidate)
        return candidate

    @staticmethod
    def _render_comment(
        comment: str | None,
        *,
        indentation: str = "",
    ) -> list[str]:
        if comment is None or not comment.strip():
            return []
        return [
            f"{indentation}# {line}" if line else f"{indentation}#"
            for line in comment.strip().splitlines()
        ]

    @staticmethod
    def _variant_key(data_type: dict[str, Any]) -> str:
        variant_keys = [
            key
            for key in (
                "simple_type",
                "declared_type_name",
                "type_of_list_element",
                "enum_elements",
            )
            if key in data_type
        ]
        if len(variant_keys) != 1:
            raise TypeConversionError(
                "A CNL-P data type must contain exactly one type variant; "
                f"received {data_type!r}."
            )
        return variant_keys[0]

    @staticmethod
    def _to_type_name(identifier: str) -> str:
        parts = [part for part in identifier.split("_") if part]
        if not parts:
            return "Field"
        return "".join(part[:1].upper() + part[1:] for part in parts)

    @staticmethod
    def _require_identifier(value: Any, source: str) -> None:
        if not isinstance(value, str) or not value:
            raise TypeError(f"{source} must contain a non-empty string name.")
        if not value.isidentifier() or keyword.iskeyword(value):
            raise TypeConversionError(
                f"{source} name '{value}' is not a valid Python identifier."
            )
