from ...schemas.parser_like import CNLPSentence, AspectSentence
from ...schemas.result import Result, Success, Failure

import re
from typing import Literal

aspect_pattern = re.compile(r'^([A-Z][a-zA-Z]*):\s*.*$')


def recognize_aspect_sentence(
        # 关于belonging这个参数，应该
        belonging: Literal["persona", "constraints", "instruction", "type", "variable"],
        cnlp_sentence: str,
        start_line: int,
        end_line: int
) -> Result:
    cnlp_sentence = cnlp_sentence.strip()
    # 使用.fullmatch()方式，确保整个语句完全匹配上述
    aspect_match = aspect_pattern.fullmatch(cnlp_sentence)
    if aspect_match:
        return Success(
            CNLPSentence(
                belonging=belonging,
                line_record={'start_line': start_line, 'end_line': end_line},
                details=AspectSentence(
                    aspect_name=aspect_match.group(1),
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

