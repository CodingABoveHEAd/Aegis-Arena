# 🛡️ AEGIS ARENA — 3D Implementation Plan
**AI Laboratory Project | CSE 3210 | KUET**
**Stack: Python (FastAPI) + Three.js (Full 3D) | Algorithms: Minimax + MCTS**

---

## 📁 Final Project Structure

```
aegis-arena/
├── backend/
│   ├── game/
│   │   ├── __init__.py
│   │   ├── state.py           # Hashable game state representation
│   │   ├── arena.py           # 8x8 grid, tile types, layout
│   │   ├── agent.py           # Agent: HP, Energy, Position, Cooldowns
│   │   └── actions.py         # Actions, validation, state transitions
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── heuristic.py       # Positional + tactical heuristic scoring
│   │   ├── minimax.py         # Minimax + Alpha-Beta + Transposition Table
│   │   ├── mcts.py            # Monte Carlo Tree Search (UCB1)
│   │   └── cache.py           # TranspositionTable + lru_cache utilities
│   ├── server.py              # FastAPI: REST + WebSocket
│   └── requirements.txt
├── frontend/
│   ├── index.html             # Entry point, HUD overlay HTML
│   ├── main.js                # Three.js bootstrap, render loop, scene init
│   ├── scene/
│   │   ├── ArenaScene.js      # 3D elevated arena: floor, walls, pillars, skybox
│   │   ├── TileSystem.js      # Tile mesh factory + pulse/glow animations
│   │   ├── AgentMesh.js       # Full 3D warrior models (built from primitives)
│   │   ├── Effects.js         # Projectiles, shockwaves, particles, damage numbers
│   │   ├── CameraRig.js       # Cinematic camera: overview + action zoom
│   │   └── Lighting.js        # Dramatic three-point + emissive lighting setup
│   ├── ui/
│   │   ├── HUD.js             # HP bars, energy, cooldown, AI stats overlay
│   │   ├── ActionPanel.js     # Human turn buttons (glowing tactical UI)
│   │   └── MenuScreen.js      # Animated title screen + mode selection
│   ├── game/
│   │   ├── GameController.js  # Game loop, turn manager, mode handler
│   │   └── APIClient.js       # Backend communication (REST + WebSocket)
│   └── shaders/
│       ├── glow.glsl          # Custom glow/aura shader for agents
│       └── scanline.glsl      # Scanline overlay for HUD cyberpunk feel
└── README.md
```

---

# PHASE 1 — Python Game Engine (Core Logic)

## 🎯 Goal
Build the complete, deterministic Python game engine. Pure logic — no rendering, no AI.
This is the foundation everything else depends on. Get it right first.

---

## Prompt for Phase 1

