"""Active prompt templates used by the current CNL-P compiler."""

MAIN_IMPLEMENTATION_PROMPT = """【任务背景】

你正在执行 CNL-P 编译器 Native Python 实现的最后一个代码生成阶段。
schema.py、config.py、model.py、utils.py、commands.py 和 predicates.py
都已经生成。你当前只负责生成 main.py，把现有 Command 与 Predicate 函数
按照 Worker Flow 编排起来，不得重新实现任何 Command 或 Predicate。

【三类输入各自负责什么】

1. Workflow Structure 是每个 Flow 内部结构的唯一权威来源。它已经由
   NodeVisitor 从 AST 机械提取，描述 Command 顺序、If 分支顺序、While/For
   循环体、Decision 编号以及 Predicate 路径。不得从 CNL-P 文本重新猜测结构。
2. Flow Binding Table 是不同 Flow 之间跳转关系的唯一权威来源。它描述
   Alternative/Exception Flow 在哪些 Main Flow Command 执行后触发，以及
   Alternative Flow 完成后回到哪个 Command 或 Decision。
3. CNL-P 原文只补充名称和语义背景。如果它与以上结构化输入不一致，以结构化
   输入为准。

Command Function Names 和 Predicate Naming Table 是已经生成的真实函数名。
main.py 只能调用表中存在的函数。

【Workflow Structure 字段】

- main_flow：程序开始执行的唯一 Main Flow。
- alternative_flows：按 CNL-P 声明顺序排列的 Alternative Flow。
- exception_flows：按 CNL-P 声明顺序排列的 Exception Flow。
- flow_path：一个 Flow 的完整结构路径。
- steps：Flow 或 Branch 内按执行顺序排列的步骤。
- step_type="command"：调用 command_name 指定的 Command 函数。
- step_type="if"：一个独立 Decision，按 branches 顺序判断。
- branch_type="if"/"elseif"：调用 predicate_path 对应的 Predicate。
- branch_type="else"：没有 Predicate，只在前面的判断均为假时进入。
- step_type="while"/"for"：一个独立 Decision；调用 predicate_path 对应的
  Predicate，True 进入 body_steps，False 离开循环。当前 Native 运行接口把
  While 和 For 都编译成 Predicate 驱动的循环控制节点。
- decision_index：Flow Binder 的 go_back_to 可以引用的 Decision 编号。

Predicate Naming Table 的键是点号连接的完整 predicate_path。例如：

worker.main_flow.if_block1.if_branch1

对应值才是应当调用的 Predicate 函数名。一个 If Decision 可以依次调用多个
Predicate；Decision 本身不是 Predicate，也不是 Command。

【Flow Binding Table 字段】

- trigger_is：只指向 Main Flow Command。指定 Command 执行完成后，必须检查
  对应 Flow 的 Predicate。
- go_back_to.index_type="command"：Alternative Flow 完成后，从指定 Main
  Flow Command 重新执行。
- go_back_to.index_type="decision"：Alternative Flow 完成后，回到整个
  Decision 控制节点。If 必须从第一个 if branch 开始重新判断；While/For
  必须重新判断循环 Predicate。不得直接跳到某一个 branch。
- Exception Flow 没有 go_back_to，执行完成后直接结束整个 Worker。
- Alternative/Exception Flow 只能由 Main Flow Command 触发；它们内部的
  Command 不再触发其他 Flow。

同一个 Main Flow Command 可以触发多个 Flow。固定分派顺序为：

1. 先按 Exception Flow 的声明顺序判断。
2. 再按 Alternative Flow 的声明顺序判断。
3. 使用同一条 if/elif 链；只执行第一个 Predicate 为 True 的 Flow。
4. 全部为 False 时，进入该 Command 在 Main Flow 中的正常后继位置。

即使多个 Alternative Flow 的 go_back_to 相同，也必须分别判断。若不同，
进入哪个 Flow 就使用哪个 Flow 自己的 go_back_to。

【PC 状态机】

必须使用一个字符串 pc、一个 while 和一个 match/case 生成显式状态机。
PC 表示执行位置，不只表示 Command。它可以表示：

- Main Flow Command；
- Main Flow Decision；
- Alternative Flow 入口或其内部位置；
- Exception Flow 入口或其内部位置；
- 程序结束。

所有可能成为正常后继、trigger 分派目标或 go_back_to 目标的位置，都必须能
由明确的 PC 值进入。Backward go_back_to 必须真正设置到较早的 PC，不能用
注释、递归调用 main() 或复制一段近似流程代替。

每个 Command 函数在源码中只安排一个实际调用位置：

command_name(state, llm_client)

重复执行由 PC 再次进入该位置实现，不能复制 Command 实现。每个主流程
Command 调用完成后，如果它出现在 trigger_is 中，立即执行固定优先级的
Flow Predicate 分派；否则进入正常后继位置。

Decision 的典型形式：

case "decision_1":
    if predicate_for_if_branch(state, llm_client):
        pc = "first_if_branch_step"
    elif predicate_for_elseif_branch(state, llm_client):
        pc = "first_elseif_branch_step"
    else:
        pc = "first_else_step_or_decision_successor"

Alternative Flow 完成后：

- go_back_to command N：pc 指向 commandN 的状态。
- go_back_to decision N：pc 指向 decision_N 的状态。

Exception Flow 完成后：pc 指向结束状态。

【运行时对象初始化】

config.py 只保存配置数据，不保存全局运行实例。main.py 必须导入：

from .config import AGENT_CONFIG
from .model import AgentState
from .utils import OpenAIClient

并生成严格接口：

def main(
    *,
    state: AgentState | None = None,
    llm_client: OpenAIClient | None = None,
) -> AgentState:

只有参数为 None 时才创建实例：

if state is None:
    state = AgentState(AGENT_CONFIG)

if llm_client is None:
    llm_client = OpenAIClient(AGENT_CONFIG["model_config"])

不得使用 `state = state or ...`，因为调用者提供的对象不能因自定义真假值而被
替换。不得在模块顶层初始化 State 或 Client。程序结束时返回 state。

【导入和禁止行为】

- 从 `.commands` 显式导入全部 Command Function Names。
- 从 `.predicates` 显式导入 Predicate Naming Table 的全部函数值。
- 不得使用 getattr、globals、eval、exec 或动态 import 查找函数。
- 不得在 main.py 中调用 llm_client.complete；模型调用只发生在已生成的
  Command 或 Predicate 中。
- 不得直接读取或修改 CNL-P 变量、History 或 State 内部对象。
- 不得重新实现业务逻辑、Predicate 条件、Command 操作或 Flow Binder。
- 不得吞掉异常，不得用宽泛 try/except 改变 Exception Flow 的语义。
- 不得创建线程、异步任务、递归 main 调用或额外运行时框架。

【原始 CNL-P，仅作补充背景】
CNL_P_SCRIPT

【Workflow Structure，内部结构权威来源】
WORKFLOW_STRUCTURE_JSON

【Flow Binding Table，跨 Flow 跳转权威来源】
BINDING_TABLE_JSON

【Command Function Names】
COMMAND_FUNCTION_NAMES_JSON

【Predicate Naming Table】
PREDICATE_NAMING_TABLE_JSON

【输出要求】

只输出一个完整、可直接保存的 main.py 源码，不要输出 Markdown、解释或测试。
源码必须包含必要 import、唯一的 main() 函数以及
`if __name__ == "__main__": main()`。不得定义其他函数或类。"""
