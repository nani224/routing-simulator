"""Anti-replay sliding window protection based on RFC 6479 / RFC 4303."""

from __future__ import annotations


class ReplayWindow:
    """Sliding window for detecting and rejecting replayed and duplicate packet sequence numbers."""

    def __init__(self, window_size: int = 128) -> None:
        self.window_size = window_size
        self.max_seq: int = 0
        self._bitmap: int = 0

    def check_and_update(self, seq: int) -> bool:
        """Check if sequence number is valid (not replayed or duplicate) and update window.

        Returns:
            True if packet is accepted (valid and new).
            False if packet is a duplicate or falls behind the sliding window.
        """
        if seq <= 0:
            return False

        if seq > self.max_seq:
            # Packet is ahead of highest seen sequence
            diff = seq - self.max_seq
            if diff >= self.window_size:
                self._bitmap = 1
            else:
                self._bitmap = (self._bitmap << diff) | 1
            self.max_seq = seq
            return True

        # Packet is older than or equal to highest seen sequence
        diff = self.max_seq - seq
        if diff >= self.window_size:
            # Sequence has fallen behind the sliding window
            return False

        mask = 1 << diff
        if (self._bitmap & mask) != 0:
            # Sequence already seen
            return False

        # Mark sequence as seen in window
        self._bitmap |= mask
        return True

    def reset(self) -> None:
        """Reset window state for a new session or after rekeying."""
        self.max_seq = 0
        self._bitmap = 0
