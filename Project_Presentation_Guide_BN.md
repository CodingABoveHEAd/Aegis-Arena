# Aegis Arena: পূর্ণ প্রেজেন্টেশন গাইড (বাংলা)

এই ডকুমেন্টটি আপনার প্রেজেন্টেশনের জন্য তৈরি করা হয়েছে। এখানে প্রজেক্টের কাজের ধরণ, ফাইলভিত্তিক দায়িত্ব, ব্যবহৃত অ্যালগরিদম, AI এজেন্টের সিদ্ধান্ত প্রক্রিয়া, API ফ্লো, এবং সম্ভাব্য শিক্ষকের প্রশ্নের প্রস্তুত উত্তর দেওয়া আছে।

---

## 1) প্রজেক্ট ওভারভিউ

Aegis Arena একটি turn-based 1v1 tactical AI combat simulation।

- ব্যাকএন্ড: Python + FastAPI
- ফ্রন্টএন্ড: Three.js (ব্রাউজার-ভিত্তিক 3D ভিজ্যুয়াল)
- গেম মোড:
1. AI vs AI
2. Human vs AI

মূল ধারণা:
- 8x8 grid arena
- দুই এজেন্ট পালাক্রমে action নেয়
- tile mechanics (COVER, ENERGY, TRAP, ELEVATED, HEAL)
- action set: move / basic attack / defensive shield / special skill
- AI সিদ্ধান্ত: Minimax, Negamax, MCTS

---

## 2) হাই-লেভেল আর্কিটেকচার

### Backend Engine
- গেম রুলস, state transition, action validation, heuristic, AI search
- REST API + WebSocket streaming

### Frontend Renderer
- 3D arena, agents, VFX, HUD, action panel, menu
- Backend থেকে state নিয়ে animation + UI আপডেট

### Data Flow
1. Frontend নতুন গেম তৈরি করে (`POST /new_game`)
2. Backend initial state রিটার্ন করে
3. Human vs AI হলে turn-by-turn REST call
4. AI vs AI হলে WebSocket দিয়ে move stream আসে
5. Frontend প্রতিটি move animate করে HUD/log আপডেট করে

---

## 3) কিভাবে প্রজেক্ট রান হয়

রান নির্দেশনা আগেই দেয়া হয়েছে, আবার সংক্ষেপে:

1. venv activate
2. `pip install -r backend/requirements-dev.txt`
3. backend চালু: `uvicorn backend.server:app --reload --port 8000`
4. frontend চালু: `python serve.py`
5. browser: `http://localhost:3000`

রেফারেন্স:
- [README.md](README.md)
- [commands.txt](commands.txt)
- [serve.py](serve.py)

---

## 4) ফাইলভিত্তিক দায়িত্ব (What file does what)

## 4.1 Root
- [serve.py](serve.py): frontend static server (no-cache header সহ)
- [commands.txt](commands.txt): setup/run/test command cheat sheet
- [Aegis_Arena_3D_Implementation_Plan.md](Aegis_Arena_3D_Implementation_Plan.md): implementation plan

## 4.2 Backend Core
- [backend/server.py](backend/server.py): FastAPI app, endpoints, game session store, WebSocket stream
- [backend/requirements.txt](backend/requirements.txt): runtime dependencies
- [backend/requirements-dev.txt](backend/requirements-dev.txt): test/dev dependencies
- [backend/test_game.py](backend/test_game.py): gameplay + AI behavior validation tests

## 4.3 Game Rules Module
- [backend/game/arena.py](backend/game/arena.py): grid generation, tile types, trap timer, cover durability, tile serialization
- [backend/game/agent.py](backend/game/agent.py): HP/energy/shield/cooldown/burn/slow state and per-turn tick
- [backend/game/state.py](backend/game/state.py): hashable game snapshot, terminal/winner logic, clone
- [backend/game/actions.py](backend/game/actions.py): valid action calculation + immutable state transition

