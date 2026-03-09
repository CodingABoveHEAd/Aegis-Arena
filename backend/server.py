"""Aegis Arena — FastAPI backend server (REST + WebSocket).

Provides endpoints for:
* Initialising a new game session
* Querying the current game state
* Submitting human / AI moves
* Running a full AI-vs-AI match
* Real-time WebSocket streaming of game events

Usage::

    uvicorn backend.server:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from backend.game.arena import Arena
    from backend.game.agent import Agent
    from backend.game.state import GameState
    from backend.game.actions import Action, apply_action, get_valid_actions
    from backend.ai.minimax import MinimaxAgent
    from backend.ai.mcts import MCTSAgent
except ImportError:
    try:
        from game.arena import Arena
        from game.agent import Agent
        from game.state import GameState
        from game.actions import Action, apply_action, get_valid_actions
        from ai.minimax import MinimaxAgent
        from ai.mcts import MCTSAgent
    except ImportError:
        from arena import Arena
        from agent import Agent
        from state import GameState
        from actions import Action, apply_action, get_valid_actions
        from minimax import MinimaxAgent
        from mcts import MCTSAgent


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Aegis Arena",
    description="Turn-based adversarial AI game engine API",
    version="1.0.0",
)

# Allow the Three.js frontend (served separately) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# In-memory session store
# ---------------------------------------------------------------------------

_sessions: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class NewGameRequest(BaseModel):
    """Body for ``POST /game/new``."""
    agent1_type: str = "human"         # "human" | "minimax" | "mcts"
    agent2_type: str = "minimax"
    grid_size: int = 8
    minimax_depth: int = 4
    minimax_time_ms: int = 800
    mcts_iterations: int = 500


class MoveRequest(BaseModel):
    """Body for ``POST /game/{session_id}/move``."""
    action: str  # e.g. "MOVE_UP", "BASIC_ATTACK"


class AIMatchRequest(BaseModel):
    """Body for ``POST /game/ai-match``."""
    agent1_algo: str = "minimax"       # "minimax" | "mcts"
    agent2_algo: str = "mcts"
    max_turns: int = 200
    minimax_depth: int = 4
    minimax_time_ms: int = 800
    mcts_iterations: int = 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ai(name: str, algo: str, cfg: Dict[str, Any]) -> Optional[Any]:
    """Create an AI agent instance or ``None`` for human players."""
    if algo == "minimax":
        return MinimaxAgent(
            name,
            depth=cfg.get("minimax_depth", 4),
            time_budget_ms=cfg.get("minimax_time_ms", 800),
        )
    if algo == "mcts":
        return MCTSAgent(
            name,
            iterations=cfg.get("mcts_iterations", 500),
        )
    return None


def _state_response(session: Dict[str, Any]) -> Dict[str, Any]:
    """Build a JSON-friendly response from a session dict."""
    state: GameState = session["state"]
    resp = state.to_dict()
    resp["session_id"] = session["session_id"]
    resp["valid_actions"] = [a.value for a in get_valid_actions(state)]
    resp["is_terminal"] = state.is_terminal()
    resp["winner"] = state.get_winner()
    return resp


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.post("/game/new")
def new_game(req: NewGameRequest) -> Dict[str, Any]:
    """Create a new game session and return the initial state."""
    session_id: str = uuid.uuid4().hex[:12]
    arena = Arena(size=req.grid_size)
    a1 = Agent("agent1", position=(0, 0))
    a2 = Agent("agent2", position=(7, 7))
    state = GameState(a1, a2, arena)

    cfg: Dict[str, Any] = {
        "minimax_depth": req.minimax_depth,
        "minimax_time_ms": req.minimax_time_ms,
        "mcts_iterations": req.mcts_iterations,
    }

    session: Dict[str, Any] = {
        "session_id": session_id,
        "state": state,
        "agent1_type": req.agent1_type,
        "agent2_type": req.agent2_type,
        "ai1": _make_ai("agent1", req.agent1_type, cfg),
        "ai2": _make_ai("agent2", req.agent2_type, cfg),
        "history": [],
    }
    _sessions[session_id] = session
    return _state_response(session)


@app.get("/game/{session_id}")
def get_state(session_id: str) -> Dict[str, Any]:
    """Return the current game state for a session."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    return _state_response(session)