```
You are building the backend game engine for "Aegis Arena" — a turn-based adversarial AI 
game for an AI Lab course (CSE 3210) at KUET. Two agents duel on a 2D grid.

## Context
- Grid-based, fully deterministic, turn-based
- Backend: Python only. No frontend or AI yet.
- Code must be clean, type-hinted, and academically readable for a lab report

---

## File 1: backend/game/arena.py

Implement an Arena class:
- Grid size: 8x8 (configurable via constructor)
- Tile types as Enum: EMPTY, COVER, ENERGY, TRAP
- Fixed symmetric layout (hardcoded, mirrored diagonally so both agents start fairly):
  - Place 6 COVER tiles, 4 ENERGY tiles, 4 TRAP tiles symmetrically
  - Example: if COVER at (1,2) then also at (6,5)
- Tile effects:
  - COVER: reduces incoming damage by 40% (applied in agent.take_damage)
  - ENERGY: standing here restores 20 energy per turn tick
  - TRAP: deals 10 damage on first step; tile resets to EMPTY for 3 turns then respawns
- Methods:
  - get_tile(x, y) -> TileType
  - is_valid(x, y) -> bool
  - get_neighbors(x, y) -> List[Tuple[int,int]]   # 4-directional adjacency
  - tick_traps() -> None   # decrement trap respawn counters each turn
  - to_grid_list() -> List[List[str]]  # for serialization

---

## File 2: backend/game/agent.py

Implement an Agent class:
- Attributes:
  - name: str
  - hp: int (default 100, max 100)
  - energy: int (default 50, max 100)
  - position: Tuple[int, int]
  - shield_active: bool (default False)
  - shield_turns_left: int (default 0)
  - skill_cooldown: int (default 0, counts down to 0)
  - shield_cooldown: int (default 0)
- Methods:
  - take_damage(base_amount: int, on_cover: bool = False) -> int
      Applies damage respecting shield (blocks 60%) and cover (reduces 40%).
      They stack multiplicatively: effective = base * (0.4 if cover else 1.0) * (0.4 if shield else 1.0)
      Returns actual damage dealt (for logging).
  - restore_energy(amount: int) -> None   # capped at max
  - activate_shield() -> None             # sets shield_active=True, shield_turns_left=2, shield_cooldown=4
  - tick(arena: Arena) -> None            # called each turn: decrement cooldowns,
                                          # handle shield expiry, apply energy tile bonus
  - clone() -> Agent                      # deep copy for AI search
  - to_dict() -> dict                     # serialization

---

## File 3: backend/game/state.py

Implement a GameState class:
- Fields:
  - agent1: Agent
  - agent2: Agent
  - current_agent: str  ("agent1" or "agent2")
  - turn_count: int (starts at 1)
  - arena: Arena (reference, not copied — arena is static except trap timers)
- Key methods:
  - to_tuple() -> tuple
      Returns a fully hashable representation of all mutable state:
      (agent1.hp, agent1.energy, agent1.position, agent1.shield_active,
       agent1.skill_cooldown, agent1.shield_cooldown,
       agent2.hp, ..., current_agent, turn_count)
      Used as key for transposition table.
  - is_terminal() -> bool   # True if either agent HP <= 0
  - get_winner() -> Optional[str]  # "agent1", "agent2", or None
  - clone() -> GameState    # deep copy for AI search (agents cloned, arena shared)
  - __hash__() and __eq__() based on to_tuple()
  - to_dict() -> dict  # full serialization for API response

---

## File 4: backend/game/actions.py

Define actions as Enum:
  MOVE_UP, MOVE_DOWN, MOVE_LEFT, MOVE_RIGHT,
  BASIC_ATTACK, DEFENSIVE_SHIELD, SPECIAL_SKILL

Action properties (define as a dict ACTION_PROPS):
  BASIC_ATTACK:    { damage: 15, energy_cost: 0,  range: 2, cooldown: 0 }
  DEFENSIVE_SHIELD:{ damage: 0,  energy_cost: 20, range: 0, cooldown: 4 }
  SPECIAL_SKILL:   { damage: 35, energy_cost: 40, range: 4, cooldown: 5 }

Implement two functions:

1. get_valid_actions(state: GameState) -> List[Action]:
   For the current agent in state:
   - Movement: valid if destination is within grid bounds
   - BASIC_ATTACK: valid if opponent is within Manhattan distance <= 2
   - DEFENSIVE_SHIELD: valid if shield_cooldown == 0 and energy >= 20
   - SPECIAL_SKILL: valid if skill_cooldown == 0 and energy >= 40

2. apply_action(state: GameState, action: Action) -> GameState:
   CRITICAL: Must NOT mutate the input state. Return a new GameState.
   Steps:
   a. Clone the state
   b. Get the acting agent and opponent from clone
   c. Apply the action:
      - MOVE: update position, call arena.tick_traps(), call agent.tick(arena)
        If new tile is TRAP: call agent.take_damage(10), mark trap as triggered
        If new tile is ENERGY: already handled in agent.tick()
      - BASIC_ATTACK: check range, apply damage to opponent (pass on_cover=True if opponent on COVER)
      - DEFENSIVE_SHIELD: call agent.activate_shield()
      - SPECIAL_SKILL: check range, apply 35 damage, deduct 40 energy, set skill_cooldown=5
   d. Decrement current agent's cooldowns via agent.tick()
   e. Switch current_agent (agent1 -> agent2 or vice versa)
   f. Increment turn_count
   g. Return new state

## Code Requirements
- Full type hints on every function and method
- Docstring on every class and method
- apply_action: immutable pattern (no mutation of input state)
- Inline comments explaining damage formula and cooldown logic
- Test block under `if __name__ == '__main__':` in each file
  showing: arena tile layout, agent taking damage, state hashing, action application
```

---

# PHASE 2 — AI Algorithms

## 🎯 Goal
Implement Minimax (with Alpha-Beta + Transposition Table) and MCTS.
Both clean, optimized, and documented for academic inspection.

**Why MCTS as second algorithm?**
- Stark academic contrast to Minimax (exhaustive search vs. statistical sampling)
- Handles large branching factors without depth explosion
- No need for a perfect heuristic — learns from rollouts
- Produces fascinatingly different tactical behavior than Minimax

---

## Prompt for Phase 2

