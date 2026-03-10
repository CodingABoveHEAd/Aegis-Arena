"""Monte Carlo Tree Search (MCTS) with PUCT selection.

Replaces the original UCB1-based MCTS with a more sophisticated engine
that incorporates:

1. **PUCT (Predictor + UCT)** — selection formula that balances exploit
   vs explore using a prior visit-count term instead of plain UCB1::

       Q(s,a) + c_puct × √(N_parent) / (1 + N_child)

   ``c_puct = 2.0`` by default.

2. **Heavy rollouts** — epsilon-greedy (ε = 0.2): with probability
   (1 − ε) the rollout picks the action with the best heuristic score;
   with probability ε a uniformly random action is chosen.  This keeps
   rollouts grounded in realistic play while retaining stochastic
   diversity.

3. **Progressive widening** — limits how many children are expanded
   from a node::

       children_allowed = max(2, floor(visits ^ 0.6))

   This focuses early search on the most promising branch subset.

4. **Loop detection** — a ``position_history`` counter (positions →
   visit count) is maintained during rollouts.  Revisiting a position
   incurs a −0.3 penalty per repeated visit, discouraging back-and-forth
   shuffling that wastes rollout depth.

5. **Negamax backpropagation** — uses an explicit ``path`` list
   assembled during the SELECT+EXPAND phase.  Result is negated at
   each level so every node accumulates value from its own mover's
   perspective.

6. **Priority-sorted untried actions** — combat actions are explored
   first (SPECIAL_SKILL > BASIC_ATTACK > DEFENSIVE_SHIELD > moves).

Time complexity note:
  Each iteration is O(d_select + d_rollout).  Total work is
  O(iterations × (d_select + d_rollout)).  Default: 1200 iterations,
  max rollout depth 30.
"""

from __future__ import annotations

import math
import random
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    from backend.game.actions import Action, apply_action, get_valid_actions
    from backend.game.state import GameState
    from backend.ai.heuristic import evaluate
except ImportError:
    try:
        from game.actions import Action, apply_action, get_valid_actions
        from game.state import GameState
        from ai.heuristic import evaluate
    except ImportError:
        from actions import Action, apply_action, get_valid_actions  # type: ignore
        from state import GameState  # type: ignore
        from heuristic import evaluate  # type: ignore


# ---------------------------------------------------------------------------
# MCTS Node
# ---------------------------------------------------------------------------

@dataclass
class MCTSNode:
    """A single node in the MCTS search tree.

    Attributes:
        state:            The game state at this node.
        parent:           The parent node (``None`` for the root).
        action_taken:     The action that led here from the parent.
        children:         Expanded child nodes.
        visits:           Number of times this node has been visited.
        value:            Cumulative reward (from the node's own mover
                          perspective after negamax flip).
        untried_actions:  Actions not yet expanded from this node.
    """

    state: GameState
    parent: Optional["MCTSNode"] = None
    action_taken: Optional[Action] = None
    children: List["MCTSNode"] = field(default_factory=list)
    visits: int = 0
    value: float = 0.0
    untried_actions: List[Action] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Populate untried actions from the game state, sorted by priority."""
        if not self.untried_actions and not self.state.is_terminal():
            actions = get_valid_actions(self.state)
            # Sort so highest-priority actions are at the END (popped first).
            priority = MCTSAgent._ACTION_PRIORITY
            actions.sort(key=lambda a: priority.get(a.value, 1))
            self.untried_actions = actions

    @property
    def q(self) -> float:
        """Mean value from this node's mover perspective."""
        return self.value / self.visits if self.visits > 0 else 0.0


# ---------------------------------------------------------------------------
# MCTS Agent
# ---------------------------------------------------------------------------

