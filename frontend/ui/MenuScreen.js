/**
 * MenuScreen.js — Title / mode-selection screen controller.
 */

export class MenuScreen {
  /**
   * @param {(mode:string, humanSide:number|null)=>void} onStart
   *   mode: 'ai_vs_ai' | 'human_vs_ai'
   *   humanSide: 1 | 2 | null
   */
  constructor(onStart) {
    this._onStart = onStart;
    this._el = document.getElementById('menu-screen');
    this._btnAI    = document.getElementById('btn-ai-vs-ai');
    this._btnHuman = document.getElementById('btn-human-vs-ai');
    this._sideSelect = document.getElementById('side-select');
    this._sideA1   = document.getElementById('side-agent1');
    this._sideA2   = document.getElementById('side-agent2');

    this._bind();
  }

  _bind() {
    this._btnAI.addEventListener('click', () => {
      this.hide();
      this._onStart('ai_vs_ai', null);
    });

    this._btnHuman.addEventListener('click', () => {
      this._sideSelect.classList.add('visible');
    });

    this._sideA1.addEventListener('click', () => {
      this.hide();
      this._onStart('human_vs_ai', 1);
    });

    this._sideA2.addEventListener('click', () => {
      this.hide();
      this._onStart('human_vs_ai', 2);
    });
  }

  show() {
    this._el.classList.remove('hidden');
    this._sideSelect.classList.remove('visible');
  }

  hide() {
    this._el.classList.add('hidden');
  }
}
