/**
 * HUD.js — Heads-Up Display controller.
 * Populates #panel-a1, #panel-a2, #turn-indicator, #action-log with live data.
 */

export class HUD {
  constructor() {
    this._panelA1 = document.getElementById('panel-a1');
    this._panelA2 = document.getElementById('panel-a2');
    this._turnInd = document.getElementById('turn-indicator');
    this._logEl   = document.getElementById('action-log');
    this._speedEl = document.getElementById('speed-controls');
    this._logEntries = [];
    this._buildPanels();
    this._buildLog();
    this._hidden = true;
  }

  // ─── Build ─────────────────────────────────────────────────────────

  _buildPanels() {
    this._panelA1.innerHTML = this._panelHTML(1, 'AGENT α', 'MINIMAX');
    this._panelA2.innerHTML = this._panelHTML(2, 'AGENT β', 'MCTS');
  }

  _panelHTML(id, name, algo) {
    const tag = id === 1 ? 'cyan' : 'red';
    return `
      <div class="agent-name">${name} <span class="algo-tag">${algo}</span></div>
      <div class="stat-row">
        <span>❤</span>
        <div class="bar hp-bar"><div class="fill" id="hp-fill-${id}" style="width:100%"></div></div>
        <span id="hp-text-${id}">20/20</span>
      </div>
      <div class="stat-row">
        <span>⚡</span>
        <div class="bar en-bar"><div class="fill" id="en-fill-${id}" style="width:100%"></div></div>
        <span id="en-text-${id}">10/10</span>
      </div>
      <div class="cooldowns" id="cd-${id}">
        <span class="cd-icon" id="cd-shield-${id}" title="Shield">🛡</span>
        <span class="cd-icon" id="cd-skill-${id}" title="Shockwave">💥</span>
      </div>
      <div class="status-effects" id="status-${id}"></div>
      <div class="ai-stats" id="ai-stats-${id}">—</div>
    `;
  }

  _buildLog() {
    this._logEl.innerHTML = '<div class="log-title">ACTION LOG</div><div id="log-body"></div>';
    this._logBody = document.getElementById('log-body');
  }

  // ─── Show / hide ──────────────────────────────────────────────────

  show() {
    this._hidden = false;
    this._panelA1.classList.add('visible');
    this._panelA2.classList.add('visible');
    this._turnInd.classList.add('visible');
    this._logEl.classList.add('visible');
  }

  hide() {
    this._hidden = true;
    this._panelA1.classList.remove('visible');
    this._panelA2.classList.remove('visible');
    this._turnInd.classList.remove('visible');
    this._logEl.classList.remove('visible');
  }

  showSpeedControls() {
    this._speedEl.classList.add('visible');
  }

  hideSpeedControls() {
    this._speedEl.classList.remove('visible');
  }

  // ─── Update data ──────────────────────────────────────────────────

  /**
   * @param {number} id — 1 or 2
   * @param {{hp:number, max_hp:number, energy:number, max_energy:number,
   *          shield_cooldown:number, skill_cooldown:number,
   *          burn_turns?:number, slow_active?:boolean}} data
   */
  updateAgent(id, data) {
    const hpFrac = data.hp / data.max_hp;
    const enFrac = data.energy / data.max_energy;
    const hpFill = document.getElementById(`hp-fill-${id}`);
    const enFill = document.getElementById(`en-fill-${id}`);
    if (hpFill) hpFill.style.width = `${hpFrac * 100}%`;
    if (enFill) enFill.style.width = `${enFrac * 100}%`;

    const hpText = document.getElementById(`hp-text-${id}`);
    const enText = document.getElementById(`en-text-${id}`);
    if (hpText) hpText.textContent = `${data.hp}/${data.max_hp}`;
    if (enText) enText.textContent = `${data.energy}/${data.max_energy}`;

    // HP bar color
    if (hpFill) {
      if (hpFrac > 0.5) hpFill.style.background = '#00ff44';
      else if (hpFrac > 0.25) hpFill.style.background = '#ddcc00';
      else hpFill.style.background = '#ff2200';
    }

    // Cooldowns
    const shieldCD = document.getElementById(`cd-shield-${id}`);
    const skillCD  = document.getElementById(`cd-skill-${id}`);
    if (shieldCD) {
      shieldCD.classList.toggle('on-cd', data.shield_cooldown > 0);
      const numEl = shieldCD.querySelector('.cd-num');
      if (data.shield_cooldown > 0) {
        if (!numEl) { const s = document.createElement('span'); s.className = 'cd-num'; s.textContent = data.shield_cooldown; shieldCD.appendChild(s); }
        else numEl.textContent = data.shield_cooldown;
      } else if (numEl) numEl.remove();
    }
    if (skillCD) {
      skillCD.classList.toggle('on-cd', data.skill_cooldown > 0);
      const numEl = skillCD.querySelector('.cd-num');
      if (data.skill_cooldown > 0) {
        if (!numEl) { const s = document.createElement('span'); s.className = 'cd-num'; s.textContent = data.skill_cooldown; skillCD.appendChild(s); }
        else numEl.textContent = data.skill_cooldown;
      } else if (numEl) numEl.remove();
    }

    // Status effects
    const statusEl = document.getElementById(`status-${id}`);
    if (statusEl) {
      let html = '';
      if (data.burn_turns > 0) html += `<span class="burn">🔥 BURN (${data.burn_turns})</span>`;
      if (data.slow_active) html += `<span class="slow">❄ SLOW</span>`;
      statusEl.innerHTML = html;
    }
  }

  /**
   * Set AI search stats (optional overlay text).
   */
  setAIStats(id, text) {
    const el = document.getElementById(`ai-stats-${id}`);
    if (el) el.textContent = text;
  }

  /**
   * Update turn indicator.
   * @param {number} turn — game turn number
   * @param {number} currentAgent — 1 or 2
   */
  setTurn(turn, currentAgent) {
    const color = currentAgent === 1 ? 'var(--agent1)' : 'var(--agent2)';
    const name = currentAgent === 1 ? 'AGENT α' : 'AGENT β';
    this._turnInd.innerHTML = `TURN ${turn} &mdash; ${name} <span class="blink-dot" style="background:${color}"></span>`;
  }

  /**
   * Append a log entry.
   */
  addLog(turn, agentId, text) {
    const tag = agentId === 1 ? 'agent-tag-cyan' : 'agent-tag-red';
    const name = agentId === 1 ? 'α' : 'β';
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `<span class="turn-num">T${turn}</span> <span class="${tag}">${name}</span> ${text}`;
    if (this._logBody.firstChild) {
      this._logBody.insertBefore(entry, this._logBody.firstChild);
    } else {
      this._logBody.appendChild(entry);
    }
    // Keep max 12 entries
    while (this._logBody.children.length > 12) {
      this._logBody.removeChild(this._logBody.lastChild);
    }
  }

  clearLog() {
    if (this._logBody) this._logBody.innerHTML = '';
  }
}
