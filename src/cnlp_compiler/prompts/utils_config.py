"""Active prompt templates used by the current CNL-P compiler."""

CONFIG_SYSTEM_PROMPT = """
你需要把“需求字段”匹配到“已有配置字段”。

返回一个 JSON 对象：
{
    "required_field_name": "matched_config_field_name or null"
}

要求：
1. 只返回 JSON，不要返回其他解释。
2. 如果找不到合适的已有配置字段，就返回 null。
3. 只有在语义明显匹配时才建立映射。
"""
