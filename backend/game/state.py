"""State module — immutable, hashable snapshot of the game.

``GameState`` bundles both agents, the arena reference, the active
player tag, and the turn counter.  It is designed for use as a
transposition-table key (via ``__hash__`` / ``__eq__`` backed by
``to_tuple``), and provides a ``clone`` method that deep-copies the
agents but *shares* the arena (only trap timers are mutable on the
arena, and those are part of the global board state not per-search).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

try:
    from .agent import Agent
    from .arena import Arena
except ImportError:  # running as standalone script
    from agent import Agent  # type: ignore[no-redef]
    from arena import Arena  # type: ignore[no-redef]


class GameState:
    """Complete snapshot of the game at a single point in time.

    Attributes:
        agent1:        The first player.
        agent2:        The second player.
        current_agent: Tag of the agent whose turn it is
                       (``"agent1"`` or ``"agent2"``).
        turn_count:    Current turn number (starts at 1).
        arena:         Shared arena reference.
    """

    MAX_TURNS: int = 200

    def __init__(
        self,
        agent1: Agent,
        agent2: Agent,
        arena: Arena,
        current_agent: str = "agent1",
        turn_count: int = 1,
    ) -> None:
        """Initialise a game state.

        Args:
            agent1:        First player agent.
            agent2:        Second player agent.
            arena:         The game board (shared, **not** copied).
            current_agent: Who moves next (``"agent1"`` or ``"agent2"``).
            turn_count:    Turn number.
        """
        self.agent1: Agent = agent1
        self.agent2: Agent = agent2
        self.arena: Arena = arena
        self.current_agent: str = current_agent
        self.turn_count: int = turn_count
        self.last_event: Optional[Dict[str, Any]] = None

    # -- hashable representation -------------------------------------------

    def to_tuple(self) -> Tuple[Any, ...]:
        """Return a fully hashable tuple encoding all mutable game state.

        This is used as the key in transposition tables to recognise
        previously evaluated positions.

        Returns:
            A flat tuple of primitive values capturing both agents'
            state, the active player, and the turn counter.
        """
        a1 = self.agent1
        a2 = self.agent2
        return (
            a1.hp, a1.energy, a1.position, a1.shield_active,
            a1.skill_cooldown, a1.shield_cooldown,
            a1.burn_turns, a1.slow_active,
            a2.hp, a2.energy, a2.position, a2.shield_active,
            a2.skill_cooldown, a2.shield_cooldown,
            a2.burn_turns, a2.slow_active,
            self.current_agent,
            self.turn_count,
            tuple(sorted(self.arena.consumed_tiles)),
        )

    def __hash__(self) -> int:
        return hash(self.to_tuple())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GameState):
            return NotImplemented
        return self.to_tuple() == other.to_tuple()

    # -- terminal conditions ------------------------------------------------

    def is_terminal(self) -> bool:
        """Check whether the game is over (at least one agent eliminated or turn limit reached).

        Returns:
            ``True`` if either agent's HP has reached zero or max turns exceeded.
        """
        return self.agent1.hp <= 0 or self.agent2.hp <= 0 or self.turn_count > self.MAX_TURNS

    def get_winner(self) -> Optional[str]:
        """Determine the winner, if any.

        Returns:
            ``"agent1"`` if agent 2 is eliminated, ``"agent2"`` if
            agent 1 is eliminated, or ``None`` if no winner yet (or
            simultaneous KO, which shouldn't happen in a turn-based game).
            When turn limit is exceeded, the agent with higher HP wins.
        """
        if self.agent1.hp <= 0 and self.agent2.hp <= 0:
            return None  # draw / simultaneous KO edge-case
        if self.agent2.hp <= 0:
            return "agent1"
        if self.agent1.hp <= 0:
            return "agent2"
        # Turn limit exceeded — higher HP wins
        if self.turn_count > self.MAX_TURNS:
            if self.agent1.hp > self.agent2.hp:
                return "agent1"
            elif self.agent2.hp > self.agent1.hp:
                return "agent2"
        return None

    # -- cloning ------------------------------------------------------------

    def clone(self) -> "GameState":
        """Deep-copy the state for speculative search.

        Both agents are independently cloned; the arena is shared
        (its layout is static except for trap timers, which belong
        to the global board, not to a search branch).
        consumed_tiles is shallow-copied so search branches stay
        independent.

        Returns:
            A new ``GameState`` with cloned agents and the same arena.
        """
        cloned = GameState(
            agent1=self.agent1.clone(),
            agent2=self.agent2.clone(),
            arena=self.arena,           # shared reference
            current_agent=self.current_agent,
            turn_count=self.turn_count,
        )
        # Ensure search branches don't share the consumed set
        cloned.arena = self.arena  # still shared grid
        # We need a copy of the mutable consumed_tiles per branch
        import copy as _copy
        cloned_arena_consumed = self.arena.consumed_tiles.copy()
        # Patch: create a lightweight arena wrapper won't work cleanly.
        # Instead, clone the arena for search branches too.
        cloned.arena = _copy.copy(self.arena)
        cloned.arena.consumed_tiles = cloned_arena_consumed
        cloned.arena.trap_timers = dict(self.arena.trap_timers)
        cloned.arena.tile_durability = dict(self.arena.tile_durability)
        cloned.last_event = None  # events are transient, not carried into search
        return cloned

    # -- serialization ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the full game state to a JSON-friendly dictionary.

        Returns:
            Dict containing agents, arena grid, current player, and
            turn count.
        """
        return {
            "agent1": self.agent1.to_dict(),
            "agent2": self.agent2.to_dict(),
            "current_agent": self.current_agent,
            "turn_count": self.turn_count,
            "arena": self.arena.to_grid_list(),
        }

    def __repr__(self) -> str:
        return (
            f"GameState(turn={self.turn_count}, current={self.current_agent}, "
            f"a1_hp={self.agent1.hp}, a2_hp={self.agent2.hp})"
        )


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    arena = Arena()
    a1 = Agent("agent1", position=(0, 0))
    a2 = Agent("agent2", position=(7, 7))

    state = GameState(a1, a2, arena)
    print(f"State: {state}")
    print(f"Hash:  {hash(state)}")
    print(f"Tuple: {state.to_tuple()}")

    # Clone independence
    s2 = state.clone()
    s2.agent1.hp = 1
    print(f"\nOriginal a1 hp={state.agent1.hp}, Clone a1 hp={s2.agent1.hp}")

    # Hash consistency
    s3 = state.clone()
    print(f"state == s3? {state == s3}")
    print(f"hash match?  {hash(state) == hash(s3)}")

    # Terminal / winner
    state.agent2.hp = 0
    print(f"\nIs terminal? {state.is_terminal()}")
    print(f"Winner:      {state.get_winner()}")

    # Serialization
    import json
    state.agent2.hp = 50  # restore for readable output
    print(f"\nto_dict:\n{json.dumps(state.to_dict(), indent=2)}")
