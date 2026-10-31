from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal


# TODO(reference-code-complex-type-schema): Extend ParameterSpec and
# ReturnSpec with expanded schemas for TypedDict, dataclass, Pydantic model,
# alias, nested-container, and union annotations. Until then, Catalog matching
# uses simplified types and detailed adaptation is performed during Call API
# implementation with the selected reference source.


ParameterKind = Literal[
    "positional_only",
    "positional_or_keyword",
    "var_positional",
    "keyword_only",
    "var_keyword",
]
RegistrationMethod = Literal["string", "decorator"]


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    type_name: str = "Any"
    kind: ParameterKind = "positional_or_keyword"
    required: bool = True
    default: str | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type_name,
            "kind": self.kind,
            "required": self.required,
            "default": self.default,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ParameterSpec:
        return cls(
            name=data["name"],
            type_name=data.get("type", "Any"),
            kind=data.get("kind", "positional_or_keyword"),
            required=data.get("required", True),
            default=data.get("default"),
            description=data.get("description", ""),
        )


@dataclass(frozen=True)
class ReturnSpec:
    has_return: bool
    type_name: str | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_return": self.has_return,
            "type": self.type_name,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReturnSpec:
        return cls(
            has_return=data["has_return"],
            type_name=data.get("type"),
            description=data.get("description", ""),
        )


@dataclass(frozen=True)
class RegisteredCode:
    name: str
    function_name: str
    description: str
    parameters: tuple[ParameterSpec, ...]
    returns: ReturnSpec
    code: str
    registration_method: RegistrationMethod
    tags: tuple[str, ...] = ()
    module: str | None = None
    qualname: str | None = None
    function: Callable[..., Any] | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe source and metadata without the live callable."""
        return {
            "name": self.name,
            "function_name": self.function_name,
            "description": self.description,
            "parameters": [
                parameter.to_dict() for parameter in self.parameters
            ],
            "return": self.returns.to_dict(),
            "code": self.code,
            "registration_method": self.registration_method,
            "language": "python",
            "tags": list(self.tags),
            "module": self.module,
            "qualname": self.qualname,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RegisteredCode:
        if data.get("language", "python") != "python":
            raise ValueError("Only Python reference code is supported.")
        return cls(
            name=data["name"],
            function_name=data["function_name"],
            description=data["description"],
            parameters=tuple(
                ParameterSpec.from_dict(item)
                for item in data.get("parameters", [])
            ),
            returns=ReturnSpec.from_dict(data["return"]),
            code=data["code"],
            registration_method=data["registration_method"],
            tags=tuple(data.get("tags", [])),
            module=data.get("module"),
            qualname=data.get("qualname"),
        )
