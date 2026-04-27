# Aegis Arena

3D turn-based AI combat simulation with:
- FastAPI backend game engine and API
- Browser frontend rendered with Three.js

## Prerequisites

- Python 3.10+
- PowerShell (Windows) or a shell terminal
- Internet access for frontend CDN assets (Three.js)

## 1) Create and activate virtual environment

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

## 2) Install dependencies

```powershell
pip install -r backend/requirements-dev.txt
```

If you only want to run the app (no tests), this also works:

```powershell
pip install -r backend/requirements.txt
```

## 3) Start backend (Terminal 1)

From the project root:

```powershell
uvicorn backend.server:app --reload --port 8000
```

Backend API URL: http://localhost:8000

## 4) Start frontend file server (Terminal 2)

From the project root:

```powershell
python serve.py
```

Frontend URL: http://localhost:3000

## 5) Open the game

Open http://localhost:3000 in a browser.

## Optional: Run tests

```powershell
python -m pytest backend/test_game.py -v
```

## Troubleshooting

- Error: `ModuleNotFoundError: No module named 'websockets'`
  - Install dependencies again: `pip install -r backend/requirements-dev.txt`
- Frontend loads but no game actions:
  - Confirm backend is running on port 8000.
- Port already in use:
  - Change port in the startup command and update frontend API base in `frontend/game/APIClient.js`.
