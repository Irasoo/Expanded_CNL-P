from __future__ import annotations

import ast
import json
import re

from ...schema import GeneratedFile, ModelConfig, VariableNode
from .....utils import (
    LLMclient,
    OpenaiClient,
    create_prompt_section,
)
from .schema import TypeImplementationResult


_MODEL_CONFIG_PLACEHOLDERS = {
    "api_key": "__CNL_P_MODEL_API_KEY__",
    "model_name": "__CNL_P_MODEL_NAME__",
    "base_url": "__CNL_P_BASE_URL__",
}


class ConfigImplementer:

    def __init__(self, llm_client: LLMclient | None = None) -> None:
        self._llm_client = llm_client

    def implement(
        self,
        *,
        cnlp_script: str,
        variables: list[VariableNode],
        model_config: ModelConfig,
        type_result: TypeImplementationResult,
    ) -> GeneratedFile:
        prompt = self.build_prompt(
            cnlp_script=cnlp_script,
            variables=variables,
            type_result=type_result,
        )
        response = self._get_llm_client(model_config).complete(
            [create_prompt_section("user", prompt)]
        )
        content = self._extract_python_code(response)
        content = self._inject_model_config(content, model_config)
        self._validate_generated_code(content)

        return {
            "relative_path": "config.py",
            "content": content,
            "write_type": "rewrite",
        }

    def build_prompt(
        self,
        *,
        cnlp_script: str,
        variables: list[VariableNode],
        type_result: TypeImplementationResult,
    ) -> str:
        variable_text = json.dumps(
            variables,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        declared_type_text = json.dumps(
            type_result["declared_type_names"],
            ensure_ascii=False,
            indent=2,
        )
        placeholder_config_text = json.dumps(
            _MODEL_CONFIG_PLACEHOLDERS,
            ensure_ascii=False,
            indent=2,
        )

        return f"""
你正在参与 CNL-P 编译器的 Native Python 代码生成阶段。

CNL-P 是一种用于描述 Agent 的受控自然语言。编译器已经完成语法解析、
变量提取和 CNL-P 类型到 Python 类型的转换。你当前只负责生成 config.py，
不要生成 schema.py、model.py、commands.py、predicates.py 或 main.py。

config.py 需要完成四件事：
1. 从原始 CNL-P 中整理 Agent 的 Persona、Audience、Concepts 和 Constraints，
   形成一段完整的 AGENT_ATTRIBUTES 字符串，供运行时作为模型的系统背景。
2. 创建 MODEL_CONFIG。
3. 按 CNL-P 声明顺序创建 VARIABLE_CONFIG，并为每个变量保留其真实 Python 类型
   和默认值。
4. 用以上内容创建最终的 AGENT_CONFIG。

【原始 CNL-P】
<CNL_P_SCRIPT>
{cnlp_script}
</CNL_P_SCRIPT>

【NodeVisitor 已提取的变量】
<VARIABLES>
{variable_text}
</VARIABLES>

【已经生成在 schema.py 中的 CNL-P 声明类型名】
<DECLARED_TYPE_NAMES>
{declared_type_text}
</DECLARED_TYPE_NAMES>

【必须原样写入 MODEL_CONFIG 的占位值】
<MODEL_CONFIG_PLACEHOLDERS>
{placeholder_config_text}
</MODEL_CONFIG_PLACEHOLDERS>

请严格遵守以下生成规则：

1. config.py 必须从 `.schema` 导入 AgentConfig、ModelConfig 和
   CNLPVariableInfo；只额外导入变量实际使用到的 CNL-P 声明类型。
2. 不得导入 AgentState，不得加入 `from __future__ import annotations`。
3. AGENT_ATTRIBUTES 只整理 Agent 的 Persona、Audience、Concepts、
   Constraints 以及其他全局 Agent 属性。不要把变量、类型、Command、
   Main Flow、Alternative Flow 或 Exception Flow 混入其中。
4. MODEL_CONFIG 只能包含 api_key、model_name、base_url 三个字段；
   不得包含 temperature 或其他字段。三个字段的值必须使用上面给定的
   占位字符串，不得修改、解释或自行替换。
5. VARIABLE_CONFIG 的类型是 `list[CNLPVariableInfo]`。每个元素只能包含：
   variable_name、value_type、default_value。
6. value_type 必须写成 Python 类型表达式，不能写成字符串：
   text 对应 str，number 对应 int | float，boolean 对应 bool；
   List 类型写成 list[元素类型]；CNL-P 声明类型直接使用其类型名。
7. default_value 存在时，使用变量信息中 default_value.value 的真实值；
   不存在时写 None。不得臆造默认值。
8. 最后必须生成：
   `AGENT_CONFIG: AgentConfig = {{...}}`，其中引用前面三个配置变量。
9. 输出必须是可以直接保存为 config.py 的完整 Python 源码。
   响应必须直接以 `from .schema import` 开始。只输出源码，不要先说明计划、
   不要声称将核对文件，不要使用 Markdown 代码块，也不要附加任何解释。
""".strip()

    def _get_llm_client(self, model_config: ModelConfig) -> LLMclient:
        if self._llm_client is not None:
            return self._llm_client

        return OpenaiClient(
            model_config["api_key"],
            model_config["model_name"],
            "",
            model_config["base_url"],
        )

    @staticmethod
    def _extract_python_code(response: str) -> str:
        content = response.strip()
        fenced_match = re.search(
            r"```(?:python)?\s*\n(?P<code>.*?)\n```",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if fenced_match is not None:
            content = fenced_match.group("code").strip()
        else:
            # Some models prepend a progress sentence even when the prompt
            # requires source-only output.  The config module has a fixed,
            # validated first import, so anything before it is not config.py.
            schema_import = "from .schema import"
            schema_import_index = content.find(schema_import)
            if schema_import_index >= 0:
                content = content[schema_import_index:].strip()

            # Likewise, discard prose appended after a complete module.  This
            # is only accepted when the retained prefix already parses and
            # contains the required final AGENT_CONFIG assignment; structural
            # validation still runs after model-config values are injected.
            try:
                ast.parse(content, filename="config.py")
            except SyntaxError:
                final_dict_end = content.rfind("}")
                if final_dict_end >= 0:
                    candidate = content[: final_dict_end + 1].strip()
                    try:
                        candidate_tree = ast.parse(
                            candidate,
                            filename="config.py",
                        )
                    except SyntaxError:
                        pass
                    else:
                        assignment_names = {
                            node.target.id
                            for node in candidate_tree.body
                            if (
                                isinstance(node, ast.AnnAssign)
                                and isinstance(node.target, ast.Name)
                            )
                        }
                        assignment_names.update(
                            target.id
                            for node in candidate_tree.body
                            if isinstance(node, ast.Assign)
                            for target in node.targets
                            if isinstance(target, ast.Name)
                        )
                        if "AGENT_CONFIG" in assignment_names:
                            content = candidate

        if not content:
            raise ValueError("LLM returned empty config.py content.")
        return f"{content}\n"

    @staticmethod
    def _inject_model_config(
        content: str,
        model_config: ModelConfig,
    ) -> str:
        result = content
        for field_name, placeholder in _MODEL_CONFIG_PLACEHOLDERS.items():
            quoted_placeholder = re.compile(
                rf"(?P<quote>['\"]){re.escape(placeholder)}(?P=quote)"
            )
            matches = list(quoted_placeholder.finditer(result))
            if len(matches) != 1:
                raise ValueError(
                    "Generated config.py must contain exactly one "
                    f"{field_name!r} model-config placeholder."
                )
            result = quoted_placeholder.sub(
                repr(model_config[field_name]),
                result,
                count=1,
            )
        return result

    @staticmethod
    def _validate_generated_code(content: str) -> None:
        try:
            syntax_tree = ast.parse(content, filename="config.py")
        except SyntaxError as exc:
            raise ValueError(
                "LLM returned invalid Python for config.py."
            ) from exc

        ConfigImplementer._validate_model_config_fields(syntax_tree)

        if any(
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            for node in syntax_tree.body
        ):
            raise ValueError(
                "Generated config.py must not import __future__."
            )

        schema_imports = {
            alias.name
            for node in syntax_tree.body
            if (
                isinstance(node, ast.ImportFrom)
                and node.level == 1
                and node.module == "schema"
            )
            for alias in node.names
        }
        required_imports = {
            "AgentConfig",
            "ModelConfig",
            "CNLPVariableInfo",
        }
        if not required_imports <= schema_imports:
            missing_imports = sorted(required_imports - schema_imports)
            raise ValueError(
                "Generated config.py is missing schema imports: "
                f"{missing_imports}."
            )

        assignment_names: set[str] = set()
        for node in syntax_tree.body:
            if isinstance(node, ast.Assign):
                assignment_names.update(
                    target.id
                    for target in node.targets
                    if isinstance(target, ast.Name)
                )
            elif (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
            ):
                assignment_names.add(node.target.id)

        required_assignments = {
            "AGENT_ATTRIBUTES",
            "MODEL_CONFIG",
            "VARIABLE_CONFIG",
            "AGENT_CONFIG",
        }
        if not required_assignments <= assignment_names:
            missing_assignments = sorted(
                required_assignments - assignment_names
            )
            raise ValueError(
                "Generated config.py is missing assignments: "
                f"{missing_assignments}."
            )

    @staticmethod
    def _validate_model_config_fields(syntax_tree: ast.Module) -> None:
        model_config_values: list[ast.expr | None] = []
        for node in syntax_tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name)
                and target.id == "MODEL_CONFIG"
                for target in node.targets
            ):
                model_config_values.append(node.value)
            elif (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "MODEL_CONFIG"
            ):
                model_config_values.append(node.value)

        if len(model_config_values) != 1:
            raise ValueError(
                "Generated config.py must assign MODEL_CONFIG exactly once."
            )

        model_config_value = model_config_values[0]
        if not isinstance(model_config_value, ast.Dict):
            raise ValueError(
                "Generated MODEL_CONFIG must be a dictionary literal."
            )

        field_names: list[str] = []
        for key in model_config_value.keys:
            if not isinstance(key, ast.Constant) or not isinstance(
                key.value,
                str,
            ):
                raise ValueError(
                    "Generated MODEL_CONFIG keys must be string literals."
                )
            field_names.append(key.value)

        required_fields = {"api_key", "model_name", "base_url"}
        if len(field_names) != len(set(field_names)) or set(
            field_names
        ) != required_fields:
            raise ValueError(
                "Generated MODEL_CONFIG must contain exactly api_key, "
                "model_name, and base_url."
            )