## 4.4 AI Module
- [backend/ai/agent_factory.py](backend/ai/agent_factory.py): algorithm registry + agent creation
- [backend/ai/heuristic.py](backend/ai/heuristic.py): weighted evaluation function
- [backend/ai/cache.py](backend/ai/cache.py): transposition table (EXACT/LOWER/UPPER)
- [backend/ai/minimax.py](backend/ai/minimax.py): minimax + alpha-beta + iterative deepening + TT
- [backend/ai/negamax.py](backend/ai/negamax.py): negamax + alpha-beta + killer heuristic + TT
- [backend/ai/mcts.py](backend/ai/mcts.py): MCTS + PUCT + heavy rollout + progressive widening

## 4.5 Frontend Entry & Control
- [frontend/index.html](frontend/index.html): layout, CSS, importmap, root containers
- [frontend/main.js](frontend/main.js): Three.js bootstrap + subsystem wiring + render loop
- [frontend/game/APIClient.js](frontend/game/APIClient.js): REST + WS client
- [frontend/game/GameController.js](frontend/game/GameController.js): orchestrator (state apply, animation sequencing, HUD sync)

## 4.6 Frontend Scene
- [frontend/scene/ArenaScene.js](frontend/scene/ArenaScene.js): tile mesh/decor + grid rebuild/update
- [frontend/scene/AgentMesh.js](frontend/scene/AgentMesh.js): agent model, bars, shield, reactions
- [frontend/scene/Lighting.js](frontend/scene/Lighting.js): environment + agent-follow lights
- [frontend/scene/CameraRig.js](frontend/scene/CameraRig.js): overview/action cam, proximity zoom, shake
- [frontend/scene/Effects.js](frontend/scene/Effects.js): projectile, shockwave, heal, burn, slow, death effects

## 4.7 Frontend UI
- [frontend/ui/MenuScreen.js](frontend/ui/MenuScreen.js): mode + side + algorithm selector
- [frontend/ui/HUD.js](frontend/ui/HUD.js): HP/energy/cooldown/status/action log/turn indicator
- [frontend/ui/ActionPanel.js](frontend/ui/ActionPanel.js): human action input panel

---

## 5) গেম রুলস ও মেকানিক্স

### 5.1 Tile Types
[backend/game/arena.py](backend/game/arena.py) অনুযায়ী:

- EMPTY: neutral
- COVER: incoming damage কমায় (damage reduction)
- ENERGY: energy restore
- TRAP: step করলে damage, তারপর cooldown শেষে respawn
- ELEVATED: attacker damage multiplier (high-ground advantage)
- HEAL: একবার ব্যবহারযোগ্য heal

### 5.2 Agent Action Set
[backend/game/actions.py](backend/game/actions.py):

- MOVE_UP / DOWN / LEFT / RIGHT
- BASIC_ATTACK
- DEFENSIVE_SHIELD
- SPECIAL_SKILL

### 5.3 Turn Processing
`apply_action` immutable patternে কাজ করে:
1. state clone
2. action resolve
3. acting agent tick (cooldown, shield duration, tile effects)
4. current agent switch
5. turn increment

এতে AI search tree branch side-effect-free থাকে।

### 5.4 Win/Terminal
[backend/game/state.py](backend/game/state.py):
- HP <= 0 হলে defeat
- max turn exceeded হলে HP comparison
- draw edge-case handle আছে

---

## 6) AI অ্যালগরিদম কী কী, কেন ব্যবহার করা হয়েছে

## 6.1 Minimax
রেফারেন্স: [backend/ai/minimax.py](backend/ai/minimax.py)

ধারণা:
- দুই-পক্ষ optimal play ধরেই search
- maximizing/minimizing alternate

প্রজেক্টে optimization:
- Alpha-Beta pruning
- Iterative deepening (time budget-এর মধ্যে depth বাড়ানো)
- Transposition Table cache
- move ordering

কাজ:
- deterministic tactical play
- সীমিত সময়েও legal best-known move রিটার্ন

## 6.2 Negamax
রেফারেন্স: [backend/ai/negamax.py](backend/ai/negamax.py)

ধারণা:
- Minimax-এর zero-sum reformulation
- same logic with simpler recursion: score = -childScore

optimization:
- Alpha-Beta
- TT with EXACT/LOWER/UPPER bounds
- Killer heuristic
- Iterative deepening

কেন গুরুত্বপূর্ণ:
- cleaner implementation
- strong pruning + speed
- deep tactical lookahead

