/**
 * GameController.js — Main game orchestrator.
 *
 * Handles game flow for both AI-vs-AI (WebSocket streaming) and
 * Human-vs-AI (turn-by-turn REST) modes.
 */

import * as THREE from 'three';
import { APIClient } from './APIClient.js';

const MAX_HP = 100;
const MAX_ENERGY = 100;

// ─── Backend ↔ Frontend conversion helpers ────────────────────────

/** Convert backend action string ("MOVE_UP", "BASIC_ATTACK", …) to frontend object. */
function parseAction(actionStr) {
  if (typeof actionStr === 'object') return actionStr;
  const s = String(actionStr).toUpperCase();
  if (s === 'MOVE_UP')          return { type: 'move', direction: 'up' };
  if (s === 'MOVE_DOWN')        return { type: 'move', direction: 'down' };
  if (s === 'MOVE_LEFT')        return { type: 'move', direction: 'left' };
  if (s === 'MOVE_RIGHT')       return { type: 'move', direction: 'right' };
  if (s === 'BASIC_ATTACK')     return { type: 'attack' };
  if (s === 'DEFENSIVE_SHIELD') return { type: 'shield' };
  if (s === 'SPECIAL_SKILL')    return { type: 'skill' };
  return { type: actionStr };
}

/** Convert frontend action object to backend action string. */
function serializeAction(actionObj) {
  if (typeof actionObj === 'string') return actionObj;
  if (actionObj.type === 'move')   return `MOVE_${actionObj.direction.toUpperCase()}`;
  if (actionObj.type === 'attack') return 'BASIC_ATTACK';
  if (actionObj.type === 'shield') return 'DEFENSIVE_SHIELD';
  if (actionObj.type === 'skill')  return 'SPECIAL_SKILL';
  return String(actionObj.type).toUpperCase();
}

/** "agent1" | "agent2" | 1 | 2 → 1 | 2 */
function agentNum(tag) {
  if (tag === 'agent1' || tag === 1) return 1;
  if (tag === 'agent2' || tag === 2) return 2;
  return null;
}

/** 1 | 2 | "agent1" | "agent2" → "agent1" | "agent2" */
function agentTag(v) {
  if (v === 1 || v === 'agent1') return 'agent1';
  if (v === 2 || v === 'agent2') return 'agent2';
  return null;
}

