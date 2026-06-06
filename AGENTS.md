# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project

**Pepper Medical Assistance Robot** — AAST graduation project turning a SoftBank Pepper humanoid into a hospital receptionist for Andalusia Hospital. Bilingual (Arabic/English), voice + touch, runs fully local on a LAN between a Windows laptop and the robot.

## Runtime Layout — Dual-Python Architecture

This repo is **two Python runtimes running side-by-side**; every change needs to consider which side it lives on.

- **Python 3 (laptop-side)**: Flask backend, Whisper STT, Codex/Ollama LLM, FAISS RAG, SQLite, WebSocket bridge. Lives under `Pepper-Controller-main-2/pepper_ui/server/` and `Pepper-Controller-main-2/pepper_voice/ws_bridge.py`.
- **Python 2.7 + NAOqi SDK (robot-side)**: Everything that touches the robot hardware — mic capture, TTS, camera stream, tablet loader, navigation. Lives under `Pepper-Controller-main-2/pepper_voice/MainVoice.py`, `Pepper-Controller-main-2/pepper_ui/robot/`, and `Pepper-Controller-main-2/navigation/`. Requires NAOqi 2.8 SDK at `C:\pynaoqi\pynaoqi-python2.7-2.8.6.23-win64-vs2015-20191127_152649` (hard-coded path in `main.py`).

`main.py` is the master launcher — it spawns each subsystem as a `subprocess.Popen` in the correct Python runtime, injects config via env vars, opens Windows firewall ports, and tears everything down on Ctrl+C. **Tablet script is one-shot and must finish before `nav_bridge` starts** — concurrent NAOqi sessions cause "Session closed" errors (see `main.py:232-236`).

## How The Pieces Talk

- **Tablet UI → Flask backend**: HTTP (tablet browser points at `http://<SERVER_IP>:<SERVER_PORT>`).
- **Flask backend ↔ Robot scripts**: WebSocket relay at `ws_bridge.py` (port 8765). It's a dumb broadcast relay — every message from one client goes to all others. Both Python 2 (NAOqi) and Python 3 clients connect here.
- **Voice flow**: Python 3 drops a `voice_start.flag` file → `MainVoice.py` (Py2) picks it up, records via Pepper's mic, transfers audio via PSCP/SCP to the laptop, POSTs to Flask `/voice`, Flask runs Whisper STT → LLM → returns TTS text which MainVoice speaks via NAOqi.
- **Camera**: `camera_server.py` (Py2) runs its own HTTP server on port 8082 with MJPEG snapshots; Flask proxies them via `/api/camera`.

## LLM Abstraction

`app.py` has a unified `call_llm()` (around line 1513) that routes to either Codex API (online) or Ollama (offline) based on `OFFLINE_MODE` env var. Both paths use the **same agentic tool-calling loop** — tools are defined once and work for both providers. When adding a new AI feature or tool, implement it once in this loop, don't branch.

- Online: Anthropic Codex (`Codex-haiku-4-5-20251001`), needs `CLAUDE_API_KEY` / `ANTHROPIC_API_KEY` in `.env`.
- Offline: Ollama with `qwen2.5:7b` (native tool calling). Start with `ollama serve` before running.

## Common Commands

```bash
# Install Py3 deps (activate venv first)
pip install -r requirements.txt

# Build/rebuild RAG index (needed once, and after rag_corpus.json changes)
cd Pepper-Controller-main-2/pepper_ui/server/app && python rag_engine.py

# Full run — robot + server, Codex API
python main.py

# Offline run — Ollama backend, no internet (start `ollama serve` first)
python main.py --offline

# Server-only (no NAOqi) — typical for laptop-only backend dev
python main.py --server-only

# Offline integration test suite (forces OFFLINE_MODE, hits real Ollama)
python test_offline.py

# Diagnostics (checks robot health, backend, pipeline end-to-end)
python run_diagnostic.py               # full
python run_diagnostic.py --quick       # skip motion/recording
python run_diagnostic.py --server-only # no robot
```

No lint/test CI — this is a graduation project. The authoritative "does it work" check is `test_offline.py` + `run_diagnostic.py`.

## Config

`config.json` (gitignored; copy from `config.example.json`) holds network IPs and Whisper settings. Keys consumed by `main.py`:

- `ROBOT_IP`, `ROBOT_PORT` (NAOqi broker, always 9559)
- `SERVER_IP`, `SERVER_PORT` (Flask)
- `WS_PORT` (WebSocket bridge, default 8765)
- `WHISPER_MODEL` / `WHISPER_DEVICE` / `WHISPER_COMPUTE_TYPE` / `WHISPER_CPU_THREADS` — consumed by `app.py` directly; supports `auto` for device (CUDA auto-detect via CTranslate2, falls back to CPU int8 if GPU init fails).

`main.py` injects these as env vars into both Py2 and Py3 child processes.

## Database

SQLite (`hospital.db` / `app.db`) via Flask-SQLAlchemy. Auto-created on first run; seeded from `Pepper-Controller-main-2/pepper_ui/server/app/Data/` CSV/XLSX files. Models include `Doctor`, `Schedule`, `Appointment`, `Branch`, `Department`, `Contact`, `Patient`, `Staff`, `PatientMemory`, `Medication`, `DrugInteraction`, `MedicationReminder`, `VitalRecord`, `TriageHistory`, `SymptomHistory` — all defined in `app.py`. DBs contain patient data and are gitignored.

## AI Modules

Each AI capability is a standalone module under `Pepper-Controller-main-2/pepper_ui/server/app/ai_modules/` (sentiment, medical NER, symptom checker, face auth, fall detection, vitals, drug interactions, medication reminders, translator, wait estimator, symptom progression, acoustic analyzer, pose analyzer, multi-agent clinical, clinical predictor, conversation memory). They are imported and wired into Flask routes in `app.py`. Face recognition runtime artifacts (`face_model.xml`, `labels.json`) are gitignored and rebuilt on enrollment.

## Gotchas

- **Two Python versions is real**: do not mix imports. NAOqi-side code is Python 2.7 syntax only (print statements, `from __future__`, no f-strings).
- **The hard-coded `PEPPER_SDK` path in `main.py:13`** — update per machine; gitignored SDK.
- **Pepper's tablet caches aggressively**; `app.py` sets `Cache-Control: no-store` globally, don't remove this.
- **Patient data**: DBs, face data, and audio recordings are PII and must stay gitignored. The `.gitignore` already handles this — don't `git add -A` blindly.
- **Firewall**: `main.py` tries to add Windows Firewall rules for ports 8080/8765/8082; needs Admin on public/hotspot networks.