```
Implement the AI algorithms for "Aegis Arena" (AI Lab course, CSE 3210, KUET).
The game engine from Phase 1 is complete. Import freely from backend/game/.

===================================================================
## ALGORITHM 1: Minimax + Alpha-Beta Pruning + Transposition Table
===================================================================

### File: backend/ai/heuristic.py

Implement:
  evaluate(state: GameState, agent_name: str) -> float

Heuristic is a weighted sum of 6 components. Score is always from the
perspective of `agent_name` (positive = good for us, negative = bad).

Components:
  1. hp_advantage       = (my_hp - opp_hp) * 2.0
  2. energy_advantage   = (my_energy - opp_energy) * 0.5
  3. position_value:
       my_tile = arena.get_tile(*my_pos)
       +10 if COVER, +6 if ENERGY, -15 if TRAP
  4. distance_control:
       dist = manhattan(my_pos, opp_pos)
       If my_hp > opp_hp: reward dist <= 2 (aggressive): +5 if True else -3
       If my_hp < opp_hp: reward dist >= 3 (defensive):  +5 if True else -3
  5. skill_readiness    = +8 if my skill_cooldown==0 and my_energy >= 40 else 0
  6. shield_readiness   = +3 if my shield_cooldown==0 and my_energy >= 20 else 0

Add a detailed docstring explaining each weight choice and the design philosophy.

---

### File: backend/ai/cache.py

Implement TranspositionTable class:
  - Internal store: dict[tuple, tuple[float, int]]
    key = state hash tuple, value = (score, depth)
  - get(state_hash: tuple, depth: int) -> Optional[float]:
      Returns score if stored depth >= requested depth, else None
  - store(state_hash: tuple, depth: int, score: float) -> None
  - clear() -> None
  - size() -> int
  - hit_count: int   (increment on successful get)
  - miss_count: int  (increment on failed get)
  - hit_rate() -> float   (hit_count / (hit_count + miss_count), safe division)

---

### File: backend/ai/minimax.py

Implement MinimaxAgent class:

```python
class MinimaxAgent:
    """
    Minimax algorithm with Alpha-Beta Pruning and Transposition Table caching.

    Alpha-Beta Pruning eliminates branches that cannot affect the final decision,
    reducing average complexity from O(b^d) to O(b^(d/2)) in best case.

    Transposition Table stores previously evaluated states to avoid recomputation
    when the same board position is reached via different action sequences.

    This agent always treats itself as the maximizing player.
    """

    def __init__(self, agent_name: str, depth: int = 4, use_cache: bool = True):
        self.agent_name = agent_name
        self.depth = depth
        self.table = TranspositionTable() if use_cache else None
        self.stats = {"nodes_evaluated": 0, "cache_hits": 0, "cache_misses": 0, "time_ms": 0}

    def choose_action(self, state: GameState) -> Action:
        """Entry point. Returns best action via root-level minimax call."""
        ...

    def minimax(self, state: GameState, depth: int, alpha: float,
                beta: float, maximizing: bool) -> float:
        """
        Recursive minimax with alpha-beta pruning.
        alpha: best value the maximizer can guarantee so far
        beta:  best value the minimizer can guarantee so far
        Prune when alpha >= beta (the opponent would never allow this branch).
        """
        ...
```

Requirements:
- Move ordering in choose_action: sort actions so SPECIAL_SKILL > BASIC_ATTACK > SHIELD > MOVE
  (attacks first = better pruning because good moves are evaluated early)
- Transposition Table lookup: check at start of minimax(), before recursion
- Transposition Table store: after computing score, before returning
- Terminal check: return +10000 for win, -10000 for loss (before depth==0 check)
- At depth==0: return heuristic evaluate(state, self.agent_name)
- Track nodes_evaluated (increment each minimax() call)
- Time the full choose_action() call with time.perf_counter()

---

===========================================
## ALGORITHM 2: Monte Carlo Tree Search
===========================================

### File: backend/ai/mcts.py

```python
"""
Monte Carlo Tree Search (MCTS) with UCB1 selection.

MCTS avoids the need for a perfect heuristic by estimating state value
through random simulated playouts (rollouts). It balances:
- Exploitation: choosing moves that have won often
- Exploration: trying less-visited moves (controlled by constant C)

UCB1 formula: wins/visits + C * sqrt(ln(parent.visits) / visits)
C = sqrt(2) ≈ 1.414 is the standard exploration constant.

The 4 phases:
  1. SELECT   — traverse tree using UCB1 until an unexpanded node
  2. EXPAND   — add one new child for an untried action
  3. SIMULATE — random playout from new node until terminal or max depth
  4. BACKPROPAGATE — update wins/visits up the path to root
"""
```

Implement MCTSNode dataclass:
  - state: GameState
  - parent: Optional[MCTSNode]
  - action_taken: Optional[Action]
  - children: List[MCTSNode]
  - visits: int = 0
  - wins: float = 0.0
  - untried_actions: List[Action]   # initialized from get_valid_actions(state)

Implement MCTSAgent class:
  - __init__(agent_name, iterations=500, exploration_c=1.414, max_rollout_depth=30)
  - choose_action(state) -> Action:
      Build tree for `iterations` iterations, return action of most-visited child
  - _select(node) -> MCTSNode:
      UCB1 traversal. If node has untried actions, return it. Else recurse into
      child with highest UCB1 score. Handle visits==0 (treat as infinity → explore first)
  - _expand(node) -> MCTSNode:
      Pop one action from untried_actions, apply it, create child node, add to children
  - _simulate(state) -> float:
      Random rollout: each agent picks random valid action until terminal or max_rollout_depth.
      Return +1 if self.agent_name wins, -1 if loses, 0 if draw/max_depth
  - _backpropagate(node, result):
      Walk up parent chain: node.visits += 1, node.wins += result
      Flip result sign when crossing agent boundary (opponent's node gets -result)
  - stats dict: {nodes_expanded, total_simulations, avg_simulation_depth, time_ms}

## Shared Interface Rule
Both MinimaxAgent and MCTSAgent MUST have identical signature:
  choose_action(state: GameState) -> Action
This lets the server swap them interchangeably.

## Each file must include:
- Module-level docstring explaining the algorithm in plain English
- Time complexity note as a comment (e.g., "# O(b^(d/2)) with alpha-beta")
- `if __name__ == '__main__':` demo showing agent choosing a move from a fresh state
```

---

# PHASE 3 — FastAPI Backend Server

## 🎯 Goal
REST + WebSocket server connecting the Python game engine to the Three.js frontend.
Clean, well-documented, production-style API.

---

## Prompt for Phase 3

