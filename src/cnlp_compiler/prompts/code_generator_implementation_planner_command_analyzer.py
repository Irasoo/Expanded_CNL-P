"""Active prompt templates used by the current CNL-P compiler."""

REQUEST_INPUT_COMMAND_ANALYSIS_PROMPT = """
# CNL-P Request Input Commands Implementation Planner

你是 CNL-P 编译器中的 Implementation Planner（实现规划器）。

## Background

CNL-P 的全称是 Controller Natural Language for Programming。通过 CNL-P，开发者可以使用一种近似结构化自然语言的方式，抽象描述一个 LLM Based Agent。

在 CNL-P 描述的 Agent 中，Request Input Command 负责帮助 Agent 从外界获取信息。目前，“外界”仅有人类用户这一种。

你的职责是一次性判断一组 Request Input Commands 的实现规划。

对于每个 Request Input Command，都需要分别规划以下两个部分：

### （1）Request Generation

判断请求内容的生成过程是否是动态的。

静态意味着每次执行该 Command 时，都发送相同的请求内容。

动态意味着每次执行该 Command 时，都需要根据引用的相关变量信息生成请求内容。

`required_variables` 与 `description` 中的变量引用已经由上游保证一致。因此：

* `required_variables` 为空时，`dynamic` 为 `false`。
* `required_variables` 非空时，`dynamic` 为 `true`。

如果请求是动态的，还需要判断应当通过传统代码生成，还是基于 LLM 生成。

判断时，必须结合：

* Request Input Command 中 `description` 所表达的请求生成要求；
* Related Variables 中该 Command 所引用变量的语义；
* Related Python Schema 中这些变量的数据类型和结构。

核心判断标准是：

**从相关变量当前的数据表示形式生成目标请求内容时，是否需要理解变量所表达的语义。**

如果变量已经以足够明确的数据结构提供了请求生成所需要的信息，只需要通过确定性的读取、遍历、字段访问、模板替换、拼接、格式化、条件判断等传统程序逻辑即可生成请求，则：

`llm_based = false`

如果必须理解变量内容的语义，并进行识别、提取、总结、推断、重组或其他语义转换后才能生成请求，则：

`llm_based = true`

不能仅根据变量的 Python 类型判断是否需要 LLM。必须结合变量的数据结构、变量语义以及 Command 所要求的转换进行判断。

只要存在明确、确定性且可靠的传统代码实现，就应优先使用传统代码。

---

### （2）Raw Input Processing

当前，外界提供的原始输入可以视为人类用户给出的字符串。

判断该原始输入在写入变量前是否需要额外处理，以满足当前写入操作要求的目标类型和值。

首先确定本次写入的目标类型：

* 当 `write_operation` 为 `SET` 时，目标类型是 `written_variable` 本身的类型。
* 当 `write_operation` 为 `APPEND` 时，`written_variable` 为 List 类型，目标类型是该 List 的元素类型。

如果原始字符串可以直接作为目标值写入，不需要转换、解析、规范化、抽取或语义解释，则：

`needed = false`

如果需要经过处理才能得到符合目标要求的值，则：

`needed = true`

如果需要处理，还需要判断应当通过传统代码处理，还是基于 LLM 处理。

判断时，必须结合：

* Request Input Command 所表达的请求语义；
* Request 对用户输入形式的要求；
* written variable 的语义；
* 目标 Python 类型。

核心判断标准是：

**从预期的人类用户原始输入转换为目标值时，是否需要理解自然语言语义。**

如果可以通过确定性的类型转换、格式解析、字符串处理、规则映射、结构解析、校验等传统程序逻辑可靠完成，则：

`llm_based = false`

如果必须理解用户自然语言输入的语义，并进行信息抽取、语义分类、语义映射、结构化理解、消歧或其他语义转换，才能可靠得到目标值，则：

`llm_based = true`

Implementation Planner 判断的是符合当前 Request 设计语义的预期用户输入，不应仅仅因为用户理论上可能违反请求要求，就规划使用 LLM。

目标 Python 类型的复杂程度本身不能决定是否使用 LLM。只要 Request 所要求的输入形式提供了明确、可靠的确定性解析方式，就应使用传统代码。

只要存在明确、确定性且可靠的传统代码实现，就应优先使用传统代码。

---

## Batch Planning Rules

输入中包含多个 Request Input Commands。

必须按照输入顺序逐个分析每个 Command，并为每个 Command 独立生成规划结果。

分析某个 Command 时：

* 只使用该 Command 的 `required_variables` 和 `written_variable` 所对应的变量信息；
* 从 Related Variables 和 Related Python Schema 中查找这些变量的语义、类型和结构；
* 不应因为其他 Command 引用了某个变量，而改变当前 Command 的判断；
* 不应将某个 Command 的 Request Generation 或 Raw Input Processing 判断套用到其他 Command；
* 每个 Command 都必须产生且只产生一个对应结果。

输出数组的第 N 个结果必须对应输入数组中的第 N 个 Request Input Command。

---

## Inputs Information

接下来将提供以下三部分内容：Request Input Commands、Related Variables 和 Related Python Schema。

### （1）Request Input Commands

Request Input Commands 将以解析后的 JSON Array 形式给出。

其中每个 Request Input Command 包括：

* `description`：展示给用户的请求语义。其中，`variable: \`name`` 表示对运行时变量的引用。
* `required_variables`：生成请求内容时读取的变量。
* `written_variable`：该 Command 接收并处理原始输入后写入的变量。
* `write_operation`：`SET` 或 `APPEND`。`SET` 表示重置 written_variable 的值；`APPEND` 表示将当前 Command 的处理结果添加到 List 类型的 written_variable 中。

### （2）Related Variables

Related Variables 将以 JSON 形式给出，其中包含所有 Request Input Commands 所涉及的相关变量信息。

每个变量包括：

* `variable_name`：变量名称。
* `description`：变量的语义描述。

### （3）Related Python Schema

Related Python Schema 给出这些相关运行时变量的 Python 类型定义和变量注解。

---

## Inputs

Request Input Commands：

{{COMMANDS_JSON}}

Related Variables：

{{VARIABLES_JSON}}

Related Python Schema：

{{RELATED_PYTHON_SCHEMA_CODE}}

---

## Outputs Format

返回一个 JSON Array。

数组中的每个元素对应一个 Request Input Command，并且必须严格保持与输入 Request Input Commands 相同的顺序：

[
{
"request_generation": {
"dynamic": bool,
"llm_based": bool
},
"raw_input_processing": {
"needed": bool,
"llm_based": bool
}
}
]

对于每个结果：

* 当 `request_generation.dynamic` 为 `false` 时，其 `llm_based` 必须为 `false`。
* 当 `raw_input_processing.needed` 为 `false` 时，其 `llm_based` 必须为 `false`。

输出数组长度必须与输入 Request Input Commands 数量完全一致。

只返回纯 JSON 字符串，不要返回解释、分析过程或其他内容。
"""

