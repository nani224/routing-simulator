"""Censor interface and decision telemetry structures."""

from __future__ import annotations

import abc
import enum
from dataclasses import dataclass, field
from typing import Any


class CensorAction(enum.StrEnum):
    """Actions the censor can execute on an intercepted flow."""

    ALLOW = "ALLOW"
    THROTTLE = "THROTTLE"
    BLOCK = "BLOCK"


@dataclass
class CensorDecision:
    """Evaluation result emitted by a censor on inspecting packet metadata."""

    score: float  # Inspection suspicion score (0.0 stealth -> 1.0 certain violation)
    action: CensorAction
    confidence: float
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseCensor(abc.ABC):
    """Abstract base censor that inspects METADATA ONLY (size, direction, timestamp).

    Strictly forbidden from inspecting packet payloads or ciphertext bytes.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    @abc.abstractmethod
    def inspect(self, size: int, direction: str, timestamp: float) -> CensorDecision:
        """Evaluate packet metadata and produce an enforcement decision."""
        ...

    @abc.abstractmethod
    def reset(self) -> None:
        """Clear rolling inspection state for a new episode."""
        ...
