<div align="center">

#  Pepper Medical Assistance Robot

**An intelligent humanoid hospital receptionist for Andalusia Hospital Group**
**AAST Computer Engineering — Graduation Project, 2025/2026**

[![Python](https://img.shields.io/badge/Python-3.13_+_2.7-3776AB?logo=python&logoColor=white)](#)
[![NAOqi](https://img.shields.io/badge/NAOqi-2.8-009BDB)](#)
[![Flask](https://img.shields.io/badge/Flask-3-000000?logo=flask&logoColor=white)](#)
[![Whisper](https://img.shields.io/badge/Whisper-faster--whisper-green)](#)
[![Claude](https://img.shields.io/badge/Claude-Haiku_4.5-D97757)](#)
[![Ollama](https://img.shields.io/badge/Ollama-qwen2.5_7b-000)](#)
[![FAISS](https://img.shields.io/badge/RAG-FAISS-0467DF)](#)
[![License](https://img.shields.io/badge/License-Academic-lightgrey)](#license)

</div>

---

##  What This Is

Pepper Medical Assistance Robot transforms a **SoftBank Pepper humanoid** into a fully functional, bilingual (Arabic / English) hospital receptionist deployed at **Andalusia Hospital Group**. Patients walk up, get recognized by face, talk to the robot in their own language, book appointments, get triaged, and are physically guided to the right department — all on a local network with **no cloud dependency** in offline mode.

It's the kind of project that sits at the intersection of robotics, real-time systems, and modern AI: Whisper for speech, Claude (or local Ollama) for reasoning with agentic tool-calling, FAISS-indexed RAG for hospital knowledge, OpenCV for face login, and NAOqi for the body underneath it all.

> **Watch it in action:** _(add demo video link / GIF here once recorded)_

---

##  Key Features

### Patient-Facing
-  **Voice Interaction** — Speak Arabic or English; Whisper STT transcribes in ~0.9 s
-  **Agentic AI Conversation** — Claude API (online) or local Ollama / qwen2.5:7b (offline), both running the same tool-calling loop
-  **Appointment Booking** — Voice-driven booking, viewing, and cancellation
-  **Autonomous Navigation** — Pepper physically guides patients to their destination
-  **Face Recognition Login** — OpenCV LBPH; recognized on arrival, no typing
-  **Emergency Triage** — Symptom-based urgency scoring with department routing
-  **Health Tips & Symptom Checker** — Context-aware, language-aware

### Technical
-  **Full bilingual UI** with proper RTL support for Arabic
-  **FAISS-indexed RAG** over the Andalusia Hospital knowledge base
-  **Sentiment & emotion analysis** that shapes response tone
-  **Medical NER** for extracting symptoms, drugs, and body parts from free text
-  **Offline mode** — no internet required after model pull
-  **Live MJPEG camera stream** from Pepper to the tablet UI

---

##  System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         WINDOWS LAPTOP                          │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │           Flask Backend (Python 3, port 8080)             │  │
│  │                                                           │  │
│  │  ┌─────────────┐ ┌──────────────┐ ┌─────────────────┐     │  │
│  │  │ Whisper STT │ │  Claude API  │ │  Ollama (local) │     │  │
│  │  │ (CTranslate)│ │   (online)   │ │   qwen2.5:7b    │     │  │
│  │  └─────────────┘ └──────────────┘ └─────────────────┘     │  │
│  │                                                           │  │
│  │  ┌─────────────┐ ┌──────────────┐ ┌─────────────────┐     │  │
│  │  │  FAISS RAG  │ │  Face Auth   │ │   Hospital DB   │     │  │
│  │  │  (corpus)   │ │   (OpenCV)   │ │    (SQLite)     │     │  │
│  │  └─────────────┘ └──────────────┘ └─────────────────┘     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                          │                                      │
│  ┌──────────────────────┐│  ┌──────────────────────────┐        │
│  │   WebSocket Bridge   │◄──┤      Camera Server       │        │
│  │      (port 8765)     │   │ (port 8082, Python 2.7)  │        │
│  └──────────┬───────────┘   └──────────────────────────┘        │
└─────────────┼───────────────────────────────────────────────────┘
              │  LAN Cable (192.168.x.x)
┌─────────────┼───────────────────────────────────────────────────┐
│             │              PEPPER ROBOT (NAOqi 2.8)             │
│  ┌──────────▼───────────┐   ┌──────────────────────────────────┐│
│  │   NAOqi WebSocket    │   │           Tablet Browser         ││
│  │   (MainVoice.py)     │   │      → Flask server UI           ││
│  │   (nav_bridge.py)    │   │      → Arabic / English touch UI ││
│  └──────────────────────┘   └──────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Why dual-runtime?
NAOqi's Python SDK is **Python 2.7 only**. Modern AI tooling (Whisper, Hugging Face, Claude SDK, Flask 3) is Python 3 only. The system runs **both interpreters side-by-side** and bridges them with a WebSocket relay — a deliberate engineering choice that's documented in [`CLAUDE.md`](./CLAUDE.md).

### The agentic loop
Both online (Claude) and offline (Ollama) use the **same tool-calling loop** in `app.py::call_llm()`. Tools are defined once and routed to whichever provider is active — booking, schedule lookup, navigation, RAG search, emergency dispatch, and ~10 more are exposed as callable tools the LLM can choose from.

---

## 🛠️ Tech Stack

| Layer | Technology |
| --- | --- |
| **Robot Platform** | SoftBank Pepper · NAOqi 2.8 · Python 2.7 |
| **Backend Server** | Python 3.13 · Flask 3 · SQLAlchemy |
| **Speech-to-Text** | faster-whisper · CTranslate2 (int8 quantized) |
| **AI — Online** | Anthropic Claude API · `claude-haiku-4-5-20251001` |
| **AI — Offline** | Ollama · `qwen2.5:7b` (native tool calling) |
| **Knowledge Base** | FAISS · sentence-transformers · custom RAG |
| **Face Recognition** | OpenCV LBPH face recognizer |
| **Database** | SQLite · Flask-SQLAlchemy |
| **Real-time Bridge** | asyncio · WebSocket (port 8765) |
| **Robot Camera** | HTTP MJPEG stream (port 8082) |
| **Tablet UI** | HTML5 · CSS3 · Vanilla JS · i18n bilingual |
| **Networking** | LAN Ethernet (robot ↔ laptop) |

---

##  Project Layout

```
Pepper-Medical-Assistance-Robot/
├── main.py                  # Master launcher — spawns all subsystems
├── config.json              # Network config (gitignored)
├── config.example.json      # Template for config.json
├── requirements.txt         # Python 3 dependencies
├── test_offline.py          # Integration test suite (offline mode)
├── run_diagnostic.py        # End-to-end health check
│
├── Pepper-Controller-main-2/
│   ├── pepper_ui/
│   │   ├── robot/           # Python 2.7 + NAOqi (camera, tablet, bridge)
│   │   └── server/app/
│   │       ├── app.py                    # Flask — REST API + agentic LLM loop
│   │       ├── rag_engine.py             # FAISS-indexed retrieval
│   │       └── ai_modules/               # 17 standalone AI capabilities
│   │           ├── conversation_memory.py
│   │           ├── face_auth.py
│   │           ├── medical_ner.py
│   │           ├── sentiment.py
│   │           ├── symptom_checker.py
│   │           ├── drug_checker.py
│   │           ├── medication_reminder.py
│   │           ├── vital_tracker.py
│   │           ├── translator.py
│   │           ├── wait_estimator.py
│   │           ├── symptom_progression.py
│   │           ├── multi_agent.py
│   │           ├── clinical_predictor.py
│   │           ├── fall_detection.py
│   │           ├── pose_analyzer.py
│   │           ├── acoustic_analyzer.py
│   │           └── ...
│   │
│   ├── pepper_voice/
│   │   ├── MainVoice.py     # NAOqi voice capture loop + TTS (Py2)
│   │   └── ws_bridge.py     # WebSocket relay (Py3)
│   │
│   └── navigation/          # NAOqi nav (Py2)
│
└── Documents/               # Final reports & technical PDFs
```

---

##  Quick Start

### Prerequisites

- **Hardware:** SoftBank Pepper (NAOqi 2.8.x), Windows 10/11 laptop, LAN cable
- **Software:** Python 3.10+, Python 2.7, NAOqi SDK at `C:\pynaoqi\pynaoqi-python2.7-2.8.6.23-win64-vs2015`
- **Optional (offline):** [Ollama](https://ollama.com)

### Install

```bash
git clone https://github.com/AlyLotfy/Pepper-Medical-Assistance-Robot.git
cd Pepper-Medical-Assistance-Robot

python -m venv pepper_env
pepper_env\Scripts\activate
pip install -r requirements.txt
```

Create `.env`:
```
ANTHROPIC_API_KEY=your_key_here
```

Build the RAG index (first run only):
```bash
cd Pepper-Controller-main-2/pepper_ui/server/app
python rag_engine.py
```

### Run

```bash
# Online — Claude API
python main.py

# Offline — local Ollama
ollama serve            # in a separate terminal
ollama pull qwen2.5:7b  # one-time
python main.py --offline

# Server only — no robot
python main.py --server-only
```

The tablet UI is reachable at `http://<SERVER_IP>:<SERVER_PORT>` from any browser on the LAN.

### Verify

```bash
python run_diagnostic.py        # full end-to-end check
python run_diagnostic.py --quick
python test_offline.py          # offline mode integration tests
```

---

##  Configuration

Copy `config.example.json` → `config.json` and edit:

```json
{
  "ROBOT_IP":   "1.1.1.10",
  "ROBOT_PORT": 9559,
  "SERVER_IP":  "1.1.1.249",
  "SERVER_PORT": 8080,
  "WS_PORT":    8765,
  "WHISPER_MODEL": "small",
  "WHISPER_DEVICE": "auto",
  "WHISPER_COMPUTE_TYPE": "int8"
}
```

`main.py` auto-injects these into both Python 2 and Python 3 child processes.

---

##  API Reference

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/voice` | Submit audio → AI text + TTS |
| `POST` | `/chat` | Submit text → AI response |
| `GET` / `POST` | `/language` | Get/set UI language (ar/en) |
| `GET` | `/api/doctors` | List doctors with availability |
| `GET` | `/api/departments` | List departments |
| `POST` | `/api/book` | Book appointment |
| `GET` | `/api/appointments/<patient_id>` | Patient appointments |
| `DELETE` | `/api/appointments/<id>` | Cancel appointment |
| `POST` | `/api/login` · `/api/signup` | Username/password auth |
| `POST` | `/api/face/enroll` · `/api/face/login` | Face auth |
| `POST` | `/api/navigate` | Send nav command to Pepper |
| `GET` | `/api/nav/targets` | Named navigation targets |
| `GET` | `/api/camera` | Latest JPEG frame from Pepper |
| `POST` | `/api/emergency` · `/api/triage` | Emergency / triage |

Full schema in [`Documents/Technical Report.pdf`](./Documents/).

---

##  Offline Mode

`python main.py --offline` swaps the LLM provider only. Everything else — Whisper, FAISS, face recognition, the database, the tablet UI — already runs locally.

Requirements:
- Ollama installed and running (`ollama serve`)
- `qwen2.5:7b` pulled (~5 GB)

The **same tool-calling agentic loop** drives both online and offline modes. There is no behavioural fork in the code — only the underlying LLM call differs.

---

##  Testing & Diagnostics

| Command | What it checks |
| --- | --- |
| `python run_diagnostic.py` | Full end-to-end: robot health, backend, voice pipeline, navigation |
| `python run_diagnostic.py --quick` | Skips motion / recording |
| `python run_diagnostic.py --server-only` | Backend only, no robot needed |
| `python test_offline.py` | Forces `OFFLINE_MODE=1`, hits real Ollama |

---

##  Team

**Arab Academy for Science, Technology & Maritime Transport (AAST)**
Computer Engineering Department — Graduation Project 2025/2026

| Name | Role |
| --- | --- |
| **Aly Lotfy** | Backend AI · Flask Server · Offline Mode · Agentic LLM Loop |

**Industry partner:** Andalusia Hospital Group — Alexandria, Egypt

---

##  License

This project was developed for academic purposes at AAST in partnership with Andalusia Hospital Group. All rights reserved. Patient data and trained face-recognition artifacts are intentionally gitignored.

---

<div align="center">

_If you found this project interesting, ⭐ the repo — it helps other students discover it._

</div>
