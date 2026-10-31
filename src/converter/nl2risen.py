from pathlib import Path

from .client import complete_conversion, output_path


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


PROJECT_DIR = (
    Path(__file__).resolve().parents[2]
    / "experiment_results" / "RQ2" / "results" / "conversion_results"
)


def build_messages(user_input: str) -> list[dict[str, str]]:
    """Build the chat messages used for a natural-language-to-RISEN conversion."""
    return [
        {"role": "system", "content": to_risen_system_content},
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


def to_risen(
    user_input: str,
    task_idx: str,
    model: str,
) -> None:
    """Convert one natural-language prompt to RISEN and save it in the conversion-results directory."""
    complete_conversion(
        output_file=output_path(PROJECT_DIR, task_idx, "risen"),
        model=model,
        messages=build_messages(user_input),
    )


