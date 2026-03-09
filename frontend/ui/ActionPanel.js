/**
 * ActionPanel.js — Human player action controls (D-pad + action buttons).
 */

// Direction map: D-pad button data-dir → backend action
const DIR_MAP = {
  'up':    { type: 'move', direction: 'up' },
  'down':  { type: 'move', direction: 'down' },
  'left':  { type: 'move', direction: 'left' },
  'right': { type: 'move', direction: 'right' },
};

export class ActionPanel {
  /**
   * @param {(action:object)=>void} onAction — callback when human picks an action.
   */
  constructor(onAction) {
    this._onAction = onAction;
    this._panel = document.getElementById('action-panel');
    this._validActions = [];
    this._build();
  }

  // ─── Build ─────────────────────────────────────────────────────────

  _build() {
    this._panel.innerHTML = `
      <div class="dpad">
        <div class="empty-cell"></div>
        <button data-dir="up">▲</button>
        <div class="empty-cell"></div>
        <button data-dir="left">◄</button>
        <div class="empty-cell"></div>
        <button data-dir="right">►</button>
        <div class="empty-cell"></div>
        <button data-dir="down">▼</button>
        <div class="empty-cell"></div>
      </div>
      <div class="action-buttons">
        <button data-action="attack">⚔ ATTACK</button>
        <button data-action="shield">🛡 SHIELD</button>
        <button data-action="skill">💥 SHOCKWAVE</button>
      </div>
    `;

    // D-pad listeners
    for (const btn of this._panel.querySelectorAll('.dpad button')) {
      btn.addEventListener('click', () => {
        const dir = btn.dataset.dir;
        const action = DIR_MAP[dir];
        if (action && this._isValid(action)) this._onAction(action);
      });
    }

    // Action button listeners
    for (const btn of this._panel.querySelectorAll('.action-buttons button')) {
      btn.addEventListener('click', () => {
        const type = btn.dataset.action;
        const action = { type };
        if (this._isValid(action)) this._onAction(action);
      });
    }
  }

  // ─── API ───────────────────────────────────────────────────────────

  /** Show the panel (slide in). */
  show() { this._panel.classList.add('visible'); }

  /** Hide the panel (slide out). */
  hide() { this._panel.classList.remove('visible'); }

  /**
   * Set currently valid actions and enable/disable buttons accordingly.
   * @param {object[]} actions — list of valid action objects from backend.
   */
  setValidActions(actions) {
    this._validActions = actions;

    // D-pad
    for (const btn of this._panel.querySelectorAll('.dpad button')) {
      const dir = btn.dataset.dir;
      const match = actions.some(a => a.type === 'move' && a.direction === dir);
      btn.disabled = !match;
    }

    // Action buttons
    for (const btn of this._panel.querySelectorAll('.action-buttons button')) {
      const type = btn.dataset.action;
      const match = actions.some(a => a.type === type);
      btn.disabled = !match;
    }
  }

  _isValid(action) {
    return this._validActions.some(a => {
      if (a.type !== action.type) return false;
      if (action.direction && a.direction !== action.direction) return false;
      return true;
    });
  }
}
