# 1 Composition of a CNL-P Prompt

## 1.1 Defining the Agent’s Attributes

### 1.1.1 Role / PERSONA (Fundamental) (Core)

“Role” refers to a specific identity or persona assigned to the model within the prompt. Defining a role helps the model adopt a particular tone, style, or perspective, thereby improving the relevance and quality of its responses.
For example, explicitly asking the model to answer as an expert in a certain domain (e.g., “As a medical expert, please explain…”) can make the response more authoritative. This helps the model better understand the context and adjust its responses so that the output is more appealing and better aligned with requirements.

```
[DEFINE_PERSONA]
  ROLE: You are a patient and gentle teacher.
  TeachingSubject: The main subject you teach is <REF> major_subject </REF>.
  ...
[END_PERSONA]
```

### 1.1.2 Audience / AUDIENCE (Fundamental)

“Audience” refers to explicitly specifying the target audience in the prompt, thereby guiding the model to adjust tone, wording, and the level of detail accordingly.
By clearly indicating the intended audience, the model can adapt its language style, vocabulary choice, and conceptual complexity to better fit the context.
For example, when explaining a math problem, if you explicitly inform the model that the audience is elementary school students (e.g., “Explain in a way a primary school student can understand”), the model will avoid referencing advanced concepts from middle school or college. This helps the model better align with the communication intent and improves output relevance and clarity.

```
[DEFINE_AUDIENCE]
  Teaching level: Primary school graduates (pre-junior high).
  ...
[END_AUDIENCE]
```

### 1.1.3 Constraints / CONSTRAINTS (Fundamental)

“Constraints” are guiding principles or restrictions imposed on the model’s output to more effectively shape the response. Constraints can focus on limiting the model’s creativity to ensure results meet specific expectations.
For example, a formatting constraint might require organizing the answer in a specific structure (e.g., “List five benefits in bullet points”); a content constraint might specify which content must be included or excluded (e.g., “Discuss renewable energy, but do not mention solar power”).

```
[DEFINE_CONSTRAINTS]
  Scope: Primarily elementary content, with select concepts bridging to junior-high mathematics.
  ...
[DEFINE_CONSTRAINTS]
```

### 1.1.4 Concepts / CONCEPTS (Fundamental)

“Concepts” allow explicit definition or clarification of specific terms, abbreviations, or context-specific keywords within the prompt to avoid ambiguity or misunderstanding.
This mechanism reduces the risk of the model making erroneous assumptions due to language ambiguity or insufficient definitions, thereby improving the accuracy and consistency of responses.
For example, when “LLM” may have multiple meanings, the prompt can clarify: “Here, LLM refers to Master of Laws, not Large Language Model.” Such clarification is especially important in cross-disciplinary applications because terminology may overlap or have different interpretations across fields.

```
[DEFINE_CONCEPTS]
  LLM: LLM here refers exclusively to the 'Master of Laws', not to a 'large language model'.
[END_CONCEPTS]
```

## 1.2 Configuring the Agent’s Behavior

### 1.2.1 Types / TYPES (Advanced)

“Types” describe the kinds of data the agent will handle. This makes data exchange more reliable.
Some basic types (such as `text`, `number`, `boolean`) do not need to be specially defined in this module. Complex types (such as `list`, `enum`), or even custom structured types (such as `UserProfile`, containing `name: text`, `age: number`, `interests: text`, etc.) should be defined here.
By explicitly stating these types in the TYPES module, the agent can perform type checking during input, output, and command execution (initially implemented), reducing errors and improving maintainability.

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

### 1.2.2 Variables / VARIABLES (Core) (Advanced)

List the variables the agent will use or operate on. By abstracting variables, the agent can pass data between different flows or commands without repeatedly describing concrete values.
Each variable typically includes the following information:

* **Variable name** (for reference): e.g., `user_name`
* **Type** (corresponding to TYPES definitions): e.g., `text` or `UserProfile`
* **Usage description**: explains the meaning and usage scenarios of the variable (the usage description is optional)

### 1.2.3 Worker / WORKER (Fundamental) (Core)

