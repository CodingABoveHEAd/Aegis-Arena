"""Actions module — action definitions, validation, and state transitions.

Provides the ``Action`` enum, ``ACTION_PROPS`` look-up table, and the
two core functions ``get_valid_actions`` and ``apply_action``.

``apply_action`` follows a strict *immutable* pattern: the input
``GameState`` is **never** mutated; a cloned successor state is returned.
"""

from __future__ import annotations

import enum
from typing import Any, Dict, List, Tuple

try:
    from .agent import Agent
    from .arena import Arena, TileType
    from .state import GameState
except ImportError:  # running as standalone script
    from agent import Agent  # type: ignore[no-redef]
    from arena import Arena, TileType  # type: ignore[no-redef]
    from state import GameState  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Action Enum
# ---------------------------------------------------------------------------

class Action(enum.Enum):
    """All actions an agent may take on its turn."""

    MOVE_UP = "MOVE_UP"
    MOVE_DOWN = "MOVE_DOWN"
    MOVE_LEFT = "MOVE_LEFT"
    MOVE_RIGHT = "MOVE_RIGHT"
    BASIC_ATTACK = "BASIC_ATTACK"
    DEFENSIVE_SHIELD = "DEFENSIVE_SHIELD"
    SPECIAL_SKILL = "SPECIAL_SKILL"


# ---------------------------------------------------------------------------
# Action Property Table
# ---------------------------------------------------------------------------

ACTION_PROPS: Dict[Action, Dict[str, int]] = {
    Action.BASIC_ATTACK: {
        "damage": 15,
        "energy_cost": 0,
        "range": 2,
        "cooldown": 0,
    },
    Action.DEFENSIVE_SHIELD: {
        "damage": 0,
        "energy_cost": 20,
        "range": 0,
        "cooldown": 4,
    },
    Action.SPECIAL_SKILL: {
        "damage": 35,
        "energy_cost": 40,
        "range": 4,
        "cooldown": 5,
    },
}

