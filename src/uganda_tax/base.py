"""The abstract :class:`Tax` base class shared by every tax in the engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from typing import ClassVar

from .context import ResultLine, TaxContext, TaxResult
from .money import Money


class Tax(ABC):
    """A tax that turns a :class:`TaxContext` into a :class:`TaxResult`.

    Subclasses implement :meth:`calculate`. They should validate the context
    fields they use and raise a :class:`~uganda_tax.exceptions.TaxError`
    subclass instead of returning a misleading zero.
    """

    #: Short display name, e.g. ``"PAYE"``.
    name: ClassVar[str] = "Tax"

    @abstractmethod
    def calculate(self, ctx: TaxContext) -> TaxResult:
        """Compute the liability for ``ctx``."""

    def __call__(self, ctx: TaxContext) -> TaxResult:
        """Allow ``tax(ctx)`` as shorthand for ``tax.calculate(ctx)``."""
        return self.calculate(ctx)

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"

    # ----- helper shared by subclasses ------------------------------------------
    def _result(
        self,
        base: Money,
        lines: Iterable[ResultLine],
        schedule: str = "",
        notes: Mapping[str, Money] | None = None,
    ) -> TaxResult:
        """Build a :class:`TaxResult` whose amount is the rounded sum of ``lines``.

        Rounding happens exactly once, here, so every tax follows the same rule.
        """
        lines = tuple(lines)
        unrounded = Money.sum(line.amount for line in lines)
        return TaxResult(
            tax=self.name,
            amount=unrounded.rounded(),
            unrounded=unrounded,
            base=base,
            lines=lines,
            schedule=schedule,
            notes=dict(notes or {}),
        )