The WORKER module defines the agent’s behavioral logic, including inputs and outputs, examples, execution flows, and embedded internal control structures and commands. It provides a clear hierarchical structure and powerful control capabilities.
There are additional submodules within the Worker module.

#### 1.2.3.1 INPUTS, OUTPUTS

Define the worker module’s inputs and outputs; this is one of the top-level modules under WORKER.
Use `REFERENCE` to introduce initial inputs/final outputs; mark an input/output as necessary with `REQUIRED` or `OPTIONAL`.

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

Provide example behaviors of the Worker; this is one of the top-level modules under WORKER.
The EXAMPLES module contains two types of Worker behaviors: `EXPECTED_WORKER_BEHAVIOR` and `DEFECT_WORKER_BEHAVIOR`.
For `EXPECTED_WORKER_BEHAVIOR`:

* Example input `inputs`: fields of type `STRUCTURED_TEXT`
* Expected sample output `expected-outputs`: fields of type `STRUCTURED_TEXT`
* Execution path `excution-path`: a string composed of `COMMAND` identifiers separated by commas; the specific form is to display the content from the COMMAND statements

For `DEFECT_WORKER_BEHAVIOR`:

* Example input `inputs`: fields of type `STRUCTURED_TEXT`
* Defective sample output `defect-outputs`: fields of type `STRUCTURED_TEXT`
* Execution path `excution-path`: a string composed of `COMMAND` identifiers separated by commas; the specific form is to display the content from the COMMAND statements
* Defect type `defect-type`: currently one of `"Processing Logic Error" | "Invalid Input Handling Error" | "Output Generation Error" | "Input Specification Error"`
* Defect explanation `defect-explanation`: explanation of type `STATIC_DESCRIPTION`

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

Defines the worker’s default and primary execution flow (the “sunny-day scenario” in software engineering; the Worker only needs to use MAIN_FLOW in about 80% of cases).
This is a top-level module under WORKER.

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

Defines other optional execution flows of the Worker; after executing this flow it can return to the main flow.
ALTERNATIVE_FLOW must have a corresponding triggering `condition`. This condition can be described in natural language or expressed in a pseudo-programming language and may reference variables. It is of type `DESCRIPTION_WITH_REFERENCE`.
This is a top-level module under WORKER.

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

Defines other exceptional handling flows for the Worker. Once this flow begins execution, it means the Worker has encountered a severe error and cannot continue execution in any way; thus completion of the exception flow means the end of the entire Worker processing.
EXCEPTION_FLOW not only requires a triggering `condition`, but can also record logs via the `LOG` field. The `LOG` field is also of type `DESCRIPTION_WITH_REFERENCE`.
This is a top-level module under WORKER.

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

#### 1.2.3.6 SEQUENTIAL_BLOCK, IF_BLOCK, LOOP_BLOCK

Three basic control structures, used respectively for sequential logic, conditional branching, and loop control. They are modules located under MAIN_FLOW, ALTERNATIVE_FLOW, EXCEPTION_FLOW:

* `IF_BLOCK` may contain multiple branches; except for the `ELSE` branch, all other branches require a corresponding `condition`. The `condition` here is also of type `DESCRIPTION_WITH_REFERENCE`.
* `LOOP_BLOCK` is further divided into `FOR_BLOCK` and `WHILE_BLOCK`. All `LOOP_BLOCK`s also require a termination `condition`; this `condition` is likewise of type `DESCRIPTION_WITH_REFERENCE`.
* Note: In practical usage, `LOOP_BLOCK` only appears as `FOR_BLOCK` and `WHILE_BLOCK`; `LOOP_BLOCK` itself cannot be used directly.

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

*Nested BLOCK usage is not allowed. When logic becomes complex, introduce new FLOW structures to organize it!* An example concerning nested BLOCKs is as follows:

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

`COMMAND` is a syntax module placed under BLOCKs. `COMMAND` defines commands and may include general commands, API calls, input requests, or display messages.

