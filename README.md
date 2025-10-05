# Pepper Medical Assistance Robot

A graduation project developed by AAST College of Artificial Intelligence (Alamein Campus).
This project leverages Pepper Robot, AI, and Edge Computing to create an intelligent medical assistant for hospitals — capable of interacting with patients through speech, tablet UI, and gesture control.

## Project Overview

The Pepper Medical Assistance Robot acts as a bilingual (Arabic/English) hospital assistant designed to support patients and staff.
It can speak, guide, answer questions, and perform simple triage tasks while maintaining privacy and accessibility.

### Core Features
- Reception & Check-In: Confirms appointments using ID/QR codes.
- Queue Management: Displays wait times and notifies patients.
- FAQs & Guidance: Answers hospital-related questions (visiting hours, insurance, etc.).
- Wayfinding Assistance: Directs patients to departments.
- Simple Triage: Asks structured health questions and alerts nurses for urgent cases.
- Accessibility: Voice + touch interface with Arabic/English support.

## System Architecture

Think of the system as three connected layers:

### 1. Pepper Layer (`robot/`)
- Runs on Python 2.7 with the NAOqi SDK.
- Handles robot speech, tablet display, and motion.
- File: `bridge.py` → WebSocket client connecting Pepper ↔ Backend.
- Functions:
  - TTS: Text-to-speech via `ALTextToSpeech`
  - Tablet: Displays HTML UI via `ALTabletService`
  - Alert: Nurse call command

### 2. Backend Layer (`server/`)
- Built with FastAPI (Python 3.x) for modular and efficient communication.
- Core files:
  - `main.py` → API endpoints (`/api/speak`, `/api/faq/search`, `/api/triage/submit`)
  - `rag.py` → FAQ retrieval (local RAG-based)
  - `triage.py` → Simple rule-based scoring system
  - `bridge_bus.py` → WebSocket publisher (sends messages to Pepper)

All communication between the UI, logic, and robot happens here.

### 3. User Interface Layer (`pepper_ui/`)
- A web app displayed on Pepper’s tablet.
- Built with HTML, CSS, and JavaScript.
- Structure:
  - `index.html`: Tabs for Check-In, FAQ, and Triage
  - `style.css`: Large fonts and buttons for elderly accessibility
  - `script.js`: Uses `fetch()` to send API requests to backend

## Data Flow (Pipeline)

1. Patient Interaction – The user types or speaks a query on Pepper’s tablet.
2. UI → Backend – The UI sends the request to FastAPI (`/api/faq/search`).
3. Backend Logic – `rag.py` finds an appropriate answer from the FAQ index.
4. Backend → Bridge – The answer is published via WebSocket (`bridge_bus.py`).
5. Bridge → Pepper – Pepper speaks the response through `ALTextToSpeech` and displays it on the tablet.

Everything runs locally (edge-based) → ensuring privacy, low latency, and reliability.

## Repository Structure

```
GRADUATION PROJECT/
│
├─ pepper_env/               # Virtual environment (auto-generated)
│
├─ robot/                    # Pepper bridge (Python 2.7, NAOqi)
│   ├─ bridge.py
│   ├─ config.ini
│   └─ __init__.py
│
├─ server/                   # Backend (Python 3.x, FastAPI)
│   ├─ app/
│   │   ├─ main.py
│   │   ├─ rag.py
│   │   ├─ triage.py
│   │   ├─ bridge_bus.py
│   │   └─ __init__.py
│   ├─ tools/
│   │   └─ build_faq_index.py
│   ├─ .env
│   └─ requirements.txt
│
├─ pepper_ui/                # Tablet web app
│   ├─ index.html
│   ├─ style.css
│   └─ script.js
│
├─ Proposals/
│
├─ Scripts/
│   └─ run_all.bat           # Run server + bridge together
│
└─ pynaoqi-.../lib/naoqi.py  # NAOqi SDK
```

## Setup & Activation

Follow the Week 1 Activation Guide for Pepper setup:

1. Install Requirements
   - Pepper Robot (NAOqi 2.8/2.9)
   - Python 2.7 (64-bit)
   - pynaoqi SDK for Windows
   - Python 3.x for backend
   - Virtualenv installed (`pip install virtualenv`)

2. Create Environment
   ```bash
   virtualenv -p "C:\Python27\python.exe" pepper_env
   .\pepper_env\Scripts\activate
   ```

3. Add NAOqi SDK to Environment
   ```powershell
   $SDK = "C:\SDK\pynaoqi-python2.7-2.8.6.23-win64-vs2015"
   $env:PYTHONPATH = "$SDK\lib;$SDK\lib\python2.7\site-packages;$env:PYTHONPATH"
   $env:PATH       = "$SDK\lib;$env:PATH"
   ```

4. Test Connection
   ```python
   from naoqi import ALProxy
   tts = ALProxy("ALTextToSpeech", "<PEPPER_IP>", 9559)
   tts.say("Hello, I am Pepper!")
   ```

5. Run Backend & UI
   ```bash
   cd server
   uvicorn app.main:app --reload
   python robot/bridge.py
   ```

6. Access UI
   Open Pepper’s tablet browser or PC browser at:
   `http://<SERVER_IP>:8080`

## Team Members
| Name | ID |
|------|----|
| Aly Ahmed Lotfy | 221000412 |
| Amr Sherif Emara | 221000299 |
| Youssef Ahmed Tawfik | 221001264 |
| Abdelrahman Karam | 221002035 |
| Mohamed El-Maghwary | 221001747 |
| Amira El Sayed | 221002982 |

## Collaboration Partner
Andalusia Hospital – Pilot testing and validation site.

## Expected Outcomes
- Working Pepper assistant deployed in a demo hospital environment.
- Improved patient engagement and staff efficiency.
- Pilot testing with Andalusia Hospital.
- Academic publications on applied healthcare robotics.

## License
This project is for educational and research purposes under the AAST College of AI.
