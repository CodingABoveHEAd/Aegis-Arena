/**
 * MenuScreen.js — Title / mode-selection screen controller.
 */

const API_BASE = 'http://localhost:8000';

export class MenuScreen {
  /**
   * @param {(mode:string, humanSide:number|null, algorithms:object)=>void} onStart
   *   mode: 'ai_vs_ai' | 'human_vs_ai'
   *   humanSide: 1 | 2 | null
   *   algorithms: { agent1_algorithm, agent2_algorithm }
   */
  constructor(onStart) {
    this._onStart = onStart;
    this._el = document.getElementById('menu-screen');
    this._btnAI    = document.getElementById('btn-ai-vs-ai');
    this._btnHuman = document.getElementById('btn-human-vs-ai');
    this._sideSelect = document.getElementById('side-select');
    this._sideA1   = document.getElementById('side-agent1');
    this._sideA2   = document.getElementById('side-agent2');
    this._algoSelect = document.getElementById('algo-select');
    this._algoBtns = document.getElementById('algo-btns');

    this._selectedAlgo = 'negamax';  // default
    this._algorithms = [];

    this._bind();
    this._fetchAlgorithms();
  }

  async _fetchAlgorithms() {
    try {
      const res = await fetch(`${API_BASE}/available_algorithms`);
      if (!res.ok) return;
      const data = await res.json();
      this._algorithms = data.algorithms || [];
      this._selectedAlgo = (data.defaults && data.defaults.agent2) || 'negamax';
      this._buildAlgoButtons();
    } catch (_) {
      // Server not yet running — will use defaults
    }
  }

  _buildAlgoButtons() {
    this._algoBtns.innerHTML = '';
    for (const algo of this._algorithms) {
      const btn = document.createElement('button');
      btn.className = 'algo-btn' + (algo === this._selectedAlgo ? ' selected' : '');
      btn.textContent = algo.toUpperCase();
      btn.addEventListener('click', () => {
        this._selectedAlgo = algo;
        this._algoBtns.querySelectorAll('.algo-btn').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
      });
      this._algoBtns.appendChild(btn);
    }
  }

  _getAlgorithms() {
    return {
      agent1_algorithm: 'minimax',
      agent2_algorithm: this._selectedAlgo,
    };
  }

  _bind() {
    this._btnAI.addEventListener('click', () => {
      this._algoSelect.classList.add('visible');
      this._sideSelect.classList.remove('visible');
      // Add a "Start" confirm after algo selection, or start directly
      // For simplicity: start after a brief display
      // Actually let's add a confirm: click algo button selects, clicking AI vs AI button again starts
      // Better: first click shows algo selector, second click starts
      if (this._algoSelect._ready) {
        this.hide();
        this._onStart('ai_vs_ai', null, this._getAlgorithms());
        this._algoSelect._ready = false;
      } else {
        this._algoSelect._ready = true;
      }
    });

    this._btnHuman.addEventListener('click', () => {
      this._sideSelect.classList.add('visible');
      this._algoSelect.classList.add('visible');
    });

    this._sideA1.addEventListener('click', () => {
      this.hide();
      this._onStart('human_vs_ai', 1, this._getAlgorithms());
    });

    this._sideA2.addEventListener('click', () => {
      this.hide();
      this._onStart('human_vs_ai', 2, this._getAlgorithms());
    });
  }

  show() {
    this._el.classList.remove('hidden');
    this._sideSelect.classList.remove('visible');
    this._algoSelect.classList.remove('visible');
    if (this._algoSelect) this._algoSelect._ready = false;
    this._fetchAlgorithms();  // refresh in case server restarted
  }

  hide() {
    this._el.classList.add('hidden');
  }
}