class MCTSAgent:
    """MCTS agent with PUCT selection, heavy rollouts, and progressive widening.

    Attributes:
        agent_name:        Which side this agent plays.
        iterations:        Number of MCTS iterations per ``choose_action``.
        c_puct:            PUCT exploration constant.
        max_rollout_depth: Maximum heavy-playout length.
        epsilon:           Probability of choosing a random action in rollout.
        widen_exp:         Progressive-widening exponent.
        loop_penalty:      Penalty per revisit during rollout.
        stats:             Per-call performance counters.
    """

    # Priority weights for action ordering — combat actions explored first.
    _ACTION_PRIORITY: Dict[str, int] = {
        "SPECIAL_SKILL": 4,
        "BASIC_ATTACK": 3,
        "DEFENSIVE_SHIELD": 2,
    }

    def __init__(
        self,
        agent_name: str,
        iterations: int = 1200,
        c_puct: float = 2.0,
        max_rollout_depth: int = 30,
        epsilon: float = 0.2,
        widen_exp: float = 0.6,
        loop_penalty: float = 0.3,
    ) -> None:
        self.agent_name: str = agent_name
        self.iterations: int = iterations
        self.c_puct: float = c_puct
        self.max_rollout_depth: int = max_rollout_depth
        self.epsilon: float = epsilon
        self.widen_exp: float = widen_exp
        self.loop_penalty: float = loop_penalty
        self.stats: Dict[str, float] = {}

    # -- public interface ---------------------------------------------------

    def choose_action(self, state: GameState) -> Action:
        """Build an MCTS tree and return the most-visited root child's action."""
        start: float = time.perf_counter()
        self.stats = {
            "nodes_expanded": 0,
            "total_simulations": 0,
            "avg_simulation_depth": 0.0,
            "time_ms": 0.0,
        }

        root = MCTSNode(state=state)
        total_depth: int = 0

        for _ in range(self.iterations):
            # 1. SELECT + EXPAND — collect path for backprop
            path: List[MCTSNode] = []
            node = self._select(root, path)

            # 2. EXPAND (progressive widening gate)
            if node.untried_actions and not node.state.is_terminal():
                allowed = max(2, int(math.pow(max(node.visits, 1), self.widen_exp)))
                if len(node.children) < allowed:
                    node = self._expand(node)
                    path.append(node)

            # 3. SIMULATE (heavy rollout)
            result, depth = self._simulate(node)
            total_depth += depth
            self.stats["total_simulations"] += 1

            # 4. BACKPROPAGATE (negamax via path)
            self._backpropagate(path, result)

        # Pick child with most visits (most robust choice)
        if not root.children:
            # Fallback: if no children were expanded, return first valid action
            actions = get_valid_actions(state)
            return actions[0] if actions else Action.MOVE_DOWN

        best_child: MCTSNode = max(root.children, key=lambda c: c.visits)
        assert best_child.action_taken is not None

        elapsed_ms = (time.perf_counter() - start) * 1000
        self.stats["time_ms"] = elapsed_ms
        sim_count = self.stats["total_simulations"]
        self.stats["avg_simulation_depth"] = (
            total_depth / sim_count if sim_count > 0 else 0.0
        )

        return best_child.action_taken

    # -- MCTS phases --------------------------------------------------------

    def _select(self, node: MCTSNode, path: List[MCTSNode]) -> MCTSNode:
        """Traverse the tree using PUCT, appending each visited node to *path*.

        Stops at a node that has untried actions (subject to progressive
        widening) or is terminal.
        """
        path.append(node)
        while not node.state.is_terminal():
            # Check progressive-widening limit
            allowed = max(2, int(math.pow(max(node.visits, 1), self.widen_exp)))
            if node.untried_actions and len(node.children) < allowed:
                break  # need to expand
            if not node.children:
                break  # terminal-like (no actions at all)
            node = self._puct_child(node)
            path.append(node)
        return node

    def _expand(self, node: MCTSNode) -> MCTSNode:
        """Expand one untried action from *node*."""
        action: Action = node.untried_actions.pop()
        child_state: GameState = apply_action(node.state, action)
        child = MCTSNode(state=child_state, parent=node, action_taken=action)
        node.children.append(child)
        self.stats["nodes_expanded"] += 1
        return child

    def _simulate(self, node: MCTSNode) -> Tuple[float, int]:
        """Heavy rollout from *node* using epsilon-greedy action selection.

        Returns ``(result, depth)`` where *result* is in [-1, +1] and
        *depth* is the number of steps taken.
        """
        sim_state: GameState = node.state.clone()
        depth: int = 0
        # Loop detection: position_history tracks (agent_pos, current_agent)
        position_history: Counter = Counter()
        penalty: float = 0.0

        while not sim_state.is_terminal() and depth < self.max_rollout_depth:
            # Record position for loop detection
            pos_key = (
                sim_state.agent1.position,
                sim_state.agent2.position,
                sim_state.current_agent,
            )
            position_history[pos_key] += 1
            if position_history[pos_key] > 1:
                penalty += self.loop_penalty

            # Epsilon-greedy action selection
            action = self._heavy_action(sim_state)
            sim_state = apply_action(sim_state, action)
            depth += 1

        # Score the terminal / leaf state
        result: float
        if sim_state.is_terminal():
            winner = sim_state.get_winner()
            if winner == self.agent_name:
                result = 1.0
            elif winner is not None:
                result = -1.0
            else:
                result = 0.0
        else:
            # Non-terminal: use heuristic, scaled to [-1, +1]
            h = evaluate(sim_state, self.agent_name)
            result = max(-1.0, min(1.0, h / 200.0))

        # Apply loop penalty (reduce magnitude toward 0)
        if penalty > 0.0:
            result *= max(0.0, 1.0 - penalty)

        return result, depth

    def _backpropagate(self, path: List[MCTSNode], result: float) -> None:
        """Negamax backpropagation along the collected *path*.

        The result is from the MCTS agent's perspective.  At each node
        in the path the sign is set according to whether the node's
        mover matches ``self.agent_name``.
        """
        for node in reversed(path):
            node.visits += 1
            # If the node's current_agent is the MCTS agent, the result
            # is positive when the MCTS agent wins.  Otherwise negate.
            if node.state.current_agent == self.agent_name:
                node.value += result
            else:
                node.value -= result

    # -- helpers ------------------------------------------------------------

    def _puct_child(self, node: MCTSNode) -> MCTSNode:
        """Select the child of *node* with the highest PUCT score.

        PUCT formula::

            Q_child + c_puct × √(N_parent) / (1 + N_child)

        Children with zero visits get an infinite exploration bonus.
        """
        sqrt_parent: float = math.sqrt(node.visits) if node.visits > 0 else 1.0
        best_score: float = float("-inf")
        best_child: MCTSNode = node.children[0]

        for child in node.children:
            if child.visits == 0:
                return child  # unvisited → explore immediately
            exploit: float = child.q
            explore: float = self.c_puct * sqrt_parent / (1.0 + child.visits)
            score: float = exploit + explore
            if score > best_score:
                best_score = score
                best_child = child

        return best_child

    def _heavy_action(self, state: GameState) -> Action:
        """Epsilon-greedy action selection for heavy rollouts.

        With probability ``epsilon`` a uniformly random action is chosen.
        Otherwise the action yielding the best heuristic score (from the
        current mover's perspective) is selected.
        """
        actions: List[Action] = get_valid_actions(state)
        if len(actions) <= 1:
            return actions[0] if actions else Action.MOVE_DOWN

        if random.random() < self.epsilon:
            return random.choice(actions)

        # Greedy: pick action with best immediate heuristic
        current_agent = state.current_agent
        best_action: Action = actions[0]
        best_val: float = float("-inf")
        for a in actions:
            successor = apply_action(state, a)
            val = evaluate(successor, current_agent)
            if val > best_val:
                best_val = val
                best_action = a
        return best_action


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

    from game.arena import Arena
    from game.agent import Agent
    from game.state import GameState

    random.seed(42)

    arena = Arena()
    a1 = Agent("agent1", position=(0, 0))
    a2 = Agent("agent2", position=(7, 7))
    state = GameState(a1, a2, arena)

    agent = MCTSAgent("agent1", iterations=200)
    action = agent.choose_action(state)
    print(f"MCTS chose: {action.value}")
    print(f"Stats: {agent.stats}")