```
Build the FastAPI server for "Aegis Arena". Game engine (Phase 1) and AI (Phase 2) are done.

## File: backend/server.py

### In-Memory Store
games: dict[str, GameSession]

GameSession is a dataclass:
  game_id: str
  state: GameState
  arena: Arena
  agents: dict[str, MinimaxAgent | MCTSAgent | None]  # None = human player
  mode: str   # "ai_vs_ai" | "human_vs_ai"
  human_side: Optional[str]
  history: List[dict]   # list of move records for replay

---

### Helper: serialize_state(state, arena, agents) -> dict

Returns:
{
  "agent1": {
    "hp": int, "energy": int, "position": [x, y],
    "shield_active": bool, "skill_cooldown": int, "shield_cooldown": int
  },
  "agent2": { ...same... },
  "grid": [[tile_type_str, ...], ...],     // 8x8, values: "EMPTY","COVER","ENERGY","TRAP"
  "turn": "agent1" | "agent2",
  "turn_count": int,
  "is_terminal": bool,
  "winner": str | null,
  "agent_stats": {
    "agent1": { "nodes_evaluated": int, "cache_hit_rate": float, "time_ms": float },
    "agent2": { "iterations": int, "simulations": int, "time_ms": float }
  }
}

---

### REST Endpoints

POST /new_game
  Body: { "mode": "ai_vs_ai" | "human_vs_ai", "human_side": "agent1" | "agent2" | null }
  - Create Arena with default 8x8 layout
  - Create Agent1 at position (1,1), Agent2 at (6,6), HP=100, Energy=50
  - Create GameState
  - Assign AI: agent1=MinimaxAgent("agent1", depth=4), agent2=MCTSAgent("agent2", iterations=500)
  - If human_vs_ai: set the human's side agent slot to None
  - Store in games dict with uuid4 game_id
  Response: { "game_id": str, "state": serialize_state(...) }

GET /valid_actions/{game_id}
  - Return list of valid action names for current player's turn
  Response: { "actions": ["MOVE_UP", "BASIC_ATTACK", ...] }

POST /action/{game_id}
  Body: { "action": "MOVE_UP" }
  - Only valid when current turn is the human player's side
  - Apply action using apply_action()
  - Append to history
  Response: { "state": serialize_state(...), "action_applied": str }

GET /ai_move/{game_id}
  - Trigger the AI agent for the current turn to compute its move
  - Measure time taken
  - Apply the chosen action
  - Append to history
  Response: {
    "action": str,
    "state": serialize_state(...),
    "stats": { agent-specific stats dict }
  }

GET /history/{game_id}
  - Return full move history for replay
  Response: { "history": [...move records...] }

---

### WebSocket: /ws/{game_id}

Used for AI vs AI mode streaming. On connect, the server runs the full game
automatically, sending a message after each move:

Message types:
  { "type": "move",      "agent": str, "action": str, "state": dict, "stats": dict }
  { "type": "game_over", "winner": str, "total_turns": int, "history": [...] }

Add a configurable delay between moves (default 0.8s) so Three.js can animate.
Accept incoming message: { "type": "set_speed", "delay_ms": int } to allow
the frontend to control replay speed.

---

### CORS + Startup

Enable CORS for all origins (local dev).
Add startup event that logs: "Aegis Arena server ready."

## requirements.txt
fastapi
uvicorn[standard]
websockets
pydantic>=2.0
```

---

# PHASE 4 — Three.js 3D Frontend

## 🎯 Goal
Build a fully realized 3D game. Not a top-down board — a **real 3D tactical arena**
with elevated terrain, dramatic lighting, animated 3D warrior characters,
cinematic camera movement, particle effects, and a glitchy cyberpunk HUD.

This is the most important phase for visual impact. Every detail matters.

---

## Prompt for Phase 4

