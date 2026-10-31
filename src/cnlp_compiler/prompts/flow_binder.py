"""Active prompt templates used by the current CNL-P compiler."""

ALTERNATIVE_FLOW_SYSTEM_PROMPT = """你需要分析 main_flow 与一个 alternative_flow 之间的跳转关系。我将以 JSON 形式提供：

1. 已添加 decision_index 的 main_flow AST；
2. 当前需要绑定的 alternative_flow AST。

main_flow 和 alternative_flow 中可能包含以下三类 block：

1. sequential_block：顺序执行其中的 command；
2. if_block：根据条件选择分支；
3. loop_block：包括 while_block 和 for_block，根据循环条件决定是否执行或继续执行循环。

if_block 和 loop_block 都具有 decision_index，用于唯一标记该 block；sequential_block 没有 decision_index。每个 command 的键名由“command”加整数编号构成，用于唯一标记该 command。

alternative_flow 具有一个 condition 字段，用于描述其触发条件。系统执行 main_flow；当某个触发位置执行完成，并且该 condition 成立时，进入 alternative_flow。alternative_flow 执行完成后，返回 main_flow 的一个位置继续执行。

你需要确定：

1. main_flow 中执行完哪些 command 后需要判断是否进入该 alternative_flow，并将这些 command 记录在 trigger_is 中；
2. alternative_flow 执行完成后，main_flow 应从哪个 command 或 decision 继续执行，并将该位置记录在 go_back_to 中。

关于 trigger_is：

trigger_is 表示 main_flow 中执行完某条 command 后，需要判断 alternative_flow.condition 是否成立。判断时，应识别 condition 依赖的变量或执行结果，并定位 main_flow 中产生、更新或确定这些内容的 command。trigger_is 只能指向 main_flow 中的 command，可以包含一个或多个触发位置。

同一个 alternative_flow 的所有 trigger_is 共用同一个 go_back_to。只有当多个触发位置在 alternative_flow 执行完成后都应返回同一位置时，才可以同时将它们加入 trigger_is。

关于 go_back_to：

go_back_to 表示 alternative_flow 执行完成后，返回 main_flow 时应从哪条 command 或哪个 decision 继续执行。go_back_to 只能指向唯一的一个位置。

当 go_back_to 指向 command 时，main_flow 从该 command 开始继续执行。

当 go_back_to 指向 decision 时，main_flow 返回该 decision 所在的 block：如果是 loop_block，则重新判断其循环条件；如果是 if_block，则从第一个 if 条件开始重新判断，再根据判断结果选择相应分支。不得绕过该 decision，直接返回其内部的某条 command。

判断 go_back_to 时，应识别 alternative_flow 产生或更新的内容，并定位 main_flow 中下一处应使用或判断这些内容的 command 或 decision。go_back_to 不一定是 trigger_is 后编号相邻的 command。

输出约束：

- trigger_is 只能引用 main_flow 中实际存在的 command；
- go_back_to 只能引用 main_flow 中实际存在的 command 或 decision；
- index 必须使用 AST 中已有的整数编号；
- 只输出 JSON 对象，不要输出分析过程、解释、Markdown 或代码围栏。

返回格式：

{
  "trigger_is": [
    {
      "index_type": "command",
      "index": int
    }
  ],
  "go_back_to": {
    "index_type": "command" 或 "decision",
    "index": int
  }
}"""

EXCEPTION_FLOW_SYSTEM_PROMPT = """你需要分析 main_flow 与一个 exception_flow 之间的跳转关系。我将以 JSON 形式提供：

1. 已添加 decision_index 的 main_flow AST；
2. 当前需要绑定的 exception_flow AST。

main_flow 和 exception_flow 中可能包含以下三类 block：

1. sequential_block：顺序执行其中的 command；
2. if_block：根据条件选择分支；
3. loop_block：包括 while_block 和 for_block，根据循环条件决定是否执行或继续执行循环。

每个 command 的键名由“command”加整数编号构成，用于唯一标记该 command。

exception_flow 具有 condition 和 log 字段。condition 描述其触发条件，log 描述需要报告的信息。系统执行 main_flow；当某个触发位置执行完成，并且该 condition 成立时，进入 exception_flow。exception_flow 执行完成后不再返回 main_flow。

你需要根据 exception_flow.condition、log 和内部处理内容，确定 main_flow 中执行完哪些 command 后需要判断是否进入该 exception_flow，并将这些 command 记录在 trigger_is 中。

关于 trigger_is：

trigger_is 表示 main_flow 中执行完某条 command 后，需要判断 exception_flow.condition 是否成立。判断时，应识别 condition 描述的异常情况及其依赖的变量或执行结果，并定位 main_flow 中可能产生、更新或确定这些内容的 command。

trigger_is 只能指向 main_flow 中的 command。如果多个 command 都可能独立产生该异常，可以返回多个触发位置；即使只有一个触发位置，也必须使用列表。

输出约束：

- trigger_is 只能引用 main_flow 中实际存在的 command；
- index 必须使用 AST 中已有的整数编号；
- 只输出 JSON 数组，不要输出分析过程、解释、Markdown 或代码围栏。

返回格式：

[
  {
    "index_type": "command",
    "index": int
  }
]"""
