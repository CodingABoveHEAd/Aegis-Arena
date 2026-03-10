"""Heuristic evaluation for Aegis Arena game states.

Scores a ``GameState`` from the perspective of a named agent using a
weighted sum of tactical components.  The evaluation is used by
Minimax (and as a soft guide in MCTS heavy rollouts).

Design philosophy
-----------------
Each component captures a distinct tactical concern, rescaled so the
total range sits roughly in **[-200, +200]**:

* **HP advantage** (×1.8) — the most decisive factor; 200 HP swing
  maps to ~360 which dominates other terms at extremes.
* **Energy advantage** (×0.4) — energy enables abilities but is less
  immediately impactful than raw HP.
* **Position value** — tile-dependent bonus/penalty so the agent learns
  to seek cover/energy/heal and avoid traps.
* **Distance control** — rewards aggressive positioning when leading in
  HP, and defensive spacing when trailing.
* **Elevation control** (×14 / −10) — being on high ground is a strong
  offensive advantage; the opponent being there is a threat.
* **Burn penalty** (−8 × remaining ticks) — a burning agent is losing
  HP every tick; scales with remaining burn duration.
* **Threat awareness** — penalises the opponent having skill/shield
  ready while we do not.
* **Tile proximity** — rewards being near beneficial tiles (HEAL,
  ENERGY, COVER) and penalises being near traps.
* **Skill readiness** (+10) — having the special skill available is a
  potent threat multiplier.
* **Shield readiness** (+4) — having the shield available adds
  defensive flexibility.

Weights were chosen to reflect game-theoretic precedence:
  HP > Elevation > Skill > Position > Energy > Shield > Distance > Tile-prox.
"""

from __future__ import annotations

from typing import List, Tuple

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
# Helpers
# ---------------------------------------------------------------------------

def _manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    """Manhattan distance between two grid positions."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _nearest_tile_distance(
    arena: Arena,
    pos: Tuple[int, int],
    tile_types: List[TileType],
) -> int:
    """Return the Manhattan distance to the nearest tile of any listed type.

    Consumed tiles are excluded (they appear as EMPTY via ``get_tile``).
    If no matching tile exists, returns ``arena.size * 2`` (a large
    upper-bound sentinel value).
    """
    best = arena.size * 2
    for r in range(arena.size):
        for c in range(arena.size):
            if arena.get_tile(r, c) in tile_types:
                d = _manhattan(pos, (r, c))
                if d < best:
                    best = d
                    if d <= 1:
                        return d  # can't get closer than adjacent
    return best


# ---------------------------------------------------------------------------
# Heuristic
# ---------------------------------------------------------------------------

def evaluate(state: GameState, agent_name: str = None) -> float:
    """Evaluate *state* from the perspective of *agent_name*.

    Positive scores favour *agent_name*; negative scores favour the
    opponent.  Output range is approximately **[-200, +200]**.

    Args:
        state:      The game state to evaluate.
        agent_name: ``"agent1"`` or ``"agent2"`` — the perspective.
                    Defaults to ``state.current_agent`` if ``None``.

    Returns:
        A float score.
    """
    if agent_name is None:
        agent_name = state.current_agent

    if agent_name == "agent1":
        me, opp = state.agent1, state.agent2
    else:
        me, opp = state.agent2, state.agent1

    arena: Arena = state.arena
    score: float = 0.0

    # 1. HP advantage — most critical resource  (×1.8, range ±180)
    score += (me.hp - opp.hp) * 1.8

    # 2. Energy advantage  (×0.4, range ±40)
    score += (me.energy - opp.energy) * 0.4

    # 3. Position value — tile-dependent bonus / penalty
    my_tile: TileType = arena.get_tile(*me.position)
    _TILE_VALUE = {
        TileType.COVER: 12.0,
        TileType.ENERGY: 7.0,
        TileType.TRAP: -18.0,
        TileType.ELEVATED: 14.0,
    }
    # HEAL tile support (attribute may not exist in older builds)
    if hasattr(TileType, "HEAL"):
        _TILE_VALUE[TileType.HEAL] = 16.0
    score += _TILE_VALUE.get(my_tile, 0.0)

    # 4. Distance control
    dist: int = _manhattan(me.position, opp.position)
    hp_diff = me.hp - opp.hp
    if hp_diff > 15:
        # Strong lead — rush in
        score += max(8.0 - dist * 1.5, -4.0)
    elif hp_diff > 0:
        score += 5.0 if dist <= 2 else -3.0
    elif hp_diff < -15:
        # Far behind — stay away; seek resources
        score += min(dist * 1.2 - 2.0, 6.0)
    elif hp_diff < 0:
        score += 5.0 if dist >= 3 else -3.0
    else:
        # Equal HP — reward engagement range
        if dist <= 2:
            score += 5.0
        elif dist <= 4:
            score += 1.0
        else:
            score -= 2.0

    # 5. Elevation control — high ground is a strong advantage
    opp_tile: TileType = arena.get_tile(*opp.position)
    if my_tile == TileType.ELEVATED:
        score += 14.0
    if opp_tile == TileType.ELEVATED:
        score -= 10.0

    # 6. Burn penalty — scales with remaining ticks  (−8 per tick)
    if me.burn_turns > 0:
        score -= 8.0 * me.burn_turns
    if opp.burn_turns > 0:
        score += 8.0 * opp.burn_turns

    # 7. Skill readiness  (+10)
    if me.skill_cooldown == 0 and me.energy >= 40:
        score += 10.0

    # 8. Shield readiness  (+4)
    if me.shield_cooldown == 0 and me.energy >= 20:
        score += 4.0

    # 9. Threat awareness — penalise opponent's readiness
    if opp.skill_cooldown == 0 and opp.energy >= 40:
        score -= 6.0
    if opp.shield_cooldown == 0 and opp.energy >= 20:
        score -= 2.0

    # 10. Tile proximity — encourage moving toward good tiles
    beneficial_types = [TileType.COVER, TileType.ENERGY, TileType.ELEVATED]
    if hasattr(TileType, "HEAL") and me.hp < 70:
        beneficial_types.append(TileType.HEAL)

    near_good = _nearest_tile_distance(arena, me.position, beneficial_types)
    score += max(0.0, 4.0 - near_good * 0.8)  # up to +4 when adjacent

    near_trap = _nearest_tile_distance(arena, me.position, [TileType.TRAP])
    if near_trap <= 1:
        score -= 5.0  # penalise standing next to a trap

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
    a1 = Agent("agent1", hp=80, energy=60, position=(1, 2))
    a2 = Agent("agent2", hp=100, energy=50, position=(7, 7))

    state = GameState(a1, a2, arena)
    s1 = evaluate(state, "agent1")
    s2 = evaluate(state, "agent2")
    print(f"Evaluation from agent1 perspective: {s1:+.1f}")
    print(f"Evaluation from agent2 perspective: {s2:+.1f}")
    print(f"(Sum should be near zero for symmetric components: {s1 + s2:+.1f})")