```
[DEFINE_WORKER: "this is an example of worker" example_worker_name]

  ... 
 
  [MAIN_FLOW]
    [IF the condition is description_with_reference]
      ...
      COMMAND-3 [... ]
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

There are currently four types of `COMMAND` statements:

* GENERAL_COMMAND: commands used in normal situations

```
COMMAND-1 [COMMAND 用DESCRIPTION_WITH_REFERENCE描述具体的操作 RESULT var: var_type SET] 
COMMAND-1 [COMMAND Summarize all <REF> user_feedback </REF> provided by the user. RESULT feedback_summary: text SET]
# SET means setting the value of a variable; RESULT and its following parts are not always required

COMMAND-1 [COMMAND 用DESCRIPTION_WITH_REFERENCE描述具体的操作 RESULT <REF> list_var </REF> APPEND] 
# APPEND means adding an additional new value into a dictionary or list type

# Additional possible RESULT forms for COMMAND:
COMMAND-1 [... RESULT var: var_type APPEND]
COMMAND-1 [... RESULT <REF> var </REF> SET]
```

* CALL_API: call an API that the agent can interact with.

```
COMMNAD-1 [CALL api_name WITH {para_name1: STRUCTURED_TEXT, para_name2: STRUCTURED_TEXT} RESPONSE var: var_type SET] 
# If the API called requires no parameters, you do not need to provide a parameter list via WITH  
# If the API returns nothing, then RESPONSE and its following fields are not needed
# Handling of RESPONSE and its following fields otherwise follows the usage described for RESULT in GENERAL_COMMAND
```

* REQUEST_INPUT: command to request user input

```
COMMAND-1 [INPUT 用DESCRIPTION_WITH_REFERENCE描述具体的操作 VALUE var: var_type SET] 
# Indicates setting the value of a variable;
# VALUE and what follows are mandatory
# Other handling details for VALUE follow the usage of RESULT in GENERAL_COMMAND
```

* DISPLAY_MESSAGE: command to display specified content to the user

```
COMMAND-1 [DISPLAY 用DESCRIPTION_WITH_REFERENCE描述具体的操作]
```

## 1.3 Fundamental Syntax Elements that Support CNL-P

### 1.3.1 STATIC_DESCRIPTION

Can be simply understood as a piece of natural language (natural languages refer to languages like Chinese, English used in human daily communication). It can of course also be descriptions in similar programming-like language.

```
I hope you can become an AI assistant and the task is gives me dietary advice.
```

### 1.3.2 REFERENCE

REF (reference) to a variable means directly referencing the variable’s content by its name.

```
<REF> variable_name </REF>
```

If the referenced variable has a complex structured type and you do not need the entire variable’s value, you can reference it as follows:

```
<REF> structured_var.field_name </REF>
<REF> structured_var.field_name1.field_name2 </REF>

<REF> structured_var[0] </REF>
<REF> structured_var[0][1] </REF>

