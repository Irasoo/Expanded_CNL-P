from typing import List, Dict

from .reconstruct_pattern.default_pattern_with_checking import reconstruct_reference, reconstruct_description_with_reference, reconstruct_command, reconstruct_example
from .judge_sentence_type import judge_sentence_type
from ...schemas.result import Success, Failure, Result
from ...schemas.parser_like import CNLPSentence, CommandSentence, IOSentence, ExampleSentence, IntermediateSentence, AspectSentence
from ...schemas.process_decision import ContinueProcess, StopProcess, ProcessDecision


class CNLPReconstructorDefault:

    __slots__ = (
        # 不太确定这个是否需要编号
        "reference_oder"
    )

    def __init__(self):
        pass

    # 不需要分类，这应该是在上一个阶段就完成的工作，即sentence_recognizer阶段应该直接返回好一个字典
    @staticmethod
    def classify_cnlp_sentence(cnlp_sentences: List[CNLPSentence]):
        pass

    @staticmethod
    def reconstruct_persona(cnlp_sentences: List[CNLPSentence]) -> Dict[str, List[Result]]:

        persona_dict = {}
        error_list = []

        for cnlp_sentence in cnlp_sentences:

            reconstruct_result = reconstruct_description_with_reference(cnlp_sentence)
            if isinstance(reconstruct_result, Failure):
                reconstruct_result.start_line = cnlp_sentence['line_record']['start_line']
                reconstruct_result.end_line = cnlp_sentence['line_record']['end_line']
                error_list.append(reconstruct_result)

                persona_dict[cnlp_sentence['details']['aspect_name']] = reconstruct_result.message
                continue

            persona_dict[cnlp_sentence['details']['aspect_name']] = reconstruct_result.value

        return {"persona_dict": persona_dict, "error_list": error_list}

    @staticmethod
    def reconstruct_constraints(cnlp_sentences: List[CNLPSentence]) -> Dict[str, List[Result]]:

        constraints_dict = {}
        error_list = []

        for cnlp_sentence in cnlp_sentences:

            reconstruct_result = reconstruct_description_with_reference(cnlp_sentence)
            if isinstance(reconstruct_result, Failure):
                reconstruct_result.start_line = cnlp_sentence['line_record']['start_line']
                reconstruct_result.end_line = cnlp_sentence['line_record']['end_line']
                error_list.append(reconstruct_result)
                constraints_dict[cnlp_sentence['details']['aspect_name']] = reconstruct_result.message
                continue

            constraints_dict[cnlp_sentence['details']['aspect_name']] = reconstruct_result.value

        return {"constraints_dict": constraints_dict, "error_list": error_list}

    @staticmethod
    def reconstruct_concepts(cnlp_sentences: List[CNLPSentence]) -> Dict[str, List[Result]]:

        constraints_dict = {}
        error_list = []

        for cnlp_sentence in cnlp_sentences:

            reconstruct_result = reconstruct_description_with_reference(cnlp_sentence)
            if isinstance(reconstruct_result, Failure):
                reconstruct_result.start_line = cnlp_sentence['line_record']['start_line']
                reconstruct_result.end_line = cnlp_sentence['line_record']['end_line']
                error_list.append(reconstruct_result)
                constraints_dict[cnlp_sentence['details']['aspect_name']] = reconstruct_result.message
                continue

            constraints_dict[cnlp_sentence['details']['aspect_name']] = reconstruct_result.value

        return {"concepts_dict": constraints_dict, "error_list": error_list}

    @staticmethod
    def reconstruct_audience(cnlp_sentences: List[CNLPSentence]) -> Dict[str, List[Result]]:

        constraints_dict = {}
        error_list = []

        for cnlp_sentence in cnlp_sentences:

            reconstruct_result = reconstruct_description_with_reference(cnlp_sentence)
            if isinstance(reconstruct_result, Failure):
                reconstruct_result.start_line = cnlp_sentence['line_record']['start_line']
                reconstruct_result.end_line = cnlp_sentence['line_record']['end_line']
                error_list.append(reconstruct_result)
                constraints_dict[cnlp_sentence['details']['aspect_name']] = reconstruct_result.message
                continue

            constraints_dict[cnlp_sentence['details']['aspect_name']] = reconstruct_result.value

        return {"audience_dict": constraints_dict, "error_list": error_list}

    @staticmethod
    def reconstruct_worker(cnlp_sentences: List[CNLPSentence]) -> Dict[str, List[Result]]:
        # TODO: 是应该先把所有的句子分好类再统一构建CNL_P字典，还是一边识别句子种类然后每识别一个后再加入到逐渐构建的字典中

        def build_input_dict(input_reference_index: int, worker_dict: dict, reconstruct_result: Success, cnlp_sentence: CNLPSentence, *args, **kwargs):
            input_dict = worker_dict.setdefault('input', {})
            input_dict[f'reference{input_reference_index}'] = reconstruct_result.value
            input_dict[f'reference{input_reference_index}']['is_required'] = cnlp_sentence['details']['is_required']
            input_reference_index += 1
            return None

        def build_output_dict(output_reference_index: int, worker_dict: dict, reconstruct_result: Success, cnlp_sentence: CNLPSentence, *args, **kwargs):
            output_dict = worker_dict.setdefault('output', {})
            output_dict[f'reference{output_reference_index}'] = reconstruct_result.value
            output_dict[f'reference{output_reference_index}']['is_required'] = cnlp_sentence['details']['is_required']
            output_reference_index += 1
            return None

        # def build_command_dict(worker_dict: dict, reconstruct_result: Success, cnlp_sentence: CNLPSentence, if_branch_index: int, *args, **kwargs) -> List[Failure] | None:
        #     flow = cnlp_sentence['details']['flow']
        #     block = cnlp_sentence['details']['block']
        #     flow_condition = cnlp_sentence['details']['flow_condition']
        #     if_condition = cnlp_sentence['details']['if_condition']
        #     loop_condition = cnlp_sentence['details']['loop_condition']
        #     order = cnlp_sentence['details'].get('order', 0)
        #
        #     errors: list[Failure] = []
        #
        #     flow_dict = worker_dict.setdefault(flow, {})
        #     block_dict = flow_dict.setdefault(block, {})
        #
        #     # flow-level condition
        #     if flow_condition:
        #         if 'condition' not in flow_dict:
        #             flow_res = reconstruct_description_with_reference(
        #                 CNLPSentence(belonging="instruction", details=IntermediateSentence(sentence=flow_condition))
        #             )
        #             if isinstance(flow_res, Failure):
        #                 flow_res.start_line = cnlp_sentence['details']['flow_condition_line']
        #                 flow_res.end_line = cnlp_sentence['details']['flow_condition_line']
        #                 errors.append(flow_res)
        #                 flow_dict['condition'] = flow_res.message
        #             else:
        #                 flow_dict['condition'] = flow_res.value
        #         # elif flow_dict.get('condition') != flow_condition:
        #         #     # 如果新来的 flow_condition 与已有的不同，说明冲突，应该报错
        #         #     errors.append(
        #         #         Failure(
        #         #             value=flow_condition,
        #         #             start_line=cnlp_sentence['details']['flow_condition_line'],
        #         #             end_line=cnlp_sentence['details']['flow_condition_line'],
        #         #             is_fatal=True,
        #         #             error_type="flow_conflict",
        #         #             message=f"Conflicting flow-level condition found in flow '{flow}'"
        #         #         )
        #         #     )
        #
        #     if block.startswith('if'):
        #         if if_condition is None:
        #             # else branch
        #             else_branch = block_dict.setdefault('else_branch', {})
        #             else_branch[f'command{order}'] = reconstruct_result.value
        #         else:
        #             # 尝试在已有分支中查找匹配条件
        #             successfully_find_target_branch: bool = False
        #             for branch_name, branch_dict in block_dict.items():
        #                 if isinstance(branch_dict, dict) and 'condition' in branch_dict:
        #                     if branch_dict['condition']['original'] == if_condition:
        #                         branch_dict[f'command{order}'] = reconstruct_result.value
        #                         successfully_find_target_branch = True
        #                         break
        #
        #             if not successfully_find_target_branch:
        #                 # 构建新的 if_branch
        #                 block_res = reconstruct_description_with_reference(
        #                     CNLPSentence(belonging="instruction", details=IntermediateSentence(sentence=if_condition))
        #                 )
        #
        #                 branch_key = f'if_branch{if_branch_index}'
        #                 branch_dict = block_dict.setdefault(branch_key, {})
        #                 if isinstance(block_res, Failure):
        #                     block_res.start_line = cnlp_sentence['details']['block_condition_line']
        #                     block_res.end_line = cnlp_sentence['details']['block_condition_line']
        #                     errors.append(block_res)
        #                     branch_dict['condition'] = {}
        #                 else:
        #                     branch_dict['condition'] = block_res.value
        #                 branch_dict['condition']['original'] = if_condition
        #
        #                 branch_dict[f'command{order}'] = reconstruct_result.value
        #                 # 注意：函数外部要确保 if_branch_index 递增，否则 index 重复
        #                 if_branch_index += 1
        #     elif loop_condition:
        #         if 'condition' not in block_dict:
        #             block_res = reconstruct_description_with_reference(
        #                 CNLPSentence(belonging="instruction", details=IntermediateSentence(sentence=loop_condition))
        #             )
        #             if isinstance(block_res, Failure):
        #                 block_res.start_line = cnlp_sentence['details']['block_condition_line']
        #                 block_res.end_line = cnlp_sentence['details']['block_condition_line']
        #                 errors.append(block_res)
        #                 block_dict['condition'] = block_res.message
        #             else:
        #                 block_dict['condition'] = block_res.value
        #
        #         block_dict[f'command{order}'] = reconstruct_result.value
        #     else:
        #         # 普通 block（如 sequential）
        #         block_dict[f'command{order}'] = reconstruct_result.value
        #
        #     return errors if errors else None

        def build_command_dict(
                worker_dict: dict,
                reconstruct_result: Success,
                cnlp_sentence: CNLPSentence,
                *args, **kwargs
        ) -> List[Failure] | None:
            flow = cnlp_sentence['details']['flow']
            block = cnlp_sentence['details']['block']
            flow_condition = cnlp_sentence['details']['flow_condition']
            flow_condition_line = cnlp_sentence['details']['flow_condition_line']
            flow_log = cnlp_sentence['details']['flow_log']
            flow_log_line = cnlp_sentence['details']['flow_log_line']
            if_condition = cnlp_sentence['details']['if_condition']
            loop_condition = cnlp_sentence['details']['loop_condition']
            order = cnlp_sentence['details'].get('order', 0)
            block_condition_line = cnlp_sentence['details']['block_condition_line']

            errors: list[Failure] = []

            flow_dict = worker_dict.setdefault(flow, {})
            block_dict = flow_dict.setdefault(block, {})

            # flow-level condition
            if flow_condition:
                if 'condition' not in flow_dict:
                    # 对于所有FLOW都要初始化CONDITION
                    flow_res = reconstruct_description_with_reference(
                        CNLPSentence(belonging="instruction", details=IntermediateSentence(sentence=flow_condition))
                    )
                    if isinstance(flow_res, Failure):
                        flow_res.start_line = flow_condition_line
                        flow_res.end_line = flow_condition_line
                        errors.append(flow_res)
                        flow_dict['condition'] = flow_res.message
                    else:
                        flow_dict['condition'] = flow_res.value
                    # 如果是EXCEPTION_FLOW, 还要额外初始化LOG
                    if flow.startswith('exception'):
                        log_result = reconstruct_description_with_reference(
                            CNLPSentence(belonging="instruction", details=IntermediateSentence(sentence=flow_log))
                        )
                        if isinstance(log_result, Failure):
                            log_result.start_line = flow_log_line
                            log_result.end_line = flow_log_line
                            errors.append(log_result)
                            flow_dict['log'] = log_result.message
                        else:
                            flow_dict['log'] = log_result.value

            if block.startswith('if'):
                if if_condition is None:
                    # else branch
                    else_branch = block_dict.setdefault('else_branch', {})
                    else_branch[f'command{order}'] = reconstruct_result.value
                else:
                    # 尝试匹配已有 branch
                    matched = False
                    for branch_name, branch_dict in block_dict.items():
                        if isinstance(branch_dict, dict) and 'condition' in branch_dict:
                            if branch_dict['condition'].get('original') == if_condition:
                                branch_dict[f'command{order}'] = reconstruct_result.value
                                matched = True
                                break

                    if not matched:
                        block_res = reconstruct_description_with_reference(
                            CNLPSentence(belonging="instruction", details=IntermediateSentence(sentence=if_condition))
                        )

                        # === 自动生成 if_branchX 名称 ===
                        existing_indices = [
                            int(k.removeprefix("if_branch"))
                            for k in block_dict.keys()
                            if k.startswith("if_branch") and k.removeprefix("if_branch").isdigit()
                        ]
                        next_index = max(existing_indices, default=0) + 1
                        branch_key = f'if_branch{next_index}'

                        branch_dict = block_dict.setdefault(branch_key, {})
                        if isinstance(block_res, Failure):
                            block_res.start_line = block_condition_line
                            block_res.end_line = block_condition_line
                            errors.append(block_res)
                            branch_dict['condition'] = {}
                        else:
                            branch_dict['condition'] = block_res.value
                        branch_dict['condition']['original'] = if_condition
                        branch_dict[f'command{order}'] = reconstruct_result.value

            elif loop_condition:
                if 'condition' not in block_dict:
                    block_res = reconstruct_description_with_reference(
                        CNLPSentence(belonging="instruction", details=IntermediateSentence(sentence=loop_condition))
                    )
                    if isinstance(block_res, Failure):
                        block_res.start_line = cnlp_sentence['details']['block_condition_line']
                        block_res.end_line = cnlp_sentence['details']['block_condition_line']
                        errors.append(block_res)
                        block_dict['condition'] = block_res.message
                    else:
                        block_dict['condition'] = block_res.value

                block_dict[f'command{order}'] = reconstruct_result.value
            else:
                # 普通 block（如 sequential）
                block_dict[f'command{order}'] = reconstruct_result.value

            return errors if errors else None

        def build_example_dict(worker_dict: dict, reconstruct_result: Success, cnlp_sentence: CNLPSentence, *args, **kwargs):
            example_dict = worker_dict.setdefault('example', {})
            example_type = cnlp_sentence['details']['example_type']
            order = cnlp_sentence['details']['order']
            example_dict[f'{example_type}_worker_behavior{order}'] = reconstruct_result.value


        worker_dict = {}
        error_list = []

        # 用于计数input与output中reference
        input_reference_index: int = 1
        output_reference_index: int = 1
        if_branch_index: int = 1

        reconstruct_worker_sentence_func_map = {
            "INPUT": reconstruct_reference,
            "OUTPUT": reconstruct_reference,
            "COMMAND": reconstruct_command,
            "EXAMPLE": reconstruct_example
        }

        build_worker_dict_func_map = {
            "INPUT": build_input_dict,
            "OUTPUT": build_output_dict,
            "COMMAND": build_command_dict,
            "EXAMPLE": build_example_dict,
        }

        for cnlp_sentence in cnlp_sentences:

            sentence_type = judge_sentence_type(cnlp_sentence['details'])
            if sentence_type == "UnKnow":
                raise RuntimeError(f"The sentence：{cnlp_sentence}\nPlease upgrade the version of sentence_reconstructor to the same level as sentence_recognizer. There is type of CNL-P sentence that can be recognized by sentence_recognizer but not by sentence_reconstructor")

            reconstruct_result = reconstruct_worker_sentence_func_map[sentence_type](cnlp_sentence)
            if isinstance(reconstruct_result, Failure):
                reconstruct_result.start_line = cnlp_sentence['line_record']['start_line']
                reconstruct_result.end_line = cnlp_sentence['line_record']['end_line']
                error_list.append(reconstruct_result)
            else:
                build_result = build_worker_dict_func_map[sentence_type](
                    worker_dict=worker_dict,
                    reconstruct_result=reconstruct_result,
                    cnlp_sentence=cnlp_sentence,
                    input_reference_index=input_reference_index,
                    output_reference_index=output_reference_index,
                    if_branch_index=if_branch_index,
                )
                if build_result is not None:
                    error_list.extend(build_result)
                    
        return {"worker_dict": worker_dict, "error_list": error_list}



