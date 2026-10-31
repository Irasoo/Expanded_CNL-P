from ...schema.parser import CNLPSentence, AspectSentence
from ...schema.result import Result, Success, Failure

import re
from typing import Literal

aspect_sentence_pattern = re.compile(
    r'^(?P<name>[A-Za-z_][a-zA-Z0-9_]*):\s*(?P<content>.*)$'
)
aspect_name_pattern = re.compile(r'^[A-Z][a-zA-Z0-9_]*$')


def recognize_aspect_sentence(
        # 关于belonging这个参数，应该
        belonging: Literal["persona", "constraints", "instruction", "type", "variable"],
        cnlp_sentence: str,
        start_line: int,
        end_line: int
) -> Result:
    cnlp_sentence = cnlp_sentence.strip()
    # 使用.fullmatch()方式，确保整个语句完全匹配上述
    aspect_match = aspect_sentence_pattern.fullmatch(cnlp_sentence)
    if aspect_match:
        aspect_name = aspect_match.group("name")
        if not aspect_name_pattern.fullmatch(aspect_name):
            return Failure(
                value=cnlp_sentence,
                is_fatal=False,
                error_type="invalid_aspect_name",
                message=(
                    "An Agent aspect name must start with an uppercase "
                    "letter and contain only letters, digits, or underscores."
                ),
                start_line=start_line,
                end_line=end_line,
            )
        if not aspect_match.group("content").strip():
            return Failure(
                value=cnlp_sentence,
                is_fatal=False,
                error_type="empty_aspect_value",
                message="An Agent aspect must contain text after ':'.",
                start_line=start_line,
                end_line=end_line,
            )
        return Success(
            CNLPSentence(
                belonging=belonging,
                line_record={'start_line': start_line, 'end_line': end_line},
                details=AspectSentence(
                    aspect_name=aspect_name,
                    sentence=cnlp_sentence
                )
            )
        )
    else:
        return Failure(
            value=cnlp_sentence,
            is_fatal=False,
            error_type="unrecognized_sentence",
            message="This sentence is not an 'aspect sentence' in CNL-P BNF",
            start_line=start_line,
            end_line=end_line
        )
