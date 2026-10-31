from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any


_BUILTIN_ALIASES = {
    "str": "text",
    "string": "text",
    "text": "text",
    "int": "int",
    "float": "float",
    "number": "number",
    "bool": "boolean",
    "boolean": "boolean",
    "dict": "dict",
    "list": "list",
}


@dataclass(frozen=True)
class TypeSpec:
    kind: str
    name: str | None = None
    fields: dict[str, "TypeSpec"] = field(default_factory=dict)
    required_fields: frozenset[str] = frozenset()
    element: "TypeSpec | None" = None
    literals: tuple[Any, ...] = ()


class TypeRegistry:
    """Resolve CNL-P local types and the instance-provided Python schema."""

    def __init__(self, local_types: dict[str, Any], schema_source: str) -> None:
        self.local_types = dict(local_types)
        self.external_types = self._parse_schema(schema_source)

    def exists(self, type_name: str | None) -> bool:
        if not type_name:
            return False
        if type_name == "UnKnown":
            return True
        return (
            type_name.lower() in _BUILTIN_ALIASES
            or type_name in self.local_types
            or type_name in self.external_types
        )

    def compatible(self, actual_name: str, expected_name: str) -> bool:
        if actual_name == "UnKnown" or expected_name == "UnKnown":
            return True
        if not self.exists(actual_name) or not self.exists(expected_name):
            return False
        actual = self.resolve_name(actual_name)
        expected = self.resolve_name(expected_name)
        if actual_name == expected_name or actual == expected:
            return True
        if actual.kind == expected.kind and actual.kind in {
            "text",
            "int",
            "float",
            "number",
            "boolean",
            "dict",
        }:
            return True
        if actual.kind == "struct" and expected.kind == "dict":
            return True
        if actual.kind == "int" and expected.kind in {"float", "number"}:
            return True
        if actual.kind == "float" and expected.kind == "number":
            return True
        return False

    def resolve_name(self, type_name: str, active: frozenset[str] = frozenset()) -> TypeSpec:
        builtin = _BUILTIN_ALIASES.get(type_name.lower())
        if builtin is not None:
            return TypeSpec(kind=builtin, name=type_name)
        if type_name in active:
            return TypeSpec(kind="unknown", name=type_name)
        if type_name in self.local_types:
            return self._from_cnlp(
                self.local_types[type_name],
                active | {type_name},
            )
        if type_name in self.external_types:
            return self._resolve_external(
                self.external_types[type_name],
                active | {type_name},
            )
        return TypeSpec(kind="unknown", name=type_name)

    def validate_value(self, value: Any, expected_name: str) -> tuple[str, ...]:
        if not self.exists(expected_name):
            return (f"Type '{expected_name}' cannot be found.",)
        problems: list[str] = []
        self._validate(value, self.resolve_name(expected_name), "", problems)
        return tuple(problems)

    def _validate(
        self,
        value: Any,
        spec: TypeSpec,
        path: str,
        problems: list[str],
    ) -> None:
        label = path or "value"
        if spec.kind == "text" and not isinstance(value, str):
            problems.append(f"{label} must be text.")
        elif spec.kind == "int" and (not isinstance(value, int) or isinstance(value, bool)):
            problems.append(f"{label} must be int.")
        elif spec.kind in {"float", "number"} and (
            not isinstance(value, (int, float)) or isinstance(value, bool)
        ):
            problems.append(f"{label} must be a number.")
        elif spec.kind == "boolean" and not isinstance(value, bool):
            problems.append(f"{label} must be boolean.")
        elif spec.kind == "dict" and not isinstance(value, dict):
            problems.append(f"{label} must be a mapping.")
        elif spec.kind == "list":
            if not isinstance(value, list):
                problems.append(f"{label} must be a list.")
            elif spec.element is not None:
                for index, item in enumerate(value):
                    self._validate(item, spec.element, f"{label}[{index}]", problems)
        elif spec.kind == "literal" and value not in spec.literals:
            problems.append(f"{label} must be one of {list(spec.literals)!r}.")
        elif spec.kind == "struct":
            if not isinstance(value, dict):
                problems.append(f"{label} must be a mapping.")
                return
            for field_name in sorted(spec.required_fields - set(value)):
                field_path = f"{path}.{field_name}" if path else field_name
                problems.append(f"Required field '{field_path}' is missing.")
            for field_name, field_spec in spec.fields.items():
                if field_name in value:
                    field_path = f"{path}.{field_name}" if path else field_name
                    self._validate(value[field_name], field_spec, field_path, problems)

    def _from_cnlp(self, value: Any, active: frozenset[str]) -> TypeSpec:
        if isinstance(value, list):
            fields: dict[str, TypeSpec] = {}
            required: set[str] = set()
            for field_info in value:
                if not isinstance(field_info, dict):
                    continue
                name = field_info.get("field_name")
                if not isinstance(name, str):
                    continue
                fields[name] = self._from_cnlp(field_info.get("field_content"), active)
                if not field_info.get("is_optional", False):
                    required.add(name)
            return TypeSpec(
                kind="struct",
                fields=fields,
                required_fields=frozenset(required),
            )
        if not isinstance(value, dict):
            return TypeSpec(kind="unknown")
        if isinstance(value.get("simple_type"), str):
            return self.resolve_name(value["simple_type"], active)
        if isinstance(value.get("declared_type_name"), str):
            return self.resolve_name(value["declared_type_name"], active)
        if isinstance(value.get("enum_elements"), list):
            return TypeSpec(kind="literal", literals=tuple(value["enum_elements"]))
        if "type_of_list_element" in value:
            return TypeSpec(
                kind="list",
                element=self._from_cnlp(value["type_of_list_element"], active),
            )
        return TypeSpec(kind="unknown")

    def _resolve_external(self, spec: TypeSpec, active: frozenset[str]) -> TypeSpec:
        if spec.kind != "reference" or spec.name is None:
            if spec.kind == "list" and spec.element is not None:
                return TypeSpec(kind="list", element=self._resolve_external(spec.element, active))
            if spec.kind == "struct":
                return TypeSpec(
                    kind="struct",
                    fields={
                        name: self._resolve_external(field_spec, active)
                        for name, field_spec in spec.fields.items()
                    },
                    required_fields=spec.required_fields,
                )
            return spec
        if spec.name in active:
            return TypeSpec(kind="unknown", name=spec.name)
        return self.resolve_name(spec.name, active)

    @classmethod
    def _parse_schema(cls, source: str) -> dict[str, TypeSpec]:
        if not source.strip():
            return {}
        tree = ast.parse(source)
        result: dict[str, TypeSpec] = {}
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                fields: dict[str, TypeSpec] = {}
                required: set[str] = set()
                for statement in node.body:
                    if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                        continue
                    fields[statement.target.id] = cls._from_python_annotation(statement.annotation)
                    required.add(statement.target.id)
                result[node.name] = TypeSpec(
                    kind="struct",
                    name=node.name,
                    fields=fields,
                    required_fields=frozenset(required),
                )
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                result[node.targets[0].id] = cls._from_python_annotation(node.value)
        return result

    @classmethod
    def _from_python_annotation(cls, node: ast.AST) -> TypeSpec:
        if isinstance(node, ast.Name):
            builtin = _BUILTIN_ALIASES.get(node.id.lower())
            return TypeSpec(kind=builtin, name=node.id) if builtin else TypeSpec(kind="reference", name=node.id)
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            container = node.value.id
            if container in {"List", "list"}:
                return TypeSpec(kind="list", element=cls._from_python_annotation(node.slice))
            if container == "Literal":
                values = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
                return TypeSpec(
                    kind="literal",
                    literals=tuple(
                        item.value for item in values if isinstance(item, ast.Constant)
                    ),
                )
        return TypeSpec(kind="unknown")


def type_name_from_cnlp(data_type: Any) -> str | None:
    if not isinstance(data_type, dict):
        return None
    for key in ("simple_type", "declared_type_name"):
        value = data_type.get(key)
        if isinstance(value, str):
            return value
    return None


__all__ = ["TypeRegistry", "TypeSpec", "type_name_from_cnlp"]
