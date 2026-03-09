from cnlp_linting_tool.config import settings
from cnlp_linting_tool.schemas.result import Failure, Result, Success
from .aspect_recognizer import recognize_aspect_sentence
from .example_recognizer import recognize_example_sentence
from .command_recognizer import recognize_command_sentence
from .io_recognizer import recognize_input_sentence, recognize_output_sentence

from typing import Dict, List, Literal
import re


# class SentenceRecognizer:
#     # TODO：对”疑似“内容的鉴别需要进一步优化，当然这个都是日后的事情了，具体是指当关键字非常接近标准而存在细微的缺陷时，我们应该将其包裹的内容收集起来进行下一步的分析
#
#     @staticmethod
#     def classify_cnlp_sentences(cnl_p: str) -> Dict[Literal["cnlp_sentences_belonging", "error_list"], Success | List[Failure]]:
#         # TODO: 注意所有的DEFINE、END标识对只应该出现一次。例如DEFINE_PERSONA应该只出现一次，反复的出现也是一种错误。
#         define_pattern = re.compile(r"\[(DEFINE_[A-Z]+):?\s*(.*?)]")
#         end_pattern = re.compile(r"\[END_([A-Z_]+)]$")
#         agent_sections = settings.parser_like_settings['agent_sections']
#
#         cnlp_sentences_belonging = {}
#         error_list = []
#
#         current_agent_section_content = []
#         defining_agent = False
#         current_agent_section = None
#
#         for line in cnl_p.splitlines():
#             line_strip = line.strip()
#             if not line_strip:
#                 continue
#
#             # 识别DEFINE_语句
#             define_match = define_pattern.match(line_strip)
#             # 该语句为DEFINE语句
#             if define_match:
#                 define_keyword = define_match.group(1)
#                 content = define_match.group(2).strip()
#
#
#                 if defining_agent is False:
#                     if define_keyword == "DEFINE_AGENT":
#                         defining_agent = True
#                         cnlp_sentences_belonging['agent'] = content
#                         continue
#
#                 if define_keyword in agent_sections:
#                     if current_agent_section is None:
#                         current_agent_section = define_keyword.replace("DEFINE_", "").lower()
#                         continue
#                     else:
#                         cnlp_sentences_belonging[current_agent_section] = current_agent_section_content
#                         current_agent_section_content = []
#                         current_agent_section = define_keyword.replace("DEFINE_", "").lower()
#                         continue
#
#             # 识别END_语句
#             end_match = end_pattern.match(line_strip)
#             if end_match:
#                 end_keyword = end_match.group(1)
#                 if end_keyword.lower() == current_agent_section:
#                     cnlp_sentences_belonging[current_agent_section] = current_agent_section_content
#                     current_agent_section = None
#                     current_agent_section_content = []
#                 elif end_keyword == "END_AGENT":
#                     defining_agent = False
#                 elif end_keyword != current_agent_section and f"DEFINE_{end_keyword}" not in agent_sections:
#                     current_agent_section_content.append(line_strip)
#                 else:
#                     error_list.append(
#                         Failure(
#                             value=line_strip,
#                             is_fatal=False,
#                             error_type="unrecognized_sentence",
#                             message="the sentence is out of agent"
#                         )
#                     )
#                 continue
#
#             # 判断当前语句是否违法
#             # 首先判断该语句是否在定义Agent内
#             if defining_agent:
#                 if current_agent_section:
#                     current_agent_section_content.append(line_strip)
#                 else:
#                     error_list.append(
#                         Failure(
#                             value=line_strip,
#                             is_fatal=False,
#                             error_type="unrecognized_sentence",
#                             message="the sentence is out of agent"
#                         )
#                     )
#             # 不在DEFINE_AGENT内就直接标记为异常
#             else:
#                 error_list.append(
#                     Failure(
#                         value=line_strip,
#                         is_fatal=False,
#                         error_type="unrecognized_sentence",
#                         message="the sentence is out of agent"
#                     )
#                 )
#                 continue
#
#         return {"cnlp_sentences_belonging": cnlp_sentences_belonging, "error_list": error_list}




