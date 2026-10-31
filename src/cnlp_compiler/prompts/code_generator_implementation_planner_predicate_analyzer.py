"""Active prompt templates used by the current CNL-P compiler."""

PREDICATE_ANALYSIS_PROMPT = """你是CNL-P编译器的Implementation Planner。

在CNL-P Agent中，判断条件用于流程控制。每个判断条件根据引用的相关变量，
判断description所描述的条件是否成立，并返回True或False。

你需要一次分析下面给出的全部判断条件，判断每个判断条件应当使用纯代码实现，
还是在运行时使用LLM完成判断。

判断标准如下：

- 如果对于所有符合相关类型要求的输入，都可以使用明确、确定的Python规则
  忠实完成description中的判断，则llm_based_processing为false。
- 如果判断依赖自然语言语义理解，例如内容是否相关、信息是否充分、结论是否
  可信、文本是否表达某种意图，且无法用完整的确定性规则忠实表达，则
  llm_based_processing为true。

判断时应注意：

- 不要因为规则复杂就使用LLM。只要规则明确，仍应使用纯代码。
- 不要因为最终结果是布尔值，就认为一定可以使用纯代码。
- condition_kind只表示判断条件在流程控制中的用途，不影响实现方式的选择。
- 结合description、引用的相关变量信息以及相关变量的类型要求进行判断。
- 不得增加、删除或修改判断条件引用的相关变量。
- 必须按照输入顺序返回全部分析结果。即使多个判断条件具有相同名称或路径，
  也不得合并、重排或遗漏。
Judgement Conditions：

{{PREDICATES_JSON}}

Related Variables：

{{RELATED_VARIABLES_JSON}}

Related Python Schema：

{{RELATED_PYTHON_SCHEMA_CODE}}

只返回以下JSON，不要返回Markdown、解释或额外字段：

{
  "predicate_analyses": [
    {
      "condition_path": ["..."],
      "llm_based_processing": true
    }
  ]
}"""
