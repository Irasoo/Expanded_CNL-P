from __future__ import annotations

from typing import TypeAlias, TypedDict

from ...schema import GeneratedFile


CommandFunctionNames: TypeAlias = list[str]
"""Generated Command function names in CNL-P source order."""

PredicateNamingTable: TypeAlias = dict[str, str]
"""
Map each dot-separated condition_path to its generated function name.

TODO(main-condition-location): Main generation must confirm that it can
reconstruct exactly the same canonical path from the workflow input. If a
text-only generation step cannot reliably identify a path such as
worker.main_flow.if_block1.if_branch1, MainImplementer should receive a
normalized structural routing record instead of guessing the correspondence.
"""


class FunctionImplementation(TypedDict):
    function_name: str
    function_code: str


class TypeImplementationResult(TypedDict):
    generated_file: GeneratedFile
    python_type_code: str
    declared_type_names: list[str]
    variable_type_expression_table: dict[str, str]
    config_schema_import_names: list[str]
    config_typing_import_names: list[str]


class CommandImplementationResult(TypedDict):
    generated_file: GeneratedFile
    command_function_names: CommandFunctionNames


class PredicateImplementationResult(TypedDict):
    generated_file: GeneratedFile
    predicate_naming_table: PredicateNamingTable
