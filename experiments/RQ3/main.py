import os
from datetime import datetime
import pandas as pd
from dotenv import dotenv_values
from tools import DataLoader, LLM, to_cnlp_system_content, to_rodes_system_content, to_risen_system_content, create_llm_client, create_prompt_section

tasks_dir = r"../../natural-instructions/tasks"

SOCIAL_GOOD_TASK_IDS = [
    'task137_',
    'task327_', 'task333_', 'task335_', 'task337_',
    'task905_',
    'task320_',  # prompt formatted-ish, classification
    'task1502_', 'task1503_', 'task1504_',  # no prompt format: classification, classification, generation
    'task1664_',  # no prompt format: set of words as output
    'task1669_', 'task1670_',
    'task1720_', 'task1725_',  # no prompt format, binary classification
    'task904_',  # no prompt format, classification,
    'task277_', 'task278_', 'task279_', 'task280_', 'task316_', 'task317_', 'task318_', 'task319_', 'task320_',
    'task321_',
    'task108_',
    'task322_', 'task323_', 'task324_', 'task325_', 'task326_', 'task327_', 'task328_',
    'task1604_', 'task1605_', 'task1606_', 'task1607_',
    'task1721_', 'task1722_', 'task1723_', 'task1724_',
    'task607_', 'task608_', 'task609_', 'task286_'
]

SUPERNATURAL_INSTRUCTIONS_TASKS_WITH_NO_FORMAT = [
    'task1502_', 'task1503_', 'task1504_',  # no prompt format: classification, classification, generation
    'task1664_',  # no prompt format: set of words as output
    'task1669_', 'task1670_',
    'task1720_', 'task1725_',  # no prompt format, binary classification
    'task904_',  # no prompt format, classification
    'task108_',
    'task1604_', 'task1605_', 'task1606_', 'task1607_',
    'task1721_', 'task1722_', 'task1723_', 'task1724_',
    'task607_', 'task608_', 'task609_', 'task286_',
    'task1149_', 'task1189_'
]

FORMATTED_MULTIPLE_CHOICE_SUPERNATURAL_INSTRUCTIONS_TASKS = [  # ends up being one-field format
    'task065_', 'task1297_', 'task084_', 'task697_', 'task729_',
    'task1380_', 'task1381_', 'task309_', 'task1431_', 'task220_', 'task1612_', 'task190_', 'task1347_',
    'task069_', 'task070_',
    'task137_', 'task138_', 'task139_', 'task140_', 'task296_', 'task297_', 'task118_', 'task1135_',
    'task1424_', 'task1423_', 'task1422_', 'task1421_', 'task1420_', 'task1419_',
    'task1678_', 'task385_', 'task580_', 'task214_', 'task213_'
]

FORMATTED_TWO_TEXT_FIELDS_SUPERNATURAL_INSTRUCTIONS_TASKS = ['task1661_', 'task027_', 'task136_', 'task021_', 'task018_', 'task020_', 'task740_',
     'task1366_', 'task1162_', 'task1587_', 'task491_', 'task492_', 'task050_', 'task1387_',
     'task1186_', 'task1283_', 'task1284_', 'task905_', 'task501_']

FORMATTED_ONE_TEXT_FIELDS_SUPERNATURAL_INSTRUCTIONS_TASKS = [
    'task155_', 'task158_', 'task161_', 'task163_', 'task162_', 'task322_', 'task323_',
    'task324_', 'task325_', 'task326_', 'task327_', 'task328_', 'task333_', 'task335_',
    'task337_', 'task277_', 'task278_', 'task279_', 'task280_', 'task316_', 'task317_',
    'task113_', 'task114_']

max_tokens = 4000
gpt_models = ['gpt-4o-mini-2024-07-18', 'gpt-4o']  # gpt-4o gpt-4o-mini-2024-07-18
llama_models = ['llama3-70b-8192']


env_values = dotenv_values('../../.env')

client = create_llm_client(vals=env_values)


def to_cnlp(input: str):
    return client.complete_with_specified_model_and_retry_strategy(model="gpt-4o-2024-08-06", prompt=[create_prompt_section(role="system", content=to_cnlp_system_content), create_prompt_section(role="user", content=input)])


def to_risen(input: str):
    return client.complete_with_specified_model_and_retry_strategy(model="gpt-4o-2024-08-06", prompt=[create_prompt_section(role="system", content=to_risen_system_content), create_prompt_section(role="user", content=input)])


def to_rodes(input: str):
    return client.complete_with_specified_model_and_retry_strategy(model="gpt-4o-2024-08-06", prompt=[create_prompt_section(role="system", content=to_rodes_system_content), create_prompt_section(role="user", content=input)])


def predict_instance(used_model, llm, instance_input, definition, cnlp_definition, risen_definition, rodes_definition):
    nl_messages = LLM.get_msg(prompt=definition, user_input=instance_input, user_role_need=False)
    cnlp_messages = LLM.get_msg(prompt=cnlp_definition, user_input=instance_input, user_role_need=False)
    risen_messages = LLM.get_msg(prompt=risen_definition, user_input=instance_input, user_role_need=False)
    rodes_messages = LLM.get_msg(prompt=rodes_definition, user_input=instance_input, user_role_need=False)

    nl_output = llm.query(used_model, nl_messages)
    cnlp_output = llm.query(used_model, cnlp_messages)
    risen_output = llm.query(used_model, risen_messages)
    rodes_output = llm.query(used_model, rodes_messages)

    return nl_output, cnlp_output, risen_output, rodes_output


