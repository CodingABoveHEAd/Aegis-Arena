"""Transposition Table — caches evaluated game states for search reuse.

A transposition table stores ``(score, depth)`` pairs keyed by a fully
hashable state tuple.  When the search encounters the same state again
it can reuse the stored score *provided* the stored depth is at least
as deep as the current request — a shallower stored result may be less
accurate and should be ignored.

The table also tracks hit / miss statistics so the caller can monitor
cache effectiveness.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple


class TranspositionTable:
    """Dictionary-backed transposition table with depth-aware lookups.

    Attributes:
        _store:     Internal mapping from state hash tuple to
                    ``(score, depth)`` pairs.
        hit_count:  Number of successful cache lookups.
        miss_count: Number of failed cache lookups.
    """

    def __init__(self) -> None:
        """Create an empty transposition table."""
        self._store: Dict[tuple, Tuple[float, int]] = {}
        self.hit_count: int = 0
        self.miss_count: int = 0

    # -- core operations ----------------------------------------------------

    def get(self, state_hash: tuple, depth: int) -> Optional[float]:
        """Retrieve a cached score if stored at sufficient depth.

        Args:
            state_hash: Hashable tuple representing the game state.
            depth:      Minimum search depth required for the result
                        to be usable.

        Returns:
            The cached evaluation score, or ``None`` if the state is
            not stored or was evaluated at a shallower depth.
        """
        entry = self._store.get(state_hash)
        if entry is not None:
            stored_score, stored_depth = entry
            if stored_depth >= depth:
                self.hit_count += 1
                return stored_score
        self.miss_count += 1
        return None

    def store(self, state_hash: tuple, depth: int, score: float) -> None:
        """Store (or overwrite) a score for the given state.

        Overwrites only if the new depth is greater than or equal to
        the existing stored depth (prefer deeper evaluations).

        Args:
            state_hash: Hashable tuple representing the game state.
            depth:      Depth at which this score was computed.
            score:      The evaluation score.
        """
        existing = self._store.get(state_hash)
        if existing is None or depth >= existing[1]:
            self._store[state_hash] = (score, depth)

    def clear(self) -> None:
        """Remove all entries and reset statistics."""
        self._store.clear()
        self.hit_count = 0
        self.miss_count = 0

    # -- statistics ---------------------------------------------------------

    def size(self) -> int:
        """Return the number of entries currently stored."""
        return len(self._store)

    def hit_rate(self) -> float:
        """Return the cache hit rate as a float in [0, 1].

        Returns 0.0 if no lookups have been made (avoids division by zero).
        """
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0.0


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tt = TranspositionTable()

    # Store a result at depth 3
    key = (100, 50, (0, 0), False, 0, 0, 100, 50, (7, 7), False, 0, 0, "agent1", 1)
    tt.store(key, depth=3, score=42.5)
    print(f"Size after 1 store: {tt.size()}")

    # Retrieve at depth <= stored depth → hit
    result = tt.get(key, depth=2)
    print(f"get(depth=2): {result}  (expected 42.5)")

    # Retrieve at depth > stored depth → miss
    result = tt.get(key, depth=5)
    print(f"get(depth=5): {result}  (expected None)")

    # Overwrite with deeper result
    tt.store(key, depth=5, score=55.0)
    result = tt.get(key, depth=5)
    print(f"get(depth=5) after deeper store: {result}  (expected 55.0)")

    print(f"\nHits: {tt.hit_count}, Misses: {tt.miss_count}")
    print(f"Hit rate: {tt.hit_rate():.2%}")

    tt.clear()
    print(f"Size after clear: {tt.size()}")
