"""Result type shared by the four evaluators (T011, FR-102, FR-103, data-model §7)."""

from __future__ import annotations

from dataclasses import dataclass, field

CHECK_NAMES = ("schema", "invariants", "outcome", "quality")


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    score: float | None = None
    details: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.name not in CHECK_NAMES:
            raise ValueError(f"unknown check name: {self.name!r}")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "score": self.score,
            "details": list(self.details),
        }
