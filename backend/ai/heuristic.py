"""Heuristic evaluation for Aegis Arena game states.

Scores a ``GameState`` from the perspective of a named agent using a
weighted sum of tactical components.  The evaluation is used by
Minimax (and as a soft guide in MCTS weighted rollouts).

Design philosophy
-----------------
Each component captures a distinct tactical concern:

* **HP advantage** (×2.0) — the most decisive factor; more HP means
  more room for trades and survival.
* **Energy advantage** (×0.5) — energy enables abilities but is less
  immediately impactful than raw HP.
* **Position value** — tile-dependent bonus/penalty so the agent learns
  to seek cover/energy and avoid traps.
* **Distance control** — rewards aggressive positioning when leading in
  HP, and defensive spacing when trailing.
* **Elevation control** (×12 / −8) — being on high ground is a strong
  offensive advantage; the opponent being there is a threat.
* **Burn threat** (−6) — a burning agent is losing HP every tick;
  penalize this to encourage evasion and shield usage.
* **Skill readiness** (+8) — having the special skill available is a
  potent threat multiplier.
* **Shield readiness** (+3) — having the shield available adds
  defensive flexibility.

Weights were chosen to reflect game-theoretic precedence:
  HP > Position > Elevation > Skill > Energy > Shield > Distance.
"""

from __future__ import annotations

from typing import Tuple

try:
    from backend.game.arena import Arena, TileType
    from backend.game.state import GameState
except ImportError:
    try:
        from game.arena import Arena, TileType
        from game.state import GameState
    except ImportError:
        from arena import Arena, TileType  # type: ignore[no-redef]
        from state import GameState  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    """Manhattan distance between two grid positions."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


# ---------------------------------------------------------------------------
# Heuristic
# ---------------------------------------------------------------------------

def evaluate(state: GameState, agent_name: str) -> float:
    """Evaluate *state* from the perspective of *agent_name*.

    Positive scores favour *agent_name*; negative scores favour the
    opponent.

    Components (with default weights):

    1. **hp_advantage**      ``(my_hp − opp_hp) × 2.0``
    2. **energy_advantage**  ``(my_energy − opp_energy) × 0.5``
    3. **position_value**    +10 COVER, +6 ENERGY, −15 TRAP, +12 ELEVATED
    4. **distance_control**  ±5 / ±3 depending on HP lead and spacing
    5. **elevation_control** +12 on ELEVATED; −8 if opponent on ELEVATED
    6. **burn_threat**       −6 per active burn status
    7. **skill_readiness**   +8 if special skill is available
    8. **shield_readiness**  +3 if defensive shield is available

    Args:
        state:      The game state to evaluate.
        agent_name: ``"agent1"`` or ``"agent2"`` — the perspective.

    Returns:
        A float score (not bounded).
    """
    if agent_name == "agent1":
        me, opp = state.agent1, state.agent2
    else:
        me, opp = state.agent2, state.agent1

    arena: Arena = state.arena
    score: float = 0.0

    # 1. HP advantage — most critical resource
    score += (me.hp - opp.hp) * 2.0

    # 2. Energy advantage — enables abilities
    score += (me.energy - opp.energy) * 0.5

    # 3. Position value — tile-dependent bonus / penalty
    my_tile: TileType = arena.get_tile(*me.position)
    if my_tile == TileType.COVER:
        score += 10.0
    elif my_tile == TileType.ENERGY:
        score += 6.0
    elif my_tile == TileType.TRAP:
        score -= 15.0
    elif my_tile == TileType.ELEVATED:
        score += 12.0   # counted here AND in elevation_control

    # 4. Distance control
    dist: int = _manhattan(me.position, opp.position)
    if me.hp > opp.hp:
        # We're winning — reward aggressive positioning (close range)
        score += 5.0 if dist <= 2 else -3.0
    elif me.hp < opp.hp:
        # We're losing — reward defensive positioning (far range)
        score += 5.0 if dist >= 3 else -3.0
    else:
        # Equal HP — reward closing to engagement range to force a fight
        if dist <= 2:
            score += 4.0
        elif dist <= 4:
            score += 1.0
        else:
            score -= 2.0

    # 5. Elevation control — high ground is a strong advantage
    opp_tile: TileType = arena.get_tile(*opp.position)
    if my_tile == TileType.ELEVATED:
        score += 12.0
    if opp_tile == TileType.ELEVATED:
        score -= 8.0

    # 6. Burn threat — burning agent is losing HP passively
    if me.burn_turns > 0:
        score -= 6.0
    if opp.burn_turns > 0:
        score += 6.0

    # 7. Skill readiness — having the nuke available is a threat
    if me.skill_cooldown == 0 and me.energy >= 40:
        score += 8.0

    # 8. Shield readiness — defensive flexibility
    if me.shield_cooldown == 0 and me.energy >= 20:
        score += 3.0

    return score


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
    a1 = Agent("agent1", hp=80, energy=60, position=(1, 2))  # on COVER
    a2 = Agent("agent2", hp=100, energy=50, position=(7, 7))

    state = GameState(a1, a2, arena)
    s1 = evaluate(state, "agent1")
    s2 = evaluate(state, "agent2")
    print(f"Evaluation from agent1 perspective: {s1:+.1f}")
    print(f"Evaluation from agent2 perspective: {s2:+.1f}")
    print(f"(Sum should be near zero for symmetric components: {s1 + s2:+.1f})")