@app.post("/game/{session_id}/move")
def submit_move(session_id: str, req: MoveRequest) -> Dict[str, Any]:
    """Apply a human (or manual) move and return the new state."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    state: GameState = session["state"]
    if state.is_terminal():
        raise HTTPException(400, "Game is already over")

    # Validate the action string
    try:
        action = Action(req.action)
    except ValueError:
        raise HTTPException(400, f"Unknown action: {req.action}")

    valid = get_valid_actions(state)
    if action not in valid:
        raise HTTPException(400, f"Action {req.action} is not valid in current state")

    new_state = apply_action(state, action)
    session["state"] = new_state
    session["history"].append({"agent": state.current_agent, "action": req.action})

    return _state_response(session)


@app.post("/game/{session_id}/ai-move")
def ai_move(session_id: str) -> Dict[str, Any]:
    """Let the AI choose and apply a move for the current agent."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    state: GameState = session["state"]
    if state.is_terminal():
        raise HTTPException(400, "Game is already over")

    # Determine which AI controls the current agent
    ai_agent = session["ai1"] if state.current_agent == "agent1" else session["ai2"]
    if ai_agent is None:
        raise HTTPException(400, f"{state.current_agent} is human-controlled")

    action: Action = ai_agent.choose_action(state)
    new_state = apply_action(state, action)
    session["state"] = new_state
    session["history"].append({"agent": state.current_agent, "action": action.value})

    resp = _state_response(session)
    resp["ai_action"] = action.value
    resp["ai_stats"] = getattr(ai_agent, "stats", {})
    return resp


@app.post("/game/ai-match")
def run_ai_match(req: AIMatchRequest) -> Dict[str, Any]:
    """Run a complete AI-vs-AI match and return the result + history."""
    arena = Arena()
    a1 = Agent("agent1", position=(0, 0))
    a2 = Agent("agent2", position=(7, 7))
    state = GameState(a1, a2, arena)

    cfg: Dict[str, Any] = {
        "minimax_depth": req.minimax_depth,
        "minimax_time_ms": req.minimax_time_ms,
        "mcts_iterations": req.mcts_iterations,
    }

    ai1 = _make_ai("agent1", req.agent1_algo, cfg)
    ai2 = _make_ai("agent2", req.agent2_algo, cfg)
    if ai1 is None or ai2 is None:
        raise HTTPException(400, "Both agents must be AI for ai-match")

    history: list[Dict[str, Any]] = []

    for turn in range(req.max_turns):
        if state.is_terminal():
            break
        ai = ai1 if state.current_agent == "agent1" else ai2
        action: Action = ai.choose_action(state)
        history.append({
            "turn": state.turn_count,
            "agent": state.current_agent,
            "action": action.value,
            "a1_hp": state.agent1.hp,
            "a2_hp": state.agent2.hp,
        })
        state = apply_action(state, action)

    return {
        "winner": state.get_winner(),
        "total_turns": state.turn_count,
        "final_state": state.to_dict(),
        "history": history,
    }


@app.get("/game/{session_id}/history")
def get_history(session_id: str) -> Dict[str, Any]:
    """Return the move history for a session."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    return {"session_id": session_id, "history": session["history"]}


# ---------------------------------------------------------------------------
# WebSocket for real-time game updates
# ---------------------------------------------------------------------------

@app.websocket("/ws/{session_id}")
async def game_websocket(websocket: WebSocket, session_id: str) -> None:
    """WebSocket endpoint for real-time game streaming.

    Messages from client:
      ``{"type": "move", "action": "MOVE_UP"}``
      ``{"type": "ai_move"}``

    Messages to client:
      Full state JSON after each action.
    """
    session = _sessions.get(session_id)
    if session is None:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()

    try:
        # Send initial state
        await websocket.send_json(_state_response(session))

        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue

            state: GameState = session["state"]
            if state.is_terminal():
                await websocket.send_json({"error": "Game over", **_state_response(session)})
                continue

            msg_type: str = msg.get("type", "")

            if msg_type == "move":
                action_str = msg.get("action", "")
                try:
                    action = Action(action_str)
                except ValueError:
                    await websocket.send_json({"error": f"Unknown action: {action_str}"})
                    continue
                valid = get_valid_actions(state)
                if action not in valid:
                    await websocket.send_json({"error": f"Invalid action: {action_str}"})
                    continue
                new_state = apply_action(state, action)
                session["state"] = new_state
                session["history"].append({"agent": state.current_agent, "action": action_str})

            elif msg_type == "ai_move":
                ai = session["ai1"] if state.current_agent == "agent1" else session["ai2"]
                if ai is None:
                    await websocket.send_json({"error": "Current agent is human"})
                    continue
                action = ai.choose_action(state)
                new_state = apply_action(state, action)
                session["state"] = new_state
                session["history"].append({"agent": state.current_agent, "action": action.value})
            else:
                await websocket.send_json({"error": f"Unknown message type: {msg_type}"})
                continue

            await websocket.send_json(_state_response(session))

    except WebSocketDisconnect:
        pass  # client disconnected gracefully


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000, reload=True)
