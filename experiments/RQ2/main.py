from task.task01_content_with_wrong_position import task01_json_format
from task.task02_identifier_issue import task02_json_format
from task.task03_structural_issue import task03_json_format
from task.task04_sentence_pattern_issue import task04_json_format
from task.task05_reference_issue import task05_json_format
from task.task06_required_field_issue import task06_json_format
from cnlp_linting_tool.parser_like import ParserLike
from linting_agent_based_on_llms.agent_linting import syntax_issue_linting_agent


import pandas as pd
import os
# import datetime
from datetime import datetime

task_list = [task01_json_format, task02_json_format, task03_json_format, task04_json_format, task05_json_format, task06_json_format]

parser_like = ParserLike()

agent_results = []
linting_tool_results = []

for task in task_list:
    for instance in task['instances']:
        agent_linting_result = syntax_issue_linting_agent(instance['cnl_p'])
        tool_linting_result = parser_like.syntax_analysis(instance['cnl_p'])

        agent_results.append({
            "instance_id": instance['id'],
            "cnl_p": instance['cnl_p'],
            "sample_answer": instance['sample_answer'],
            "result": agent_linting_result,
            "position": None,
            "content": None,
            "reason": None,
        })

        linting_tool_results.append({
            "instance_id": instance['id'],
            "cnl_p": instance['cnl_p'],
            "sample_answer": instance['sample_answer'],
            "result": tool_linting_result,
            "position": None,
            "content": None,
            "reason": None,
        })


llm_df = pd.DataFrame(agent_results)
linting_df = pd.DataFrame(linting_tool_results)

result_dir = "./result"
os.makedirs(result_dir, exist_ok=True)

current_time = datetime.now().strftime("%Y%m%d_%H%M")
llm_output_path = os.path.join(result_dir, f"llm_error_summary_{current_time}.csv")
linting_output_path = os.path.join(result_dir, f"linting_error_summary_{current_time}.csv")

llm_df.to_csv(llm_output_path, index=False, encoding='utf-8')
linting_df.to_csv(linting_output_path, index=False, encoding='utf-8')

print(f"The result has been saved to {os.path.abspath(llm_output_path)}")
print(f"The result has been saved to {os.path.abspath(linting_output_path)}")


