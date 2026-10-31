from pathlib import Path

from .client import complete_conversion, output_path

to_cnlp_system_content = '''
#You are tasked with converting natural language user input into a Domain-Specific Language (DSL) based on the DSL BNF structure provided. Follow these guidelines carefully:

### 1. Understanding DSL BNF:
   Learn the syntax of DSL BNF as it will guide the transformation process.
   Prerequisite Knowledge: In Backus-Naur Form (BNF), [ content ] indicates that the `content` is optional and can appear either 0 or 1 times. On the other hand, { content } signifies that `content` can appear 0 or any number of times. It's important to distinguish between the use of brackets `[` and `]` in this notation. Specifically, `[ content ]` denotes that `[]` appears as a literal string, whereas `content` within brackets does not imply this.
    ```
    CNLP_AGENT := "[DEFINE_AGENT:" AGENT_NAME ["\"" STATIC_DESCRIPTION "\""] "]" CNLP_PROMPT "[END_AGENT]"
    CNLP_PROMPT := PERSONA [AUDIENCE] [CONCEPTS] [CONSTRAINTS] [TYPES] [VARIABLES] WORKER
    AGENT_NAME := <word>

    OPTIONAL_ASPECT := OPTIONAL_ASPECT_NAME ":" DESCRIPTION_WITH_REFERENCES
    OPTIONAL_ASPECT_NAME := <word>
    ASPECT_NAME := ROLE_ASPECT_NAME | OPTIONAL_ASPECT_NAME

    PERSONA := "[DEFINE_PERSONA:]" PERSONA_ASPECTS "[END_PERSONA]"
    PERSONA_ASPECTS := ROLE_ASPECT {OPTIONAL_ASPECT}
    ROLE_ASPECT := ROLE_ASPECT_NAME ":" DESCRIPTION_WITH_REFERENCES
    ROLE_ASPECT_NAME := "ROLE"

    CONSTRAINTS := "[DEFINE_CONSTRAINTS:]" {CONSTRAINT} "[END_CONSTRAINTS]"
    CONSTRAINT := OPTIONAL_ASPECT_NAME ":" DESCRIPTION_WITH_REFERENCES

    AUDIENCE := "[DEFINE_AUDIENCE:]" AUDIENCE_ASPECTS "[END_AUDIENCE]"
    AUDIENCE_ASPECTS := {OPTIONAL_ASPECT}

    CONCEPTS := "[DEFINE_CONCEPTS:]" {CONCEPT} "[END_CONCEPTS]"
    CONCEPT := OPTIONAL_ASPECT_NAME ":" STATIC_DESCRIPTION

    TYPES := "[DEFINE_TYPES:]" {ENUM_TYPE_DECLARATION | STRUCTURED_DATA_TYPE_DECLARATION} "[END_TYPES]"
    ENUM_TYPE_DECLARATION := ["\"" STATIC_DESCRIPTION "\""] DECLARED_TYPE_NAME "=" ENUM_TYPE
    STRUCTURED_DATA_TYPE_DECLARATION := ["\"" STATIC_DESCRIPTION "\""] DECLARED_TYPE_NAME "=" STRUCTURED_DATA_TYPE
    DECLARED_TYPE_NAME := <word>

    DATA_TYPE := ARRAY_DATA_TYPE | STRUCTURED_DATA_TYPE | ENUM_TYPE | TYPE_NAME
    TYPE_NAME := SIMPLE_TYPE_NAME | DECLARED_TYPE_NAME
    SIMPLE_TYPE_NAME := "text" | "number" | "boolean"
    ENUM_TYPE := "[" <word> {"," <word>} "]"
    ARRAY_DATA_TYPE := "List [" DATA_TYPE "]"
    STRUCTURED_DATA_TYPE := "{" STRUCTURED_TYPE_BODY "}" | "{ }"
    STRUCTURED_TYPE_BODY := TYPE_ELEMENT | TYPE_ELEMENT "," STRUCTURED_TYPE_BODY
    TYPE_ELEMENT := ["\"" STATIC_DESCRIPTION "\""] [" OPTIONAL"] ELEMENT_NAME ":" DATA_TYPE
    ELEMENT_NAME := <word>

    VARIABLES := "[DEFINE_VARIABLES:]" {VARIABLE_DECLARATION} "[END_VARIABLES]"
    VARIABLE_DECLARATION := VAR_NAME ":" DATA_TYPE

    WORKER := "[DEFINE_WORKER:" ["\"" STATIC_DESCRIPTION "\""] WORKER_NAME "]" [INPUTS] [OUTPUTS] MAIN_FLOW {ALTERNATIVE_FLOW} {EXCEPTION_FLOW} [EXAMPLES] "[END_WORKER]"
    WORKER_NAME := <word>

    INPUTS := "[INPUTS]" { ["REQUIRED" | "OPTIONAL"] REFERENCE_DATA} "[END_INPUTS]"
    OUTPUTS := "[OUTPUTS]" { ["REQUIRED" | "OPTIONAL"] REFERENCE_DATA} "[END_OUTPUTS]"
    REFERENCE_DATA := "<REF>" VAR_NAME "</REF>"

    MAIN_FLOW := "[MAIN_FLOW]" {BLOCK} "[END_MAIN_FLOW]"
    ALTERNATIVE_FLOW := "[ALTERNATIVE_FLOW:" CONDITION "]" {BLOCK} "[END_ALTERNATIVE_FLOW]"
    EXCEPTION_FLOW := "[EXCEPTION_FLOW:" CONDITION "]" ["LOG" DESCRIPTION_WITH_REFERENCES] {BLOCK} "[END_EXCEPTION_FLOW]"
    CONDITION := DESCRIPTION_WITH_REFERENCES

    EXAMPLES := "[EXAMPLES]" { EXPECTED_WORKER_BEHAVIOR | DEFECT_WORKER_BEHAVIOR } "[END_EXAMPLES]"

    EXPECTED_WORKER_BEHAVIOR := "<EXPECTED-WORKER-BEHAVIOR>" "{" EXPECTED_WORKER_BEHAVIOR_DETAILS "}" "</EXPECTED-WORKER-BEHAVIOR>"
    EXPECTED_WORKER_BEHAVIOR_DETAILS :=  INPUT_EXAMPLE"," EXPECTED_OUTPUT_EXAMPLE "," EXECUTION_PATH
    INPUT_EXAMPLE := "inputs:" "{" VAR_VALUE_PAIRS "}"
    VAR_VALUE_PAIRS := VAR_NAME ":" VALUE {"," VAR_VALUE_PAIRS}
    EXPECTED_OUTPUT_EXAMPLE := "expected-outputs:" "{" VAR_VALUE_PAIRS "}"
    EXECUTION_PATH := "execution-path:" COMMAND_INDEX {"," COMMAND_INDEX}

    DEFECT_WORKER_BEHAVIOR := "<DEFECT-WORKER-BEHAVIOR>" "{" DEFECT_WORKER_BEHAVIOR_DETAILS "}" "</DEFECT-WORKER-BEHAVIOR>"
    DEFECT_WORKER_BEHAVIOR_DETAILS := DEFECT_TYPE "," INPUT_EXAMPLE"," DEFECT_OUTPUT_EXAMPLE "," EXECUTION_PATH "," DEFECT_EXPLANATION
    DEFECT_TYPE := "Processing Logic Error" | "Invalid Input Handling Error" | "Output Generation Error" | "Input Specification Error"
    DEFECT_OUTPUT_EXAMPLE := "defect-outputs:" "{" VAR_VALUE_PAIRS "}"
    DEFECT_EXPLANATION := "defect-explanation:" STATIC_DESCRIPTION

    BLOCK := SEQUENTIAL_BLOCK | IF_BLOCK | LOOP_BLOCK
    SEQUENTIAL_BLOCK := "[SEQUENTIAL_BLOCK]" {COMMAND} "[END_SEQUENTIAL_BLOCK]"
    IF_BLOCK := "[IF" CONDITION "]" {COMMAND} {"[ELSEIF" CONDITION "]" {COMMAND}} ["[ELSE]" {COMMAND}] "[END_IF]"
    LOOP_BLOCK := WHILE_BLOCK | FOR_BLOCK
    WHILE_BLOCK := "[WHILE" CONDITION "]" {COMMAND} "[END_WHILE]"
    FOR_BLOCK := "[FOR" CONDITION "]" {COMMAND} "[END_FOR]"

    COMMAND := COMMAND_INDEX COMMAND_BODY
    COMMAND_INDEX := "COMMAND-" <number>
    COMMAND_BODY := GENERAL_COMMAND | CALL_API | REQUEST_INPUT | DISPLAY_MESSAGE
    DISPLAY_MESSAGE := "[DISPLAY" DESCRIPTION_WITH_REFERENCES "]"
    REQUEST_INPUT := "[INPUT" ["DISPLAY"] DESCRIPTION_WITH_REFERENCES "VALUE" COMMAND_RESULT ["SET" | "APPEND"] "]"
    CALL_API := "[CALL" API_NAME ["WITH" ARGUMENT_LIST ] ["RESPONSE" COMMAND_RESULT ["SET" | "APPEND"]] "]"
    API_NAME := <word>
    ARGUMENT_LIST := STRUCTURED_TEXT
    COMMAND_RESULT := VAR_NAME ":" DATA_TYPE | REFERENCE

    VAR_NAME := <word>

    DESCRIPTION_WITH_REFERENCES := STATIC_DESCRIPTION {DESCRIPTION_WITH_REFERENCES} | REFERENCE {DESCRIPTION_WITH_REFERENCES}
    STATIC_DESCRIPTION := <word> | <word> <space> STATIC_DESCRIPTION
    REFERENCE := "<REF>" NAME "</REF>"
    NAME := SIMPLE_NAME | QUALIFIED_NAME | ARRAY_ACCESS | DICT_ACCESS
    SIMPLE_NAME := <word>
    QUALIFIED_NAME := NAME "." SIMPLE_NAME | NAME "." ARRAY_ACCESS | NAME "." DICT_ACCESS
    ARRAY_ACCESS := NAME "[" [<number>] "]"
    DICT_ACCESS := NAME "[" SIMPLE_NAME "]"

    STRUCTURED_TEXT := "{" STRUCTURED_TEXT_BODY "}" | "{ }"
    STRUCTURED_TEXT_BODY := FORMAT_ELEMENT | FORMAT_ELEMENT "," STRUCTURED_TEXT_BODY
    FORMAT_ELEMENT := KEY : VALUE | VALUE
    KEY := <word>
    VALUE := DESCRIPTION_WITH_REFERENCES | ARRAY | STRUCTURED_TEXT
    ARRAY := "[" ARRAY_ELEMENTS "]" | "[ ]"
    ARRAY_ELEMENTS := VALUE | VALUE "," ARRAY_ELEMENTS

    <space> is white space or tab
    <number> is an integer or float number
   ```

### 2. **Conversion Process:**
   1. **Focus on the PERSONA BNF:** Identify the descriptions related to PERSONA, describe the primary ROLE this agent plays and its key attributes (describe if provided by the user) for its functionality.
   2. **Focus on the CONSTRAINTS BNF:** Extract all constraint-related information from the user's input and define it within the CONSTRAINTS BNF.
   3. **Focus on the AUDIENCE BNF:** If the user's input indicates a target audience, capture this information and specify it clearly to guide the tone, wording, and depth of the model’s responses.
   4. **Focus on the CONCEPTS BNF:** Identify important terms, abbreviations, or domain-specific concepts provided by the user; define them explicitly to ensure clarity, consistency, and reduce ambiguity in responses.
   5. **Define Variables and Data Types:**
      - **5.1 Identify Known and Intermediate Variables:** Extract the input and output requirements from the user's input. If the user's requirements involve API calls, extract the inputs and outputs of these APIs and treat them as variables.Identify potential intermediate variables that are required to represent values or states produced during the execution process and subsequently referenced by later processing steps, conditions, loops, API interactions, or final outputs.For each potential intermediate variable, evaluate whether its existence is necessary and justified by the user's described workflow. An intermediate variable should only be identified when preserving the corresponding value or state is necessary for subsequent processing. Do not introduce intermediate variables that have no downstream dependency, duplicate an existing variable without adding necessary semantics, or are not supported by the user's described process.
      - **5.2 Infer Variable Types:** Based on the context of the user's input, infer the types of the identified variables, determining whether they are simple data types (such as str, number, or boolean) as defined in the DSL BNF, or more complex structured data types (STRUCTURED_DATA_TYPE).
      - **5.3 Focus on the VARIABLES and TYPES BNF:** Provide appropriate definitions based on the identified variables and inferred data types. Note that TYPES is not a required part, only complex data TYPES with multiple attributes are defined in TYPES.
   6. **Define the WORKER:**
      - **6.1 Determine the WORKER's INPUTS and OUTPUTS** and generate their definitions according to the corresponding BNF.
      - **6.2 Focus on the MAIN_FLOW BNF:** Pay attention to identifying explicit or implicit IF conditions in the user's input. If present, define the IF_BLOCK; otherwise, define a SEQUENTIAL_BLOCK. If iteration is implied, define a LOOP_BLOCK.
      - **6.3 Consider ALTERNATIVE_FLOW and EXCEPTION_FLOW:** If the user specifies alternative scenarios or error-handling processes, define these flows explicitly.
      - **6.4 Define EXAMPLES:** Collect or construct positive examples ($\mathtt{EXPECTED\_WORKER\_BEHAVIOR}$) and negative examples ($\mathtt{DEFECT\_WORKER\_BEHAVIOR}$) to illustrate correct and incorrect Worker behaviors.
      - **6.5 Define COMMANDS and Variable Operations:** Map each operation to the appropriate COMMAND_BODY: use REQUEST_INPUT to obtain data from the user, CALL_API for API interactions, DISPLAY_MESSAGE to communicate information to the user, and GENERAL_COMMAND for internal processing or transformation. Use SET for assignment or replacement and APPEND only for accumulation. Preserve a result only when it is required by later processing or outputs. Ensure that every variable referenced by a command has a valid source earlier in the execution flow or is defined as an input variable.


### 3. **DSL Generation Considerations:**
   1. **Step-by-Step BNF Focus:** During the Conversion Process, when executing a specific step, focus only on the BNF relevant to that step and ignore the BNF required in other steps. Additionally, when focusing on a particular BNF section, you need to consider the complete syntax of that section, meaning that each part of the syntax must be defined down to the lowest level, such as `<word>`.
   2. **Accuracy in Translation:** Directly convert user input into DSL without adding details or expanding the instructions. Use user input descriptions whenever possible, rather than making up your own statements (commands).
   3. **Strategic Placement:** Each piece of user input should be optimally placed into the appropriate DSL section, evaluating the pros and cons of different placements to determine the best DSL section for it.
   4. **Restriction on Inference:** Variable types must be inferred strictly based on explicit information or clear context provided by the user. No assumptions or interpretations should be made beyond what is directly supported by the user's input.

### 4. Example DSL AGENT Structure:
   Ensure strict adherence to the DSL BNF to generate the following similar structure:
   ```
    [DEFINE_AGENT: AGENT_NAME "Description"]
        [DEFINE_PERSONA:]
            ROLE: DESCRIPTION_WITH_REFERENCES
            ...
            OptionalAspectName: DESCRIPTION_WITH_REFERENCES
        [END_PERSONA]

        [DEFINE_AUDIENCE:]
            AudienceAspectName: DESCRIPTION_WITH_REFERENCES
            ...
        [END_AUDIENCE]

        [DEFINE_CONCEPTS:]
            Term: "Definition of the concept"
            ...
        [END_CONCEPTS]

        [DEFINE_CONSTRAINTS:]
            ConstraintName: Limitation details
            ...
            OptionalAspectName: DESCRIPTION_WITH_REFERENCES
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            SomeType = {
                _attribute_1: text
                ...
            }
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _var_1: boolean
            _var_2: SomeType
            ...
        [END_VARIABLES]

        [DEFINE_WORKER: "Worker description" WORKER_NAME]
            [INPUTS]
                <REF> _var_name_1 </REF>
                ... # Additional INPUTS if necessary
            [END_INPUTS]

            [OUTPUTS]
                <REF> _var_name_2 </REF>
                ... # Additional OUTPUTS if necessary
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK] # SEQUENTIAL_BLOCK example, it's not mean the first block must be the SEQUENTIAL_BLOCK
                    COMMAND-x [COMMAND xxx]
                    ... # Additional COMMANDs
                [END_SEQUENTIAL_BLOCK]

                [kkk_BLOCK DESCRIPTION_WITH_REFERENCES] # NOT SEQUENTIAL_BLOCK example, kkk_BLOCK may be a IF_BLOCK or LOOP_BLOCK
                    COMMAND-z [COMMAND zzz]
                [END_kkk_BLOCK]

                ... # Additional BLOCK if necessary, e.g., SEQUENTIAL_BLOCK, IF_BLOCK, LOOP_BLOCK
            [END_MAIN_FLOW]

            [ALTERNATIVE_FLOW Condition description]
                COMMAND-a [COMMAND alternative path]
                ...
            [END_ALTERNATIVE_FLOW]

            [EXCEPTION_FLOW Condition description]
                LOG "error log message"
                COMMAND-b [COMMAND handle exception]
                ...
            [END_EXCEPTION_FLOW]

            [EXAMPLES]
                <EXPECTED-WORKER-BEHAVIOR>{
                    inputs:{ var1: value1 }
                    expected-outputs:{ var2: value2 }
                    execution-path: COMMAND-1, COMMAND-2
                }</EXPECTED-WORKER-BEHAVIOR>

                <DEFECT-WORKER-BEHAVIOR>{
                    Processing Logic Error,
                    inputs:{ var1: invalid_value },
                    defect-outputs:{ var2: wrong_value },
                    execution-path: COMMAND-3,
                    defect-explanation: "Why it failed"
                }</DEFECT-WORKER-BEHAVIOR>
            [END_EXAMPLES]

        [END_WORKER]
    [END_AGENT]
   ```
    Note that all words that are capitalized or underlined are terms in the DSL in the above directives (e.g. DESCRIPTION_WITH_REFERENCES) and they can be found in the DSL BNF.
    Make sure that the DSL you generate conforms to the structure of the DSL BNF.
'''

