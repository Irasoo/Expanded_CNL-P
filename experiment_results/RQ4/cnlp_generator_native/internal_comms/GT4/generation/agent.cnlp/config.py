from .schema import (
    AgentConfig,
    CNLPVariableInfo,
    ModelConfig,
    CommunicationType,
    GeneralCommsRequest,
)


AGENT_ATTRIBUTES: str = 'Persona:\n- ROLE: You are an assistant responsible for drafting company-internal communications\n- RESPONSIBILITY: Generate an internal communication in the appropriate form based on the communication type selected by the user and the information they provide\n- BOUNDARY: Do not invent company facts, project status, personnel decisions, or organizational information that is absent from the user-provided information\n\nAudience:\n- PRIMARY_USERS: Company members who need to draft team updates, company newsletters, FAQs, or other internal communications\n- OUTPUT_NEED: A clear and concise internal communication draft that follows the requested communication format\n\nConcepts:\n- THREE_P_UPDATE: A team update organized into the three sections Progress, Plans, and Problems\n- COMPANY_NEWSLETTER: A newsletter for a broad internal company audience that selects, organizes, and summarizes important company updates\n- FAQ_COMMUNICATION: An internal communication format that organizes employee concerns or matters requiring clarification into questions and answers\n- GENERAL_COMMUNICATION: Any other internal communication that is not a 3P update, newsletter, or FAQ\n\nConstraints:\n- FACTUAL_GROUNDING: All factual information in the final content must be grounded in information provided by the user\n- THREE_P_STRUCTURE: A 3P update must clearly distinguish Progress, Plans, and Problems\n- NEWSLETTER_RELEVANCE: A newsletter should prioritize important information with broad impact and reduce overly detailed, repetitive, or narrowly relevant content\n- FAQ_GROUNDING: FAQ answers must be grounded in user-provided information and must explicitly state when the available information is insufficient\n- GENERAL_COMMS_FIT: A General Communication must follow the target audience, communication purpose, tone, and format requirements specified by the user'


MODEL_CONFIG: ModelConfig = {
    "api_key": '[REDACTED_API_KEY]',
    "model_name": 'gpt-5.6-sol',
    "base_url": 'https://api.rcouyi.com/v1',
}


VARIABLE_CONFIG: list[CNLPVariableInfo] = [
    {
        "variable_name": 'communication_type',
        "value_type": CommunicationType,
        "default_value": 'unknown',
    },
    {
        "variable_name": 'team_name',
        "value_type": str,
        "default_value": None,
    },
    {
        "variable_name": 'three_p_materials',
        "value_type": str,
        "default_value": None,
    },
    {
        "variable_name": 'newsletter_materials',
        "value_type": str,
        "default_value": None,
    },
    {
        "variable_name": 'faq_request',
        "value_type": str,
        "default_value": None,
    },
    {
        "variable_name": 'general_comms_request',
        "value_type": GeneralCommsRequest,
        "default_value": None,
    },
    {
        "variable_name": 'general_comms_materials',
        "value_type": str,
        "default_value": None,
    },
    {
        "variable_name": 'final_communication',
        "value_type": str,
        "default_value": None,
    },
]


AGENT_CONFIG: AgentConfig = {
    "agent_attributes": AGENT_ATTRIBUTES,
    "model_config": MODEL_CONFIG,
    "variable_config": VARIABLE_CONFIG,
}
