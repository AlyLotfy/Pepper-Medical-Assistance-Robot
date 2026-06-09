<div align="center">

# Pepper Medical Assistance Robot

**An intelligent humanoid hospital receptionist for Andalusia Hospital Group**
**AAST College of Artificial Intelligence — Graduation Project, 2025 / 2026**

[![Python](https://img.shields.io/badge/Python-3.13_+_2.7-3776AB?logo=python&logoColor=white)](#)
[![NAOqi](https://img.shields.io/badge/NAOqi-2.8-009BDB)](#)
[![Flask](https://img.shields.io/badge/Flask-3-000000?logo=flask&logoColor=white)](#)
[![Whisper](https://img.shields.io/badge/Whisper-faster--whisper-green)](#)
[![Claude](https://img.shields.io/badge/Claude-Haiku_4.5-D97757)](#)
[![Ollama](https://img.shields.io/badge/Ollama-qwen2.5_7b-000)](#)
[![FAISS](https://img.shields.io/badge/RAG-FAISS-0467DF)](#)
[![License](https://img.shields.io/badge/License-Academic-lightgrey)](#license)

![Pepper Robot](Pepper-Controller-main-2/pepper_ui/server/static/Pepper.jpg)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Demo Video](#demo-video)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [How It Works](#how-it-works)
  - [Voice and Speech Pipeline](#voice-and-speech-pipeline)
  - [The Agentic LLM Loop](#the-agentic-llm-loop)
  - [RAG and Grounded Retrieval](#rag-and-grounded-retrieval)
  - [Face Authentication](#face-authentication)
  - [Triage and Safety](#triage-and-safety)
- [Tablet UI Gallery](#tablet-ui-gallery)
- [Runtime and Console](#runtime-and-console)
- [Evaluation and Benchmarks](#evaluation-and-benchmarks)
- [Technology Stack](#technology-stack)
- [Project Layout](#project-layout)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Offline Mode](#offline-mode)
- [Testing and Diagnostics](#testing-and-diagnostics)
- [Team](#team)
- [License](#license)

---

## Overview

Pepper Medical Assistance Robot transforms a **SoftBank Pepper humanoid** into a fully functional, bilingual (Arabic / English) hospital receptionist deployed at **Andalusia Hospital Group**. Patients walk up, get recognized by face, talk to the robot in their own language, book appointments, get triaged, and are physically guided to the right department — all on a local network with **no cloud dependency** in offline mode.

The system sits at the intersection of robotics, real-time systems, and modern AI: Whisper for speech, Claude (or local Ollama) for reasoning with agentic tool-calling, FAISS-indexed RAG for hospital knowledge, OpenCV for face login, and NAOqi for the body underneath it all.

| ![Interaction concept](project_images/Screenshot%202026-06-01%20023852.png) | ![End-to-end patient journey](project_images/Screenshot%202026-06-02%20154644.png) |
| :---: | :---: |
| **Socially assistive healthcare robot — interaction concept** | **End-to-end patient journey with Pepper** |

---

## Demo Video

A short walkthrough of a patient interacting with Pepper — voice request, AI response, and the tablet UI in action.

**[Watch the demo (project_images/pepper_demo.mp4)](project_images/pepper_demo.mp4)**

---

## Key Features

### Patient-Facing

- **Voice Interaction** — Speak Arabic or English; Whisper STT transcribes in roughly 0.9 seconds
- **Agentic AI Conversation** — Claude API (online) or local Ollama / qwen2.5:7b (offline), both running the same tool-calling loop
- **Appointment Booking** — Voice-driven booking, viewing, and cancellation
- **Autonomous Navigation** — Pepper physically guides patients to their destination
- **Face Recognition Login** — OpenCV LBPH; recognized on arrival, no typing
- **Emergency Triage** — Symptom-based urgency scoring with department routing
- **Health Tips and Symptom Checker** — Context-aware and language-aware

### Technical

- **Full bilingual UI** with proper right-to-left support for Arabic
- **FAISS-indexed RAG** over the Andalusia Hospital knowledge base
- **Sentiment and emotion analysis** that shapes response tone
- **Medical NER** for extracting symptoms, drugs, and body parts from free text
- **Offline mode** — no internet required after the model pull
- **Live MJPEG camera stream** from Pepper to the tablet UI

---

## System Architecture

```
+-------------------------------------------------------------------+
|                          WINDOWS LAPTOP                           |
|                                                                   |
|   +-----------------------------------------------------------+   |
|   |             Flask Backend  (Python 3, port 8080)          |   |
|   |                                                           |   |
|   |   +-------------+   +--------------+   +----------------+  |   |
|   |   | Whisper STT |   |  Claude API  |   | Ollama (local) |  |   |
|   |   | (CTranslate)|   |  (online)    |   |  qwen2.5:7b    |  |   |
|   |   +-------------+   +--------------+   +----------------+  |   |
|   |                                                           |   |
|   |   +-------------+   +--------------+   +----------------+  |   |
|   |   |  FAISS RAG  |   |  Face Auth   |   |  Hospital DB   |  |   |
|   |   |  (corpus)   |   |  (OpenCV)    |   |  (SQLite)      |  |   |
|   |   +-------------+   +--------------+   +----------------+  |   |
|   +-----------------------------------------------------------+   |
|                              |                                    |
|   +----------------------+   |   +--------------------------+     |
|   |  WebSocket Bridge    |<--+   |  Camera Server           |     |
|   |  (port 8765)         |      |  (port 8082, Python 2.7) |     |
|   +----------+-----------+      +--------------------------+      |
+--------------|----------------------------------------------------+
               |  LAN Cable (192.168.x.x)
+--------------|----------------------------------------------------+
|              |          PEPPER ROBOT (NAOqi 2.8)                  |
|   +----------v-----------+   +----------------------------------+ |
|   |  NAOqi WebSocket     |   |  Tablet Browser                  | |
|   |  (MainVoice.py)      |   |  -> Flask server UI              | |
|   |  (nav_bridge.py)     |   |  -> Arabic / English touch UI    | |
|   +----------------------+   +----------------------------------+ |
+-------------------------------------------------------------------+
```

The formal architecture as documented in the technical report:

| ![Overall system architecture](project_images/Screenshot%202026-06-02%20154605.png) | ![Deployment and communication](project_images/Screenshot%202026-06-02%20154619.png) |
| :---: | :---: |
| **Figure 1 — Overall system architecture** | **Figure 2 — Deployment and communication architecture** |
| ![Three-tier architecture](project_images/Screenshot%202026-06-02%20154533.png) | ![Use case diagram](project_images/Screenshot%202026-06-02%20154549.png) |
| **Three-tier architecture of the system** | **Figure 3 — Use case diagram** |
| ![Platform integration overview](project_images/Screenshot%202026-06-02%20154048.png) | ![Platform and backend integration concept](project_images/Screenshot%202026-06-02%20154518.png) |
| **Pepper and Python intelligence server integration** | **Platform and backend integration concept** |

### Why dual-runtime?

NAOqi's Python SDK is **Python 2.7 only**. Modern AI tooling (Whisper, Hugging Face, Claude SDK, Flask 3) is Python 3 only. The system runs **both interpreters side-by-side** and bridges them with a WebSocket relay — a deliberate engineering choice documented in [`CLAUDE.md`](./CLAUDE.md).

---

## How It Works

### Voice and Speech Pipeline

Pepper captures speech through its own microphone, the audio is cleaned and transferred to the laptop, and faster-whisper transcribes it with automatic Arabic / English language detection. The transcript becomes the input to the agentic assistant.

| ![Voice processing pipeline](project_images/Screenshot%202026-06-02%20154216.png) | ![Bilingual Whisper workflow](project_images/Screenshot%202026-06-02%20154245.png) |
| :---: | :---: |
| **Implemented voice processing pipeline** | **Bilingual Whisper speech-to-text workflow** |
| ![ASR data flow](project_images/Screenshot%202026-06-02%20154309.png) | ![Voice interaction summary](project_images/Screenshot%202026-06-02%20154323.png) |
| **Automatic speech recognition data flow** | **Project voice interaction summary** |

### The Agentic LLM Loop

Both online (Claude) and offline (Ollama) use the **same tool-calling loop** in `app.py::call_llm()`. Tools are defined once and routed to whichever provider is active — booking, schedule lookup, navigation, RAG search, emergency dispatch, and roughly ten more are exposed as callable tools the model can choose from.

| ![Agentic tool-calling loop](project_images/Screenshot%202026-06-02%20154709.png) | ![Online and offline AI modes](project_images/Screenshot%202026-06-02%20154339.png) |
| :---: | :---: |
| **Simplified agentic tool-calling loop** | **Online and offline AI modes share one core** |

A real conversation showing grounded, memory-aware reasoning — Pepper recalls the patient's medical profile and recommends suitable doctors:

![Personalized chat with doctor recommendations](project_images/f3b16beb-4743-4368-8445-4979045cdd87.jpg)

### RAG and Grounded Retrieval

Answers are grounded in project-owned data: a curated hospital knowledge corpus indexed with FAISS, a registered set of navigation targets, and the SQLite operational database. This keeps responses accurate and auditable.

| ![RAG pipeline for health queries](project_images/Screenshot%202026-06-02%20155228.png) | ![Data-source evidence for grounded retrieval](project_images/Screenshot%202026-06-02%20155119.png) |
| :---: | :---: |
| **RAG pipeline for health queries** | **Data-source evidence for grounded retrieval** |
| ![Hospital database schema](project_images/Screenshot%202026-06-02%20155100.png) | ![Data-source evidence summary](project_images/Screenshot%202026-06-02%20154420.png) |
| **Figure 9 — Simplified hospital database schema** | **Grounded data sources at a glance** |

![Distribution of medical specialties in the knowledge base](project_images/Screenshot%202026-06-02%20155151.png)

### Face Authentication

Patients enroll their face once, then log in hands-free on subsequent visits using an OpenCV LBPH recognizer running locally on the laptop.

| ![Face authentication workflow](project_images/Screenshot%202026-06-02%20154501.png) | ![Face login screen](project_images/59ccd130-34d7-43e9-b447-850727b53213.jpg) |
| :---: | :---: |
| **Figure 5 — Face authentication workflow** | **Face login — live Pepper camera** |

![Face ID enrollment](project_images/photo_5828179043839315512_y.jpg)

*Face ID enrollment — patients register their face to log in without a password.*

### Triage and Safety

A guided symptom check produces an urgency level and escalation path. Critical signs trigger an immediate-attention flag and notify staff, with the assessment stored for the care team.

| ![Triage safety and escalation workflow](project_images/Screenshot%202026-06-02%20155249.png) | ![Symptom check step 1](project_images/131df69b-d9dc-4027-846a-8f9573fe8547.jpg) |
| :---: | :---: |
| **Figure 8 — Triage safety and escalation workflow** | **Symptom check — chief complaint selection** |
| ![Triage result immediate](project_images/a41ddea7-7098-42c7-bebc-353bcd6dc0f7.jpg) | ![Staff triage dashboard](project_images/37ae3f6b-b3c6-48d7-89e0-97e1039bda0d.jpg) |
| **Triage result — immediate-attention flag** | **Staff dashboard — triage queue** |

---

## Tablet UI Gallery

The bilingual touch interface that runs on Pepper's chest tablet.

### Home and Sign In

| ![English home](project_images/photo_5828179043839315528_y.jpg) | ![Arabic home](project_images/6fa0a156-7b82-4338-80a4-2ac3fa51e316.jpg) |
| :---: | :---: |
| **Home screen — English** | **Home screen — Arabic (right-to-left)** |
| ![Sign in](project_images/9fe525a7-095e-4ba0-8d40-7516b4266692.jpg) | ![About Pepper](project_images/ea3bd116-8eb7-4db3-ad74-e17935e2d9da.jpg) |
| **Sign in — patient or staff** | **About Pepper — mission and capabilities** |

### Conversation and Booking

| ![Pepper chat greeting](project_images/e9741fc9-a348-4eb0-abe4-5eab7706798e.jpg) | ![Book appointment step 1](project_images/92fca9d4-74d8-4811-acfb-86698aac8d86.jpg) |
| :---: | :---: |
| **Pepper chat — greeting** | **Book appointment — step 1, details** |
| ![Book appointment step 3](project_images/8af240c7-a259-47e2-ae1a-48719c0adf3d.jpg) | ![Booking confirmed](project_images/53a43873-9e2d-4f51-91d1-8f3c27f63a24.jpg) |
| **Book appointment — step 3, date and time** | **Booking confirmed** |

### Schedules, Guidance and My Appointments

| ![Doctor schedule](project_images/24c57934-812f-40fb-8e7e-31b9bf70792b.jpg) | ![Find your doctor](project_images/2c20ff1c-7980-4713-a7c9-3eb63a1ef795.jpg) |
| :---: | :---: |
| **Doctor schedule lookup** | **Find your doctor — Pepper guides to the room** |
| ![My appointments](project_images/741db248-0711-444b-adc5-2cb9125bf717.jpg) | ![Appointment card](project_images/5b79f75b-03ee-4809-a7c2-3676e342e233.jpg) |
| **My appointments — view and cancel** | **Appointment detail card** |

### Emergency, Health Tips and Staff

| ![Emergency help](project_images/864a5a1c-f82f-4d8b-b49f-fe4e3ecf95ce.jpg) | ![Health tips](project_images/c57b7a86-31d1-4517-aad0-b0768460456f.jpg) |
| :---: | :---: |
| **Emergency help — press and hold to alert staff** | **Health tips — personalized** |
| ![Staff dashboard doctors](project_images/a5bd512a-afc0-41a9-9543-8515dbaa4c28.jpg) | |
| **Staff dashboard — doctor management** | |

---

## Runtime and Console

The master launcher (`main.py`) starts every subsystem in the correct Python runtime, opens the required firewall ports, and initializes the AI modules.

| ![Main launcher startup](project_images/41710b0f-fac1-4d2d-8ad4-340d4996bb4f.jpg) | ![AI modules initialization](project_images/436c5f79-67a3-4ab0-a23a-b0e05ca39979.jpg) |
| :---: | :---: |
| **Main launcher — startup and firewall setup** | **AI modules — initialization log** |
| ![Flask server log](project_images/91faa1bd-ee6a-4b8f-a385-38d9a85ae90b.jpg) | ![Database schema in DB Browser](project_images/9d2eae66-d5fa-4d10-967b-709a5e581f2a.jpg) |
| **Flask backend — request log** | **Hospital database — schema in DB Browser** |

| ![System startup and runtime initialization](project_images/Screenshot%202026-06-02%20155041.png) | ![Appointment booking sequence](project_images/Screenshot%202026-06-02%20155009.png) |
| :---: | :---: |
| **System startup and runtime initialization flow** | **Figure 4 — appointment booking sequence** |

---

## Evaluation and Benchmarks

The system was validated with an automated, multi-scenario test suite (`test_offline.py`) plus end-to-end diagnostics. Headline results are summarized below.

| ![Functional capability coverage](project_images/Screenshot%202026-06-02%20155602.png) | ![Final system capabilities summary](project_images/Screenshot%202026-06-02%20155640.png) |
| :---: | :---: |
| **Functional capability coverage across domains** | **Final system capabilities summary** |

### Accuracy

| ![Evaluation summary offline](project_images/Screenshot%202026-06-02%20155304.png) | ![Accuracy before vs after](project_images/Screenshot%202026-06-02%20155537.png) |
| :---: | :---: |
| **Evaluation summary (offline mode)** | **Accuracy before vs. after bug-fixes and optimization** |
| ![Test assertion outcomes](project_images/Screenshot%202026-06-02%20155511.png) | ![Per-scenario hard accuracy](project_images/Screenshot%202026-06-02%20155456.png) |
| **Overall test assertion outcomes (194 assertions)** | **Per-scenario hard accuracy** |
| ![Test assertion breakdown](project_images/Screenshot%202026-06-02%20155526.png) | ![Automated test and runtime evidence](project_images/Screenshot%202026-06-02%20155616.png) |
| **Test assertion breakdown by scenario** | **Automated test and runtime evidence** |

### Speech Recognition

| ![Speech recognition WER clinical](project_images/Screenshot%202026-06-02%20155318.png) | ![ASR accuracy comparison](project_images/Screenshot%202026-06-02%20155333.png) |
| :---: | :---: |
| **Speech recognition word error rate — clinical vocabulary** | **ASR accuracy — model comparison** |

### Latency

| ![AI response time distribution](project_images/Screenshot%202026-06-02%20155345.png) | ![Response time percentile profile](project_images/Screenshot%202026-06-02%20155400.png) |
| :---: | :---: |
| **Distribution of AI response times (offline mode)** | **Response time percentile profile** |
| ![Mean response latency per scenario](project_images/Screenshot%202026-06-02%20155414.png) | ![Conversation depth per scenario](project_images/Screenshot%202026-06-02%20155549.png) |
| **Mean response latency per scenario** | **Conversation depth per scenario** |
| ![Long conversation latency](project_images/Screenshot%202026-06-02%20155427.png) | ![Emergency triage per-turn latency](project_images/Screenshot%202026-06-02%20155442.png) |
| **Response latency across a long conversation** | **Emergency triage per-turn latency (rule-based fast path)** |

---

## Technology Stack

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
| **Tablet UI** | HTML5 · CSS3 · Vanilla JS · bilingual i18n |
| **Networking** | LAN Ethernet (robot to laptop) |

---

## Project Layout

```
Pepper-Medical-Assistance-Robot/
├── main.py                       # Master launcher — spawns all subsystems
├── config.json                   # Network config (gitignored)
├── config.example.json           # Template for config.json
├── requirements.txt              # Python 3 dependencies
├── test_offline.py               # Integration test suite (offline mode)
├── run_diagnostic.py             # End-to-end health check
│
├── Pepper-Controller-main-2/
│   ├── pepper_ui/
│   │   ├── robot/                # Python 2.7 + NAOqi (camera, tablet, bridge)
│   │   └── server/app/
│   │       ├── app.py            # Flask — REST API + agentic LLM loop
│   │       ├── rag_engine.py     # FAISS-indexed retrieval
│   │       └── ai_modules/       # 17 standalone AI capabilities
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
│   │   ├── MainVoice.py          # NAOqi voice capture loop + TTS (Py2)
│   │   └── ws_bridge.py          # WebSocket relay (Py3)
│   │
│   └── navigation/               # NAOqi navigation (Py2)
│
├── project_images/               # Documentation: figures, UI, benchmarks, demo video
└── Documents/                    # Final reports and technical PDFs
```

---

## Quick Start

### Prerequisites

- **Hardware:** SoftBank Pepper (NAOqi 2.8.x), Windows 10 / 11 laptop, LAN cable
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
ollama serve              # in a separate terminal
ollama pull qwen2.5:7b    # one-time
python main.py --offline

# Server only — no robot
python main.py --server-only
```

The tablet UI is reachable at `http://<SERVER_IP>:<SERVER_PORT>` from any browser on the LAN.

### Verify

```bash
python run_diagnostic.py          # full end-to-end check
python run_diagnostic.py --quick
python test_offline.py            # offline mode integration tests
```

---

## Configuration

Copy `config.example.json` to `config.json` and edit:

```json
{
  "ROBOT_IP": "1.1.1.10",
  "ROBOT_PORT": 9559,
  "SERVER_IP": "1.1.1.249",
  "SERVER_PORT": 8080,
  "WS_PORT": 8765,
  "WHISPER_MODEL": "small",
  "WHISPER_DEVICE": "auto",
  "WHISPER_COMPUTE_TYPE": "int8"
}
```

`main.py` auto-injects these into both the Python 2 and Python 3 child processes.

---

## API Reference

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/voice` | Submit audio, returns AI text and TTS |
| `POST` | `/chat` | Submit text, returns AI response |
| `GET` / `POST` | `/language` | Get or set UI language (ar / en) |
| `GET` | `/api/doctors` | List doctors with availability |
| `GET` | `/api/departments` | List departments |
| `POST` | `/api/book` | Book appointment |
| `GET` | `/api/appointments/<patient_id>` | Patient appointments |
| `DELETE` | `/api/appointments/<id>` | Cancel appointment |
| `POST` | `/api/login` · `/api/signup` | Username and password auth |
| `POST` | `/api/face/enroll` · `/api/face/login` | Face auth |
| `POST` | `/api/navigate` | Send navigation command to Pepper |
| `GET` | `/api/nav/targets` | Named navigation targets |
| `GET` | `/api/camera` | Latest JPEG frame from Pepper |
| `POST` | `/api/emergency` · `/api/triage` | Emergency and triage |

Full schema in [`Documents/Technical Report.pdf`](./Documents/).

---

## Offline Mode

`python main.py --offline` swaps the LLM provider only. Everything else — Whisper, FAISS, face recognition, the database, the tablet UI — already runs locally.

Requirements:

- Ollama installed and running (`ollama serve`)
- `qwen2.5:7b` pulled (around 5 GB)

The **same tool-calling agentic loop** drives both online and offline modes. There is no behavioural fork in the code — only the underlying LLM call differs.

---

## Testing and Diagnostics

| Command | What it checks |
| --- | --- |
| `python run_diagnostic.py` | Full end-to-end: robot health, backend, voice pipeline, navigation |
| `python run_diagnostic.py --quick` | Skips motion and recording |
| `python run_diagnostic.py --server-only` | Backend only, no robot needed |
| `python test_offline.py` | Forces `OFFLINE_MODE=1`, hits real Ollama |

---

## Team

**Arab Academy for Science, Technology and Maritime Transport (AAST)**
College of Artificial Intelligence — Graduation Project 2025 / 2026

| Name | Role |
| --- | --- |
| **Aly Lotfy** | Backend AI · Flask Server · Offline Mode · Agentic LLM Loop |
| _Team Member_ | Navigation and Robot Control |
| _Team Member_ | Frontend UI and Tablet Interface |
| _Team Member_ | Face Recognition and Computer Vision |

**Supervisor:** _Dr. [Name], AAST College of Artificial Intelligence_

**Industry partner:** Andalusia Hospital Group — Alexandria, Egypt

---

## License

This project was developed for academic purposes at AAST in partnership with Andalusia Hospital Group. All rights reserved. Patient data and trained face-recognition artifacts are intentionally gitignored.
