from pathlib import Path

from .client import complete_conversion, output_path


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


PROJECT_DIR = (
    Path(__file__).resolve().parents[2]
    / "experiment_results" / "RQ2" / "results" / "conversion_results"
)


def build_messages(user_input: str) -> list[dict[str, str]]:
    """Build the chat messages used for a natural-language-to-RODES conversion."""
    return [
        {"role": "system", "content": to_rodes_system_content},
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


def to_rodes(
    user_input: str,
    task_idx: str,
    model: str,
) -> None:
    """Convert one natural-language prompt to RODES and save it in the conversion-results directory."""
    complete_conversion(
        output_file=output_path(PROJECT_DIR, task_idx, "rodes"),
        model=model,
        messages=build_messages(user_input),
    )


