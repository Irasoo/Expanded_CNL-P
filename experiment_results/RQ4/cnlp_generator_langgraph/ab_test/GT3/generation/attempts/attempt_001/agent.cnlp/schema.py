from __future__ import annotations

from typing import Any, Literal
from typing_extensions import NotRequired, TypedDict


WriteOperation = Literal["SET", "APPEND"]
HistoryRole = Literal["system", "user", "assistant"]


class CNLPVariableInfo(TypedDict):
    """Configuration required to initialize one CNL-P variable."""

    variable_name: str
    # config.py imports generated types from schema.py and stores the actual
    # Python type object here.
    value_type: Any
    default_value: Any


class HistorySection(TypedDict):
    role: HistoryRole
    content: str


class ModelConfig(TypedDict):
    api_key: str
    model_name: str
    base_url: NotRequired[str | None]


class AgentConfig(TypedDict):
    variable_config: list[CNLPVariableInfo]
    agent_attributes: str
    model_config: ModelConfig


class BooleanResponse(TypedDict):
    result: bool


# CNL-P declared types are appended below this static section by the
# Native schema generator.

from typing import Literal, TypeAlias
from typing_extensions import NotRequired, TypedDict

PowerStatus: TypeAlias = Literal['adequate', 'underpowered', 'unavailable']

AnalysisOutcome: TypeAlias = Literal['significant_positive_safe', 'significant_positive_guardrail_concern', 'not_significant_positive', 'not_significant_flat', 'significant_negative', 'inconclusive']

Recommendation: TypeAlias = Literal['ship', 'investigate', 'extend', 'stop', 'dont_ship', 'undetermined']

class ABTestExperimentData(TypedDict):
    test_name: str
    hypothesis: str
    variant_change: str
    primary_metric: str
    control_sample_size: int | float
    control_successes: int | float
    variant_sample_size: int | float
    variant_successes: int | float
    duration_days: int | float
    control_traffic_share: int | float
    variant_traffic_share: int | float
    minimum_detectable_effect: NotRequired[int | float]
    guardrail_information: str

class ABTestStatistics(TypedDict):
    control_conversion_rate: int | float
    variant_conversion_rate: int | float
    absolute_difference: int | float
    relative_lift: NotRequired[int | float]
    p_value: int | float
    confidence_interval_lower: int | float
    confidence_interval_upper: int | float
    statistically_significant: bool
    power_status: 'PowerStatus'
    sample_ratio_mismatch: bool
