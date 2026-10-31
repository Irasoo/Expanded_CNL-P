from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal, TypedDict

from dotenv import dotenv_values
from openai import OpenAI

from cnlp_compiler.semantic_analysis import SemanticAnalyzer
from experiments.RQ3.experiment_runtime import call_with_retry


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
CLEAN_VALIDATION_SENTENCE = (
    "If no error described by this prompt is found, return an empty JSON list: []."
)
LLM_MODEL = "gpt-5.6-sol"
LLM_REASONING_EFFORT = "high"


class PromptSection(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


def create_prompt_section(
    role: Literal["system", "user", "assistant"],
    content: str,
) -> PromptSection:
    return {"role": role, "content": content}


class RQ3LLMClient:
    """Small OpenAI-compatible client used only by the RQ3 experiment."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        organization: str = "",
        base_url: str = "",
        reasoning_effort: str = LLM_REASONING_EFFORT,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.organization = organization
        self.base_url = base_url
        self.reasoning_effort = reasoning_effort

    def complete(
        self,
        prompt: list[PromptSection],
        *,
        max_retries: int = 10,
        retry_delay_seconds: int = 15,
        attempt_log_path: Path | None = None,
        attempt_context: dict[str, Any] | None = None,
    ) -> str:
        client_arguments: dict[str, object] = {"api_key": self.api_key}
        if self.organization:
            client_arguments["organization"] = self.organization
        if self.base_url:
            client_arguments["base_url"] = self.base_url
        client = OpenAI(**client_arguments)

        def request() -> str:
            completion = client.chat.completions.create(
                model=self.model,
                n=1,
                messages=prompt,
                reasoning_effort=self.reasoning_effort,
            )
            if not completion.choices:
                raise RuntimeError(
                    "The LLM endpoint returned no completion choices."
                )
            choice = completion.choices[0]
            content = choice.message.content
            if not content or not content.strip():
                raise RuntimeError(
                    "The LLM endpoint returned an empty message.content "
                    f"(finish_reason={choice.finish_reason!r})."
                )
            return content

        return call_with_retry(
            request,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
            attempt_log_path=attempt_log_path,
            context=attempt_context,
        )


def create_llm_client(vals: dict[str, str | None]) -> RQ3LLMClient:
    api_key = vals.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Missing environment variable OPENAI_API_KEY.")

    base_url = (
        vals.get("OPENAI_BASE_URL")
        or vals.get("BASE_URL")
        or ""
    )
    return RQ3LLMClient(
        api_key=api_key,
        model=LLM_MODEL,
        organization=vals.get("OPENAI_ORG") or "",
        base_url=base_url,
        reasoning_effort=LLM_REASONING_EFFORT,
    )


class CNLPDataloader:
    def __init__(self, tasks_dir: str, task_filename: str):
        with open(os.path.join(tasks_dir, task_filename), 'r', encoding='utf-8') as file:
            self.json_data = json.load(file)

        self.instances = self.json_data['instance']
        self.total_instances = len(self.instances)

    def get_total_instances(self):
        return self.total_instances

    def get_instance_iterator(self):
        for instance in self.instances:
            yield {
                "id": instance['id'],
                "agent_name": instance['agent_name'],
                "global_variable": instance['global_variable'],
                "api_info": instance['api_info'],
                "schema": instance['schema'],
                "cnlp": instance['cnlp'],
                "reference_version": instance['reference_version']
            }


def build_semantic_analysis_system_prompt(
    global_variable: str,
    api_info: str,
    type_info: str,
    *,
    clean_validation: bool = False,
) -> str:
    system_prompt = f"""
    1. What is CNLP
    CNLP is a structured language that combines features of natural language with programming language characteristics. It is used to define the behavior and workflow of interactive intelligent agents. CNLP describes an agent's role, tasks, workflows, API calls, etc., enabling the agent to perform complex logic operations.

    CNLP consists of the following main parts:
    - DEFINE_AGENT: Defines the agent, including its role (Persona), constraints, data types, variables, and workflow.
    - DEFINE_PERSONA: Describes the agent’s role and function.
    - DEFINE_CONSTRAINTS: Specifies any constraints on the agent’s behavior.
    - DEFINE_TYPES: Describes data types, including simple types (e.g., '[]' can represent the 'list' type), enumerations, and structured types.
    - DEFINE_VARIABLES: Provides the typed catalog of Agent-state variable slots used by the Workers. An entry reserves a known state-variable name and type but does not initialize its runtime value. Therefore, a command's first executable declaration such as `name: Type` is not a duplicate merely because the same name appears in DEFINE_VARIABLES. A write target such as `RESPONSE <REF>name</REF> SET`, `VALUE <REF>name</REF> SET`, or `RESULT <REF>name</REF> SET` may perform the first runtime assignment to a cataloged state-variable slot; it does not require an earlier executable declaration. Reading that variable before any Worker input, external Global value, default value, or executable assignment supplies its value is still an error. The type of a global variable can be set as 'UnKnown' because its concrete value is supplied externally.
    - DEFINE_WORKER: Defines one Worker in the Agent, including its INPUTS, OUTPUTS, MAIN_FLOW, optional ALTERNATIVE_FLOW and EXCEPTION_FLOW sections, and commands. One Agent may contain multiple Workers.
    - ABOUT_COMMAND: "There are four types of commands: 'CALL' for calling either an external API or another Worker, where the 'RESPONSE' keyword is used as needed to handle return values; 'INPUT' for requesting user input, which must use the 'VALUE' keyword to store the input in a variable; 'COMMAND' as a regular command type that may use the 'RESULT' keyword to manage variable modifications; and 'DISPLAY' for printing content to the terminal, able to display variables of any type. The first three types can declare new temporary variables using 'var_name: var_type' or reassign existing ones using '<REF>var_name</REF>', but they cannot re-declare variables with the same name."

    Worker-call resolution rules:
    - First collect the exact symbol name of every DEFINE_WORKER in the current Agent.
    - If the target name following CALL exactly matches one of those Worker symbols, the command calls that Worker; do not look for that target in the external API list.
    - Otherwise, the CALL target is an external API and must exist in the supplied API Information.
    - In `CALL TargetWorker WITH {{formal_input: <REF>actual_variable</REF>}}`, each key is a formal INPUT name declared by TargetWorker, while its value is a variable available to the caller.
    - RESPONSE receives the called Worker's declared OUTPUT. A Worker with no OUTPUTS must not be called with RESPONSE.

    2. Differences Between Global and Temporary Elements in CNLP
    In CNLP, elements can be categorized as either global or temporary, applying to variables, types, and APIs:

    - Global Elements:
      - Global variables and global types are supplied as Background Data for the current dataset instance and can be referenced by its Workers.
      - APIs are external to the CNL-P text and must be predefined in the API Information supplied for the current dataset instance.

    - Temporary Elements:
      - Temporary variables and types are defined and used only within the current CNLP instance. They are usually declared in DEFINE_TYPES and DEFINE_VARIABLES and are not accessible in other CNLP instances.

    Runtime variable rules:
    - DEFINE_VARIABLES is only the catalog described above; do not count its entries as executable declarations.
    - Worker INPUTS and OUTPUTS contain interface references. They do not create local variables and do not conflict with a global variable of the same name.
    - A Worker's INPUTS are available when that Worker starts. A value written by the Worker and listed in OUTPUTS can be returned to its caller.
    - Global variables supplied in Background Data are available at the beginning of every Worker flow.
    - `name: Type` in VALUE, RESPONSE, or RESULT is an executable temporary-variable declaration. `<REF>name</REF>` in a write-target position assigns a state-variable slot already cataloged in DEFINE_VARIABLES, supplied globally, or made available as a Worker INPUT; the assignment may be that slot's first runtime value.
    - Report a duplicate declaration only when the same temporary variable is executably declared more than once on a relevant flow path. Report a global naming conflict only when an executable `name: Type` declaration attempts to create a temporary variable whose name already belongs to a supplied global variable.

    Built-in type compatibility rules:
    - `text`, `str`, and `string` are equivalent text types.
    - `bool` and `boolean` are equivalent boolean types.
    - `int` is compatible with `float` and `number`; `float` is compatible with `number`.
    - A structured record type is compatible with `dict`.

    3. All Possible Error Types in CNLP and Their Explanation
    To ensure CNLP correctness, here are all potential error types, each with an explanation:

    3.1 Reference-Related Errors
    - 3.1.1 Referencing Non-Existent Global Variables: Referring to variables not defined globally. For example, referencing <REF>_user_preference</REF> in the PERSONA section when it doesn't exist globally.
    - 3.1.2 Using Undeclared Variables: Using variables in the workflow that are not declared in DEFINE_VARIABLES or globally.
    - 3.1.3 Duplicate Variable Declaration: Executably declaring the same temporary variable more than once. Do not count its descriptive entry in DEFINE_VARIABLES as a declaration.
    - 3.1.4 Variables Undefined in Conditional Branches: Variables may not be properly defined or assigned in some branches of IF/ELSEIF/ELSE, leading to issues later.

    3.2 Type-Related Errors
    - 3.2.1 Target Type Not Found: Using a type that hasn't been defined in DEFINE_TYPES or the global schema.
    - 3.2.2 API Parameter Type Mismatch: Passing parameters to an API with types that do not match the API's expected types after applying the built-in compatibility rules above. When the parameter is a global variable with an unknown type, it should be compared with the defined value type.
    - 3.2.3 API Return Type Mismatch: The type of the API's return value doesn't match the type of the receiving variable after applying the built-in compatibility rules above.

    3.3 API Call-Related Errors
    - 3.3.1 Calling Non-Existent APIs: Attempting to call an API that is not defined in the global API list.
    - 3.3.2 Extraneous API Parameters: Providing more parameters than the API definition requires.
    - 3.3.3 Missing API Parameters: Failing to provide all necessary parameters for an API call.
    - 3.3.4 Unhandled API Return Values: API returns a result, but it is not stored or processed.
    - 3.3.5 Improper Handling of API Return Values: Attempting to capture a return value from an API that doesn’t return any.

    3.4 Global Variable Conflict Errors
    - 3.4.1 Global Variable Naming Conflicts: An executable `name: Type` declaration in VALUE, RESPONSE, or RESULT creates a temporary variable with the same name as a supplied global variable. Merely listing or referencing a global variable in DEFINE_VARIABLES, INPUTS, OUTPUTS, PERSONA, CONSTRAINTS, or a command argument is not a conflict.

    3.5 Worker Call Contract Errors
    - 3.5.1 Missing Required Worker Inputs: A CALL to another Worker omits an INPUT marked REQUIRED by the target Worker.
    - 3.5.2 Extraneous Worker Inputs: A CALL supplies a formal input name that is not declared in the target Worker's INPUTS.
    - 3.5.3 Worker Input Type Mismatch: A caller variable supplied to a Worker INPUT has a type incompatible with the corresponding interface variable.
    - 3.5.4 Unexpected Worker Return Handling: A CALL declares RESPONSE even though the target Worker has no OUTPUTS.

    3.6 Example Execution Path Errors
    - 3.6.1 Mutually Exclusive Branches: An execution-path cannot contain commands from two or more mutually exclusive branches of the same IF/ELSEIF/ELSE block.
    - 3.6.2 Non-Existent Command: Every COMMAND-N in an execution-path must exist in the same Worker that owns the Example.
    - 3.6.3 Output-Path Inconsistency: Every field in expected-outputs must be produced by a command included in that Expected Example's execution-path, unless the value is already a Worker input.

    EXAMPLES are illustrative behavioral records. Do not report missing Worker inputs, ordinary value-type differences, or the intentionally incorrect business result described by DEFECT-WORKER-BEHAVIOR as CNL-P errors. For DEFECT-WORKER-BEHAVIOR, only validate that its command references exist and that it does not combine mutually exclusive branches.

    Scope boundary:
    - Check only formal static semantics that can be established from AST structure, symbol resolution, declarations, types, control flow, Example execution paths, API signatures, and Worker interfaces.
    - Do not judge whether natural-language descriptions are sensible, truthful, complete, aligned with business intent, or behaviorally consistent with PERSONA, CONSTRAINTS, Worker descriptions, commands, APIs, or other prose.
    - PERSONA and CONSTRAINTS are checked only for formal errors such as references to non-existent supplied global variables; their natural-language meaning is outside the analysis scope.

    4. Error Return Format
    Return only a valid JSON list of dictionaries containing two key fields: error_path and error_reason. Do not add Markdown fences, analysis, headings, or explanatory prose before or after the JSON list.

    Important: The error_path should identify PERSONA, CONSTRAINTS, or the relevant Worker and Flow. It should not point to DEFINE_VARIABLES or DEFINE_TYPES merely because those sections catalog a name or type; when an invalid declaration or type is used by a command, point to that command.

    Error Path Explanation
    The error path identifies where the error occurs in the CNLP instance, including but not limited to:
    - persona.ROLE: Indicates an error in the persona definition.
    - workers.NewsWorkflow.main_flow.if_block1.command4: Indicates an error in COMMAND-4 inside NewsWorkflow's Main Flow.
    - workers.NewsWorkflow.main_flow.command2: Indicates an invalid call made by NewsWorkflow.

    Error Return Format Example:

    If an error occurs in the PERSONA section:
    Example CNLP:
    ROLE: You are a news assistant looking up various current events, the specific task information is subject to <REF>_user_preferences</REF>.
    If _user_preferences is undeclared, the error would be:

    [
        {{
            "error_path": "persona.ROLE.reference1",
            "error_reason": "The variable '_user_preferences' referenced in <REF>_user_preferences</REF> is not declared in the DEFINE_VARIABLES section or globally."
        }}
    ]

    5. Background Data
    - Global Variable: {global_variable}
    - API Information (If the API description lacks a return statement, it means the API doesn't return any value): {api_info}
    - Global Type(s): {type_info}
    """
    if clean_validation:
        system_prompt += "\n" + CLEAN_VALIDATION_SENTENCE
    return system_prompt


def check_cnlp_by_llm(
    global_variable: str,
    api_info: str,
    type_info: str,
    cnlp: str,
    *,
    clean_validation: bool = False,
    max_retries: int = 10,
    retry_delay_seconds: int = 15,
    attempt_log_path: Path | None = None,
    attempt_context: dict[str, Any] | None = None,
):
    chat_client = create_llm_client(
        vals=dotenv_values(WORKSPACE_ROOT / ".env")
    )
    system_prompt = build_semantic_analysis_system_prompt(
        global_variable,
        api_info,
        type_info,
        clean_validation=clean_validation,
    )

    messages = [
        create_prompt_section(role="system", content=system_prompt),
        create_prompt_section(role="user", content=cnlp)
    ]
    return chat_client.complete(
        messages,
        max_retries=max_retries,
        retry_delay_seconds=retry_delay_seconds,
        attempt_log_path=attempt_log_path,
        attempt_context=attempt_context,
    )


def check_cnlp_by_linting(
    cnlp: str,
    *,
    global_variable: str,
    api_info: str,
    type_info: str,
):
    report = SemanticAnalyzer().analyze_source(
        cnlp,
        global_variables=global_variable,
        apis=api_info,
        schema=type_info,
    )
    return [
        {
            "error_code": diagnostic.code,
            "error_path": diagnostic.path,
            "error_reason": diagnostic.message,
        }
        for diagnostic in report.diagnostics
    ]




