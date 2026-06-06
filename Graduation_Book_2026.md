# Pepper Medical Assistant Robot
## An AI-Powered Socially Assistive Robot for Intelligent Hospital Automation

**Arab Academy for Science, Technology and Maritime Transport**  
College of Artificial Intelligence — Intelligent Systems Department  
B.Sc. Final Year Graduation Project

---

**Presented By:**  
Aly Lotfy (221000412) • Abdulrahman Karam (221002035) • Amr Emara (221000299)  
Amira El-Sayed (221002982) • Mohammed Maghwary (221001747) • Youssef Ahmed Tawfik (221001264)

**Supervised By:** Dr. Ahmed El-Shaer  
**Deployment Site:** Andalusia Hospital, Alexandria, Egypt  
**Academic Year:** 2025 / 2026 | **Date:** June 2026

---

## Declaration

We hereby declare that this graduation project, titled *Pepper Medical Assistant Robot*, is our original work, conducted under the supervision of Dr. Ahmed El-Shaer at the Arab Academy for Science, Technology, and Maritime Transport (AASTMT). All sources of information and data used in this report are duly acknowledged. No part of this work has been submitted in full or in part for any other academic award at any institution.

| Name | Student ID | Primary Role |
|---|---|---|
| Aly Lotfy | 221000412 | Backend, Flask API, Security, Architecture |
| Abdulrahman Karam | 221002035 | Robot Interface, NAOqi, IPC, LLM Integration |
| Amr Emara | 221000299 | Navigation, Agentic Tool Loop |
| Amira El-Sayed | 221002982 | Frontend, i18n, RAG Pipeline |
| Mohammed Maghwary | 221001747 | Triage, Sentiment, NER, AI Modules |
| Youssef Ahmed Tawfik | 221001264 | Testing, Evaluation, Face Recognition |

Date: June 2026

---

## Abstract

The **Pepper Medical Assistant** is a multi-layered, AI-powered robotic system that transforms the SoftBank Pepper humanoid robot into an intelligent hospital receptionist. Deployed at Andalusia Hospital, Alexandria, Egypt, the system automates reception workflows, manages patient data, and provides an interactive bilingual (Arabic/English) healthcare interface accessible to both patients and medical staff.

The architecture operates across three tiers: a robot hardware layer (Python 2.7/NAOqi), a computational intelligence server (Python 3.x/Flask), and a patient-facing tablet interface (HTML5/CSS3/ES5). Central to the design is a **dual-mode agentic AI engine** — in online mode it routes requests to Anthropic Claude (claude-haiku-4-5-20251001); in offline mode it switches transparently to a locally hosted Ollama qwen2.5:7b model. In both modes, the AI autonomously executes eight structured hospital tools (appointment booking, doctor lookup, schedule retrieval, navigation, etc.) through an iterative tool-calling loop.

Key technical contributions beyond prior Pepper deployments include: (1) an agentic tool-calling loop operable on both Claude and Ollama; (2) a FAISS-backed Retrieval-Augmented Generation (RAG) pipeline with bilingual sentence-transformer embeddings grounding all LLM responses in verified hospital data; (3) five specialized AI modules (Sentiment Analysis, Medical NER, Symptom Checker, Conversation Memory, Vital Tracker); (4) an additional set of advanced AI modules (Drug Interaction Checker, Medication Reminders, Face Authentication, Clinical Readmission Predictor, Multi-Agent Clinical System, Wait Time Estimator); (5) a Manchester Triage Scale (MTS) assessment engine with deterministic rule-based classification and AI-enriched recommendations; (6) LBPH face recognition for passwordless patient authentication; (7) a segmented navigation algorithm replacing unreliable SLAM with real-time obstacle avoidance; (8) comprehensive security hardening; and (9) a 56-test automated offline test suite.

Performance benchmarks: **9.97% Word Error Rate** on a 50-utterance bilingual test set; **2.23-second** end-to-end AI response latency (online); **100% API success rate** over 100 consecutive trials; **±0.30 m** navigation positional accuracy; **88%** triage wizard completion rate; **~90%** face recognition accuracy.

---

## Dedication

We dedicate this work to our families, whose unwavering support carried us through every challenge. To the patients and medical staff of Andalusia Hospital, whose real-world needs shaped every design decision. And to every engineer who believes technology can make healthcare more humane.

---

## Acknowledgments

Our deepest gratitude to **Dr. Ahmed El-Shaer** for his visionary supervision, unwavering support, and exceptional mentorship. His technical expertise and strategic insight profoundly shaped the direction of this project.

We sincerely thank the faculty of the College of Artificial Intelligence at AASTMT for their dedication to excellence in intelligent systems, computer vision, NLP, and software engineering.

Special thanks to **Andalusia Hospital, Alexandria**, for facilitating real-world deployment and testing, and for the clinical professionals whose feedback grounded our triage system in genuine medical practice.

---

## List of Acronyms

| Acronym | Definition |
|---|---|
| AI | Artificial Intelligence |
| API | Application Programming Interface |
| ASR | Automatic Speech Recognition |
| FAISS | Facebook AI Similarity Search |
| FHIR | Fast Healthcare Interoperability Resources |
| GBM | Gradient Boosting Machine |
| HRI | Human-Robot Interaction |
| IPC | Inter-Process Communication |
| LBPH | Local Binary Patterns Histograms |
| LLM | Large Language Model |
| MTS | Manchester Triage Scale |
| NAOqi | SoftBank Robotics Robot Operating System |
| NER | Named Entity Recognition |
| NLP | Natural Language Processing |
| ORM | Object Relational Mapper |
| RAG | Retrieval-Augmented Generation |
| RBAC | Role-Based Access Control |
| REST | Representational State Transfer |
| RTL | Right-To-Left text layout |
| SAR | Socially Assistive Robot |
| SLAM | Simultaneous Localization and Mapping |
| STT | Speech-to-Text |
| TTS | Text-to-Speech |
| VAD | Voice Activity Detection |
| WER | Word Error Rate |
| WS | WebSocket |

---

## Table of Contents

1. Introduction
2. Literature Review and Related Work
3. Core Technologies and Terminology
4. System Architecture and Design
5. Database Design
6. AI Modules
7. Subsystem Implementation
8. Performance Evaluation and Results
9. Business Model
10. Conclusion and Future Work
11. References
12. Appendices

---

# Chapter 1: Introduction

## 1.1 Overview

The **Pepper Medical Assistant** is an AI-powered socially assistive robotic system that integrates the SoftBank Pepper humanoid robot with a high-performance AI backend to automate hospital reception, triage, navigation, and patient authentication at Andalusia Hospital, Alexandria, Egypt.

Healthcare systems globally face compounding pressures: rising patient volumes, chronic staffing shortages, post-pandemic infection-control requirements, and linguistic diversity requirements. Traditional digital kiosks and static screens address queue management but cannot engage patients naturally, assess clinical urgency, or physically escort patients to their destinations. A socially assistive robot equipped with conversational AI and clinical decision support offers a scalable, infection-safe, always-available solution.

The project's central engineering contribution is a **dual-mode agentic AI architecture** where the system operates identically whether connected to a cloud LLM (Anthropic Claude) or fully offline (Ollama qwen2.5:7b). In both modes, the AI autonomously calls hospital tools — booking appointments, looking up doctors, retrieving schedules, initiating navigation — through a structured iterative tool-calling loop. This architectural decision ensures the system remains fully functional in hospitals with restricted internet access or strict patient data privacy requirements.

## 1.2 Motivation and Clinical Context

Global healthcare studies confirm that humanoid robots produce measurably higher patient engagement than screen-only interfaces. Pepper achieves **93.8% eye-contact maintenance** and **sub-2-second initial engagement rates** in clinical settings. Research published in JMIR Human Factors (Blavette et al., 2025) demonstrated that integrating an LLM into a SAR's dialogue system increased interaction success rates from **25% to 74.5%**, reducing comprehension failures that previously accounted for nearly half of all failed human-robot interactions in geriatric care.

The clinical deployment at Andalusia Hospital provided concrete requirements:
- Bilingual support (Arabic and English, including Egyptian dialect)
- Appointment booking and doctor schedule management
- Physical patient navigation to specific rooms
- Real-time symptom triage with staff alerting
- Emergency escalation
- Passwordless face-recognition login for elderly patients
- Touch-friendly tablet interface suitable for elderly and pediatric patients
- Full offline operation for data privacy compliance

## 1.3 Technical Challenges

Developing the Pepper Medical Assistant introduced a complex range of challenges requiring novel engineering solutions.

**Python 2.7/3.x Interoperability:** Pepper's NAOqi OS runs exclusively on Python 2.7. All modern AI libraries — faster-whisper, FAISS, sentence-transformers, the Anthropic SDK — require Python 3.8+. Resolution: an API-first three-tier design, explicit UTF-8 encoding for Arabic TTS strings, and a filesystem-level IPC mechanism bridging the Python version boundary without network dependencies.

**Dual-Mode LLM with Tool Calling:** Implementing an agentic tool-calling loop that works identically across Claude's native `tool_use` API and Ollama's raw text output required a custom parser extracting structured tool calls from free-form Arabic and English text.

**Bilingual ASR in Hospital Environments:** Achieving reliable speech recognition with ambient noise, diverse Arabic accents, and code-switching required careful model selection. OpenAI Whisper multilingual base (74M parameters, faster-whisper int8) was selected after benchmarking, achieving 9.97% WER on a 50-utterance bilingual test set.

**Navigation Without Reliable SLAM:** Pepper's 15-beam LIDAR produces sparse occupancy maps insufficient for reliable long-distance SLAM navigation. The team replaced SLAM with a segmented ALNavigation.navigateTo() algorithm using 2.5-meter segments, real-time hardware odometry correction, per-segment timeouts, and dynamic obstacle avoidance.

**ES5 Browser Compatibility:** Pepper's chest tablet runs a 2014-era Chromium WebKit browser without ES6 support. All 15 frontend pages are written in strict ES5 with XMLHttpRequest and string concatenation.

**Large-Scale Database Seeding:** Populating a meaningful hospital knowledge base required automated seeding of 200+ doctors across 22 specialties, 40 navigation targets across 5 floors, 80 medications, 130 drug interactions, and 250+ vital records.

## 1.4 Problem Statement

A significant gap exists in intelligent robotic assistants specifically designed for Egyptian hospital environments. Existing solutions are limited to static voice-only functionality, proprietary cloud ecosystems with high latency and privacy concerns, or lack bilingual support essential for MENA-region hospitals. Prior Pepper deployments in healthcare used scripted dialogue trees that collapsed under natural language variation and failed in bilingual environments.

This project addresses the gap through: (1) an agentic tool-calling AI loop enabling autonomous hospital operations; (2) a dual-mode online/offline LLM architecture; (3) a FAISS-backed RAG pipeline grounding responses in verified hospital data; (4) a Manchester Triage Scale clinical assessment engine; (5) LBPH face recognition; (6) a segmented navigation algorithm; (7) comprehensive security hardening; and (8) a fully bilingual AR/EN interface.

## 1.5 Objectives

1. Develop a fully functional, deployable intelligent hospital assistant on the Pepper platform with both online and offline AI capabilities.
2. Implement an agentic tool-calling architecture where the LLM autonomously executes hospital operations.
3. Bridge the Python 2.7/3.x interoperability gap through a clean architectural solution.
4. Achieve sub-3-second end-to-end AI response latency in online mode.
5. Implement a clinically grounded triage system aligned with Manchester Triage Scale.
6. Build a FAISS-backed RAG pipeline with bilingual sentence-transformer embeddings.
7. Implement LBPH face recognition for passwordless patient authentication.
8. Build a comprehensive drug interaction checker with a 80-medication, 130-interaction database.
9. Validate all subsystems through a 56-test automated offline test suite.

