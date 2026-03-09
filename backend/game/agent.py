"""Agent module — player entity with HP, energy, cooldowns, and combat.

Each agent lives on the arena grid and tracks its own health, energy,
shield state, and cooldown timers.  The ``tick`` method is called once
per turn to update time-dependent state (cooldowns, shield expiry,
energy-tile bonus).
"""

from __future__ import annotations

import copy
from typing import Dict, Tuple

try:
    from .arena import Arena, TileType
except ImportError:  # running as standalone script
    from arena import Arena, TileType  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_HP: int = 100
MAX_ENERGY: int = 100
ENERGY_TILE_BONUS: int = 20    # energy restored per turn on an ENERGY tile
SHIELD_DURATION: int = 2       # turns a shield stays active
SHIELD_COOLDOWN: int = 4       # turns before shield can be used again
SHIELD_REDUCTION: float = 0.4  # multiplier on incoming damage while shielded
COVER_REDUCTION: float = 0.4   # multiplier on incoming damage while on cover
BURN_DAMAGE: int = 5           # damage per tick while burning


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class Agent:
    """A duelling agent on the Aegis Arena grid.

    Attributes:
        name:              Human-readable identifier (e.g. ``"agent1"``).
        hp:                Current hit-points (0 – ``MAX_HP``).
        energy:            Current energy (0 – ``MAX_ENERGY``).
        position:          ``(row, col)`` on the arena grid.
        shield_active:     Whether the defensive shield is currently up.
        shield_turns_left: Remaining turns of active shield.
        skill_cooldown:    Turns until the special skill can be used again.
        shield_cooldown:   Turns until the defensive shield can be used again.
        burn_turns:        Remaining turns of burn DoT (0 = not burning).
        slow_active:       Whether this agent is slowed (movement restricted).
    """

    def __init__(
        self,
        name: str,
        hp: int = MAX_HP,
        energy: int = 50,
        position: Tuple[int, int] = (0, 0),
    ) -> None:
        """Initialise an agent.

        Args:
            name:     Agent identifier.
            hp:       Starting hit-points.
            energy:   Starting energy.
            position: Starting ``(row, col)`` on the grid.
        """
        self.name: str = name
        self.hp: int = hp
        self.energy: int = energy
        self.position: Tuple[int, int] = position

        self.shield_active: bool = False
        self.shield_turns_left: int = 0
        self.skill_cooldown: int = 0
        self.shield_cooldown: int = 0
        self.burn_turns: int = 0      # remaining burn DoT ticks
        self.slow_active: bool = False  # movement restriction flag

    # -- combat -------------------------------------------------------------

    def take_damage(self, base_amount: int, on_cover: bool = False) -> int:
        """Apply damage to this agent, respecting shield and cover.

        Damage formula (multiplicative stacking)::

            effective = base_amount
                      × (COVER_REDUCTION   if on_cover      else 1.0)
                      × (SHIELD_REDUCTION  if shield_active else 1.0)

        Args:
            base_amount: Raw incoming damage before any reduction.
            on_cover:    ``True`` when the agent stands on a COVER tile.

        Returns:
            The actual (integer) damage dealt after reductions.
        """
        # Multiplicative damage reduction
        effective: float = float(base_amount)
        if on_cover:
            effective *= COVER_REDUCTION       # 40 % of original passes through
        if self.shield_active:
            effective *= SHIELD_REDUCTION       # another 40 % passes through

        actual: int = int(effective)            # truncate toward zero
        self.hp = max(0, self.hp - actual)
        return actual

    def restore_energy(self, amount: int) -> None:
        """Add *amount* energy, capped at ``MAX_ENERGY``.

        Args:
            amount: Energy to restore (must be non-negative).
        """
        self.energy = min(MAX_ENERGY, self.energy + amount)

    def activate_shield(self) -> None:
        """Raise the defensive shield.

        Sets ``shield_active`` to ``True``, starts the duration counter,
        and puts the ability on cooldown.
        """
        self.shield_active = True
        self.shield_turns_left = SHIELD_DURATION
        self.shield_cooldown = SHIELD_COOLDOWN

    # -- per-turn update ----------------------------------------------------

    def tick(self, arena: "Arena") -> None:
        """Per-turn update: cooldowns, shield expiry, and energy tile bonus.

        Called once at the end of the acting agent's turn.

        Args:
            arena: The game arena (used to check the tile under the agent).
        """
        # --- Cooldown ticking ---
        if self.skill_cooldown > 0:
            self.skill_cooldown -= 1
        if self.shield_cooldown > 0:
            self.shield_cooldown -= 1

        # --- Shield duration ---
        if self.shield_active:
            self.shield_turns_left -= 1
            if self.shield_turns_left <= 0:
                self.shield_active = False
                self.shield_turns_left = 0

        # --- Energy tile bonus ---
        tile: TileType = arena.get_tile(*self.position)
        if tile == TileType.ENERGY:
            self.restore_energy(ENERGY_TILE_BONUS)

        # --- Burn damage-over-time ---
        if self.burn_turns > 0:
            self.hp = max(0, self.hp - BURN_DAMAGE)
            self.burn_turns -= 1

        # --- Slow wears off each tick ---
        if self.slow_active:
            self.slow_active = False

    # -- utility ------------------------------------------------------------

    def clone(self) -> "Agent":
        """Return an independent deep copy of this agent.

        Returns:
            A new ``Agent`` with identical attribute values.
        """
        return copy.deepcopy(self)

    def to_dict(self) -> Dict[str, object]:
        """Serialize the agent to a plain dictionary.

        Returns:
            A JSON-friendly dict of all public attributes.
        """
        return {
            "name": self.name,
            "hp": self.hp,
            "energy": self.energy,
            "position": list(self.position),
            "shield_active": self.shield_active,
            "shield_turns_left": self.shield_turns_left,
            "skill_cooldown": self.skill_cooldown,
            "shield_cooldown": self.shield_cooldown,
            "burn_turns": self.burn_turns,
            "slow_active": self.slow_active,
        }

    def __repr__(self) -> str:
        return (
            f"Agent({self.name!r}, hp={self.hp}, energy={self.energy}, "
            f"pos={self.position}, shield={self.shield_active}, "
            f"burn={self.burn_turns})"
        )


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    arena = Arena()

    a = Agent("agent1", position=(0, 0))
    print(f"Created: {a}")

    # Damage without protection
    dmg = a.take_damage(30)
    print(f"Took 30 raw damage → {dmg} actual, hp={a.hp}")

    # Damage with cover only
    a2 = Agent("agent2", position=(1, 2))  # (1,2) is COVER
    dmg = a2.take_damage(30, on_cover=True)
    print(f"agent2 on COVER took 30 raw → {dmg} actual, hp={a2.hp}")

    # Damage with shield only
    a3 = Agent("agent3", position=(0, 0))
    a3.activate_shield()
    dmg = a3.take_damage(30)
    print(f"agent3 shielded took 30 raw → {dmg} actual, hp={a3.hp}")

    # Damage with both cover + shield (multiplicative)
    a4 = Agent("agent4", position=(1, 2))
    a4.activate_shield()
    dmg = a4.take_damage(100, on_cover=True)
    # Expected: 100 * 0.4 * 0.4 = 16
    print(f"agent4 (cover+shield) took 100 raw → {dmg} actual, hp={a4.hp}")

    # Energy restoration on ENERGY tile
    a5 = Agent("agent5", energy=30, position=(0, 3))  # (0,3) is ENERGY
    print(f"\nagent5 before tick: energy={a5.energy}")
    a5.tick(arena)
    print(f"agent5 after tick on ENERGY tile: energy={a5.energy}")

    # Clone independence
    original = Agent("orig", hp=80, energy=40, position=(2, 2))
    cloned = original.clone()
    cloned.hp = 10
    print(f"\nOriginal hp={original.hp}, Clone hp={cloned.hp}")