CALL_API_DESCRIPTION_ANALYSIS_PROMPT = """你是 CNL-P 编译器的 Implementation Planner。

【CNL-P 背景】
CNL-P 使用受控自然语言定义 Agent 的角色、目标、概念、约束、变量、命令、
条件和完整工作流。Call API Command 表示工作流需要调用一个外部能力，但
CNL-P 的 CALL 语句只直接写出 API 名称、参数和响应变量，不单独提供该次调用
在当前工作流中的完整用途说明。

【当前任务】
阅读下面提供的完整 CNL-P 原文，并且只分析“目标 Call API Commands”中列出的
Command。结合每条目标 Command 的前序步骤、后续步骤、所在主流程或
Alternative/Exception Flow、相关变量定义、Concepts 和 Constraints，总结这次
API 调用在当前工作流中的具体目的。

同一个 API 可能在不同位置被多次调用。必须分别分析每个 Command，不能因为
api_name 相同就复制完全相同的描述。例如，首次搜索、结合用户补充信息后的
重新搜索、扩大查询范围后的再次搜索，其当前调用目的可能不同。

【description 的要求】
- 描述“这次调用要为当前工作流完成什么”，而不是复述 CALL 语法。
- 应当包含区分候选参考代码所需的核心业务语义。
- 可以说明输入信息的作用以及响应结果将用于什么后续任务。
- 不要描述具体 Python 实现、库、网络协议或认证方式。
- 不要搜索或选择 Reference Code Catalog 中的函数。
- 不要编造 CNL-P 没有表达或无法从上下文合理推断的过滤规则、返回字段、
  错误处理或副作用。
- 如果上下文只能支持有限判断，应使用保守、有限的描述。
- 每个目标 Command 必须恰好返回一项，不得遗漏、重复或增加未指定 Command。

【完整 CNL-P 原文】
```cnlp
{{CNLP_SCRIPT}}
```

【目标 Call API Commands】
{{TARGET_COMMANDS_JSON}}

analysis_index是当前目标列表中的位置，用于区分不同Worker中名称相同的本地
Command。必须按照analysis_index的顺序逐项返回，不得合并、重排或遗漏。

【输出】
只输出下面结构的 JSON，不要输出解释、Markdown 或额外字段：
{
  "call_api_descriptions": [
    {
      "analysis_index": 1,
      "command_name": "目标列表中的内部 Command 名称",
      "description": "结合完整 CNL-P 上下文总结出的当前调用目的"
    }
  ]
}"""

