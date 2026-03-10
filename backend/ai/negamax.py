"""Negamax with Iterative Deepening, Killer Heuristic, and Transposition Table.

Negamax is a reformulation of minimax that exploits the zero-sum
property: ``value(state, playerA) = -value(state, playerB)``.  This
lets us eliminate the explicit *maximizing* flag — the current mover
always maximises, and child scores are negated on return.

**Alpha-Beta Pruning** is integrated via the standard negation + swap
trick::

    score = -negamax(child, depth-1, -beta, -alpha)

**Iterative Deepening** runs negamax at depths 1 → ``max_depth``
within a 900 ms wall-clock budget.  The best move from the deepest
completed search is returned.

**Killer Heuristic** remembers the two most recent actions that caused
a β-cutoff at each depth.  During move ordering, killers are tried
immediately after the TT best-move, improving pruning efficiency.

**Transposition Table** stores ``(score, depth, flag)`` triples with
EXACT / LOWER / UPPER flags, enabling sound cutoffs when the same
position is reached via different action sequences.

**Move Ordering Pipeline** (highest priority first):
  1. TT best-move (from previous shallower search)
  2. Killer moves for the current depth
  3. Domain heuristic: SPECIAL_SKILL > BASIC_ATTACK > DEFENSIVE_SHIELD > moves

Time complexity:
  Negamax:     O(b^d)       with branching factor b and depth d
  Alpha-Beta:  O(b^(d/2))   best case (perfect move ordering)
  + Transposition Table amortises repeated states
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Set, Tuple

try:
    from backend.game.actions import Action, apply_action, get_valid_actions
    from backend.game.state import GameState
    from backend.ai.heuristic import evaluate
    from backend.ai.cache import TranspositionTable, EXACT, LOWER, UPPER
except ImportError:
    try:
        from game.actions import Action, apply_action, get_valid_actions
        from game.state import GameState
        from ai.heuristic import evaluate
        from ai.cache import TranspositionTable, EXACT, LOWER, UPPER
    except ImportError:
        from actions import Action, apply_action, get_valid_actions  # type: ignore
        from state import GameState  # type: ignore
        from heuristic import evaluate  # type: ignore
        from cache import TranspositionTable, EXACT, LOWER, UPPER  # type: ignore


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WIN_SCORE: float = 10_000.0

# Domain priority for move ordering (higher = explored first)
_ACTION_ORDER: Dict[Action, int] = {
    Action.SPECIAL_SKILL:    4,
    Action.BASIC_ATTACK:     3,
    Action.DEFENSIVE_SHIELD: 2,
    Action.MOVE_UP:          1,
    Action.MOVE_DOWN:        1,
    Action.MOVE_LEFT:        1,
    Action.MOVE_RIGHT:       1,
}

# Number of killer-move slots per depth level
_KILLER_SLOTS: int = 2


class _TimeoutSentinel(Exception):
    """Raised when the time budget runs out mid-search."""


class NegamaxAgent:
    """Negamax agent with iterative deepening, killer heuristic, and TT.

    Attributes:
        agent_name:     Which side this agent plays.
        max_depth:      Depth cap for iterative deepening.
        time_budget_ms: Wall-clock millisecond budget per move.
        table:          Transposition table (``None`` if disabled).
        killers:        Killer-move table — ``Dict[int, List[Action]]``.
        best_moves:     TT best-move cache — ``Dict[tuple, Action]``.
        stats:          Per-call performance counters.
    """

    def __init__(
        self,
        agent_name: str,
        time_budget_ms: int = 900,
        max_depth: int = 10,
        use_tt: bool = True,
    ) -> None:
        self.agent_name: str = agent_name
        self.max_depth: int = max_depth
        self.time_budget_ms: int = time_budget_ms
        self.table: Optional[TranspositionTable] = (
            TranspositionTable() if use_tt else None
        )
        self.killers: Dict[int, List[Action]] = {}
        self.best_moves: Dict[tuple, Action] = {}
        self._deadline: float = 0.0
        self.stats: Dict[str, float] = {}
        # Tracks board positions seen in the real game (not search) to
        # penalise repetitions at leaf nodes and break oscillation loops.
        self._game_history: Dict[tuple, int] = {}
        # Tracks which actions have been taken from each board position so the
        # cycle-escape can force diversity when the same position recurs.
        self._used_actions_from: Dict[tuple, Set[Action]] = {}

    # -- public interface ---------------------------------------------------

    def choose_action(self, state: GameState) -> Action:
        """Return the best action via iterative deepening negamax."""
        start: float = time.perf_counter()

        self.stats = {
            "nodes_evaluated": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "time_ms": 0.0,
            "depth_reached": 0,
            "killer_hits": 0,
        }
        if self.table is not None:
            self.table.clear()
        self.killers.clear()
        self.best_moves.clear()

        # Record this real-game position before searching (for loop detection)
        pk = self._position_key(state)
        self._game_history[pk] = self._game_history.get(pk, 0) + 1

        self._deadline = start + self.time_budget_ms / 1000.0

        actions: List[Action] = get_valid_actions(state)
        if not actions:
            return Action.MOVE_DOWN  # fallback

        best_action: Action = actions[0]

        for d in range(1, self.max_depth + 1):
            if time.perf_counter() >= self._deadline:
                break
            try:
                candidate = self._root_search(state, actions, d)
                best_action = candidate
                self.stats["depth_reached"] = d
            except _TimeoutSentinel:
                break

            if time.perf_counter() >= self._deadline:
                break

        elapsed_ms = (time.perf_counter() - start) * 1000
        self.stats["time_ms"] = elapsed_ms
        if self.table is not None:
            self.stats["cache_hits"] = self.table.hit_count
            self.stats["cache_misses"] = self.table.miss_count

        # --- Root-level cycle escape (action diversity) ---
        # When we've been at this board config before AND we're about to reuse
        # an action tried previously from here, force a less-used alternative.
        # This fires AFTER the search so it never touches the negamax logic.
        current_count = self._game_history.get(pk, 0)
        if current_count >= 2:
            used = self._used_actions_from.get(pk, set())
            if best_action in used:
                for alt in actions:   # actions already available in scope
                    if alt not in used:
                        best_action = alt
                        break  # take first fresh action
        # Record which action we used from this position
        if pk not in self._used_actions_from:
            self._used_actions_from[pk] = set()
        self._used_actions_from[pk].add(best_action)

        return best_action

    # -- root search --------------------------------------------------------

    def _root_search(
        self,
        state: GameState,
        actions: List[Action],
        depth: int,
    ) -> Action:
        """Root-level negamax at a fixed depth."""
        ordered = self._order_moves(actions, state.to_tuple(), depth)
        best_score: float = float("-inf")
        best_action: Action = ordered[0]
        alpha: float = float("-inf")
        beta: float = float("inf")

        for action in ordered:
            child: GameState = apply_action(state, action)
            score = -self._negamax(child, depth - 1, -beta, -alpha)
            if score > best_score:
                best_score = score
                best_action = action
            alpha = max(alpha, score)

        # Store best move for TT move ordering
        self.best_moves[state.to_tuple()] = best_action
        return best_action

    # -- recursive negamax --------------------------------------------------

    def _negamax(
        self,
        state: GameState,
        depth: int,
        alpha: float,
        beta: float,
    ) -> float:
        """Recursive negamax with alpha-beta, TT, and killer heuristic."""
        if time.perf_counter() >= self._deadline:
            raise _TimeoutSentinel

        self.stats["nodes_evaluated"] += 1
        original_alpha: float = alpha

        # --- Terminal check ---
        if state.is_terminal():
            winner = state.get_winner()
            if winner == state.current_agent:
                return _WIN_SCORE
            elif winner is not None:
                return -_WIN_SCORE
            return 0.0  # draw

        # --- Leaf node ---
        if depth <= 0:
            score = evaluate(state, state.current_agent)
            # Penalise revisiting a real-game position (breaks oscillation loops)
            count = self._game_history.get(self._position_key(state), 0)
            if count > 0:
                score -= 50.0 * count
            return score

        # --- TT lookup ---
        state_key: tuple = state.to_tuple()
        if self.table is not None:
            tt_entry = self.table.get(state_key, depth)
            if tt_entry is not None:
                tt_score, _, tt_flag = tt_entry
                if tt_flag == EXACT:
                    return tt_score
                elif tt_flag == LOWER:
                    alpha = max(alpha, tt_score)
                elif tt_flag == UPPER:
                    beta = min(beta, tt_score)
                if alpha >= beta:
                    return tt_score

        # --- Recursive expansion ---
        actions: List[Action] = get_valid_actions(state)
        if not actions:
            return evaluate(state, state.current_agent)

        ordered = self._order_moves(actions, state_key, depth)

        best_score: float = float("-inf")
        best_action: Action = ordered[0]

        for action in ordered:
            child = apply_action(state, action)
            score = -self._negamax(child, depth - 1, -beta, -alpha)
            if score > best_score:
                best_score = score
                best_action = action
            alpha = max(alpha, score)
            if alpha >= beta:
                # β-cutoff — record killer move
                self._record_killer(depth, action)
                break

        # --- TT store ---
        if self.table is not None:
            if best_score <= original_alpha:
                flag = UPPER
            elif best_score >= beta:
                flag = LOWER
            else:
                flag = EXACT
            self.table.store(state_key, depth, best_score, flag)

        # Store best move for future move ordering
        self.best_moves[state_key] = best_action

        return best_score

    # -- move ordering ------------------------------------------------------

    def _order_moves(
        self,
        actions: List[Action],
        state_key: tuple,
        depth: int,
    ) -> List[Action]:
        """Order moves: TT best-move > killers > domain heuristic."""
        tt_move: Optional[Action] = self.best_moves.get(state_key)
        killer_list: List[Action] = self.killers.get(depth, [])

        def sort_key(a: Action) -> int:
            if a == tt_move:
                return 100
            if a in killer_list:
                self.stats["killer_hits"] = self.stats.get("killer_hits", 0) + 1
                return 50
            return _ACTION_ORDER.get(a, 0)

        return sorted(actions, key=sort_key, reverse=True)

    # -- killer heuristic ---------------------------------------------------

    def _position_key(self, state: GameState) -> tuple:
        """Spatial-only key for cycle/repetition detection.

        Uses only grid positions (not HP, energy, or cooldowns) so that
        small per-tick fluctuations in those values don't prevent matching
        a genuine spatial movement loop.
        """
        return (state.agent1.position, state.agent2.position)

    def _record_killer(self, depth: int, action: Action) -> None:
        """Store *action* as a killer move at *depth* (2 slots)."""
        # Skip moves (killers are most useful for tactical actions)
        if action in (Action.MOVE_UP, Action.MOVE_DOWN,
                      Action.MOVE_LEFT, Action.MOVE_RIGHT):
            return

        slots = self.killers.setdefault(depth, [])
        if action in slots:
            return
        if len(slots) < _KILLER_SLOTS:
            slots.append(action)
        else:
            # FIFO: evict oldest
            slots[0] = slots[1]
            slots[1] = action


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

    from game.arena import Arena
    from game.agent import Agent
    from game.state import GameState

    arena = Arena()
    a1 = Agent("agent1", position=(0, 0))
    a2 = Agent("agent2", position=(7, 7))
    state = GameState(a1, a2, arena)

    agent = NegamaxAgent("agent2", time_budget_ms=900, max_depth=10)
    action = agent.choose_action(state)
    print(f"Negamax chose: {action.value}")
    print(f"Stats: {agent.stats}")
    if agent.table:
        print(f"TT size: {agent.table.size()}, hit rate: {agent.table.hit_rate():.2%}")
