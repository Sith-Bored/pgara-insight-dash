"""Errors raised by parsing, validation, and allocation."""


class PGARAError(ValueError):
    """Base class for request and analysis failures that callers can handle."""

    error = "error"

    def __init__(self, message: str, line: int | None = None) -> None:
        self.line = line
        super().__init__(message)


class IRError(PGARAError):
    """The program text or structure is malformed."""

    error = "ir_validation_error"


class InputError(PGARAError):
    """A request violates a documented input policy."""

    error = "input_error"


class AllocationError(PGARAError):
    """The allocator produced an assignment that breaks its own invariant.

    This indicates a defect in the analyzer, not a bad user program.
    """

    error = "allocation_error"
