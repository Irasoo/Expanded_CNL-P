from ..schemas.result import Failure, Result, Success
from ..schemas.parser_like import CNLPSentence, AspectSentence, ExampleSentence, CommandSentence, IOSentence
from ..schemas import ProcessDecision, StopProcess, ContinueProcess
from .sentence_recognizer import SentenceRecognizer
from .reconstructor.cnlp_reconstructor import CNLPReconstructorDefault
from ..config import settings, parser_like_settings

from typing import List


# 检查返回的错误列表是否存在致命错误
def deside_proceed(result_list: List[Result]) -> bool:
    if result_list == None:
        return False

    for result in result_list:
        if isinstance(result, Failure):
            if result.is_fatal is True:
                return True

    return False


# 检查需要Python Dict中是否存在指定的路径，并取出相应的键值
# TODO：进一步确认是否会有指定路径存在但是键值为None的情况发生，如果CNL-P AST_LIKE被生成出来，这种情况是不应该存在的。
def path_exists(data: dict, path: list) -> bool:
    current = data
    for i, key in enumerate(path):
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return False
    return True


class ParserLike:
    # TODO: 统一不同层级的section命名

    def __init__(self):
        self.recognize_funcs_map = {
        "persona": SentenceRecognizer.persona_sentences_recognition,
        "constraints": SentenceRecognizer.constraints_sentences_recognition,
        "worker": SentenceRecognizer.workers_sentences_recognition,
        "concepts": SentenceRecognizer.concepts_sentences_recognition,
        "audience": SentenceRecognizer.audience_sentences_recognition,
        }
        self.default_reconstructor_map = {
            "persona": CNLPReconstructorDefault.reconstruct_persona,
            "constraints": CNLPReconstructorDefault.reconstruct_constraints,
            "worker": CNLPReconstructorDefault.reconstruct_worker,
            "concepts": CNLPReconstructorDefault.reconstruct_concepts,
            "audience": CNLPReconstructorDefault.reconstruct_audience,
        }

    def syntax_analysis(self, cnl_p: str) -> ProcessDecision:

        errors = []

        recognize_result = self.recognize_cnlp_sentence(cnl_p=cnl_p)
        if isinstance(recognize_result, StopProcess):
            return recognize_result

        errors.extend(recognize_result.errors)

        reconstruct_result = self.reconstruct_cnlp_sentence_default(recognize_result.value)
        if isinstance(reconstruct_result, StopProcess):
            reconstruct_result.errors.extend(errors)
            return reconstruct_result

        errors.extend(reconstruct_result.errors)

        # TODO：把对required_fields的检查剥离出来，形成一个单独的函数
        required_fields = parser_like_settings['required_fields']
        for required_field in required_fields:
            if not path_exists(data=reconstruct_result.value, path=required_field):
                missing_required_field_path = ".".join(required_field)
                errors.append(
                    Failure(
                        is_fatal=True if required_field[1] == "main_flow" else False,
                        error_type="",
                        value=None,
                        message=f"Missing required field: {missing_required_field_path}",
                    )
                )

        return ContinueProcess(value=reconstruct_result.value, errors=errors)

    def recognize_cnlp_sentence(self, cnl_p: str) -> ProcessDecision:

        errors = []

        classify_cnlp_sentences_results = SentenceRecognizer.classify_cnlp_sentences(cnl_p=cnl_p)
        cnlp_sentences_classification_dict = classify_cnlp_sentences_results['cnlp_sentences_belonging']


        if deside_proceed(classify_cnlp_sentences_results['error_list']):
            return StopProcess(errors=errors, value=None)
        else:
            errors.extend(classify_cnlp_sentences_results['error_list'])

        # main_section是指"persona", "constraints", "instruction"这些最表层CNL-P 语法结构
        for agent_section_name, agent_section_content in cnlp_sentences_classification_dict.items():
            if agent_section_name == "agent" or f"DEFINE_{agent_section_name.upper()}" in settings.parser_like_settings['ignored_agent_sections']:
                continue
            result = self.recognize_funcs_map[agent_section_name](agent_section_content)
            if deside_proceed(result["error_list"]):
                errors.extend(result["error_list"])
                return StopProcess(errors=errors, value=None, reason="Due to some fatal errors that seriously disrupted the subsequent static analysis, the process was terminated.")
            else:
                errors.extend(result["error_list"])
            cnlp_sentences_classification_dict[agent_section_name] = result["success_list"]

        return ContinueProcess(errors=errors, value=cnlp_sentences_classification_dict)

    def reconstruct_cnlp_sentence_default(self, cnlp_sentence_dict: dict) -> ProcessDecision:

        errors = []
        cnlp_ast_like = {}

        for agent_section_name, sentence_list in cnlp_sentence_dict.items():
            if agent_section_name == "agent" or f"DEFINE_{agent_section_name.upper()}" in settings.parser_like_settings['ignored_agent_sections']:
                continue
            reconstruct_result = self.default_reconstructor_map[agent_section_name](sentence_list)
            if deside_proceed(reconstruct_result['error_list']):
                errors.extend(reconstruct_result['error_list'])
                return StopProcess(errors=errors, value=None, reason="Due to some fatal errors that seriously disrupted the subsequent static analysis, the process was terminated.")
            else:
                errors.extend(reconstruct_result['error_list'])

            cnlp_ast_like[agent_section_name] = reconstruct_result[f'{agent_section_name}_dict']

        return ContinueProcess(errors=errors, value=cnlp_ast_like)

if __name__ == '__main__':
    print("test running...")