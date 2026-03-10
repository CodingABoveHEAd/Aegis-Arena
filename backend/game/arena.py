"""Arena module — 8×8 grid with tile types and spatial queries.

Defines the game board for Aegis Arena, including tile enums, a fixed
symmetric layout, trap-respawn logic, and helper methods for adjacency
and serialization.
"""

from __future__ import annotations

import enum
import random
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Tile Enum
# ---------------------------------------------------------------------------

class TileType(enum.Enum):
    """Enumeration of tile types on the arena grid."""

    EMPTY = "EMPTY"
    COVER = "COVER"        # Reduces incoming damage by 40 %
    ENERGY = "ENERGY"      # Restores 20 energy per turn tick
    TRAP = "TRAP"          # Deals 10 damage on first step; respawns after 3 turns
    ELEVATED = "ELEVATED"  # +20 % damage multiplier when attacking from here
    HEAL = "HEAL"          # Restores up to 30 HP on first step (one-time)


# ---------------------------------------------------------------------------
# Arena
# ---------------------------------------------------------------------------

class Arena:
    """8×8 (configurable) game board with fixed symmetric tile layout.

    The layout is mirrored diagonally so that both agents start on
    equivalent terrain.  Trap tiles track a respawn counter: when
    triggered they become EMPTY for ``TRAP_RESPAWN_TURNS`` turns, then
    revert to TRAP.

    Attributes:
        size:            Side length of the square grid.
        grid:            2-D list of ``TileType`` values.
        trap_timers:     Mapping ``(x, y) -> turns_remaining`` for
                         triggered traps currently on cooldown.
        tile_durability: Mapping ``(x, y) -> hits_remaining`` for
                         COVER tiles (destroyed after 3 hits).
    """

    TRAP_RESPAWN_TURNS: int = 3   # turns a triggered trap stays empty
    COVER_MAX_DURABILITY: int = 3  # hits before a COVER tile is destroyed

    # -- construction -------------------------------------------------------

    def __init__(self, size: int = 8) -> None:
        """Create a new arena with the given *size* and place tiles.

        Args:
            size: Side length of the square grid (default 8).
        """
        self.size: int = size
        self.grid: List[List[TileType]] = [
            [TileType.EMPTY for _ in range(size)] for _ in range(size)
        ]
        self.trap_timers: Dict[Tuple[int, int], int] = {}
        self.tile_durability: Dict[Tuple[int, int], int] = {}
        self.consumed_tiles: set = set()  # tiles that gave their one-time effect
        self.generate_layout()

    # -- random symmetric layout -------------------------------------------

    def generate_layout(self) -> None:
        """Generate a random symmetric tile layout.

        Tiles are placed in mirrored pairs ``(r, c)`` ↔ ``(s-r, s-c)``
        to guarantee fair starting conditions.  A safe zone around each
        spawn corner is kept EMPTY.

        Tile counts per match (pairs placed, each pair = 2 tiles):
            COVER: 3 pairs (6 tiles), ENERGY: 2 pairs (4 tiles),
            TRAP: 2 pairs (4 tiles), ELEVATED: 2 pairs (4 tiles).
        """
        s = self.size - 1

        # Reset grid
        for r in range(self.size):
            for c in range(self.size):
                self.grid[r][c] = TileType.EMPTY

        # Reset mutable state
        self.trap_timers.clear()
        self.tile_durability.clear()
        self.consumed_tiles.clear()

        # Safe zone: 2-Manhattan-distance from spawn corners (0,0) and (s,s)
        safe = set()
        for r in range(self.size):
            for c in range(self.size):
                if abs(r) + abs(c) <= 2:
                    safe.add((r, c))
                if abs(r - s) + abs(c - s) <= 2:
                    safe.add((r, c))

        # Candidate cells: upper-triangle (r*size+c < mirror), not in safe zone
        candidates: List[Tuple[int, int]] = []
        for r in range(self.size):
            for c in range(self.size):
                mr, mc = s - r, s - c
                # Only consider one cell of each mirror pair (avoid double-place)
                if (r * self.size + c) >= (mr * self.size + mc):
                    continue
                if (r, c) in safe or (mr, mc) in safe:
                    continue
                candidates.append((r, c))

        random.shuffle(candidates)

        # Tile quotas: (TileType, count_of_pairs)
        quotas = [
            (TileType.COVER, 3),
            (TileType.ENERGY, 2),
            (TileType.TRAP, 2),
            (TileType.ELEVATED, 2),
        ]

        idx = 0
        for tile_type, count in quotas:
            placed = 0
            while placed < count and idx < len(candidates):
                r, c = candidates[idx]
                idx += 1
                mr, mc = s - r, s - c
                self.grid[r][c] = tile_type
                self.grid[mr][mc] = tile_type
                if tile_type == TileType.COVER:
                    self.tile_durability[(r, c)] = self.COVER_MAX_DURABILITY
                    self.tile_durability[(mr, mc)] = self.COVER_MAX_DURABILITY
                placed += 1

        # Place HEAL tiles: 2 pairs, min distance 3 from spawn corners,
        # and not adjacent to any TRAP tile.
        heal_placed = 0
        while heal_placed < 2 and idx < len(candidates):
            r, c = candidates[idx]
            idx += 1
            mr, mc = s - r, s - c

            # Min distance 3 from spawn corners (0,0) and (s,s)
            if abs(r) + abs(c) < 3 or abs(r - s) + abs(c - s) < 3:
                continue

            # Not adjacent to a TRAP tile
            adjacent_to_trap = False
            for nr, nc in self.get_neighbors(r, c):
                if self.grid[nr][nc] == TileType.TRAP:
                    adjacent_to_trap = True
                    break
            if not adjacent_to_trap:
                for nr, nc in self.get_neighbors(mr, mc):
                    if self.grid[nr][nc] == TileType.TRAP:
                        adjacent_to_trap = True
                        break
            if adjacent_to_trap:
                continue

            self.grid[r][c] = TileType.HEAL
            self.grid[mr][mc] = TileType.HEAL
            heal_placed += 1

    # -- queries ------------------------------------------------------------

    def get_tile(self, x: int, y: int) -> TileType:
        """Return the tile type at grid position ``(x, y)``.

        Consumed tiles (one-time effect already used) appear as EMPTY.
        """
        if not self.is_valid(x, y):
            raise IndexError(f"Position ({x}, {y}) is out of bounds.")
        if (x, y) in self.consumed_tiles:
            return TileType.EMPTY
        return self.grid[x][y]

    def is_valid(self, x: int, y: int) -> bool:
        """Check whether ``(x, y)`` lies within the grid.

        Args:
            x: Row index.
            y: Column index.

        Returns:
            ``True`` if ``0 <= x < size`` and ``0 <= y < size``.
        """
        return 0 <= x < self.size and 0 <= y < self.size

    def get_neighbors(self, x: int, y: int) -> List[Tuple[int, int]]:
        """Return 4-directional neighbors of ``(x, y)`` that are in bounds.

        Args:
            x: Row index.
            y: Column index.

        Returns:
            A list of ``(row, col)`` tuples for valid adjacent cells
            (up, down, left, right).
        """
        directions: List[Tuple[int, int]] = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        return [
            (x + dx, y + dy)
            for dx, dy in directions
            if self.is_valid(x + dx, y + dy)
        ]

    # -- cover durability ---------------------------------------------------

    def damage_cover(self, x: int, y: int) -> bool:
        """Reduce durability of a COVER tile. Destroys it when depleted.

        Args:
            x: Row index of the COVER tile.
            y: Column index of the COVER tile.

        Returns:
            ``True`` if the cover tile was destroyed by this hit.
        """
        key = (x, y)
        if key not in self.tile_durability:
            return False
        self.tile_durability[key] -= 1
        if self.tile_durability[key] <= 0:
            self.grid[x][y] = TileType.EMPTY
            del self.tile_durability[key]
            return True
        return False

    # -- elevation helper ---------------------------------------------------

    @staticmethod
    def elevation_multiplier(attacker_tile: TileType) -> float:
        """Return the damage multiplier for attacking from *attacker_tile*.

        ELEVATED tiles grant a +20 % bonus (multiplier 1.2); all other
        tiles return 1.0.

        Args:
            attacker_tile: The ``TileType`` the attacker is standing on.

        Returns:
            A float multiplier (>= 1.0).
        """
        return 1.2 if attacker_tile == TileType.ELEVATED else 1.0

    # -- trap lifecycle -----------------------------------------------------

    def trigger_trap(self, x: int, y: int) -> None:
        """Mark a TRAP tile as triggered — it becomes EMPTY and enters cooldown.

        Args:
            x: Row index of the trap.
            y: Column index of the trap.
        """
        self.grid[x][y] = TileType.EMPTY
        self.trap_timers[(x, y)] = self.TRAP_RESPAWN_TURNS

    def tick_traps(self) -> None:
        """Decrement every triggered-trap respawn counter by one.

        When a counter reaches zero the tile reverts to ``TileType.TRAP``.
        Call this once per turn.
        """
        expired: List[Tuple[int, int]] = []
        for pos, remaining in self.trap_timers.items():
            if remaining <= 1:
                # Timer expired — respawn the trap
                self.grid[pos[0]][pos[1]] = TileType.TRAP
                expired.append(pos)
            else:
                self.trap_timers[pos] = remaining - 1

        for pos in expired:
            del self.trap_timers[pos]

    # -- serialization ------------------------------------------------------

    def consume_tile(self, x: int, y: int) -> None:
        """Mark a tile as consumed — its one-time effect has been used.

        The tile will appear as EMPTY to get_tile and to_grid_list.
        """
        self.consumed_tiles.add((x, y))

    def to_grid_list(self) -> List[List[str]]:
        """Serialize the grid to a 2-D list of tile-name strings.

        Consumed tiles are reported as ``"EMPTY"``.
        """
        result: List[List[str]] = []
        for r, row in enumerate(self.grid):
            result_row: List[str] = []
            for c, cell in enumerate(row):
                if (r, c) in self.consumed_tiles:
                    result_row.append(TileType.EMPTY.value)
                else:
                    result_row.append(cell.value)
            result.append(result_row)
        return result


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    arena = Arena()

    print("=== Arena 8×8 Layout ===")
    for r, row in enumerate(arena.grid):
        print(f"  Row {r}: {[t.value.ljust(6) for t in row]}")

    print(f"\nTile at (1,2): {arena.get_tile(1, 2).value}")
    print(f"Is (7,7) valid? {arena.is_valid(7, 7)}")
    print(f"Is (8,0) valid? {arena.is_valid(8, 0)}")
    print(f"Neighbors of (0,0): {arena.get_neighbors(0, 0)}")
    print(f"Neighbors of (3,4): {arena.get_neighbors(3, 4)}")

    # Trigger a trap and tick it three times to see it respawn
    print("\n--- Trap lifecycle ---")
    print(f"Tile (1,4) before trigger: {arena.get_tile(1, 4).value}")
    arena.trigger_trap(1, 4)
    print(f"Tile (1,4) after trigger:  {arena.get_tile(1, 4).value}")
    for turn in range(1, 5):
        arena.tick_traps()
        print(f"  After tick {turn}: {arena.get_tile(1, 4).value}  timers={arena.trap_timers}")

    # Cover durability
    print("\n--- Cover durability ---")
    arena2 = Arena()
    for hit in range(1, 5):
        destroyed = arena2.damage_cover(1, 2)
        tile = arena2.get_tile(1, 2).value
        print(f"  Hit {hit}: destroyed={destroyed}, tile={tile}")

    # Elevation multiplier
    print("\n--- Elevation multiplier ---")
    print(f"  ELEVATED: {Arena.elevation_multiplier(TileType.ELEVATED)}")
    print(f"  EMPTY:    {Arena.elevation_multiplier(TileType.EMPTY)}")
