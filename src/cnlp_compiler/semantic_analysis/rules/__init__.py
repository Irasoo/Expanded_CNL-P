from .api_calls import APICallContractRule
from .examples import (
    ExampleCommandExistsRule,
    ExampleMutuallyExclusiveBranchesRule,
    ExampleOutputPathConsistencyRule,
)
from .references import GlobalReferenceRule, VariableFlowRule
from .types import APITypeRule
from .worker_calls import WorkerCallContractRule


DEFAULT_RULES = (
    GlobalReferenceRule(),
    VariableFlowRule(),
    APICallContractRule(),
    APITypeRule(),
    WorkerCallContractRule(),
    ExampleMutuallyExclusiveBranchesRule(),
    ExampleCommandExistsRule(),
    ExampleOutputPathConsistencyRule(),
)


__all__ = [
    "APICallContractRule",
    "APITypeRule",
    "DEFAULT_RULES",
    "ExampleCommandExistsRule",
    "ExampleMutuallyExclusiveBranchesRule",
    "ExampleOutputPathConsistencyRule",
    "GlobalReferenceRule",
    "VariableFlowRule",
    "WorkerCallContractRule",
]
