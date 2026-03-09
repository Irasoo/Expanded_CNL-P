import json
import os
import random
import time
from openai import OpenAI
from typing import Protocol, Literal
from openai import OpenAI

to_risen_system_content = '''### **Task Overview**
Transform the user's input into a RISEN framework prompt, ensuring each section is clearly defined and accurately reflects the user’s intent.

### **Understanding RISEN**
- Role: [Define the AI's role. E.g., Advisor, Creator]
- Input: [Provide detailed input. E.g., Specific question or topic]
- Steps: [Outline clear steps. E.g., First, provide an overview, then delve into details]
- Expectation: [State your desired outcome. E.g., A comprehensive guide, a brief summary]
- Narrowing: [State any limitations, restrictions, or what to focus on. E.g., word limit, focus on cost-effective options]

### **Conversion Process**
1. **Role**: Identify and specify the role based on the user’s task (e.g., “Advisor,” “Content Creator”).
2. **Input**: Extract the key topics, questions, or data provided by the user.
3. **Steps**: Outline clear, actionable steps the AI should follow, in sequence.
4. **Expectation**: Determine the type of output the user wants.
5. **Narrowing**: Include any constraints, limitations, or specific focus areas.

### **Key Considerations**
- Keep it concise and accurate.
- Ensure each section directly reflects the user’s input.
- Maintain clarity and logical flow.

### **Prompt Architecture**
```
Role: [AI's role, e.g., "Analyst"]

Input: [User's detailed question or topic]

Steps: 
1. [First action]
2. [Next action]
...
 
Expectation: [Desired outcome]

Narrowing: [Any restrictions or focus areas]
```
'''

to_rodes_system_content = '''### **Task Overview**
You are tasked with generating a RODES framework prompt based on user input, ensuring that all sections are clearly defined and accurately tailored to the user's intent.

### **Understanding RODES**
The RODES framework consists of five main components:
```
1. **Role (R)**: Defines the persona or identity the AI should adopt.
2. **Objective (O)**: Specifies the main goal or task.
3. **Details (D)**: Outlines specific requirements, constraints, or steps for the task.
4. **Examples (E)**: Provides examples of the desired input and output.
5. **Sense Check (S)**: Confirms understanding and checks for additional clarifications needed.
```
The final RODES prompt should adhere to this structure, enabling the AI to perform the task effectively.

### **Conversion Process for Each RODES Component**
1. **Role (R)**:
   - Identify the persona or role needed for the task based on user input.
   - Example: If the user asks for marketing advice, the role could be "Digital Marketing Expert."
2. **Objective (O)**:
   - Extract the main goal or task from the user’s input.
   - Example: If the user wants insights on social media trends, the objective could be “Provide an analysis of current social media trends.”
3. **Details (D)**:
   - Include any specific instructions, requirements, or steps provided by the user.
   - Example: If the user specifies, "Focus on trends related to TikTok and Instagram," include this in the details.
4. **Examples (E)**:
   - Identify and provide any examples given by the user to clarify expectations.
   - If no examples are provided, mention this section should be completed based on the context.
5. **Sense Check (S)**:
   - Ensure that a final step asks if the AI understands the task and if additional details are needed.

### **Key Considerations**
- Keep the prompt clear and concise.
- Ensure each section directly reflects the user's intent.
- Maintain logical flow and avoid unnecessary complexity.

### **Prompt Architecture**
```
1. Role (R):
   [Define the AI's role based on the task. E.g., "SEO Specialist"]

2. Objective (O):
   [State the goal. E.g., "Analyze and provide SEO strategies for a new website."]

3. Details (D):
   [Include any requirements, constraints, or steps. E.g., "Focus on keyword research and link-building techniques."]

4. Examples (E):
   [Provide input-output examples if available, or specify that the user should provide them.]

5. Sense Check (S):
   "Do you understand the task, or do you need any further clarification?"
```
'''

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
    CONCEPT := OPTIONAL_ASPECT_NAME ":" STATIC_DESCRIPTION """Concepts do not need parameters or references."""
    
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
      - **5.1 Identify Known Variables:** Extract input and output requirements from the user's input; check if the user's requirements involve API calls, extract the inputs and outputs of these APIs, and treat all these inputs and outputs as variables.
      - **5.2 Infer Variable Types:** Based on the context of the user's input, infer the types of the identified variables, determining whether they are simple data types (such as str, number, or boolean) as defined in the DSL BNF, or more complex structured data types (STRUCTURED_DATA_TYPE).
      - **5.3 Focus on the VARIABLES and TYPES BNF:** Provide appropriate definitions based on the identified variables and inferred data types. Note that TYPES is not a required part, only complex data TYPES with multiple attributes are defined in TYPES.
   6. **Define the WORKER:**
      - **6.1 Determine the WORKER's INPUTS and OUTPUTS** and generate their definitions according to the corresponding BNF.
      - **6.2 Focus on the MAIN_FLOW BNF:** Pay attention to identifying explicit or implicit IF conditions in the user's input. If present, define the IF_BLOCK; otherwise, define a SEQUENTIAL_BLOCK. If iteration is implied, define a LOOP_BLOCK.
      - **6.3 Consider ALTERNATIVE_FLOW and EXCEPTION_FLOW:** If the user specifies alternative scenarios or error-handling processes, define these flows explicitly.
      - **6.4 Define EXAMPLES:** Collect or construct positive examples ($\mathtt{EXPECTED\_WORKER\_BEHAVIOR}$) and negative examples ($\mathtt{DEFECT\_WORKER\_BEHAVIOR}$) to illustrate correct and incorrect Worker behaviors.
      - **6.5 Define COMMANDS:** Carefully distinguish between different types of COMMAND_BODY and strictly map the relevant content from the user's input to the corresponding COMMAND_BODY.


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
                _attribute_1: str
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