```
Build the complete Three.js 3D frontend for "Aegis Arena" — an AI combat game
for a university AI Lab project. The FastAPI backend runs at http://localhost:8000.

====================
## VISUAL DIRECTION
====================
Aesthetic: Tactical holographic war room. A glowing 3D arena suspended in
a dark void. Agents are imposing armored warriors built from geometric primitives.
Attacks are explosive and kinetic. The HUD feels like a military AI interface.

Color system:
  --bg:         #050810  (deep space black)
  --grid:       #0d2035  (steel blue grid lines)
  --tile-empty: #0a1520  (dark slate floor)
  --tile-cover: #0a2a12  (dark green bunker)
  --tile-energy:#1a1200  (dark gold)
  --tile-trap:  #1a0000  (dark blood red)
  --agent1:     #00d4ff  (Minimax — electric cyan)
  --agent2:     #ff3333  (MCTS — combat red)
  --accent:     #ffffff  (white)
  --hud-bg:     rgba(5,10,20,0.85)
  --hud-border: #1a3a5c

Font: "Rajdhani" (Google Fonts) — military stencil feel

===================
## 3D ARENA DESIGN
===================

### File: frontend/scene/ArenaScene.js

Build a full 3D arena environment:

FLOOR TILES (8x8 grid):
- Each tile: BoxGeometry(0.92, 0.15, 0.92). Position at (col, 0, row).
- Tile materials (MeshStandardMaterial):
  - EMPTY:  color #0a1520, roughness 0.8, metalness 0.4
  - COVER:  color #0a2a12, roughness 0.6, emissive #003300, emissiveIntensity 0.15
            Add a vertical half-wall: BoxGeometry(0.3, 0.6, 0.92) on tile's back edge
            (representing a barricade the agent crouches behind)
  - ENERGY: color #1a1200, emissive #aa5500, emissiveIntensity animate between 0.2-0.6
            Add a small floating crystal: OctahedronGeometry(0.12) rotating above tile
  - TRAP:   color #200000, emissive #660000, emissiveIntensity animate between 0.1-0.5
            Add spike geometry: 4x ConeGeometry(0.06, 0.2) arranged in X pattern on tile

ARENA BORDER:
- 4 thick walls: BoxGeometry(8.2, 0.8, 0.1) framing the arena perimeter
- Color #0d2035, metalness 0.8
- Thin emissive trim on top edge: BoxGeometry(8.2, 0.03, 0.03), emissive #00aaff

ARENA PILLARS:
- 4 corner pillars: CylinderGeometry(0.15, 0.15, 3.0, 8) at corners
- Color #152535, metalness 0.7
- Glowing ring at top: TorusGeometry(0.2, 0.02, 8, 32) emissive #0066aa

FLOOR GRID LINES:
- LineSegments overlay of full 8x8 grid at y=0.08
- Color #1a3a5c, opacity 0.4

ARENA PLATFORM:
- Single BoxGeometry(8.5, 0.3, 8.5) base underneath tiles
- Color #071018, slight emissive glow #001122

---

### File: frontend/scene/Lighting.js

Build dramatic 3D lighting:

1. AmbientLight: color #223344, intensity 0.3
   (dim enough that emissive tiles and agents glow visibly)

2. DirectionalLight (main): position (5, 12, 8), color #aabbdd, intensity 0.8
   castShadow = true
   shadow.mapSize = 1024x1024
   shadow.camera: near=0.5, far=30, left=-6, right=6, top=6, bottom=-6

3. PointLight (agent1 aura): color #00d4ff, intensity 0.6, distance 3.0
   Follows agent1 position (updated each frame)

4. PointLight (agent2 aura): color #ff3333, intensity 0.6, distance 3.0
   Follows agent2 position (updated each frame)

5. HemisphereLight: skyColor #001133, groundColor #000000, intensity 0.2

6. SpotLight (arena overhead): position (4, 15, 4), target = (4, 0, 4)
   color #ffffff, intensity 0.4, angle 0.4, penumbra 0.3
   Creates a dramatic spotlight cone on the arena

Enable shadow receiving on all tile meshes (receiveShadow = true)
Enable shadow casting on agent meshes (castShadow = true)

---

### File: frontend/scene/AgentMesh.js

Build fully 3D agent characters from Three.js primitives:

AGENT BODY (both agents same structure, different colors):

Body: CylinderGeometry(0.22, 0.28, 0.65, 8) — armored torso
  emissive = agent color, emissiveIntensity 0.3

Head: SphereGeometry(0.18, 8, 8) positioned at y+0.5 above body
  metalness 0.5, roughness 0.3
  Visor: BoxGeometry(0.28, 0.06, 0.1) across front of head
  emissive = agent color, emissiveIntensity 0.8  ← glowing visor

Shoulders: 2x SphereGeometry(0.12, 6, 6), one each side at y+0.2
  metalness 0.7

Legs: 2x CylinderGeometry(0.07, 0.09, 0.35, 6) below torso
  offset left and right by 0.1

Feet: 2x BoxGeometry(0.12, 0.08, 0.18) at bottom of each leg

Base ring: TorusGeometry(0.3, 0.025, 8, 32) at ground level
  emissive = agent color, emissiveIntensity 0.9  ← glowing base

Wrap all parts in a Group. The group's position maps to grid tile center.

SHIELD VISUAL:
  SphereGeometry(0.55, 16, 16)
  MeshPhongMaterial: color = agent color, opacity 0.18, transparent, wireframe false
  Visible only when shield_active = true
  Animate: scale pulses between 1.0 and 1.06 using sin(time)

HP BAR (3D, above agent):
  Background: BoxGeometry(0.8, 0.06, 0.04), color #330000
  Fill: BoxGeometry scaled on X axis proportional to hp/100
  Color interpolates: green (#00ff44) at 100%, yellow (#ffcc00) at 50%, red (#ff2200) at 20%
  Always faces camera (billboard): update rotation in render loop

ENERGY BAR (below HP bar):
  Same structure, color #aa6600 → #ffcc00, proportional to energy/100

Idle animation: agent group bobs up/down by 0.03 units using sin(time * 1.5)
  Each agent has a different phase offset so they don't bob in sync

MOVEMENT ANIMATION:
  Do NOT teleport. Use lerp interpolation.
  Store targetPosition (Three.js Vector3) and currentPosition.
  Each frame: currentPosition.lerp(targetPosition, 0.12)
  If distance < 0.01: snap to target and fire "move complete" callback

---

### File: frontend/scene/CameraRig.js

Implement a two-mode camera system:

MODE 1 — OVERVIEW (default):
  PerspectiveCamera at position (3.5, 11, 14), FOV 50
  Looking at arena center (3.5, 0, 3.5)
  OrbitControls enabled: limited polar angle [10°, 70°], azimuth [-60°, 60°]
  This gives a commanding isometric-ish view of the whole arena

MODE 2 — ACTION CAM (triggers on attack):
  Smoothly move camera to position between the attacker and target,
  slightly elevated and offset to the side.
  Formula: midpoint + offset(0, 3, 4), looking at target agent
  Duration: 0.5s smooth lerp in, hold 1.0s, 0.5s lerp back to overview
  
Implement:
  focusOnAttack(attackerPos3D, targetPos3D):
    Computes action cam position, triggers MODE 2 sequence
  
  update(deltaTime):
    Called every frame. Handles lerp between modes.

---

### File: frontend/scene/Effects.js

Implement all visual effects:

1. PROJECTILE EFFECT — for BASIC_ATTACK:
   - Create a SphereGeometry(0.07) with emissive color of attacker
   - Animate from attacker 3D position to target 3D position over 0.3s
   - On arrival: explode into 20 Points (random directions, fade out over 0.4s)
   - Points geometry: BufferGeometry with 20 vertices, PointsMaterial size 0.05

2. SHOCKWAVE — for SPECIAL_SKILL:
   - TorusGeometry(0.1, 0.05, 8, 32) at target tile position, y = 0.1
   - Scale from 0.1 to 2.5 over 0.5s, opacity fades from 1 to 0
   - Color = attacker's agent color
   - Simultaneously: 40-particle burst (Points) at target with random upward velocity
   - Camera shake: apply small random offset to camera position (amplitude 0.08, decay over 0.4s)

3. SHIELD PULSE — for DEFENSIVE_SHIELD activation:
   - Expanding ring: TorusGeometry(0.3 → 0.9), opacity 1 → 0, duration 0.6s
   - Color = agent color

4. DAMAGE NUMBER (CSS2DRenderer):
   - Create a div with damage amount in red ("-15") or heal in green ("+20 ⚡")
   - Position at target agent's 3D position + (0, 1.5, 0), projected to screen
   - Float upward 60px and fade out over 1.2s using CSS animation
   - Font: bold, "Rajdhani", size 1.4rem

5. TILE GLOW PULSE — for ENERGY and TRAP tiles:
   - Maintain a time uniform, animate emissiveIntensity per-tile in render loop
   - ENERGY: emissiveIntensity = 0.3 + 0.3 * sin(time * 2.0 + tile_phase)
   - TRAP:   emissiveIntensity = 0.2 + 0.2 * sin(time * 3.0 + tile_phase)
   - Each tile has a random phase offset so they don't all pulse in sync

6. DEATH EFFECT — when an agent reaches 0 HP:
   - Explode the agent into 30 debris particles (small Box/SphereGeometry pieces)
   - Particles fly outward and fall with gravity simulation (velocity + gravity each frame)
   - Agent mesh fades out over 0.8s
   - Large shockwave ring expands at ground level

---

## HUD SYSTEM

### File: frontend/ui/HUD.js

Build the HTML/CSS HUD overlay (position:absolute over canvas):

AGENT 1 PANEL (top-left):
```html
<div id="panel-a1" class="agent-panel cyan">
  <div class="agent-name">AGENT α <span class="algo-tag">MINIMAX</span></div>
  <div class="stat-row">
    <span>HP</span>
    <div class="bar hp-bar"><div class="fill" id="hp1"></div></div>
    <span id="hp1-val">100/100</span>
  </div>
  <div class="stat-row">
    <span>⚡</span>
    <div class="bar en-bar"><div class="fill" id="en1"></div></div>
    <span id="en1-val">50/100</span>
  </div>
  <div class="cooldowns">
    <span class="cd-icon" id="shield1" title="Shield">🛡</span>
    <span class="cd-icon" id="skill1"  title="Skill">⚡</span>
  </div>
  <div class="ai-stats" id="stats1">Nodes: — | Cache: —%</div>
