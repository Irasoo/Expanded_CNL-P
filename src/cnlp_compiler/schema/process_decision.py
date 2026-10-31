from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeVar

from .result import Failure


T = TypeVar("T", covariant=True)


@dataclass
class ContinueProcess(Generic[T]):
    value: T
    errors: list[Failure]


@dataclass
class StopProcess(Generic[T]):
    value: T
    reason: str
    errors: list[Failure]


ProcessDecision: TypeAlias = ContinueProcess[T] | StopProcess[T]