all_classified_tasks = [
    'task137_', 'task327_', 'task333_', 'task335_', 'task337_', 'task905_', 'task320_',
    'task1502_', 'task1503_', 'task1504_', 'task1664_', 'task1669_', 'task1670_',
    'task1720_', 'task1725_', 'task904_', 'task277_', 'task278_', 'task279_',
    'task280_', 'task316_', 'task317_', 'task318_', 'task319_', 'task321_',
    'task108_', 'task322_', 'task323_', 'task324_', 'task325_', 'task326_',
    'task328_', 'task1604_', 'task1605_', 'task1606_', 'task1607_', 'task1721_',
    'task1722_', 'task1723_', 'task1724_', 'task607_', 'task608_', 'task609_',
    'task286_', 'task1149_', 'task1189_', 'task065_', 'task1297_', 'task084_',
    'task697_', 'task729_', 'task1380_', 'task1381_', 'task309_', 'task1431_',
    'task220_', 'task1612_', 'task190_', 'task1347_', 'task069_', 'task070_',
    'task138_', 'task139_', 'task140_', 'task296_', 'task297_', 'task118_',
    'task1135_', 'task1424_', 'task1423_', 'task1422_', 'task1421_', 'task1420_',
    'task1419_', 'task1678_', 'task385_', 'task580_', 'task214_', 'task213_',
    'task1661_', 'task027_', 'task136_', 'task021_', 'task018_', 'task020_',
    'task740_', 'task1366_', 'task1162_', 'task1587_', 'task491_', 'task492_',
    'task050_', 'task1387_', 'task1186_', 'task1283_', 'task1284_', 'task501_',
    'task155_', 'task158_', 'task161_', 'task163_', 'task162_', 'task113_',
    'task114_', 'task133_', 'task240_', 'task845_', 'task348_', 'task389_',
    'task443_', 'task223_', 'task105_', 'task1401_', 'task040_', 'task067_',
    'task071_', 'task072_', 'task1326_', 'task037_', 'task038_', 'task1613_',
    'task216_',
]


class LLM_REQUEST:
    def __init__(self):
        self.request_info = {
            'mistral': {
                'url': "api.mistral.ai",
                'key': "POn3wrjpWUHuACMxjSLZ4RFlzlpGZ6M9",
                'models': ['ministral-8b-latest']
            },
            'rcouyi': {
                'url': "api.rcouyi.com/v1/",
                'key': "https://api.rcouyi.com/v1",
                'models': ['claude-3-haiku-20240307', 'gemini-pro', 'gpt-4o-mini-2024-07-18', 'gpt-4o-2024-08-06', 'gpt-4o']
            },
            # 'openai': {
            #     'url': "https://api.openai.com/v1/chat/completions",
            #     'key': "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",
            #     'models': ['gpt-4o-mini-2024-07-18', 'gpt-4o']
            # },
            'groq': {
                'url': "api.groq.com",
                'key': "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",
                'models': ['llama3-70b-8192']
            }
        }

    def query(self, model, messages, max_tokens=4000, temperature=0, max_retries=10, retry_delay=15):
        url, key = self.get_request_info(model)
        import http.client
        import json

        print(url)

        conn = http.client.HTTPSConnection(url)
        payload = json.dumps({
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })
        headers = {
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json'
        }


        retried_count = 0
        while retried_count < max_retries:
            try:
                conn.request("POST", "/v1/chat/completions", payload, headers)
                res = conn.getresponse()
                data = res.read().decode("utf-8")
                print(data)
                content = json.loads(data)['choices'][0]['message']['content']
                return content
            except Exception:
                print(f"Request failed! Retrying {retried_count+1}/{max_retries} after {retry_delay} seconds...")
                time.sleep(retry_delay)
                retried_count += 1

        raise ValueError(f"The {model}'s request url or api key INCORRECT!")

    def get_request_info(self, model) -> tuple:
        for info in self.request_info.values():
            for m in info['models']:
                if model == m:
                    return info['url'], info['key']
        raise ValueError(f"The {model} is NOT Register!")

    @staticmethod
    def get_msg(prompt, user_input, user_role_need: bool = False):
        messages = [{"role": "system", "content": prompt}]
        if not user_role_need:
            messages[0]['content'] = prompt + f'\n\nUser input:\n{user_input}'
        else:
            messages.append({"role": "user", "content": user_input})
        return messages


