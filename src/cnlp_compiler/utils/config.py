from .json import extract_single_json_from_text

try:
    from ..prompts.utils_config import CONFIG_SYSTEM_PROMPT
except ImportError:  # Supports legacy top-level package imports.
    from prompts.utils_config import CONFIG_SYSTEM_PROMPT



def configurate_parameters(configs: dict, required_configs):
    """
    configs就是外部传入的agent_configs,这个字典长下面这样：
    {
        "config_field_name": {
            "description": ...,
            "value": ...,
        },
        ...
    }

    而required_configs长这样：
    {
        "required_config_field_name": description,
        ...
    }

    这里的处理逻辑应该是，如果required_config_field_name，config_field_name重名，那就直接拿对应的value
    不然就就用大模型去搜索，拿着required_config_field_name的description去和configs作比较，然后返回一个json。提取出来之后在处理，最后完成汇总
    """
    if not isinstance(configs, dict):
        raise ValueError("configs must be a dict")

    if not isinstance(required_configs, dict):
        raise ValueError("required_configs must be a dict")

    configured_parameters = {}
    unresolved_required_configs = {}

    for required_config_field_name, required_config_description in required_configs.items():
        matched_config = configs.get(required_config_field_name)

        if isinstance(matched_config, dict) and "value" in matched_config:
            configured_parameters[required_config_field_name] = matched_config.get("value")
            continue

        unresolved_required_configs[required_config_field_name] = required_config_description

    if not unresolved_required_configs:
        return configured_parameters

    available_configs = {}
    for config_field_name, config_field_info in configs.items():
        if not isinstance(config_field_info, dict):
            continue
        available_configs[config_field_name] = {
            "description": config_field_info.get("description"),
        }

    if not available_configs:
        for required_config_field_name in unresolved_required_configs.keys():
            configured_parameters[required_config_field_name] = None
        return configured_parameters

    llm_tools = _load_llm_tools()
    if llm_tools is None:
        for required_config_field_name in unresolved_required_configs.keys():
            configured_parameters[required_config_field_name] = None
        return configured_parameters

    create_prompt_section, get_model_response = llm_tools

    system_prompt = CONFIG_SYSTEM_PROMPT

    user_prompt = f"""已有配置字段：
{available_configs}

待补全的需求字段：
{unresolved_required_configs}
"""

    mapping_result = None
    messages = [
        create_prompt_section(role="system", content=system_prompt),
        create_prompt_section(role="user", content=user_prompt),
    ]

    try:
        response = get_model_response(messages)
        if isinstance(response, str):
            mapping_result = extract_single_json_from_text(response)
    except Exception:
        mapping_result = None

    if not isinstance(mapping_result, dict):
        mapping_result = {}

    for required_config_field_name in unresolved_required_configs.keys():
        matched_config_field_name = mapping_result.get(required_config_field_name)

        if (
            isinstance(matched_config_field_name, str)
            and matched_config_field_name in configs
            and isinstance(configs[matched_config_field_name], dict)
            and "value" in configs[matched_config_field_name]
        ):
            configured_parameters[required_config_field_name] = configs[matched_config_field_name].get("value")
        else:
            configured_parameters[required_config_field_name] = None

    return configured_parameters


def _load_llm_tools():
    try:
        from .llm import create_prompt_section, get_model_response
    except Exception:
        return None

    return create_prompt_section, get_model_response
