from typing import Dict, List

from ....schema.cnlp_variables import CNLPVariableIR
from ....schema.result import Failure, Result
from .variable_parser import CNLPVariableParser


class CNLPVariableReconstructor:
    @staticmethod
    def reconstruct_cnlp_variables(
        variable_sentences: List[dict],
    ) -> Dict[str, List[CNLPVariableIR] | List[Result]]:
        success_list: list[CNLPVariableIR] = []
        error_list: list[Failure] = []

        for variable_sentence in variable_sentences:
            sentence = variable_sentence["sentence"]
            if not sentence.strip():
                continue

            result = CNLPVariableParser.parse_line(
                sentence=sentence,
                line_number=variable_sentence["line_number"],
            )
            if isinstance(result, Failure):
                error_list.append(result)
            else:
                success_list.append(result.value)

        return {
            "success_list": success_list,
            "error_list": error_list,
        }