## 6.3 MCTS
রেফারেন্স: [backend/ai/mcts.py](backend/ai/mcts.py)

ধারণা:
- simulation-based search
- explore/exploit balance

প্রজেক্টের কনফিগ:
- PUCT selection
- Heavy rollout (epsilon-greedy + heuristic guided)
- Progressive widening
- Loop penalty in rollout
- visit-count ভিত্তিক final action selection

কাজ:
- uncertainty-heavy or broader action-space এ robust behavior
- heuristic + stochastic mix

---

## 7) Heuristic কীভাবে কাজ করে

রেফারেন্স: [backend/ai/heuristic.py](backend/ai/heuristic.py)

Weighted components:
- HP advantage
- Energy advantage
- Tile value (cover/elevated/heal/trap)
- Distance control (lead/lag অনুযায়ী aggressive বা defensive spacing)
- Elevation control
- Burn penalty
- Skill/Shield readiness
- Threat awareness
- Beneficial tile proximity

অর্থাৎ heuristic শুধু damage দেখে না; position, resource, tempo, survivability সব বিবেচনা করে।

---

## 8) AI Agent কীভাবে কাজ করে (Decision Lifecycle)

### প্রতি turn এ generic flow
1. valid actions বের করে
2. algorithm দিয়ে action evaluate/select করে
3. state transition apply করে
4. stats collect করে frontend-এ পাঠায়

### Backend থেকে stats উদাহরণ
[backend/server.py](backend/server.py) ও [frontend/game/GameController.js](frontend/game/GameController.js):
- nodes evaluated
- search depth reached
- cache hit rate
- iterations/simulations
- time ms

এগুলো presentation-এ explainable AI evidence হিসেবে ব্যবহার করতে পারবেন।

---

## 9) API ও রিয়েলটাইম ফ্লো

রেফারেন্স: [backend/server.py](backend/server.py), [frontend/game/APIClient.js](frontend/game/APIClient.js)

### REST Endpoints
- `POST /new_game`
- `GET /valid_actions/{game_id}`
- `POST /action/{game_id}`
- `GET /ai_move/{game_id}`
- `GET /history/{game_id}`
- `GET /available_algorithms`

### WebSocket
- `WS /ws/{game_id}`
- AI vs AI mode-এ move-by-move stream
- speed control message support

---

## 10) Frontend কিভাবে state visualize করে

মূল orchestration:
- [frontend/main.js](frontend/main.js): সব subsystem create/wire
- [frontend/game/GameController.js](frontend/game/GameController.js): backend state -> animation/UI updates

ভিজ্যুয়াল স্তর:
- Arena mesh update: [frontend/scene/ArenaScene.js](frontend/scene/ArenaScene.js)
- Agent movement/reaction: [frontend/scene/AgentMesh.js](frontend/scene/AgentMesh.js)
- Combat/heal/status VFX: [frontend/scene/Effects.js](frontend/scene/Effects.js)
- Turn + bars + cooldown + logs: [frontend/ui/HUD.js](frontend/ui/HUD.js)

---

## 11) প্রেজেন্টেশন ডেমো স্ক্রিপ্ট (৩-৫ মিনিট)

1. Project intro
2. Architecture diagram-like explanation (backend rules + frontend rendering)
3. Tile mechanics demo (trap/heal/elevated)
4. AI vs AI: minimax vs negamax
5. Algorithm change করে mcts দেখানো
6. HUD stats explain (depth, nodes, ms)
7. Human vs AI mode briefly
8. Test mention and closing

---

## 12) সম্ভাব্য শিক্ষক প্রশ্ন ও প্রতিরক্ষামূলক উত্তর (Q&A)

### Q1) কেন Minimax, Negamax, MCTS তিনটিই রেখেছেন?
উত্তর:
- comparative AI behavior দেখাতে
- deterministic adversarial search (minimax/negamax) এবং simulation-based search (mcts) দুটো ধারাই কভার হয়
- educational + performance benchmarking value বাড়ে

### Q2) Minimax আর Negamax তো প্রায় একই, আলাদা করে লাভ কী?
উত্তর:
- তাত্ত্বিকভাবে সমমান, কিন্তু implementation ও optimization perspective ভিন্ন
- Negamax code path ছোট হওয়ায় maintenance সহজ
- killer heuristic ও bound-based TT integration practical performance বাড়ায়