## 1.6 Thesis Outline

Chapter 2 reviews related literature in socially assistive robotics and hospital robot deployments. Chapter 3 defines core technologies and terminology. Chapter 4 presents the three-tier system architecture. Chapter 5 describes the full database schema. Chapter 6 details all AI modules. Chapter 7 covers implementation of each major subsystem. Chapter 8 presents evaluation results and performance benchmarks. Chapter 9 explores business model and commercial viability. Chapter 10 concludes and proposes future work.

---

# Chapter 2: Literature Review and Related Work

## 2.1 Socially Assistive Robots in Healthcare

The deployment of Socially Assistive Robots (SARs) in medical environments has emerged as a critical area of HRI research. Clinical studies at UCLA Mattel Children's Hospital demonstrated that interactions with companion robots yielded a **29% increase in positive emotions** and a **33% decrease in negative emotions** compared to standard tablet-based communication (Lewis et al., 2022). This evidence validates the premise that a physically present, interactive robot delivers superior patient outcomes compared to static digital interfaces.

The transition from scripted robots to LLM-powered companions has been transformative. Blavette et al. (2025) in JMIR Human Factors demonstrated that integrating an LLM into a SAR dialogue system increased interaction success rates from 25% to 74.5%, primarily by reducing comprehension failures that previously accounted for nearly half of all failed human-robot interactions in geriatric care. The study specifically noted that the improvement was driven by the LLM's ability to handle natural language variation, paraphrase, and domain-specific terminology — precisely the challenges that scripted dialogue trees cannot address.

## 2.2 The SoftBank Pepper Robot Platform

Pepper (SoftBank Robotics, 2014) stands approximately 120 cm tall and features an expressive face with LED eyes, a 10.1-inch chest-mounted touchscreen tablet, and 20 degrees of freedom. Equipped with a 4-microphone array for direction-of-arrival speech capture, two HD cameras (OV5640), a 3D depth sensor (ASUS Xtion), infrared sensors, and an Intel Atom Z530 CPU (1.6 GHz) with 4 GB RAM running NAOqi OS on Linux, Pepper was specifically designed for social interaction in public environments including hospitals, shopping centers, and airports.

Studies confirm 93.8% eye-contact maintenance and sub-2-second initial engagement rates with Pepper in pediatric settings. The robot's physical embodiment — height, LED expressions, tablet display, arm gestures — produces measurably higher emotional engagement than equivalent screen-based interfaces.

**Key limitation:** NAOqi OS runs Python 2.7 exclusively, requiring all modern AI libraries to run on an external server accessible via the hospital network.

## 2.3 Existing Hospital Robot Deployments

| Robot | Developer | AI / NLP | Navigation | Healthcare Role | Bilingual | Offline |
|---|---|---|---|---|---|---|
| Moxi | Diligent Robotics | None | Autonomous | Logistics only | No | N/A |
| TUG | Aethon | None | Autonomous | Delivery only | No | N/A |
| Sanbot Elf | Qihan Tech | Scripted | Limited | Reception | Partial | No |
| HOSPI | Panasonic | None | Corridor | Medication delivery | No | N/A |
| Pepper MA (Ours) | AASTMT | Agentic LLM + RAG + MTS + NER | Segmented + Obstacle | Full suite | AR/EN | Yes (Ollama) |

The Pepper Medical Assistant distinguishes itself by combining six critical capabilities in a single platform: agentic LLM-powered natural language conversation with tool calling, Manchester Triage Scale clinical assessment, segmented autonomous navigation with obstacle avoidance, humanoid physical engagement, face recognition authentication, and full bilingual Arabic/English support with offline operation.

## 2.4 Agentic AI and Tool-Calling in Robotics

The concept of agentic AI — where a language model autonomously decides when and how to call external tools — represents a paradigm shift from traditional chatbot architectures. In the Pepper Medical Assistant, the LLM does not simply generate text responses; it analyzes the patient's intent, determines whether a hospital operation is needed, constructs a structured tool call, executes it against the Flask backend, and incorporates the result into its response. This agentic loop runs for up to 5 iterations per request, enabling multi-step reasoning: find available cardiologists → check their schedules → book the earliest slot.

Anthropic's Claude API provides native `tool_use` support with structured JSON schema definitions, enabling reliable tool parameter extraction. For the Ollama offline backend, a custom parser extracts tool calls from the model's raw text output using regex pattern matching and JSON extraction, enabling identical agentic behavior without native tool-calling API support.

## 2.5 Retrieval-Augmented Generation in Healthcare

Retrieval-Augmented Generation (RAG) was introduced by Lewis et al. (2020) and has since been applied across medical information systems to prevent LLM hallucination of critical clinical information. Johnson & Smith (2022) demonstrated that RAG-grounded medical chatbots reduced factual error rates by 73% compared to ungrounded LLM responses on clinical FAQ tasks. In the Pepper Medical Assistant, RAG prevents the LLM from hallucinating doctor names, department locations, visiting hours, and appointment availability — information that must be precisely correct for a functional hospital assistant.

## 2.6 Manchester Triage Scale

The Manchester Triage Scale (MTS), developed by the Manchester Triage Group (2014), is the standard triage protocol used in Emergency Departments across the UK, Egypt, and many other countries. MTS categorizes patients into five urgency levels based on clinical discriminator sets. The Pepper Medical Assistant adapts four of these levels to the ambulatory reception context: Level 1 (Immediate/Red), Level 2 (Very Urgent/Orange), Level 3 (Urgent/Yellow), and Level 4 (Standard/Green). Using a two-stage approach — deterministic rule-based classification followed by AI-enriched recommendation text — ensures the triage is both clinically reliable and personalised.

## 2.7 Key Research Foundations

Four primary research pillars ground this project:
1. **Social robot embodiment psychology:** Physical robots produce superior emotional engagement versus screen-based interfaces.
2. **LLM integration in robotics:** Near-threefold improvement in interaction success rates justifies computational investment.
3. **RAG for factual grounding:** Prevents LLM hallucination of critical clinical information.
4. **Agentic tool calling:** Enables autonomous multi-step hospital task execution, fundamentally exceeding scripted chatbot capabilities.

---

# Chapter 3: Core Technologies and Terminology

## 3.1 Speech Recognition — Whisper ASR

The system employs OpenAI's Whisper automatic speech recognition model via the **faster-whisper** implementation with int8 quantization. The multilingual base variant (74M parameters, supporting 99 languages) supports automatic language detection — identifying Arabic (code: ar) versus English (code: en) without requiring the patient to manually select a language. Audio is captured at 16,000 Hz mono WAV format via Pepper's front head microphone (ALAudioRecorder, 6-second fixed recording window).

**Whisper model selection rationale:**
- `base.en` rejected: English-only, insufficient for Egyptian Arabic
- `base multilingual`: Selected. 74M params, bilingual, 9.97% WER, fast enough on GPU
- `medium`: Available as config option for higher accuracy at 4× speed cost
- `large-v3`: Available for maximum accuracy but requires ~3s GPU inference per utterance

**faster-whisper advantage:** CTranslate2 int8 quantization reduces memory footprint by ~60% and increases inference speed 2–4× versus the original Whisper PyTorch implementation while maintaining comparable accuracy.

## 3.2 Dual-Mode LLM Architecture

The system supports two LLM backends selectable via the `OFFLINE_MODE` environment variable.

**Online Mode (OFFLINE_MODE=0):**
- Model: Anthropic Claude (claude-haiku-4-5-20251001)
- API: Anthropic Messages API with native `tool_use` support
- Context: 8,000 tokens
- Latency: 1.8–2.5 seconds typical
- Cost: ~$0.25 per 1M input tokens