class SentenceRecognizer:
    # TODO：对”疑似“内容的鉴别需要进一步优化，当然这个都是日后的事情了，具体是指当关键字非常接近标准而存在细微的缺陷时，我们应该将其包裹的内容收集起来进行下一步的分析





    @staticmethod
    def classify_cnlp_sentences(cnl_p: str) -> Dict[Literal["cnlp_sentences_belonging", "error_list"], Dict[Literal['sentence', 'line_number'], str | int] | List[Failure]]:


        # TODO: 注意所有的DEFINE、END标识对只应该出现一次。例如DEFINE_PERSONA应该只出现一次，反复的出现也是一种错误。
        define_pattern = re.compile(r"\[(DEFINE_[A-Z]+):?\s*(.*?)]")
        end_pattern = re.compile(r"\[END_([A-Z_]+)]$")
        agent_sections = settings.parser_like_settings['agent_sections']

        cnlp_sentences_belonging = {}
        error_list = []

        current_agent_section_content = []
        defining_agent = False
        current_agent_section = None

        # 用来记录最后一行语句的行数，当最后没有"[END_AGENT]"时，程序可以准确定位错误发生的具体原因
        last_line_number: int = 0
        # 用来记录最后一个agent_section开始的行数
        last_agent_section_begin_line: int = 0

        # 注意，此时是line_index, 具体的行数需要+1
        for line_index, line in enumerate(cnl_p.splitlines()):
            line_strip = line.strip()
            if not line_strip:
                continue

            line_number = line_index
            last_line_number = line_number

            # 识别DEFINE_语句
            define_match = define_pattern.match(line_strip)
            if define_match:
                define_keyword = define_match.group(1)
                content = define_match.group(2).strip()

                if defining_agent is False:
                    if define_keyword == "DEFINE_AGENT":
                        defining_agent = True
                        cnlp_sentences_belonging['agent'] = content
                        continue

                if define_keyword in agent_sections:
                    if current_agent_section is None:
                        current_agent_section = define_keyword.replace("DEFINE_", "").lower()
                    else:
                        cnlp_sentences_belonging[current_agent_section] = current_agent_section_content
                        error_list.append(
                            Failure(
                                is_fatal=False,
                                error_type="",
                                value=None,
                                start_line=last_agent_section_begin_line,
                                end_line=line_number,
                                message=f"""'[DEFINE_{current_agent_section}]' should end with '[END_{current_agent_section}]'"""
                            )
                        )

                        current_agent_section_content = []
                        current_agent_section = define_keyword.replace("DEFINE_", "").lower()

                    last_agent_section_begin_line = line_number
                    continue

            # 识别END_语句
            end_match = end_pattern.match(line_strip)
            if end_match:
                end_keyword = end_match.group(1)
                if end_keyword.lower() == current_agent_section:
                    if current_agent_section_content is None:
                        error_list.append(
                            Failure(
                                is_fatal=True if current_agent_section == 'worker' else False,
                                error_type="",
                                value=None,
                                start_line=last_agent_section_begin_line,
                                end_line=line_number,
                                message=f"The {current_agent_section} section is empty."
                            )
                        )
                    cnlp_sentences_belonging[current_agent_section] = current_agent_section_content
                    current_agent_section = None
                    current_agent_section_content = []
                elif end_keyword == "AGENT":
                    defining_agent = False
                elif end_keyword != current_agent_section and f"DEFINE_{end_keyword}" not in agent_sections:
                    current_agent_section_content.append({'sentence': line_strip, 'line_number': line_number})
                elif current_agent_section_content:
                    error_list.append(
                        Failure(
                            value=line_strip,
                            is_fatal=False,
                            error_type="unrecognized_sentence",
                            message=f"'[DEFINE_{current_agent_section.upper()}]' should end with '[END_{current_agent_section.upper()}]', but actually is '[END_{end_keyword}]'",
                            start_line=last_agent_section_begin_line,
                            end_line=line_number,
                        )
                    )
                elif current_agent_section is None:
                    error_list.append(
                        Failure(
                            value=line_strip,
                            is_fatal=True if end_keyword == 'worker' else False,
                            error_type="",
                            start_line=line_number,
                            end_line=line_number,
                            message=f"Here there is only a single end definition sentence: '{line_strip}'"
                        )
                    )
                continue

            # 判断当前语句是否违法
            if defining_agent:
                if current_agent_section:
                    current_agent_section_content.append({'sentence': line_strip, 'line_number': line_number})
                else:
                    error_list.append(
                        Failure(
                            value=line_strip,
                            is_fatal=False,
                            error_type="unrecognized_sentence",
                            message="The sentence should be between '[DEFINE...]' and '[END...]'",
                            start_line=line_number,
                            end_line=line_number,
                        )
                    )
            else:
                error_list.append(
                    Failure(
                        value=line_strip,
                        is_fatal=False,
                        error_type="unrecognized_sentence",
                        message="the sentence is outside of agent definition.",
                        start_line=line_number,
                        end_line=line_number,
                    )
                )
                continue

        if defining_agent:
            error_list.append(
                Failure(
                    value=None,
                    is_fatal=False,
                    error_type="missing_sentence",
                    start_line=last_line_number,
                    end_line=last_line_number,
                    message="""The sentence "[END_AGENT]" is missing."""
                )
            )

        if current_agent_section:
            if current_agent_section_content is None:
                error_list.append(
                    Failure(
                        value=None,
                        is_fatal=True if current_agent_section == 'worker' else False,
                        error_type="missing_sentence",
                        start_line=last_agent_section_begin_line,
                        end_line=last_agent_section_begin_line,
                        message=f"The {current_agent_section} section is missing."
                    )
                )
            else:
                cnlp_sentences_belonging[current_agent_section] = current_agent_section_content
                error_list.append(
                    Failure(
                        is_fatal=False,
                        error_type="",
                        value=None,
                        start_line=last_agent_section_begin_line,
                        end_line=last_agent_section_begin_line,
                        message=f"""'[DEFINE_{current_agent_section.upper()}]' should end with '[END_{current_agent_section.upper()}]'"""
                    )
                )

        return {
            "cnlp_sentences_belonging": cnlp_sentences_belonging,
            "error_list": error_list
        }


    @staticmethod
    def persona_sentences_recognition(persona_sentences: List[dict]) -> Dict[str, List[Result]]:

        success_list = []
        error_list = []

        for sentence in persona_sentences:
            line_number = sentence["line_number"]
            sentence = sentence["sentence"]

            result = recognize_aspect_sentence(cnlp_sentence=sentence, belonging="persona", start_line=line_number, end_line=line_number)
            if isinstance(result, Failure):
                error_list.append(result)
            else:
                success_list.append(result.value)

        return {"success_list": success_list, "error_list": error_list}

    @staticmethod
    def constraints_sentences_recognition(constraints_sentences: List[dict]) -> Dict[str, List[Result]]:

        success_list = []
        error_list = []

        for sentence in constraints_sentences:
            line_number = sentence["line_number"]
            sentence = sentence["sentence"]
            result = recognize_aspect_sentence(cnlp_sentence=sentence, belonging="constraints", start_line=line_number, end_line=line_number)
            if isinstance(result, Failure):
                error_list.append(result)
            else:
                success_list.append(result.value)

        return {"success_list": success_list, "error_list": error_list}



    @staticmethod
    def concepts_sentences_recognition(constraints_sentences: List[dict]) -> Dict[str, List[Result]]:

        success_list = []
        error_list = []

        for sentence in constraints_sentences:
            line_number = sentence["line_number"]
            sentence = sentence["sentence"]
            result = recognize_aspect_sentence(cnlp_sentence=sentence, belonging="concepts", start_line=line_number, end_line=line_number)
            if isinstance(result, Failure):
                error_list.append(result)
            else:
                success_list.append(result.value)

        return {"success_list": success_list, "error_list": error_list}

    @staticmethod
    def audience_sentences_recognition(constraints_sentences: List[dict]) -> Dict[str, List[Result]]:

        success_list = []
        error_list = []

        for sentence in constraints_sentences:
            line_number = sentence["line_number"]
            sentence = sentence["sentence"]
            result = recognize_aspect_sentence(cnlp_sentence=sentence, belonging="audience", start_line=line_number, end_line=line_number)
            if isinstance(result, Failure):
                error_list.append(result)
            else:
                success_list.append(result.value)

        return {"success_list": success_list, "error_list": error_list}

    @staticmethod
    def types_sentences_recognition(types_sentences: List[str]) -> List[Result]:
        result_list = []
        pass

    @staticmethod
    def workers_sentences_recognition(worker_sentences: List[dict]) -> Dict[str, List[Result]]:
        # TODO:
        #  if_block的匹配模式需要进一步细化
        #  while_block的匹配模式需要进一步细化
        #  使用match或者fullmatch或许并不是一个好的选择，也许应该使用search：应该要处理换行问题
        #  后续应该考虑将识别内容和识别器的设置加入config中
        #  identifiers中的内容应该还是要通过正则表达式来实现（不能只是简单的字符串匹配判断），依靠精确匹配和非精确匹配能够实现更灵活的判断
        # inputs_pattern = re.compile(r"^\[INPUTS\]$")
        # output_pattern = re.compile(r"^\[OUTPUTS\]$")
        # main_flow_pattern = re.compile(r"^\[MAIN_FLOW\]$")
        # example_pattern = re.compile(r"^\[EXAMPLES\]$")
        # sequential_block_pattern = re.compile(r"^\[SEQUENTIAL_BLOCK\]$")
        # if_block_pattern = re.compile(r"^\[IF")
        # while_block_pattern = re.compile(r"^\[WHILE")
        #
        # end_pattern = re.compile(r"\[END_([A-Z]+)]$")
        #
        # for sentence in workers_sentences:
        #     pass

        # worker_section_patterns = [
        #     {"type": "input", "start": "[(INPUTS)]", "end": "[END_INPUTS]"},
        #     {"type": "output", "start": "[(OUTPUTS)]", "end": "[END_OUTPUTS]"},
        #     {"type": "examples", "start": "[(EXAMPLES)]", "end": "[END_EXAMPLES]"},
        #     {"type": "main_flow","start": "[(MAIN_FLOW)]", "end": "[END_MAIN_FLOW]"},
        #     {"type": "alternative_flow","start": "[(ALTERNATIVE_FLOW) (condition)]", "end": "[END_ALTERNATIVE_FLOW]"},
        # ]

        # worker中各个section的匹配模式与对应的类型
        worker_section_patterns = {
            "inputs": re.compile(r"^\s*\[INPUTS\]\s*$"),
            "outputs": re.compile(r"^\s*\[OUTPUTS\]\s*$"),
            "examples": re.compile(r"^\s*\[EXAMPLES\]\s*$"),
            "main_flow": re.compile(r"^\s*\[MAIN_FLOW\]\s*$"),
            "alternative_flow": re.compile(r"^\s*\[ALTERNATIVE_FLOW\s*(.+?)\]\s*$"),
            "exception_flow": re.compile(r"^\s*\[EXCEPTION_FLOW\s*(.+?)\]\s*$"),
        }

        # 定义识别器索引字典：用于随时
        # 该索引字典的每个键值对的键名即为上方识别符的类型
        worker_sentence_recognizers_index_map = {
            "inputs": recognize_input_sentence,
            "outputs": recognize_output_sentence,
            "examples": recognize_example_sentence,
            "main_flow": recognize_command_sentence,
            "alternative_flow": recognize_command_sentence,
            "exception_flow": recognize_command_sentence,
        }

        # 计数每种flow出现的次数，以此进行编号
        flow_counters = {
            "main_flow": 0,
            "alternative_flow": 0,
            "exception_flow": 0,
        }

        end_pattern = re.compile(r"\[END_([A-Z_]+)]$")

        success_list = []
        error_list = []

        # 当前正在定义的section，即当遇到某个start_identifier时，就会从None值赋值为对应section的字符
        current_worker_section = None
        # condition是指alternative_flow或者exception_flow的condition，如果没有则设置为None或者保持为None
        condition = None
        # 当前section内积累的内容
        current_worker_section_content = []
        # 这个变量: worker_section_begin_match很重要，如果匹配到了某一个section的开头，那么就应该设置True，用来后续跳过
        worker_section_begin_match = False
        # worker中可能存在worker_section: 注意，每一个worker_section都需要小写，在settings中，这一部分为大写，因此需要通过.lower()方法转换为小写
        worker_sections = [worker_section.lower() for worker_section in settings.parser_like_settings['worker_sections']]
        # 用来记住每一个flow_condition的行数
        flow_condition_line: int | None = None
        # TODO: 用来检查是否为空的FLOW
        flow_has_block = False
        #记录最后一个worker_section开始的行数
        last_section_start_line = 0

        for sentence in worker_sentences:

            line_number = sentence["line_number"]
            sentence = sentence["sentence"]

            # 查看当前语句是否为section定义开始的标识符
            # TODO：应该先首先识别是否以"["开头, 其他处应该也以类似的方式进行改进，但是这里也要警惕Example中过于“自由”的复杂表达
            if sentence.startswith("["):
                # 特殊的开头，再开始检测是否为开始或者终止符
                for worker_section_type, pattern in worker_section_patterns.items():
                    # 如果匹配结果为“是”
                    worker_section_begin_match = pattern.match(sentence)
                    if worker_section_begin_match:
                        # 查看当前是否处于其他section，如果处于该状态，则可能是上一个worker中的某个section没有正确的关闭
                        if current_worker_section:
                            error_list.append(
                                Failure(
                                    value=None,
                                    is_fatal=False,
                                    start_line=last_section_start_line,
                                    end_line=line_number,
                                    error_type="identifier_error",
                                    message=f"The current section: {current_worker_section} does not seem to have been terminated correctly with '[END...]'."
                                )
                            )
                            current_worker_section_content = []
                        # 更换当前的section
                        current_worker_section = worker_section_type
                        last_section_start_line = line_number
                        # 如果是flow类型，那么需要进行额外计数
                        if worker_section_type in flow_counters.keys():
                            flow_has_block = False
                            flow_condition_line = line_number
                            flow_counters[worker_section_type] += 1
                            # 用来在main_flow数量超过一个时进行报错
                            if flow_counters['main_flow'] > 1 and worker_section_type == 'main_flow':
                                main_flow_number = flow_counters['main_flow']
                                if main_flow_number == 2:
                                    ordinal_suffix = 'nd'
                                elif main_flow_number == 3:
                                    ordinal_suffix = 'rd'
                                else:
                                    ordinal_suffix = 'th'

                                error_list.append(
                                    Failure(
                                        value=sentence,
                                        is_fatal=True,
                                        error_type="",  # TODO: 此处错误类型待定，需要修改Failure的TypedDict类型定义
                                        message=f"There can only be and must be one MAIN_FLOW in the worker, but in fact this is the {main_flow_number}{ordinal_suffix} MIAN_FLOW.",
                                        start_line=line_number,
                                        end_line=line_number
                                    )
                                )
                        # 如果捕获组中存在condition相关的内容，则会被进行捕获，否则为None
                        condition = worker_section_begin_match.group(1) if worker_section_begin_match.lastindex else None
                        worker_section_begin_match = True
                        break

                # 当为“[”开头且为可以识别的模式时，就跳过当前循环
                if worker_section_begin_match:
                    # 跳过后重新设置为False
                    worker_section_begin_match = False
                    continue

                worker_section_end_match = end_pattern.match(sentence)
                if worker_section_end_match:
                    # 提取相关的关键字
                    worker_section_end_match_keyword = worker_section_end_match.group(1).lower()
                    # 如果当前正属于某个worker_section的内容
                    if current_worker_section:
                        # 通过判断终止符的内容与当前的section是否匹配
                        if worker_section_end_match_keyword == current_worker_section:
                            result = worker_sentence_recognizers_index_map[current_worker_section](
                                    cnlp_sentences=current_worker_section_content,
                                    belonging="instruction",
                                    flow=f"{current_worker_section}{flow_counters[current_worker_section]}" if "flow" in current_worker_section else None,
                                    flow_condition=condition,
                                    flow_condition_line = flow_condition_line
                            )
                            for i in result["success_list"]:
                                success_list.append(i.value)
                            error_list.extend(result["error_list"])
                            current_worker_section = None
                            condition = None
                            current_worker_section_content = []
                            continue
                        elif worker_section_end_match_keyword not in worker_sections:
                            current_worker_section_content.append({"line_number": line_number, "sentence": sentence})
                            continue
                        # 如果终止符与当前内容并不匹配，那么记录该错误，且并不关闭当前section的
                        else:
                            error_list.append(
                                Failure(
                                    value=sentence,
                                    is_fatal=False,
                                    error_type="identifier_error",
                                    message=f"The current section: {current_worker_section} did not match the correct terminator: {sentence}",
                                    start_line=line_number,
                                    end_line=line_number
                                )
                            )
                            continue

            # 当确定了既不是开始定义的标识，也不是结束定义的标识以后，就开始判断为一般的语句, 并开始
            if current_worker_section:
                current_worker_section_content.append({"line_number": line_number, "sentence": sentence})
            else:
                error_list.append(
                    Failure(
                        value=sentence,
                        is_fatal=False,
                        error_type="unrecognized_sentence",
                        message=f"The sentence: {sentence} does not belong to any section in the worker.",
                        start_line=line_number,
                        end_line=line_number
                    )
                )

        if current_worker_section:
            if current_worker_section_content:
                result = worker_sentence_recognizers_index_map[current_worker_section](
                    cnlp_sentences=current_worker_section_content,
                    belonging="instruction",
                    flow=f"{current_worker_section}{flow_counters[current_worker_section]}" if "flow" in current_worker_section else None,
                    flow_condition=condition,
                    flow_condition_line=flow_condition_line
                )
                for i in result["success_list"]:
                    success_list.append(i.value)
                error_list.extend(result["error_list"])
            error_list.append(
                Failure(
                    value=None,
                    is_fatal=True,
                    error_type="identifier_error",
                    message=f"The current section: {current_worker_section} does not end with '[END...]'",
                    start_line=last_section_start_line,
                    end_line=last_section_start_line
                )
            )

        return {"success_list": success_list, "error_list": error_list}


        # for identifier in identifiers:
        #     current_type = identifier["type"]
        #     is_matching = False
        #     for sentence in worker_sentences:
        #         current_sentences = []
        #         if is_matching is False:
        #             if sentence == identifier["start"]:
        #                 is_matching = True
        #                 continue
        #         else:
        #             if sentence == identifier["end"]:
        #                 is_matching = False
        #                 result_list.append(worker_sentence_recognizers_index_map[current_type](cnlp_sentence=sentence, belonging="instruction"))
        #                 continue
        #             else:
        #                 current_sentences.append(sentence)
        #                 continue


