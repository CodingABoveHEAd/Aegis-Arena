"""Aegis Arena — FastAPI backend server (REST + WebSocket).

Provides endpoints for:
* Creating new game sessions (human-vs-AI or AI-vs-AI)
* Querying game state and valid actions
* Submitting human moves and triggering AI moves
* Full game history for replay
* WebSocket streaming for AI-vs-AI auto-play with configurable speed

Usage::

    uvicorn server:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from backend.game.arena import Arena, TileType
    from backend.game.agent import Agent
    from backend.game.state import GameState
    from backend.game.actions import Action, apply_action, get_valid_actions
    from backend.ai.minimax import MinimaxAgent
    from backend.ai.mcts import MCTSAgent
except ImportError:
    try:
        from game.arena import Arena, TileType
        from game.agent import Agent
        from game.state import GameState
        from game.actions import Action, apply_action, get_valid_actions
        from ai.minimax import MinimaxAgent
        from ai.mcts import MCTSAgent
    except ImportError:
        from arena import Arena, TileType  # type: ignore
        from agent import Agent  # type: ignore
        from state import GameState  # type: ignore
        from actions import Action, apply_action, get_valid_actions  # type: ignore
        from minimax import MinimaxAgent  # type: ignore
        from mcts import MCTSAgent  # type: ignore

logger = logging.getLogger("aegis_arena")


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Aegis Arena",
    description="Turn-based adversarial AI game engine API",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _on_startup() -> None:
    logger.info("Aegis Arena server ready.")


@app.get("/")
def root() -> Dict[str, Any]:
    """Health-check / info endpoint."""
    return {
        "game": "Aegis Arena",
        "version": "2.0.0",
        "status": "running",
        "endpoints": [
            "POST /new_game",
            "GET  /valid_actions/{game_id}",
            "POST /action/{game_id}",
            "GET  /ai_move/{game_id}",
            "GET  /history/{game_id}",
            "WS   /ws/{game_id}",
        ],
    }


# ---------------------------------------------------------------------------
# In-memory game store
# ---------------------------------------------------------------------------

@dataclass
class GameSession:
    """Persistent session for a single game."""

    game_id: str
    state: GameState
    arena: Arena
    agents: Dict[str, Union[MinimaxAgent, MCTSAgent, None]]
    mode: str                          # "ai_vs_ai" | "human_vs_ai"
    human_side: Optional[str]          # "agent1" | "agent2" | None
    history: List[Dict[str, Any]] = field(default_factory=list)


games: Dict[str, GameSession] = {}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class NewGameRequest(BaseModel):
    mode: str = "human_vs_ai"          # "ai_vs_ai" | "human_vs_ai"
    human_side: Optional[str] = "agent1"


class ActionRequest(BaseModel):
    action: str                        # e.g. "MOVE_UP", "BASIC_ATTACK"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_session(game_id: str) -> GameSession:
    session = games.get(game_id)
    if session is None:
        raise HTTPException(404, "Game not found")
    return session


def _agent_stats(session: GameSession) -> Dict[str, Any]:
    """Build per-agent AI stats (empty dict for human slots)."""
    out: Dict[str, Any] = {}
    for name in ("agent1", "agent2"):
        ai = session.agents.get(name)
        if ai is None:
            out[name] = {}
        elif isinstance(ai, MinimaxAgent):
            s = getattr(ai, "stats", {})
            out[name] = {
                "nodes_evaluated": int(s.get("nodes_evaluated", 0)),
                "cache_hit_rate": (
                    ai.table.hit_rate() if ai.table is not None else 0.0
                ),
                "time_ms": s.get("time_ms", 0.0),
                "search_depth_reached": int(s.get("depth_reached", 0)),
            }
        elif isinstance(ai, MCTSAgent):
            s = getattr(ai, "stats", {})
            out[name] = {
                "iterations": ai.iterations,
                "simulations": int(s.get("total_simulations", 0)),
                "time_ms": s.get("time_ms", 0.0),
            }
    return out


def _elevated_tiles(arena: Arena) -> List[List[int]]:
    """Return list of [row, col] positions that are ELEVATED."""
    result: List[List[int]] = []
    for r in range(arena.size):
        for c in range(arena.size):
            if arena.grid[r][c] == TileType.ELEVATED:
                result.append([r, c])
    return result


def _tile_durability_map(arena: Arena) -> Dict[str, int]:
    """Return tile durability as ``{"r,c": hits_remaining}``."""
    return {
        f"{r},{c}": hp
        for (r, c), hp in arena.tile_durability.items()
    }


def serialize_state(
    state: GameState,
    arena: Arena,
    session: GameSession,
) -> Dict[str, Any]:
    """Produce the canonical JSON-friendly state representation.

    Includes Phase 3 additions: burn_turns, slow_active per agent,
    tile_durability map, elevated_tiles list, and search_depth_reached
    for Minimax agents.
    """
    a1 = state.agent1
    a2 = state.agent2
    return {
        "agent1": {
            "hp": a1.hp,
            "energy": a1.energy,
            "position": list(a1.position),
            "shield_active": a1.shield_active,
            "skill_cooldown": a1.skill_cooldown,
            "shield_cooldown": a1.shield_cooldown,
            "burn_turns": a1.burn_turns,
            "slow_active": a1.slow_active,
        },
        "agent2": {
            "hp": a2.hp,
            "energy": a2.energy,
            "position": list(a2.position),
            "shield_active": a2.shield_active,
            "skill_cooldown": a2.skill_cooldown,
            "shield_cooldown": a2.shield_cooldown,
            "burn_turns": a2.burn_turns,
            "slow_active": a2.slow_active,
        },
        "grid": arena.to_grid_list(),
        "turn": state.current_agent,
        "turn_count": state.turn_count,
        "is_terminal": state.is_terminal(),
        "winner": state.get_winner(),
        "tile_durability": _tile_durability_map(arena),
        "elevated_tiles": _elevated_tiles(arena),
        "consumed_tiles": [[r, c] for r, c in sorted(arena.consumed_tiles)],
        "agent_stats": _agent_stats(session),
    }


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.post("/new_game")
def new_game(req: NewGameRequest) -> Dict[str, Any]:
    """Create a new game session.

    * Agent1 starts at (1,1), Agent2 at (6,6), HP=100, Energy=50.
    * Agent1 = MinimaxAgent(depth=4), Agent2 = MCTSAgent(iterations=500).
    * In human_vs_ai mode the human's slot is set to None.
    """
    game_id = uuid.uuid4().hex
    arena = Arena()
    a1 = Agent("agent1", position=(1, 1))
    a2 = Agent("agent2", position=(6, 6))
    state = GameState(a1, a2, arena)

    agents: Dict[str, Union[MinimaxAgent, MCTSAgent, None]] = {
        "agent1": MinimaxAgent("agent1", depth=4),
        "agent2": MCTSAgent("agent2", iterations=1000),
    }

    human_side: Optional[str] = None
    mode = req.mode
    if mode == "human_vs_ai":
        human_side = req.human_side or "agent1"
        agents[human_side] = None

    session = GameSession(
        game_id=game_id,
        state=state,
        arena=arena,
        agents=agents,
        mode=mode,
        human_side=human_side,
    )
    games[game_id] = session
    return {"game_id": game_id, "state": serialize_state(state, arena, session)}


@app.get("/valid_actions/{game_id}")
def valid_actions(game_id: str) -> Dict[str, Any]:
    """Return valid action names for the current player."""
    session = _get_session(game_id)
    actions = get_valid_actions(session.state)
    return {"actions": [a.value for a in actions]}


@app.post("/action/{game_id}")
def submit_action(game_id: str, req: ActionRequest) -> Dict[str, Any]:
    """Apply a human move. Only valid when it is the human player's turn."""
    session = _get_session(game_id)
    state = session.state

    if state.is_terminal():
        raise HTTPException(400, "Game is already over")

    # Enforce human-side restriction in human_vs_ai mode
    if session.mode == "human_vs_ai" and state.current_agent != session.human_side:
        raise HTTPException(400, f"It is not the human player's turn")

    try:
        action = Action(req.action)
    except ValueError:
        raise HTTPException(400, f"Unknown action: {req.action}")

    valid = get_valid_actions(state)
    if action not in valid:
        raise HTTPException(400, f"Action {req.action} is not valid in current state")

    new_state = apply_action(state, action)
    session.state = new_state
    session.history.append({
        "turn": state.turn_count,
        "agent": state.current_agent,
        "action": req.action,
    })
    return {
        "state": serialize_state(new_state, session.arena, session),
        "action_applied": req.action,
    }