### Q3) Alpha-Beta pruning না থাকলে কী সমস্যা?
উত্তর:
- branching factor বেশি হলে search explode করে
- alpha-beta large অংশ prune করে, তাই একই সময়ে বেশি depth যায়

### Q4) কেন Iterative Deepening?
উত্তর:
- সময় শেষ হলেও last completed depth থেকে legal best move পাওয়া যায়
- real-time responsiveness বজায় থাকে

### Q5) Heuristic কি biased?
উত্তর:
- heuristic weighted approximation, তাই perfect নয়
- তবে HP, resource, terrain, threat, status effect মিলিয়ে multi-factor হওয়ায় robust
- test suite দিয়ে behavior validate করা হয়েছে

### Q6) MCTS-এ random থাকলে result unstable হবে না?
উত্তর:
- pure random নয়, heavy rollout heuristic-guided
- progressive widening + PUCT দিয়ে exploration নিয়ন্ত্রিত
- iterations বাড়ালে policy আরও stable হয়

### Q7) State mutation bug কীভাবে এড়িয়েছেন?
উত্তর:
- `apply_action` immutable transition follow করে
- clone-based successor তৈরি হওয়ায় search branch contamination কমে

### Q8) Frontend আর backend sync কীভাবে maintain হয়?
উত্তর:
- backend single source of truth
- frontend শুধু returned state অনুযায়ী render করে
- প্রতি turn-এ full canonical state update হয়

### Q9) Game fairness কীভাবে নিশ্চিত?
উত্তর:
- arena symmetric generation
- spawn-safe zone rules
- mirrored tile placement

### Q10) কেন WebSocket প্রয়োজন ছিল?
উত্তর:
- AI vs AI continuous streaming-এর জন্য low-latency push দরকার
- polling-based REST-এর চেয়ে smoother animation cadence পাওয়া যায়

### Q11) টেস্টে কী কী validate হয়?
উত্তর:
- heal tile placement/mechanics
- heuristic behavior
- MCTS validity/progressive widening
- Negamax tactical decisions/depth scaling
- comparative competitiveness tests

### Q12) Limitations কী?
উত্তর:
- এখনও learning-based policy (RL) নেই
- match replay analytics basic
- persistent DB session নেই (in-memory)

### Q13) Future scope কী?
উত্তর:
- Elo-based AI benchmarking
- replay export + explainability dashboard
- tournament mode + batch simulations
- RL agent integration

### Q14) শিক্ষক যদি বলেন “এটা শুধু game না, AI contribution কোথায়?”
উত্তর:
- multi-algorithm adversarial decision engine
- heuristic engineering + search optimization
- transposition caching, killer heuristic, PUCT tuning
- explainable runtime metrics (depth/nodes/time/hit-rate)

---

## 13) খুব ছোট viva pitch (৩০-৪৫ সেকেন্ড)

Aegis Arena একটি turn-based adversarial AI platform, যেখানে একই গেম environment-এ Minimax, Negamax, এবং MCTS এজেন্টকে চালিয়ে তুলনামূলক decision quality দেখা যায়। Backend immutable game-state engine দিয়ে rule correctness বজায় রাখে, আর frontend real-time 3D visualization দিয়ে প্রতিটি সিদ্ধান্তের effect দেখায়। আমাদের ফোকাস শুধু game তৈরি না, বরং search optimization, heuristic design, এবং explainable AI metrics প্রদর্শন।

---

## 14) Presentation Checklist

- backend server চালু আছে
- frontend 3000 port এ চলছে
- AI vs AI demo ready
- Human vs AI quick run ready
- algorithms switch দেখানো হবে
- HUD stats explain করতে প্রস্তুত
- Q&A section থেকে 5-6টি core answer মুখস্থ

---

যদি চান, আমি এই ডকুমেন্টের আরও একটি “সংক্ষিপ্ত ১-পেজ সংস্করণ”ও বানিয়ে দিতে পারি, যেটা presentation slide speaker notes হিসেবে ব্যবহার করা সহজ হবে।