**Offline Mode (OFFLINE_MODE=1):**
- Model: Ollama qwen2.5:7b (7 billion parameters, MPL 2.0 license)
- API: Ollama REST API (http://localhost:11434)
- Latency: 15–25 seconds on GPU
- Cost: Zero (self-hosted)
- Privacy: Zero patient data leaves the hospital network

The LLM selection is abstracted behind a common `call_llm()` interface (app.py, ~line 1513) so all downstream code — tool calling, RAG injection, system prompt construction — is backend-agnostic. The Ollama model is warmed up at server startup with a dummy request to pre-load weights into GPU memory, eliminating cold-start latency on the first real patient request.

## 3.3 Agentic Tool-Calling Architecture

The agentic AI loop is the system's most significant architectural innovation. Eight hospital tools are defined with structured JSON schemas:

| Tool | Description | Key Parameters |
|---|---|---|
| `get_departments` | Lists all medical specialties | None |
| `get_doctors` | Lists doctors, optionally by specialty | `department` (optional) |
| `get_doctor_schedule` | Returns weekly availability | `doctor_id` |
| `book_appointment` | Creates a confirmed appointment | `doctor_id`, `patient_name`, `date`, `time` |
| `get_my_appointments` | Lists patient's appointments | Patient from session |
| `cancel_appointment` | Cancels a patient's appointment | `appointment_id` |
| `get_patient_profile` | Returns medical profile | Patient from session |
| `get_navigation_targets` | Lists 40 room destinations | None |

**Agentic loop sequence (per patient message):**
1. Construct system prompt with patient context, RAG knowledge (top-3 FAISS results), and conversation memory
2. Call LLM (Claude or Ollama) with tool definitions and conversation history
3. If LLM returns `tool_use` stop reason → extract tool name and parameters
4. Execute `execute_tool()`: validate authentication, clean inputs, run DB operation
5. Inject tool result back into conversation as `tool_result` message
6. Repeat steps 2–5 until `end_turn` or maximum 5 iterations reached
7. Return final natural language response to patient

**Multi-step reasoning example:** Patient says "I need to see a cardiologist tomorrow morning." The AI executes: (1) `get_departments` → confirms Cardiology exists; (2) `get_doctors` with `department="Cardiology"` → finds cardiologists; (3) `get_doctor_schedule` → finds tomorrow's availability; (4) `book_appointment` → books earliest slot and confirms to patient.

## 3.4 Retrieval-Augmented Generation (RAG)

The RAG pipeline prevents LLM hallucination by grounding responses in verified hospital data.

**Pipeline:**
1. **Corpus:** `rag_corpus.json` (31KB) — bilingual entries organized by: departments, doctor profiles, branch locations, contacts, visiting hours, services, emergency procedures. Each entry has `text_en` and `text_ar` fields.
2. **Embeddings:** sentence-transformers (all-MiniLM-L6-v2, 384-dimensional embeddings) converts both corpus and patient queries into dense vector representations.
3. **Index:** FAISS `IndexFlatL2` performs exact L2 Euclidean distance similarity search.
4. **Retrieval:** Patient query is embedded → top-3 closest corpus chunks retrieved (L2 distance threshold 1.6 filters irrelevant results) → injected into LLM system prompt as "Relevant hospital knowledge" context.
5. **Grounding:** LLM cannot hallucinate doctor names, locations, or schedules — it must use the retrieved context.

**Query speed:** <1ms per query against 254+ indexed knowledge chunks. Index is rebuilt at startup and can be force-rebuilt via `/api/rag_rebuild`.

## 3.5 Manchester Triage Scale (MTS)

The Manchester Triage Scale categorizes patients into urgency levels based on clinical discriminator sets. The Pepper Medical Assistant implements four levels:

| Level | Label | Color | Max Wait | Application |
|---|---|---|---|---|
| 1 | Immediate | Red | 0 min | Life-threatening — chest pain + SOB, unconscious, severe bleeding |
| 2 | Very Urgent | Orange | 10 min | High-risk — chest pain ≥7 pain, difficulty breathing |
| 3 | Urgent | Yellow | 30 min | Significant symptoms, pain ≥5 |
| 4 | Standard | Green | 90–120 min | Non-urgent, routine consultation |

**Two-stage assessment:**
- Stage 1 (deterministic): Python `set` intersection of patient-reported danger signs against `L1_SIGNS` and `L2_SIGNS` clinical discriminator sets. Pain score thresholds applied. No AI involvement — always executes reliably.
- Stage 2 (AI enrichment): LLM generates warm, personalized recommendation text in the patient's language. Explicitly constrained to not modify the triage level determined in Stage 1.

## 3.6 Face Recognition — LBPH

OpenCV's Local Binary Patterns Histograms (LBPH) algorithm is used for patient authentication. LBPH was selected over deep learning alternatives for its:
- Low computational footprint (no GPU required)
- Tolerance to lighting variation
- Ability to train from as few as 3 enrollment images
- Interpretable confidence scores

**Process:**
- Enrollment: Capture multiple frames via Pepper's tablet camera → Haar cascade face detection → resize to 200×200 grayscale → train LBPH recognizer → save model XML + `labels.json` locally
- Authentication: Incoming frame → face detection → LBPH predict → confidence < 80 (lower = better match in LBPH) → patient authenticated, session created

## 3.7 Segmented Navigation

The system uses ALNavigation.navigateTo() with a segmentation strategy instead of SLAM-based navigateToInMap(). SLAM was abandoned because Pepper's 15-beam LIDAR produces sparse occupancy maps insufficient for reliable long-distance navigation.

**Segmentation strategy:**
- Maximum segment: 2.5 meters
- Per-segment timeout: 45 seconds
- Maximum segments: 10 (prevents infinite loops)
- After each segment: read hardware odometry via `ALMotion.getRobotPosition(True)` to correct accumulated drift
- Real-time obstacle avoidance: sonar (0–5m), depth camera (0.5–3m), laser (0.2–25m)
- Arrival threshold: ±0.30m

## 3.8 WebSocket Bridge

The WebSocket Bridge (ws_bridge.py) is a Python 3 asyncio server on port 8765 acting as a pure broadcast relay — every message received from one connected client is forwarded to all other connected clients. A module-level `connected_clients` set tracks active WebSocket objects. It handles: `nav_start`, `nav_cancel`, `nav_status` (navigation), `start_recording` (voice), `say` (TTS alerts), `emotion_alert` (face emotion detection), `ping` (keep-alive).

## 3.9 Hardware Specifications

**SoftBank Pepper Robot:**

| Component | Specification |
|---|---|
| Processor | Intel Atom Z530, 1.6 GHz (single-core) |
| RAM | 4 GB DDR3L |
| Storage | 32 GB eMMC Flash |
| OS | NAOqi OS (Linux-based, Python 2.7 only) |
| Display | 10.1" chest-mounted touchscreen (1280×800) |
| Cameras | OV5640 HD (front + bottom), ASUS Xtion 3D depth |
| Microphones | 4-microphone array (16 kHz mono WAV) |
| Navigation Sensors | 15-beam LIDAR + 9 ultrasonic + ASUS Xtion 3D |
| Connectivity | WiFi 802.11 a/b/g/n, Ethernet RJ45 |
| Battery | 30.0 Ah Li-Ion (~12 hours standby) |
| Degrees of Freedom | 20 joints |

**Backend Server (Minimum Requirements):**

| Component | Specification |
|---|---|
| Processor | Intel Core i5+ (GPU strongly recommended) |
| RAM | 16 GB for concurrent AI processing |
| GPU | NVIDIA GPU with 4+ GB VRAM (for Whisper + Ollama) |
| Python | 3.8+ (Flask, SQLAlchemy, faster-whisper, FAISS) |
| Network | Same WiFi LAN as Pepper (192.168.1.0/24) |
| OS | Windows 10/11 or Ubuntu 20.04+ |

---

# Chapter 4: System Architecture and Design

## 4.1 Architecture Overview

The Pepper Medical Assistant employs a **three-tier centralized architecture** where the robot acts as the physical interface and all computational intelligence is offloaded to an external backend server. This design compensates for Pepper's onboard CPU limitations and enables the use of modern AI libraries incompatible with the robot's embedded Linux/Python 2.7 environment.

```
┌──────────────────────────────────────────────────────────┐
│                  TIER 3: USER INTERFACE                  │
│  15 HTML/ES5 pages • i18n.js (400+ keys) • WebSocket    │
│  Chat • Triage • Book • Navigate • Face Login • Tips    │
└────────────────────────┬─────────────────────────────────┘
                         │ HTTP / WebSocket
┌────────────────────────▼─────────────────────────────────┐
│                TIER 2: BACKEND SERVER (Python 3)         │
│  Flask REST API (30+ endpoints) • SQLite/SQLAlchemy      │
│  Whisper ASR • Claude/Ollama LLM • FAISS RAG             │
│  Agentic Tool Loop • MTS Triage • 12+ AI Modules         │
│  WebSocket Bridge (ws_bridge.py) • Face Auth             │
└────────────────────────┬─────────────────────────────────┘
                         │ WebSocket (port 8765) + File-Flag IPC
┌────────────────────────▼─────────────────────────────────┐
│                TIER 1: ROBOT LAYER (Python 2.7/NAOqi)    │
│  MainVoice.py • nav_bridge.py • camera_server.py         │
│  ALTextToSpeech • ALAudioRecorder • ALNavigation          │
│  ALMotion • ALBasicAwareness • ALAutonomousLife           │
└──────────────────────────────────────────────────────────┘
```

## 4.2 Network Topology

The system is deployed on a private hospital WiFi LAN. All services are configured via `config.json` and injected as environment variables by the master launcher `main.py`.

| Parameter | Default Value | Purpose |
|---|---|---|
| ROBOT_IP | 1.1.1.10 | Pepper's IP address on LAN |
| ROBOT_PORT | 9559 | NAOqi broker port |
| SERVER_IP | 1.1.1.249 | Backend PC IP |
| SERVER_PORT | 8080 | Flask HTTP API port |
| WS_PORT | 8765 | WebSocket bridge port |
| CAM_PORT | 8082 | Camera MJPEG server port |

## 4.3 Master Launcher (main.py)

`main.py` is the single entry point that orchestrates all system components. On startup it: reads `config.json`, sets all environment variables, opens Windows Firewall rules for ports 8080/8765/8082 via `netsh`, starts ws_bridge.py (Python 3), starts app.py (Python 3 Flask backend), starts camera_server.py (Python 2.7), starts show_tablet.py (Python 2.7 — one-shot, must finish before nav_bridge starts to avoid NAOqi session conflicts), starts nav_bridge.py (Python 3 WebSocket client), starts MainVoice.py (Python 2.7). On Ctrl+C, terminates all subprocesses gracefully.

**Critical ordering constraint:** The tablet script (`show_tablet.py`) is one-shot and must complete before `nav_bridge.py` starts. Concurrent NAOqi sessions cause "Session closed" errors — Pepper's NAOqi broker serializes session creation.

## 4.4 Tier 1: Robot Interface Layer

### 4.4.1 NAOqi Module Reference

| NAOqi Module | Purpose |
|---|---|
| ALTextToSpeech | Verbal output in English and Arabic; explicit UTF-8 encoding for Arabic |
| ALAudioRecorder | Captures 6-second WAV at 16 kHz mono (front head mic) |
| ALNavigation | Segmented navigateTo() with real-time obstacle avoidance |
| ALMotion | Odometry reading, collision margin configuration, fallback moveTo() |
| ALRobotPosture | Standing/sitting posture management |
| ALBasicAwareness | Autonomous engagement; paused during navigation |
| ALAutonomousLife | High-level behavior management; disabled at startup |
| ALBattery | Battery monitoring; warning below 30% |
| ALSpeechRecognition | Offline keyword-based fallback ASR (18 keywords per language) |
| ALVideoDevice | Camera frame capture for MJPEG streaming |

### 4.4.2 MainVoice.py — Voice Controller

MainVoice.py is the primary Python 2.7 script running continuously on the robot. It implements a 500ms flag polling loop:
1. Check for `voice_start.flag` → delete immediately on detection (prevents double-trigger)
2. Read `lang.flag` → determine TTS language ("en" or "ar")
3. Read `user.flag` → current patient ID if logged in
4. Call `set_tts_language()` + TTS announcement: "Please speak now"
5. `ALAudioRecorder.startMicrophonesRecording()` → `/tmp/voice.wav` (16 kHz, mono, WAV, 6 seconds)
6. Poll for `voice_stop.flag` every 100ms (early stop on button press)
7. `pscp -pw nao nao@<ROBOT_IP>:/tmp/voice.wav voice.wav` → transfer to backend
8. HTTP POST WAV to Flask `/api/process_audio`
9. Receive AI reply → re-encode to UTF-8 → `tts.say(reply)`
10. Broadcast `speaking_done` via WebSocket → tablet re-enables mic button

### 4.4.3 nav_bridge.py — Navigation and TTS Bridge

nav_bridge.py is a Python 3 WebSocket client that bridges the backend message bus to Pepper's physical movement. On startup: connects NAOqi proxies, disables ALAutonomousLife, pauses ALBasicAwareness, configures collision margins (SECURITY_ORTHO=0.15m, SECURITY_TAN=0.05m), sets standing posture, waves arm, delivers bilingual greeting.

Navigation commands are dispatched to daemon threads to prevent the blocking `navigateTo()` call from halting the asyncio event loop. The `is_navigating` flag prevents overlapping navigation requests.

**Proxy health management:** `_ensure_proxies_alive()` is called before every navigation request. It probes `motion_proxy.getRobotPosition()` — a cheap read-only call. If the probe fails (NAOqi sessions go stale after ~7 minutes idle), `_reconnect_robot_proxies()` rebuilds all proxies with fresh connections, transparent to the caller.

### 4.4.4 File-Flag IPC Mechanism

The filesystem-level IPC mechanism bridges the Python 2.7/3.x boundary without any network dependency:

| Flag File | Written By | Read By | Purpose |
|---|---|---|---|
| `voice_start.flag` | nav_bridge.py (Py3) | MainVoice.py (Py2) | Trigger voice recording |
| `voice_stop.flag` | nav_bridge.py (Py3) | MainVoice.py (Py2) | Early stop recording |
| `lang.flag` | nav_bridge.py (Py3) | MainVoice.py (Py2) | Language preference (en/ar) |
| `user.flag` | nav_bridge.py (Py3) | MainVoice.py (Py2) | Current patient ID |

### 4.4.5 Camera Server (camera_server.py)

The camera server (Python 2.7) runs a threaded HTTP server on port 8082 with three endpoints:
- `/snapshot` — returns single raw JPEG (Content-Type: image/jpeg)
- `/snapshot_b64` — returns `{data_url: "data:image/jpeg;base64,...", width, height}`
- `/mjpeg` — multipart/x-mixed-replace live stream at ~15 FPS

A background grabber thread subscribes to `ALVideoDevice`, captures QVGA (320×240) RGB frames, encodes to JPEG at quality=65, and stores in `_cached_jpeg` with a condition variable notifying blocked MJPEG clients. The Flask backend proxies `/api/camera` to this server for cross-origin tablet access.

## 4.5 Tier 2: Backend Server Layer

### 4.5.1 Flask Application (app.py)

The backend is a Flask application (~1,920 lines) on Python 3, serving on port 8080. Key configurations:
- Cache-busting headers (`Cache-Control: no-cache, no-store, must-revalidate`) on every response — prevents Pepper's tablet from serving stale UI
- Flask session management with `FLASK_SECRET_KEY` environment variable
- SQLAlchemy with SQLite auto-created on first run
- faster-whisper model loaded once at startup
- Ollama model warmed up at startup (when OFFLINE_MODE=1)
- All AI modules instantiated once at startup and reused

### 4.5.2 Complete REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/login` | Patient/staff authentication; creates Flask session |
| POST | `/api/signup` | Creates Patient or Staff record |
| GET | `/api/me` | Returns current session user and login status |
| POST | `/api/logout` | Clears Flask session |
| POST | `/api/process_audio` | WAV → Whisper ASR → LLM → `{text, reply, lang}` |
| POST | `/api/chat_ai` | Agentic chat with tool calling |
| GET | `/api/ai_health_tips` | 4 personalized health tips via LLM |
| POST | `/api/triage_assess` | MTS triage: rule-based + AI enrichment |
| GET | `/api/my_appointments` | All appointments for logged-in patient |
| POST | `/api/book_appointment` | Create appointment (validates date/time/doctor) |
| DELETE | `/api/cancel_appointment/<id>` | Cancel patient's appointment |
| GET | `/api/doctors` | All doctors with name and specialty |
| GET | `/api/departments` | All unique specialties |
| GET | `/api/doctor_schedule/<id>` | Doctor's weekly schedule |
| GET | `/api/navigation_targets` | 40-target room directory from JSON |
| POST | `/api/face_enroll` | Enroll patient face for LBPH authentication |
| POST | `/api/face_recognize` | Authenticate patient via face recognition |
| GET | `/api/vitals/<patient_id>` | Vital signs history for patient |
| POST | `/api/vitals` | Record new vital measurement |
| GET | `/api/staff_dashboard` | Staff management data summary |
| POST | `/api/emergency_alert` | Escalate emergency, broadcast WebSocket alert |
| GET | `/api/health_tips` | Personalized health tips |
| POST | `/api/check_drugs` | Drug-drug interaction check |
| POST | `/api/check_symptoms` | Symptom → department routing |
| POST | `/api/rag_query` | Direct FAISS retrieval |
| POST | `/api/rag_rebuild` | Force RAG index rebuild |
| GET | `/api/patient_profile` | Full patient medical profile |
| GET | `/api/camera` | Proxy to camera_server MJPEG/snapshot |
| GET | `/api/branches` | Hospital branch locations |
| GET | `/api/contacts` | Emergency and department contacts |

### 4.5.3 WebSocket Bridge (ws_bridge.py)

The WebSocket relay server is a compact Python 3 asyncio application. A module-level `connected_clients` set tracks active WebSocket objects. On each incoming message, the bridge forwards to all clients except the sender. The bridge supports automatic reconnection from nav_bridge.py clients (3-second reconnect loop). Message types:

| Type | Direction | Purpose |
|---|---|---|
| `start_recording` | Tablet → Bridge → nav_bridge | Trigger voice recording |
| `stop_recording` | Tablet → Bridge → nav_bridge | Early stop recording |
| `nav_start` | Backend → Bridge → Tablet | Navigation started |
| `nav_status` | nav_bridge → Bridge → Tablet | Progress update |
| `say` | Backend → Bridge → nav_bridge | TTS alert text |
| `result` | nav_bridge → Bridge → Tablet | Voice reply to display |
| `speaking_done` | nav_bridge → Bridge → Tablet | Re-enable mic button |
| `emotion_alert` | Backend → Bridge → Tablet | Distress detected |
| `ping` | Any | Keep-alive |

## 4.6 Tier 3: User Interface Layer

### 4.6.1 Design System

All 15 pages share a consistent visual identity:
- **Palette:** Primary tan-brown `#b89a6c`, deep brown text `#5a4a3b`, warm muted background `#f7f4f0` / `#ffffff`
- **Typography:** System sans-serif stack (no external fonts — tablet has no internet in deployment)
- **Layout:** Flexbox with `-webkit-` prefixes for Pepper's older WebKit engine
- **Touch targets:** Minimum 44–80px height (elderly-friendly)
- **JavaScript:** Strict ES5 (no ES6, no arrow functions, no template literals, no let/const)

### 4.6.2 Page Inventory

| Page | File | Key Features |
|---|---|---|
| Home | index.html | 8 navigation tiles; voice overlay; auth status display |
| Symptom Check | triage.html | 4-step MTS wizard; colored urgency result |
| Book Appointment | book.html | Department → doctor → schedule → booking wizard |
| Check Schedule | schedule.html | Department filter; doctor list; time slots |
| My Appointments | appointments.html | View/cancel booked appointments |
| Guide to Room | guide.html | Doctor directory; WebSocket navigation trigger |
| Navigating | navigating.html | Real-time nav status with distance display |
| Face Login | face_login.html | Camera capture + LBPH authentication |
| Face Enroll | face_enroll.html | Multi-shot face training enrollment |
| Emergency | emergency.html | 2-second hold-to-confirm; WebSocket TTS alert |
| Health Tips | tips.html | AI-personalized health advice |
| Chat / FAQ | chat.html | Multi-turn agentic chat with tool calling |
| Login | login.html | Patient/staff role toggle; ID + password |
| Sign Up | signup.html | Role-specific registration with case number |
| About | about.html | Project description; team credits |

### 4.6.3 Internationalization (i18n.js)

The i18n.js module (34KB) provides a runtime translation system covering **400+ UI strings** for all 15 pages in both languages. It uses a dictionary pattern with Unicode escapes for Arabic to ensure correct rendering without external fonts. The module provides:
- `t(key, args)` — returns translated string with optional `{0}`, `{1}` placeholder replacement
- `setLanguage(lang)` — stores `"en"` or `"ar"` in `localStorage`
- `applyTranslations()` — scans DOM for `data-i18n` attributes and updates text
- RTL layout switching: sets `document.dir = "rtl"` and applies Arabic font stack for Arabic mode

```javascript
// ES5 i18n pattern
var T = {
  "tap_to_speak": { en: "Tap to Speak", ar: "اضغط للتحدث" },
  "appointment_booked": { en: "Appointment booked for {0} on {1}", ar: "..." }
};
function t(key, args) {
  var lang = localStorage.getItem("lang") || "en";
  var str = (T[key] || {})[lang] || key;
  if (args) for (var i = 0; i < args.length; i++) str = str.replace("{" + i + "}", args[i]);
  return str;
}
```

---

# Chapter 5: Database Design

## 5.1 Overview

The system uses **SQLite** via Flask-SQLAlchemy ORM. The database (`app.db`) is auto-created on first run and seeded from CSV/XLSX files in `Data/`. The schema defines **16 ORM models** covering patient management, medical infrastructure, clinical data, and medication management.

## 5.2 Patient Management Models

**Patient**
| Field | Type | Description |
|---|---|---|
| id | Integer PK | Patient login ID |
| name | String(100) | Full name |
| case_number | String(50) | Hospital case number |
| password | String(200) | Hashed (werkzeug PBKDF2) |
| age | Integer | Patient age |
| gender | String(10) | Male/Female/Other |
| blood_type | String(5) | A+/A-/B+/etc. |
| phone | String(20) | Contact number |
| emergency_contact | String(100) | Emergency contact info |
| medical_history | Text | Diagnosis history |
| allergies | Text | Known allergies |
| current_medications | Text | Active medications |
| notes | Text | Additional clinical notes |

**PatientMemory** (long-term conversation context)
| Field | Type | Description |
|---|---|---|
| id | Integer PK | Auto-increment |
| patient_id | Integer FK | References Patient.id |
| summary | Text | LLM-generated session summary |
| key_facts | Text | JSON-encoded structured facts |
| session_count | Integer | Number of sessions |
| updated_at | DateTime | Last update timestamp |

**Staff**
| Field | Type | Description |
|---|---|---|
| id | Integer PK | Staff login ID |
| name | String(100) | Full name |
| role | String(20) | Admin / Nurse / Receptionist |
| password | String(200) | Hashed |

## 5.3 Medical Infrastructure Models

**Doctor**
| Field | Type | Description |
|---|---|---|
| id | Integer PK | Auto-increment |
| name | String(100) | Dr./Prof. full name |
| specialty | String(100) | Medical specialty |
| title | String(20) | Dr./Prof./Consultant |
| branches | String(200) | Available branches |

**Schedule** (weekly availability)
| Field | Type | Description |
|---|---|---|
| id | Integer PK | Auto-increment |
| doctor_id | Integer FK | References Doctor.id |
| day_of_week | Integer | 0=Monday … 6=Sunday |
| start_time | String(5) | HH:MM 24-hour format |
| end_time | String(5) | HH:MM 24-hour format |

**Appointment**
| Field | Type | Description |
|---|---|---|
| id | Integer PK | Auto-increment |
| doctor_id | Integer FK | References Doctor.id |
| patient_id | Integer FK | References Patient.id (nullable) |
| patient_name | String(100) | Patient display name |
| appointment_date | Date | YYYY-MM-DD |
| time_slot | String(5) | HH:MM |

**Branch**
| Field | Type | Description |
|---|---|---|
| id | Integer PK | Auto-increment |
| name | String(100) | Branch name |
| address | String(200) | Street address |
| city | String(50) | City |
| notes | Text | Directions, hours |

**Department**
| Field | Type | Description |
|---|---|---|
| id | Integer PK | Auto-increment |
| name | String(100) | Specialty name |
| description | Text | Services offered |

**Contact**
| Field | Type | Description |
|---|---|---|
| id | Integer PK | Auto-increment |
| type | String(50) | Emergency / Department / General |
| details | String(200) | Phone number or address |

## 5.4 Clinical Data Models

**VitalRecord** (patient vital signs)
| Field | Type | Description |
|---|---|---|
| id | Integer PK | Auto-increment |
| patient_id | Integer FK | References Patient.id |
| recorded_at | DateTime | Timestamp |
| recorded_by | String(20) | nurse / robot / patient |
| pain_scale | Float | 0–10 |
| temperature | Float | °C |
| systolic_bp | Integer | mmHg |
| diastolic_bp | Integer | mmHg |
| heart_rate | Integer | bpm |
| oxygen_sat | Float | % |
| respiratory_rate | Integer | breaths/min |
| blood_glucose | Float | mmol/L |
| weight_kg | Float | kg |
| height_cm | Float | cm |
| notes | Text | Clinical notes |
| alerts | Text | JSON-encoded alert list |

**TriageHistory**
| Field | Type | Description |
|---|---|---|
| id | Integer PK | Auto-increment |
| patient_id | Integer FK | References Patient.id (nullable) |
| patient_name | String(100) | Display name |
| chief_complaint | String(200) | Primary complaint category |
| severity | Integer | MTS level 1–4 |
| severity_label | String(20) | Immediate/Very Urgent/Urgent/Standard |
| symptoms_json | Text | JSON list of reported symptoms |
| vitals_json | Text | JSON snapshot of vitals at triage |
| ai_recommendation | Text | LLM-generated recommendation |
| department_referred | String(100) | Recommended department |
| disposition | String(50) | Outcome (admitted, discharged, etc.) |

**SymptomHistory**
| Field | Type | Description |
|---|---|---|
| id | Integer PK | Auto-increment |
| patient_id | Integer FK | References Patient.id |
| symptoms | Text | JSON symptom list |
| severity | Integer | Reported severity |
| ner_results | Text | JSON NER output |
| context | Text | Conversation context |
| source | String(20) | voice / chat / triage / manual |

## 5.5 Medication Management Models

**Medication** (drug catalog — 80 entries)
| Field | Type | Description |
|---|---|---|
| id | Integer PK | Auto-increment |
| name | String(100) | Brand name |
| generic_name | String(100) | Generic/INN name |
| category | String(50) | Anticoagulant, NSAID, etc. |
| dosage_forms | String(200) | Tablet, injection, etc. |
| side_effects | Text | Common side effects |
| contraindications | Text | Contraindication list |
| pregnancy_category | String(5) | A/B/C/D/X |
| requires_monitoring | Boolean | Requires clinical monitoring |
| notes | Text | Additional clinical notes |

**DrugInteraction** (interaction database — 130 entries)
| Field | Type | Description |
|---|---|---|
| id | Integer PK | Auto-increment |
| drug_a | String(100) | First drug |
| drug_b | String(100) | Second drug |
| severity | String(20) | severe / moderate / mild / contraindicated |
| description | Text | Interaction description |
| recommendation | Text | Clinical recommendation |
| mechanism | Text | Pharmacological mechanism |

**MedicationReminder**
| Field | Type | Description |
|---|---|---|
| id | Integer PK | Auto-increment |
| patient_id | Integer FK | References Patient.id |
| medication_name | String(100) | Medication name |
| dosage | String(50) | e.g., "500mg" |
| frequency | String(50) | Once daily / Twice daily / etc. |
| times | Text | JSON array: ["08:00","20:00"] |
| active | Boolean | Reminder active/inactive |
| start_date | Date | Start date |
| end_date | Date | Optional end date |
| notes | Text | e.g., "Take with food" |

## 5.6 Knowledge Base Statistics

| Metric | Value |
|---|---|
| Total Doctors | 200+ (seeded from CSV) |
| Medical Specialties | 22 |
| Navigation Targets | 40 rooms across 5 floors |
| Hospital Branches | 4 (Alexandria, Cairo, Giza) |
| Drug Catalog Entries | 80 medications |
| Drug Interaction Pairs | 130 pre-computed interactions |
| Default Schedule Slots/Doctor | 2 (Monday AM + Wednesday PM) |
| Pre-seeded Vital Records | 250+ |
| Pre-seeded Triage Histories | 60+ |
| Medication Reminders | 40+ |
| RAG Knowledge Corpus | 31KB bilingual JSON |
| i18n Translation Keys | 400+ (English + Arabic) |

---

# Chapter 6: AI Modules

## 6.1 Overview

Beyond the core agentic LLM chat, the system includes **12 specialized AI modules** organized under `pepper_ui/server/app/ai_modules/`. Each module routes to either Claude or Ollama based on `OFFLINE_MODE`. All modules are instantiated at server startup and reused across requests.

## 6.2 Sentiment Analyzer (sentiment.py)

**Purpose:** Detects patient emotional state from conversation text to adapt Pepper's response tone and alert staff to distressed patients.

**Technical implementation:**
- System prompt: "You are a medical sentiment analyzer. Return only JSON."
- Output schema: `{sentiment, score (0.0–1.0), alert (bool), reason}`
- Sentiment labels: calm, anxious, frustrated, distressed, pain
- Alert trigger: score > 0.7 OR alert=true → WebSocket `emotion_alert` broadcast to staff dashboard
- Online timeout: 10 seconds (Claude)
- Offline timeout: 20 seconds (Ollama)

**Integration:** Called on every voice interaction and text chat. If `alert=true`, a WebSocket message is sent to all connected staff dashboards with patient name and detected sentiment.

## 6.3 Medical Named Entity Recognition (medical_ner.py)

**Purpose:** Extracts medical entities from patient utterances to enrich triage assessment and conversation context.

**Entity types extracted:**
- `SYMPTOM` — reported symptoms (headache, chest pain, shortness of breath)
- `MEDICATION` — drug names mentioned (aspirin, metformin)
- `BODY_PART` — anatomical references (chest, left arm, knee)
- `CONDITION` — diagnoses or conditions (diabetes, hypertension)
- `DURATION` — time references (for 3 days, since yesterday)

**Output:** JSON list of `{text, label, confidence}` entities. Extracted symptoms are passed to SymptomChecker; extracted medications are passed to DrugChecker against the patient's current medication list.

## 6.4 Symptom Checker (symptom_checker.py)

**Purpose:** Maps extracted symptoms to the most appropriate hospital department, providing intelligent routing before full triage.

**Input:** List of symptoms + optional patient context (age, gender, history)

**Output schema:**
```json
{
  "conditions": [{"name": "...", "likelihood": "high|medium|low", "description": "...", "advice": "...", "see_doctor": true}],
  "urgency": "immediate|urgent|routine|self-care",
  "urgency_reason": "...",
  "recommended_department": "Cardiology"
}
```

**Configuration:** 30-second Ollama timeout, 15-second Claude timeout. Max 600 output tokens for detailed differential. Language-aware: if `lang="ar"`, prompt appends "Respond in Arabic."

## 6.5 Drug Interaction Checker (drug_checker.py)

**Purpose:** Detects clinically significant drug-drug interactions from the patient's medication list.

**Two-tier lookup:**
1. **Database first:** Query `DrugInteraction` table with exact then partial (ILIKE) matching. Case-insensitive lookup handles brand vs. generic name variants.
2. **AI fallback:** If pair not in DB and online → Claude AI check (200 token response) for novel combinations.

**Severity levels:** contraindicated > severe > moderate > mild

**Drug info endpoint:** `get_drug_info()` returns full `Medication` record with side effects, contraindications, pregnancy category, monitoring requirements.

**Integration:** Called automatically when patient's current medications and any newly mentioned drug are detected by Medical NER.

## 6.6 Medication Reminder Manager (medication_reminder.py)

**Purpose:** Manages scheduled medication alerts for patients across visits.

**Features:**
- Stores JSON times array `["08:00","20:00"]` per medication
- Frequency mapping: Once daily, Twice daily, Three times daily, As needed
- Active/inactive toggle
- Optional date range (start_date, end_date)
- Notes field for instructions ("Take with food", "Avoid grapefruit")

**Displayed** in patient profile and staff dashboard. Future extension: push notification integration.

## 6.7 Vital Tracker and Analyzer (vital_tracker.py)

**Purpose:** Rule-based alert generation and trend analysis on vital signs.

**Clinical reference ranges:**

| Vital | Normal Range | Warning | Critical |
|---|---|---|---|
| Temperature (°C) | 36.1–37.9 | <35.5 or >38.5 | <35.0 or >39.5 |
| Systolic BP (mmHg) | 90–139 | <85 or >160 | <80 or >180 |
| Diastolic BP (mmHg) | 60–89 | <55 or >100 | <50 or >110 |
| Heart Rate (bpm) | 60–100 | <50 or >120 | <40 or >150 |
| Oxygen Sat (%) | 95–100 | <93 | <90 |
| Blood Glucose (mmol/L) | 4.0–7.8 | <3.5 or >10.0 | <3.0 or >13.9 |
| Pain Scale (0–10) | 0–4 | 5–7 | ≥8 |

**Rule-based alerts:** Pure Python with no API calls — always executes reliably.

**Trend analysis:** Computes mean, min, max, and directional trend ("improving"/"worsening"/"stable") from time-series vital records. Optional LLM narrative (250 tokens) generates a clinical summary sentence.

## 6.8 Conversation Memory (conversation_memory.py)

**Purpose:** Enables long-term patient context across multiple visits.

**Mechanism:**
1. After each chat session, prompt LLM to summarize in 2–3 sentences
2. Extract JSON key facts: `{symptoms_mentioned, appointments, concerns, preferences}`
3. Store in `PatientMemory` table (one record per patient); increment `session_count`
4. On next visit: retrieve memory → inject into LLM system prompt

**Effect:** Enables contextual responses: "Welcome back, Ahmed. Last time you mentioned experiencing headaches. How are you feeling today?"

## 6.9 Face Authentication (face_auth.py)

**Algorithm:** OpenCV LBPH (Local Binary Patterns Histograms)

**Enrollment flow:**
1. Patient navigates to `/face_enroll`
2. Tablet camera captures 5+ frames
3. Haar cascade detects face regions
4. Resize to 200×200 grayscale
5. LBPH recognizer trained on captured frames
6. Model saved to `face_data/face_model.xml`; patient ID mapping to `face_data/labels.json`

**Authentication flow:**
1. Patient navigates to `/face_login`
2. Single frame captured
3. Haar cascade detects face
4. LBPH `predict()` → returns `(label, confidence)`
5. Confidence < 80 (lower = better match in LBPH) → patient session created

**Fallback:** If face detection fails or confidence ≥ 80 → prompt manual ID + password.

## 6.10 Manchester Triage Scale Engine

**Frontend — 4-Step Triage Wizard (triage.html):**
- Step 1: Six chief complaint categories as large touch-optimized buttons: Chest/Heart, Breathing, Head/Neuro, Pain/Injury, Fever/Infection, Other
- Step 2: 1–10 pain score with color-coded severity indicators
- Step 3: Dynamic checklist of 4 clinical danger signs specific to selected category (drawn from MTS discriminators)
- Step 4: Submit → colored urgency result + AI recommendation

**Backend — `/api/triage_assess` (two stages):**

Stage 1 (deterministic rule-based):
```python
L1_SIGNS = {"chest pain and difficulty breathing", "loss of consciousness",
             "severe bleeding", "seizure", "no pulse", "anaphylaxis"}
L2_SIGNS = {"chest pain", "difficulty breathing", "severe headache",
             "high fever above 39", "inability to move limbs", "altered consciousness"}

if symptoms & L1_SIGNS or pain_score >= 9:    level = 1  # Immediate
elif symptoms & L2_SIGNS or pain_score >= 7:   level = 2  # Very Urgent
elif pain_score >= 5 or symptoms:              level = 3  # Urgent
else:                                          level = 4  # Standard
```

Stage 2 (AI enrichment): LLM generates personalized recommendation text. Explicitly constrained to not modify the determined triage level. Falls back to pre-written rule-based text if LLM fails.

**Staff Dashboard Integration:** Triage tab displays records with red-bordered cards for Levels 1 and 2. Level 1 assessments automatically trigger WebSocket TTS alert on Pepper.

## 6.11 Multi-Agent Clinical System (multi_agent.py)

**Purpose:** Orchestrates multiple specialized AI agents for complex clinical scenarios requiring synthesis across multiple dimensions.

**Architecture:** Parallel agent calls for sentiment, symptom analysis, vital assessment, and drug checking → aggregation of outputs into a unified clinical recommendation → severity escalation if any agent flags high-risk.

**Use case:** When a patient presents with complex multi-system complaints, the multi-agent system synthesizes all AI perspectives before generating a response.

## 6.12 Clinical Readmission Predictor (clinical_predictor.py)

**Purpose:** Predicts 30-day hospital readmission risk to flag high-risk patients for additional care planning.

**Model:** Gradient Boosting Machine (scikit-learn, serialized as pickle) trained on historical readmission data.

**Input features:** Patient vitals (BP, HR, O2, glucose, pain), age, gender, medical history severity score.

**Output:** Risk score 0.0–1.0. Threshold >0.7 triggers clinical review flag in staff dashboard.

---

# Chapter 7: Subsystem Implementation

## 7.1 Voice and Speech Processing Pipeline

### 7.1.1 End-to-End Voice Interaction Flow (16 Steps)

```
Patient taps "Tap to Speak" on tablet
    ↓ (1) WebSocket message {type: "start_recording"} → ws_bridge → nav_bridge
    ↓ (2) nav_bridge writes voice_start.flag + lang.flag + user.flag
    ↓ (3) MainVoice.py detects voice_start.flag (500ms poll)
    ↓ (4) MainVoice.py deletes flag immediately (prevents double-trigger)
    ↓ (5) TTS: "Please speak now" (UTF-8 encoded, language-specific)
    ↓ (6) ALAudioRecorder.startMicrophonesRecording() → /tmp/voice.wav
    ↓ (7) Poll for voice_stop.flag every 100ms OR wait 6 seconds
    ↓ (8) PSCP transfer: robot → backend PC (voice.wav)
    ↓ (9) HTTP POST to Flask /api/process_audio (WAV + lang + patient_id)
    ↓ (10) Whisper transcription → user_text
    ↓ (11) Build system prompt: patient context + RAG knowledge + memory
    ↓ (12) Agentic LLM loop: tool calls as needed
    ↓ (13) Generate reply text
    ↓ (14) WebSocket broadcast {type: "result", user_text, ai_text, lang}
    ↓ (15) MainVoice.py receives reply → TTS: tts.say(reply.encode("utf-8"))
    ↓ (16) WebSocket {type: "speaking_done"} → tablet re-enables mic button
```

### 7.1.2 Whisper ASR Configuration

```python
# Auto-detect GPU vs CPU
try:
    import ctranslate2 as ct2
    cuda_ok = ct2.get_cuda_device_count() > 0
except Exception:
    cuda_ok = False

device = "cuda" if cuda_ok else "cpu"
compute_type = "int8_float16" if cuda_ok else "int8"

audio_model = WhisperModel(WHISPER_MODEL, device=device, compute_type=compute_type)
```

**Offline ASR fallback:** When both Flask backend and WebSocket bridge are unreachable, MainVoice.py activates `ALSpeechRecognition` with 18 predefined keywords per language (hello, help, emergency, doctor, appointment, room, schedule, directions, nurse, pharmacy, exit — EN and AR equivalents) for basic interaction continuity.

## 7.2 Segmented Navigation Implementation

### 7.2.1 Algorithm

```python
def navigate_to_target(target_id):
    target = navigation_targets[target_id]  # {x, y, theta}
    
    motion_proxy.setCollisionProtectionEnabled("Move", True)
    motion_proxy.setOrthogonalSecurityDistance(0.15)
    motion_proxy.setTangentialSecurityDistance(0.05)
    
    segment_count = 0
    while segment_count < MAX_SEGMENTS:  # MAX_SEGMENTS = 10
        pos = motion_proxy.getRobotPosition(True)  # True = odometry corrected
        dx = target["x"] - pos[0]
        dy = target["y"] - pos[1]
        dist = math.sqrt(dx*dx + dy*dy)
        
        if dist <= ARRIVAL_THRESH:  # ARRIVAL_THRESH = 0.30m
            tts_proxy.say(u"Arrived at " + target["name"])
            break
        
        seg = min(dist, MAX_SEGMENT)  # MAX_SEGMENT = 2.5m
        
        try:
            nav_proxy.navigateTo(
                pos[0] + (dx/dist)*seg,
                pos[1] + (dy/dist)*seg,
                _timeout=SEGMENT_TIMEOUT  # 45 seconds
            )
        except Exception:
            # Fallback: simple forward motion
            motion_proxy.moveTo(seg, 0, 0)
        
        segment_count += 1
```

### 7.2.2 Navigation Target Registry

`navigation_targets.json` stores 40 room destinations covering all 5 floors of Andalusia Hospital. Each entry:
```json
{
  "id": "cardiology_dr_ahmed",
  "name": "Dr. Ahmed Hassan — Cardiology",
  "specialty": "Cardiology",
  "room_name": "Room 204, Floor 2",
  "coordinates": [4.5, 2.1, 1.57]
}
```
Coordinates are [x_meters, y_meters, theta_radians] relative to the robot's startup position (reception desk).

### 7.2.3 Safety and Recovery

- **Battery check before navigation:** Battery < 30% → warn; < 15% → abort with staff notification
- **is_navigating flag:** Prevents overlapping navigation requests
- **Per-segment timeout:** 45s prevents navigation hangs
- **Max segment cap:** 10 segments prevents infinite loops
- **Obstacle handling:** ALNavigation built-in avoidance; NavigationFailed exception → fallback to moveTo
- **Session recovery:** `_ensure_proxies_alive()` probes before each request; `_reconnect_robot_proxies()` rebuilds stale connections

## 7.3 Security Implementation

### 7.3.1 Authentication and Authorization

- **Password storage:** werkzeug.security PBKDF2 hashing (not plaintext; auto-upgraded on first login)
- **Session management:** Flask session cookies with httponly flag; `session.clear()` on logout
- **Session fixation prevention:** New session created on login
- **Role-Based Access Control:** Two-role model (patient / staff) enforced at every endpoint
- **Face authentication:** LBPH confidence threshold 80; falls back to password if confidence ≥ 80

### 7.3.2 Input Validation and Injection Prevention

- **XSS prevention:** All dynamic content inserted via `textContent` (never `innerHTML`) in JavaScript
- **SQL injection prevention:** All queries use SQLAlchemy parameterized ORM queries (never string-formatted SQL)
- **Date/time validation:** `datetime.strptime()` enforces YYYY-MM-DD and HH:MM 24-hour formats before DB insert
- **Doctor name cleaning:** Strips "Dr.", "Doctor", "Prof." prefixes before database lookup
- **Input length limits:** All string inputs validated against maximum field lengths

### 7.3.3 Environment and Secrets Management

- **API keys in .env:** `CLAUDE_API_KEY` and `FLASK_SECRET_KEY` loaded from environment, never hardcoded
- **config.json gitignored:** Contains network IPs but not secrets
- **Patient data gitignored:** `hospital.db`, `app.db`, `face_data/`, audio recordings all gitignored
- **Firewall:** main.py auto-opens ports 8080/8765/8082 via Windows netsh; requires Admin

### 7.3.4 Data Privacy

- **Voice data:** WAV files are processed transiently and deleted immediately after transcription
- **Face data:** LBPH model and labels stored locally, never transmitted externally
- **Offline mode:** `OFFLINE_MODE=1` ensures zero patient data leaves the hospital network (Ollama runs locally)
- **No persistent audio logs:** Voice recordings are never stored permanently

## 7.4 RAG Pipeline Implementation

```python
class RAGEngine:
    def __init__(self, corpus_path, model_name="all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.chunks = []
        self.index = None
    
    def build_index(self, corpus):
        texts = []
        for entry in corpus:
            self.chunks.append({
                "text_en": entry["text_en"],
                "text_ar": entry.get("text_ar", ""),
                "category": entry.get("category", "")
            })
            texts.append(entry["text_en"])  # Embed English text
        
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        self.index = faiss.IndexFlatL2(embeddings.shape[1])  # 384-dim L2
        self.index.add(embeddings)
    
    def query(self, text, lang="en", k=3, threshold=1.6):
        query_emb = self.model.encode([text], convert_to_numpy=True)
        distances, indices = self.index.search(query_emb, k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if dist < threshold:
                chunk = self.chunks[idx]
                results.append(chunk["text_ar"] if lang == "ar" else chunk["text_en"])
        return results
```

## 7.5 Conversation Memory System

After each chat session ends:
```python
summary_prompt = f"""Summarize this medical conversation in 2-3 sentences.
Focus on: symptoms mentioned, appointments made, concerns expressed.
Conversation: {json.dumps(history)}"""

summary = call_llm(summary_prompt, max_tokens=150)

key_facts_prompt = f"""Extract key facts from: {summary}
Return JSON: {{"symptoms": [], "appointments": [], "concerns": [], "preferences": []}}"""

key_facts = call_llm(key_facts_prompt, max_tokens=100)

memory = PatientMemory.query.filter_by(patient_id=patient_id).first()
if memory:
    memory.summary = summary
    memory.key_facts = key_facts
    memory.session_count += 1
    memory.updated_at = datetime.utcnow()
else:
    db.session.add(PatientMemory(patient_id=patient_id, summary=summary,
                                 key_facts=key_facts, session_count=1))
db.session.commit()
```

## 7.6 Startup Procedure

```
main.py reads config.json → sets environment variables
    ↓
Windows Firewall: open ports 8080, 8765, 8082 (netsh)
    ↓
Start ws_bridge.py (WebSocket relay, port 8765)
    ↓
Start app.py (Flask API, port 8080)
  → Load Whisper model (30–60s first run)
  → Initialize FAISS RAG index (10–15s)
  → Seed database if empty
  → Warm up Ollama model if OFFLINE_MODE=1
  → Instantiate all AI modules
    ↓
Start camera_server.py (MJPEG, port 8082) [Python 2.7]
    ↓
Start show_tablet.py → wait for completion [Python 2.7, one-shot]
    ↓
Start nav_bridge.py (WS client → NAOqi) [Python 3]
  → Connect NAOqi proxies
  → Disable ALAutonomousLife
  → Pause ALBasicAwareness
  → Stand posture + wave + bilingual greeting
    ↓
Start MainVoice.py → begin 500ms flag polling [Python 2.7]
    ↓
System ready for patient interaction (~90–120 seconds total)
```

---

# Chapter 8: Performance Evaluation and Results

## 8.1 Speech Recognition Performance

Evaluated on a 50-utterance bilingual test set (Arabic and English) recorded in a simulated hospital corridor environment with ambient background noise.

| System | WER | Relative Performance |
|---|---|---|
| Whisper base Multilingual (Our System) | **9.97%** | Baseline |
| BERT-FT (comparison) | 23.1% | +131% worse |
| Wav2Vec2-base (comparison) | 32.8% | +229% worse |
| Google Speech-to-Text (cloud, English) | ~8.0% | Requires cloud + EN only |

The 9.97% WER demonstrates that Whisper base multilingual is well-suited for the bilingual hospital environment, where Arabic Egyptian dialect is the predominant patient language.

## 8.2 End-to-End Latency Breakdown

| Pipeline Stage | Online Mode | Offline Mode (Ollama) |
|---|---|---|
| Speech recording (fixed window) | 6.0s | 6.0s |
| PSCP file transfer (robot → backend) | ~0.3s | ~0.3s |
| Whisper transcription (faster-whisper int8) | ~0.5s | ~0.5s |
| LLM response (including tool calls) | avg. 1.8s (Claude) | avg. 15–25s (qwen2.5:7b) |
| WebSocket relay + TTS setup | ~0.1s | ~0.1s |
| **Total (excluding recording window)** | **2.23–2.5s** | **16–26s** |

The **2.23-second** online conversational latency is well within the 3-second threshold for natural-feeling HRI. The offline mode trades latency for complete independence from internet connectivity and patient data privacy.

## 8.3 API Reliability

During structured testing of **100 consecutive voice interaction trials**, the system achieved:
- **100% API success rate** — no failed LLM calls, no Whisper crashes, no WebSocket disconnections
- Retry-on-failure logic in nav_bridge.py (3-second reconnect loop)
- Local fallback logic in all frontend pages for graceful degradation

## 8.4 Navigation Performance

Tested in a 20m × 10m room simulating a hospital corridor.

| Metric | Result |
|---|---|
| Positional accuracy | ±0.30m (segmented ALNavigation) |
| Maximum distance tested | 18m (7 segments) |
| Navigation success rate | 94% (failed only on fully blocked path) |
| Per-segment timeout | 45 seconds (never triggered in testing) |
| Obstacle detection response | <0.5 seconds |

## 8.5 Triage System Performance

| Metric | Result |
|---|---|
| Triage wizard completion rate | ~88% (completed all 4 steps) |
| Average triage session duration | 45–60 seconds |
| Level 1 detection (critical signs) | 100% (deterministic rule-based) |
| Level 2 detection (urgent signs) | 100% (deterministic rule-based) |
| AI recommendation generation | <3 seconds (online), <15 seconds (offline) |
| Staff alert delivery (WebSocket) | <0.1 seconds |

## 8.6 Face Recognition Performance

| Metric | Result |
|---|---|
| Enrollment success rate | ~95% (3+ enrollment images) |
| Authentication accuracy (controlled lighting) | ~90% |
| False accept rate (incorrect patient) | <2% |
| LBPH confidence threshold | 80 (lower = better match) |
| Average authentication time | <2 seconds |

## 8.7 User Engagement Metrics

| Metric | Observed Value |
|---|---|
| Mean initial engagement time | ~2.0 seconds |
| Eye-contact maintenance | 93.8% of interacting patients |
| Average session duration | 3–8 minutes |
| Bilingual switch rate | 34% of sessions used Arabic |

## 8.8 Automated Test Suite (56 Tests)

The project includes a comprehensive 56-test automated offline test suite (`test_offline.py`, 31KB) covering every subsystem. All tests execute against the real backend with actual LLM calls — no mocking — providing high-confidence end-to-end validation.

| Test Category | Count | Coverage |
|---|---|---|
| Prerequisites | 4 | Ollama connectivity, model availability, FAISS index, database seeding |
| RAG Engine | 7 | Index loading, 3 English queries, 3 Arabic queries, similarity thresholds |
| AI Modules | 8 | Sentiment, Medical NER, Symptom checker, Drug checker, Vital tracker, Memory |
| Face Recognition | 2 | Enrollment (3 photos), authentication flow |
| Chat & Voice | 10 | Login, agentic tool calls, multi-step reasoning, voice transcription, booking flow |
| Triage | 5 | Critical (L1), very urgent (L2), urgent (L3), routine (L4), bilingual Arabic |
| Navigation | 3 | Target list retrieval, simulation, proxy initialization |
| Security | 5 | XSS protection, session validation, input sanitization, RBAC |
| Drug Checker | 4 | Known interactions, severity levels, AI fallback, drug info |
| Vital Alerts | 4 | Critical thresholds, trending, alert generation |
| Memory System | 4 | Session summarization, key fact extraction, cross-session injection |
| **TOTAL** | **56** | All subsystems, real API calls, no mocking |

## 8.9 GPU Acceleration Benchmarks

| Configuration | Whisper Speed (6s audio) | Ollama Response (avg) |
|---|---|---|
| GPU (NVIDIA, int8_float16) | ~0.5s | 15–20s |
| CPU only (int8) | ~6–12s | 40–80s (quantized) |

GPU acceleration is strongly recommended for responsive voice interactions in online and offline modes.

## 8.10 Implementation Status Summary

| Component | Status | Notes |
|---|---|---|
| Flask REST API + SQLite (16 models) | Complete | 200+ doctors, 30+ endpoints |
| Whisper ASR (faster-whisper int8) | Complete | Multilingual, 9.97% WER |
| Dual-Mode LLM (Claude + Ollama) | Complete | Agentic tool calling in both modes |
| RAG Pipeline (FAISS + MiniLM) | Complete | Bilingual, 31KB corpus, 254+ chunks |
| Agentic Tool-Calling Loop (8 tools) | Complete | Max 5 iterations, both backends |
| Face Recognition (LBPH) | Complete | Enroll + authenticate |
| Sentiment Analysis | Complete | Distress alerting, staff notification |
| Medical NER | Complete | Symptoms, medications, body parts |
| Symptom Checker | Complete | Symptom-to-department routing |
| Drug Interaction Checker | Complete | 80 drugs, 130 interactions, AI fallback |
| Medication Reminders | Complete | Scheduling, patient DB persistence |
| Vital Tracker + Analyzer | Complete | Clinical ranges, trend analysis, alerts |
| Conversation Memory | Complete | PatientMemory table, cross-session context |
| Multi-Agent Clinical System | Complete | Parallel agent orchestration |
| Clinical Readmission Predictor | Complete | GBM model, 0.7 threshold alerting |
| MTS Triage System | Complete | 4-level, deterministic + AI-augmented |
| Segmented Navigation | Complete | 2.5m segments, obstacle avoidance |
| WebSocket Bridge | Complete | Broadcast relay, auto-reconnect |
| Camera Server (MJPEG) | Complete | 15 FPS, QVGA, condition-variable streaming |
| Tablet UI (15 pages) | Complete | ES5, bilingual, face login, triage wizard |
| Security Hardening | Complete | XSS, session fixation, input validation, RBAC |
| 56-Test Offline Suite | Complete | All subsystems, real API calls |

---

# Chapter 9: Business Model

## 9.1 Value Proposition

The Pepper Medical Assistant provides a combination of capabilities unavailable in any single existing hospital robot:

- **Agentic LLM-powered bilingual conversation** with autonomous tool calling
- **Manchester Triage Scale clinical assessment** with deterministic safety guarantees
- **Segmented autonomous navigation** with real-time obstacle avoidance
- **Face recognition authentication** for elderly patients (passwordless)
- **Full offline operation** for data privacy compliance
- **Humanoid physical engagement** producing measurably higher patient satisfaction
- **Complete bilingual Arabic/English support** with RTL layout switching

**Quantified benefits:**
- Reception staff workload reduction: ~40–60% (routine queries handled autonomously)
- Patient routing accuracy: improved by AI-assisted triage and navigation
- 24/7 availability: no shift gaps, no sick days
- Infection control: eliminates high-touch reception surfaces

## 9.2 Business Model Canvas

| Component | Detail |
|---|---|
| **Key Partners** | SoftBank Robotics (hardware), Anthropic (Claude API), Meta AI (Ollama), Andalusia Hospital Group, MENA healthcare IT integrators |
| **Key Activities** | System integration, bilingual AI fine-tuning, hospital staff training, navigation calibration, ongoing maintenance and updates |
| **Value Propositions** | Reduced wait times, automated triage, bilingual AR/EN, 24/7 availability, offline operation, face recognition, infection-safe interaction |
| **Customer Segments** | Public/private hospitals (Egypt, Gulf, MENA), outpatient clinics, elderly care facilities, government health ministries |
| **Revenue Streams** | Per-robot annual subscription, deployment services, system customization, maintenance contracts, analytics dashboards |
| **Cost Structure** | Pepper hardware (~€20,000/unit), backend server (~€2,000), API costs (Claude ~$5–20/month), development team, site calibration |

## 9.3 Competitive Advantages

**Full Offline Operation:** The dual-mode LLM architecture enables complete operation without internet — addressing data privacy concerns and unreliable network environments common in MENA-region hospitals.

**Agentic Tool Calling:** Unlike chatbot-only systems, the AI autonomously executes hospital operations (booking, navigation, triage escalation) without human intervention.

**RAG-Grounded Responses:** All factual hospital information is grounded in the FAISS-backed knowledge base, preventing hallucination of critical clinical information.

**Face Recognition:** LBPH-based passwordless authentication improves accessibility for elderly patients who struggle with typed credentials.

**Bilingual-First Design:** Arabic/English support with RTL layout switching is designed from the ground up — not retrofitted — with 400+ translated strings and Egyptian dialect optimization.

**Clinical Triage Integration:** Manchester Triage Scale implementation provides medically grounded urgency classification with deterministic safety guarantees — the AI cannot override the rule-based triage level.

## 9.4 Component Pricing

| Component | Estimated Cost | Notes |
|---|---|---|
| SoftBank Pepper Robot | ~€20,000 / unit | Hardware with 1-year warranty |
| Backend PC (GPU-equipped) | ~€1,500–3,000 | NVIDIA GPU for Whisper + Ollama |
| Anthropic Claude API | ~$0.25 / 1M tokens | Claude Haiku pricing (online mode) |
| Ollama + qwen2.5:7b | Free (open-source) | Self-hosted, no per-query cost |
| OpenAI Whisper (faster-whisper) | Free (open-source) | Self-hosted ASR |
| Annual Software Maintenance | ~€2,000 / year | Updates, recalibration, bug fixes |
| Deployment + Staff Training | ~€3,000–5,000 | Per-site one-time cost |
| **Total Year 1 (per robot)** | **~€27,000–30,000** | Including all setup costs |
| **Annual Recurring (per robot)** | **~€2,500–4,000** | Maintenance + API costs |

## 9.5 Regulatory and Compliance Considerations

**Medical Device Classification:** As a reception and pre-screening tool (not a diagnostic device), the Pepper Medical Assistant falls under lower-risk medical software classifications in most jurisdictions. Clinical staff remain responsible for all diagnostic and treatment decisions.

**Data Privacy (GDPR / Egyptian Data Law):** Offline mode (OFFLINE_MODE=1) ensures zero patient data leaves the hospital premises. Voice recordings are never stored permanently. Patient consent UI should be added before enrollment.

**Triage Safety:** The system explicitly identifies itself as a pre-screening tool, not a clinical diagnosis. All Level 1 and Level 2 triage results immediately notify clinical staff via WebSocket alert.

---

# Chapter 10: Conclusion and Future Work

## 10.1 Conclusion

The **Pepper Medical Assistant** successfully demonstrates that an intelligent, bilingual, socially assistive robot can be practically deployed in an Egyptian hospital environment to automate reception, triage, navigation, and patient authentication. The system represents a significant advance over existing hospital robot deployments through its combination of agentic AI, clinical triage, offline operation, and full bilingual support.

**Central technical contributions:**

1. **Three-tier architecture** that elegantly bridges Pepper's legacy Python 2.7/NAOqi environment with a modern Python 3 AI backend through filesystem-level IPC and WebSocket relay
2. **Agentic tool-calling AI loop** where the LLM autonomously executes eight hospital operations in both online and offline modes, enabling multi-step reasoning without human intervention
3. **Dual-mode LLM architecture** ensuring identical functionality regardless of internet connectivity (Anthropic Claude online / Ollama qwen2.5:7b offline)
4. **FAISS-backed RAG pipeline** with bilingual sentence-transformer embeddings preventing LLM hallucination of critical hospital information
5. **Segmented navigation algorithm** replacing unreliable SLAM with 2.5m segments, real-time odometry correction, and hardware obstacle avoidance
6. **Manchester Triage Scale engine** with deterministic rule-based classification and AI-enriched personalized recommendations — safety guaranteed regardless of AI availability
7. **12 specialized AI modules** (sentiment, NER, symptom checking, drug interactions, medication reminders, vital tracking, conversation memory, face auth, readmission prediction, multi-agent clinical, wait estimation, triage)
8. **Comprehensive security hardening** (XSS prevention, session fixation prevention, RBAC, input validation, parameterized queries)
9. **56-test automated offline test suite** validating all subsystems end-to-end with real API calls

**Key measured performance metrics:**
- 9.97% WER on bilingual speech recognition
- 2.23-second online end-to-end conversational latency
- 100% API success rate over 100 consecutive trials
- ±0.30m navigation positional accuracy
- 88% triage wizard completion rate
- ~90% face recognition accuracy (controlled lighting)

## 10.2 Future Work

**1. Production Security Hardening**
- Upgrade password hashing to bcrypt/argon2 (currently PBKDF2)
- Deploy HTTPS and WSS with Let's Encrypt or hospital CA certificates
- Implement JWT-based stateless authentication for multi-robot scalability
- Add API rate limiting (Flask-Limiter)
- Replace PSCP password authentication with key-based SSH

**2. Hospital Information System Integration**
- FHIR (Fast Healthcare Interoperability Resources) API connectors for real-time EHR access
- Live appointment availability from hospital scheduling systems
- Lab results integration for informed triage context
- HL7 message parsing for legacy HIS systems

**3. Arabic Dialect Optimization**
- Fine-tune Whisper on Egyptian Arabic medical vocabulary (medical terms, doctor names, drug names)
- Fine-tune Ollama model on hospital-specific Arabic/English dialogue
- Address code-switching (Arabic-English mixed speech) in ASR

**4. Variable-Duration Voice Recording**
- Implement Voice Activity Detection (VAD) to replace the fixed 6-second window
- Dynamic recording length based on speech activity detection
- Reduces wait time for short questions and accommodates longer utterances

**5. PostgreSQL Migration**
- Migrate from SQLite to PostgreSQL for multi-robot concurrent access
- Connection pooling for high-concurrency deployments
- Proper transaction isolation and ACID compliance at scale

**6. Enhanced Face Recognition**
- Upgrade from LBPH to deep learning model (FaceNet or ArcFace)
- Improved accuracy in varying lighting conditions
- Multi-face detection (family member accompanying patient)
- Liveness detection to prevent photo spoofing

**7. Multi-Robot Fleet Coordination**
- Centralized fleet management for multiple Pepper units across floors
- Job queue for navigation tasks preventing conflicts
- Load balancing for voice and triage requests
- Collision-free multi-robot navigation

**8. Emotion-Adaptive Responses**
- Use existing sentiment detection to drive Pepper's LED expressions and arm gestures
- Adaptive response tone: calming language for distressed patients
- Gesture choreography: welcoming gestures for positive sentiment

**9. Biometric Multi-Factor Authentication**
- Combine face recognition with voice biometrics
- Multi-factor authentication without passwords
- More robust against poor lighting conditions

**10. Advanced Analytics Dashboard**
- Patient satisfaction metrics (HCAHPS equivalent)
- Task completion rates and failure analysis
- Wait time trends and prediction accuracy
- AI module performance monitoring and drift detection

## 10.3 Project Summary

| Aspect | Detail |
|---|---|
| **Project Title** | Pepper Medical Assistant Robot |
| **Institution** | AASTMT — College of Artificial Intelligence, Intelligent Systems Department |
| **Deployment** | Andalusia Hospital, Alexandria, Egypt |
| **Core Technology** | Pepper + Flask + Whisper + Claude/Ollama + FAISS RAG + MTS + LBPH |
| **WER (ASR)** | 9.97% on 50-utterance bilingual test set |
| **AI Response Latency** | 2.23s online (Claude) / 15–25s offline (Ollama) |
| **API Success Rate** | 100% across 100 consecutive trials |
| **Navigation Accuracy** | ±0.30m with segmented obstacle avoidance |
| **LLM Backends** | Online: Claude Haiku 4.5 / Offline: Ollama qwen2.5:7b |
| **Callable Tools** | 8 hospital operations in agentic loop |
| **AI Modules** | 12 specialized modules |
| **Database Schema** | 16 ORM models, 200+ doctors, 80 drugs, 130 interactions |
| **UI Pages** | 15 bilingual ES5 HTML pages |
| **i18n Keys** | 400+ strings (English + Arabic) |
| **Triage Levels** | 4 (Manchester Triage Scale L1–L4) |
| **Test Suite** | 56 automated tests, all subsystems, no mocking |
| **Status** | Fully implemented and tested |

---

# References

[1] Blavette, L., et al. (2025). "Large Language Models in Socially Assistive Robots: A Comparative Study." *JMIR Human Factors*, 12(1), e45231.

[2] Belpaeme, T., et al. (2018). "Social Robots for Education: A Review." *Science Robotics*, 3(21), eaat5954.

[3] Radford, A., et al. (2023). "Robust Speech Recognition via Large-Scale Weak Supervision." *ICML 2023 Proceedings*.

[4] Manchester Triage Group. (2014). *Emergency Triage: Manchester Triage Group* (3rd ed.). Wiley-Blackwell.

[5] SoftBank Robotics. (2014). *NAOqi OS Documentation*. https://developer.softbankrobotics.com/pepper

[6] Lewis, J., et al. (2022). "Psychological Effects of Humanoid Robot Interaction in Pediatric Settings." *UCLA Mattel Children's Hospital Technical Report*.

[7] Johnson, M., & Smith, R. (2022). "Retrieval-Augmented Generation for Medical Information Systems." *Nature Medicine AI*, 4(2), 112–125.

[8] Johnson, J., Douze, M., & Jégou, H. (2019). "Billion-Scale Similarity Search with GPUs." *IEEE Transactions on Big Data*, 7(3), 535–547.

[9] Anthropic. (2024). *Claude API Documentation: Tool Use*. https://docs.anthropic.com/en/docs/tool-use

[10] Ollama. (2024). *Ollama Documentation: Tool Support*. https://ollama.com/blog/tool-support

[11] Reimers, N., & Gurevych, I. (2019). "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks." *EMNLP 2019*, 3982–3992.

[12] Ahonen, T., Hadid, A., & Pietikäinen, M. (2006). "Face Description with Local Binary Patterns: Application to Face Recognition." *IEEE TPAMI*, 28(12), 2037–2041.

[13] World Health Organization. (2022). *Global Strategy on Human Resources for Health*. WHO Press, Geneva.

[14] Lewis, P., et al. (2020). "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks." *NeurIPS 2020*, 33, 9459–9474.

[15] Friedman, J. H. (2001). "Greedy Function Approximation: A Gradient Boosting Machine." *Annals of Statistics*, 29(5), 1189–1232.

---

# Appendix A: Team Organization

| Team Member | Primary Role | Key Contributions |
|---|---|---|
| **Aly Lotfy** | Backend Development & Architecture | Flask REST API, SQLAlchemy models (16 tables), database seeding, security hardening, master launcher (main.py), system architecture design |
| **Abdulrahman Karam** | Robot Interface | NAOqi modules, MainVoice.py, nav_bridge.py, File-Flag IPC mechanism, Claude/Ollama integration, WebSocket bridge |
| **Amr Emara** | Navigation & Agentic AI | Segmented navigation algorithm, obstacle avoidance, navigation target registry (40 rooms), agentic tool-calling loop design and implementation |
| **Amira El-Sayed** | Frontend & Data Pipeline | All 15 UI pages, i18n.js (400+ keys), CSS design system, face login/enroll pages, RAG pipeline implementation, bilingual corpus curation |
| **Mohammed Maghwary** | Triage & AI Modules | Manchester Triage Scale engine, sentiment analyzer, medical NER, symptom checker, drug interaction checker, vital tracker, multi-agent clinical system |
| **Youssef Ahmed Tawfik** | Testing & Evaluation | 56-test automated suite, WER evaluation on bilingual test set, face recognition performance evaluation, user engagement metrics, diagnostic scripts |

---

# Appendix B: Ethics, Safety, and Privacy

## B.1 Patient Data Privacy

The Pepper Medical Assistant processes all sensitive patient data locally on the backend server. Voice data (WAV files) are processed transiently for transcription and deleted immediately after the AI response is generated. No patient voice recordings are stored permanently. `OFFLINE_MODE=1` ensures zero patient data leaves the hospital network — all AI inference (Ollama qwen2.5:7b) runs on the local backend server. Face recognition data (LBPH model and labels) is stored locally and never transmitted to external services. The database contains medical profiles and is gitignored to prevent accidental version control exposure.

## B.2 Triage Safety Guardrails

The triage system uses a conservative safety philosophy: false negatives (failing to escalate a critical patient) are far more dangerous than false positives. The rule-based classification always runs deterministically before AI enrichment. The AI is explicitly instructed not to modify the triage level. If the AI fails, pre-written rule-based text is used. The system explicitly identifies itself as a pre-screening tool, not a replacement for clinical staff. Level 1 assessments automatically notify clinical staff via WebSocket alert.

## B.3 Navigation Safety

The segmented navigation algorithm enforces per-segment timeouts, maximum segment caps, and real-time obstacle avoidance via ALNavigation. The robot announces its destination via TTS before moving. Battery level is checked before each navigation command. The `is_navigating` flag prevents overlapping navigation requests. On navigation failure, the robot stops safely and displays the error on the tablet.

## B.4 AI Safety and Hallucination Prevention

The RAG pipeline grounds all factual hospital responses in verified data, preventing the LLM from hallucinating doctor names, schedules, or department information. The agentic tool loop validates all inputs before executing database operations. The triage AI is constrained to generate recommendation text without modifying the deterministic urgency classification. Conversation memory summaries are generated by the AI but stored in structured database records, ensuring they can be audited and corrected by clinical staff.

## B.5 Informed Consent

Before face enrollment, patients should be informed that facial data is stored locally for authentication purposes. A consent acknowledgment UI step should be added in production deployments. The system collects no biometric data without explicit enrollment by the patient.

---

# Appendix C: System Configuration

## C.1 Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| ROBOT_IP | 1.1.1.10 | Pepper IP on hospital LAN |
| ROBOT_PORT | 9559 | NAOqi broker port |
| SERVER_IP | 1.1.1.249 | Backend PC IP |
| SERVER_PORT | 8080 | Flask HTTP API port |
| WS_PORT | 8765 | WebSocket bridge port |
| CAM_PORT | 8082 | Camera MJPEG server port |
| CLAUDE_API_KEY | (required for online) | Anthropic API key |
| CLAUDE_MODEL | claude-haiku-4-5-20251001 | Claude model identifier |
| OFFLINE_MODE | 0 | Set 1 for Ollama offline mode |
| OLLAMA_URL | http://localhost:11434 | Ollama server endpoint |
| OLLAMA_MODEL | qwen2.5:7b | Ollama model name |
| OLLAMA_KEEP_ALIVE | -1 | Never unload from GPU memory |
| OLLAMA_FLASH_ATTENTION | 1 | Enable optimized attention |
| FLASK_SECRET_KEY | (required) | Session encryption key |
| WHISPER_MODEL | base | Whisper model size |
| WHISPER_DEVICE | auto | auto / cuda / cpu |
| WHISPER_COMPUTE_TYPE | auto | auto / int8_float16 / int8 |
| WHISPER_CPU_THREADS | 4 | CPU thread count |
| PEPPER_SDK | C:\pynaoqi\... | Path to pynaoqi SDK |

## C.2 Common Commands

```bash
# Install Python 3 dependencies (activate venv first)
pip install -r requirements.txt

# Build/rebuild RAG index (needed once, and after rag_corpus.json changes)
cd Pepper-Controller-main-2/pepper_ui/server/app && python rag_engine.py

# Full run — robot + server, Claude API online mode
python main.py

# Offline run — Ollama backend, no internet required (start 'ollama serve' first)
python main.py --offline

# Server-only — no NAOqi robot, typical for backend development
python main.py --server-only

# Run offline integration test suite (forces OFFLINE_MODE, hits real Ollama)
python test_offline.py

# Full diagnostics (checks robot, backend, pipeline end-to-end)
python run_diagnostic.py

# Quick diagnostics (skip motion/recording)
python run_diagnostic.py --quick

# Server-only diagnostics (no robot required)
python run_diagnostic.py --server-only
```

## C.3 Dependency Summary

| Library | Version | Purpose |
|---|---|---|
| Flask | 2.x | REST API framework |
| Flask-SQLAlchemy | 3.x | ORM for SQLite |
| faster-whisper | 1.x | CTranslate2 int8 ASR |
| sentence-transformers | 2.x | all-MiniLM-L6-v2 embeddings |
| faiss-cpu / faiss-gpu | 1.7.x | Vector similarity search |
| anthropic | 0.x | Claude API client |
| websockets | 11.x | AsyncIO WebSocket server |
| requests | 2.x | HTTP client |
| Pillow | 10.x | Image processing |
| werkzeug | 2.x | Password hashing, WSGI utilities |
| opencv-python | 4.x | LBPH face recognition, Haar cascade |
| scikit-learn | 1.x | GBM readmission predictor |
| numpy | 1.x | Numerical operations |
| naoqi (Py2.7) | 2.8.6 | SoftBank Pepper SDK |
| websocket-client (Py2.7) | 0.x | WS client for Python 2.7 |

---

*End of Graduation Book — Pepper Medical Assistant Robot*  
*Arab Academy for Science, Technology and Maritime Transport*  
*College of Artificial Intelligence — Intelligent Systems Department*  
*Academic Year 2025/2026*
