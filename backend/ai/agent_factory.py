"""Agent Factory — algorithm registry and creation.

Provides a central registry of available AI algorithms and a factory
function to instantiate agents by name.  This decouples the server
from concrete agent classes and makes it trivial to add new algorithms.

Usage::

    from backend.ai.agent_factory import create_agent, available_algorithms

    agent = create_agent("agent2", "negamax")
    algos = available_algorithms()  # ["minimax", "negamax", "mcts"]
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, Type

try:
    from backend.ai.minimax import MinimaxAgent
    from backend.ai.negamax import NegamaxAgent
    from backend.ai.mcts import MCTSAgent
except ImportError:
    try:
        from ai.minimax import MinimaxAgent  # type: ignore
        from ai.negamax import NegamaxAgent  # type: ignore
        from ai.mcts import MCTSAgent  # type: ignore
    except ImportError:
        from minimax import MinimaxAgent  # type: ignore
        from negamax import NegamaxAgent  # type: ignore
        from mcts import MCTSAgent  # type: ignore


# ---------------------------------------------------------------------------
# Registry: algorithm_name -> (class, default_kwargs)
# ---------------------------------------------------------------------------

_REGISTRY: Dict[str, Tuple[Type, Dict[str, Any]]] = {
    # depth=10 matches negamax's max_depth so minimax can search just as deep
    # within the same time budget (iterative deepening stops when time runs out).
    "minimax": (MinimaxAgent, {"depth": 10, "use_cache": True, "time_budget_ms": 900}),
    "negamax": (NegamaxAgent, {"time_budget_ms": 900, "max_depth": 10, "use_tt": True}),
    "mcts":    (MCTSAgent,    {"iterations": 1200}),
}

# Default algorithms per agent slot
DEFAULT_ALGORITHMS: Dict[str, str] = {
    "agent1": "minimax",
    "agent2": "negamax",
}


def available_algorithms() -> List[str]:
    """Return a sorted list of registered algorithm names."""
    return sorted(_REGISTRY.keys())


def create_agent(agent_name: str, algorithm: str) -> Any:
    """Instantiate an agent using the named algorithm.

    Args:
        agent_name: The agent slot (``"agent1"`` or ``"agent2"``).
        algorithm:  Algorithm key (e.g. ``"minimax"``, ``"negamax"``, ``"mcts"``).

    Returns:
        An agent instance with a ``choose_action(state)`` method.

    Raises:
        ValueError: If *algorithm* is not in the registry.
    """
    entry = _REGISTRY.get(algorithm)
    if entry is None:
        valid = ", ".join(available_algorithms())
        raise ValueError(f"Unknown algorithm {algorithm!r}. Choose from: {valid}")

    cls, default_kwargs = entry
    return cls(agent_name, **default_kwargs)
