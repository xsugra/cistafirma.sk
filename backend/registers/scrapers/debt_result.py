from dataclasses import dataclass
from enum import StrEnum


class DebtCheckState(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    # The source listed the company and published no amount for it. Not a
    # figure -- so it must never be written as one -- but not a failure either:
    # the source answered, the answer is on the record, and it says the company
    # is in the register. `soc_poist_debt` is the only source that can return
    # it, and the difference it makes is the difference between "we looked and
    # found nothing" and "we looked and found this".
    LISTED_NO_AMOUNT = "listed_no_amount"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DebtCheckResult:
    state: DebtCheckState
    amount: float | None = None
    error: str = ""
    error_type: str = ""
    # What the attempt had to say about itself, in the source's own terms. The
    # only state that currently sets it is `LISTED_NO_AMOUNT`, where the source
    # publishes the periods the company failed to report *instead of* a sum --
    # which is the claim, and losing it would leave the state unexplained.
    detail: str = ""

    @property
    def is_authoritative(self) -> bool:
        """Whether this answer settles the question for this company.

        True for every state but `UNKNOWN`. An authoritative answer is one the
        rotation may stop re-asking: it says something about the company rather
        than about our own ability to read the page. `LISTED_NO_AMOUNT` is
        authoritative and carries no figure, which is why callers must read
        `amount` rather than assume it is set.
        """
        return self.state in {
            DebtCheckState.FOUND,
            DebtCheckState.NOT_FOUND,
            DebtCheckState.LISTED_NO_AMOUNT,
        }

    @classmethod
    def found(cls, amount: float) -> "DebtCheckResult":
        return cls(state=DebtCheckState.FOUND, amount=amount)

    @classmethod
    def not_found(cls) -> "DebtCheckResult":
        return cls(state=DebtCheckState.NOT_FOUND, amount=0.0)

    @classmethod
    def listed_without_amount(cls, detail: str = "") -> "DebtCheckResult":
        """The company is in the register, and no sum is published for it.

        `amount` stays `None` on purpose. Zero would be a figure the source
        never printed, and the one thing this pipeline must not do is publish
        a number for somebody's debts that no register stated.
        """
        return cls(state=DebtCheckState.LISTED_NO_AMOUNT, detail=detail)

    @classmethod
    def unknown(cls, error: str, error_type: str) -> "DebtCheckResult":
        return cls(state=DebtCheckState.UNKNOWN, error=error, error_type=error_type)
