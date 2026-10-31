from __future__ import annotations

import ast
import inspect
import re
import textwrap
from dataclasses import dataclass

from .models import ParameterSpec, ReturnSpec


# TODO(reference-code-dependencies): RegisteredCode currently stores only one
# complete function block. Module-level imports, constants, helper functions,
# and other external definitions used by that function are not collected yet.
# For the first Native implementation, reference functions should therefore be
# self-contained; required imports can be written inside the function body.
# A future version should record and validate explicit dependency metadata.
@dataclass(frozen=True)
class SourceInformation:
    code: str
    function_name: str
    description: str
    parameters: tuple[ParameterSpec, ...]
    returns: ReturnSpec


def inspect_source(code: str) -> SourceInformation:
    """Inspect one top-level function without executing its source."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError("code must be a non-empty string.")

    normalized = textwrap.dedent(code).strip()
    try:
        tree = ast.parse(normalized)
    except SyntaxError as exc:
        raise ValueError(
            f"Invalid Python source at line {exc.lineno}: {exc.msg}."
        ) from exc

    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if len(functions) != 1:
        raise ValueError(
            "String registration requires exactly one top-level function."
        )

    function = functions[0]
    doc = _read_docstring(ast.get_docstring(function) or "")
    return SourceInformation(
        code=normalized + "\n",
        function_name=function.name,
        description=doc["description"],
        parameters=_read_parameters(
            function,
            doc["parameter_descriptions"],
        ),
        returns=_read_return(function, doc["return_description"]),
    )


def inspect_function(function) -> SourceInformation:
    """Extract source and metadata from a decorated Python function."""
    if not inspect.isfunction(function):
        raise TypeError("Only Python functions can be registered.")
    try:
        raw_source = textwrap.dedent(inspect.getsource(function))
    except (OSError, TypeError) as exc:
        raise ValueError(
            f"Source for {function.__qualname__!r} is not readable; "
            "use string registration instead."
        ) from exc

    tree = ast.parse(raw_source)
    node = next(
        (
            item
            for item in tree.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == function.__name__
        ),
        None,
    )
    if node is None or node.end_lineno is None:
        raise ValueError(f"Cannot locate source for {function.__qualname__!r}.")

    lines = raw_source.splitlines()
    source_without_decorators = "\n".join(
        lines[node.lineno - 1 : node.end_lineno]
    )
    return inspect_source(source_without_decorators)


def _read_parameters(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    descriptions: dict[str, str],
) -> tuple[ParameterSpec, ...]:
    result = []
    arguments = function.args
    positional = [
        ("positional_only", argument)
        for argument in arguments.posonlyargs
    ] + [
        ("positional_or_keyword", argument)
        for argument in arguments.args
    ]
    default_start = len(positional) - len(arguments.defaults)

    for index, (kind, argument) in enumerate(positional):
        default = (
            arguments.defaults[index - default_start]
            if index >= default_start
            else None
        )
        result.append(
            ParameterSpec(
                name=argument.arg,
                type_name=_annotation(argument.annotation),
                kind=kind,
                required=default is None,
                default=ast.unparse(default) if default is not None else None,
                description=descriptions.get(argument.arg, ""),
            )
        )

    if arguments.vararg:
        result.append(
            ParameterSpec(
                name=arguments.vararg.arg,
                type_name=_annotation(arguments.vararg.annotation),
                kind="var_positional",
                required=False,
                description=descriptions.get(arguments.vararg.arg, ""),
            )
        )

    for argument, default in zip(
        arguments.kwonlyargs,
        arguments.kw_defaults,
    ):
        result.append(
            ParameterSpec(
                name=argument.arg,
                type_name=_annotation(argument.annotation),
                kind="keyword_only",
                required=default is None,
                default=ast.unparse(default) if default is not None else None,
                description=descriptions.get(argument.arg, ""),
            )
        )

    if arguments.kwarg:
        result.append(
            ParameterSpec(
                name=arguments.kwarg.arg,
                type_name=_annotation(arguments.kwarg.annotation),
                kind="var_keyword",
                required=False,
                description=descriptions.get(arguments.kwarg.arg, ""),
            )
        )
    return tuple(result)


def _read_return(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    description: str,
) -> ReturnSpec:
    annotation = (
        ast.unparse(function.returns) if function.returns is not None else None
    )
    if annotation in {"None", "NoneType"}:
        return ReturnSpec(False, None, description)
    if annotation:
        return ReturnSpec(True, annotation, description)

    has_value_return = any(
        isinstance(node, ast.Return) and node.value is not None
        for node in ast.walk(function)
    )
    return ReturnSpec(
        has_return=has_value_return,
        type_name="Any" if has_value_return else None,
        description=description,
    )


def _annotation(annotation: ast.expr | None) -> str:
    return ast.unparse(annotation) if annotation is not None else "Any"


def _read_docstring(docstring: str) -> dict:
    """Read summary plus Google/Sphinx parameter and return descriptions."""
    lines = inspect.cleandoc(docstring).splitlines()
    description = []
    parameter_descriptions = {}
    return_description = []
    section = "description"
    current_parameter = None

    for raw_line in lines:
        line = raw_line.strip()
        lowered = line.lower()
        if lowered in {"args:", "arguments:", "parameters:"}:
            section = "parameters"
            current_parameter = None
            continue
        if lowered in {"return:", "returns:"}:
            section = "return"
            current_parameter = None
            continue
        if lowered in {"raises:", "examples:", "notes:"}:
            section = "ignore"
            current_parameter = None
            continue

        sphinx_parameter = re.match(
            r"^:param\s+([*]{0,2}\w+)\s*:\s*(.*)$",
            line,
        )
        if sphinx_parameter:
            parameter_descriptions[
                sphinx_parameter.group(1).lstrip("*")
            ] = sphinx_parameter.group(2)
            continue
        sphinx_return = re.match(r"^:returns?\s*:\s*(.*)$", line)
        if sphinx_return:
            return_description.append(sphinx_return.group(1))
            continue

        if section == "description":
            description.append(line)
        elif section == "parameters":
            match = re.match(
                r"^([*]{0,2}\w+)(?:\s*\([^)]*\))?\s*:\s*(.*)$",
                line,
            )
            if match:
                current_parameter = match.group(1).lstrip("*")
                parameter_descriptions[current_parameter] = match.group(2)
            elif line and current_parameter:
                parameter_descriptions[current_parameter] += f" {line}"
        elif section == "return" and line:
            typed = re.match(r"^[\w.\[\], |]+\s*:\s*(.*)$", line)
            return_description.append(typed.group(1) if typed else line)

    return {
        "description": _paragraph(description),
        "parameter_descriptions": parameter_descriptions,
        "return_description": _paragraph(return_description),
    }


def _paragraph(lines: list[str]) -> str:
    return " ".join(line for line in lines if line).strip()
