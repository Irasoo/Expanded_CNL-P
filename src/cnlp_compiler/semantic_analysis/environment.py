from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from typing import Any


def _decode_mapping(value: str | dict[str, Any] | None) -> dict[str, Any]:
    """Decode the JSON/Python-literal formats used by the ICLR dataset."""

    if value is None:
        return {}
    current: Any = value
    for _ in range(6):
        if isinstance(current, dict):
            break
        if not isinstance(current, str):
            raise ValueError("Semantic environment must be a mapping or string.")
        source = current.strip()
        if not source:
            return {}
        decoded = None
        for loader in (json.loads, ast.literal_eval):
            try:
                decoded = loader(source)
                break
            except (ValueError, SyntaxError, json.JSONDecodeError):
                continue
        if decoded is None:
            try:
                decoded = ast.literal_eval("{" + source + "}")
            except (ValueError, SyntaxError) as exc:
                raise ValueError("Invalid semantic-environment mapping.") from exc
        current = decoded
    if not isinstance(current, dict):
        raise ValueError("Semantic environment did not decode to a mapping.")
    return current


@dataclass(frozen=True)
class GlobalVariable:
    name: str
    type_name: str
    value: Any
    source: str | None = None


@dataclass(frozen=True)
class APIDefinition:
    name: str
    parameters: dict[str, str]
    return_type: str | None
    source: str | None = None


@dataclass(frozen=True)
class SemanticEnvironment:
    """Per-instance Global/API/Schema context for semantic analysis."""

    global_variables: dict[str, GlobalVariable]
    apis: dict[str, APIDefinition]
    schema_source: str

    @classmethod
    def from_raw(
        cls,
        *,
        global_variables: str | dict[str, Any] | None = None,
        apis: str | dict[str, Any] | None = None,
        schema: str | None = None,
    ) -> "SemanticEnvironment":
        raw_globals = _decode_mapping(global_variables)
        # A few historical instances wrap the real fragment one extra time.
        while set(raw_globals) == {"global_variable"}:
            raw_globals = _decode_mapping(raw_globals["global_variable"])

        parsed_globals: dict[str, GlobalVariable] = {}
        for name, payload in raw_globals.items():
            if not isinstance(name, str) or not isinstance(payload, dict):
                continue
            type_name = payload.get("type", "UnKnown")
            parsed_globals[name] = GlobalVariable(
                name=name,
                type_name=(type_name if isinstance(type_name, str) else "UnKnown"),
                value=payload.get("value"),
                source=(payload.get("source") if isinstance(payload.get("source"), str) else None),
            )

        raw_apis = _decode_mapping(apis)
        parsed_apis: dict[str, APIDefinition] = {}
        for name, payload in raw_apis.items():
            if not isinstance(name, str) or not isinstance(payload, dict):
                continue
            raw_parameters = payload.get("paras", {})
            parameters = {
                parameter: type_name
                for parameter, type_name in raw_parameters.items()
                if isinstance(parameter, str) and isinstance(type_name, str)
            } if isinstance(raw_parameters, dict) else {}
            raw_return = payload.get("return")
            parsed_apis[name] = APIDefinition(
                name=name,
                parameters=parameters,
                return_type=(raw_return if isinstance(raw_return, str) and raw_return else None),
                source=(payload.get("source") if isinstance(payload.get("source"), str) else None),
            )

        return cls(
            global_variables=parsed_globals,
            apis=parsed_apis,
            schema_source=schema or "",
        )


__all__ = [
    "APIDefinition",
    "GlobalVariable",
    "SemanticEnvironment",
]
