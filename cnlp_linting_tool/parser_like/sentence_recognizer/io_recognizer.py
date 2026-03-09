from ...schemas.parser_like import IOSentence, CNLPSentence
from ...schemas.result import Success, Failure, Result
from typing import Literal, List, Dict

import re


reference_pattern = re.compile(r"^\s*(REQUIRED|OPTIONAL)?\s*(<REF>.*?</REF>)\s*$", re.DOTALL | re.IGNORECASE)


def recognize_input_sentence(
        belonging: Literal["persona", "constraints", "instruction", "type", "variable"],
        cnlp_sentences: List[dict],
        *args,
        **kwargs
) -> Dict[str, List[Result]]:

    success_list = []
    error_list = []

    for sentence in cnlp_sentences:

        line_number = sentence["line_number"]
        sentence = sentence["sentence"]

        reference_match_result = reference_pattern.match(sentence)
        if reference_match_result:
            success_list.append(
                Success(
                    CNLPSentence(
                        belonging=belonging,
                        line_record={'start_line': line_number, 'end_line': line_number},
                        details=IOSentence(
                            IO="input",
                            is_required=True if reference_match_result.group(1) == "REQUIRED" else False,
                            sentence=reference_match_result.group(2),
                        )
                    )
                )
            )
        else:
            error_list.append(
                Failure(
                    value=sentence,
                    is_fatal=False,
                    error_type="unrecognized_sentence",
                    message=f"The sentence: '{sentence}' does not match the basic pattern of the reference.",
                    start_line=line_number,
                    end_line=line_number
                )
            )

    return {"success_list": success_list, "error_list": error_list}


def recognize_output_sentence(
        belonging: Literal["persona", "constraints", "instruction", "type", "variable"],
        cnlp_sentences: List[dict],
        *args,
        **kwargs
) -> Dict[str, List[Result]]:

    success_list = []
    error_list = []

    for sentence in cnlp_sentences:

        line_number = sentence["line_number"]
        sentence = sentence["sentence"]


        reference_match_result = reference_pattern.match(sentence)
        if reference_match_result:
            success_list.append(
                Success(
                    CNLPSentence(
                        belonging=belonging,
                        line_record={'start_line': line_number, 'end_line': line_number},
                        details=IOSentence(
                            IO="output",
                            is_required=True if reference_match_result.group(1) == "REQUIRED" else False,
                            sentence=reference_match_result.group(2),
                        )
                    )
                )
            )
        else:
            error_list.append(
                Failure(
                    value=sentence,
                    is_fatal=False,
                    error_type="unrecognized_sentence",
                    message=f"The sentence: '{sentence}' does not match the basic pattern of the reference.",
                    start_line = line_number,
                    end_line = line_number
                )
            )

    return {"success_list": success_list, "error_list": error_list}

