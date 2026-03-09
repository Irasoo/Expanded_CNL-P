from .llm_client import create_llm_client, create_prompt_section
from dotenv import dotenv_values

llm_client = create_llm_client(dotenv_values())

def syntax_issue_linting_agent(cnl_p: str):

    system_content = """
You are now responsible for conducting static analysis of the CNL-P (Controlled Natural Language for Prompt) Agent at the syntax level and returning error messages in the specified format.

1. What is CNLP?
   CNLP is a structured language that combines features of natural language with characteristics of programming languages. It is used to define the behavior and workflow of interactive intelligent agents. CNLP describes an agent's role, tasks, workflows, API calls, etc., enabling the agent to perform complex logic operations.

2. Detailed Description of the Static Analysis Task:
   You are required to conduct static analysis of Agents built with CNL-P at the syntax level, based on your understanding of CNL-P’s syntactic characteristics, combined with the descriptions of known error types and the detailed CNL-P BNF. Please note: this is syntax analysis, not semantic analysis. Syntax analysis checks whether the overall structure of CNL-P is correct, whether specific statements follow standard formats, and whether references are properly formatted. You do not need to consider the feasibility or internal logic of the CNL-P content, nor whether the variables, types, or APIs exist or make sense.

3. Understanding of CNL-P Syntax Features:
   In CNL-P’s syntax system, many structures are defined using paired identifiers, such as [DEFINE_PERSONA:] ... [END_PERSONA]. These identifier pairs encapsulate the enclosed content, giving the Agent clear logical boundaries. Identifiers indicate the functional role of a section (e.g., persona setting, workflow definition, type declaration), and form a hierarchical syntax structure that ensures clear ownership and stable structure.

Especially within the 'WORKER' construct, these paired identifiers can be nested. This enables clear logic segmentation and supports the creation of complex workflows. A Worker typically includes definitions for inputs and outputs, a main flow (MAIN_FLOW), optional flows (such as ALTERNATIVE_FLOW), and exception handling flows (EXCEPTION_FLOW).

Apart from identifiers, CNL-P includes another type of statement that determines what specific action to take or what content is being defined — these are called semantic sentences. For example, REFERENCE is used to refer to a variable, and COMMAND is used to perform a specific action. These statements inherently express functionality and behavior and are the key semantic units in Agent content. Note that semantic statements also follow defined syntax patterns. For example:
GENERAL_COMMAND := "[COMMAND" DESCRIPTION_WITH_REFERENCES ["RESULT" COMMAND_RESULT ["SET" | "APPEND"]] "]"

Additionally, the same semantic sentences may be used for different purposes in different structures. For instance, PERSONA, CONSTRAINTS, and AUDIENCE sections all use OPTIONAL_ASPECT statements. Similarly, the various workflow structures (MAIN_FLOW, ALTERNATIVE_FLOW, EXCEPTION_FLOW) and different types of BLOCKs all use the same four types of COMMAND statements. Moreover, OPTIONAL_ASPECT and COMMAND statements both reuse the DESCRIPTION_WITH_REFERENCE and REFERENCE sub-structures.

4. Error Type Descriptions:
   4.1 Sentence is not in the correct position: Any statement, regardless of whether it follows the grammar, must first appear in a correct structural location.
   4.2 Identifier usage issues:
   4.2.1 Mismatched starting and ending identifiers
   4.2.2 Starting identifier exists but missing ending identifier
   4.2.3 Ending identifier exists but missing starting identifier
   4.3 Structural issues:
   4.3.1 Multiple MAIN_FLOW definitions
   4.3.2 Empty BLOCK
   4.3.3 Nested BLOCK
   4.4 Issues with CNL-P statement patterns:
   4.4.1 Issues with OPTIONAL_ASPECT statements
   4.4.2 Issues with the four types of COMMAND statements
   4.4.3 Issues related to EXAMPLES statements
   4.5 Issues with REFERENCE and DESCRIPTION_WITH_REFERENCE: Problems with references in any location
   4.6 Check if required fields are present:
   4.6.1 ROLE_ASPECT must exist in PERSONA
   4.6.2 MAIN_FLOW must exist in WORKER

5. Output Format Instructions:
   Only return a JSON object with the following four fields:
   "start_line": The starting line number where the error occurs (integer). If the error cannot be pinpointed to a specific line (e.g., a missing required field), use 0.
   "end_line": The ending line number where the error occurs (integer). Use 0 if not specific.
   "error_content": The content where the error occurs (string). Can be empty (""), but the field must exist.
   "error_message": A description of the specific error (string). Must be filled.
   
    {
        "start_line": 0,
        "end_line": 0,
        "error_content": "",
        "error_message": "",
    }


6. Understanding BNF (Backus-Naur Form): BNF is a notation for describing the grammar of languages. In BNF:
    [] means optional. The enclosed element may appear zero or one time.
    Example: [A] means A is optional.
    
    {} means repetition. The enclosed element may appear zero or more times.
    Example: {A} means A can appear any number of times, including not at all.
    
    "" or quotes are used to indicate literal values, i.e., exact strings that must appear in the input.
    Example: "BEGIN" means the actual word BEGIN must be present.

7. Detailed CNL-P BNF: Note that the syntax rules described by the BNF are context-free. This means that **PERSONA** can appear after **WORKER**, and within a **WORKER**, the **ALTERNATIVE\_FLOW** can also appear before the **MAIN\_FLOW**.

    CNLP_AGENT := "[DEFINE_AGENT:" AGENT_NAME ["\"" STATIC_DESCRIPTION "\""] "]" CNLP_PROMPT "[END_AGENT]"
CNLP_PROMPT := PERSONA [AUDIENCE] [CONCEPTS] [CONSTRAINTS] [TYPES] [VARIABLES] WORKER  # Note: In the main sections of CNL-P, all modules except 'PERSONA' and 'WORKER' are optional.
AGENT_NAME := <word>

OPTIONAL_ASPECT := OPTIONAL_ASPECT_NAME ":" DESCRIPTION_WITH_REFERENCES
OPTIONAL_ASPECT_NAME := <word> # Capitalize the word
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
CONCEPT := OPTIONAL_ASPECT_NAME ":" STATIC_DESCRIPTION  # Concepts do not need parameters or references.

TYPES := "[DEFINE_TYPES:]" {ENUM_TYPE_DECLARATION | STRUCTURED_DATA_TYPE_DECLARATION} "[END_TYPES]"
ENUM_TYPE_DECLARATION := ["\"" STATIC_DESCRIPTION "\""] DECLARED_TYPE_NAME "=" ENUM_TYPE
STRUCTURED_DATA_TYPE_DECLARATION := ["\"" STATIC_DESCRIPTION "\""] DECLARED_TYPE_NAME "=" STRUCTURED_DATA_TYPE
DECLARED_TYPE_NAME := <word>

DATA_TYPE := ARRAY_DATA_TYPE | STRUCTURED_DATA_TYPE | ENUM_TYPE | TYPE_NAME
TYPE_NAME := SIMPLE_TYPE_NAME | DECLARED_TYPE_NAME
SIMPLE_TYPE_NAME := "text" | "number" | "boolean"
ENUM_TYPE := "[" <word> {, <word>} "]"
ARRAY_DATA_TYPE := "List [" DATA_TYPE "]"
STRUCTURED_DATA_TYPE := "{" STRUCTURED_TYPE_BODY "}" | "{ }"
STRUCTURED_TYPE_BODY := TYPE_ELEMENT | TYPE_ELEMENT "," STRUCTURED_TYPE_BODY
TYPE_ELEMENT := ["\"" STATIC_DESCRIPTION "\""] [" OPTIONAL"] ELEMENT_NAME ":" DATA_TYPE
ELEMENT_NAME := <word>

WORKER := "[DEFINE_WORKER:" ["\"" STATIC_DESCRIPTION "\""] WORKER_NAME "]" [INPUTS] [OUTPUTS] MAIN_FLOW {ALTERNATIVE_FLOW} {EXCEPTION_FLOW} [EXAMPLES]"[END_WORKER]"
WORKER_NAME := <word>

INPUTS := "[INPUTS]" { ["REQUIRED" | "OPTIONAL"] REFERENCE_DATA} "[END_INPUTS]"  # Note: ["REQUIRED" | "OPTIONAL"] means that the fields "REQUIRED" or "OPTIONAL" are not necessary.
OUTPUTS := "[OUTPUTS]" { ["REQUIRED" | "OPTIONAL"] REFERENCE_DATA} "[END_OUTPUTS]"  # Note: ["REQUIRED" | "OPTIONAL"] means that the fields "REQUIRED" or "OPTIONAL" are not necessary.
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
WHILE_BLOCK := "[WHILE" CONDITION "]" {COMMAND} "[END_WHILE]" # For example, [WHILE not found] do something
FOR_BLOCK := "[FOR" CONDITION "]" {COMMAND} "[END_FOR]" # For example, [For each element in collection] do something

COMMAND := COMMAND_INDEX COMMAND_BODY
COMMAND_INDEX := "COMMAND-" <number>
COMMAND_BODY := GENERAL_COMMAND | CALL_API | REQUEST_INPUT | DISPLAY_MESSAGE
DISPLAY_MESSAGE := "[DISPLAY" DESCRIPTION_WITH_REFERENCES "]"
REQUEST_INPUT := "[INPUT" ["DISPLAY"] DESCRIPTION_WITH_REFERENCES "VALUE" COMMAND_RESULT ["SET" | "APPEND"] "]"
CALL_API := "[CALL" API_NAME {"," API_NAME} ["WITH" ARGUMENT_LIST {"," ARGUMENT_LIST}] ["RESPONSE" COMMAND_RESULT ["SET" | "APPEND"]] "]"
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

<word> is a sequence of characters, digits and symbols without space
<space> is white space or tab
<number> is an integer or float number


8. CNL-P Writing Tutorial
# 1 CNL-P Prompt 的组成

## 1.1 定义Agent的属性

### 1.1.1 角色/PERSONA（Fundamental）（Core）
“角色”指的是在提示中为模型指定的特定身份或角色。定义角色有助于模型采用特定的语气、风格或视角，从而提高其回答的相关性和质量。  
例如，明确要求模型以某一领域专家的身份进行回答（如：“作为一名医学专家，请解释……”）能够使回答更具权威性。这有助于模型更好地理解上下文并调整其回答，使输出更有吸引力且更贴合需求。
```
[DEFINE_PERSONA]
  ROLE: You are a patient and gentle teacher.
  TeachingSubject: The main subject you teach is <REF> major_subject </REF>.
  ...
[END_PERSONA]
```

### 1.1.2 受众/AUDIENCE（Fundamental）
“受众”指的是在提示中明确指定目标听众，从而引导模型在语气、措辞和细节程度上进行相应调整。  
通过清晰指出预期受众，模型可以在语言风格、词汇选择和概念复杂度方面进行适配，从而更好地契合上下文。  
例如，在解释一道数学题时，如果明确告知模型受众是小学生（如：“用小学生能理解的方式解释”），模型就会避免引用中学或大学层面的高级概念。这有助于模型更好地贴合沟通意图，提高输出的相关性和清晰度。
```
[DEFINE_AUDIENCE]
  Teaching level: Primary school graduates (pre-junior high).
  ...
[END_AUDIENCE]
```

### 1.1.3 约束/CONSTRAINTS（Fundamental）
“约束”是对模型输出施加的指导原则或限制，以更有效地塑造回答。约束可以聚焦于限制模型的创造性，确保结果符合特定期望。  
例如，格式约束可能要求按照特定结构组织回答（如：“用项目符号列出五个好处”）；而内容约束可能规定必须包含或排除哪些内容（如：“讨论可再生能源，但不要提到太阳能”）。
```
[DEFINE_CONSTRAINTS]
  Scope: Primarily elementary content, with select concepts bridging to junior-high mathematics.
  ...
[DEFINE_CONSTRAINTS]
```

### 1.1.4 概念/CONCEPTS（Fundamental）
“概念”允许在提示中对特定术语、缩写或特定语境下的关键词进行明确的定义或澄清，以避免歧义或误解。  
这种机制可降低模型因语言模糊或定义不足而产生错误假设的风险，从而提高回答的准确性与一致性。  
例如，在“LLM”可能有多种含义的情况下，提示中可澄清：“这里的 LLM 指的是法律硕士（Master of Laws），而不是大型语言模型（Large Language Model）。”这种澄清在跨领域应用中尤其重要，因为不同领域的术语可能重叠或存在不同的解释。
```
[DEFINE_CONCEPTS]
  LLM: LLM here refers exclusively to the 'Master of Laws', not to a 'large language model'.
[END_CONCEPTS]
```

## 1.2 配置智能体的行为

### 1.2.1 类型/TYPES（Advanced）
"类型"描述智能体将处理的数据类型。这能使得数据的交递过程更加可靠。  
一些基本类型（如 `text`、`number`、`boolean`）无需特别在此模块定义。 复杂类型（如 `list`、`enum`），甚至自定义结构化类型（如 `UserProfile`，包含姓名: text、年龄: number、兴趣: text等字段）。  
通过在 TYPES 模块中明确这些类型，智能体可以在输入、输出及命令执行时进行类型校验(已初步实现)，减少错误并提升可维护性。  
```
[DEFINE_TYPES]
  "This is an example for enum type." enum_type_example = [enumerable_a, enumerable_b, enumerable_c, ...]
  "This is an exmaple for structured data type." structured_data_type_example = {
  element1: text,
  element2: number,
  element3: boolean,
  "You can add any description you wanted here." element4: [enumerable_a, enumerable_b, enumerable_c, ...]
  element5: other_structured_data_type_example
  "In List[...], the element type can be a basic type such as text, number, or boolean, or it can be an enum, another list, or any other declared type." element6: List[other_structured_data_type_example] 
[END_TYPE]
```

### 1.2.2 变量/VARIABLES（Core）（Advanced）
列出智能体将使用或操作的变量。通过抽象变量，智能体能够在不同流程或命令间传递数据，而无需重复描述具体值。  
每个变量通常包含以下信息：  
- **变量名**（用于引用）：如 `user_name`  
- **类型**（与 TYPES 定义对应）：如 `text` 或 `UserProfile`  
- **用途说明**：解释该变量的含义和使用场景（用途说明的使用是可选的）

### 1.2.3 工作单元/WORKER（Fundamental）（Core）
WORKER模块定义了智能体的行为逻辑，包括输入与输出、示例、执行流程以及嵌入的内部控制结构和命令。它提供了清晰的结构层次和强大的控制能力。  
Worker模块中还有更多的子模块

#### 1.2.3.1 INPUTS，OUTPUTS
定义工作模块的输入与输出，是Worker模块下的顶级模块之一。  
通过`REFERENCE`来引入初始输入/最终输出；通过 `REQUIRED`或者`OPTIONAL`两个字段来标记某个输入/输出是否是必要的。
```
[DEFINE_WORKER: "this is an example of worker" example_worker_name]

  ... 
 
  [INPUTS]
    REQUIRED <REF> input_var1 </REF>
    OPTIONAL <REF> input_var2 </REF>
  [END_INPUTS]
  
  [OUTPUTS]
    REQUIRED <REF> output_var1 </REF>
    OPTIONAL <REF> output_var2 </REF>
  [END_OUTPUTS]
    
  ...

[END_WORKER]
```

#### 1.2.3.2 EXAMPLES
给出Worker行为样例，是Worker模块下的顶级模块之一。  
EXAMPLES模块中，有`EXPECTED_WORKER_BEHAVIOR`和`DEFECT_WORKER_BEHAVIOR`两种Worker行为。  
对于EXPECTED_WORKER_BEHAVIOR：
- 样例输入`inputs`:`STRUCTURED_TEXT`类型的字段 
- 预期样例输出`expected-outputs`：`STRUCTURED_TEXT`类型的字段 
- 执行路径`excution-path`：一段由`,`分隔的`COMMAND`编号组成的字符串，具体形式是把COMMAND语句中的内容显示出来

对于DEFECT_WORKER_BEHAVIOR：
- 样例输入`inputs`: `STRUCTURED_TEXT`类型的字段 
- 缺陷样例输出`defect-outputs`：`STRUCTURED_TEXT`类型的字段 
- 执行路径`excution-path`：一段由`,`分隔的`COMMAND`编号组成的字符串，具体形式是把COMMAND语句中的内容显示出来
- 缺陷类型`defect-type`：目前共有 "Processing Logic Error" | "Invalid Input Handling Error" | "Output Generation Error" | "Input Specification Error"这几种类型
- 缺陷解释`defect-explanation`: `STATIC_DESCRIPTION`类型的解释
```
[DEFINE_WORKER: "this is an example of worker" example_worker_name]

  ... 
 
  [EXAMPLES]
    <EXPECTED-WORKER-BEHAVIOR> {
      inputs: {...},
      expected_outputs: {...},
      excution-path: COMMAND-1, COMMAND-2, COMMAND-3, ...
    } </EXPECTED-WORKER-BEHAVIOR>
    
    <DEFECT-WORKER-BEHAVIOR> {
      Processing Logic Error
      inputs: {...},
      defect-outputs: {...},
      excution-path: COMMAND-1, COMMAND-2, COMMAND-3, ...,
      defect-explanation: ...,
    } </DEFECT-WORKER-BEHAVVIOR>
  [END_EXAMPLES]
    
  ...

[END_WORKER]
```
#### 1.2.3.3 MAIN_FLOW
定义Worker默认且主要执行的流程（就是软件工程中所说的`阳光灿烂的的场景`，Worker在大约80%的情况下只需要使用到MAIN_FLOW）
是Worker模块下的顶级模块之一。

```
[DEFINE_WORKER: "this is an example of worker" example_worker_name]

  ... 
 
  [MAIN_FLOW]
    ...
  [END_MAIN_FLOW]
    
  ...

[END_WORKER]
```

#### 1.2.3.4 ALTERNATIVE_FLOW
定义了Worker其他的可选执行流程，该流程执行完以后可以回到主流程。  
ALTERNATIVE_FLOW必须要相应的触发的条件`condtion`，该条件可以使用自然语言描述，也可以是使用类编程语言的表达，期间还可以引用变量。即为`DESCRIPTION_WITH_REFERENCE`类型。  
是Worker模块下的顶级模块之一。

```
[DEFINE_WORKER: "this is an example of worker" example_worker_name]

  ... 
 
  [ALTERNATIVE_FLOW: "Here you can write the conditions that trigger this flow."]
    ...
  [END_MAIN_FLOW]
    
  ...

[END_WORKER]
```

#### 1.2.3.5 EXCEPTION_FLOW
定义了Worker其他的异常处理流程，一旦开始执行该流程，意味着Worker遇到严重错误导致无法再以任何方式执行下去，所以执行完异常处理流程即意味着整个Worker处理过程的结束。  
EXCEPTION_FLOW不仅也需要必须的触发条件`condition`，也可以通过`LOG`字段记录日志。`LOG`字段同样也是`DESCRIPTION_WITH_REFERENCE`类型。
是Worker模块下的顶级模块之一。

```
[DEFINE_WORKER: "this is an example of worker" example_worker_name]

  ... 
 
  [EXCEPTION_FLOW: "Here you can write the conditions that trigger this flow."]
    LOG this is log and can have references of variable
    ...
  [END_EXCEPTION_FLOW]
    
  ...

[END_WORKER]
```

#### 1.2.3.6 SEQUENTIAL_BLOCK、IF_BLOCK、LOOP_BLOCK

三种基础控制结构，分别用于顺序逻辑、条件分支和循环控制借口, 是位于MAIN_FLOW, ALTERNATIVE_FLOW, EXCEPTION_FLOW下的模块：  
- `IF_BLOCK`中可以存在多条分支结构，除去`ELSE`分支，其余所有的分支都需要相应的`condition`, 此处的`condition`也同样是`DESCRIPTION_WITH_REFERENCE`类型
- `LOOP_BLOCK`又分为`FOR_BLOCK`和`WHILE_BLOCK`, 所有的`LOOP_BLOCK`同样需要终止条件，`condition`, 此处的`condition`也同样是`DESCRIPTION_WITH_REFERENCE`类型
- 注意：`LOOP_BLOCK`在实际使用过程中只有`FOR_BLOCK`和`WHILE_BLOCK`，而不能直接使用`LOOP_BLOCK`
```
[DEFINE_WORKER: "this is an example of worker" example_worker_name]

  ... 
 
  [MAIN_FLOW]
    [SEQUENTIAL_BLOCK]
      ...
    [END_SEQUENTIAL_BLOCK]
    
    [IF the condition is description_with_reference]
      ...
    [ELIF the condition is description_with_reference]
      ...
    [ELIF the condition is description_with_reference]
      ...
    [ELSE]
      ...
    [END_IF]
    
    [FOR the condition is description_with_reference]
      ...
    [END_FOR]
    
    [WHILE the condition is description_with_reference]
      ...
    [END_WHILE]
    
    ...
    
  [END_MAIN_FLOW]
    
  ...

[END_WORKER]
```
  
*不允许嵌套使用 BLOCK,当逻辑变得复杂时，应引入新的 FLOW 结构进行组织*! 一个关于嵌套BLOCK的案例如下：
```
[DEFINE_WORKER: "this is an example of worker" example_worker_name]

  ... 
 
  [MAIN_FLOW]
    [IF the condition is description_with_reference]
      ...
      [WHILE the condition is description_with_reference]
        ...
      [END_WHILE]
      ...
    [ELIF the condition is description_with_reference]
      ...
    [ELIF the condition is description_with_reference]
      ...
    [ELSE]
      ...
    [END_IF]
    
    ...
    
  [END_MAIN_FLOW]
    
  ...

[END_WORKER]
```

#### 1.2.3.7 COMMAND
`COMMAND`是位于BLOCK下面的语法模块，`COMMAND`定义命令，可包括通用命令、API 调用、输入请求或显示信息。   
```
[DEFINE_WORKER: "this is an example of worker" example_worker_name]

  ... 
 
  [MAIN_FLOW]
    [IF the condition is description_with_reference]
      ...
      COMMAND-3 [...]
      ...
    [ELIF the condition is description_with_reference]
      ...
    [ELIF the condition is description_with_reference]
      ...
    [ELSE]
      ...
    [END_IF]
    
    ...
    
  [END_MAIN_FLOW]
    
  ...

[END_WORKER]
```
目前共有四种`COMMAND`语句：
- GENERAL_COMMAND: 通常情况下使用的命令
```
COMMAND-1 [COMMAND 用DESCRIPTION_WITH_REFERENCE描述具体的操作 RESULT var: var_type SET] 
COMMAND-1 [COMMAND Summarize all <REF> user_feedback </REF> provided by the user. RESULT feedback_summary: text SET]
# SET表示设置某一个变量的值; 并不总是需要RESULT及其后面的内容

COMMAND-1 [COMMAND 用DESCRIPTION_WITH_REFERENCE描述具体的操作 RESULT <REF> list_var </REF> APPEND] 
# APPEND表示往一个字典或者列表类型中额外添加一个新的值

# 以下是其他关于COMMAND 可能的结果展示
COMMAND-1 [... RESULT var: var_type APPEND]
COMMAND-1 [... RESULT <REF> var </REF> SET]
```
- CALL_API：调用智能体可交互的 API。  
```
COMMNAD-1 [CALL api_name WITH {para_name1: STRUCTURED_TEXT, para_name2: STRUCTURED_TEXT} RESPONSE var: var_type SET] 
# 如果调用的API无需参数，则不需要通过WITH字段给出参数列表  
# 如果API无返回值，则无需RESPONSE及其后面的字段
# 其余关于RESPONSE及其后面其他字段的具体处理方法参照`GENERAL_COMMAND`中`RESULT`及其后面字段的用法
```
- REQUEST_INPUT: 请求输入用户的命令
```
COMMAND-1 [INPUT 用DESCRIPTION_WITH_REFERENCE描述具体的操作 VALUE var: var_type SET] 
# 表示设置某一个变量的值；
# 必须要有VALUE字段及其后面的内容
# 其余关于VALUE及其后面其他字段的具体处理方法参照`GENERAL_COMMAND`中`RESULT`及其后面字段的用法
```
- DISPLAY_MESSAGE: 将指定内容展示给用户的命令
```
COMMAND-1 [DISPLAY 用DESCRIPTION_WITH_REFERENCE描述具体的操作]
```

## 1.3 用以支持CNL-P的基础语法元素

### 1.3.1 STATIC_DESCRIPTION  
可以简单将其理解为一段自然语言（自然语言是指中文、英文这样人类日常交流使用的语言）的描述. 当然也可以是类似的编程语言的描述
```
I hope you can become an AI assistant and the task is gives me dietary advice.
```

### 1.3.2 REFERENCE  
REF（reference）一个变量就是指通过变量名字而直接引用其中变量的内容。
```
<REF> variable_name </REF>
```
如果被引用的变量具有复杂的结构类型，且引用时不需要整个变量的值，则可以通过如下示例进行引用：
```
<REF> structured_var.field_name </REF>
<REF> structured_var.field_name1.field_name2 </REF>

<REF> structured_var[0] </REF>
<REF> structured_var[0][1] </REF>

<REF> structured_var[0].field_name1[3].field_name2 </REF>
```


### 1.3.3 DESCRIPTION_WITH_REFERENCE  
可以在理解static_description与`<REF> variable_name </REF>`的基础上，例如设置一个变量  
`task_overview = 'gives me dietary advice.'`  
那么`I hope you can become an AI assistant and the task is gives me dietary advice.`  
就变成了
```
I hope you can become an AI assistant and task is <REF> task_overview </REF>
```

### 1.3.4 STRUCTURED_TEXT  
`STRUCTURED_TEXT`是类似于Python字典的一种结构化表达，外部为`{}`，内部由类似"键值对"的字段组成。  
`STRUCTURED_TEXT`中的键值对，无论是键名还是键值，都不需要双引号来包括字符串。且对于键值，可以是`STATIC_DESCRIPTION `, `DESCRIPTION_WITH_REFERENCE`, 也可以是一个列表结构`[]`（列表结构中可以继续嵌套其他`STATIC_DESCRIPTION `, `DESCRIPTION_WITH_REFERENCE`，`[]`, `STRUCTURED_TEXT`），
或者继续嵌套一个`STRUCTURED_TEXT`
```
{
  order_id: <REF> order.id </REF>,
  customer: {
    name: <REF> user.full_name </REF>,
    email: <REF> user.email </REF>
  },
  items: [
    { product_id: 101, note: Special discount for <REF> user.segment </REF> },
    { product_id: 202, note: Add gift wrap if <REF> user.vip_status </REF> }
  ],
  total: "Total amount calculated from <REF> cart.summary </REF>"
}
```
---

# 2 如何更好的理解CNL-P Prompt?

CNL-P Prompt 中的语句总体上可分为两类：

## 2.1 标识语句/Identifier Sentence
第一类语句总是成对出现，并将其他内容包裹其中，我们称其为标识语句（Identifier sentence）（例如 `[DEFINE_PERSONA:] ... [END_PERSONA]`）。标识语句不仅界定了CNL-P Prompt的主体结构，还表明了某一区域内容的功能定位；  

## 2.2 语义语句/Semantic Sentence
第二类是直接描述“具体要做什么”或“具体是什么内容”的语句，我们称之为语义语句（Semantic Sentence）（如 REFERENCE 表示引用变量，COMMAND 表示执行操作）。语义语句通常可在多个模块中复用，其语义也随所处的标识语句不同而发生进一步变化（例如 REFERENCE 在 `[INPUTS] ... [END_INPUTS]` 中表示输入变量，而在 `[OUTPUTS] ... [END_OUTPUTS]` 中表示输出变量）。



### 2.3 语义语句目前有以下几类：

***Persona、Audience、Concepts、Constraints 模块中的 Aspect Sentence***：  
  给整段描述取一个用驼峰拼写法的，概括性的名字：`AspectName`，加上`:`，再加上具体的`DESCRIPTION_WITH_REFERENCE`。
```
AspectName: DESCRIPTION_WITH_REFERENCE
```

***Input/Output 中的 I/O Sentence***：  
  `"REQUIRED" | "OPTIONAL" REFERENCE`, 其中如果没有`REQUIRED`或者`OPTIONAL`字段，则默认为`REQUIRED`
  例如 `"REQUIRED <REF> example_var1 </REF>"` 表示在"INPUT"中或者"OUTPUT"中，变量"example_var1"是必要的。
```
REQUIRED <REF> example_var1 </REF>
<REF> example_var2 </REF>
OPTIONAL <REF> example_var3 </REF>
```

***Examples 中的 Example Sentence***:  
  共有两种类型的EXAMPLE，都需要示例的输入输出和执行路径，其中defect type还需要额外的defect type和defect explaination两个字段，其中defect type有几种类型。
  具体详情请参照`1.2.3.2 EXAMPLES`节

***各类 Block 中的 Command Sentence***:  
  COMMAND大致由`COMMAND-<number order>`和`COMMAND BODY`组成
`COMMAND-<number order>`中，"-"后为纯数字编号：
```
COMMAND-1 ...
COMMAND-2 ...
COMMAND-3 ...
```
`COMMAND BODY`被包括在`[]`中，内部需要依次申明`COMMAND TYPE`, 用以描述COMMAND具体操作的`DESCRIPTION_WITH_REFERENCE`（`CALL_API`类型的COMMAND则为api_name和WITH申明的参数列表）
以及对COMMAND操作结果的处理（`DISPLAY_MESSAGE`类型的COMMAND不涉及对结果的处理， `GENERAL_COMMAND`中使用字段`RESULT`,`REQUEST_INPUT`中使用字段`VALUE`, `CALL_API`中使用字段`RESPONSE`）
，可以把COMMAND操作产生的值重新赋值（SET）/添加（APPEND）到一个新声明变量中（var_name: var_type）,也可以对已有的变量进行操作（<REF> var_name </REF>）
- `GENERAL_COMMAND`: `RESULT`及其后面对结果的处理并不总是必须的，依照实际情况使用。
```
COMMAND-1 [COMMAND description_with_reference RESULT var_name: var_type SET]
COMMAND-1 [COMMAND description_with_reference]
```
- `CALL_API`: `WITH`及其后面的参数列表并不总是必须的，依照实际情况使用。`RESPONSE`及其后面对结果的处理并不总是必须的，依照实际情况使用。
```
COMMAND-1 [CALL api_name WITH {...} RESPONSE var_name: var_type SET]
COMMAND-1 [CALL api_name RESPONSE var_name: var_type SET]
COMMAND-1 [CALL api_name WITH {...}]
COMMAND-1 [CALL api_name]
```
- `REQUEST_INPUT`: `VALUE`及其后面的参数列表并总是必须的.
```
COMMAND-1 [INPUT description_with_reference VALUE var_name: var_type SET]
```
- `DISPLAY_MESSAGE`: 表示需要展示的信息
```
COMMAND-1 [DISPLAY description_with_reference]
```

这些语义语句在语法组成上又依赖更底层的语法元素，如 REFERENCE、DESCRIPTION_WITH_REFERENCE、STRUCTURED_TEXT。

---
# 3 CNL-P写作规范

## 注意缩进
同等级的模块具有相同的缩进等级

## 注意换行
语义语句中， `I/O Sentence`, `Aspect Sentence`, `Command Sentence`都是一句一行，而`Example Sentence`则一句多行

---
# 4 CNL-P Prompt 的示例

```
[DEFINE_AGENT: agent_name static_description]
  [DEFINE_PERSONA:]
    Role: description_with_reference
    OptionalAspectName: description_with_reference
    ...
  [END_PERSONA]

  [DEFINE_CONSTRAINTS:]
    OptionalAspectName: description_with_reference
    ...
  [END_CONSTRAINTS]

  [DEFINE_CONCEPTS:]
    OptionalAspectName: description_with_reference
    ...
  [END_CONCEPTS]

  [DEFINE_AUDIENCE:]
    OptionalAspectName: description_with_reference
    ...
  [END_AUDIENCE]

  [DEFINE_WORKER: worker_name static_description]
    [INPUTS]
      REQUIRED <REF> ref_var1 </REF>
      <REF> ref_var2 </REF>
      <REF> ref_var3 </REF>
    [END_INPUTS]

    [OUTPUTS]
      <REF> result1 </REF>
      <REF> result2 </REF>
    [END_OUTPUTS]

    [EXAMPLES]
      <EXPECTED-WORKER-BEHAVIOR> {
        inputs: { example_input_name: example_input_value, ... },
        expected-outputs: { expected_output_name: expected_output_value, ... },
        execution-path: command-1, command-2, command-3, command-4,
      } </EXPECTED-WORKER-BEHAVIOR>

      <DEFECT-WORKER-BEHAVIOR> {
        Processing Logic Error | Invalid Input Handling Error | Output Generation Error | Input Specification Error
        inputs: { example_input_name: example_input_value, ... },
        defect-outputs: { defect_output_name: expected_output_value, ... },
        execution-path: command-1, command-2, command-3, command-4,
        defect-explanation: static_description,
      } </DEFECT-WORKER-BEHAVIOR>
    [END_EXAMPLES]

    [MAIN_FLOW]
      [SEQUENTIAL_BLOCK]
        COMMAND-1 [COMMAND description_with_reference RESULT internal_var1: test_schema1 SET]
        COMMAND-2 [INPUT description_with_reference VALUE internal_var2: number SET]
      [END_SEQUENTIAL_BLOCK]

      [IF description_with_reference]
        COMMAND-3 [CALL api_name1 WITH {formal_para_name1: actual_para_name1, formal_para_name2: actual_para_name2} RESPONSE internal_var3: test_schema3 SET]
      [ELSEIF description_with_reference]
        COMMAND-4 [CALL api_name2 WITH {formal_para_name1: actual_para_name1, formal_para_name2: actual_para_name2} RESPONSE internal_var3: test_schema3 SET]
      [ELSEIF description_with_reference]
        COMMAND-5 [CALL api_name3 WITH {formal_para_name1: actual_para_name1, formal_para_name2: actual_para_name2} RESPONSE internal_var3: test_schema3 SET]
      [ELSE]
        COMMAND-6 [CALL api_name4 WITH {formal_para_name1: actual_para_name1, formal_para_name2: actual_para_name2} RESPONSE internal_var3: test_schema3 SET]
      [END_IF]

      [WHILE description_with_reference]
        COMMAND-7 [COMMAND description_with_reference RESULT internal_var4: boolean SET]
        COMMAND-8 [INPUT description_with_reference VALUE internal_var5: text SET]
        COMMAND-9 [COMMAND description_with_reference RESULT <REF> internal_var3 </REF> SET]
      [END_WHILE]

      [FOR description_with_reference]
        COMMAND-10 [INPUT description_with_reference VALUE internal_var6: boolean SET]
        COMMAND-11 [DISPLAY description_with_reference]
      [END_FOR]
    [END_MAIN_FLOW]

    [ALTERNATIVE_FLOW: description_with_reference]
      ...
    [END_ALTERNATIVE_FLOW]

    [EXCEPTION_FLOW: description_with_reference]
      LOG description_with_reference
      ...
    [END_EXCEPTION_FLOW]
  [END_WORKER]
[END_AGENT]
```
"""
    user_input = f"""
The following is the CNL-P instance that requires static analysis:\n
{cnl_p}
"""

    example_input1 = """
this a test error sentence.
[DEFINE_AGENT:ReceiptProcessor "Extracts, categorizes, and summarizes travel expenses from receipt images."]
    [DEFINE_PERSONA:]
        ROLE: An AI assistant specialized in automating business receipt processing for corporate travel.
        Expertise: Skilled in OCR (optical character recognition), expense classification, and structured data extraction from image formats.
        Accuracy: High reliability in numeric parsing, currency recognition, and total computation.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        UserType: Financial analysts, auditors, and operations staff responsible for business expense review and reporting.
        BusinessContext: Employees submitting receipts for reimbursement after business trips.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        OCR: The process of converting images of text (receipts) into machine-encoded text.
        ExpenseCategory: The classification of business expenses (e.g., Meals, Lodging, Transportation).
        ReceiptMetadata: Key fields such as Vendor Name, Date, Amount, and Category.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        DataQuality: Receipt images must be clear, non-blurry, and legible. LOG Reject image with poor quality.
        Compliance: Only valid receipts issued by recognized vendors and dated within business trip duration should be processed. LOG Flag non-compliant receipts.
        Privacy: Sensitive personal or payment info on receipts must not be stored or displayed unnecessarily. LOG Mask personal identifiers.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        ExpenseCategory = [Meals, Lodging, Transportation, Other]

        ReceiptItem = {
          vendor: str,
          date: str,
          amount: number,
          category: ExpenseCategory
        }

        ExtractedData = {
          vendor: str,
          date: str,
          amount: number,
          description: str
        }

        OCRResult = List [str]
        ReceiptImage = List [str]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        receipt_images: ReceiptImage
        ocr_texts: OCRResult
        extracted_data: List [ExtractedData]
        categorized_expenses: List [ReceiptItem]
        structured_receipts: List [ReceiptItem]
        total_amount: number
    [END_VARIABLES]

    [DEFINE_WORKER: "Process travel receipt images to extract, categorize, and total expenses." ReceiptWorkflow]
        [INPUTS]
            REQUIRED <REF>receipt_images</REF>
        [END_INPUTS]

        [OUTPUTS]
            REQUIRED <REF>structured_receipts</REF>
            REQUIRED <REF>categorized_expenses</REF>
            REQUIRED <REF>total_amount</REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <EXPECTED-WORKER-BEHAVIOR> {
            inputs: {
                user_id: 12345,
                preferences: { categories: ["electronics", "books"], max_price: 100 }
            },
            expected-outputs: {
                recommended_items: [
                { name: "Wireless Headphones", price: 89.99, rating: 4.5 },
                { name: "Bestseller Book", price: 20, rating: 4.8 }
                ]
            },
            execution-path: COMMAND-2, COMMAND-4
            } </EXPECTED-WORKER-BEHAVIOR>

            <DEFECT-WORKER-BEHAVIOR> {
            Processing Logic Error,
            inputs: {
                order_id: 98765,
                user_id: 12345,
                order_details: { items: ["Laptop", "Mouse"], total_price: 1200 }
            },
            defect-outputs: {
                confirmation_message: "Order has been placed successfully.",
                shipping_status: "Pending"
            },
            execution-path: COMMAND-1, COMMAND-3, COMMAND-7,
            defect-explanation: "Order confirmation message was sent, but the order was not actually recorded in the database."
            } </DEFECT-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [COMMAND Check if <REF>receipt_images</REF> resolution >= 300dpi RESULT is_high_quality:boolean SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>is_high_quality</REF> = false]
                COMMAND-0 [DISPLAY Receipt image resolution is too low for reliable OCR.]
                COMMAND-1 [COMMAND Abort processing]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-2 [COMMAND Extract text from <REF>receipt_images</REF> using OCR RESULT ocr_texts:List[text] SET]
                COMMAND-3 [COMMAND Parse <REF>ocr_texts</REF> to extract metadata (vendor, date, amount, etc.) RESULT extracted_data:List[{vendor:text, date:text, amount:number, description:text}] SET]
                COMMAND-4 [COMMAND Categorize each <REF>extracted_data</REF> item into predefined expense categories RESULT categorized_expenses:List[{vendor:text, date:text, amount:number, category:[Meals, Lodging, Transportation, Other]}] SET]
                COMMAND-5 [COMMAND Compute the total from <REF>categorized_expenses</REF> RESULT total_amount:number SET]
                COMMAND-6 [COMMAND Format all structured outputs as <REF>structured_receipts</REF> RESULT structured_receipts:List[{vendor:text, date:text, amount:number, category:text}] SET]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: OCR extraction returns incomplete or missing fields]
            [SEQUENTIAL_BLOCK]
                COMMAND-7 [COMMAND Try to reprocess image using enhanced OCR engine RESULT ocr_texts: OCRResult SET]
                COMMAND-8 [COMMAND Log enhanced OCR reprocessing attempt]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]

        [ALTERNATIVE_FLOW: A single receipt contains multiple expense items]
            [SEQUENTIAL_BLOCK]
                COMMAND-9 [COMMAND Split text into multiple sections based on date or vendor pattern RESULT extracted_data: List [ExtractedData] SET]
                COMMAND-10 [COMMAND Process each section as an individual receipt entry]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Receipt image is unreadable or corrupted]
            LOG Image file could not be opened or parsed for <REF>receipt_images</REF>
            [SEQUENTIAL_BLOCK]
                COMMAND-11 [DISPLAY Receipt image is corrupted or unreadable. Please upload a valid image.]
                COMMAND-12 [COMMAND Skip this receipt and continue processing remaining files]
            [END_SEQUENTIAL_BLOCK]
        [END_EXCEPTION_FLOW]

        [EXCEPTION_FLOW: Failed to extract numeric amount from OCR text]
            LOG Amount parsing failed for <REF>ocr_texts</REF>
            [SEQUENTIAL_BLOCK]
                COMMAND-13 [CALL a_name WITH {name: <REF> key_name </REF>}]
                COMMAND-14 [DISPLAY Amount extraction failed. Manual review may be required.]
            [END_SEQUENTIAL_BLOCK]
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
"""

    example_output1 = """
{
    "start_line": 1,
    "end_line": 1,
    "error_content": "this a test error sentence.",
    "error_message": "the sentence is outside of agent definition."
}
"""

    messages = [
        create_prompt_section(role="system", content=system_content),
        create_prompt_section(role="user", content=example_input1),
        create_prompt_section(role="assistant", content=example_output1),
        create_prompt_section(role="user", content=user_input)
    ]

    return llm_client.complete(messages)

