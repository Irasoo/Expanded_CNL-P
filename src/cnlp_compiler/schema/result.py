from dataclasses import dataclass
from typing import Generic, Optional, TypeAlias, TypeVar


T = TypeVar("T", covariant=True)


@dataclass
class Success(Generic[T]):
    value: T


@dataclass
class Failure(Generic[T]):
    value: T
    is_fatal: bool
    error_type: str
    message: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    error_path: Optional[str] = None


Result: TypeAlias = Success[T] | Failure[T]