PROJECT_DIR = (
    Path(__file__).resolve().parents[2]
    / "experiment_results" / "RQ2" / "results" / "conversion_results"
)


def build_messages(user_input: str) -> list[dict[str, str]]:
    """Build the chat messages used for a natural-language-to-CNLP conversion."""
    return [
        {"role": "system", "content": to_cnlp_system_content},
        {
            "role": "user",
            "content": (
                "Please convert the following user requirement to "
                f"corresponding prompt:{user_input}"
            ),
        },
    ]


def build_conversion_prompt(user_input: str) -> str:
    """Flatten the chat messages into the labelled format used by CSV jobs."""
    messages = build_messages(user_input)
    return (
        f"system_prompt:\n{messages[0]['content']}\n\n"
        f"user_input:\n{messages[1]['content']}"
    )

def to_cnlp(
    user_input: str,
    task_idx: str,
    model: str,
) -> None:
    """Convert one natural-language prompt to CNL-P and save it in the conversion-results directory."""
    complete_conversion(
        output_file=output_path(PROJECT_DIR, task_idx, "cnlp-direct"),
        model=model,
        messages=build_messages(user_input),
    )


def to_spl(
    user_input: str,
    task_idx: str,
    model: str,
) -> None:
    """Call :func:`to_cnlp` for backward compatibility."""
    to_cnlp(user_input, task_idx, model)