def run_task_request_cnlp(task, instance_num: int, used_models: list):
    current_time = datetime.now().strftime("%Y%m%d_%H%M")
    result_dir = "./add_result"

    dataloader = DataLoader(tasks_dir=tasks_dir, instance_num=instance_num)
    definition_list = []
    task_content = dataloader.get_task_content_random(task_filename=task)
    definition = task_content['definition'][0]
    _definition = "".join(['Please convert the following user requirement to corresponding prompt:\n', definition])
    print(1)
    instances = task_content['instances']

    def extract_definition(text):
        import re
        matches = re.findall(r'```(.*?)```', text, re.DOTALL)
        if matches:
            return matches[0].strip()
        else:
            return text

    cnlp_definition = extract_definition(to_cnlp(_definition))
    definition_list.append({
        "task_name": task,
        "type": "cnlp",
        "content": cnlp_definition
    })

    print(2)

    error_record = []
    for used_model in used_models:
        print(f'Start testing {task} by model {used_model} (CNLP only)...')

        result_list = []
        accuracy_list = []
        cnlp_correct_count = 0

        for index, instance in enumerate(instances):
            try:
                instance_input = instance['input']
                standard_output = ','.join(instance['output'])

                cnlp_output = client.complete_with_specified_model_and_retry_strategy(
                    model=used_model,
                    prompt=[create_prompt_section(role="system", content=cnlp_definition),
                            create_prompt_section(role="user", content=instance_input)]
                )

                if cnlp_output == standard_output:
                    cnlp_correct_count += 1

                result_list.append({
                    'task_name': task,
                    'instance_id': index + 1,
                    'instance_content': instance_input,
                    'standard_output': standard_output,
                    'cnlp_output': cnlp_output,
                    'cnlp_score': None,
                })
            except Exception as e:
                error_record.append({
                    'task_name': task,
                    'instance_id': index + 1,
                    'retry_model_name': used_model,
                    'error_reason': str(e),
                })

        cnlp_accuracy = cnlp_correct_count / instance_num
        accuracy_list.append({
            'task_name': task,
            'cnlp_accuracy': cnlp_accuracy,
        })

        definition_df = pd.DataFrame(definition_list)
        result_df = pd.DataFrame(result_list)
        accuracy_df = pd.DataFrame(accuracy_list)

        os.makedirs(os.path.join(result_dir, "definition"), exist_ok=True)
        os.makedirs(os.path.join(result_dir, "result"), exist_ok=True)
        os.makedirs(os.path.join(result_dir, "accuracy"), exist_ok=True)
        os.makedirs(os.path.join(result_dir, "error_record"), exist_ok=True)

        definition_path = os.path.join("./add_result/definition",
                                       f"{task}definition_cnlp_instance{instance_num}_tokens{max_tokens}_{current_time}.csv")
        result_path = os.path.join("./add_result/result",
                                   f"{task}result_cnlp_{used_model}_instance{instance_num}_tokens{max_tokens}_{current_time}.csv")
        accuracy_path = os.path.join("./add_result/accuracy",
                                     f"{task}accuracy_cnlp_{used_model}_instance{instance_num}_tokens{max_tokens}_{current_time}.csv")

        definition_df.to_csv(definition_path, index=False, encoding='utf-8')
        result_df.to_csv(result_path, index=False, encoding='utf-8')
        accuracy_df.to_csv(accuracy_path, index=False, encoding='utf-8')

        print('=' * 100 + '\n', definition_path, '\n', result_path, '\n', accuracy_path, '\n', '=' * 100)
        print(f'{task} (CNLP only) has been completed by model {used_model}.\n')

    if error_record:
        error_record_df = pd.DataFrame(error_record)
        error_record_path = os.path.join("./add_result/error_record",
                                         f"record_in_{current_time}.csv")
        error_record_df.to_csv(error_record_path, index=False, encoding='utf-8')

    print(f"The task {task} (CNLP only) has been completed by all the models:", used_models)


if __name__ == '__main__':
    instance_num = 50
    tasks = ['task190_']
    used_models = ['gpt-4o-mini-2024-07-18', 'gpt-4o', 'llama3-70b-8192']
    added_models = ['claude-3-haiku-20240307', 'ministral-8b-latest']
    all_models = ['gpt-4o-mini-2024-07-18', 'gpt-4o', 'gemini-1.5-pro-002', 'claude-3-haiku-20240307']
    # added_models = ['ministral-8b-latest', 'gpt-4o-mini-2024-07-18', 'gpt-4o', 'gemini-1.5-pro-002', 'claude-3-haiku-20240307']
    # 'gpt-4o-mini-2024-07-18', 'gpt-4o', 'gemini-1.5-pro-002', 'claude-3-haiku-20240307',
    #  'task385_', 'task729_', 'task1162_', 'task1424_', 'task1678_'
    for task in tasks:
        run_task_request_cnlp(task, instance_num, all_models)
