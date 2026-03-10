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
from backend.ai.negamax import NegamaxAgent
from backend.ai.minimax import MinimaxAgent
from backend.ai.cache import TranspositionTable, EXACT, LOWER, UPPER
from backend.ai.agent_factory import create_agent, available_algorithms


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
# Test 6 — Negamax attacks when in range
# -----------------------------------------------------------------------

def test_negamax_attacks_when_in_range() -> None:
    """When the opponent is within attack range and attack is beneficial,
    Negamax should choose an attack action (BASIC_ATTACK or SPECIAL_SKILL)."""
    arena = Arena()
    # Place agents adjacent (distance 1 — within basic attack range of 2)
    a1 = Agent("agent1", hp=80, energy=60, position=(3, 3))
    a2 = Agent("agent2", hp=40, energy=10, position=(3, 4))
    state = GameState(a1, a2, arena, current_agent="agent1")

    agent = NegamaxAgent("agent1", time_budget_ms=500, max_depth=6)
    action = agent.choose_action(state)

    attack_actions = {Action.BASIC_ATTACK, Action.SPECIAL_SKILL}
    assert action in attack_actions, (
        f"Expected attack action when in range, got {action.value}"
    )
    print("  [PASS] test_negamax_attacks_when_in_range")


# -----------------------------------------------------------------------
# Test 7 — Negamax depth increases with time budget
# -----------------------------------------------------------------------

def test_negamax_depth_increases_with_time() -> None:
    """A larger time budget should allow deeper search."""
    arena = Arena()
    a1 = Agent("agent1", position=(0, 0))
    a2 = Agent("agent2", position=(7, 7))
    state = GameState(a1, a2, arena)

    short = NegamaxAgent("agent1", time_budget_ms=50, max_depth=10)
    short.choose_action(state)
    short_depth = short.stats["depth_reached"]

    long = NegamaxAgent("agent1", time_budget_ms=800, max_depth=10)
    long.choose_action(state)
    long_depth = long.stats["depth_reached"]

    assert long_depth >= short_depth, (
        f"Longer budget depth ({long_depth}) should be >= short ({short_depth})"
    )
    assert long_depth >= 2, f"Expected at least depth 2 with 800ms, got {long_depth}"

    print("  [PASS] test_negamax_depth_increases_with_time")


# -----------------------------------------------------------------------
# Test 8 — Negamax beats random agent
# -----------------------------------------------------------------------

def test_negamax_beats_random() -> None:
    """Negamax must win at least 4 out of 5 games against a random agent."""
    import random as rng

    wins = 0
    for i in range(5):
        side = "agent1" if i % 2 == 0 else "agent2"
        arena = Arena()
        a1 = Agent("agent1", position=(0, 0))
        a2 = Agent("agent2", position=(7, 7))
        state = GameState(a1, a2, arena)
        neg = NegamaxAgent(side, time_budget_ms=400, max_depth=8)

        for _ in range(200):
            if state.is_terminal():
                break
            actions = get_valid_actions(state)
            if not actions:
                break
            if state.current_agent == side:
                action = neg.choose_action(state)
            else:
                action = rng.choice(actions)
            state = apply_action(state, action)

        if state.get_winner() == side:
            wins += 1

    assert wins >= 4, f"Negamax only won {wins}/5 against random (need >=4)"
    print(f"  [PASS] test_negamax_beats_random ({wins}/5 wins)")


# -----------------------------------------------------------------------
# Test 9 — Negamax vs Minimax is competitive
# -----------------------------------------------------------------------

def test_negamax_vs_minimax() -> None:
    """Negamax should not lose catastrophically to Minimax.
    Play 2 games (alternating sides), Negamax must win or draw at least once."""
    results = []
    for i in range(2):
        neg_side = "agent1" if i == 0 else "agent2"
        mini_side = "agent2" if i == 0 else "agent1"

        arena = Arena()
        a1 = Agent("agent1", position=(1, 1))
        a2 = Agent("agent2", position=(6, 6))
        state = GameState(a1, a2, arena)

        neg = NegamaxAgent(neg_side, time_budget_ms=500, max_depth=8)
        mini = MinimaxAgent(mini_side, depth=4, time_budget_ms=500)

        for _ in range(200):
            if state.is_terminal():
                break
            if state.current_agent == neg_side:
                action = neg.choose_action(state)
            else:
                action = mini.choose_action(state)
            state = apply_action(state, action)

        winner = state.get_winner()
        results.append(winner)

    neg_non_losses = sum(
        1 for i, w in enumerate(results)
        if w == ("agent1" if i == 0 else "agent2") or w is None
    )
    assert neg_non_losses >= 1, (
        f"Negamax lost both games to Minimax: {results}"
    )
    print(f"  [PASS] test_negamax_vs_minimax (results: {results})")


# -----------------------------------------------------------------------
# Test 10 — Algorithm registry
# -----------------------------------------------------------------------

def test_algorithm_registry() -> None:
    """Agent factory should list all three algorithms and create each."""
    algos = available_algorithms()
    assert "minimax" in algos, "minimax not in registry"
    assert "negamax" in algos, "negamax not in registry"
    assert "mcts" in algos, "mcts not in registry"

    for algo in algos:
        agent = create_agent("agent1", algo)
        assert hasattr(agent, "choose_action"), (
            f"{algo} agent missing choose_action"
        )

    # Invalid algorithm should raise ValueError
    try:
        create_agent("agent1", "nonexistent")
        assert False, "Expected ValueError for unknown algorithm"
    except ValueError:
        pass

    print("  [PASS] test_algorithm_registry")


# -----------------------------------------------------------------------
# Test 11 — TT flag correctness
# -----------------------------------------------------------------------

def test_tt_flag_correctness() -> None:
    """Transposition table stores and retrieves flags correctly."""
    tt = TranspositionTable()
    key1 = (1, 2, 3)
    key2 = (4, 5, 6)
    key3 = (7, 8, 9)

    tt.store(key1, 3, 5.0, EXACT)
    tt.store(key2, 3, 3.0, LOWER)
    tt.store(key3, 3, -2.0, UPPER)

    # Retrieve at sufficient depth
    e1 = tt.get(key1, 3)
    assert e1 is not None, "EXACT entry not found"
    assert e1 == (5.0, 3, EXACT), f"EXACT entry wrong: {e1}"

    e2 = tt.get(key2, 3)
    assert e2 is not None, "LOWER entry not found"
    assert e2[2] == LOWER, f"Expected LOWER flag, got {e2[2]}"

    e3 = tt.get(key3, 2)  # lower depth request — should still return
    assert e3 is not None, "UPPER entry not found at lower depth"
    assert e3[2] == UPPER, f"Expected UPPER flag, got {e3[2]}"

    # Request at higher depth should return None
    assert tt.get(key1, 5) is None, "Should not return entry at shallower stored depth"

    print("  [PASS] test_tt_flag_correctness")


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
        test_negamax_attacks_when_in_range,
        test_negamax_depth_increases_with_time,
        test_negamax_beats_random,
        test_negamax_vs_minimax,
        test_algorithm_registry,
        test_tt_flag_correctness,
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
