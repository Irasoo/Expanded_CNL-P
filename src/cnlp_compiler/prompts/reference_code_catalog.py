"""Active prompt templates used by the current CNL-P compiler."""

LLM_MATCHING_PROMPT = """你正在为一个待生成的 Python 调用选择最合适的参考函数。

【待实现调用】
{{SEARCH_QUERY_JSON}}

【候选参考函数】
{{SEARCH_DOCUMENTS_JSON}}

【任务】
在候选函数中选择最适合作为当前调用实现参考的一个函数。函数名不必完全相同，
重点是调用目的、参数含义、参数类型和返回结果是否最适合。候选信息只包含元数据，
不包含源码；不要假设候选函数具有未列出的行为。

如果没有任何候选函数适合，返回 null。

【输出】
只输出 JSON，不要输出解释、Markdown 或额外字段：
{"function_name": "候选函数名"}
或
{"function_name": null}"""