</div>
```

AGENT 2 PANEL (top-right): Same structure, mirrored, red color scheme.

TURN INDICATOR (top-center):
  <div id="turn-indicator">AGENT α COMPUTING...</div>
  Animate with blinking dot and pulse glow during AI computation

ACTION LOG (bottom-left):
  Scrolling div showing last 8 actions:
  "Turn 5 | Agent α → SPECIAL_SKILL → -35 HP"
  Monospace font, newest on top, old entries fade to 30% opacity

CSS REQUIREMENTS:
  - All panels use backdrop-filter: blur(8px) for glass effect
  - Borders: 1px solid --hud-border with box-shadow glow in agent color
  - HP fill color transitions with CSS: green → yellow → red
  - Cooldown icons dim (opacity 0.25) + show countdown number when on cooldown
  - Panels slide in from their respective edges on game start (CSS transition)

---

### File: frontend/ui/ActionPanel.js

For Human vs AI mode — appears at bottom-center on human's turn:

```
[ ↑ ]
[ ← ] [↓] [ → ]        [ ⚔ ATTACK ]  [ 🛡 SHIELD ]  [ ⚡ SKILL ]
```

Styling:
- D-pad: 3x3 grid of buttons, square, 48x48px, dark bg with cyan/red border
- Action buttons: wider, with glow effect
- All buttons: hover scale(1.05), active scale(0.95)
- Buttons for SHIELD and SKILL dim (opacity 0.4, pointer-events:none) when on cooldown
- Tooltip on disabled button: "Cooldown: 3 turns"
- Slide up from bottom when it's human's turn, slide down when not

---

### File: frontend/ui/MenuScreen.js

Full-screen animated menu overlaying the 3D scene:

Title: "AEGIS ARENA"
- Font: Rajdhani 900 weight, 6rem, color white
- Glitch animation: every 4s, the title briefly skews and color-shifts
  (CSS animation with clip-path and transform for glitch frames)
- Subtitle: "ADVERSARIAL AI COMBAT SIMULATION"
  in small uppercase tracking-widest, color #4488aa

Mode buttons:
  [ ⚔  AI vs AI    ]   — cyan border
  [ 🎮  Human vs AI ]   — red border
  Buttons are large, full-width, styled as tactical interface elements

Side selection (appears after Human vs AI click):
  "CHOOSE YOUR SIDE"
  [ AGENT α — MINIMAX — CYAN ] [ AGENT β — MCTS — RED ]

Background: the 3D arena is visible and slowly rotating behind the menu
(camera slowly orbiting during menu screen)

---

### File: frontend/game/GameController.js

Main orchestrator:

```javascript
class GameController {
  constructor(scene, hud, actionPanel, camera, apiClient) { ... }

