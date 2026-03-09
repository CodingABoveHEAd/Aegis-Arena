"""Minimax with Alpha-Beta Pruning, Transposition Table, and Iterative Deepening.

Minimax is a classic adversarial search algorithm for two-player
zero-sum games.  Starting from the current state it recursively
evaluates every reachable game tree node up to a fixed depth, assuming
the opponent plays optimally.

**Alpha-Beta Pruning** eliminates branches that provably cannot
influence the final decision, reducing average-case complexity from
O(b^d) to O(b^(d/2)) when moves are well-ordered.

**Transposition Table** (``cache.TranspositionTable``) stores
previously evaluated states.  When the same board position is reached
via different move sequences the cached score is reused, provided the
stored depth is adequate.

**Iterative Deepening** runs minimax at depths 1, 2, 3, … inside a
wall-clock budget (default 800 ms).  The best move from the deepest
completed search is returned.  This guarantees a legal move is always
available even under tight time constraints, while progressively
improving quality.

Time complexity note:
  Minimax:     O(b^d)       with branching factor b and depth d
  Alpha-Beta:  O(b^(d/2))   in the best case (good move ordering)
  + Transposition Table amortises repeated states
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

try:
    from backend.game.actions import Action, apply_action, get_valid_actions
    from backend.game.state import GameState
    from backend.ai.heuristic import evaluate
    from backend.ai.cache import TranspositionTable
except ImportError:
    try:
        from game.actions import Action, apply_action, get_valid_actions
        from game.state import GameState
        from ai.heuristic import evaluate
        from ai.cache import TranspositionTable
    except ImportError:
        from actions import Action, apply_action, get_valid_actions  # type: ignore
        from state import GameState  # type: ignore
        from heuristic import evaluate  # type: ignore
        from cache import TranspositionTable  # type: ignore


# ---------------------------------------------------------------------------
# Move ordering priority (higher = evaluated first for better pruning)
# ---------------------------------------------------------------------------

_ACTION_ORDER: Dict[Action, int] = {
    Action.SPECIAL_SKILL:    4,
    Action.BASIC_ATTACK:     3,
    Action.DEFENSIVE_SHIELD: 2,
    Action.MOVE_UP:          1,
    Action.MOVE_DOWN:        1,
    Action.MOVE_LEFT:        1,
    Action.MOVE_RIGHT:       1,
}

# Terminal utility constants (large enough to dominate any heuristic)
_WIN_SCORE: float = 10_000.0
_LOSS_SCORE: float = -10_000.0


class MinimaxAgent:
    """Minimax agent with Alpha-Beta Pruning and Transposition Table caching.

    Alpha-Beta Pruning eliminates branches that cannot affect the final
    decision, reducing average complexity from O(b^d) to O(b^(d/2)) in
    the best case.

    The Transposition Table stores previously evaluated states to avoid
    recomputation when the same board position is reached via different
    action sequences.

    Iterative Deepening searches at depths 1, 2, 3, … within a time
    budget, returning the best move from the deepest completed search.

    This agent always treats itself as the maximizing player.

    Attributes:
        agent_name: Which side this agent plays (``"agent1"`` or ``"agent2"``).
        max_depth:  Maximum search depth (for fixed-depth fallback).
        table:      Transposition table (``None`` if caching disabled).
        stats:      Per-call performance counters.
    """

    def __init__(
        self,
        agent_name: str,
        depth: int = 4,
        use_cache: bool = True,
        time_budget_ms: int = 800,
    ) -> None:
        """Initialise the minimax agent.

        Args:
            agent_name:     ``"agent1"`` or ``"agent2"``.
            depth:          Maximum search depth (used as a cap for
                            iterative deepening).
            use_cache:      Whether to enable the transposition table.
            time_budget_ms: Wall-clock millisecond budget for iterative
                            deepening.  Set to 0 to use fixed *depth*.
        """
        self.agent_name: str = agent_name
        self.max_depth: int = depth
        self.table: Optional[TranspositionTable] = (
            TranspositionTable() if use_cache else None
        )
        self.time_budget_ms: int = time_budget_ms
        self.stats: Dict[str, float] = {
            "nodes_evaluated": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "time_ms": 0.0,
            "depth_reached": 0,
        }

    # -- public interface ---------------------------------------------------

    def choose_action(self, state: GameState) -> Action:
        """Entry point — return the best action via iterative deepening.

        If ``time_budget_ms > 0``, runs minimax at increasing depths
        1 … ``max_depth``.  Otherwise falls back to a single search at
        ``max_depth``.

        Args:
            state: The current game state.

        Returns:
            The ``Action`` with the highest minimax value.
        """
        start: float = time.perf_counter()

        # Reset per-call stats
        self.stats = {
            "nodes_evaluated": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "time_ms": 0.0,
            "depth_reached": 0,
        }
        if self.table is not None:
            self.table.clear()

        actions: List[Action] = get_valid_actions(state)
        # Move ordering: evaluate high-value actions first (better pruning)
        actions.sort(key=lambda a: _ACTION_ORDER.get(a, 0), reverse=True)

        best_action: Action = actions[0]  # fallback

        if self.time_budget_ms > 0:
            best_action = self._iterative_deepening(state, actions, start)
        else:
            best_action = self._search_at_depth(state, actions, self.max_depth)

        elapsed_ms = (time.perf_counter() - start) * 1000
        self.stats["time_ms"] = elapsed_ms
        if self.table is not None:
            self.stats["cache_hits"] = self.table.hit_count
            self.stats["cache_misses"] = self.table.miss_count
        return best_action

    # -- iterative deepening ------------------------------------------------

    def _iterative_deepening(
        self,
        state: GameState,
        actions: List[Action],
        start: float,
    ) -> Action:
        """Run minimax at depths 1 … max_depth within the time budget.

        Args:
            state:   Current game state.
            actions: Pre-sorted legal actions.
            start:   ``time.perf_counter()`` timestamp when search began.

        Returns:
            The best action found by the deepest completed search.
        """
        best_action: Action = actions[0]
        deadline: float = start + self.time_budget_ms / 1000.0

        for d in range(1, self.max_depth + 1):
            if time.perf_counter() >= deadline:
                break

            try:
                candidate = self._search_at_depth(state, actions, d)
                best_action = candidate
                self.stats["depth_reached"] = d
            except _TimeoutSentinel:
                break  # partial depth — discard and keep previous result

            if time.perf_counter() >= deadline:
                break

        return best_action

    def _search_at_depth(
        self,
        state: GameState,
        actions: List[Action],
        depth: int,
    ) -> Action:
        """Root-level minimax at a fixed *depth*.

        Args:
            state:   Current game state.
            actions: Pre-sorted legal actions.
            depth:   Search depth.

        Returns:
            The action with the highest score.
        """
        best_score: float = float("-inf")
        best_action: Action = actions[0]
        alpha: float = float("-inf")
        beta: float = float("inf")

        for action in actions:
            child: GameState = apply_action(state, action)
            # Opponent's turn is minimizing
            score: float = self.minimax(child, depth - 1, alpha, beta, maximizing=False)
            if score > best_score:
                best_score = score
                best_action = action
            alpha = max(alpha, best_score)

        self.stats["depth_reached"] = max(self.stats.get("depth_reached", 0), depth)
        return best_action

    # -- recursive minimax --------------------------------------------------

    def minimax(
        self,
        state: GameState,
        depth: int,
        alpha: float,
        beta: float,
        maximizing: bool,
    ) -> float:
        """Recursive minimax with alpha-beta pruning.

        Args:
            state:      Current game state node.
            depth:      Remaining depth to search.
            alpha:      Best value the maximiser can guarantee so far.
            beta:       Best value the minimiser can guarantee so far.
            maximizing: ``True`` when it is the maximising player's turn.

        Returns:
            The minimax evaluation of *state*.
        """
        self.stats["nodes_evaluated"] += 1

        # --- Terminal check (before depth check) ---
        if state.is_terminal():
            winner = state.get_winner()
            if winner == self.agent_name:
                return _WIN_SCORE
            elif winner is not None:
                return _LOSS_SCORE
            return 0.0  # draw

        # --- Leaf node: evaluate with heuristic ---
        if depth <= 0:
            return evaluate(state, self.agent_name)

        # --- Transposition table lookup ---
        state_key: tuple = state.to_tuple()
        if self.table is not None:
            cached: Optional[float] = self.table.get(state_key, depth)
            if cached is not None:
                return cached

        # --- Recursive expansion ---
        actions: List[Action] = get_valid_actions(state)
        actions.sort(key=lambda a: _ACTION_ORDER.get(a, 0), reverse=True)

        if maximizing:
            value: float = float("-inf")
            for action in actions:
                child = apply_action(state, action)
                value = max(value, self.minimax(child, depth - 1, alpha, beta, False))
                alpha = max(alpha, value)
                if alpha >= beta:
                    break  # β-cutoff: minimiser would never allow this
        else:
            value = float("inf")
            for action in actions:
                child = apply_action(state, action)
                value = min(value, self.minimax(child, depth - 1, alpha, beta, True))
                beta = min(beta, value)
                if alpha >= beta:
                    break  # α-cutoff: maximiser already has a better option

        # --- Transposition table store ---
        if self.table is not None:
            self.table.store(state_key, depth, value)

        return value


class _TimeoutSentinel(Exception):
    """Internal sentinel raised when the time budget runs out mid-search."""


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

    from game.arena import Arena
    from game.agent import Agent
    from game.state import GameState

    arena = Arena()
    a1 = Agent("agent1", position=(0, 0))
    a2 = Agent("agent2", position=(7, 7))
    state = GameState(a1, a2, arena)

    agent = MinimaxAgent("agent1", depth=4, time_budget_ms=800)
    action = agent.choose_action(state)
    print(f"Minimax (iterative deepening) chose: {action.value}")
    print(f"Stats: {agent.stats}")
    if agent.table:
        print(f"TT size: {agent.table.size()}, hit rate: {agent.table.hit_rate():.2%}")
