from dataclasses import dataclass
from typing_extensions import Generic, TypeAlias, TypeVar, Literal, Optional

T = TypeVar("T", covariant=True)

@dataclass
class Success(Generic[T]):
    """An object representing a successful operation with a result of type `T`."""
    value: T


@dataclass
class Failure(Generic[T]):
    """An object representing an operation that failed for the reason given in `message`."""
    value: T
    is_fatal: bool
    # TODO: there should be more types of error to be added
    error_type: Literal["unrecognized_sentence", "identifier_error", "reference_error"]
    message: str
    # when error is about syntax
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    # when error is about semantic
    error_path: Optional[str] = None


"""
An object representing a successful or failed operation of type `T`.
"""
Result: TypeAlias = Success[T] | Failure[T]