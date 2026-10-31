from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .models import ParameterSpec, RegisteredCode, ReturnSpec
from .source_inspector import SourceInformation, inspect_function, inspect_source

__all__ = [
    "ParameterSpec",
    "RegisteredCode",
    "ReturnSpec",
    "register_code",
    "register_function",
]


# The only runtime storage for registered reference code.
_REGISTERED_CODE: dict[str, RegisteredCode] = {}


def register_code(
    *,
    code: str,
    description: str,
    parameter_spec: Sequence[
        ParameterSpec | Mapping[str, Any]
    ] | None = None,
    return_spec: ReturnSpec | Mapping[str, Any] | None = None,
) -> RegisteredCode:
    """Register one function supplied as a source string."""
    source = inspect_source(code)
    entry = _build_entry(
        source,
        description=description,
        parameters=parameter_spec,
        returns=return_spec,
        registration_method="string",
    )
    return _store(entry)


def register_function(
    *,
    description: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register a decorated function in the internal catalog storage."""

    def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
        source = inspect_function(function)
        entry = _build_entry(
            source,
            description=description,
            parameters=None,
            returns=None,
            registration_method="decorator",
            function=function,
        )
        _store(entry)
        return function

    return decorator


def _get_registered_code(name: str) -> RegisteredCode:
    """Internal read API used only by ReferenceCodeCatalog."""
    try:
        return _REGISTERED_CODE[name]
    except KeyError as exc:
        raise KeyError(f"Reference code {name!r} is not registered.") from exc


def _all_registered_code() -> tuple[RegisteredCode, ...]:
    """Internal read API used only by ReferenceCodeCatalog."""
    return tuple(
        _REGISTERED_CODE[name] for name in sorted(_REGISTERED_CODE)
    )


def _registered_code_count() -> int:
    return len(_REGISTERED_CODE)


def _build_entry(
    source: SourceInformation,
    *,
    description: str,
    parameters,
    returns,
    registration_method,
    function=None,
) -> RegisteredCode:
    if not isinstance(description, str) or not description.strip():
        raise ValueError("description must be a non-empty string.")

    return RegisteredCode(
        name=source.function_name,
        function_name=source.function_name,
        description=description.strip(),
        parameters=_normalize_parameters(parameters, source.parameters),
        returns=_normalize_return(returns, source.returns),
        code=source.code,
        registration_method=registration_method,
        function=function,
        module=function.__module__ if function else None,
        qualname=function.__qualname__ if function else None,
    )


def _store(entry: RegisteredCode) -> RegisteredCode:
    if entry.name in _REGISTERED_CODE:
        raise ValueError(
            f"Reference code {entry.name!r} is already registered."
        )
    _REGISTERED_CODE[entry.name] = entry
    return entry


def _normalize_parameters(
    parameters,
    inferred: tuple[ParameterSpec, ...],
) -> tuple[ParameterSpec, ...]:
    if parameters is None:
        return inferred

    normalized = tuple(
        item
        if isinstance(item, ParameterSpec)
        else ParameterSpec.from_dict(item)
        for item in parameters
    )
    if [item.name for item in normalized] != [
        item.name for item in inferred
    ]:
        raise ValueError(
            "parameter_spec must follow the function signature order."
        )
    return normalized


def _normalize_return(
    returns,
    inferred: ReturnSpec,
) -> ReturnSpec:
    if returns is None:
        return inferred
    if isinstance(returns, ReturnSpec):
        return returns
    if isinstance(returns, Mapping):
        return ReturnSpec.from_dict(returns)
    raise TypeError("return_spec must be ReturnSpec or a mapping.")
