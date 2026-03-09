from pydantic_settings import BaseSettings
from typing_extensions import TypedDict, List, Literal


class SentenceRecognizerSettings(TypedDict):
    pass


class ParserLikeSettings(TypedDict):
    agent_sections: List[
        Literal[
            "DEFINE_PERSONA",
            "DEFINE_CONSTRAINTS",
            "DEFINE_TYPES",
            "DEFINE_VARIABLES",
            "DEFINE_WORKER",
            "DEFINE_AUDIENCE",
            "DEFINE_CONCEPTS"
        ]
    ]
    # sentence_recognizer: SentenceRecognizerSettings
    worker_sections: List[str]
    ignored_agent_sections: List[str]
    # 检查所有要求的字段是否存在。列表中存储着的是每个要求字段的路径列表，每个路径列表中存放的是其路径键名的一系列值。
    required_fields: List[List[str]]


class Settings(BaseSettings):
    OPENAI_MODEL: str
    OPENAI_API_KEY: str
    BASE_URL: str
    parser_like_settings: ParserLikeSettings

    class Config:
        env_file = ".env"


class OfflineSettings(BaseSettings):
    parser_like_settings: ParserLikeSettings


parser_like_settings = {
    "agent_sections": ["DEFINE_PERSONA", "DEFINE_CONSTRAINTS", "DEFINE_CONCEPTS", "DEFINE_TYPES", "DEFINE_VARIABLES","DEFINE_WORKER", "DEFINE_AUDIENCE"],
    "ignored_agent_sections": ["DEFINE_TYPES", "DEFINE_VARIABLES"],
    "worker_sections": ["INPUTS", "OUTPUTS", "EXAMPLES", "MAIN_FLOW", "ALTERNATIVE_FLOW", "EXCEPTION_FLOW"],
    "required_fields": [
        ['persona', 'ROLE'],
        ['worker', 'main_flow']
    ]
}


try:
    settings = Settings(parser_like_settings=parser_like_settings)
except:
    settings = OfflineSettings(parser_like_settings=parser_like_settings)