  async startGame(mode, humanSide) {
    // POST /new_game → get game_id + initial state
    // Initialize arena mesh, agent meshes
    // If ai_vs_ai: connect WebSocket, start streaming
    // If human_vs_ai: render human's turn when appropriate
  }

  async handleAITurn() {
    // GET /ai_move → get action + new state + stats
    // Play attack animation if applicable (await Effects.projectile/shockwave)
    // Await camera action focus, then return to overview
    // Update HUD with new stats
    // If terminal: show game over screen
  }

  handleHumanAction(action) {
    // POST /action → new state
    // Animate move/attack
    // Then trigger handleAITurn()
  }

  applyStateToScene(state) {
    // Update agent mesh targetPositions
    // Update HP/energy bars
    // Update cooldown icons
    // Update tile visuals if trap triggered
  }
}
```

Speed control (AI vs AI only): [0.5×] [1×] [2×] buttons in top-center.
Sends WebSocket message { "type": "set_speed", "delay_ms": X } to backend.

Game Over overlay:
  - Full-screen overlay fades in
  - "AGENT α WINS" / "AGENT β WINS" in large glitch-animated text
  - Final stats: total turns, nodes evaluated, cache hit rate
  - "PLAY AGAIN" button

---

### File: frontend/game/APIClient.js

```javascript
export const APIClient = {
  base: 'http://localhost:8000',

  newGame: async (mode, humanSide) => {
    const res = await fetch(`${APIClient.base}/new_game`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode, human_side: humanSide })
    });
    return res.json();
  },

  getValidActions: async (gameId) => { ... },
  submitAction: async (gameId, action) => { ... },
  getAIMove: async (gameId) => { ... },

  connectWebSocket: (gameId, onMessage) => {
    const ws = new WebSocket(`ws://localhost:8000/ws/${gameId}`);
    ws.onmessage = (event) => onMessage(JSON.parse(event.data));
    return ws;
  }
};
```

---

### File: frontend/index.html

```html
<!DOCTYPE html>
<html>
<head>
  <title>Aegis Arena</title>
  <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700;900&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #050810; overflow: hidden; font-family: 'Rajdhani', sans-serif; }
    #canvas-container { position: fixed; inset: 0; }
    /* HUD elements positioned absolute over canvas */
    ...
  </style>
</head>
<body>
  <div id="canvas-container"></div>
  <!-- HUD panels injected by HUD.js -->
  <!-- CSS2DRenderer labels injected by Effects.js -->
  <!-- Menu overlay injected by MenuScreen.js -->

  <script type="importmap">
    { "imports": { "three": "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.module.js" } }
  </script>
  <script type="module" src="main.js"></script>
</body>
</html>
```

---

### File: frontend/main.js

Three.js bootstrap and render loop:

```javascript
import * as THREE from 'three';
// Import OrbitControls from Three.js r128 CDN examples path
import { OrbitControls } from 'https://cdn.jsdelivr.net/npm/three@0.128/examples/jsm/controls/OrbitControls.js';
import { CSS2DRenderer } from 'https://cdn.jsdelivr.net/npm/three@0.128/examples/jsm/renderers/CSS2DRenderer.js';

// Setup: WebGLRenderer with antialias + shadowMap enabled
// CSS2DRenderer for damage numbers
// Scene, Camera, Controls
// Clock for deltaTime

// Render loop:
function animate() {
  requestAnimationFrame(animate);
  const delta = clock.getDelta();
  const time  = clock.getElapsedTime();

  controls.update();
  arenaScene.update(time);     // tile pulse animations
  agentMeshes.forEach(a => a.update(time, delta));  // idle bob + lerp movement
  effects.update(time, delta); // particle systems, projectiles
  cameraRig.update(delta);     // camera mode transitions
  lightingRig.update();        // move point lights to agent positions

  renderer.render(scene, camera);
  css2DRenderer.render(scene, camera);
}
```

## Critical Three.js r128 Notes
- DO NOT use THREE.CapsuleGeometry (added in r142). Use CylinderGeometry for agent limbs.
- DO NOT use THREE.RoundedBoxGeometry. Use BoxGeometry.
- OrbitControls and CSS2DRenderer must be loaded from CDN examples JSM path.
- Use WebGLRenderer({ antialias: true, shadowMap: true }).
- renderer.shadowMap.type = THREE.PCFSoftShadowMap for soft shadows.
- All grid positions: arena(row, col) → Three.js(col * 1.0, 0, row * 1.0).
- Group agent parts under a parent Group; move the Group for position updates.
```

