from typing import TypedDict, NotRequired, Literal, List, Dict


"""
用来描述CNL-P中某一内容的位置信息
"""
class AspectPosition(TypedDict):
    aspect_type: Literal["role_aspect", "optional_aspect"]


class InstructionPosition(TypedDict):
    instruction_subsection_name: str # Literal["input", "output", "example", "main_flow", "alternative_flow..", "exception_flow.."]
    # when the 'instruction_section_name' is input/output
    is_required: NotRequired[bool]
    # when the 'instruction_section_name' is main_flow/alternative_flow../exception_flow..
    block_order_in_current_flow: NotRequired[int]
    # when the 'block' is start with "if_block"
    branch_count: NotRequired[int]
    # when the 'block' is start with "if_block"
    branch_order: NotRequired[int]
    # when the 'instruction_section_name' is main_flow/alternative_flow../exception_flow..
    command_order_in_current_flow: NotRequired[int]


class PositionDescription(TypedDict):
    # main_section 是指CNL-P Agent中顶级的语法区块，例如Persona，Constraints等等这些都算是main_section
    main_section: str
    position_detailed: InstructionPosition | AspectPosition


"""
用来记录某一个变量的信息
"""
# TODO: 此用法待定
# class VariableDeclaration(TypedDict):
#     starting_declaration_flow: str
#     position: PositionDescription
#
# class VariableDeclaration(TypedDict):
#     flow: str
#     block: str
#     # when the 'block' is if_block
#     total_branch: NotRequired[int]


class HistoryOfVariableValues(TypedDict):
    history_value: NotRequired[any]
    position: PositionDescription


class VariableDescription(TypedDict):
    var_name: str
    # 用来表明该变量是否是当前agent内私有的变量
    is_internal: bool
    # 用来说明设置该变量的意义
    var_explanation: NotRequired[str]
    current_var_value: NotRequired[any]
    # var_type描述的是该变量类型的名字，而没有实际存储变量信息
    var_type: str
    # 用来记录var初始声明的位置:
    # 这里的str必须当前worker中的某一个变量名
    # 当键值的类型为list时，说明该变量的声明位置在if_block中
    var_declarations: NotRequired[Dict[str, List[InstructionPosition] | InstructionPosition]]
    # var_declarations
    history_of_var_values: List[HistoryOfVariableValues]


"""
用来描述某一个接口，这个借口可以是API，可以工作流，可以是某一个Agent
"""
class InterfaceInput(TypedDict):
    pass


class InterfaceReturn(TypedDict):
    pass


class InterfaceDescription(TypedDict):
    interface_name: str
    interface_type: Literal["agent", "work_flow", "function"]
    interface_explanation: NotRequired[str]
    # 记录了该接口需要的输入类型
    interface_input: dict
    interface_source: NotRequired[str]
    interface_return: NotRequired[dict]




    