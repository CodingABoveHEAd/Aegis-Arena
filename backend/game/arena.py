"""Arena module — 8×8 grid with tile types and spatial queries.

Defines the game board for Aegis Arena, including tile enums, a fixed
symmetric layout, trap-respawn logic, and helper methods for adjacency
and serialization.
"""

from __future__ import annotations

import enum
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Tile Enum
# ---------------------------------------------------------------------------

class TileType(enum.Enum):
    """Enumeration of tile types on the arena grid."""

    EMPTY = "EMPTY"
    COVER = "COVER"      # Reduces incoming damage by 40 %
    ENERGY = "ENERGY"    # Restores 20 energy per turn tick
    TRAP = "TRAP"        # Deals 10 damage on first step; respawns after 3 turns


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
    """

    TRAP_RESPAWN_TURNS: int = 3  # turns a triggered trap stays empty

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
        self._place_tiles()

    # -- fixed symmetric layout ---------------------------------------------

    def _place_tiles(self) -> None:
        """Hard-code a symmetric tile layout (mirrored about the main diagonal).

        Placement pairs ``(r, c)`` ↔ ``(size-1-r, size-1-c)`` guarantee
        fair starting conditions for both agents.
        """
        s = self.size - 1  # shorthand for mirror index

        # 6 COVER tiles (3 pairs)
        cover_positions: List[Tuple[int, int]] = [
            (1, 2), (3, 3), (2, 5),
        ]
        # 4 ENERGY tiles (2 pairs)
        energy_positions: List[Tuple[int, int]] = [
            (0, 3), (2, 1),
        ]
        # 4 TRAP tiles (2 pairs)
        trap_positions: List[Tuple[int, int]] = [
            (1, 4), (3, 1),
        ]

        for r, c in cover_positions:
            self.grid[r][c] = TileType.COVER
            self.grid[s - r][s - c] = TileType.COVER  # diagonal mirror

        for r, c in energy_positions:
            self.grid[r][c] = TileType.ENERGY
            self.grid[s - r][s - c] = TileType.ENERGY

        for r, c in trap_positions:
            self.grid[r][c] = TileType.TRAP
            self.grid[s - r][s - c] = TileType.TRAP

    # -- queries ------------------------------------------------------------

    def get_tile(self, x: int, y: int) -> TileType:
        """Return the tile type at grid position ``(x, y)``.

        Args:
            x: Row index (0-based).
            y: Column index (0-based).

        Returns:
            The ``TileType`` at the given cell.

        Raises:
            IndexError: If ``(x, y)`` is outside the grid.
        """
        if not self.is_valid(x, y):
            raise IndexError(f"Position ({x}, {y}) is out of bounds.")
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

    def to_grid_list(self) -> List[List[str]]:
        """Serialize the grid to a 2-D list of tile-name strings.

        Returns:
            ``size × size`` list of lists, each element being the
            ``TileType.value`` string (e.g. ``"COVER"``).
        """
        return [[cell.value for cell in row] for row in self.grid]


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