---

# PHASE 5 — Integration, Polish & Academic Report

## 🎯 Goal
Wire everything together, validate AI vs AI and Human vs AI modes,
add test scripts, and finalize documentation for the lab report.

---

## Prompt for Phase 5

```
Aegis Arena is complete — all phases done. Final integration and polish pass.

## 1. Integration Test: backend/test_game.py

Write a headless test runner (no server, no frontend):
- Create Arena and two agents
- Create MinimaxAgent("agent1") and MCTSAgent("agent2")
- Run a complete game to terminal state, logging each turn:
    "Turn 4 | agent1 @ (2,3) | SPECIAL_SKILL → agent2 loses 35 HP | agent2 HP: 65"
- After game: print final stats table:
    Winner, Total turns, Minimax nodes evaluated, Cache hit rate, MCTS simulations
- Run 5 games, print win rate per agent and average game length

## 2. Add performance stats to server serialization
- serialize_state() must always include latest agent stats
- Frontend HUD.js must update "Nodes: X | Cache: Y%" panel after each AI move

## 3. Game balance sanity check
- In test_game.py, assert games end within 100 turns
- Assert both agents win at least once across 5 games (non-trivial play)
- Print warning if Minimax always wins (may need MCTS iteration increase)

## 4. README.md
```markdown
# 🛡️ Aegis Arena
AI Laboratory Project — CSE 3210 | KUET

## Setup
cd backend
pip install -r requirements.txt
uvicorn server:app --reload

## Open frontend/index.html in browser (use Live Server or any static server)

## Modes
- AI vs AI: Watch Minimax (Agent α) vs MCTS (Agent β) duel live
- Human vs AI: Play against MCTS using keyboard/buttons

## Algorithms
| Agent | Algorithm | Optimization |
|-------|-----------|--------------|
| α | Minimax + Alpha-Beta Pruning | Transposition Table, Move Ordering |
| β | Monte Carlo Tree Search | UCB1, Random Rollouts |

## Architecture
Python backend (game engine + AI + FastAPI) ↔ Three.js frontend (full 3D)

## Reference
Russell, S. & Norvig, P. — Artificial Intelligence: A Modern Approach
```

## 5. Code audit
- Every .py file: module docstring, all functions type-hinted and docstrung
- Every .js file: JSDoc comment on each class and major function
- minimax.py: comment block at top explaining Alpha-Beta Pruning algorithm step-by-step
- mcts.py: comment block at top explaining the 4 MCTS phases with pseudocode
- Remove all debug console.log and print statements (or gate behind DEBUG flag)
```

---

# 📊 Algorithm Comparison

| Feature | Minimax + α-β | MCTS |
|---|---|---|
| Strategy | Exhaustive adversarial tree search | Statistical sampling via random rollouts |
| Depth control | Fixed (depth=4) | Iteration-based (500 rollouts) |
| Key optimization | Alpha-Beta pruning + Transposition Table | UCB1 exploration-exploitation balance |
| Strength | Tactically precise, deterministic | Handles large branching, no perfect heuristic needed |
| Weakness | Exponential depth growth | Stochastic — results vary between runs |
| Complexity | O(b^(d/2)) with α-β (best case) | O(iterations × rollout_depth) |
| Best in game | Early/mid game positioning | Late game with complex energy states |

---

# 🔄 Build Order

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
 Engine     AI      Server    3D Front   Polish
```

**Rules:**
- Test Phase 1 with `if __name__=='__main__'` blocks before writing any AI
- Test Phase 2 with `test_game.py` before starting the server
- Test Phase 3 with curl/Postman before building the frontend
- Build Phase 4 connecting to live backend (have server running during frontend dev)

---

# 🎮 Final 3D Game Features Summary

| Feature | Implementation |
|---|---|
| 3D arena with terrain | Elevated tiles, barricades, crystals, spikes, border walls, corner pillars |
| 3D agent characters | Full warrior built from CylinderGeometry + SphereGeometry + BoxGeometry parts |
| Dramatic lighting | Directional (shadows) + per-agent point lights + arena spotlight |
| Attack animations | Projectile, shockwave ring, particle burst, camera shake |
| Cinematic camera | Overview orbit + action zoom during attacks |
| Death effect | Debris explosion + fade out |
| Damage numbers | CSS2DRenderer floating labels |
| Tile effects | Pulsing emissive glow, rotating energy crystals, trap spikes |
| Shield visual | Semi-transparent pulsing sphere |
| Glitch title screen | CSS glitch animation on "AEGIS ARENA" |
| AI stats HUD | Live nodes evaluated, cache hit rate, MCTS simulations |
| Speed control | 0.5× / 1× / 2× for AI vs AI viewing |

---

*Aegis Arena | CSE 3210 AI Laboratory | KUET | 2026*
*Algorithms: Minimax + Alpha-Beta Pruning (Agent α) vs Monte Carlo Tree Search (Agent β)*