class LLM():
    def __init__(self, keys, base_url='https://api.openai.com/v1'):
        self.gpt_models = ['gpt-4o-mini-2024-07-18', 'gpt-4o', "gpt-4o-2024-08-06"]  # gpt-4o gpt-4o-mini-2024-07-18
        self.llama_models = ['llama3-70b-8192']
        self.keys = []
        if isinstance(keys, str):
            self.keys.append(keys)
        elif isinstance(keys, list):
            self.keys.extend(keys)
        if not self.keys:
            raise ValueError("No API keys provided.")
        elif self.keys[0].startswith('sk'):
            self.client = OpenAI(api_key=self.keys[0], base_url=base_url)
            self.client_name = 'openai'
        self.all_clients = ('openai', 'groq')

    def create_client(self, client_name: str, key):
        name = client_name.lower()
        if name not in self.all_clients:
            raise Exception(f"The {client_name} is not support! We only support the following clients: {str(self.all_clients)}.")
        elif name == 'openai':
            return OpenAI(api_key=key)

    def query(self, model, messages: list, temperature=0, max_tokens=4000, max_retries=10, retry_delay=60):
        if model not in self.gpt_models and model not in self.llama_models:
            raise Exception(f'The {model} is not support!')
        key_index = 0

        retries = 0
        # client = self.create_client(client_name=client_name, key=self.keys[key_index])
        while retries < max_retries:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=1,
                )

                return response.choices[0].message.content

            except Exception as e:
                error_message = str(e)
                if "Rate limit reached" in error_message or "exceeded your current quota" in error_message.lower():
                    print(f"API key at index {key_index}/{len(self.keys)} is out of funds or quota. Switching to the next key...")
                    key_index += 1
                    if key_index >= len(self.keys):
                        raise Exception("All API keys have been exhausted.")
                    self.client = self.create_client(client_name=self.client_name, key=self.keys[key_index])
                    print('The API key has been switched because of limited tokens.')
                else:
                    retries += 1
                    print(
                        f"Request failed with error: {e}. Retrying {retries}/{max_retries} after {retry_delay} seconds...")
                    time.sleep(retry_delay)

        raise Exception(f"Failed to complete request after {max_retries} retries.")

    @staticmethod
    def get_msg(prompt, user_input, user_role_need: bool = False):
        messages = [{"role": "system", "content": prompt}]
        if not user_role_need:
            messages[0]['content'] = prompt + f'\n\nUser input:\n{user_input}'
        else:
            messages.append({"role": "user", "content": user_input})

        return messages


def load_raw_dataset_supernatural_instructions(tasks_dir: str, task_filename: str):
    if not os.path.isdir(tasks_dir):
        raise FileNotFoundError(f"The directory {tasks_dir} does not exist.")

    task_filenames = [filename for filename in os.listdir(tasks_dir) if task_filename in filename]

    if len(task_filenames) != 1:
        raise ValueError(f"Expected one file but actually is {len(task_filenames)}: {task_filenames}")

    task_filename = task_filenames[0]
    filepath = os.path.join(tasks_dir, task_filename)
    # print(filepath)

    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            raw_dataset = json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"The file {filepath} does not exist.")
    except json.JSONDecodeError:
        raise ValueError(f"Error decoding JSON from the file {filepath}.")

    return raw_dataset


