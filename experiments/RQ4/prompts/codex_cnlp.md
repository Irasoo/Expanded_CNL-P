【任务】

请根据当前目录中提供的 CNL-P Script 和 Reference Code，生成一个可以
实际运行的 Python Agent 项目。

必须立即使用本地工具读取以下两个输入文件并开始生成代码，不要只回复工作计划：

- `_codex_inputs/agent.cnlp`：完整的 CNL-P Script，是 Agent 业务语义的唯一权威来源。
- `_codex_inputs/reference_code.py`：为 CNL-P 中 CALL API 提供的 Python 参考实现。

不得修改这两个输入文件。生成后的 Agent 不得在运行时读取或依赖
`_codex_inputs`。

【生成结果】

当前工作目录就是最终 Agent 的根目录，不要创建额外的外层项目目录。

项目可以只有一个 Python 文件，也可以包含多个文件，但根目录必须包含 `main.py`，
并提供以下无参数入口：

def main():
    ...

`main()` 应初始化 Agent、执行入口 Worker，并返回最终执行结果。

`main.py` 被 import 时不得自动运行，同时必须支持直接运行：

if __name__ == "__main__":
    main()

项目内部如何划分文件、保存变量和组织流程，由你自行决定。

【终端交互】

生成的 Agent 与用户之间的所有交互必须在终端中完成：

- 使用标准输出向用户展示提示、说明和结果。
- 使用标准输入读取用户回答。
- 不得生成 GUI、Web 页面或后台服务。
- 每次执行一个 CNL-P INPUT Command，只读取一次用户输入。
- 如果一个 INPUT Command 需要获得多个字段，应从这一次用户输入中理解并提取，
  不得擅自拆成多轮提问。
- 只有当 CNL-P Flow 再次执行某个 INPUT Command 时，才可以再次读取输入。

【CNL-P 语义】

必须完整实现 CNL-P Script 表达的 Types、Variables、Commands、Conditions、Workers、
INPUTS、OUTPUTS 和控制流程。

不得使用固定示例值、占位返回值或与当前 Script 绑定的测试答案替代真实功能。

【CNL-P 基本执行语义】

类型和值：
- `[a, b, c]` 表示只能取这些值之一的有限值域，不表示列表。
- `List [T]` 表示由若干 T 类型元素组成的列表。
- `{field: T}` 表示包含具名字段的结构化值。
- `OPTIONAL field: T` 表示该字段可以不存在。
- 写入变量的值必须满足变量声明的类型，不得擅自改变变量类型。

引用和写入：
- `<REF>x</REF>` 表示读取当前状态中变量 x 的值；带字段路径的引用表示读取对应
  嵌套字段。
- `SET` 表示用新值替换变量当前值。
- `VALUE <REF>x</REF> SET` 表示将 INPUT Command 处理后的用户输入写入 x。
- `RESULT <REF>x</REF> SET` 表示将 COMMAND 的处理结果写入 x。
- `RESPONSE <REF>x</REF> SET` 表示将 CALL API 或 CALL Worker 的返回结果写入 x。

Command：
- INPUT：展示请求，读取恰好一次用户输入，按照 Command 描述处理后写入 VALUE
  指定的变量。
- COMMAND：根据 Command 描述及其引用的数据完成计算或语义处理，并将结果写入
  RESULT 指定的变量。
- CALL：调用指定的 API 或 Worker，并将返回值写入 RESPONSE 指定的变量。
- DISPLAY：向用户展示指定内容；除非 Script 明确要求，否则不得修改变量。
- LOG：记录诊断信息，不等同于面向用户的 DISPLAY。

控制结构和 Worker：
- SEQUENTIAL_BLOCK 中的内容按照书写顺序执行。
- 同一组 IF、ELSEIF 和 ELSE 是互斥分支，只执行第一个满足条件的分支。
- 调用 Worker 时，只通过其声明的 INPUTS 传入数据，并通过其声明的 OUTPUTS
  返回结果。
- REQUIRED OUTPUT 在 Worker 正常结束时必须存在；OPTIONAL OUTPUT 可以不存在。
- DISPLAY 某个值不等于已经设置或返回该 OUTPUT。

【Reference Code】

Reference Code 为 CNL-P 中对应的 CALL API 提供参考实现。