@app.get("/ai_move/{game_id}")
def ai_move(game_id: str) -> Dict[str, Any]:
    """Trigger the AI agent for the current turn to compute and apply a move."""
    session = _get_session(game_id)
    state = session.state

    if state.is_terminal():
        raise HTTPException(400, "Game is already over")

    ai_agent = session.agents.get(state.current_agent)
    if ai_agent is None:
        raise HTTPException(400, f"{state.current_agent} is human-controlled")

    action: Action = ai_agent.choose_action(state)
    new_state = apply_action(state, action)
    session.state = new_state

    stats = dict(getattr(ai_agent, "stats", {}))
    # Include search_depth_reached for Minimax agents
    if isinstance(ai_agent, MinimaxAgent):
        stats["search_depth_reached"] = int(stats.pop("depth_reached", 0))

    session.history.append({
        "turn": state.turn_count,
        "agent": state.current_agent,
        "action": action.value,
        "stats": stats,
    })

    return {
        "action": action.value,
        "state": serialize_state(new_state, session.arena, session),
        "stats": stats,
    }


@app.get("/history/{game_id}")
def get_history(game_id: str) -> Dict[str, Any]:
    """Return full move history for replay."""
    session = _get_session(game_id)
    return {"history": session.history}


# ---------------------------------------------------------------------------
# WebSocket — AI vs AI streaming
# ---------------------------------------------------------------------------