<REF> structured_var[0].field_name1[3].field_name2 </REF>
```

### 1.3.3 DESCRIPTION_WITH_REFERENCE

Building on STATIC_DESCRIPTION and `<REF> variable_name </REF>`, for example, set a variable
`task_overview = 'gives me dietary advice.'`
Then `I hope you can become an AI assistant and the task is gives me dietary advice.`
becomes

```
I hope you can become an AI assistant and task is <REF> task_overview </REF>
```

### 1.3.4 STRUCTURED_TEXT

`STRUCTURED_TEXT` is a structured expression similar to a Python dictionary: it is enclosed by `{}`, and contains "key-value pair"-like fields inside.
In `STRUCTURED_TEXT` the key names and values do not need to be enclosed in double quotes. For values, they can be `STATIC_DESCRIPTION`, `DESCRIPTION_WITH_REFERENCE`, a list structure `[]` (inside which you can continue to nest other `STATIC_DESCRIPTION`, `DESCRIPTION_WITH_REFERENCE`, `[]`, or `STRUCTURED_TEXT`), or another nested `STRUCTURED_TEXT`.

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

# 2 How to Better Understand a CNL-P Prompt?

Statements in a CNL-P Prompt are generally classified into two types:

## 2.1 Identifier Sentence

The first type of sentence always appears in pairs and wraps other content; we call it an Identifier sentence (for example `[DEFINE_PERSONA:] ... [END_PERSONA]`). Identifier sentences not only define the main structure of the CNL-P Prompt but also indicate the functional role of a particular region of content.

## 2.2 Semantic Sentence

The second type directly describes “what to do” or “what the content is”; we call these Semantic Sentences (such as REFERENCE indicating referencing a variable, COMMAND indicating executing an operation). Semantic sentences are often reusable across multiple modules, and their semantics may further vary depending on the identifier sentence they are inside (for example, REFERENCE in `[INPUTS] ... [END_INPUTS]` denotes input variables, while in `[OUTPUTS] ... [END_OUTPUTS]` it denotes output variables).

### 2.3 Current categories of Semantic Sentences:

***Aspect Sentence in Persona, Audience, Concepts, Constraints modules***:
Give the entire description a camelCase, summarizing name: `AspectName`, followed by `:`, and then a specific `DESCRIPTION_WITH_REFERENCE`.

```
AspectName: DESCRIPTION_WITH_REFERENCE
```

***I/O Sentence in Input/Output***:
`"REQUIRED" | "OPTIONAL" REFERENCE`. If neither `REQUIRED` nor `OPTIONAL` is present, it defaults to `REQUIRED`.
For example, `"REQUIRED <REF> example_var1 </REF>"` indicates that in INPUT or OUTPUT, the variable `example_var1` is required.

```
REQUIRED <REF> example_var1 </REF>
<REF> example_var2 </REF>
OPTIONAL <REF> example_var3 </REF>
```

***Example Sentence in EXAMPLES***:
There are two types of EXAMPLE; both require example inputs, outputs, and an execution path. Defect examples additionally require `defect type` and `defect explanation` fields. Details are in section `1.2.3.2 EXAMPLES`.

***Command Sentence in various Blocks***:
A `COMMAND` roughly consists of `COMMAND-<number order>` and a `COMMAND BODY`.
In `COMMAND-<number order>`, the part after `-` is a purely numeric index:

```
COMMAND-1 ...
COMMAND-2 ...
COMMAND-3 ...
```

The `COMMAND BODY` is included in `[]`. Inside, you must sequentially declare the `COMMAND TYPE`, a `DESCRIPTION_WITH_REFERENCE` describing the command’s specific operation (for `CALL_API` commands this is the `api_name` and a `WITH` parameter list), and handling of the command’s result (`DISPLAY_MESSAGE` does not involve result handling; `GENERAL_COMMAND` uses `RESULT`; `REQUEST_INPUT` uses `VALUE`; `CALL_API` uses `RESPONSE`). The values produced by a COMMAND operation can be assigned (SET) or appended (APPEND) to a newly declared variable (`var_name: var_type`), or they can operate on existing variables (`<REF> var_name </REF>`).

* `GENERAL_COMMAND`: `RESULT` and subsequent handling is not always mandatory; use as appropriate.

```
COMMAND-1 [COMMAND description_with_reference RESULT var_name: var_type SET]
COMMAND-1 [COMMAND description_with_reference]
```

* `CALL_API`: `WITH` and its parameter list are not always required. `RESPONSE` and its result handling are not always required. Use as appropriate.

```
COMMAND-1 [CALL api_name WITH {...} RESPONSE var_name: var_type SET]
COMMAND-1 [CALL api_name RESPONSE var_name: var_type SET]
COMMAND-1 [CALL api_name WITH {...}]
COMMAND-1 [CALL api_name]
```

* `REQUEST_INPUT`: `VALUE` and the following parameter list are always required.

```
COMMAND-1 [INPUT description_with_reference VALUE var_name: var_type SET]
```

* `DISPLAY_MESSAGE`: indicates the information to be displayed.

```
COMMAND-1 [DISPLAY description_with_reference]
```

These semantic sentences further depend on lower-level syntax elements such as REFERENCE, DESCRIPTION_WITH_REFERENCE, and STRUCTURED_TEXT.

---

# 3 CNL-P Writing Conventions

## Pay attention to indentation

Modules at the same level should have the same indentation level.

## Pay attention to line breaks

In semantic sentences, `I/O Sentence`, `Aspect Sentence`, and `Command Sentence` are each one line per sentence, while `Example Sentence` can span multiple lines.

---

# 4 Example of a CNL-P Prompt

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