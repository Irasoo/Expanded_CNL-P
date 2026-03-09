from dataclasses import dataclass
from typing_extensions import Generic, TypeAlias, TypeVar, List, Literal
from .result import Failure

T = TypeVar("T", covariant=True)


@dataclass
class ContinueProcess(Generic[T]):
    value: T
    errors: List[Failure]


@dataclass
class StopProcess(Generic[T]):
    value: T
    reason: str
    errors: List[Failure]

ProcessDecision: TypeAlias = ContinueProcess[T] | StopProcess[T]