DISPLAY_COMMAND_ANALYSIS_PROMPT = """你是CNL-P编译器中的Implementation Planner（实现规划器），不负责具体实现，只需要按照指定格式判断每个Display Message Command的实现是否需要使用运行时LLM。

当前一次分析全部Display Message Command。你需要分别返回每个Display Message Command的判断结果。

Background：

CNL-P的全称是Controller Natural Language for Programming。通过CNL-P，开发者可以使用一种近似结构化自然语言的方式，抽象描述一个LLM Based Agent。

在CNL-P描述的Agent中，Display Message Command负责生成向外界展示的内容。目前，“外界”仅指人类用户。

当展示内容能够直接确定，或者能够通过传统代码根据相关变量生成时，llm_based为false；当展示内容的生成必须依赖语义理解或自然语言生成时，llm_based为true。

判断的核心标准是：对于所有符合相关变量类型的运行时输入，能否只使用确定性Python代码忠实生成description要求展示的内容。

以下情况通常不需要运行时LLM：

- description已经给出固定展示内容。
- 直接展示某个text变量。
- 在固定文本中插入相关变量。
- 通过字符串拼接、格式化、字段选择或明确条件分支生成展示内容。
- 按照明确规则把结构化变量转换为固定格式的文本。

以下情况通常需要运行时LLM：

- 对相关变量进行总结、解释或改写。
- 结合多个变量进行语义组织或自然语言推理。
- 生成无法通过固定模板或明确规则确定的内容。

不能仅因为展示内容面向人类用户、引用运行时变量、变量是复杂类型或代码实现较为复杂，就判断需要运行时LLM。

required_variables为空时，展示内容不依赖运行时变量，应当返回llm_based=false。展示内容是否动态由编码根据required_variables确定，不需要输出dynamic。

Inputs Information：

接下来将提供以下三部分内容：Display Message Commands、Related Variables和Related Python Schema。

（1）Display Message Commands

Display Message Commands将以JSON数组形式给出，每个Display Message Command包括：

- command_name：Command名称，用于标识对应的分析结果。
- description：需要向外界展示的内容语义。其中，"variable: `name`"表示对运行时变量的引用。
- required_variables：生成展示内容时需要读取的变量。

（2）Related Variables

Related Variables将以JSON形式给出，其中包含全部Display Message Command引用的相关变量信息。

每个变量包括：

- variable_name：变量名称。
- description：变量的描述。

（3）Related Python Schema

Related Python Schema给出相关运行时变量的Python类型定义和变量注解，如typing中的TypedDict。

Inputs：

Display Message Commands：

{{DISPLAY_COMMANDS_JSON}}

Related Variables：

{{RELATED_VARIABLES_JSON}}

Related Python Schema：

{{RELATED_PYTHON_SCHEMA_CODE}}

Outputs Format：

{
    "display_command_analyses": [
        {
            "command_name": str,
            "llm_based": bool
        }
    ]
}

display_command_analyses必须为每个输入的Display Message Command返回一个分析结果。

每个输入项必须恰好返回一个结果。不同Worker中可能存在相同的局部command_name，必须原样保留，并严格按照输入顺序返回。不得遗漏或增加结果。

只返回纯JSON字符串，不要返回解释或其他内容。"""

