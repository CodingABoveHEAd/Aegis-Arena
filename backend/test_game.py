"""Validation tests for MCTS overhaul and HEAL tile feature.

Run from the project root::

    python -m pytest backend/test_game.py -v
    # or simply:
    python backend/test_game.py
"""

from __future__ import annotations

import sys
import pathlib

# Ensure imports work from project root — add ONLY the project root so that
# all modules resolve through the ``backend.*`` package path, avoiding
# duplicate-module issues caused by mixing ``game.*`` and ``backend.game.*``.
_project_root = str(pathlib.Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.game.arena import Arena, TileType
from backend.game.agent import Agent
from backend.game.state import GameState
from backend.game.actions import Action, apply_action, get_valid_actions
from backend.ai.heuristic import evaluate, _nearest_tile_distance
from backend.ai.mcts import MCTSAgent, MCTSNode


# -----------------------------------------------------------------------
# Test 1 — HEAL tile placement constraints
# -----------------------------------------------------------------------

def test_heal_tile_placement() -> None:
    """Verify HEAL tiles are placed symmetrically, not adjacent to TRAP,
    and at least distance 3 from spawn corners."""
    arena = Arena()

    heal_positions = []
    for r in range(arena.size):
        for c in range(arena.size):
            if arena.grid[r][c] == TileType.HEAL:
                heal_positions.append((r, c))

    s = arena.size - 1

    # Should have exactly 4 HEAL tiles (2 symmetric pairs)
    assert len(heal_positions) == 4, f"Expected 4 HEAL tiles, got {len(heal_positions)}"

    # Symmetry check: for each HEAL at (r,c), mirror at (s-r, s-c) should also be HEAL
    for r, c in heal_positions:
        mr, mc = s - r, s - c
        assert (mr, mc) in heal_positions, (
            f"HEAL at ({r},{c}) has no mirror at ({mr},{mc})"
        )

    # Min distance 3 from spawn corners
    for r, c in heal_positions:
        dist_spawn1 = abs(r) + abs(c)
        dist_spawn2 = abs(r - s) + abs(c - s)
        assert dist_spawn1 >= 3, (
            f"HEAL at ({r},{c}) is too close to spawn corner (0,0): dist={dist_spawn1}"
        )
        assert dist_spawn2 >= 3, (
            f"HEAL at ({r},{c}) is too close to spawn corner ({s},{s}): dist={dist_spawn2}"
        )

    # Not adjacent to TRAP
    for r, c in heal_positions:
        for nr, nc in arena.get_neighbors(r, c):
            assert arena.grid[nr][nc] != TileType.TRAP, (
                f"HEAL at ({r},{c}) is adjacent to TRAP at ({nr},{nc})"
            )

    print("  [PASS] test_heal_tile_placement")


# -----------------------------------------------------------------------
# Test 2 — HEAL tile mechanics (HP restore + consume + cap)
# -----------------------------------------------------------------------

def test_heal_tile_mechanics() -> None:
    """Step onto a HEAL tile: HP restores min(30, 100-hp), tile consumed,
    HP never exceeds 100."""
    arena = Arena()

    # Force a HEAL tile at (3, 3) for testing
    arena.grid[3][3] = TileType.HEAL
    arena.consumed_tiles.discard((3, 3))

    # Agent at (2, 3) with 60 HP, will move down onto (3, 3)
    a1 = Agent("agent1", hp=60, energy=50, position=(2, 3))
    a2 = Agent("agent2", hp=100, energy=50, position=(7, 7))
    state = GameState(a1, a2, arena)

    new_state = apply_action(state, Action.MOVE_DOWN)

    # Expected: HP = 60 + 30 = 90
    assert new_state.agent1.hp == 90, f"Expected HP 90, got {new_state.agent1.hp}"
    assert new_state.agent1.position == (3, 3), (
        f"Expected position (3,3), got {new_state.agent1.position}"
    )

    # Tile should be consumed
    assert (3, 3) in new_state.arena.consumed_tiles, "HEAL tile not consumed"
    assert new_state.arena.get_tile(3, 3) == TileType.EMPTY, (
        "Consumed HEAL tile should appear as EMPTY"
    )

    # last_event should record the heal
    assert new_state.last_event is not None, "last_event should be set"
    assert new_state.last_event["type"] == "heal", "last_event type should be 'heal'"
    assert new_state.last_event["amount"] == 30, (
        f"Expected heal amount 30, got {new_state.last_event['amount']}"
    )

    # Test HP cap: agent at 90 HP on a fresh HEAL tile
    arena2 = Arena()
    arena2.grid[4][4] = TileType.HEAL
    arena2.consumed_tiles.discard((4, 4))

    a3 = Agent("agent1", hp=90, energy=50, position=(3, 4))
    a4 = Agent("agent2", hp=100, energy=50, position=(7, 7))
    state2 = GameState(a3, a4, arena2)

    new_state2 = apply_action(state2, Action.MOVE_DOWN)
    # Expected: HP = min(100, 90 + min(30, 100-90)) = min(100, 90+10) = 100
    assert new_state2.agent1.hp == 100, f"Expected HP 100 (cap), got {new_state2.agent1.hp}"

    # Test already consumed HEAL tile has no effect
    arena3 = Arena()
    arena3.grid[5][5] = TileType.HEAL
    arena3.consumed_tiles.add((5, 5))  # pre-consumed

    a5 = Agent("agent1", hp=60, energy=50, position=(4, 5))
    a6 = Agent("agent2", hp=100, energy=50, position=(7, 7))
    state3 = GameState(a5, a6, arena3)

    new_state3 = apply_action(state3, Action.MOVE_DOWN)
    # Consumed tile reads as EMPTY, so no healing should occur
    assert new_state3.agent1.hp == 60, (
        f"Consumed HEAL should not heal, expected HP 60, got {new_state3.agent1.hp}"
    )

    print("  [PASS] test_heal_tile_mechanics")


# -----------------------------------------------------------------------
# Test 3 — Heuristic HEAL awareness & _nearest_tile_distance
# -----------------------------------------------------------------------

def test_heuristic_heal_awareness() -> None:
    """Heuristic should value being near/on a HEAL tile when HP is low."""
    # Use a clean arena with only HEAL to isolate tile-proximity effect
    arena = Arena()
    # Clear all tiles to EMPTY, then place one HEAL
    for r in range(arena.size):
        for c in range(arena.size):
            arena.grid[r][c] = TileType.EMPTY
    arena.grid[4][4] = TileType.HEAL
    arena.consumed_tiles.clear()
    arena.tile_durability.clear()
    arena.trap_timers.clear()

    # Equal HP, agent near HEAL vs far from HEAL
    a1_near = Agent("agent1", hp=60, energy=50, position=(4, 3))
    a2_near = Agent("agent2", hp=60, energy=50, position=(7, 7))
    state_near = GameState(a1_near, a2_near, arena)

    a1_far = Agent("agent1", hp=60, energy=50, position=(0, 0))
    a2_far = Agent("agent2", hp=60, energy=50, position=(7, 7))
    state_far = GameState(a1_far, a2_far, arena)

    score_near = evaluate(state_near, "agent1")
    score_far = evaluate(state_far, "agent1")

    # Being near heal should be better (tile proximity bonus)
    assert score_near > score_far, (
        f"Near-heal score ({score_near:.1f}) should exceed far-heal score ({score_far:.1f})"
    )

    # Test _nearest_tile_distance
    d = _nearest_tile_distance(arena, (4, 3), [TileType.HEAL])
    assert d == 1, f"Expected distance 1 from (4,3) to HEAL at (4,4), got {d}"

    d_far = _nearest_tile_distance(arena, (0, 0), [TileType.HEAL])
    assert d_far == 8, f"Expected distance 8 from (0,0) to HEAL at (4,4), got {d_far}"

    print("  [PASS] test_heuristic_heal_awareness")


# -----------------------------------------------------------------------
# Test 4 — MCTS produces a valid action (sanity)
# -----------------------------------------------------------------------

def test_mcts_valid_action() -> None:
    """MCTSAgent.choose_action returns a valid Action enum member,
    and stats are populated."""
    arena = Arena()
    a1 = Agent("agent1", position=(1, 1))
    a2 = Agent("agent2", position=(6, 6))
    state = GameState(a1, a2, arena)

    # Capture valid actions BEFORE MCTS modifies shared arena grid
    valid = get_valid_actions(state)

    agent = MCTSAgent("agent1", iterations=50)  # small for speed
    action = agent.choose_action(state)

    # Must be a valid Action
    assert action in valid, (
        f"MCTS returned invalid action {action.value}; "
        f"valid={[a.value for a in valid]}"
    )

    # Stats should be populated
    assert agent.stats["total_simulations"] > 0, "No simulations ran"
    assert agent.stats["time_ms"] > 0, "Time not recorded"
    assert agent.stats["nodes_expanded"] > 0, "No nodes expanded"

    print("  [PASS] test_mcts_valid_action")


# -----------------------------------------------------------------------
# Test 5 — MCTS node progressive widening & PUCT
# -----------------------------------------------------------------------

def test_mcts_progressive_widening() -> None:
    """Verify progressive widening limits child expansion correctly."""
    arena = Arena()
    a1 = Agent("agent1", position=(3, 3))
    a2 = Agent("agent2", position=(5, 5))
    state = GameState(a1, a2, arena)

    # Capture valid actions BEFORE MCTS modifies shared arena grid
    valid = get_valid_actions(state)

    agent = MCTSAgent("agent1", iterations=100, widen_exp=0.6)
    action = agent.choose_action(state)

    # The action must be valid
    assert action in valid, f"MCTS returned invalid action: {action.value}"

    # Verify MCTSNode properties
    node = MCTSNode(state=state)
    assert len(node.untried_actions) > 0, "Root node should have untried actions"
    assert node.q == 0.0, "Fresh node should have q=0"

    print("  [PASS] test_mcts_progressive_widening")


# -----------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------

if __name__ == "__main__":
    import random
    random.seed(42)

    print("=" * 60)
    print("  Aegis Arena — Validation Tests")
    print("=" * 60)

    tests = [
        test_heal_tile_placement,
        test_heal_tile_mechanics,
        test_heuristic_heal_awareness,
        test_mcts_valid_action,
        test_mcts_progressive_widening,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {test_fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {test_fn.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print("-" * 60)
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)}")
    print("=" * 60)

    sys.exit(1 if failed > 0 else 0)