@app.websocket("/ws/{game_id}")
async def ws_game(websocket: WebSocket, game_id: str) -> None:
    """Stream an AI-vs-AI match move by move.

    On connect the server runs the full game automatically, sending a
    message after each move.  Accepts ``{"type": "set_speed", "delay_ms": int}``
    from the client to adjust animation pace.

    Message types sent::

        { "type": "move",      "agent": str, "action": str,
          "state": dict, "stats": dict }
        { "type": "game_over", "winner": str | null,
          "total_turns": int, "history": list }
    """
    session = games.get(game_id)
    if session is None:
        await websocket.close(code=4004, reason="Game not found")
        return

    await websocket.accept()

    delay_s: float = 0.8  # default 800 ms between moves

    try:
        while not session.state.is_terminal():
            # Check for incoming speed-control messages (non-blocking)
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(), timeout=0.01
                )
                msg = json.loads(raw)
                if msg.get("type") == "set_speed":
                    delay_s = max(0.0, msg.get("delay_ms", 800)) / 1000.0
            except (asyncio.TimeoutError, json.JSONDecodeError):
                pass

            state = session.state
            current = state.current_agent
            ai_agent = session.agents.get(current)
            if ai_agent is None:
                # human slot in a ws stream — skip (shouldn't happen for ai_vs_ai)
                break

            action: Action = ai_agent.choose_action(state)
            new_state = apply_action(state, action)
            session.state = new_state

            stats = dict(getattr(ai_agent, "stats", {}))
            if isinstance(ai_agent, MinimaxAgent):
                stats["search_depth_reached"] = int(stats.pop("depth_reached", 0))

            session.history.append({
                "turn": state.turn_count,
                "agent": current,
                "action": action.value,
                "stats": stats,
            })

            await websocket.send_json({
                "type": "move",
                "agent": current,
                "action": action.value,
                "state": serialize_state(new_state, session.arena, session),
                "stats": stats,
            })

            await asyncio.sleep(delay_s)

        # Game over
        await websocket.send_json({
            "type": "game_over",
            "winner": session.state.get_winner(),
            "total_turns": session.state.turn_count,
            "history": session.history,
        })

    except WebSocketDisconnect:
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