export class GameController {
  /**
   * @param {object} deps — injected subsystems.
   * @param {import('../scene/ArenaScene.js').ArenaScene} deps.arena
   * @param {import('../scene/Lighting.js').Lighting} deps.lighting
   * @param {import('../scene/AgentMesh.js').AgentMesh} deps.agent1
   * @param {import('../scene/AgentMesh.js').AgentMesh} deps.agent2
   * @param {import('../scene/CameraRig.js').CameraRig} deps.cameraRig
   * @param {import('../scene/Effects.js').Effects} deps.effects
   * @param {import('../ui/HUD.js').HUD} deps.hud
   * @param {import('../ui/ActionPanel.js').ActionPanel} deps.actionPanel
   */
  constructor(deps) {
    this.arena = deps.arena;
    this.lighting = deps.lighting;
    this.agent1 = deps.agent1;
    this.agent2 = deps.agent2;
    this.cameraRig = deps.cameraRig;
    this.effects = deps.effects;
    this.hud = deps.hud;
    this.actionPanel = deps.actionPanel;

    this.gameId = null;
    this.mode = null;      // 'ai_vs_ai' | 'human_vs_ai'
    this.humanSide = null; // 1 | 2 | null
    this.ws = null;
    this._prevState = null;
    this._speed = 800;
    this._animating = false;
    this._turnQueue = [];

    // Speed control buttons
    const speedBtns = document.querySelectorAll('#speed-controls button');
    speedBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        speedBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this._speed = parseInt(btn.dataset.speed, 10);
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify({ type: 'set_speed', speed_ms: this._speed }));
        }
      });
    });

    // Play-again
    document.getElementById('play-again-btn').addEventListener('click', () => {
      document.getElementById('game-over').classList.remove('visible');
      this._cleanup();
      // Signal to main to show menu
      if (this._onReturnToMenu) this._onReturnToMenu();
    });
  }

  /** Register a callback for returning to menu. */
  onReturnToMenu(fn) { this._onReturnToMenu = fn; }

  // ───────────────────────────────────────────────────────────────────
  // Start game
  // ───────────────────────────────────────────────────────────────────

  async startGame(mode, humanSide) {
    this.mode = mode;
    this.humanSide = humanSide ? agentTag(humanSide) : null;
    this._prevState = null;
    this._turnQueue = [];

    const data = await APIClient.newGame(mode, this.humanSide);
    this.gameId = data.game_id;
    const state = data.state;

    // Build arena (rebuild each game for random layouts)
    this.arena.rebuild(state.grid, state.elevated_tiles);

    // Position agents
    const pos1 = this.arena.gridToWorld(state.agent1.position);
    const pos2 = this.arena.gridToWorld(state.agent2.position);
    this.agent1.setPosition(pos1);
    this.agent2.setPosition(pos2);
    this.agent1.show();
    this.agent2.show();

    // HUD
    this.hud.show();
    this.hud.clearLog();
    this._applyHUD(state);

    if (mode === 'ai_vs_ai') {
      this.hud.showSpeedControls();
      this._startAIvsAI();
    } else {
      this.hud.hideSpeedControls();
      this._handleHumanVsAI(state);
    }
  }

  // ───────────────────────────────────────────────────────────────────
  // AI vs AI — WebSocket streaming
  // ───────────────────────────────────────────────────────────────────

  _startAIvsAI() {
    this.ws = APIClient.connectWebSocket(this.gameId, (msg) => {
      if (msg.type === 'move') {
        this._turnQueue.push(msg);
        this._processQueue();
      } else if (msg.type === 'game_over') {
        this._turnQueue.push(msg);
        this._processQueue();
      }
    });
  }

  async _processQueue() {
    if (this._animating || this._turnQueue.length === 0) return;
    this._animating = true;

    const msg = this._turnQueue.shift();

    if (msg.type === 'move') {
      await this._applyTurn(msg.action, msg.state, msg.agent);
    } else if (msg.type === 'game_over') {
      if (msg.state) this._applyHUD(msg.state);
      this._showGameOver(msg.winner);
    }

    this._animating = false;
    // Process next in queue
    if (this._turnQueue.length > 0) {
      setTimeout(() => this._processQueue(), 50);
    }
  }

  // ───────────────────────────────────────────────────────────────────
  // Human vs AI — REST turn-by-turn
  // ───────────────────────────────────────────────────────────────────

  async _handleHumanVsAI(state) {
    if (state.is_terminal) {
      this._showGameOver(state.winner);
      return;
    }

    const isHumanTurn = state.turn === this.humanSide;

    if (isHumanTurn) {
      // Show action panel with valid actions
      const validData = await APIClient.getValidActions(this.gameId);
      this.actionPanel.setValidActions(validData.actions.map(a => parseAction(a)));
      this.actionPanel.show();
    } else {
      this.actionPanel.hide();
      // Request AI move
      const result = await APIClient.getAIMove(this.gameId);
      await this._applyTurn(result.action, result.state, state.turn);
      this._handleHumanVsAI(result.state);
    }
  }

  /**
   * Called by ActionPanel when human picks an action.
   */
  async handleHumanAction(action) {
    this.actionPanel.hide();
    const actionStr = serializeAction(action);
    const result = await APIClient.submitAction(this.gameId, actionStr);
    await this._applyTurn(action, result.state, this.humanSide);
    this._handleHumanVsAI(result.state);
  }

  // ───────────────────────────────────────────────────────────────────
  // Apply turn — animate and update scene
  // ───────────────────────────────────────────────────────────────────

  async _applyTurn(action, state, agentId) {
    const prevState = this._prevState;
    this._prevState = state;

    // Normalize action & agent id
    const parsed   = parseAction(action);
    const actorNum = agentNum(agentId);

    // Who acted?
    const actor   = actorNum === 1 ? this.agent1 : this.agent2;
    const target  = actorNum === 1 ? this.agent2 : this.agent1;
    const agentState = actorNum === 1 ? state.agent1 : state.agent2;
    const targetState = actorNum === 1 ? state.agent2 : state.agent1;

    // Move agent mesh
    const newPos = this.arena.gridToWorld(agentState.position);
    actor.moveTo(newPos);

    // Face direction of action
    if (parsed.type === 'attack' || parsed.type === 'skill') {
      const targetPos = this.arena.gridToWorld(targetState.position);
      actor.lookAt(targetPos);
    }

    // Visual effects
    if (parsed.type === 'attack') {
      const from = actor.group.position.clone();
      from.y += 0.5;
      const to = target.group.position.clone();
      to.y += 0.5;
      const color = actorNum === 1 ? 0x00d4ff : 0xff3333;
      this.effects.projectile(from, to, color, () => {
        // Damage number
        const dmg = this._calcDamage(prevState, state, actorNum);
        if (dmg > 0) {
          this.effects.damageNumber(to, `-${dmg}`, 'damage-label red');
          target.applyHitReaction(new THREE.Vector3().subVectors(to, from));
        }
      });
      this.cameraRig.triggerActionCam(to, 0.8);
    } else if (parsed.type === 'skill') {
      const center = actor.group.position.clone();
      center.y += 0.3;
      const color = actorNum === 1 ? 0x00d4ff : 0xff3333;
      this.effects.shockwave(center, color, this.cameraRig);
      const dmg = this._calcDamage(prevState, state, actorNum);
      if (dmg > 0) {
        const tPos = target.group.position.clone();
        tPos.y += 0.5;
        this.effects.damageNumber(tPos, `-${dmg}`, 'damage-label red');
        target.applyHitReaction(new THREE.Vector3().subVectors(tPos, center));
      }
    } else if (parsed.type === 'shield') {
      actor.setShield(true);
      const center = actor.group.position.clone();
      center.y += 0.5;
      const color = actorNum === 1 ? 0x00d4ff : 0xff3333;
      this.effects.shieldPulse(center, color);
    } else if (parsed.type === 'move') {
      // Slow visual if agent is slowed
      if (agentState.slow_active) {
        this.effects.slowVisual(newPos);
      }
    }

    // Shield: deactivate if agent's shield is off
    if (!agentState.shield_active) {
      actor.setShield(false);
    }

    // Burn visual
    if (agentState.burn_turns > 0) {
      this.effects.burnVisual(actor.group, 1.5);
    }

    // Target burn visual
    if (targetState.burn_turns > 0) {
      this.effects.burnVisual(target.group, 1.5);
    }

    // Update target mesh position (in case of knockback)
    const tNewPos = this.arena.gridToWorld(targetState.position);
    target.moveTo(tNewPos);

    // Update HP/Energy bars
    actor.setHP(agentState.hp / MAX_HP);
    actor.setEnergy(agentState.energy / MAX_ENERGY);
    target.setHP(targetState.hp / MAX_HP);
    target.setEnergy(targetState.energy / MAX_ENERGY);

    // Update lighting
    this.lighting.updateAgentPositions(
      this.arena.gridToWorld(state.agent1.position),
      this.arena.gridToWorld(state.agent2.position),
    );

    // Update grid (cover destroyed, traps triggered, etc.)
    this.arena.updateGrid(state.grid);

    // Update HUD
    this._applyHUD(state);

    // Log
    const actionText = this._actionText(parsed);
    this.hud.addLog(state.turn_count, actorNum, actionText);

    // AI stats
    if (state.agent_stats) {
      if (state.agent_stats.agent1 && Object.keys(state.agent_stats.agent1).length) {
        const s = state.agent_stats.agent1;
        this.hud.setAIStats(1, this._formatStats(s));
      }
      if (state.agent_stats.agent2 && Object.keys(state.agent_stats.agent2).length) {
        const s = state.agent_stats.agent2;
        this.hud.setAIStats(2, this._formatStats(s));
      }
    }

    // Death
    if (state.agent1.hp <= 0) {
      this.effects.deathEffect(this.agent1.group.position.clone(), 0x00d4ff);
      this.agent1.hide();
    }
    if (state.agent2.hp <= 0) {
      this.effects.deathEffect(this.agent2.group.position.clone(), 0xff3333);
      this.agent2.hide();
    }

    // Wait for animation
    await this._wait(this._speed * 0.5);
  }

  // ─── Helpers ───────────────────────────────────────────────────────

  _calcDamage(prevState, newState, attackerId) {
    if (!prevState) return 0;
    const targetKey = attackerId === 1 ? 'agent2' : 'agent1';
    const prev = prevState[targetKey]?.hp ?? 0;
    const curr = newState[targetKey]?.hp ?? 0;
    return Math.max(0, prev - curr);
  }

  _applyHUD(state) {
    this.hud.updateAgent(1, {
      hp: state.agent1.hp, max_hp: MAX_HP,
      energy: state.agent1.energy, max_energy: MAX_ENERGY,
      shield_cooldown: state.agent1.shield_cooldown,
      skill_cooldown: state.agent1.skill_cooldown,
      burn_turns: state.agent1.burn_turns,
      slow_active: state.agent1.slow_active,
    });
    this.hud.updateAgent(2, {
      hp: state.agent2.hp, max_hp: MAX_HP,
      energy: state.agent2.energy, max_energy: MAX_ENERGY,
      shield_cooldown: state.agent2.shield_cooldown,
      skill_cooldown: state.agent2.skill_cooldown,
      burn_turns: state.agent2.burn_turns,
      slow_active: state.agent2.slow_active,
    });
    this.hud.setTurn(state.turn_count, state.turn);
  }

  _actionText(action) {
    if (action.type === 'move') return `MOVE ${action.direction.toUpperCase()}`;
    if (action.type === 'attack') return 'ATTACK';
    if (action.type === 'shield') return 'SHIELD';
    if (action.type === 'skill') return 'SHOCKWAVE';
    return action.type.toUpperCase();
  }

  _formatStats(s) {
    if (s.search_depth_reached !== undefined) {
      return `Depth ${s.search_depth_reached} · ${s.nodes_evaluated} nodes · ${Math.round(s.time_ms)}ms`;
    }
    if (s.iterations !== undefined) {
      return `${s.iterations} iter · ${s.simulations} sims · ${Math.round(s.time_ms)}ms`;
    }
    return '—';
  }

  _showGameOver(winner) {
    this.hud.hide();
    this.actionPanel.hide();
    const winnerText = document.getElementById('winner-text');
    const finalStats = document.getElementById('final-stats');
    const overlay = document.getElementById('game-over');

    const w = agentNum(winner);
    if (w === 1) {
      winnerText.textContent = 'AGENT α WINS';
      winnerText.style.color = 'var(--agent1)';
    } else if (w === 2) {
      winnerText.textContent = 'AGENT β WINS';
      winnerText.style.color = 'var(--agent2)';
    } else {
      winnerText.textContent = 'DRAW';
      winnerText.style.color = 'var(--accent)';
    }

    finalStats.textContent = `Turn ${this._prevState?.turn_count || '?'}`;
    overlay.classList.add('visible');
  }

  _cleanup() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.gameId = null;
    this._prevState = null;
    this._turnQueue = [];
    this._animating = false;
  }

  _wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