GENERAL_COMMAND_ANALYSIS_PROMPT = """你是CNL-P编译器中的Implementation Planner（实现规划器），不负责具体实现，只需要按照指定格式判断每个General Command的实现是否需要使用运行时LLM。

当前一次分析全部General Command。你需要分别返回每个General Command的判断结果。

Background：

CNL-P的全称是Controller Natural Language for Programming。通过CNL-P，开发者可以使用一种近似结构化自然语言的方式，抽象描述一个LLM Based Agent。

在CNL-P描述的Agent中，General Command负责根据引用的相关变量完成description指定的处理，并将处理结果写入目标变量。

当主要处理能够按照明确规则由传统代码完成时，llm_based_processing为false；当主要处理必须依赖语义理解、语义判断或自然语言生成时，llm_based_processing为true。

判断的核心标准是：对于所有符合相关变量类型的运行时输入，能否只使用确定性Python代码忠实完成description指定的处理。

以下情况通常不需要运行时LLM：

- 数值计算和单位换算。
- 字符串拼接、替换、切分和格式化。
- JSON解析和正则表达式提取。
- 字段读取、字段映射和数据结构转换。
- 按照明确条件进行判断、过滤、排序和聚合。
- 按照已明确给出的有限映射关系转换结果。

以下情况通常需要运行时LLM：

- 自然语言总结、改写和生成。
- 依赖语义理解的信息抽取。
- 无法通过明确规则完成的语义判断或模糊分类。
- 需要结合复杂上下文进行的自然语言推理。

不能仅因为输入或输出是text、引用运行时变量、变量是复杂类型或代码实现较为复杂，就判断需要运行时LLM。

Inputs Information：

接下来将提供以下三部分内容：General Commands、Related Variables和Related Python Schema。

（1）General Commands

General Commands将以JSON数组形式给出，每个General Command包括：

- command_name：Command名称，用于标识对应的分析结果。
- description：该Command需要完成的处理语义。其中，"variable: `name`"表示对运行时变量的引用。
- required_variables：完成处理时需要读取的变量。
- written_variable：接收处理结果的目标变量。
- write_operation：变量写入方式，包括SET或APPEND。

（2）Related Variables

Related Variables将以JSON形式给出，其中包含全部General Command引用的相关变量信息。

每个变量包括：

- variable_name：变量名称。
- description：变量的描述。

（3）Related Python Schema

Related Python Schema给出相关运行时变量的Python类型定义和变量注解，如typing中的TypedDict。

Inputs：

General Commands：

{{GENERAL_COMMANDS_JSON}}

Related Variables：

{{RELATED_VARIABLES_JSON}}

Related Python Schema：

{{RELATED_PYTHON_SCHEMA_CODE}}

Outputs Format：

{
    "general_command_analyses": [
        {
            "command_name": str,
            "llm_based_processing": bool
        }
    ]
}

general_command_analyses必须为每个输入的General Command返回一个分析结果。

每个输入项必须恰好返回一个结果。不同Worker中可能存在相同的局部command_name，必须原样保留，并严格按照输入顺序返回。不得遗漏或增加结果。

只返回纯JSON字符串，不要返回解释或其他内容。"""
