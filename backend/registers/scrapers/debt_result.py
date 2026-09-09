from dataclasses import dataclass
from enum import StrEnum


class DebtCheckState(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DebtCheckResult:
    state: DebtCheckState
    amount: float | None = None
    error: str = ""
    error_type: str = ""

    @property
    def is_authoritative(self) -> bool:
        return self.state in {DebtCheckState.FOUND, DebtCheckState.NOT_FOUND}

    @classmethod
    def found(cls, amount: float) -> "DebtCheckResult":
        return cls(state=DebtCheckState.FOUND, amount=amount)

    @classmethod
    def not_found(cls) -> "DebtCheckResult":
        return cls(state=DebtCheckState.NOT_FOUND, amount=0.0)

    @classmethod
    def unknown(cls, error: str, error_type: str) -> "DebtCheckResult":
        return cls(state=DebtCheckState.UNKNOWN, error=error, error_type=error_type)
