"""Monte Carlo Tree Search (MCTS) with UCB1 selection.

MCTS avoids the need for a perfect heuristic by estimating state value
through random simulated playouts (rollouts).  It balances:

* **Exploitation** — choosing moves that have won often
* **Exploration** — trying less-visited moves (controlled by constant C)

UCB1 formula::

    score = wins / visits + C * sqrt(ln(parent.visits) / visits)

``C = sqrt(2) ≈ 1.414`` is the standard exploration constant.

The four phases, repeated for each iteration:

1. **SELECT**        — traverse tree using UCB1 until an unexpanded node
2. **EXPAND**        — add one new child for an untried action
3. **SIMULATE**      — playout from the new node until terminal or max depth
4. **BACKPROPAGATE** — update wins / visits back up to the root

Time complexity note:
  Each iteration is O(d_select + d_rollout) where d_select is the tree
  depth and d_rollout is the maximum rollout length.  Total work is
  O(iterations × (d_select + d_rollout)).  Unlike Minimax, MCTS is
  anytime — more iterations yield better estimates without guaranteed
  exhaustive coverage.

Weighted rollout enhancement
-----------------------------
Instead of uniformly random action selection during rollouts, the
``_weighted_action`` method computes a softmax distribution over the
top-3 successor states (scored by the heuristic).  This biases
rollouts toward realistic play, improving result quality while
retaining stochastic diversity.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

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
        wins:             Cumulative reward passed through this node.
        untried_actions:  Actions not yet expanded from this node.
    """

    state: GameState
    parent: Optional["MCTSNode"] = None
    action_taken: Optional[Action] = None
    children: List["MCTSNode"] = field(default_factory=list)
    visits: int = 0
    wins: float = 0.0
    untried_actions: List[Action] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Populate untried actions from the game state."""
        if not self.untried_actions and not self.state.is_terminal():
            self.untried_actions = get_valid_actions(self.state)


# ---------------------------------------------------------------------------
# MCTS Agent
# ---------------------------------------------------------------------------

class MCTSAgent:
    """Monte Carlo Tree Search agent with UCB1 selection and weighted rollouts.

    Attributes:
        agent_name:        Which side this agent plays.
        iterations:        Number of MCTS iterations per ``choose_action``.
        exploration_c:     UCB1 exploration constant.
        max_rollout_depth: Maximum random-playout length.
        stats:             Per-call performance counters.
    """

    def __init__(
        self,
        agent_name: str,
        iterations: int = 500,
        exploration_c: float = 1.414,
        max_rollout_depth: int = 30,
    ) -> None:
        """Initialise the MCTS agent.

        Args:
            agent_name:        ``"agent1"`` or ``"agent2"``.
            iterations:        Search iterations per move decision.
            exploration_c:     UCB1 constant ``C``  (default √2).
            max_rollout_depth: Maximum depth for random playouts.
        """
        self.agent_name: str = agent_name
        self.iterations: int = iterations
        self.exploration_c: float = exploration_c
        self.max_rollout_depth: int = max_rollout_depth
        self.stats: Dict[str, float] = {
            "nodes_expanded": 0,
            "total_simulations": 0,
            "avg_simulation_depth": 0.0,
            "time_ms": 0.0,
        }

    # -- public interface ---------------------------------------------------

    def choose_action(self, state: GameState) -> Action:
        """Build an MCTS tree and return the most-visited root child's action.

        Args:
            state: The current game state.

        Returns:
            The ``Action`` of the root child with the highest visit count.
        """
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
            # 1. SELECT
            node: MCTSNode = self._select(root)

            # 2. EXPAND (if node has untried actions and is non-terminal)
            if node.untried_actions and not node.state.is_terminal():
                node = self._expand(node)

            # 3. SIMULATE
            result, depth = self._simulate(node.state)
            total_depth += depth
            self.stats["total_simulations"] += 1

            # 4. BACKPROPAGATE
            self._backpropagate(node, result)

        # Pick child with most visits (most robust choice)
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

    def _select(self, node: MCTSNode) -> MCTSNode:
        """Traverse the tree using UCB1 until a node with untried actions.

        If a fully expanded node has no children (terminal state), it is
        returned directly.

        Args:
            node: Current tree node.

        Returns:
            A node eligible for expansion (has untried actions) or a
            terminal node.
        """
        while not node.untried_actions and node.children:
            node = self._ucb1_child(node)
        return node

    def _expand(self, node: MCTSNode) -> MCTSNode:
        """Expand one untried action from *node*.

        Args:
            node: A non-terminal node with at least one untried action.

        Returns:
            The newly created child node.
        """
        action: Action = node.untried_actions.pop()
        child_state: GameState = apply_action(node.state, action)
        child = MCTSNode(state=child_state, parent=node, action_taken=action)
        node.children.append(child)
        self.stats["nodes_expanded"] += 1
        return child

    def _simulate(self, state: GameState) -> tuple[float, int]:
        """Random rollout from *state* with heuristic-weighted action selection.

        Returns:
            A ``(result, depth)`` tuple where *result* is +1 (win for
            ``self.agent_name``), −1 (loss), or 0 (draw / max depth),
            and *depth* is the number of steps taken.
        """
        sim_state: GameState = state.clone()
        depth: int = 0

        while not sim_state.is_terminal() and depth < self.max_rollout_depth:
            action: Action = self._weighted_action(sim_state)
            sim_state = apply_action(sim_state, action)
            depth += 1

        # Score the terminal / leaf state
        if sim_state.is_terminal():
            winner = sim_state.get_winner()
            if winner == self.agent_name:
                return 1.0, depth
            elif winner is not None:
                return -1.0, depth
        return 0.0, depth

    def _backpropagate(self, node: MCTSNode, result: float) -> None:
        """Propagate playout result up to the root, flipping at agent boundaries.

        At each node, ``visits`` is incremented and ``wins`` receives
        ``+result`` or ``−result`` depending on whose perspective the
        node represents.

        Args:
            node:   The leaf from which the rollout was performed.
            result: +1 for a ``self.agent_name`` win, −1 for a loss, 0 draw.
        """
        current: Optional[MCTSNode] = node
        while current is not None:
            current.visits += 1
            # If the node's state has our agent as the *next* mover,
            # then the previous move was the opponent's — so the
            # result sign flips.
            if current.state.current_agent == self.agent_name:
                current.wins += result
            else:
                current.wins -= result
            current = current.parent

    # -- helpers ------------------------------------------------------------

    def _ucb1_child(self, node: MCTSNode) -> MCTSNode:
        """Select the child of *node* with the highest UCB1 score.

        Children with zero visits are treated as having infinite UCB1
        (explored first).

        Args:
            node: A fully expanded parent node.

        Returns:
            The child with the highest UCB1 score.
        """
        log_parent: float = math.log(node.visits) if node.visits > 0 else 0.0
        best_score: float = float("-inf")
        best_child: MCTSNode = node.children[0]

        for child in node.children:
            if child.visits == 0:
                return child  # unvisited → explore immediately
            exploitation: float = child.wins / child.visits
            exploration: float = self.exploration_c * math.sqrt(log_parent / child.visits)
            score: float = exploitation + exploration
            if score > best_score:
                best_score = score
                best_child = child

        return best_child

    def _weighted_action(self, state: GameState) -> Action:
        """Select a rollout action using softmax over heuristic-scored successors.

        Evaluates the top-3 actions (by heuristic) and samples one
        proportionally to their softmax weights.  Falls back to uniform
        random if fewer than 2 actions are available.

        Args:
            state: The current rollout state.

        Returns:
            A single ``Action`` to apply.
        """
        actions: List[Action] = get_valid_actions(state)
        if len(actions) <= 1:
            return actions[0] if actions else Action.MOVE_DOWN

        # Determine perspective for heuristic
        perspective: str = state.current_agent

        # Score a subset of actions (top-3) for efficiency in rollout
        scored: List[tuple[float, Action]] = []
        for act in actions[:min(len(actions), 5)]:
            child = apply_action(state, act)
            h = evaluate(child, perspective)
            scored.append((h, act))
        scored.sort(key=lambda x: x[0], reverse=True)
        top3 = scored[:3]

        # Softmax over scores (temperature τ = 1.0)
        max_s: float = top3[0][0]
        exps: List[float] = [math.exp(s - max_s) for s, _ in top3]  # numerically stable
        total: float = sum(exps)
        probs: List[float] = [e / total for e in exps]

        # Weighted random choice
        r: float = random.random()
        cumulative: float = 0.0
        for prob, (_, act) in zip(probs, top3):
            cumulative += prob
            if r <= cumulative:
                return act
        return top3[-1][1]


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
