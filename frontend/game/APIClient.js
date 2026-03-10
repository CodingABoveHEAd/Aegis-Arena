/**
 * APIClient.js — HTTP + WebSocket client for the Aegis Arena backend.
 *
 * All REST calls target the FastAPI server.  The WebSocket helper is used
 * for AI-vs-AI streaming.
 */

const BASE = 'http://localhost:8000';

export const APIClient = {
  base: BASE,

  /** POST /new_game */
  newGame: async (mode, humanSide = null, algorithms = {}) => {
    const body = { mode };
    if (humanSide) body.human_side = humanSide;
    if (algorithms.agent1_algorithm) body.agent1_algorithm = algorithms.agent1_algorithm;
    if (algorithms.agent2_algorithm) body.agent2_algorithm = algorithms.agent2_algorithm;
    const res = await fetch(`${BASE}/new_game`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  /** GET /valid_actions/{gameId} */
  getValidActions: async (gameId) => {
    const res = await fetch(`${BASE}/valid_actions/${gameId}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  /** POST /action/{gameId} */
  submitAction: async (gameId, action) => {
    const res = await fetch(`${BASE}/action/${gameId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  /** GET /ai_move/{gameId} */
  getAIMove: async (gameId) => {
    const res = await fetch(`${BASE}/ai_move/${gameId}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  /** GET /history/{gameId} */
  getHistory: async (gameId) => {
    const res = await fetch(`${BASE}/history/${gameId}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  /** Open a WebSocket to /ws/{gameId}. Returns the WebSocket instance. */
  connectWebSocket: (gameId, onMessage) => {
    const wsBase = BASE.replace(/^http/, 'ws');
    const ws = new WebSocket(`${wsBase}/ws/${gameId}`);
    ws.onmessage = (event) => {
      try { onMessage(JSON.parse(event.data)); }
      catch (e) { console.error('WS parse error', e); }
    };
    return ws;
  },
};
