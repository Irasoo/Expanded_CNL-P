from ....schema.cnlp_types import CNLPTypeToken, TokenTypeOfCNLPTypes, CNLPTypeIR, FieldOfCNLPStructType, CNLPEnumType, CNLPArrayType, CNLPDeclaredType, CNLPSimpleType
from ....schema.result import Success, Failure, Result

from typing import List, Dict
from collections import deque

def list_parse(token_list: List[CNLPTypeToken]) -> Success[CNLPArrayType] | List[Failure]:
    # TODO: 这里使用error_list是因为后续可以继续扩展兼容性
    error_list = []

    # 将是否找到列表中元素的类型作为解析的关键点
    # 找到元素类型之前，无非就是"List"与"["之间交叉出现
    # 找到元素类型之后，无非就是与之前"List", "["等数量的连续"]"
    # 在本因连续的类型声明中，PyCharm IDE也会因为突然错误而中断解析，在遇到问题之后直接抛出报错，不会尝试继续进行兼容解析
    find_element_type: bool = False
    left_bracket_count: int = 0
    right_bracket_count: int = 0
    list_keyword_count: int = 0

    # 对于"List"来说，后面只期待一种类型的Token："["
    # 对于"["来说，后面期三种类型的Token: "List", SIMPLE_TYPE, WORD(实际上就是declared_type_name)
    # 因此需要记录上一个Token的类型,来检验嵌套的"List"声明是否正确
    previous_token_type = None

    # 保存最终解析出的元素类型（简单类型、声明类型或嵌套 List）
    element_type = None

    # 循环将依据变量：find_element_type的状态分为两个解析模式
    for index, token in enumerate(token_list):
        # 当还没有找到列表元素的类型时：
        if not find_element_type:
            if token['token_type'] == TokenTypeOfCNLPTypes.LIST:
                if previous_token_type is None or previous_token_type == TokenTypeOfCNLPTypes.LBRACKET:
                    list_keyword_count += 1
                    previous_token_type = TokenTypeOfCNLPTypes.LIST
                    continue
                else:
                    error_list.append(
                        Failure(
                            value=token['token_value'],
                            start_line=token['start_line'],
                            end_line=token_list[-1]['end_line'],
                            is_fatal=False,
                            error_type="type_definition_error",
                            # TODO: 这里后续还是应该要加上具体列数，否则太抽象了
                            message="Unexpected 'List'. Expected '[' after 'List'."
                        )
                    )
                    return error_list

            if token['token_type'] == TokenTypeOfCNLPTypes.LBRACKET:
                if previous_token_type == TokenTypeOfCNLPTypes.LIST:
                    left_bracket_count += 1
                    previous_token_type = TokenTypeOfCNLPTypes.LBRACKET
                    continue
                else:
                    error_list.append(
                        Failure(
                            value=token['token_value'],
                            start_line=token['start_line'],
                            end_line=token_list[-1]['end_line'],
                            is_fatal=False,
                            error_type="type_definition_error",
                            message="Unexpected '['. '[' must follow 'List'."
                        )
                    )
                    return error_list

            if token['token_type'] in [
                TokenTypeOfCNLPTypes.TEXT,
                TokenTypeOfCNLPTypes.BOOLEAN,
                TokenTypeOfCNLPTypes.NUMBER
            ]:
                # 简单类型作为元素类型
                element_type = CNLPSimpleType(simple_type=token['token_value'])
                find_element_type = True
                continue

            if token['token_type'] == TokenTypeOfCNLPTypes.WORD:
                # 用户自定义的类型
                element_type = CNLPDeclaredType(declared_type_name=token['token_value'])
                find_element_type = True
                continue

            # 这个变量完全就是为了下面的f-string中引用一个新的变量值，因为python 3.11以上不支持嵌套引号...
            token_value = token['token_value']

            error_list.append(
                Failure(
                    value=token_value,
                    start_line=token['start_line'],
                    end_line=token_list[-1]['end_line'],
                    is_fatal=False,
                    error_type="type_definition_error",
                    message=f"Unexpected token: {token_value} while parsing List element type."
                )
            )
            return error_list

        else:
            # 期待连续的右括号“]”
            if token['token_type'] == TokenTypeOfCNLPTypes.RBRACKET:
                right_bracket_count += 1
                previous_token_type = TokenTypeOfCNLPTypes.RBRACKET
                continue

            token_value = token['token_value']

            # 遇到除 "]" 以外的 Token
            error_list.append(
                Failure(
                    value=token_value,
                    start_line=token['start_line'],
                    end_line=token_list[-1]['end_line'],
                    is_fatal=False,
                    error_type="type_definition_error",
                    message=f"Unexpected token: {token_value} after List element type. Only ']' is expected."
                )
            )
            return error_list

    if left_bracket_count != right_bracket_count:
        error_list.append(
            Failure(
                value=None,
                start_line=token_list[0]['start_line'],
                end_line=token_list[-1]['end_line'],
                is_fatal=False,
                error_type="type_definition_error",
                message="Mismatched '[' and ']' count."
            )
        )
        return error_list

    return Success(
        CNLPArrayType(
            type_of_list_element=element_type,
            nesting_level=list_keyword_count,
        )
    )

