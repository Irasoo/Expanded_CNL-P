import fnmatch


def find_keys(self, pattern):
    """
    Searches for keys in the instance dictionary of the class that match the fuzzy matching pattern.

    Parameters: pattern: The fuzzy matching pattern, such as 'reference*' which will match 'reference1', 'reference2', etc.

    Returns: A dictionary where the keys are the full key paths and the values are the corresponding key values.

    Example:
    Suppose self.cnlp_ast_like is as follows:
       {
           "instruction": {
               "worker": "Obtain and report information",
               "input": {
                   "reference1": {
                       "asterisk": False,
                       "var_name": "user_account3"
                   }
               },
               "output": {
                   "reference2": {
                       "asterisk": False,
                       "var_name": "_report_info"
                   }
               },
               "main_flow": {
                   "sequential_block1": {
                       "command1": {
                           "type": "request_input",
                           "description_with_reference": {
                               "description": "Ask the user what type(game, finance, sport, movie, weather, google_news) of information they want and record the user's response."
                           },
                           "value": {
                               "var_name": "_request_type",
                               "var_type": "str",
                               "operation": "APPEND"
                           }
                       },
                       "command2": {
                           "type": "general_command",
                           "description_with_reference": {
                               "description": "NL..."
                           },
                           "result": {
                               "var_name": "json_info",
                               "var_type": "dict",
                               "operation": "APPEND"
                           }
                       }
                   },
                   "if_block1": {
                       "if_part": {
                           "condition": {
                               "description": "_request_type is google_news."
                           },
                           "command2": {
                               "type": "call_api",
                               "api_name": "get_google_news",
                               "paras": {
                                   "user": "user_account1"
                               },
                               "response": {
                                   "var_name": "json_info",
                                   "var_type": "dict",
                                   "operation": "SET"
                               }
                           }
                       },
                       "elif_part1": {
                           "condition": {
                               "description": "_request_type is game."
                           },
                           "command3": {
                               "type": "request_input",
                               "description_with_reference": {
                                   "description": "Ask the user for the keywords they want to search for."
                               },
                               "value": {
                                   "var_name": "_search_words",
                                   "var_type": "str",
                                   "operation": "SET"
                               }
                           },
                           "command4": {
                               "type": "call_api",
                               "api_name": "get_game_data",
                               "paras": {
                                   "user": "user_account1",
                                   "search_words": "_search_words"
                               },
                               "response": {
                                   "var_name": "json_info",
                                   "var_type": "dict",
                                   "operation": "SET"
                               }
                           }
                       },
                       ...
                   },
                   "sequential_block2": {
                       "command10": {
                           "type": "call_api",
                           "api_name": "transform_json_news",
                           "paras": {
                               "json_data": "json_info"
                           },
                           "response": {
                               "var_name": "_report_info",
                               "var_type": "str",
                               "operation": "APPEND"
                           }
                       },
                       "command11": {
                           "type": "display_message",
                           "description_with_reference": {
                               "description": "Displays the processed json information reference2.",
                               "reference2": {
                                   "asterisk": False,
                                   "var_name": "_report_info"
                               }
                           }
                       }
                   }
               }
           }
       }

       The return value of calling find_keys("command*"):
       {
           "instruction.main_flow.sequential_block1.command1": { ... },
           "instruction.main_flow.sequential_block1.command2": { ... },
           "instruction.main_flow.if_block1.if_part.command2": { ... },
           "instruction.main_flow.if_block1.elif_part1.command3": { ... },
           "instruction.main_flow.if_block1.elif_part1.command4": { ... },
           "instruction.main_flow.sequential_block2.command10": { ... },
           "instruction.main_flow.sequential_block2.command11": { ... }
       }
    """
    result = {}

    def recurse(data, key_path):
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{key_path}.{key}" if key_path else key
                if fnmatch.fnmatch(key, pattern):
                    result[new_path] = value
                recurse(value, new_path)
        elif isinstance(data, list):
            for index, item in enumerate(data):
                new_path = f"{key_path}[{index}]"
                recurse(item, new_path)

    recurse(self.cnlp_ast_like, "")

    return result