# Movement direction vectors (row_delta, col_delta)
_MOVE_DELTAS: Dict[Action, Tuple[int, int]] = {
    Action.MOVE_UP:    (-1, 0),
    Action.MOVE_DOWN:  (1, 0),
    Action.MOVE_LEFT:  (0, -1),
    Action.MOVE_RIGHT: (0, 1),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    """Return the Manhattan distance between two grid positions.

    Args:
        a: First position ``(row, col)``.
        b: Second position ``(row, col)``.

    Returns:
        Non-negative integer distance.
    """
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _get_agents(state: GameState) -> Tuple[Agent, Agent]:
    """Return ``(acting_agent, opponent)`` based on ``state.current_agent``.

    Args:
        state: The current game state.

    Returns:
        A 2-tuple of agent references from the state.
    """
    if state.current_agent == "agent1":
        return state.agent1, state.agent2
    return state.agent2, state.agent1


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def get_valid_actions(state: GameState) -> List[Action]:
    """Determine every legal action for the current agent.

    Movement is valid when the destination cell is within grid bounds.
    Combat actions are gated by range, cooldown, and energy.

    Args:
        state: The current game state.

    Returns:
        A list of ``Action`` values the current agent may execute.
    """
    actor, opponent = _get_agents(state)
    arena: Arena = state.arena
    valid: List[Action] = []

    # --- Movement actions ---
    for action, (dr, dc) in _MOVE_DELTAS.items():
        nr, nc = actor.position[0] + dr, actor.position[1] + dc
        if arena.is_valid(nr, nc):
            valid.append(action)

    # --- Basic Attack ---
    # Valid if opponent is within Manhattan distance <= range (2)
    dist: int = _manhattan(actor.position, opponent.position)
    ba_props = ACTION_PROPS[Action.BASIC_ATTACK]
    if dist <= ba_props["range"]:
        valid.append(Action.BASIC_ATTACK)

    # --- Defensive Shield ---
    # Valid if off cooldown and enough energy
    ds_props = ACTION_PROPS[Action.DEFENSIVE_SHIELD]
    if actor.shield_cooldown == 0 and actor.energy >= ds_props["energy_cost"]:
        valid.append(Action.DEFENSIVE_SHIELD)

    # --- Special Skill ---
    # Valid if off cooldown and enough energy and opponent in range
    ss_props = ACTION_PROPS[Action.SPECIAL_SKILL]
    if (
        actor.skill_cooldown == 0
        and actor.energy >= ss_props["energy_cost"]
        and dist <= ss_props["range"]
    ):
        valid.append(Action.SPECIAL_SKILL)

    return valid


# ---------------------------------------------------------------------------
# State Transition
# ---------------------------------------------------------------------------

def apply_action(state: GameState, action: Action) -> GameState:
    """Apply *action* and return the resulting **new** game state.

    **Critical**: the input ``state`` is **never** mutated.  A clone is
    made first and all changes happen on the clone.

    Sequence of operations:
        1. Clone the state.
        2. Resolve the action (movement / attack / ability).
        3. Tick the acting agent (cooldowns, shield, energy tile).
        4. Switch the active player.
        5. Increment turn counter.

    Args:
        state:  The game state *before* the action.
        action: The action to apply.

    Returns:
        A new ``GameState`` reflecting the result of the action.
    """
    # ---- 1. Clone ----
    new_state: GameState = state.clone()
    actor, opponent = _get_agents(new_state)
    arena: Arena = new_state.arena

    # ---- 2. Resolve action ----
    if action in _MOVE_DELTAS:
        _apply_move(actor, action, arena)
    elif action == Action.BASIC_ATTACK:
        _apply_basic_attack(actor, opponent, arena)
    elif action == Action.DEFENSIVE_SHIELD:
        _apply_shield(actor)
    elif action == Action.SPECIAL_SKILL:
        _apply_special_skill(actor, opponent, arena)

    # ---- 3. Tick the acting agent (cooldowns, shield expiry, energy bonus) ----
    actor.tick(arena)

    # ---- 4. Switch active player ----
    new_state.current_agent = (
        "agent2" if new_state.current_agent == "agent1" else "agent1"
    )

    # ---- 5. Increment turn ----
    new_state.turn_count += 1

    return new_state


# ---------------------------------------------------------------------------
# Action implementations (operate on the *cloned* state)
# ---------------------------------------------------------------------------

def _apply_move(actor: Agent, action: Action, arena: Arena) -> None:
    """Move the agent one step in the given direction.

    After moving:
      - If the new tile is a TRAP, deal 10 damage and trigger the trap.
      - Tick arena trap respawn counters.
      - (ENERGY bonus is handled later in ``agent.tick``.)

    Args:
        actor:  The agent that is moving.
        action: One of the four MOVE_* actions.
        arena:  The game arena.
    """
    dr, dc = _MOVE_DELTAS[action]
    new_r: int = actor.position[0] + dr
    new_c: int = actor.position[1] + dc
    actor.position = (new_r, new_c)

    tile: TileType = arena.get_tile(new_r, new_c)

    # Trap damage on entry (one-time: consume after triggering)
    if tile == TileType.TRAP:
        on_cover: bool = False  # just stepped onto a TRAP, not COVER
        actor.take_damage(10, on_cover=on_cover)
        arena.trigger_trap(new_r, new_c)  # mark trap for respawn countdown
        arena.consume_tile(new_r, new_c)  # permanent one-time effect

    # Energy tile: grant bonus once then consume
    if tile == TileType.ENERGY:
        arena.consume_tile(new_r, new_c)  # permanent one-time effect

    # Advance trap respawn timers globally
    arena.tick_traps()


def _apply_basic_attack(actor: Agent, opponent: Agent, arena: Arena) -> None:
    """Execute a basic attack against the opponent.

    Damage: 15 (from ACTION_PROPS), scaled by elevation multiplier.
    Cover is checked on the *opponent's* tile; cover durability is reduced.

    Args:
        actor:    The attacking agent.
        opponent: The defending agent.
        arena:    The game arena.
    """
    props = ACTION_PROPS[Action.BASIC_ATTACK]
    attacker_tile: TileType = arena.get_tile(*actor.position)
    opponent_tile: TileType = arena.get_tile(*opponent.position)
    on_cover: bool = opponent_tile == TileType.COVER

    # Elevation bonus: +20 % damage when attacking from ELEVATED tile
    base_damage: int = int(props["damage"] * Arena.elevation_multiplier(attacker_tile))
    opponent.take_damage(base_damage, on_cover=on_cover)

    # Reduce cover durability if opponent was behind cover
    if on_cover:
        arena.damage_cover(*opponent.position)


def _apply_shield(actor: Agent) -> None:
    """Activate the defensive shield.

    Deducts energy and delegates to ``Agent.activate_shield``.

    Args:
        actor: The shielding agent.
    """
    props = ACTION_PROPS[Action.DEFENSIVE_SHIELD]
    actor.energy -= props["energy_cost"]  # deduct 20 energy
    actor.activate_shield()


def _apply_special_skill(
    actor: Agent, opponent: Agent, arena: Arena
) -> None:
    """Fire the special skill at the opponent.

    Damage: 35 (scaled by elevation), Energy cost: 40, skill_cooldown = 5.
    Cover is checked on the *opponent's* tile.  Applies 2-turn burn DoT.

    Args:
        actor:    The acting agent.
        opponent: The target agent.
        arena:    The game arena.
    """
    props = ACTION_PROPS[Action.SPECIAL_SKILL]
    attacker_tile: TileType = arena.get_tile(*actor.position)
    opponent_tile: TileType = arena.get_tile(*opponent.position)
    on_cover: bool = opponent_tile == TileType.COVER

    # Elevation bonus: +20 % damage when attacking from ELEVATED tile
    base_damage: int = int(props["damage"] * Arena.elevation_multiplier(attacker_tile))
    opponent.take_damage(base_damage, on_cover=on_cover)
    actor.energy -= props["energy_cost"]          # deduct 40 energy
    actor.skill_cooldown = props["cooldown"]      # put on 5-turn cooldown

    # Special skill inflicts 2-turn burn (damage-over-time)
    opponent.burn_turns = 2

    # Reduce cover durability if opponent was behind cover
    if on_cover:
        arena.damage_cover(*opponent.position)


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    arena = Arena()
    a1 = Agent("agent1", position=(0, 0))
    a2 = Agent("agent2", position=(7, 7))

    state = GameState(a1, a2, arena)
    print("=== Initial state ===")
    print(state)

    # --- Valid actions from start ---
    valid = get_valid_actions(state)
    print(f"\nValid actions for {state.current_agent}: {[a.value for a in valid]}")

    # --- Apply a move ---
    s1 = apply_action(state, Action.MOVE_DOWN)
    print(f"\nAfter MOVE_DOWN: agent1 pos={s1.agent1.position}, "
          f"current={s1.current_agent}, turn={s1.turn_count}")
    # Original unchanged
    print(f"Original agent1 pos={state.agent1.position} (should be (0,0))")

    # --- Bring agents close and attack ---
    close_a1 = Agent("agent1", position=(3, 3))
    close_a2 = Agent("agent2", position=(3, 4))
    close_state = GameState(close_a1, close_a2, arena, current_agent="agent1")

    valid2 = get_valid_actions(close_state)
    print(f"\nClose-range valid: {[a.value for a in valid2]}")

    s2 = apply_action(close_state, Action.BASIC_ATTACK)
    print(f"After BASIC_ATTACK: agent2 hp={s2.agent2.hp} (was {close_state.agent2.hp})")

    # --- Shield then attack ---
    s3 = apply_action(close_state, Action.DEFENSIVE_SHIELD)
    print(f"\nAfter SHIELD: agent1 shield={s3.agent1.shield_active}, "
          f"energy={s3.agent1.energy}")
    # Now opponent attacks the shielded agent
    s3.current_agent = "agent2"  # force turn to agent2 for test
    s4 = apply_action(s3, Action.BASIC_ATTACK)
    print(f"agent2 attacks shielded agent1: hp={s4.agent1.hp}")

    # --- Special skill ---
    far_a1 = Agent("agent1", energy=100, position=(0, 0))
    far_a2 = Agent("agent2", position=(3, 1))  # Manhattan dist = 4
    far_state = GameState(far_a1, far_a2, arena)
    s5 = apply_action(far_state, Action.SPECIAL_SKILL)
    print(f"\nAfter SPECIAL_SKILL: agent2 hp={s5.agent2.hp}, "
          f"agent1 energy={s5.agent1.energy}, cooldown={s5.agent1.skill_cooldown}")

    # --- Step on trap ---
    trap_a1 = Agent("agent1", position=(0, 4))  # (1,4) is TRAP, move down
    trap_state = GameState(trap_a1, Agent("agent2", position=(7, 7)), arena)
    s6 = apply_action(trap_state, Action.MOVE_DOWN)
    print(f"\nAfter stepping on TRAP at (1,4): agent1 hp={s6.agent1.hp}")
    print(f"Tile (1,4) is now: {arena.get_tile(1, 4).value}")