class DataLoader:
    def __init__(self, tasks_dir: str, instance_num: int, seed: int = 42, output_dir: str = "saved_instances"):
        self.all_classified_tasks = []  # Make sure this gets initialized properly elsewhere
        self.tasks_dir = tasks_dir
        self.instance_num = instance_num
        self.seed = seed
        self.output_dir = output_dir

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

    def random_sample_instances(self, raw_task, task_filename):
        all_instances = raw_task['Instances']
        instances_len = len(all_instances)

        # Determine the number of instances to select
        instance_num = min(self.instance_num, instances_len)

        # Set the random seed for reproducibility
        random.seed(self.seed)

        # Randomly select instance indices
        random_indices = random.sample(range(0, instances_len), instance_num)
        instances = [all_instances[i] for i in random_indices]

        # Save the sampled instances to a JSON file
        output_path = os.path.join(self.output_dir, f"{task_filename}instances.json")

        def save_instances():
            # Save the sampled instances to a JSON file
            with open(output_path, "w", encoding="utf-8") as file:
                json.dump(instances, file, ensure_ascii=False, indent=4)
            print(f"Saved instances to '{output_path}'.")

        if os.path.exists(output_path):
            previous_instances = self.load_saved_instances(task_filename)
            if self.instance_num != len(previous_instances):
                save_instances()
            else:
                print(f"The file '{output_path}' already exists and is not empty. Skipping the write process to prevent overwriting.")
        else:
            save_instances()

    def get_task_content_random(self, task_filename: str) -> dict:
        # Load the raw task data
        raw_task = load_raw_dataset_supernatural_instructions(tasks_dir=self.tasks_dir, task_filename=task_filename)

        self.random_sample_instances(raw_task, task_filename)

        instances = self.load_saved_instances(task_filename)

        # Construct and return the task content
        task_content = {
            "definition": raw_task['Definition'],
            "positive_example": raw_task['Positive Examples'][0],
            "negative_example": raw_task['Negative Examples'][0],
            "instances": instances
        }
        return task_content

    def load_saved_instances(self, task_filename: str) -> list:
        # Load saved instances from the output directory
        output_path = os.path.join(self.output_dir, f"{task_filename}instances.json")
        if os.path.exists(output_path):
            with open(output_path, "r", encoding="utf-8") as file:
                instances = json.load(file)
            return instances
        else:
            raise FileNotFoundError(f"No saved instances found for {task_filename}")


def create_prompt_section(role: Literal["system", "user", "assistant"], content: str):
    return {"role": role, "content": [{"type": "text", "text": content}]}


class LLMclient(Protocol):
    def complete(self, prompt: str | list) -> str:
        ...

    def complete_with_specified_model_and_retry_strategy(self, prompt: str | list, model: str, max_retries: int=10, retry_delay: int=15) -> str:
        ...

class OpenaiClient(LLMclient):
    api_key: str
    model: str
    org: str
    base_url: str  # 可选：添加类型注解以保持一致性

    def __init__(self, api_key: str, model: str, org: str, base_url: str):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.org = org
        self.base_url = base_url

    def complete(self, prompt: list):
        client = OpenAI(
            api_key=self.api_key,
            organization=self.org,
            base_url=self.base_url,
        )

        completion = client.chat.completions.create(
            model=self.model,
            n=1,
            temperature=0,
            messages=prompt
        )

        return completion.choices[0].message.content

    def complete_with_specified_model_and_retry_strategy(
            self,
            prompt: str | list,
            model: str,
            max_retries: int=10,
            retry_delay: int = 15
    ) -> str:

        retried_count = 0
        while retried_count < max_retries:
            try:
                print(self.api_key)
                client = OpenAI(
                    api_key=self.api_key,
                    organization=self.org,
                    base_url=self.base_url,
                )
                print(prompt)
                completion = client.chat.completions.create(
                    model=model,
                    n=1,
                    temperature=0,
                    messages=prompt
                )

                return completion.choices[0].message.content

            except Exception as e:
                print(e)
                print(f"Request failed! Retrying {retried_count+1}/{max_retries} after {retry_delay} seconds...")
                time.sleep(retry_delay)
                retried_count += 1

        return "request fail"


def create_llm_client(vals: dict[str, str | None]) -> LLMclient:
    def required_var(name: str) -> str:
        val = vals.get(name, None)
        if val is None:
            raise ValueError(f"Missing environment variable {name}.")
        return val

    if "OPENAI_API_KEY" in vals:
        api_key = required_var("OPENAI_API_KEY")
        model = required_var("OPENAI_MODEL")
        org = vals.get("OPENAI_ORG", None) or ""
        base_url = vals.get("BASE_URL", None) or ""
        return OpenaiClient(api_key, model, org, base_url)

    else:
        raise ValueError("Missing environment variables.")


if __name__ == '__main__':
    llm = LLM_REQUEST()
    msg = LLM_REQUEST.get_msg("you are a AI.", "Hello")
    res = llm.query('ministral-8b-latest', msg)
    print(res)