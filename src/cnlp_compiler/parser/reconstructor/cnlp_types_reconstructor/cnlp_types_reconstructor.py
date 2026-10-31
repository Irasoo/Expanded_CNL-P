from .cnlp_types_tokenizer import CNLPTypeTokenizer
from .cnlp_types_parser import CNLPTypeParser
from ....schema.cnlp_types import CNLPTypeIR
from ....schema.result import Failure, Result

from typing import List, Dict
import re


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_type_identifiers(
    data_type,
    *,
    declaration_name: str,
    line_number: int | None,
) -> list[Failure]:
    errors: list[Failure] = []
    if isinstance(data_type, list):
        seen_fields: set[str] = set()
        for field in data_type:
            field_name = field.get("field_name")
            if not isinstance(field_name, str) or not _IDENTIFIER_PATTERN.fullmatch(
                field_name
            ):
                errors.append(
                    Failure(
                        value=field_name,
                        is_fatal=False,
                        error_type="type_definition_error",
                        message=(
                            f"Invalid field name {field_name!r} in type "
                            f"{declaration_name!r}."
                        ),
                        start_line=line_number,
                        end_line=line_number,
                    )
                )
            elif field_name in seen_fields:
                errors.append(
                    Failure(
                        value=field_name,
                        is_fatal=False,
                        error_type="type_definition_error",
                        message=(
                            f"Duplicate field {field_name!r} in type "
                            f"{declaration_name!r}."
                        ),
                        start_line=line_number,
                        end_line=line_number,
                    )
                )
            else:
                seen_fields.add(field_name)
            errors.extend(
                _validate_type_identifiers(
                    field.get("field_content"),
                    declaration_name=declaration_name,
                    line_number=line_number,
                )
            )
        return errors

    if not isinstance(data_type, dict):
        return errors

    declared_type_name = data_type.get("declared_type_name")
    if isinstance(declared_type_name, str) and not _IDENTIFIER_PATTERN.fullmatch(
        declared_type_name
    ):
        errors.append(
            Failure(
                value=declared_type_name,
                is_fatal=False,
                error_type="type_definition_error",
                message=(
                    f"Invalid declared type name {declared_type_name!r} in "
                    f"type {declaration_name!r}."
                ),
                start_line=line_number,
                end_line=line_number,
            )
        )

    enum_elements = data_type.get("enum_elements")
    if isinstance(enum_elements, list):
        seen_elements: set[str] = set()
        for element in enum_elements:
            if not isinstance(element, str) or not _IDENTIFIER_PATTERN.fullmatch(
                element
            ):
                errors.append(
                    Failure(
                        value=element,
                        is_fatal=False,
                        error_type="type_definition_error",
                        message=(
                            f"Invalid enum element {element!r} in type "
                            f"{declaration_name!r}."
                        ),
                        start_line=line_number,
                        end_line=line_number,
                    )
                )
            elif element in seen_elements:
                errors.append(
                    Failure(
                        value=element,
                        is_fatal=False,
                        error_type="type_definition_error",
                        message=(
                            f"Duplicate enum element {element!r} in type "
                            f"{declaration_name!r}."
                        ),
                        start_line=line_number,
                        end_line=line_number,
                    )
                )
            else:
                seen_elements.add(element)

    element_type = data_type.get("type_of_list_element")
    if element_type is not None:
        errors.extend(
            _validate_type_identifiers(
                element_type,
                declaration_name=declaration_name,
                line_number=line_number,
            )
        )
    return errors


class CNLPTypeReconstructor:

    @staticmethod
    def reconstruct_cnlp_types(cnlp_types_sentence: List[dict]) -> Dict[str, List[CNLPTypeIR] | List[Result]]:
        error_list = []

        tokenize_result = CNLPTypeTokenizer.tokenize(cnlp_types_sentence)
        token_list = tokenize_result['token_list']
        error_list.extend(tokenize_result['error_list'])

        cnlp_type_parser = CNLPTypeParser()
        parse_result = cnlp_type_parser.cnlp_type_parse(token_array=token_list)
        error_list.extend(parse_result['error_list'])

        for type_ir in parse_result["success_list"]:
            type_name = type_ir["type_name"]
            type_line = next(
                (
                    token["start_line"]
                    for token in token_list
                    if token["token_value"] == type_name
                ),
                None,
            )
            if not _IDENTIFIER_PATTERN.fullmatch(type_name):
                error_list.append(
                    Failure(
                        value=type_name,
                        is_fatal=False,
                        error_type="type_definition_error",
                        message=f"Invalid type name {type_name!r}.",
                        start_line=type_line,
                        end_line=type_line,
                    )
                )
            error_list.extend(
                _validate_type_identifiers(
                    type_ir["type_content"],
                    declaration_name=type_name,
                    line_number=type_line,
                )
            )

        return {"success_list": parse_result['success_list'], "error_list": error_list}