对于 Reference Code 中与语言模型调用有关的代码，可以根据本实验统一的
OpenAI Client、模型、Base URL 和 reasoning effort 配置进行替换，不要求复制其
LLM 客户端初始化和模型调用样板代码。

除上述 LLM 调用基础设施外，应尽可能妥善利用 Reference Code 已提供的内容，
包括 Prompt 内容和指令约束、输入数据的组织与序列化方式、调用前的数据处理、
输出提取与解析、清洗和类型转换、返回值构造、结果校验、空结果处理、错误处理，
以及不依赖 LLM 的确定性业务逻辑。

可以直接复用、封装、内联或进行必要适配，不限制生成项目的代码组织形式，但
不得无故丢弃 Reference Code 中已有的重要 Prompt、处理逻辑和行为约束。

如果 Reference Code 与 CNL-P Script 的类型、接口或业务语义存在冲突，以
CNL-P Script 为最终依据，并进行必要适配。

【运行时语言模型】

当 CNL-P Command 或 Condition 涉及自然语言理解、自然语言生成、语义转换或语义
判断时，应使用运行时语言模型完成，不得擅自替换成关键词匹配、简单正则表达式、
固定模板或硬编码结论。

明确且不需要语义理解的计算、赋值、比较、流程控制和数据处理，可以直接使用
Python 实现。

具体哪些 Commands 和 Conditions 需要语言模型，以及如何组织相关代码，由你根据
CNL-P 的真实语义决定。

运行时语言模型必须：

- 使用官方 OpenAI Python Client：`from openai import OpenAI`。
- 从 `.env` 或当前进程环境变量读取 `OPENAI_API_KEY`。
- 从 `.env` 或当前进程环境变量读取 `BASE_URL`。
- 优先从 `.env` 或当前进程环境变量读取 `CNLP_REFERENCE_LLM_MODEL` 作为模型
  名称；若未设置，则读取 `OPENAI_MODEL`。若两者均未设置，应报告明确错误。
- 所有运行时语言模型调用都必须显式使用 `high` reasoning effort，例如
  `reasoning={"effort": "high"}`。
- 不得在代码中写入真实 API Key 或其他凭据。

这些是生成后 Agent 的运行时模型配置，不是当前 Codex 生成代码时使用的配置。

【Static Attributes】

CNL-P 中的 Static Attributes 用于约束 Agent 的整体行为：

- Persona：Agent 的身份、职责和行为立场。
- Audience：目标用户及其知识背景，影响术语选择、解释深度和表达方式。
- Concepts：Agent 应遵循的领域概念及其含义。
- Constraints：Agent 必须遵守的业务边界和行为限制。

这些属性应实际影响需要自然语言理解、判断或生成的交互过程，但具体如何在项目中
体现，由你自行决定。

【三类 Flow】

- Main Flow 是 Worker 的正常执行流程和执行入口。
- Alternative Flow 是可恢复的旁路流程；满足条件时从 Main Flow 进入，执行完成后
  返回 Main Flow 中合理的位置继续执行。
- Exception Flow 是不可恢复的旁路流程；满足条件时从 Main Flow 进入，执行完成后
  结束当前 Worker，不再返回 Main Flow。
- Alternative Flow 和 Exception Flow 只能由 Main Flow 触发，旁路 Flow 之间不得相互
  触发或调用。
- CNL-P 不直接标出旁路 Flow 的触发位置和 Alternative Flow 的返回位置。应根据
  条件所依赖的数据、更新这些数据的 Command 以及整体业务语义确定，不得只根据
  Command 编号猜测。

当一个 CALL 调用另一个 Worker 时，将被调用 Worker 视为子程序：按照其 INPUTS 接收
数据，执行自身 Flow，再按照其 OUTPUTS 和 CALL RESPONSE 将结果返回给调用者。

【执行边界】

所有生成文件只能写入当前工作目录。

不得读取或修改父目录、同级目录、其他案例、已有编译产物或编译器源码。不得联网
搜索实现方案，不得写入密钥或机器相关的绝对路径。

生成完成后，仅对生成的 Python 文件执行语法检查，例如使用 `python -m py_compile`。
不得导入或启动 Agent，不得调用真实外部 API。

只有在根目录已经生成 `main.py` 及其所需文件，并完成上述语法检查后，任务才算
完成。只给出计划、建议或代码说明不算完成。