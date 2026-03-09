SENTENCE_TYPE_REGISTRY: dict[str, callable] = {}

def register_sentence_type(name: str):

    def decorator(func):
        SENTENCE_TYPE_REGISTRY[name] = func
        return func
    return decorator

@register_sentence_type("INPUT")
def is_input_sentence(details: dict) -> bool:
    return details.get('IO') == 'input' or details.get('IO') == 'Input'

@register_sentence_type("OUTPUT")
def is_output_sentence(details: dict) -> bool:
    return details.get('IO') == 'output' or details.get('IO') == 'Output'

@register_sentence_type("COMMAND")
def is_command_sentence(details: dict) -> bool:
    return "flow" in details

@register_sentence_type("EXAMPLE")
def is_example_sentence(details: dict) -> bool:
    return "example_type" in details

def judge_sentence_type(details: dict) -> str:

    for sentence_type, check_func in SENTENCE_TYPE_REGISTRY.items():
        if check_func(details):
            return sentence_type

    return "UnKnow"