class CNLPTypeParser:

    def __init__(self):
        # 其实就是记录传入的Token序列的index
        self.token_array_index: int = 0
        # 这个队列存在的意义就是记录当前token的前两个token，一旦遇到“=“，那么前两个Token就很有可能是type_name以及该type的注释
        self.type_name_and_type_comment_queue = deque(maxlen=2)
        # 当不处于类型定义状态时，无限的收集待定Token
        self.pending_tokens_queue = deque()
        self.token_array: List[CNLPTypeToken] = []
        self.total_tokens: int = 0
        # 用来记录parser目前是否处于定义types的状态
        self.is_defining_type: bool = False
        self.error_list = []
        self.cnlp_type_ir_list = []
        self.skip_record_previous_token: bool = False

    # TODO: 这个方法就是用来重置CNLPTypeParser的内部状态的，因为后面用来对CNL-P进行解析的主函数会接收不同的token序列，但CNLPParserLike
    #       实例却仍是一个
    def reset_parser_attrs(self):
        self.token_array_index = 0
        self.type_name_and_type_comment_queue.clear()
        self.pending_tokens_queue.clear()
        self.token_array = []
        self.total_tokens = 0
        self.is_defining_type = False
        self.error_list = []
        self.cnlp_type_ir_list = []
        self.skip_record_previous_token = False

    # 取得上一个token的类型
    # 注意最早一个token的越界情况
    def previous_token_type(self) -> TokenTypeOfCNLPTypes | None:
        if self.token_array_index != 0:
            return self.token_array[self.token_array_index - 1]['token_type']
        else:
            return None

    # 取得下一个token的类型
    # 注意最后一个token的越界情况
    def next_token_type(self) -> TokenTypeOfCNLPTypes | None:
        if self.token_array_index != len(self.token_array) - 1:
            return self.token_array[self.token_array_index + 1]['token_type']
        else:
            return None

    # 取得当前token的类型
    def current_token_type(self) -> TokenTypeOfCNLPTypes | None:
        if self.token_array_index + 1 <= len(self.token_array):
            return self.token_array[self.token_array_index]['token_type']
        else:
            return None

    # 对于self.token_array_index这个类型属性，当开始处理下一个token时，不能只是简单的 +=1，这个函数还应该同步处理type_name_and_type_comment_queue这个队列
    # 另外，当不处于定义Type的状态时，开启一个不设上限的待定token队列
    def index_forward(self): # -> Literal["pass", ""]:
        # TODO: 留意是否会发生越界的情况
        # type_name_and_type_comment_queue当前index对应的token之前的两位token
        self.type_name_and_type_comment_queue.append(self.token_array[self.token_array_index])

        # 当开始了对某一个type的定义时，就不需要再收集待定的token了，此状态下默认所有的token
        if not self.is_defining_type:

            if not self.skip_record_previous_token:
                # 而pending_tokens_queue应该收集当前index对应的token
                self.pending_tokens_queue.append(self.token_array[self.token_array_index])

            else:
                self.skip_record_previous_token = False

        self.token_array_index += 1


        # TODO: index_forward还是应该专注与index的移动与token序列的记录

        # # 不论是否处于类型定义状态，对"="的判断始终处于最高优先级
        # # 如果当Token是等号
        # if not self.equal_trigger():
        #     # 继续等号左侧是否满足类型定义的标准
        #
        # if self.type_name_and_type_comment_queue[-1]['token_type'] == TokenTypeOfCNLPTypes.WORD:

    # # 判断当前token是否为"="
    # def equal_trigger(self) -> bool:
    #     if self.current_token()== TokenTypeOfCNLPTypes.EQUAL:
    #         return True
    #     else:
    #         return False

    def defining_new_type_trigger(self) -> bool:
        # 如果当前token不是”=”，直接返回False代表此时无定义新类型的可能
        if self.current_token_type() != TokenTypeOfCNLPTypes.EQUAL:
            return False

        # TODO: 下面这几行代码可以去掉，只需要在types_parser的主函数：cnlp_type_parse中，在进入循环前，手动前进一位就可以了

        # # 只有为当第一个token（index=0）时，不用做后续判断
        # if len(self.type_name_and_type_comment_queue):
        #     return False

        # 就算当前是"="，也得满足: TYPE_NAME "=" ...，否则继续返回False，同样代表此时无定义新类型的可能
        if self.previous_token_type() != TokenTypeOfCNLPTypes.WORD:
            return False

        # TODO: 运行到这一步，需要开始考虑“=”的右边是否为"["或者"{"了, 后续拓展的时候拓展相应的关键字就可以了
        if self.next_token_type() in [TokenTypeOfCNLPTypes.LBRACKET, TokenTypeOfCNLPTypes.LBRACE]:
            # TODO：设置当前的parser状态：正在定义类型
            self.is_defining_type = True
            return True
        else:
            return False

    # 判断当前token是否为","
    def comma_trigger(self) -> bool:
        if self.token_array[self.token_array_index]['token_type'] == TokenTypeOfCNLPTypes.COMMA:
            return True
        else:
            return False

    def enum_type_parse(self, type_name_token: CNLPTypeToken, type_comment_token: None | CNLPTypeToken = None) -> None:

        enum_elements = []

        # 记录在类型定义的过程中是否遭到了错误
        error_detected: bool = False

        # enum_type(枚举类型)应该是严格遵循 "WORD" | "TEXT" | "BOOLEAN" | "NUMBER" 与 ","交替出现，最终以"]"收尾
        # 所以设置一个状态来记录下一个Token期待的类型，起始类型应该是"WORD" | "TEXT" | "BOOLEAN" | "NUMBER"
        # TODO: 其实遇到错误字符直接报错应该也行？具体的报错手段海有待商榷...
        # 这里要把所有字符串类型的token类型全部囊括其中
        enum_value_type = [
            TokenTypeOfCNLPTypes.TEXT,
            TokenTypeOfCNLPTypes.NUMBER,
            TokenTypeOfCNLPTypes.BOOLEAN,
            TokenTypeOfCNLPTypes.WORD,
            TokenTypeOfCNLPTypes.LIST,
            TokenTypeOfCNLPTypes.OPTIONAL
        ]
        comma_type = [TokenTypeOfCNLPTypes.COMMA]
        # 最开始的状态应该是期待一个枚举值，所以初始状态应该设置成enum_value_type
        expected_token_type_list: List[TokenTypeOfCNLPTypes] = enum_value_type

        # 往后进一位，因为能触发这个函数下一位肯定"["
        self.index_forward()

        while self.token_array_index < self.total_tokens:
            self.index_forward()
            # 如果推进到下一个index后触发了新类型的定义，那么就提前终止当前的类型定义，退出函数并做出相应的错误报告
            if self.defining_new_type_trigger():
                error_detected = False
                self.error_list.append(
                    Failure(
                        value=None,
                        is_fatal=False,
                        start_line=self.token_array[self.token_array_index]['start_line'],
                        end_line=self.token_array[self.token_array_index]['end_line'],
                        error_type="type_definition_error",
                        message=f"Unexpected interruption of enum type definition at line {self.token_array[self.token_array_index]['start_line']}. New type definition '{self.type_name_and_type_comment_queue[-1]['token_value']}' encountered before current type '{type_name_token['token_value']}' is properly closed with the closing bracket "
                    )
                )
                return None

            if self.current_token_type() == TokenTypeOfCNLPTypes.RBRACKET:
                # 如果enum_elements为空且没有检查到错误，说明在定义枚举类型时，从"["后面直接遇到了"]"：
                if len(enum_elements) == 0 and not error_detected:
                    error_detected = True
                    self.error_list.append(
                        Failure(
                            value=None,
                            start_line=self.token_array[self.token_array_index]['start_line'],
                            end_line=self.token_array[self.token_array_index]['end_line'],
                            is_fatal=False,
                            error_type="type_definition_error",
                            message="Empty enum type definition is not allowed.",
                        )
                    )

                if not error_detected:
                    self.cnlp_type_ir_list.append(
                        CNLPTypeIR(
                            type_name=type_name_token['token_value'],
                            type_comment=type_comment_token['token_value'] if type_comment_token else None,
                            type_content=CNLPEnumType(
                                enum_elements=enum_elements,
                            )
                        )
                    )

                self.is_defining_type = False
                self.skip_record_previous_token = True

                return None

            # 查看当前token是否符合预期
            if self.current_token_type() in expected_token_type_list:
                # 先将该token的值加入到枚举的列表里面
                if self.current_token_type() != TokenTypeOfCNLPTypes.COMMA:
                    enum_elements.append(self.token_array[self.token_array_index]["token_value"])
                # 将expected_token_type_list切换至另一个状态
                expected_token_type_list = enum_value_type if expected_token_type_list == comma_type else comma_type

                continue

            # 如果不符合预期，将分为三种情况进行处理：
            # 当为enum_element的类型时，说明上一个也是同样的类型，这个时候就将报错信息设置为"在一个枚举元素之后，期待一个','”
            if self.current_token_type() in enum_value_type:
                error_detected = True
                self.error_list.append(
                    Failure(
                        value=None,
                        start_line=self.token_array[self.token_array_index]['start_line'],
                        end_line=self.token_array[self.token_array_index]['end_line'],
                        error_type="type_definition_error",
                        is_fatal=False,
                        message="Expected ',' after enum element.",
                    )
                )

                continue

            # 当为COMMA类型时,说明上一个也是comma，此时期待一个枚举元素
            if self.current_token_type() == TokenTypeOfCNLPTypes.COMMA:
                error_detected = True
                self.error_list.append(
                    Failure(
                        value=None,
                        start_line=self.token_array[self.token_array_index]['start_line'],
                        end_line=self.token_array[self.token_array_index]['end_line'],
                        error_type="type_definition_error",
                        is_fatal=False,
                        message="Expected enum element after ','.",
                    )
                )

                continue

            # 否则就是遇到完全意料之外的类型
            error_detected = True
            token_value = self.token_array[self.token_array_index]["token_value"]
            self.error_list.append(
                Failure(
                    value=token_value,
                    start_line=self.token_array[self.token_array_index]['start_line'],
                    end_line=self.token_array[self.token_array_index]['end_line'],
                    error_type="type_definition_error",
                    is_fatal=False,
                    message=f"Unexpected token: {token_value} in enum definition.",
                )
            )

        error_detected = True
        self.error_list.append(
            Failure(
                value=None,
                start_line=self.token_array[self.token_array_index - 1]['start_line'],
                end_line=self.token_array[self.token_array_index - 1]['end_line'],
                error_type="type_definition_error",
                is_fatal=False,
                message=f"Incomplete enum type `{type_name_token['token_value']}` definition at line {self.token_array[self.token_array_index - 1]['end_line']}"
            )
        )


    def structured_type_parse(self, type_name_token: CNLPTypeToken, type_comment_token: None | CNLPTypeToken = None) -> None:

        def structured_type_field_parse(token_list: List[CNLPTypeToken]) -> Success | List[Failure]:

            error_list = []

            # TODO：实际上不需要field_name_detected, 但是这里为了方便阅读还是保留？
            field_name_detected: bool = False
            field_name = None

            # TODO：同样为了方便阅读而保留？
            field_comment_detected: bool = False
            field_comment = None

            optional_detected: bool = False

            # 记录下":"的下标，对于每一个field的解析，分为两个部分：
            # 冒号之前用来的内容用于识别字段的名字，注释以及是否为可选字段
            # 冒号之后用来识别字段具体的类型
            # 所以对于任何一个structured_type解析将用两个循环来实现
            # 而区分两个循环重要的节点就是是否遇到了":"
            colon_index: int = -1

            for index, token in enumerate(token_list):

                if token['token_type'] == TokenTypeOfCNLPTypes.COMMENT:
                    # field comment(字段的注释)应该在field name之前出现，否则需要报错
                    if not field_name_detected:
                        # 如果之前还没有遇到过，那么进行记录并且设置相应的状态
                        if not field_comment_detected:
                            field_comment_detected = True
                            field_comment = token['token_value']
                        # 如果之前已经记录到了，就对意料之外的field comment进行报错
                        else:
                            error_list.append(
                                Failure(
                                    value=token['token_value'],
                                    start_line=token['start_line'],
                                    end_line=token['end_line'],
                                    is_fatal=False,
                                    error_type="type_definition_error",
                                    message=f"Unexpected duplicate field comment: {field_comment}."
                                )
                            )
                    else:
                        if not field_comment_detected:
                            field_comment_detected = True
                            field_comment = token['token_value']
                            # 报告错误：field comment不应该出现在field name之后
                            message = f"Field comment: {field_comment} must appear before the field name: {field_name}."
                        else:
                            # 报告错误：field comment不应该出现在field name之后且应该只有一个field comment
                            message = f"Unexpected field comment: {field_comment}. Only one comment is allowed and it must appear before the field name: {field_name}."

                        error_list.append(
                            Failure(
                                value=token['token_value'],
                                start_line=token['start_line'],
                                end_line=token['end_line'],
                                is_fatal=False,
                                error_type="type_definition_error",
                                message=message
                            )
                        )

                elif token['token_type'] == TokenTypeOfCNLPTypes.OPTIONAL:
                    # 同样的，"OPTIONAL"字段也应该在field name之前且仅出现一次
                    if not field_name_detected:
                        # 如果之前还没有遇到过，那么记录并且记录相应的状态
                        if not optional_detected:
                            optional_detected = True
                        # 否则报告错误：“OPTIONAL”应该至多只出现一次，且不应该作为一个字段的名字
                        else:
                            error_list.append(
                                Failure(
                                    value=token['token_value'],
                                    start_line=token['start_line'],
                                    end_line=token['end_line'],
                                    is_fatal=False,
                                    error_type="type_definition_error",
                                    message=f"Unexpected duplicate 'OPTIONAL'."
                                )
                            )
                    else:
                        if not optional_detected:
                            optional_detected = True
                            # 报告关键字“OPTIONAL”应该出现在field name之前
                            message = f"'OPTIONAL' must appear before the field name: {field_name}."
                        else:
                            # 报告关键字"OPTIONAL"应该出现在field name之前且应该最多出现一次
                            message = f"Unexpected 'OPTIONAL'. Only one is allowed and it must appear before the field name: {field_name}."

                        error_list.append(
                            Failure(
                                value=token['token_value'],
                                start_line=token['start_line'],
                                end_line=token['end_line'],
                                is_fatal=False,
                                error_type="type_definition_error",
                                message=message
                            )
                        )

                elif token['token_type'] == TokenTypeOfCNLPTypes.WORD:

                    if not field_name_detected:
                        field_name = token['token_value']
                        field_name_detected = True
                    else:
                        # 报告错误，field_name有且仅能有一个，如果是其他已经声明的类型名称，应该写在":"之后
                        error_list.append(
                            Failure(
                                value=token['token_value'],
                                start_line=token['start_line'],
                                end_line=token['end_line'],
                                is_fatal=False,
                                error_type="type_definition_error",
                                message=f"Unexpected field name: {field_name}. Only one field name is allowed."
                            )
                        )

                elif token['token_type'] in [
                    TokenTypeOfCNLPTypes.TEXT,
                    TokenTypeOfCNLPTypes.BOOLEAN,
                    TokenTypeOfCNLPTypes.NUMBER,
                ]:
                    # Primitive type words are also legal identifiers in field-name
                    # position, e.g. ``number: number``.
                    if not field_name_detected:
                        field_name = token['token_value']
                        field_name_detected = True
                    else:
                        error_list.append(
                            Failure(
                                value=token['token_value'],
                                start_line=token['start_line'],
                                end_line=token['end_line'],
                                is_fatal=False,
                                error_type="type_definition_error",
                                message="Unexpected token before ':'. Only one field name is allowed.",
                            )
                        )

                elif token['token_type'] in [
                    TokenTypeOfCNLPTypes.LIST,
                    TokenTypeOfCNLPTypes.LBRACKET,
                    TokenTypeOfCNLPTypes.RBRACKET,
                ]:
                    error_list.append(
                        Failure(
                            value=token['token_value'],
                            start_line=token['start_line'],
                            end_line=token['end_line'],
                            is_fatal=False,
                            error_type="type_definition_error",
                            message="Unexpected token before ':'. Type syntax must appear after the field name and ':'.",
                        )
                    )

                # 检测到":"终止当前循环，开启下一段循环
                elif token['token_type'] == TokenTypeOfCNLPTypes.COLON:
                    colon_index = index
                    break

                else:
                    # 错误报告：意料之外字符
                    token_value = token['token_value']
                    error_list.append(
                        Failure(
                            value=token_value,
                            start_line=token['start_line'],
                            end_line=token['end_line'],
                            error_type="type_definition_error",
                            is_fatal=False,
                            message=f"Unexpected token: {token_value}."
                        )
                    )

            # 始终没有找到":"，也进行错误报告：应该使用":"分隔字段名称与字段类型
            if colon_index == -1:
                error_list.append(
                    Failure(
                        value=None,
                        start_line=token_list[-1]['start_line'],
                        end_line=token_list[-1]['end_line'],
                        is_fatal=False,
                        error_type="type_definition_error",
                        message="Expected ':' between field name and field type."
                    )
                )
                return error_list

            # 找到了冒号但是是最后一个：
            if colon_index == len(token_list) - 1:
                error_list.append(
                    Failure(
                        value=None,
                        start_line=token_list[-1]['start_line'],
                        end_line=token_list[-1]['end_line'],
                        is_fatal=False,
                        error_type="type_definition_error",
                        # ":"应该是后面是field_type
                        message="Expected field type after ':'."
                    )
                )
                return error_list

            field_of_cnlp_structured_type: FieldOfCNLPStructType | None = None

            for index, token in enumerate(token_list[colon_index + 1:]):
                if token['token_type'] in [TokenTypeOfCNLPTypes.TEXT, TokenTypeOfCNLPTypes.BOOLEAN, TokenTypeOfCNLPTypes.NUMBER]:
                    field_of_cnlp_structured_type = FieldOfCNLPStructType(
                        field_name=field_name,
                        field_comment=field_comment,
                        is_optional=optional_detected,
                        field_content=CNLPSimpleType(
                            simple_type=token['token_value'],
                        )
                    )

                    # 本应该彻底结束字段类型的定义，检查是否完全遍历token list, 如果没有，则对冗余的token(s)进行报错
                    if index < len(token_list[colon_index + 1:]) - 1:
                        error_list.append(
                            Failure(
                                value=" ".join([token['token_value'] for token in token_list[colon_index + index + 1:]]),
                                start_line=token_list[colon_index + index + 1]['start_line'],
                                end_line=token_list[-1]['end_line'],
                                error_type="type_definition_error",
                                is_fatal=False,
                                message=f"Unexpected token(s) after finished field type."
                            )
                        )
                    break

                if token['token_type'] == TokenTypeOfCNLPTypes.WORD:
                    field_of_cnlp_structured_type = FieldOfCNLPStructType(
                        field_name=field_name,
                        field_comment=field_comment,
                        is_optional=optional_detected,
                        field_content=CNLPDeclaredType(
                            declared_type_name=token['token_value'],
                        )
                    )

                    # 本应该彻底结束字段类型的定义，检查是否完全遍历token list, 如果没有，则对冗余的token(s)进行报错
                    if index < len(token_list[colon_index + 1:]) - 1:
                        error_list.append(
                            Failure(
                                value=" ".join([token['token_value'] for token in token_list[colon_index + index + 1:]]),
                                start_line=token_list[colon_index + index + 1]['start_line'],
                                end_line=token_list[-1]['end_line'],
                                error_type="type_definition_error",
                                is_fatal=False,
                                message=f"Unexpected token(s) after finished field type."
                            )
                        )
                    break

                if token['token_type'] == TokenTypeOfCNLPTypes.LIST:
                    list_parse_result = list_parse(token_list=token_list[colon_index + 1 + index:])
                    if isinstance(list_parse_result, Success):
                        field_of_cnlp_structured_type = FieldOfCNLPStructType(
                            field_name=field_name,
                            field_comment=field_comment,
                            is_optional=optional_detected,
                            field_content=list_parse_result.value
                        )
                    else:
                        error_list.extend(list_parse_result)

                    break

                # 报告错误：在定义field的类型时遇到预料之外类型的token
                token_value = token['token_value']
                error_list.append(
                    Failure(
                        value=token_value,
                        start_line=token['start_line'],
                        end_line=token['end_line'],
                        is_fatal=False,
                        error_type="type_definition_error",
                        message=f"Unexpected token: {token_value}."
                    )
                )

            if len(error_list) == 0:
                return Success(field_of_cnlp_structured_type)
            else:
                return error_list

        # 记录解析时是否遇到过错误（不论是否致命）
        error_detected: bool = False
        # 用来组成structured_type字段的待定Token列表
        pending_field_token_list: List[CNLPTypeToken] = []
        # 存储structured_type已有的字段
        field_list: List[FieldOfCNLPStructType] = []
        # 先往后推进一位, 因为能触发这个函数，下一位token肯定是
        self.index_forward()

        while self.token_array_index < self.total_tokens:
            self.index_forward()
            # 如果推进到下一个index后触发了新类型的定义，那么就提前终止当前的类型定义，退出函数并做出相应的错误报告
            if self.defining_new_type_trigger():
                error_detected = True
                self.error_list.append(
                    Failure(
                        value=None,
                        error_type="type_definition_error",
                        is_fatal=False,
                        start_line=self.token_array[self.token_array_index]['start_line'],
                        end_line=self.token_array[self.token_array_index]['end_line'],
                        message=f"Unexpected interruption of structured type definition at line {self.token_array[self.token_array_index]['start_line']}. New type definition '{self.type_name_and_type_comment_queue[-1]['token_value']}' encountered before current type '{type_name_token['token_value']}' is properly closed with the closing bracket "
                    )
                )
                return None

            # 遇到","说明该结构类型的当前字段定义完毕
            if self.comma_trigger():
                # 如果待定的field_token序列为空，说明两个","之间存在空的字段, 可能是空字段或者是多余报错
                if len(pending_field_token_list) == 0:
                    error_detected = True
                    self.error_list.append(
                        Failure(
                            value=None,
                            start_line=self.token_array[self.token_array_index]['start_line'],
                            end_line=self.token_array[self.token_array_index]['end_line'],
                            error_type="type_definition_error",
                            is_fatal=False,
                            # 其实最后使用start_line也一样，没什么差别
                            message=f"Unexpected empty field or trailing comma in type `{type_name_token['token_value']}` definition at line {self.token_array[self.token_array_index]['end_line']}"
                        )
                    )
                    # 空的序列也不需要进行清楚
                    continue

                field_parse_result = structured_type_field_parse(pending_field_token_list)
                pending_field_token_list.clear()
                if isinstance(field_parse_result, Success):
                    field_list.append(field_parse_result.value)
                else:
                    error_detected = True
                    self.error_list.extend(field_parse_result)

                continue

            # 当遇到"}"时，说明要结束
            if self.current_token_type() == TokenTypeOfCNLPTypes.RBRACE:
                # 对于最后一个field来说，如果未以","结尾
                if pending_field_token_list:
                    field_parse_result = structured_type_field_parse(pending_field_token_list)
                    pending_field_token_list.clear()
                    if isinstance(field_parse_result, Success):
                        field_list.append(field_parse_result.value)
                    else:
                        error_detected = True
                        self.error_list.extend(field_parse_result)


                # 检查field_list是否为空，如果field_list为空，且没有探测到错误，说明在"{"之后直接遇到"}"
                if len(field_list) == 0 and not error_detected:
                    error_detected = True
                    self.error_list.append(
                        Failure(
                            value=None,
                            is_fatal=False,
                            start_line=self.token_array[self.token_array_index]['start_line'],
                            end_line=self.token_array[self.token_array_index]['end_line'],
                            error_type="type_definition_error",
                            message="Empty structured type definition is not allowed."
                        )
                    )

                # 如果在整个structured_type的解析过程中没有遇到错误，就添加该类型的IR
                if not error_detected:
                    self.cnlp_type_ir_list.append(
                        CNLPTypeIR(
                            type_name=type_name_token['token_value'],
                            type_comment=type_comment_token['token_value'] if type_comment_token is not None else None,
                            type_content=field_list
                        )
                    )

                # 同时让cnlp_type_parser退出正在定义类型的状态
                self.is_defining_type = False
                self.skip_record_previous_token = True

                return None

            pending_field_token_list.append(self.token_array[self.token_array_index])

        # 对于一个structured type的定义来说，除了因为到了新的类型定义而中断和因为检测“}”而正常结束当前类型定义以外，还有可能是因为
        # 已经遍历完序列中的所有token以后，当前类型定义仍未结束:
        self.error_list.append(
            Failure(
                value=None,
                start_line=self.token_array[self.token_array_index - 1]['start_line'],
                end_line=self.token_array[self.token_array_index - 1]['end_line'],
                is_fatal=False,
                error_type="type_definition_error",
                message=f"Incomplete structured type `{type_name_token['token_value']}` definition at line {self.token_array[self.token_array_index - 1]['end_line']}"
            )
        )

    def cnlp_type_parse(self, token_array: List[CNLPTypeToken]) -> Dict[str, List[Result] | List[CNLPTypeIR]] :
        self.reset_parser_attrs()
        self.token_array = token_array
        self.total_tokens = len(self.token_array)

        while self.token_array_index < self.total_tokens:

            # 当在类型定义时因为检测到新的类型定义而意外退出时，就不讲下标往后推一个，而是直接进入新一轮的类型定义中
            if not self.is_defining_type:
                self.index_forward()

            if not self.defining_new_type_trigger():
                continue

            # 先确定type_name
            type_name_token = self.type_name_and_type_comment_queue[-1]
            # 在存储的token序列中吐出一个token，因为这个token被用做了type_name
            if len(self.pending_tokens_queue) != 0:
                self.pending_tokens_queue.pop()

            type_comment_token = None
            # 再确定type_comment
            # 在此之前需要先确定是不是可能有
            if len(self.type_name_and_type_comment_queue) > 1:
                if self.type_name_and_type_comment_queue[0]['token_type'] == TokenTypeOfCNLPTypes.COMMENT:
                    type_comment_token = self.type_name_and_type_comment_queue[0]
                    # 在存储的token序列中吐出一个token，因为这个token被用做了type_comment
                    if len(self.pending_tokens_queue) != 0:
                        self.pending_tokens_queue.pop()
                else:
                    type_comment_token = None

            # 如果此时收集待定token的序列仍不为空，那么这些token就可以被判断为冗余token
            if len(self.pending_tokens_queue) != 0:
                start_line = self.pending_tokens_queue[0]['start_line']
                end_line = self.pending_tokens_queue[-1]['end_line']

                if start_line != end_line:
                    message = f"Unexpected tokens between type definitions from line {start_line} to line {end_line}."
                else:
                    message = f"Unexpected tokens between type definitions at line {start_line}."

                self.error_list.append(
                    Failure(
                        value=" ".join([token['token_value'] for token in self.pending_tokens_queue]),
                        start_line=self.pending_tokens_queue[0]['start_line'],
                        end_line=self.pending_tokens_queue[-1]['end_line'],
                        error_type="type_definition_error",
                        message=message,
                        is_fatal=False
                    )
                )

                self.pending_tokens_queue.clear()

            if self.next_token_type() == TokenTypeOfCNLPTypes.LBRACKET:
                self.enum_type_parse(type_name_token=type_name_token, type_comment_token=type_comment_token)
            elif self.next_token_type() == TokenTypeOfCNLPTypes.LBRACE:
                self.structured_type_parse(type_name_token=type_name_token, type_comment_token=type_comment_token)

        return {"success_list": self.cnlp_type_ir_list, "error_list": self.error_list}
