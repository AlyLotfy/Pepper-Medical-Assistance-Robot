# app.py
# Flask Server for Pepper Medical Assistance Robot
# *** COMPLETE: Database + Legacy Routes + Whisper Voice AI + Health Tips AI + FAISS RAG ***

import os
import json
import time
import tempfile
import traceback
import requests
import csv
from faster_whisper import WhisperModel
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, session, make_response, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import time as time_type, datetime, date as date_type, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from rag_engine import RAGEngine
from emotion_detector import EmotionDetector
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ai_modules.sentiment import SentimentAnalyzer
from ai_modules.medical_ner import MedicalNER
from ai_modules.symptom_checker import SymptomChecker
from ai_modules.face_auth import FaceAuth
from ai_modules.conversation_memory import ConversationMemory
from ai_modules.fall_detection import FallDetector
from ai_modules.vital_tracker import check_vital_alerts, summarize_vitals, VitalAnalyzer
from ai_modules.drug_checker import DrugChecker
from ai_modules.medication_reminder import MedicationReminderManager
from ai_modules.translator import Translator
from ai_modules.wait_estimator import WaitEstimator
from ai_modules.symptom_progression import SymptomProgressionTracker
from ai_modules.acoustic_analyzer import AcousticAnalyzer
from ai_modules.pose_analyzer import PoseAnalyzer
from ai_modules.multi_agent import MultiAgentClinicalSystem
from ai_modules.clinical_predictor import ReadmissionRiskPredictor, DynamicWaitEstimator

# ====== Load .env file ======
def _load_env():
    """Load variables from .env file in the project root (4 levels up from app.py)."""
    app_path = Path(__file__).resolve()
    # Walk up to find .env
    for parent in app_path.parents:
        env_file = parent / ".env"
        if env_file.exists():
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, val = line.partition("=")
                        os.environ.setdefault(key.strip(), val.strip())
            print(f"[ENV] Loaded environment from: {env_file}")
            return
    print("[ENV] No .env file found — using system environment variables.")

_load_env()

# ====== ROBUST DIRECTORY SETUP ======
CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent

# Robustly find the 'static' folder (HTML/CSS/JS)
if (CURRENT_DIR / "static").exists():
    STATIC_DIR = CURRENT_DIR / "static"
    print(f"[INFO] Found static folder at: {STATIC_DIR}")
elif (PARENT_DIR / "static").exists():
    STATIC_DIR = PARENT_DIR / "static"
    print(f"[INFO] Found static folder at: {STATIC_DIR}")
else:
    STATIC_DIR = CURRENT_DIR / "static"
    os.makedirs(STATIC_DIR, exist_ok=True)
    print(f"[WARN] Static folder not found! Created empty one at: {STATIC_DIR}")

app = Flask(
    __name__,
    static_folder=str(STATIC_DIR),
    static_url_path=""
)

# *** CACHE BUSTING CONFIGURATION ***
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# *** FORCE ROUTE FOR QIMESSAGING ***
@app.route('/static/qimessaging.js')
def serve_qimessaging():
    return send_from_directory(STATIC_DIR, 'qimessaging.js')

# *** /static/<file> FALLBACK ***
# Files are normally served at the root (static_url_path=""), so a request for
# /static/navigating.html would 404. The robot tablet and some older links use
# the /static/ prefix, so serve those from the same folder instead of flashing
# a "Not Found" page. send_from_directory blocks path traversal automatically.
@app.route('/static/<path:filename>')
def serve_static_prefixed(filename):
    return send_from_directory(STATIC_DIR, filename)

# *** FRIENDLY 404 PAGE ***
# Replaces Werkzeug's bare "Not Found" page (which the patient sees if a tile
# links to a missing/renamed page or a stale tablet cache points at an old URL)
# with a branded, bilingual recovery screen that always offers a way back home.
# Note: views that explicitly `return jsonify(...), 404` are NOT routed here —
# this only fires for unmatched URLs / abort(404) — so API error payloads are
# unaffected. We still return JSON for /api/* and JSON-preferring clients so
# the navigation directory fetch (guide.html XHR) keeps getting JSON.
_FRIENDLY_404_HTML = """<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
  <meta charset="UTF-8">
  <title>Page Not Found</title>
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
  <style>
    *,*:before,*:after{box-sizing:border-box;-webkit-tap-highlight-color:transparent;}
    html,body{height:100%;margin:0;padding:0;}
    body{
      font-family:sans-serif;color:#5a4a3b;
      background:-webkit-linear-gradient(315deg,#f7f4f0,#ffffff);
      background:linear-gradient(135deg,#f7f4f0,#ffffff);
      display:-webkit-flex;display:flex;
      -webkit-align-items:center;align-items:center;
      -webkit-justify-content:center;justify-content:center;
      text-align:center;
    }
    .card{
      width:90%;max-width:560px;background:#fff;border-radius:24px;
      box-shadow:0 10px 28px rgba(5,31,60,0.10);padding:40px 30px;
    }
    .emoji{font-size:60px;line-height:1;margin-bottom:14px;}
    h1{margin:0 0 8px 0;font-size:30px;font-weight:700;color:#5a4a3b;}
    p{margin:6px 0;font-size:18px;color:#8a7b6b;line-height:1.5;}
    .ar{font-size:19px;color:#6b5d4d;margin-top:4px;}
    .home-btn{
      display:inline-block;margin-top:26px;padding:16px 38px;
      background:#b89a6c;color:#fff;border:none;border-radius:16px;
      font-size:19px;font-weight:700;cursor:pointer;text-decoration:none;
      box-shadow:0 4px 12px rgba(184,154,108,0.35);
    }
    .home-btn:active{background:#9a7d52;-webkit-transform:translateY(1px);transform:translateY(1px);}
  </style>
</head>
<body>
  <div class="card">
    <div class="emoji">&#129302;</div>
    <h1>Oops! Page Not Found</h1>
    <p>This page isn't available. Let me take you back to the home screen.</p>
    <p class="ar" dir="rtl">&#1593;&#1584;&#1585;&#1611;&#1575;! &#1607;&#1584;&#1607; &#1575;&#1604;&#1589;&#1601;&#1581;&#1577; &#1594;&#1610;&#1585; &#1605;&#1608;&#1580;&#1608;&#1583;&#1577;. &#1583;&#1593;&#1606;&#1610; &#1571;&#1593;&#1610;&#1583;&#1603; &#1573;&#1604;&#1609; &#1575;&#1604;&#1588;&#1575;&#1588;&#1577; &#1575;&#1604;&#1585;&#1574;&#1610;&#1587;&#1610;&#1577;.</p>
    <a class="home-btn" href="/">&#8592; Back to Home &middot; <span dir="rtl">&#1575;&#1604;&#1585;&#1574;&#1610;&#1587;&#1610;&#1577;</span></a>
  </div>
  <script>
    /* Auto-return to the home screen after 8s so the tablet never gets
       stranded if nobody taps the button. */
    setTimeout(function(){ window.location.href = "/"; }, 8000);
  </script>
</body>
</html>"""

@app.errorhandler(404)
def friendly_not_found(e):
    # API / JSON clients keep getting a JSON 404 (don't break XHR consumers).
    wants_json = (
        request.path.startswith("/api/")
        or "application/json" in (request.headers.get("Accept") or "")
    )
    if wants_json:
        return jsonify({"error": "Not found", "path": request.path}), 404
    return _FRIENDLY_404_HTML, 404

# *** SECURITY KEY (Required for Session) ***
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "pepper_medical_secret_key_99")

# ====== Initialize Whisper (faster-whisper with CTranslate2) ======
# Auto-detects CUDA; falls back to CPU automatically.
# Config keys in config.json (all optional):
#   WHISPER_MODEL        : tiny|base|small|medium|large-v2|large-v3  (default: medium)
#   WHISPER_DEVICE       : auto|cuda|cpu                              (default: auto)
#   WHISPER_COMPUTE_TYPE : float16|int8_float16|int8                  (default: auto)
#   WHISPER_CPU_THREADS  : int                                         (default: 4)
#
# GPU speed on 6-second audio: medium ~1 s | large-v3 ~3 s
# CPU speed on 6-second audio: medium ~12 s | large-v3 ~30 s
_cfg_path = Path(__file__).resolve().parents[3] / "config.json"
try:
    with open(_cfg_path) as _cf:
        _launcher_cfg = json.load(_cf)
except Exception:
    _launcher_cfg = {}

_WHISPER_MODEL   = _launcher_cfg.get("WHISPER_MODEL", "medium")
_WHISPER_THREADS = int(_launcher_cfg.get("WHISPER_CPU_THREADS", 4))

# Auto-detect CUDA via CTranslate2 (the actual inference backend —
# does NOT require a CUDA-enabled PyTorch build).
_cfg_device = _launcher_cfg.get("WHISPER_DEVICE", "auto").lower()
try:
    import ctranslate2 as _ct2
    _cuda_ok = _ct2.get_cuda_device_count() > 0
except Exception:
    _cuda_ok = False

if _cfg_device == "auto":
    _WHISPER_DEVICE = "cuda" if _cuda_ok else "cpu"
else:
    _WHISPER_DEVICE = _cfg_device

# Pick the best compute type for the device unless overridden.
# int8_float16 on GPU: ~40% less VRAM than float16, negligible accuracy loss.
_cfg_compute = _launcher_cfg.get("WHISPER_COMPUTE_TYPE", "auto").lower()
if _cfg_compute == "auto":
    if _WHISPER_DEVICE == "cuda":
        _WHISPER_COMPUTE_TYPE = "int8_float16"  # memory-efficient GPU mode
    else:
        _WHISPER_COMPUTE_TYPE = "int8"          # smallest footprint on CPU
else:
    _WHISPER_COMPUTE_TYPE = _cfg_compute

print(f"[INFO] Loading Whisper Model ({_WHISPER_MODEL}, device={_WHISPER_DEVICE}, compute={_WHISPER_COMPUTE_TYPE})...")
try:
    audio_model = WhisperModel(
        _WHISPER_MODEL,
        device=_WHISPER_DEVICE,
        compute_type=_WHISPER_COMPUTE_TYPE,
        cpu_threads=_WHISPER_THREADS,
        num_workers=1,
    )
    print(f"[INFO] Whisper Model Loaded ({_WHISPER_MODEL} on {_WHISPER_DEVICE}).")
except Exception as _we:
    # GPU init failed (driver mismatch, OOM, etc.) — retry on CPU with int8
    print(f"[WARN] Whisper GPU init failed ({_we}), retrying on CPU int8...")
    _WHISPER_DEVICE       = "cpu"
    _WHISPER_COMPUTE_TYPE = "int8"
    audio_model = WhisperModel(
        _WHISPER_MODEL,
        device="cpu",
        compute_type="int8",
        cpu_threads=_WHISPER_THREADS,
        num_workers=1,
    )
    print(f"[INFO] Whisper Model Loaded ({_WHISPER_MODEL} on CPU int8 fallback).")

SERVER_START_TIME = time.time()

# ====== Session Logger ======
try:
    from session_logger import log_event as _log_event
    _SESSION_LOGGING = True
except ImportError:
    _SESSION_LOGGING = False

def _slog(action, patient_name=None, patient_id=None, success=True,
          duration_ms=None, **details):
    """Thin wrapper — logs a session event; never raises."""
    if not _SESSION_LOGGING:
        return
    try:
        _log_event(action, patient_name=patient_name, patient_id=patient_id,
                   success=success, duration_ms=duration_ms, details=details or {},
                   error=details.pop("error", None))
    except Exception:
        pass

# ====== Initialize FAISS RAG Engine ======
print("[INFO] Initializing FAISS RAG Engine...")
rag_engine = RAGEngine(auto_load=True)
print(f"[INFO] RAG Engine ready: {rag_engine.status()['total_chunks']} knowledge chunks indexed.")
# Preload the embedding model so the first voice query doesn't wait 30s
rag_engine._ensure_model()

# ====== Initialize Emotion Detector ======
print("[INFO] Initializing Emotion Detector...")
emotion_detector = EmotionDetector()
print(f"[INFO] Emotion Detector ready: {emotion_detector.status()}")

# ====== Initialize AI Modules ======
print("[INFO] Initializing AI Modules...")
sentiment_analyzer  = SentimentAnalyzer()
medical_ner         = MedicalNER()
symptom_checker     = SymptomChecker()
face_auth           = FaceAuth()
print(f"[INFO] Face Auth status: {face_auth.status()}")
fall_detector       = FallDetector()
translator          = Translator()
vital_analyzer      = VitalAnalyzer()
print(f"[INFO] Fall Detector ready: {fall_detector.status()}")
print(f"[INFO] Translator ready: {translator.status()}")
# New AI modules
acoustic_analyzer   = AcousticAnalyzer()
pose_analyzer       = PoseAnalyzer()
multi_agent_system  = MultiAgentClinicalSystem()
readmission_predictor = ReadmissionRiskPredictor()
dynamic_wait_estimator = DynamicWaitEstimator()
print(f"[INFO] Acoustic Analyzer ready: {acoustic_analyzer.status()}")
print(f"[INFO] Pose Analyzer ready: {pose_analyzer.status()}")
print(f"[INFO] Readmission Predictor ready: {readmission_predictor.status()}")
print(f"[INFO] Dynamic Wait Estimator ready: {dynamic_wait_estimator.status()}")
# ConversationMemory, DrugChecker, MedicationReminderManager, WaitEstimator,
# SymptomProgressionTracker are instantiated per-request (they need db + models)

# ====== Database Config ======
app.config["JSON_SORT_KEYS"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + str(CURRENT_DIR / "app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ===============================
# DATABASE MODELS
# ===============================
class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    specialty = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(200), nullable=True) 
    branches = db.Column(db.String(200), nullable=True) 
    schedules = db.relationship('Schedule', backref='doctor', lazy=True)
    appointments = db.relationship('Appointment', backref='doctor', lazy=True)

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False) 
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=True)
    patient_name = db.Column(db.String(100), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    time_slot = db.Column(db.Time, nullable=False)

class Branch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    notes = db.Column(db.String(200), nullable=True)

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=True)

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(100), nullable=False)
    details = db.Column(db.String(200), nullable=False)

# --- USER MODELS ---
class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    case_number = db.Column(db.String(50), nullable=True)
    password = db.Column(db.String(100), nullable=False, default="123")
    # --- Medical Details ---
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(10), nullable=True)           # Male / Female
    blood_type = db.Column(db.String(5), nullable=True)        # A+, B-, O+, AB+, etc.
    phone = db.Column(db.String(20), nullable=True)
    emergency_contact = db.Column(db.String(100), nullable=True)
    medical_history = db.Column(db.Text, nullable=True)        # Chronic conditions
    allergies = db.Column(db.String(300), nullable=True)       # Comma-separated
    current_medications = db.Column(db.Text, nullable=True)    # Comma-separated
    notes = db.Column(db.Text, nullable=True)                  # Doctor/staff notes

    def to_profile(self):
        """Return a dict of patient details for chatbot/triage context."""
        return {
            "id": self.id,
            "name": self.name,
            "case_number": self.case_number,
            "age": self.age,
            "gender": self.gender,
            "blood_type": self.blood_type,
            "medical_history": self.medical_history,
            "allergies": self.allergies,
            "current_medications": self.current_medications,
            "notes": self.notes,
        }

class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(100), nullable=False, default="admin123")

class PatientMemory(db.Model):
    """Long-term conversational memory per patient."""
    id            = db.Column(db.Integer, primary_key=True)
    patient_id    = db.Column(db.Integer, db.ForeignKey('patient.id'), unique=True)
    summary       = db.Column(db.Text, nullable=True)      # Latest session summary
    key_facts     = db.Column(db.Text, nullable=True)      # JSON: symptoms, concerns, prefs
    session_count = db.Column(db.Integer, default=0)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow)

# ── NEW MODELS ────────────────────────────────────────────────────────────────

class Medication(db.Model):
    """Drug catalog — ~80 common hospital medications seeded at startup."""
    __tablename__ = 'medication'
    id                  = db.Column(db.Integer, primary_key=True)
    name                = db.Column(db.String(100), nullable=False, unique=True)
    generic_name        = db.Column(db.String(100), nullable=True)
    category            = db.Column(db.String(100), nullable=True)
    dosage_forms        = db.Column(db.String(200), nullable=True)
    common_side_effects = db.Column(db.Text,        nullable=True)
    contraindications   = db.Column(db.Text,        nullable=True)
    pregnancy_category  = db.Column(db.String(5),   nullable=True)   # A/B/C/D/X
    requires_monitoring = db.Column(db.Boolean,     default=False)
    notes               = db.Column(db.Text,        nullable=True)

class DrugInteraction(db.Model):
    """Known drug-drug interaction pairs (~130 entries seeded at startup)."""
    __tablename__ = 'drug_interaction'
    id             = db.Column(db.Integer, primary_key=True)
    drug_a         = db.Column(db.String(100), nullable=False)
    drug_b         = db.Column(db.String(100), nullable=False)
    severity       = db.Column(db.String(20),  nullable=False)  # mild/moderate/severe/contraindicated
    description    = db.Column(db.Text,        nullable=False)
    recommendation = db.Column(db.Text,        nullable=True)
    mechanism      = db.Column(db.String(300), nullable=True)

class MedicationReminder(db.Model):
    """Scheduled medication reminders per patient."""
    __tablename__ = 'medication_reminder'
    id              = db.Column(db.Integer, primary_key=True)
    patient_id      = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    medication_name = db.Column(db.String(100), nullable=False)
    dosage          = db.Column(db.String(50),  nullable=True)
    frequency       = db.Column(db.String(50),  nullable=True)
    times           = db.Column(db.String(200), nullable=True)  # JSON ["08:00","20:00"]
    active          = db.Column(db.Boolean,     default=True)
    start_date      = db.Column(db.Date,        nullable=True)
    end_date        = db.Column(db.Date,        nullable=True)
    notes           = db.Column(db.Text,        nullable=True)
    created_at      = db.Column(db.DateTime,    default=datetime.utcnow)

class VitalRecord(db.Model):
    """Patient vital signs history."""
    __tablename__ = 'vital_record'
    id               = db.Column(db.Integer, primary_key=True)
    patient_id       = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    recorded_at      = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    recorded_by      = db.Column(db.String(50), nullable=True)    # "patient"|"nurse"|"robot"
    pain_scale       = db.Column(db.Integer,  nullable=True)       # 0–10
    temperature      = db.Column(db.Float,    nullable=True)       # °C
    systolic_bp      = db.Column(db.Integer,  nullable=True)       # mmHg
    diastolic_bp     = db.Column(db.Integer,  nullable=True)       # mmHg
    heart_rate       = db.Column(db.Integer,  nullable=True)       # bpm
    oxygen_sat       = db.Column(db.Float,    nullable=True)       # %
    respiratory_rate = db.Column(db.Integer,  nullable=True)       # br/min
    blood_glucose    = db.Column(db.Float,    nullable=True)       # mmol/L
    weight_kg        = db.Column(db.Float,    nullable=True)
    height_cm        = db.Column(db.Float,    nullable=True)
    notes            = db.Column(db.Text,     nullable=True)
    alerts           = db.Column(db.Text,     nullable=True)       # JSON list of alert strings

    def to_dict(self):
        return {
            "id": self.id, "patient_id": self.patient_id,
            "recorded_at": self.recorded_at.strftime("%Y-%m-%d %H:%M"),
            "recorded_by": self.recorded_by,
            "pain_scale": self.pain_scale, "temperature": self.temperature,
            "systolic_bp": self.systolic_bp, "diastolic_bp": self.diastolic_bp,
            "heart_rate": self.heart_rate, "oxygen_sat": self.oxygen_sat,
            "respiratory_rate": self.respiratory_rate, "blood_glucose": self.blood_glucose,
            "weight_kg": self.weight_kg, "height_cm": self.height_cm,
            "notes": self.notes,
            "alerts": json.loads(self.alerts) if self.alerts else [],
        }

class TriageHistory(db.Model):
    """Full triage session records per patient."""
    __tablename__ = 'triage_history'
    id                  = db.Column(db.Integer, primary_key=True)
    patient_id          = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=True)
    patient_name        = db.Column(db.String(100), nullable=True)
    assessed_at         = db.Column(db.DateTime,    default=datetime.utcnow)
    chief_complaint     = db.Column(db.String(300), nullable=True)
    severity            = db.Column(db.Integer,     nullable=True)   # 1–5
    severity_label      = db.Column(db.String(50),  nullable=True)
    symptoms_json       = db.Column(db.Text,        nullable=True)   # JSON list
    vitals_json         = db.Column(db.Text,        nullable=True)   # JSON dict
    ai_recommendation   = db.Column(db.Text,        nullable=True)
    department_referred = db.Column(db.String(100), nullable=True)
    disposition         = db.Column(db.String(100), nullable=True)   # admitted/discharged/referred

class SymptomHistory(db.Model):
    """Symptom tracking over time per patient."""
    __tablename__ = 'symptom_history'
    id          = db.Column(db.Integer, primary_key=True)
    patient_id  = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    symptoms    = db.Column(db.Text,     nullable=False)   # JSON list
    severity    = db.Column(db.String(20), nullable=True)  # mild/moderate/severe
    ner_results = db.Column(db.Text,     nullable=True)    # JSON from MedicalNER
    context     = db.Column(db.Text,     nullable=True)    # free-text description
    source      = db.Column(db.String(50), nullable=True)  # voice/chat/triage/manual

# ===============================
# DATABASE SETUP
# ===============================
def setup_database(app):
    with app.app_context():
        db.create_all()

        # Add patient_id column to appointment table if it doesn't exist (SQLite migration)
        from sqlalchemy import text as _text
        with db.engine.connect() as _conn:
            try:
                _conn.execute(_text(
                    "ALTER TABLE appointment ADD COLUMN patient_id INTEGER REFERENCES patient(id)"
                ))
                _conn.commit()
                print("[DB] Added patient_id column to appointment table.")
            except Exception:
                pass  # Column already exists

        # ── Seed Drug Catalog ──────────────────────────────────────────────────
        if Medication.query.count() == 0:
            print("[DB] Seeding drug catalog...")
            _DRUGS = [
                # ── Anticoagulants / Antiplatelets ──────────────────────────────
                {"name":"warfarin","generic_name":"Warfarin sodium","category":"Anticoagulant","dosage_forms":"Tablet","common_side_effects":"Bleeding, bruising, nausea, hair loss","contraindications":"Active bleeding, pregnancy (1st/3rd trimester), hemorrhagic stroke","pregnancy_category":"X","requires_monitoring":True,"notes":"Requires regular INR monitoring. Many drug and food interactions (especially vitamin K foods)."},
                {"name":"clopidogrel","generic_name":"Clopidogrel bisulfate","category":"Antiplatelet","dosage_forms":"Tablet","common_side_effects":"Bleeding, bruising, GI upset, rash","contraindications":"Active bleeding, peptic ulcer","pregnancy_category":"B","requires_monitoring":False,"notes":"Do not stop abruptly after stent placement. Avoid omeprazole (reduces efficacy)."},
                {"name":"aspirin","generic_name":"Acetylsalicylic acid","category":"Antiplatelet/NSAID","dosage_forms":"Tablet, enteric-coated tablet","common_side_effects":"GI upset, bleeding, tinnitus (high dose)","contraindications":"Active GI bleeding, age <16 (Reye's syndrome), severe renal impairment","pregnancy_category":"C","requires_monitoring":False,"notes":"Low-dose (75–100mg) for cardioprotection. High-dose analgesic/antipyretic."},
                {"name":"apixaban","generic_name":"Apixaban","category":"Anticoagulant (NOAC)","dosage_forms":"Tablet","common_side_effects":"Bleeding, bruising, nausea","contraindications":"Active bleeding, severe hepatic impairment, prosthetic heart valves","pregnancy_category":"C","requires_monitoring":False,"notes":"No routine INR monitoring needed. Twice daily dosing for AF/DVT."},
                {"name":"rivaroxaban","generic_name":"Rivaroxaban","category":"Anticoagulant (NOAC)","dosage_forms":"Tablet","common_side_effects":"Bleeding, nausea, abdominal pain","contraindications":"Active bleeding, severe hepatic impairment","pregnancy_category":"C","requires_monitoring":False,"notes":"Once daily with evening meal. Use with caution with strong CYP3A4 inhibitors."},
                {"name":"enoxaparin","generic_name":"Enoxaparin sodium","category":"LMWH Anticoagulant","dosage_forms":"Injection (subcutaneous)","common_side_effects":"Injection site bruising, bleeding, heparin-induced thrombocytopenia (rare)","contraindications":"Active major bleeding, thrombocytopenia with positive HIT antibody","pregnancy_category":"B","requires_monitoring":True,"notes":"Monitor anti-Xa levels in renal impairment or extreme weight. Renal dose adjustment required."},
                # ── Antihypertensives ────────────────────────────────────────────
                {"name":"amlodipine","generic_name":"Amlodipine besylate","category":"Calcium Channel Blocker","dosage_forms":"Tablet","common_side_effects":"Ankle oedema, flushing, headache, palpitations","contraindications":"Cardiogenic shock, unstable angina (some formulations)","pregnancy_category":"C","requires_monitoring":False,"notes":"Once daily. Oedema is common — not a sign of fluid retention."},
                {"name":"metoprolol","generic_name":"Metoprolol tartrate/succinate","category":"Beta Blocker","dosage_forms":"Tablet, extended-release tablet, IV","common_side_effects":"Fatigue, bradycardia, cold extremities, depression, wheezing","contraindications":"Severe bradycardia, 2nd/3rd degree heart block, uncontrolled heart failure, asthma","pregnancy_category":"C","requires_monitoring":False,"notes":"Do not stop abruptly. Succinate (XL) is once daily."},
                {"name":"bisoprolol","generic_name":"Bisoprolol fumarate","category":"Beta Blocker","dosage_forms":"Tablet","common_side_effects":"Fatigue, bradycardia, cold extremities, dizziness","contraindications":"Severe bradycardia, cardiogenic shock, uncontrolled asthma","pregnancy_category":"C","requires_monitoring":False,"notes":"Highly cardioselective. Preferred beta blocker in heart failure. Once daily."},
                {"name":"atenolol","generic_name":"Atenolol","category":"Beta Blocker","dosage_forms":"Tablet","common_side_effects":"Fatigue, bradycardia, cold extremities","contraindications":"Bradycardia, heart block, asthma","pregnancy_category":"D","requires_monitoring":False,"notes":"Renal dose adjustment required. Less lipophilic than metoprolol — fewer CNS effects."},
                {"name":"lisinopril","generic_name":"Lisinopril","category":"ACE Inhibitor","dosage_forms":"Tablet","common_side_effects":"Dry cough (10–15%), hyperkalaemia, dizziness, angioedema (rare)","contraindications":"History of angioedema, bilateral renal artery stenosis, pregnancy","pregnancy_category":"D","requires_monitoring":True,"notes":"Monitor K+ and creatinine. Once daily. Cough → switch to ARB."},
                {"name":"ramipril","generic_name":"Ramipril","category":"ACE Inhibitor","dosage_forms":"Capsule, tablet","common_side_effects":"Dry cough, hyperkalaemia, dizziness, renal impairment","contraindications":"History of angioedema, pregnancy, bilateral RAS","pregnancy_category":"D","requires_monitoring":True,"notes":"Renal and K+ monitoring required. Strong evidence in post-MI and heart failure."},
                {"name":"enalapril","generic_name":"Enalapril maleate","category":"ACE Inhibitor","dosage_forms":"Tablet, IV","common_side_effects":"Dry cough, hyperkalaemia, hypotension","contraindications":"Angioedema history, pregnancy","pregnancy_category":"D","requires_monitoring":True,"notes":"Prodrug — converted to enalaprilat in liver. Twice daily dosing."},
                {"name":"losartan","generic_name":"Losartan potassium","category":"ARB","dosage_forms":"Tablet","common_side_effects":"Dizziness, hyperkalaemia, renal impairment","contraindications":"Pregnancy, bilateral renal artery stenosis","pregnancy_category":"D","requires_monitoring":True,"notes":"No cough compared to ACEi. Also reduces uric acid — beneficial in gout. Once daily."},
                {"name":"valsartan","generic_name":"Valsartan","category":"ARB","dosage_forms":"Tablet","common_side_effects":"Dizziness, hyperkalaemia, fatigue","contraindications":"Pregnancy, liver disease","pregnancy_category":"D","requires_monitoring":True,"notes":"Once or twice daily. Combined with sacubitril for heart failure (Entresto)."},
                {"name":"hydrochlorothiazide","generic_name":"Hydrochlorothiazide","category":"Thiazide Diuretic","dosage_forms":"Tablet","common_side_effects":"Hypokalaemia, hyponatraemia, hyperuricaemia, glucose intolerance","contraindications":"Anuria, sulfonamide allergy","pregnancy_category":"B","requires_monitoring":True,"notes":"Monitor electrolytes. May worsen gout. Often combined with ACEi or ARB."},
                {"name":"furosemide","generic_name":"Furosemide","category":"Loop Diuretic","dosage_forms":"Tablet, IV, IM","common_side_effects":"Hypokalaemia, dehydration, ototoxicity (IV rapid infusion), hyperuricaemia","contraindications":"Anuria, severe hypovolaemia","pregnancy_category":"C","requires_monitoring":True,"notes":"Potent diuretic. Monitor K+, Na+, creatinine. Give in morning to avoid nocturia."},
                {"name":"spironolactone","generic_name":"Spironolactone","category":"Potassium-sparing Diuretic / Aldosterone Antagonist","dosage_forms":"Tablet","common_side_effects":"Hyperkalaemia, gynaecomastia (men), menstrual irregularities, renal impairment","contraindications":"Hyperkalaemia, Addison's disease, concurrent K+ supplements with ACEi","pregnancy_category":"C","requires_monitoring":True,"notes":"Monitor K+ and renal function closely. Used in heart failure, hypertension, ascites."},
                {"name":"amiodarone","generic_name":"Amiodarone hydrochloride","category":"Antiarrhythmic","dosage_forms":"Tablet, IV","common_side_effects":"Thyroid dysfunction, photosensitivity, pulmonary toxicity, corneal microdeposits, liver toxicity","contraindications":"Iodine allergy, thyroid disorders, 2nd/3rd degree AV block","pregnancy_category":"D","requires_monitoring":True,"notes":"Many serious drug interactions (warfarin, digoxin, statins). Annual TFT, LFT, CXR required."},
                {"name":"digoxin","generic_name":"Digoxin","category":"Cardiac Glycoside","dosage_forms":"Tablet, IV","common_side_effects":"Nausea, vomiting, visual disturbances (yellow vision), bradycardia, arrhythmias","contraindications":"Ventricular fibrillation, hypertrophic obstructive cardiomyopathy, WPW syndrome","pregnancy_category":"C","requires_monitoring":True,"notes":"Narrow therapeutic index. Monitor serum levels, K+. Many drug interactions."},
                # ── Lipid-lowering ───────────────────────────────────────────────
                {"name":"atorvastatin","generic_name":"Atorvastatin calcium","category":"Statin","dosage_forms":"Tablet","common_side_effects":"Myalgia, elevated liver enzymes, GI upset, headache","contraindications":"Active liver disease, pregnancy, breastfeeding","pregnancy_category":"X","requires_monitoring":True,"notes":"Take at any time of day (unlike other statins). Monitor CK if myalgia. Avoid grapefruit."},
                {"name":"rosuvastatin","generic_name":"Rosuvastatin calcium","category":"Statin","dosage_forms":"Tablet","common_side_effects":"Myalgia, proteinuria (high dose), GI upset","contraindications":"Active liver disease, pregnancy, Asian patients (dose adjustment needed)","pregnancy_category":"X","requires_monitoring":True,"notes":"Most potent statin. Lower doses in Asian patients. Avoid grapefruit (less interaction than other statins)."},
                {"name":"simvastatin","generic_name":"Simvastatin","category":"Statin","dosage_forms":"Tablet","common_side_effects":"Myalgia, rhabdomyolysis (rare, high dose), liver enzyme elevation","contraindications":"Active liver disease, pregnancy, concurrent strong CYP3A4 inhibitors","pregnancy_category":"X","requires_monitoring":True,"notes":"Take at night. 80mg dose associated with rhabdomyolysis — max 40mg routinely. Many interactions."},
                # ── Antidiabetics ────────────────────────────────────────────────
                {"name":"metformin","generic_name":"Metformin hydrochloride","category":"Biguanide Antidiabetic","dosage_forms":"Tablet, extended-release tablet","common_side_effects":"GI upset, nausea, metallic taste, lactic acidosis (rare)","contraindications":"eGFR <30, contrast dye procedures (hold 48h), severe liver disease, excessive alcohol","pregnancy_category":"B","requires_monitoring":True,"notes":"First-line T2DM. Take with food. Stop 48h before iodinated contrast."},
                {"name":"glipizide","generic_name":"Glipizide","category":"Sulfonylurea Antidiabetic","dosage_forms":"Tablet","common_side_effects":"Hypoglycaemia, weight gain, nausea","contraindications":"T1DM, severe renal/hepatic impairment, pregnancy","pregnancy_category":"C","requires_monitoring":True,"notes":"Risk of hypoglycaemia especially if meal delayed. Take 30 min before meals."},
                {"name":"glibenclamide","generic_name":"Glibenclamide (Glyburide)","category":"Sulfonylurea Antidiabetic","dosage_forms":"Tablet","common_side_effects":"Hypoglycaemia, weight gain","contraindications":"Severe renal impairment (accumulates), elderly patients (high hypo risk), pregnancy","pregnancy_category":"C","requires_monitoring":True,"notes":"Higher hypoglycaemia risk than glipizide. Avoid in elderly and renal impairment."},
                {"name":"sitagliptin","generic_name":"Sitagliptin phosphate","category":"DPP-4 Inhibitor Antidiabetic","dosage_forms":"Tablet","common_side_effects":"Nasopharyngitis, headache, pancreatitis (rare)","contraindications":"Severe renal impairment (dose adjust), pancreatitis history","pregnancy_category":"B","requires_monitoring":False,"notes":"Weight-neutral. Renal dose adjustment required. Once daily."},
                {"name":"dapagliflozin","generic_name":"Dapagliflozin","category":"SGLT2 Inhibitor Antidiabetic","dosage_forms":"Tablet","common_side_effects":"UTI, genital mycotic infections, DKA (rare), Fournier's gangrene (rare)","contraindications":"eGFR <45 (limited efficacy), T1DM (DKA risk), recurrent UTIs","pregnancy_category":"C","requires_monitoring":True,"notes":"Also reduces CV events and progression of HF and CKD. Hold before surgery."},
                {"name":"insulin glargine","generic_name":"Insulin glargine","category":"Long-acting Insulin","dosage_forms":"Injection (subcutaneous)","common_side_effects":"Hypoglycaemia, injection site reactions, weight gain","contraindications":"Hypoglycaemia","pregnancy_category":"C","requires_monitoring":True,"notes":"Once daily at same time. Do not mix with other insulins. Clear — not cloudy."},
                {"name":"insulin aspart","generic_name":"Insulin aspart","category":"Rapid-acting Insulin","dosage_forms":"Injection (subcutaneous, IV)","common_side_effects":"Hypoglycaemia, injection site reactions","contraindications":"Hypoglycaemia","pregnancy_category":"B","requires_monitoring":True,"notes":"Give immediately before meals (or after if uncertain about carb intake). Rapid onset 10–20 min."},
                # ── Antibiotics ──────────────────────────────────────────────────
                {"name":"amoxicillin","generic_name":"Amoxicillin trihydrate","category":"Penicillin Antibiotic","dosage_forms":"Capsule, tablet, oral suspension, IV","common_side_effects":"Diarrhoea, rash, nausea, hypersensitivity","contraindications":"Penicillin allergy, mononucleosis (causes rash)","pregnancy_category":"B","requires_monitoring":False,"notes":"Broad-spectrum penicillin. If penicillin allergy → use clarithromycin or doxycycline."},
                {"name":"amoxicillin-clavulanate","generic_name":"Amoxicillin-clavulanic acid","category":"Penicillin + Beta-lactamase Inhibitor","dosage_forms":"Tablet, oral suspension, IV","common_side_effects":"Diarrhoea, nausea, liver enzyme elevation, rash","contraindications":"Penicillin allergy, hepatic dysfunction from prior amoxicillin-clavulanate use","pregnancy_category":"B","requires_monitoring":False,"notes":"Covers more organisms than amoxicillin alone. Monitor LFTs if prolonged use."},
                {"name":"ciprofloxacin","generic_name":"Ciprofloxacin hydrochloride","category":"Fluoroquinolone Antibiotic","dosage_forms":"Tablet, IV, eye/ear drops","common_side_effects":"Nausea, diarrhoea, tendinopathy/rupture, QT prolongation, CNS effects, photosensitivity","contraindications":"History of tendon problems with fluoroquinolones, myasthenia gravis, concurrent QT-prolonging drugs","pregnancy_category":"C","requires_monitoring":False,"notes":"Avoid in children/adolescents. Avoid with antacids. Risk of tendon rupture (especially Achilles, in elderly/steroids)."},
                {"name":"levofloxacin","generic_name":"Levofloxacin","category":"Fluoroquinolone Antibiotic","dosage_forms":"Tablet, IV","common_side_effects":"Nausea, insomnia, QT prolongation, tendinopathy, photosensitivity","contraindications":"Fluoroquinolone hypersensitivity, QT prolongation, myasthenia gravis","pregnancy_category":"C","requires_monitoring":False,"notes":"Respiratory fluoroquinolone. Good atypical coverage. Same tendon rupture warnings as ciprofloxacin."},
                {"name":"azithromycin","generic_name":"Azithromycin dihydrate","category":"Macrolide Antibiotic","dosage_forms":"Tablet, oral suspension, IV","common_side_effects":"GI upset, abdominal cramps, QT prolongation (rare), liver enzyme elevation","contraindications":"Hepatic impairment (use with caution), prior QT prolongation, macrolide allergy","pregnancy_category":"B","requires_monitoring":False,"notes":"Long tissue half-life — 3–5 day courses suffice. Many drug interactions via CYP3A4."},
                {"name":"clarithromycin","generic_name":"Clarithromycin","category":"Macrolide Antibiotic","dosage_forms":"Tablet, extended-release, IV","common_side_effects":"GI upset, metallic taste, QT prolongation, liver enzyme elevation","contraindications":"QT prolongation, concurrent drugs metabolised by CYP3A4 (statins, etc.), macrolide allergy","pregnancy_category":"C","requires_monitoring":False,"notes":"Strong CYP3A4 inhibitor — many interactions. Avoid simvastatin/lovastatin (rhabdomyolysis risk)."},
                {"name":"doxycycline","generic_name":"Doxycycline hyclate/monohydrate","category":"Tetracycline Antibiotic","dosage_forms":"Tablet, capsule, IV","common_side_effects":"Oesophageal irritation, photosensitivity, nausea, tooth discolouration (children)","contraindications":"Children <8 years, pregnancy (2nd/3rd trimester), breastfeeding","pregnancy_category":"D","requires_monitoring":False,"notes":"Take upright with water, do not lie down for 30 min. Avoid antacids/dairy within 2h."},
                {"name":"metronidazole","generic_name":"Metronidazole","category":"Nitroimidazole Antibiotic/Antiprotozoal","dosage_forms":"Tablet, IV, topical, vaginal gel","common_side_effects":"Metallic taste, nausea, disulfiram-like reaction with alcohol, peripheral neuropathy (prolonged)","contraindications":"First trimester of pregnancy, concurrent alcohol, disulfiram use","pregnancy_category":"B","requires_monitoring":False,"notes":"Avoid alcohol during and 48h after treatment (severe flushing/vomiting)."},
                {"name":"vancomycin","generic_name":"Vancomycin hydrochloride","category":"Glycopeptide Antibiotic","dosage_forms":"IV, oral (C.diff only)","common_side_effects":"Nephrotoxicity, ototoxicity, Red Man Syndrome (too rapid IV infusion), phlebitis","contraindications":"IV in hearing loss patients without monitoring","pregnancy_category":"C","requires_monitoring":True,"notes":"Infuse over ≥60 min to prevent Red Man Syndrome. Monitor trough levels, renal function."},
                {"name":"trimethoprim-sulfamethoxazole","generic_name":"Co-trimoxazole","category":"Sulfonamide + Dihydrofolate Reductase Inhibitor Antibiotic","dosage_forms":"Tablet, IV","common_side_effects":"Rash (including Stevens-Johnson), hyperkalaemia, nausea, bone marrow suppression","contraindications":"Sulfonamide allergy, severe renal/hepatic impairment, G6PD deficiency, pregnancy (near term)","pregnancy_category":"C","requires_monitoring":True,"notes":"Contains sulfonamide — check allergy. Increases warfarin effect and methotrexate toxicity."},
                # ── Pain / Anti-inflammatory ──────────────────────────────────────
                {"name":"paracetamol","generic_name":"Paracetamol (Acetaminophen)","category":"Non-opioid Analgesic/Antipyretic","dosage_forms":"Tablet, capsule, oral solution, IV, suppository","common_side_effects":"Liver toxicity (overdose), rash (rare)","contraindications":"Severe hepatic impairment, paracetamol hypersensitivity","pregnancy_category":"B","requires_monitoring":False,"notes":"Safest analgesic in pregnancy. Max 4g/day in adults (2g in liver disease/heavy alcohol use)."},
                {"name":"ibuprofen","generic_name":"Ibuprofen","category":"NSAID","dosage_forms":"Tablet, capsule, oral suspension, topical gel","common_side_effects":"GI upset, GI bleeding, fluid retention, renal impairment, increased CV risk","contraindications":"Active GI bleeding, severe renal impairment, aspirin-exacerbated asthma, 3rd trimester pregnancy","pregnancy_category":"C","requires_monitoring":False,"notes":"Take with food. Avoid in elderly, renal disease, heart failure. Reduces aspirin cardioprotection."},
                {"name":"naproxen","generic_name":"Naproxen sodium","category":"NSAID","dosage_forms":"Tablet","common_side_effects":"GI upset, GI bleeding, fluid retention, renal impairment","contraindications":"Active GI bleeding, severe renal impairment, heart failure, 3rd trimester pregnancy","pregnancy_category":"C","requires_monitoring":False,"notes":"Longer-acting than ibuprofen (twice daily). Lower CV risk among NSAIDs."},
                {"name":"diclofenac","generic_name":"Diclofenac sodium","category":"NSAID","dosage_forms":"Tablet, injection, topical gel, suppository","common_side_effects":"GI upset, liver enzyme elevation, fluid retention, CV events","contraindications":"Active GI bleeding, severe renal/hepatic impairment, heart failure, pregnancy (3rd trimester)","pregnancy_category":"C","requires_monitoring":True,"notes":"Higher CV risk than other NSAIDs. Monitor LFTs with prolonged use."},
                {"name":"tramadol","generic_name":"Tramadol hydrochloride","category":"Weak Opioid Analgesic","dosage_forms":"Tablet, capsule, SR tablet, injection","common_side_effects":"Nausea, vomiting, dizziness, constipation, seizures, serotonin syndrome risk","contraindications":"MAOI use, uncontrolled epilepsy, severe hepatic impairment","pregnancy_category":"C","requires_monitoring":False,"notes":"Lowers seizure threshold. Serotonin syndrome risk with SSRIs/SNRIs. Avoid in poor CYP2D6 metabolisers."},
                {"name":"codeine","generic_name":"Codeine phosphate","category":"Opioid Analgesic/Antitussive","dosage_forms":"Tablet, oral solution, IV","common_side_effects":"Constipation, sedation, nausea, respiratory depression","contraindications":"Children <12 (post-tonsillectomy), ultra-rapid CYP2D6 metabolisers, breastfeeding, severe respiratory disease","pregnancy_category":"C","requires_monitoring":False,"notes":"Prodrug — requires CYP2D6. ~10% of patients don't respond. Addictive potential."},
                {"name":"morphine","generic_name":"Morphine sulphate","category":"Strong Opioid Analgesic","dosage_forms":"Tablet, SR tablet, oral solution, injection","common_side_effects":"Constipation, nausea, sedation, respiratory depression, hypotension","contraindications":"Severe respiratory depression, head injury (raises ICP), paralytic ileus","pregnancy_category":"C","requires_monitoring":True,"notes":"Strong opioid — use with caution. Start low. Regular laxatives required."},
                {"name":"pregabalin","generic_name":"Pregabalin","category":"Anticonvulsant/Neuropathic Pain","dosage_forms":"Capsule, oral solution","common_side_effects":"Dizziness, somnolence, weight gain, peripheral oedema, visual disturbance","contraindications":"Hypersensitivity, rare hereditary galactose intolerance","pregnancy_category":"C","requires_monitoring":False,"notes":"Dose adjust in renal impairment. Misuse potential. Gradual taper on stopping."},
                {"name":"gabapentin","generic_name":"Gabapentin","category":"Anticonvulsant/Neuropathic Pain","dosage_forms":"Capsule, tablet, oral solution","common_side_effects":"Dizziness, somnolence, ataxia, weight gain","contraindications":"Hypersensitivity","pregnancy_category":"C","requires_monitoring":False,"notes":"Renal dose adjustment required. Do not stop abruptly. Misuse/abuse potential."},
                # ── Gastrointestinal ──────────────────────────────────────────────
                {"name":"omeprazole","generic_name":"Omeprazole","category":"Proton Pump Inhibitor","dosage_forms":"Capsule, IV","common_side_effects":"Headache, diarrhoea, hypomagnesaemia (long-term), C.diff risk, fracture risk (prolonged)","contraindications":"Hypersensitivity to PPI","pregnancy_category":"C","requires_monitoring":False,"notes":"30–60 min before meals. Interacts with clopidogrel (reduces efficacy) — use pantoprazole instead."},
                {"name":"pantoprazole","generic_name":"Pantoprazole sodium","category":"Proton Pump Inhibitor","dosage_forms":"Tablet, IV","common_side_effects":"Headache, diarrhoea, hypomagnesaemia (long-term)","contraindications":"Hypersensitivity to PPI","pregnancy_category":"B","requires_monitoring":False,"notes":"Preferred PPI with clopidogrel (fewer CYP2C19 interactions). Take 30–60 min before meals."},
                {"name":"esomeprazole","generic_name":"Esomeprazole magnesium","category":"Proton Pump Inhibitor","dosage_forms":"Capsule, IV","common_side_effects":"Headache, abdominal pain, diarrhoea","contraindications":"Hypersensitivity to PPI","pregnancy_category":"C","requires_monitoring":False,"notes":"S-enantiomer of omeprazole. Once daily before breakfast."},
                {"name":"ondansetron","generic_name":"Ondansetron hydrochloride","category":"5-HT3 Antagonist Antiemetic","dosage_forms":"Tablet, oral dissolution, IV, IM","common_side_effects":"Headache, constipation, QT prolongation","contraindications":"Concurrent apomorphine, congenital QT syndrome","pregnancy_category":"B","requires_monitoring":False,"notes":"IV should be diluted and given slowly. Useful post-operative and chemo nausea."},
                {"name":"metoclopramide","generic_name":"Metoclopramide hydrochloride","category":"Prokinetic Antiemetic","dosage_forms":"Tablet, IV, IM","common_side_effects":"Extrapyramidal effects (young/elderly), tardive dyskinesia (prolonged), sedation","contraindications":"GI obstruction/perforation, Parkinson's disease, phaeochromocytoma","pregnancy_category":"B","requires_monitoring":False,"notes":"Maximum 5 days. Avoid in Parkinson's (worsens symptoms). Extrapyramidal effects → stop immediately."},
                # ── Respiratory ───────────────────────────────────────────────────
                {"name":"salbutamol","generic_name":"Salbutamol sulphate (Albuterol)","category":"Short-acting Beta-2 Agonist Bronchodilator","dosage_forms":"Inhaler (MDI, nebuliser), IV, tablet","common_side_effects":"Tremor, tachycardia, hypokalaemia (high doses), headache","contraindications":"Hypersensitivity","pregnancy_category":"C","requires_monitoring":False,"notes":"Reliever inhaler — use for acute symptoms. If using >3x/week → step up preventer therapy."},
                {"name":"tiotropium","generic_name":"Tiotropium bromide","category":"Long-acting Anticholinergic Bronchodilator","dosage_forms":"Inhaler (HandiHaler, Respimat)","common_side_effects":"Dry mouth, urinary retention, constipation, blurred vision","contraindications":"Hypersensitivity, narrow-angle glaucoma, urinary retention","pregnancy_category":"C","requires_monitoring":False,"notes":"Once daily. COPD controller. Do not use for acute bronchospasm."},
                {"name":"fluticasone","generic_name":"Fluticasone propionate/furoate","category":"Inhaled Corticosteroid","dosage_forms":"Inhaler (MDI, DPI), nasal spray","common_side_effects":"Oral candidiasis, hoarseness, adrenal suppression (high doses)","contraindications":"Hypersensitivity, active pulmonary TB","pregnancy_category":"C","requires_monitoring":False,"notes":"Rinse mouth after use to prevent candidiasis. Preventive — not for acute attacks."},
                {"name":"montelukast","generic_name":"Montelukast sodium","category":"Leukotriene Receptor Antagonist","dosage_forms":"Tablet, granules","common_side_effects":"Headache, GI upset, neuropsychiatric effects (mood changes, depression — FDA warning)","contraindications":"Hypersensitivity","pregnancy_category":"B","requires_monitoring":False,"notes":"Take in evening. Monitor for neuropsychiatric effects. Alternative to ICS in mild asthma."},
                {"name":"theophylline","generic_name":"Theophylline","category":"Xanthine Bronchodilator","dosage_forms":"SR tablet, IV","common_side_effects":"Nausea, arrhythmias, seizures (toxicity), insomnia, tachycardia","contraindications":"Acute porphyria","pregnancy_category":"C","requires_monitoring":True,"notes":"Narrow therapeutic index. Monitor serum levels (target 10–20 mg/L). Many interactions (fluoroquinolones, macrolides)."},
                # ── CNS / Psychiatry ──────────────────────────────────────────────
                {"name":"sertraline","generic_name":"Sertraline hydrochloride","category":"SSRI Antidepressant","dosage_forms":"Tablet, oral concentrate","common_side_effects":"Nausea, diarrhoea, insomnia, sexual dysfunction, serotonin syndrome (overdose/combinations)","contraindications":"MAOI use (within 14 days), pimozide","pregnancy_category":"C","requires_monitoring":False,"notes":"Start low, titrate slowly. Takes 4–6 weeks for full effect. Do not stop abruptly."},
                {"name":"fluoxetine","generic_name":"Fluoxetine hydrochloride","category":"SSRI Antidepressant","dosage_forms":"Capsule, tablet, liquid","common_side_effects":"Insomnia, anxiety, nausea, sexual dysfunction","contraindications":"MAOI use (within 14 days), thioridazine","pregnancy_category":"C","requires_monitoring":False,"notes":"Long half-life — less withdrawal syndrome. Strong CYP2D6 inhibitor — many drug interactions (codeine, tamoxifen)."},
                {"name":"escitalopram","generic_name":"Escitalopram oxalate","category":"SSRI Antidepressant","dosage_forms":"Tablet, oral solution","common_side_effects":"Nausea, insomnia, sexual dysfunction, QT prolongation (high dose)","contraindications":"MAOI use, concurrent QT-prolonging drugs at high dose","pregnancy_category":"C","requires_monitoring":False,"notes":"Once daily. Well-tolerated. Maximum 20mg/day (10mg in elderly/hepatic impairment)."},
                {"name":"venlafaxine","generic_name":"Venlafaxine hydrochloride","category":"SNRI Antidepressant","dosage_forms":"Tablet, SR capsule","common_side_effects":"Nausea, insomnia, hypertension (high dose), sweating, withdrawal syndrome","contraindications":"MAOI use, uncontrolled hypertension","pregnancy_category":"C","requires_monitoring":True,"notes":"Monitor BP especially at doses >150mg/day. Taper slowly to avoid withdrawal."},
                {"name":"duloxetine","generic_name":"Duloxetine hydrochloride","category":"SNRI Antidepressant/Neuropathic Pain","dosage_forms":"Capsule","common_side_effects":"Nausea, dry mouth, constipation, hypertension, urinary retention","contraindications":"MAOI use, uncontrolled narrow-angle glaucoma, hepatic impairment","pregnancy_category":"C","requires_monitoring":False,"notes":"Also approved for neuropathic pain, fibromyalgia, stress incontinence."},
                {"name":"amitriptyline","generic_name":"Amitriptyline hydrochloride","category":"Tricyclic Antidepressant","dosage_forms":"Tablet","common_side_effects":"Dry mouth, constipation, urinary retention, sedation, QT prolongation, weight gain","contraindications":"Recent MI, arrhythmia, MAOI use, closed-angle glaucoma","pregnancy_category":"C","requires_monitoring":False,"notes":"Low dose (10–25mg) for neuropathic pain/migraine prevention. Sedating — take at night."},
                {"name":"diazepam","generic_name":"Diazepam","category":"Benzodiazepine","dosage_forms":"Tablet, oral solution, IV, rectal","common_side_effects":"Sedation, confusion, respiratory depression, dependence, amnesia","contraindications":"Respiratory failure, sleep apnoea, hepatic impairment, myasthenia gravis","pregnancy_category":"D","requires_monitoring":False,"notes":"Short-term use only (2–4 weeks max). Dependence risk. Active metabolite accumulates in elderly."},
                {"name":"lorazepam","generic_name":"Lorazepam","category":"Benzodiazepine","dosage_forms":"Tablet, IV","common_side_effects":"Sedation, respiratory depression, dependence, amnesia","contraindications":"Respiratory failure, sleep apnoea, myasthenia gravis","pregnancy_category":"D","requires_monitoring":False,"notes":"No active metabolites — preferred in elderly and hepatic impairment. IV for status epilepticus."},
                {"name":"haloperidol","generic_name":"Haloperidol","category":"Typical Antipsychotic","dosage_forms":"Tablet, oral solution, IV, IM, depot injection","common_side_effects":"Extrapyramidal effects, tardive dyskinesia, QT prolongation, sedation, hyperprolactinaemia","contraindications":"Parkinson's disease, Lewy body dementia, severe CNS depression","pregnancy_category":"C","requires_monitoring":True,"notes":"Monitor ECG for QT prolongation. Extrapyramidal side effects common — use antiparkinsonian drugs PRN."},
                {"name":"olanzapine","generic_name":"Olanzapine","category":"Atypical Antipsychotic","dosage_forms":"Tablet, orodispersible tablet, IM","common_side_effects":"Weight gain, sedation, metabolic syndrome, hyperglycaemia, tardive dyskinesia","contraindications":"Hypersensitivity, narrow-angle glaucoma","pregnancy_category":"C","requires_monitoring":True,"notes":"Monitor weight, blood glucose, lipids. Significant metabolic side effects."},
                {"name":"sodium valproate","generic_name":"Sodium valproate / Valproic acid","category":"Anticonvulsant/Mood Stabiliser","dosage_forms":"Tablet, SR tablet, IV, oral liquid","common_side_effects":"Weight gain, tremor, hair loss, liver toxicity, pancreatitis, teratogenicity","contraindications":"Pregnancy (severe teratogen), liver disease, urea cycle disorders","pregnancy_category":"D","requires_monitoring":True,"notes":"Highly teratogenic — Valproate Pregnancy Prevention Programme required. Monitor LFTs and levels."},
                {"name":"carbamazepine","generic_name":"Carbamazepine","category":"Anticonvulsant/Mood Stabiliser","dosage_forms":"Tablet, SR tablet, oral liquid, suppository","common_side_effects":"Drowsiness, dizziness, ataxia, diplopia, hyponatraemia, Stevens-Johnson syndrome","contraindications":"AV block, bone marrow depression, MAOI use, Asian HLA-B*1502 genotype (SJS risk)","pregnancy_category":"D","requires_monitoring":True,"notes":"Strong enzyme inducer — many drug interactions. Monitor Na+ (SIADH), LFTs, FBC. Test HLA-B*1502 in Asian patients."},
                {"name":"phenytoin","generic_name":"Phenytoin sodium","category":"Anticonvulsant","dosage_forms":"Capsule, injection, oral suspension","common_side_effects":"Nystagmus, ataxia, gingival hyperplasia, hirsutism, rash, osteoporosis","contraindications":"AV block, sinus bradycardia, sino-atrial block","pregnancy_category":"D","requires_monitoring":True,"notes":"Narrow therapeutic index. Saturable kinetics — small dose increases can cause toxicity. Monitor levels."},
                {"name":"donepezil","generic_name":"Donepezil hydrochloride","category":"Acetylcholinesterase Inhibitor (Dementia)","dosage_forms":"Tablet, orodispersible tablet","common_side_effects":"Nausea, diarrhoea, insomnia, bradycardia, muscle cramps","contraindications":"Sick sinus syndrome, 2nd/3rd degree AV block, peptic ulcer disease (relative)","pregnancy_category":"C","requires_monitoring":False,"notes":"Start with 5mg at night. Can increase to 10mg after 4 weeks. Bradycardia risk — monitor pulse."},
                {"name":"memantine","generic_name":"Memantine hydrochloride","category":"NMDA Receptor Antagonist (Dementia)","dosage_forms":"Tablet, oral solution","common_side_effects":"Dizziness, headache, constipation, confusion","contraindications":"Severe renal impairment (dose adjust)","pregnancy_category":"B","requires_monitoring":False,"notes":"Moderate-severe Alzheimer's. Renal dose adjustment. Can be combined with donepezil."},
                # ── Thyroid ───────────────────────────────────────────────────────
                {"name":"levothyroxine","generic_name":"Levothyroxine sodium","category":"Thyroid Hormone Replacement","dosage_forms":"Tablet","common_side_effects":"Symptoms of hyperthyroidism if overdosed (palpitations, weight loss, tremor)","contraindications":"Untreated adrenal insufficiency, thyrotoxicosis","pregnancy_category":"A","requires_monitoring":True,"notes":"Take on empty stomach, 30–60 min before breakfast. Avoid calcium, iron within 4h. Monitor TFTs every 6–12 months."},
                {"name":"carbimazole","generic_name":"Carbimazole","category":"Antithyroid Drug","dosage_forms":"Tablet","common_side_effects":"Rash, agranulocytosis (rare but serious), arthralgia, hepatotoxicity","contraindications":"Breastfeeding (small amount in milk), previous carbimazole-induced agranulocytosis","pregnancy_category":"D","requires_monitoring":True,"notes":"If sore throat/fever → stop immediately and check FBC (agranulocytosis). Monitor TFTs."},
                # ── Immunosuppressants / Disease-modifying ───────────────────────
                {"name":"prednisolone","generic_name":"Prednisolone","category":"Corticosteroid","dosage_forms":"Tablet, oral solution, IV, topical","common_side_effects":"Hyperglycaemia, hypertension, osteoporosis, Cushing's syndrome, adrenal suppression, GI ulcers","contraindications":"Systemic infection (relative), live vaccines","pregnancy_category":"C","requires_monitoring":True,"notes":"Taper slowly if used >3 weeks. Prescribe bone protection (Ca/VitD, bisphosphonate). Monitor glucose in diabetics."},
                {"name":"dexamethasone","generic_name":"Dexamethasone","category":"Corticosteroid","dosage_forms":"Tablet, IV, IM, eye drops","common_side_effects":"Hyperglycaemia, hypertension, fluid retention, adrenal suppression","contraindications":"Systemic infection (relative)","pregnancy_category":"C","requires_monitoring":True,"notes":"8x more potent than prednisolone. Used in cerebral oedema, COVID-19, anti-emesis."},
                {"name":"hydroxychloroquine","generic_name":"Hydroxychloroquine sulphate","category":"Antimalarial/Disease-modifying Antirheumatic","dosage_forms":"Tablet","common_side_effects":"Retinal toxicity (long-term), GI upset, rash, QT prolongation","contraindications":"Retinal/visual field abnormalities, hypersensitivity, concurrent QT-prolonging drugs","pregnancy_category":"C","requires_monitoring":True,"notes":"Annual ophthalmology review. Max dose 5mg/kg/day (ideal body weight). QT monitoring."},
                {"name":"methotrexate","generic_name":"Methotrexate","category":"Disease-modifying Antirheumatic/Antimetabolite","dosage_forms":"Tablet (weekly), injection","common_side_effects":"Hepatotoxicity, bone marrow suppression, oral ulcers, pneumonitis, teratogenicity","contraindications":"Pregnancy, breastfeeding, immunodeficiency, severe renal/hepatic impairment","pregnancy_category":"X","requires_monitoring":True,"notes":"Weekly dose (not daily!). Always co-prescribe folic acid. Monitor FBC, LFTs, creatinine monthly."},
                {"name":"azathioprine","generic_name":"Azathioprine","category":"Immunosuppressant/DMARD","dosage_forms":"Tablet, IV","common_side_effects":"Bone marrow suppression, nausea, GI upset, hepatotoxicity, lymphoma risk (long-term)","contraindications":"Concurrent allopurinol (without dose reduction), hypersensitivity","pregnancy_category":"D","requires_monitoring":True,"notes":"Test TPMT enzyme activity before starting. Fatal interaction with allopurinol (xanthine oxidase inhibitor)."},
                # ── Supplements / Minerals ────────────────────────────────────────
                {"name":"folic acid","generic_name":"Folic acid","category":"Vitamin B9 Supplement","dosage_forms":"Tablet","common_side_effects":"Rare — GI upset at high doses","contraindications":"Vitamin B12 deficiency (can mask neurological symptoms)","pregnancy_category":"A","requires_monitoring":False,"notes":"5mg daily with methotrexate to reduce side effects. 400mcg pre-conception/1st trimester for neural tube prevention."},
                {"name":"ferrous fumarate","generic_name":"Ferrous fumarate","category":"Iron Supplement","dosage_forms":"Tablet, oral solution","common_side_effects":"Constipation, nausea, dark stools, abdominal pain","contraindications":"Iron overload disorders, haemolytic anaemia without iron deficiency","pregnancy_category":"A","requires_monitoring":True,"notes":"Take on empty stomach for best absorption. Space 2h from levothyroxine, antacids, dairy."},
                {"name":"calcium carbonate","generic_name":"Calcium carbonate","category":"Calcium Supplement / Antacid","dosage_forms":"Tablet, chewable tablet","common_side_effects":"Constipation, hypercalcaemia, kidney stones (high dose)","contraindications":"Hypercalcaemia, renal calculi","pregnancy_category":"A","requires_monitoring":False,"notes":"Take with meals (requires stomach acid for absorption). Space 2h from levothyroxine."},
                {"name":"vitamin d","generic_name":"Cholecalciferol (Vitamin D3)","category":"Vitamin D Supplement","dosage_forms":"Tablet, capsule, drops, IM injection","common_side_effects":"Hypercalcaemia (high dose), nausea","contraindications":"Hypercalcaemia, vitamin D toxicity, sarcoidosis","pregnancy_category":"A","requires_monitoring":True,"notes":"Monitor 25-OH vitamin D and calcium levels. High-dose loading requires medical supervision."},
            ]
            db.session.add_all([Medication(**d) for d in _DRUGS])
            db.session.commit()
            print(f"[DB] Seeded {len(_DRUGS)} medications.")

        # ── Seed Drug Interactions ────────────────────────────────────────────
        if DrugInteraction.query.count() == 0:
            print("[DB] Seeding drug interactions...")
            _IX = [
                # ── Warfarin interactions ─────────────────────────────────────
                {"drug_a":"warfarin","drug_b":"aspirin","severity":"severe","description":"Combined use significantly increases haemorrhagic risk through additive anticoagulation and platelet inhibition.","recommendation":"Avoid unless clearly indicated (e.g., mechanical heart valve, recent ACS). If used together, monitor INR frequently and watch for bleeding signs.","mechanism":"Pharmacodynamic: additive anticoagulant + antiplatelet effects."},
                {"drug_a":"warfarin","drug_b":"ibuprofen","severity":"severe","description":"NSAIDs displace warfarin from plasma proteins, inhibit platelet aggregation, and cause GI mucosal damage — markedly increasing bleeding risk.","recommendation":"Avoid combination. Use paracetamol for analgesia. If NSAID essential, use lowest dose for shortest duration with close INR monitoring.","mechanism":"Pharmacokinetic (protein displacement) + pharmacodynamic (GI toxicity, antiplatelet)."},
                {"drug_a":"warfarin","drug_b":"naproxen","severity":"severe","description":"Same mechanism as warfarin+ibuprofen. Increased INR and GI haemorrhage risk.","recommendation":"Avoid. Use paracetamol instead.","mechanism":"Protein displacement + GI mucosal damage + antiplatelet effect."},
                {"drug_a":"warfarin","drug_b":"diclofenac","severity":"severe","description":"Diclofenac enhances warfarin anticoagulation and increases GI bleeding risk.","recommendation":"Avoid. Monitor INR closely if unavoidable. Use PPI co-prescription.","mechanism":"CYP2C9 inhibition raises warfarin levels + GI mucosal toxicity."},
                {"drug_a":"warfarin","drug_b":"metronidazole","severity":"severe","description":"Metronidazole inhibits CYP2C9, the main enzyme metabolising warfarin, causing 2-3x increase in INR.","recommendation":"Monitor INR closely when starting/stopping metronidazole. Consider dose reduction of warfarin.","mechanism":"CYP2C9 inhibition → decreased warfarin clearance → elevated INR."},
                {"drug_a":"warfarin","drug_b":"ciprofloxacin","severity":"moderate","description":"Ciprofloxacin can increase warfarin effect by reducing gut flora that synthesise vitamin K.","recommendation":"Monitor INR more frequently when starting or stopping ciprofloxacin.","mechanism":"Gut flora reduction → decreased vitamin K synthesis + possible CYP1A2 interaction."},
                {"drug_a":"warfarin","drug_b":"azithromycin","severity":"moderate","description":"Azithromycin can increase warfarin's anticoagulant effect.","recommendation":"Monitor INR within 3–5 days of starting azithromycin.","mechanism":"Not fully established; possible gut flora and CYP3A4 interaction."},
                {"drug_a":"warfarin","drug_b":"clarithromycin","severity":"moderate","description":"Clarithromycin inhibits CYP3A4 and may increase warfarin levels.","recommendation":"Monitor INR closely when starting/stopping clarithromycin.","mechanism":"CYP3A4 inhibition → increased warfarin exposure."},
                {"drug_a":"warfarin","drug_b":"amiodarone","severity":"severe","description":"Amiodarone inhibits CYP2C9 and CYP3A4, dramatically increasing warfarin levels. Can take weeks to manifest.","recommendation":"Reduce warfarin dose by 30–50% when starting amiodarone. Monitor INR weekly until stable.","mechanism":"CYP2C9/CYP3A4 inhibition → markedly increased warfarin plasma levels."},
                {"drug_a":"warfarin","drug_b":"fluconazole","severity":"severe","description":"Fluconazole strongly inhibits CYP2C9 — marked increase in warfarin effect.","recommendation":"Monitor INR closely. Consider warfarin dose reduction. Short-term topical antifungals are safer.","mechanism":"Strong CYP2C9 inhibition → elevated warfarin levels."},
                {"drug_a":"warfarin","drug_b":"sertraline","severity":"moderate","description":"SSRIs impair platelet function and may modestly increase INR.","recommendation":"Monitor INR on initiation and if dose changes.","mechanism":"Serotonin reuptake inhibition in platelets reduces haemostasis."},
                {"drug_a":"warfarin","drug_b":"trimethoprim-sulfamethoxazole","severity":"severe","description":"TMP-SMX inhibits CYP2C9, significantly increasing warfarin levels and INR.","recommendation":"Monitor INR closely. Consider warfarin dose reduction.","mechanism":"CYP2C9 inhibition → reduced warfarin clearance."},
                {"drug_a":"warfarin","drug_b":"omeprazole","severity":"mild","description":"Omeprazole may slightly increase warfarin effect via CYP2C19.","recommendation":"Monitor INR if starting or changing omeprazole. No dose change usually needed.","mechanism":"Weak CYP2C19 inhibition → minor increase in warfarin (S-enantiomer less affected)."},
                {"drug_a":"warfarin","drug_b":"carbamazepine","severity":"moderate","description":"Carbamazepine is a strong CYP inducer that accelerates warfarin metabolism, reducing anticoagulation.","recommendation":"Monitor INR. May require warfarin dose increase. Monitor on drug initiation/cessation.","mechanism":"CYP2C9/CYP3A4 induction → increased warfarin clearance."},
                {"drug_a":"warfarin","drug_b":"phenytoin","severity":"moderate","description":"Complex bidirectional interaction: initially phenytoin increases then decreases warfarin effect.","recommendation":"Monitor INR and phenytoin levels closely. Unpredictable interaction.","mechanism":"Phenytoin inhibits then induces CYP2C9. Also displaces warfarin from albumin."},
                # ── Clopidogrel interactions ──────────────────────────────────
                {"drug_a":"clopidogrel","drug_b":"omeprazole","severity":"moderate","description":"Omeprazole inhibits CYP2C19, reducing conversion of clopidogrel to its active form, potentially reducing antiplatelet efficacy.","recommendation":"Use pantoprazole instead of omeprazole with clopidogrel when a PPI is needed.","mechanism":"CYP2C19 inhibition → reduced clopidogrel bioactivation."},
                {"drug_a":"clopidogrel","drug_b":"aspirin","severity":"moderate","description":"Dual antiplatelet therapy increases bleeding risk. However, this combination is clinically indicated post-ACS/stent.","recommendation":"Use only when clinically indicated (dual antiplatelet therapy post-stent). Review after 12 months.","mechanism":"Additive antiplatelet effects via different mechanisms."},
                # ── NSAID combinations ────────────────────────────────────────
                {"drug_a":"aspirin","drug_b":"ibuprofen","severity":"moderate","description":"Ibuprofen competes with aspirin for COX-1 binding, reducing aspirin's cardioprotective antiplatelet effect.","recommendation":"If both needed, take aspirin 30 min before ibuprofen. Consider alternative analgesic (paracetamol).","mechanism":"Competitive COX-1 binding — ibuprofen blocks aspirin's irreversible COX-1 acetylation."},
                {"drug_a":"ibuprofen","drug_b":"lisinopril","severity":"moderate","description":"NSAIDs reduce renal prostaglandin synthesis, blunting ACE inhibitor antihypertensive effects and risking acute kidney injury.","recommendation":"Avoid NSAIDs in patients on ACE inhibitors. Use paracetamol for analgesia. Monitor BP and renal function.","mechanism":"NSAIDs reduce renal blood flow and tubular sodium excretion, opposing ACE inhibitor effects."},
                {"drug_a":"ibuprofen","drug_b":"ramipril","severity":"moderate","description":"Same mechanism as ibuprofen + lisinopril.","recommendation":"Avoid. Use paracetamol. Monitor renal function if unavoidable.","mechanism":"Reduction of renal prostaglandins opposing ACE inhibitor natriuresis and vasodilatation."},
                {"drug_a":"ibuprofen","drug_b":"losartan","severity":"moderate","description":"NSAIDs reduce efficacy of ARBs and increase risk of acute kidney injury.","recommendation":"Avoid. Use paracetamol. Monitor BP and renal function.","mechanism":"Reduced renal prostaglandins opposing ARB effects on tubular sodium handling."},
                {"drug_a":"ibuprofen","drug_b":"furosemide","severity":"moderate","description":"NSAIDs reduce diuretic and antihypertensive effects of furosemide and increase renal toxicity risk.","recommendation":"Avoid. Monitor fluid status and renal function if unavoidable.","mechanism":"NSAIDs block prostaglandin-mediated natriuresis required for loop diuretic action."},
                {"drug_a":"ibuprofen","drug_b":"prednisolone","severity":"moderate","description":"Concurrent NSAIDs and corticosteroids significantly increase GI ulceration and bleeding risk.","recommendation":"Avoid combination. If essential, add PPI co-prescription. Use paracetamol instead.","mechanism":"Additive GI mucosal damage: NSAIDs inhibit COX-1 (prostaglandins), steroids reduce mucosal repair."},
                {"drug_a":"methotrexate","drug_b":"ibuprofen","severity":"severe","description":"NSAIDs reduce renal clearance of methotrexate, causing dangerous drug accumulation and toxicity.","recommendation":"Avoid all NSAIDs with methotrexate. Use paracetamol. If NSAID essential, reduce MTX dose and monitor closely.","mechanism":"NSAIDs reduce GFR and tubular secretion → methotrexate accumulation → bone marrow suppression, mucositis."},
                {"drug_a":"methotrexate","drug_b":"naproxen","severity":"severe","description":"Same as methotrexate + ibuprofen — reduced MTX clearance → toxicity.","recommendation":"Avoid all NSAIDs with methotrexate.","mechanism":"Impaired renal clearance of methotrexate."},
                {"drug_a":"methotrexate","drug_b":"trimethoprim-sulfamethoxazole","severity":"severe","description":"TMP-SMX and methotrexate both inhibit dihydrofolate reductase — severe additive bone marrow suppression.","recommendation":"Contraindicated. Use an alternative antibiotic (e.g., azithromycin).","mechanism":"Additive DHFR inhibition → folate depletion → bone marrow suppression."},
                # ── ACE inhibitor interactions ─────────────────────────────────
                {"drug_a":"lisinopril","drug_b":"spironolactone","severity":"moderate","description":"Both agents increase serum potassium. Combination can cause life-threatening hyperkalaemia.","recommendation":"Monitor serum potassium weekly when initiating. Avoid high-potassium foods. Beneficial in heart failure with careful monitoring.","mechanism":"ACE inhibition reduces aldosterone (reduces K+ excretion) + aldosterone antagonism → additive K+ retention."},
                {"drug_a":"ramipril","drug_b":"spironolactone","severity":"moderate","description":"Same as lisinopril + spironolactone. Hyperkalaemia risk.","recommendation":"Monitor K+ closely. Use lowest effective doses.","mechanism":"Additive potassium retention."},
                # ── Digoxin interactions ──────────────────────────────────────
                {"drug_a":"digoxin","drug_b":"amiodarone","severity":"severe","description":"Amiodarone increases digoxin plasma levels by ~50–100% (inhibits P-glycoprotein), causing digoxin toxicity.","recommendation":"Reduce digoxin dose by 50% when adding amiodarone. Monitor digoxin levels and ECG.","mechanism":"P-glycoprotein inhibition + reduced renal clearance of digoxin."},
                {"drug_a":"digoxin","drug_b":"verapamil","severity":"severe","description":"Verapamil increases digoxin levels and causes additive AV block and bradycardia.","recommendation":"Avoid combination. If used, reduce digoxin dose by 50% and monitor closely.","mechanism":"P-glycoprotein inhibition raises digoxin levels + additive AV nodal conduction slowing."},
                {"drug_a":"digoxin","drug_b":"ciprofloxacin","severity":"moderate","description":"Ciprofloxacin can increase digoxin levels by altering gut flora that metabolise digoxin.","recommendation":"Monitor digoxin levels and signs of toxicity during and after ciprofloxacin course.","mechanism":"Reduction of Eggerthella lenta gut flora that inactivates digoxin."},
                # ── Beta blocker interactions ──────────────────────────────────
                {"drug_a":"metoprolol","drug_b":"verapamil","severity":"severe","description":"Additive negative chronotropic and inotropic effects can cause severe bradycardia, heart block, or asystole.","recommendation":"Avoid IV verapamil in patients on beta blockers. Oral combination requires close monitoring.","mechanism":"Additive AV node conduction slowing (beta-blockade + calcium channel blockade)."},
                {"drug_a":"bisoprolol","drug_b":"verapamil","severity":"severe","description":"Same mechanism as metoprolol + verapamil. Severe bradycardia and heart block risk.","recommendation":"Avoid IV verapamil with oral beta blockers.","mechanism":"Additive negative chronotropic/dromotropic effects."},
                # ── Statin interactions ────────────────────────────────────────
                {"drug_a":"simvastatin","drug_b":"amiodarone","severity":"severe","description":"Amiodarone inhibits CYP3A4, causing simvastatin accumulation and high risk of myopathy/rhabdomyolysis.","recommendation":"Do not use simvastatin >20mg with amiodarone. Consider switching to rosuvastatin or pravastatin (not CYP3A4 metabolised).","mechanism":"CYP3A4 inhibition → markedly elevated simvastatin levels → muscle toxicity."},
                {"drug_a":"simvastatin","drug_b":"clarithromycin","severity":"severe","description":"Clarithromycin strongly inhibits CYP3A4, causing dangerous accumulation of simvastatin.","recommendation":"Temporarily withhold simvastatin during clarithromycin course. Use azithromycin instead if possible.","mechanism":"CYP3A4 inhibition → >10x increase in simvastatin exposure → rhabdomyolysis."},
                {"drug_a":"atorvastatin","drug_b":"clarithromycin","severity":"moderate","description":"Clarithromycin increases atorvastatin levels via CYP3A4 inhibition.","recommendation":"Temporarily withhold or use lowest dose atorvastatin during clarithromycin course.","mechanism":"CYP3A4 inhibition → increased atorvastatin exposure."},
                # ── Serotonin syndrome risk ────────────────────────────────────
                {"drug_a":"sertraline","drug_b":"tramadol","severity":"moderate","description":"Both drugs increase serotonergic activity. Combination increases risk of serotonin syndrome (agitation, hyperthermia, clonus, autonomic instability).","recommendation":"Avoid combination if possible. If used, monitor for serotonin syndrome symptoms. Use paracetamol/low-dose codeine instead.","mechanism":"SSRI inhibits serotonin reuptake; tramadol inhibits serotonin/noradrenaline reuptake + weak mu-opioid."},
                {"drug_a":"fluoxetine","drug_b":"tramadol","severity":"moderate","description":"Same serotonin syndrome risk. Fluoxetine also inhibits CYP2D6, reducing tramadol conversion to active form (paradoxically).","recommendation":"Avoid. Use alternative analgesic.","mechanism":"Dual serotonergic mechanism + CYP2D6 inhibition."},
                {"drug_a":"sertraline","drug_b":"codeine","severity":"mild","description":"Sertraline inhibits CYP2D6, reducing conversion of codeine to morphine (reduced analgesic effect) but also potentially reducing toxicity.","recommendation":"Codeine may be less effective. Consider alternative analgesic.","mechanism":"CYP2D6 inhibition reduces codeine O-demethylation to morphine."},
                {"drug_a":"fluoxetine","drug_b":"codeine","severity":"moderate","description":"Fluoxetine is a strong CYP2D6 inhibitor — markedly reduces codeine conversion to morphine, negating analgesia.","recommendation":"Use alternative analgesic (paracetamol, NSAIDs). Codeine is ineffective with fluoxetine.","mechanism":"Strong CYP2D6 inhibition → reduced morphine production from codeine."},
                # ── Opioid combinations ────────────────────────────────────────
                {"drug_a":"morphine","drug_b":"diazepam","severity":"severe","description":"Additive CNS and respiratory depression. Risk of apnoea and death.","recommendation":"Avoid routine combination. If both clinically necessary (palliative), use lowest effective doses with monitoring.","mechanism":"Additive CNS/respiratory depression via opioid receptors + GABA-A enhancement."},
                {"drug_a":"codeine","drug_b":"diazepam","severity":"moderate","description":"Additive sedation and respiratory depression.","recommendation":"Use with caution. Avoid in elderly and respiratory impairment.","mechanism":"Additive CNS depression."},
                {"drug_a":"tramadol","drug_b":"diazepam","severity":"moderate","description":"Additive sedation and respiratory depression risk.","recommendation":"Use lowest effective doses. Avoid in elderly.","mechanism":"Additive CNS depression."},
                # ── Theophylline interactions ──────────────────────────────────
                {"drug_a":"theophylline","drug_b":"ciprofloxacin","severity":"moderate","description":"Ciprofloxacin inhibits CYP1A2, increasing theophylline levels and toxicity risk (nausea, seizures, arrhythmias).","recommendation":"Reduce theophylline dose by ~50% when adding ciprofloxacin. Monitor serum theophylline levels.","mechanism":"CYP1A2 inhibition → reduced theophylline clearance."},
                {"drug_a":"theophylline","drug_b":"azithromycin","severity":"moderate","description":"Azithromycin can increase theophylline levels through uncertain mechanism.","recommendation":"Monitor theophylline levels during azithromycin course.","mechanism":"Possible inhibition of theophylline metabolism."},
                {"drug_a":"theophylline","drug_b":"clarithromycin","severity":"moderate","description":"Clarithromycin inhibits CYP3A4, increasing theophylline levels.","recommendation":"Monitor theophylline levels. Reduce dose if toxicity signs appear.","mechanism":"CYP3A4 inhibition."},
                # ── Thyroid interactions ───────────────────────────────────────
                {"drug_a":"levothyroxine","drug_b":"calcium carbonate","severity":"moderate","description":"Calcium carbonate reduces levothyroxine absorption by forming insoluble complexes in the GI tract.","recommendation":"Take levothyroxine at least 4 hours before calcium supplements.","mechanism":"Physical chelation of levothyroxine in the GI tract."},
                {"drug_a":"levothyroxine","drug_b":"ferrous fumarate","severity":"moderate","description":"Iron salts reduce levothyroxine absorption.","recommendation":"Take levothyroxine at least 4 hours before iron supplements.","mechanism":"Formation of insoluble levothyroxine-iron complexes in GI tract."},
                # ── Immunosuppressant interactions ────────────────────────────
                {"drug_a":"azathioprine","drug_b":"allopurinol","severity":"severe","description":"Allopurinol inhibits xanthine oxidase, which metabolises azathioprine's toxic metabolite. Results in 4x increase in azathioprine toxicity (bone marrow suppression, fatal).","recommendation":"Contraindicated. If xanthine oxidase inhibitor needed, use febuxostat with extreme caution and 75% azathioprine dose reduction. Better to switch azathioprine to mycophenolate.","mechanism":"Xanthine oxidase inhibition → accumulation of 6-mercaptopurine toxic metabolites."},
                {"drug_a":"prednisolone","drug_b":"metformin","severity":"mild","description":"Corticosteroids antagonise insulin action, raising blood glucose — may require metformin dose adjustment in diabetics.","recommendation":"Monitor blood glucose when starting/stopping steroids. Adjust antidiabetic therapy accordingly.","mechanism":"Glucocorticoids increase gluconeogenesis and insulin resistance."},
                {"drug_a":"prednisolone","drug_b":"ibuprofen","severity":"moderate","description":"Corticosteroids and NSAIDs together dramatically increase GI ulceration risk.","recommendation":"Avoid combination. If unavoidable, add PPI (omeprazole/pantoprazole).","mechanism":"Additive GI mucosal damage."},
                # ── Anticonvulsant interactions ────────────────────────────────
                {"drug_a":"sodium valproate","drug_b":"carbamazepine","severity":"moderate","description":"Carbamazepine reduces valproate levels through enzyme induction. Valproate inhibits carbamazepine metabolism.","recommendation":"Monitor both drug levels. Complex interaction requiring careful titration.","mechanism":"Bidirectional: CBZ induces valproate metabolism; valproate inhibits CBZ-epoxide hydrolase."},
                {"drug_a":"sodium valproate","drug_b":"aspirin","severity":"moderate","description":"Aspirin displaces valproate from plasma protein and inhibits its metabolism, increasing free valproate levels.","recommendation":"Avoid high-dose aspirin with valproate. Use paracetamol instead.","mechanism":"Protein displacement + metabolic inhibition → elevated free valproate."},
                # ── Metformin interactions ─────────────────────────────────────
                {"drug_a":"metformin","drug_b":"furosemide","severity":"mild","description":"Furosemide can increase metformin levels by competing for tubular secretion and causing volume depletion.","recommendation":"Monitor renal function. Hold metformin if dehydration occurs.","mechanism":"Reduced renal tubular secretion + volume depletion reduces metformin clearance."},
                # ── QT-prolongation risk combos ────────────────────────────────
                {"drug_a":"ciprofloxacin","drug_b":"hydroxychloroquine","severity":"moderate","description":"Both drugs prolong QT interval — additive risk of potentially fatal cardiac arrhythmia (torsades de pointes).","recommendation":"Avoid combination. If both required, obtain baseline ECG and monitor QT regularly.","mechanism":"Additive cardiac K+ channel (hERG) blockade → QT prolongation."},
                {"drug_a":"azithromycin","drug_b":"hydroxychloroquine","severity":"moderate","description":"Additive QT prolongation risk.","recommendation":"Avoid. Obtain ECG before starting combination.","mechanism":"Additive hERG channel blockade."},
                {"drug_a":"haloperidol","drug_b":"metoclopramide","severity":"moderate","description":"Both drugs block dopamine receptors. Additive extrapyramidal side effects and QT prolongation.","recommendation":"Avoid combination. Use ondansetron for nausea in patients on haloperidol.","mechanism":"Additive dopamine D2 antagonism + additive QT prolongation."},
                # ── Parkinson's interactions ───────────────────────────────────
                {"drug_a":"levodopa","drug_b":"metoclopramide","severity":"moderate","description":"Metoclopramide is a central dopamine antagonist that opposes levodopa's therapeutic effect and can worsen Parkinsonism.","recommendation":"Contraindicated in Parkinson's disease. Use domperidone for nausea (peripherally acting only).","mechanism":"Central dopamine D2 blockade opposing levodopa's dopaminergic effect."},
                {"drug_a":"levodopa","drug_b":"haloperidol","severity":"moderate","description":"Haloperidol blocks dopamine receptors, directly opposing levodopa's therapeutic effect.","recommendation":"Avoid antipsychotics in Parkinson's patients. If essential, use clozapine or quetiapine (low D2 affinity).","mechanism":"Dopamine D2 receptor antagonism opposes levodopa."},
                # ── Renal interactions ─────────────────────────────────────────
                {"drug_a":"vancomycin","drug_b":"furosemide","severity":"moderate","description":"Both drugs are nephrotoxic and ototoxic. Combination increases risk of acute kidney injury and hearing loss.","recommendation":"Monitor renal function and vancomycin levels closely. Use lowest effective furosemide dose.","mechanism":"Additive nephrotoxicity and ototoxicity."},
                # ── GI drug interactions ───────────────────────────────────────
                {"drug_a":"metoclopramide","drug_b":"digoxin","severity":"moderate","description":"Metoclopramide accelerates GI motility, reducing digoxin absorption from slow-release formulations.","recommendation":"Monitor digoxin levels. Use liquid or rapid-dissolution formulations if both are essential.","mechanism":"Increased GI motility reduces digoxin absorption time."},
                # ── Antidiabetic interactions ──────────────────────────────────
                {"drug_a":"glipizide","drug_b":"ciprofloxacin","severity":"moderate","description":"Fluoroquinolones can cause both hypoglycaemia and hyperglycaemia in patients on sulfonylureas.","recommendation":"Monitor blood glucose closely during ciprofloxacin therapy.","mechanism":"Fluoroquinolones stimulate insulin secretion unpredictably."},
                {"drug_a":"metformin","drug_b":"alcohol","severity":"moderate","description":"Alcohol potentiates metformin's risk of lactic acidosis by inhibiting gluconeogenesis and increasing lactate production.","recommendation":"Advise against regular alcohol use with metformin. Avoid binge drinking entirely.","mechanism":"Alcohol inhibits lactate clearance → lactic acidosis risk, especially with hepatic impairment."},
                # ── Antidepressant interactions ────────────────────────────────
                {"drug_a":"escitalopram","drug_b":"omeprazole","severity":"mild","description":"Omeprazole inhibits CYP2C19, increasing escitalopram plasma levels and QT prolongation risk.","recommendation":"Use pantoprazole instead or use lower escitalopram doses. Avoid maximum doses.","mechanism":"CYP2C19 inhibition → increased escitalopram exposure."},
                {"drug_a":"venlafaxine","drug_b":"tramadol","severity":"moderate","description":"Both drugs increase serotonin. Risk of serotonin syndrome. Venlafaxine also inhibits CYP2D6, reducing tramadol conversion.","recommendation":"Avoid combination. Use paracetamol or low-dose NSAIDs for analgesia.","mechanism":"Additive serotonergic activity + CYP2D6 inhibition."},
            ]
            db.session.add_all([DrugInteraction(**ix) for ix in _IX])
            db.session.commit()
            print(f"[DB] Seeded {len(_IX)} drug interactions.")

        # 1. Seed patients & staff if empty
        if not Patient.query.first():
            print("Seeding Patient Database (30 patients)...")
            patients = [
                Patient(id=100, name="Ahmed Ali", case_number="CASE-001", password="123",
                        age=52, gender="Male", blood_type="A+", phone="01001234567",
                        emergency_contact="Fatma Ali (wife) - 01009876543",
                        medical_history="Hypertension (10 yrs), Type 2 Diabetes (5 yrs), mild left-ventricular hypertrophy",
                        allergies="Penicillin",
                        current_medications="Amlodipine 5mg daily, Metformin 500mg twice daily, Aspirin 81mg daily",
                        notes="BP well-controlled on current regimen. Last HbA1c 7.2%. Due for echo follow-up."),
                Patient(id=101, name="Sara Hassan", case_number="CASE-002", password="123",
                        age=34, gender="Female", blood_type="O+", phone="01112345678",
                        emergency_contact="Mohamed Hassan (husband) - 01119876543",
                        medical_history="Asthma since childhood, seasonal allergic rhinitis",
                        allergies="Sulfa drugs, dust mites",
                        current_medications="Salbutamol inhaler PRN, Fluticasone nasal spray daily",
                        notes="Asthma well-controlled. Uses inhaler 1-2x/week. Avoid NSAIDs."),
                Patient(id=102, name="Mohamed Ibrahim", case_number="CASE-003", password="123",
                        age=67, gender="Male", blood_type="B+", phone="01223456789",
                        emergency_contact="Hoda Ibrahim (daughter) - 01229876543",
                        medical_history="Coronary artery disease (stent placed 2023), atrial fibrillation, hyperlipidemia",
                        allergies="None known",
                        current_medications="Warfarin 5mg daily, Atorvastatin 40mg daily, Bisoprolol 2.5mg daily, Clopidogrel 75mg daily",
                        notes="INR target 2.0-3.0. Last INR 2.4. High fall risk. Requires anticoagulation monitoring."),
                Patient(id=103, name="Aly Lotfy", case_number="CASE-004", password="123",
                        age=22, gender="Male", blood_type="AB+", phone="01034567890",
                        emergency_contact="Lotfy Family - 01039876543",
                        medical_history="Seasonal allergies, mild asthma",
                        allergies="Dust, Pollen",
                        current_medications="Salbutamol inhaler as needed, Cetirizine 10mg daily",
                        notes="Engineering student. Regular checkups recommended."),
                Patient(id=104, name="Omar Nabil", case_number="CASE-005", password="123",
                        age=45, gender="Male", blood_type="O-", phone="01145678901",
                        emergency_contact="Nadia Nabil (wife) - 01149876543",
                        medical_history="Chronic lower back pain (L4-L5 disc herniation), mild depression",
                        allergies="Ibuprofen (GI bleeding)",
                        current_medications="Pregabalin 75mg twice daily, Paracetamol 1g PRN, Sertraline 50mg daily",
                        notes="MRI 2024 shows stable disc herniation. PT referral active. Avoid heavy lifting."),
                Patient(id=105, name="Nadia Salem", case_number="CASE-006", password="123",
                        age=55, gender="Female", blood_type="A-", phone="01056789012",
                        emergency_contact="Tarek Salem (son) - 01059876543",
                        medical_history="Rheumatoid arthritis (15 yrs), osteoporosis, hypothyroidism",
                        allergies="Methotrexate (liver toxicity)",
                        current_medications="Hydroxychloroquine 200mg twice daily, Levothyroxine 75mcg daily, Calcium/Vitamin D supplement, Alendronate 70mg weekly",
                        notes="DXA scan due in 6 months. Thyroid levels stable. Joint deformity in hands."),
                Patient(id=106, name="Karim Farouk", case_number="CASE-007", password="123",
                        age=19, gender="Male", blood_type="B-", phone="01167890123",
                        emergency_contact="Mona Farouk (mother) - 01169876543",
                        medical_history="Type 1 Diabetes since age 8, celiac disease",
                        allergies="Gluten (celiac), latex",
                        current_medications="Insulin Aspart (mealtime), Insulin Glargine (basal), Gluten-free diet",
                        notes="Uses insulin pump. Last HbA1c 6.8%. Strict gluten-free diet required."),
                Patient(id=107, name="Heba Mahmoud", case_number="CASE-008", password="123",
                        age=41, gender="Female", blood_type="O+", phone="01078901234",
                        emergency_contact="Mahmoud Ezzat (husband) - 01079876543",
                        medical_history="Migraine with aura (chronic), anxiety disorder",
                        allergies="Ergotamine, strong perfumes (trigger)",
                        current_medications="Topiramate 50mg daily, Sumatriptan 50mg PRN, Escitalopram 10mg daily",
                        notes="Migraine diary: 3-4 episodes/month. Avoid triggers: stress, lack of sleep, bright lights."),
                Patient(id=108, name="Youssef Adel", case_number="CASE-009", password="123",
                        age=72, gender="Male", blood_type="A+", phone="01189012345",
                        emergency_contact="Adel Youssef (son) - 01189876543",
                        medical_history="COPD (former smoker, 30 pack-years), benign prostatic hyperplasia, hearing loss (bilateral)",
                        allergies="ACE inhibitors (cough)",
                        current_medications="Tiotropium inhaler daily, Salbutamol inhaler PRN, Tamsulosin 0.4mg daily, Hearing aids",
                        notes="FEV1 55% predicted. Pulmonary rehab recommended. Annual flu and pneumococcal vaccines."),
                Patient(id=109, name="Mariam Tarek", case_number="CASE-010", password="123",
                        age=8, gender="Female", blood_type="O+", phone="01090123456",
                        emergency_contact="Tarek Sami (father) - 01099876543",
                        medical_history="Epilepsy (absence seizures, diagnosed age 5), mild learning disability",
                        allergies="None known",
                        current_medications="Sodium Valproate 200mg twice daily",
                        notes="Seizure-free for 14 months. EEG follow-up scheduled. School support plan in place."),
                Patient(id=110, name="Hassan Mostafa", case_number="CASE-011", password="123",
                        age=60, gender="Male", blood_type="AB-", phone="01201234567",
                        emergency_contact="Amal Mostafa (wife) - 01209876543",
                        medical_history="Chronic kidney disease stage 3, gout, hypertension",
                        allergies="Allopurinol (severe rash)",
                        current_medications="Losartan 50mg daily, Febuxostat 40mg daily, Sodium bicarbonate 500mg twice daily",
                        notes="eGFR 42. Avoid nephrotoxic drugs. Low-protein diet advised. Nephrology follow-up every 3 months."),
                Patient(id=111, name="Aya Mohamed", case_number="CASE-012", password="123",
                        age=25, gender="Female", blood_type="B+", phone="01112234567",
                        emergency_contact="Mohamed Saad (father) - 01119876000",
                        medical_history="Polycystic ovary syndrome (PCOS), insulin resistance, acne",
                        allergies="None known",
                        current_medications="Combined oral contraceptive pill, Metformin 500mg daily, Topical retinoid",
                        notes="BMI 31. Weight management plan. Hormonal profile being monitored."),
                Patient(id=112, name="Amr Sherif", case_number="CASE-013", password="123",
                        age=38, gender="Male", blood_type="A+", phone="01023345678",
                        emergency_contact="Dina Amr (wife) - 01029876000",
                        medical_history="Peptic ulcer disease (H. pylori, treated), GERD, anxiety",
                        allergies="Aspirin (gastric), NSAIDs",
                        current_medications="Omeprazole 20mg daily, Buspirone 10mg twice daily",
                        notes="H. pylori eradicated. Endoscopy clear 2024. Avoid spicy food and late meals."),
                Patient(id=113, name="Dina Wael", case_number="CASE-014", password="123",
                        age=47, gender="Female", blood_type="O-", phone="01134456789",
                        emergency_contact="Wael Hamdy (husband) - 01139876000",
                        medical_history="Breast cancer (stage II, left breast, mastectomy 2023), lymphedema",
                        allergies="Tamoxifen (blood clots risk noted)",
                        current_medications="Anastrozole 1mg daily, Compression sleeve for lymphedema, Calcium/Vitamin D",
                        notes="In remission. Oncology follow-up every 6 months. Mammogram due. Compression therapy ongoing."),
                Patient(id=114, name="Khaled Hossam", case_number="CASE-015", password="123",
                        age=31, gender="Male", blood_type="B+", phone="01045567890",
                        emergency_contact="Hossam Khaled (father) - 01049876000",
                        medical_history="Crohn's disease (ileocolonic), vitamin B12 deficiency",
                        allergies="Mesalamine (headache)",
                        current_medications="Azathioprine 150mg daily, B12 injections monthly, Folic acid 5mg daily",
                        notes="Last colonoscopy showed mild inflammation. Biologic therapy may be needed if flare. Low-residue diet."),
                Patient(id=115, name="Noura Bassem", case_number="CASE-016", password="123",
                        age=63, gender="Female", blood_type="A+", phone="01156678901",
                        emergency_contact="Bassem Adel (husband) - 01159876000",
                        medical_history="Osteoarthritis (bilateral knees), hypertension, obesity (BMI 38)",
                        allergies="Codeine (constipation)",
                        current_medications="Amlodipine 10mg daily, Paracetamol 1g three times daily, Glucosamine supplement",
                        notes="Knee replacement candidate. Weight loss program initiated. Physiotherapy 2x/week."),
                Patient(id=116, name="Tamer Essam", case_number="CASE-017", password="123",
                        age=50, gender="Male", blood_type="O+", phone="01067789012",
                        emergency_contact="Essam Tamer (brother) - 01069876000",
                        medical_history="Hepatitis C (treated, SVR achieved 2022), liver fibrosis (F2), fatty liver",
                        allergies="None known",
                        current_medications="Ursodeoxycholic acid 250mg twice daily, Low-fat diet",
                        notes="SVR confirmed. FibroScan every 12 months. Liver enzymes stable. No alcohol."),
                Patient(id=117, name="Rania Gamal", case_number="CASE-018", password="123",
                        age=36, gender="Female", blood_type="AB+", phone="01178890123",
                        emergency_contact="Gamal Nour (father) - 01179876000",
                        medical_history="Systemic lupus erythematosus (SLE), lupus nephritis class III",
                        allergies="Trimethoprim (rash)",
                        current_medications="Mycophenolate 500mg twice daily, Hydroxychloroquine 200mg daily, Prednisolone 5mg daily, Sunscreen SPF 50",
                        notes="Renal function stable. Avoid sun exposure. Immunosuppressed - avoid live vaccines."),
                Patient(id=118, name="Sherif Walid", case_number="CASE-019", password="123",
                        age=58, gender="Male", blood_type="A-", phone="01089901234",
                        emergency_contact="Walid Sherif (son) - 01089876000",
                        medical_history="Parkinson's disease (diagnosed 2021), mild cognitive impairment, orthostatic hypotension",
                        allergies="Metoclopramide (worsens tremor)",
                        current_medications="Levodopa/Carbidopa 100/25 three times daily, Rivastigmine patch 4.6mg",
                        notes="Tremor-dominant PD. Fall risk assessment done. Occupational therapy referral. Swallow assessment needed."),
                Patient(id=119, name="Layla Samir", case_number="CASE-020", password="123",
                        age=22, gender="Female", blood_type="O+", phone="01190012345",
                        emergency_contact="Samir Ahmed (father) - 01199876000",
                        medical_history="Iron-deficiency anemia (chronic heavy periods), vitamin D deficiency",
                        allergies="None known",
                        current_medications="Ferrous fumarate 210mg twice daily, Vitamin D3 50000 IU weekly, Tranexamic acid during periods",
                        notes="Hb improving (last 10.2). Gynecology referral for menorrhagia workup."),
                Patient(id=120, name="Alaa Ramadan", case_number="CASE-021", password="123",
                        age=44, gender="Male", blood_type="B-", phone="01001123456",
                        emergency_contact="Ramadan Alaa (father) - 01009876111",
                        medical_history="Obstructive sleep apnea (severe, AHI 42), obesity (BMI 40), hypertension",
                        allergies="None known",
                        current_medications="CPAP machine nightly, Lisinopril 20mg daily",
                        notes="CPAP compliance 65%. Weight loss surgery consultation pending. Daytime sleepiness improving."),
                Patient(id=121, name="Mona Sayed", case_number="CASE-022", password="123",
                        age=70, gender="Female", blood_type="A+", phone="01112234000",
                        emergency_contact="Sayed Kamal (son) - 01119876111",
                        medical_history="Heart failure (HFrEF, EF 35%), atrial fibrillation, Type 2 Diabetes",
                        allergies="Digoxin (toxicity history)",
                        current_medications="Sacubitril/Valsartan 50mg twice daily, Dapagliflozin 10mg daily, Furosemide 40mg daily, Apixaban 5mg twice daily, Metformin 500mg daily",
                        notes="Fluid restriction 1.5L/day. Daily weight monitoring. Last echo EF 35%. NYHA class II."),
                Patient(id=122, name="George Hany", case_number="CASE-023", password="123",
                        age=33, gender="Male", blood_type="O+", phone="01023345000",
                        emergency_contact="Hany George (father) - 01029876111",
                        medical_history="Multiple sclerosis (relapsing-remitting, diagnosed 2020), optic neuritis (resolved)",
                        allergies="None known",
                        current_medications="Dimethyl fumarate 240mg twice daily, Vitamin D 2000 IU daily",
                        notes="MRI shows stable lesion load. No relapses in 18 months. Annual neuro review due."),
                Patient(id=123, name="Yasmin Ashraf", case_number="CASE-024", password="123",
                        age=29, gender="Female", blood_type="B+", phone="01134456000",
                        emergency_contact="Ashraf Magdy (father) - 01139876111",
                        medical_history="Hashimoto's thyroiditis, depression, irritable bowel syndrome (IBS-D)",
                        allergies="Lactose intolerant",
                        current_medications="Levothyroxine 100mcg daily, Fluoxetine 20mg daily, Loperamide PRN",
                        notes="TSH stable on current dose. Low-FODMAP diet trial. Mental health stable."),
                Patient(id=124, name="Samy Lotfy", case_number="CASE-025", password="123",
                        age=75, gender="Male", blood_type="AB+", phone="01045567000",
                        emergency_contact="Lotfy Samy (son) - 01049876111",
                        medical_history="Alzheimer's disease (moderate stage), prostate cancer (Gleason 6, watchful waiting), cataracts",
                        allergies="Ciprofloxacin (tendon pain)",
                        current_medications="Donepezil 10mg daily, Memantine 10mg daily, Eye drops (Timolol)",
                        notes="Cognitive decline progressive. Caregiver support needed. PSA stable. Cataract surgery planned."),
                Patient(id=125, name="Hala Nasser", case_number="CASE-026", password="123",
                        age=42, gender="Female", blood_type="O-", phone="01056678111",
                        emergency_contact="Nasser Hala (husband) - 01059876222",
                        medical_history="Graves' disease (hyperthyroidism), anxiety, palpitations",
                        allergies="Propylthiouracil (liver toxicity)",
                        current_medications="Carbimazole 15mg daily, Propranolol 40mg twice daily",
                        notes="Thyroid levels improving. Radioactive iodine therapy under consideration. Eye exam normal."),
                Patient(id=126, name="Tarek Samy", case_number="CASE-027", password="123",
                        age=56, gender="Male", blood_type="A+", phone="01167789222",
                        emergency_contact="Samy Tarek (brother) - 01169876333",
                        medical_history="Peripheral artery disease, Type 2 Diabetes, ex-smoker (quit 2020)",
                        allergies="Contrast dye (mild reaction)",
                        current_medications="Cilostazol 100mg twice daily, Metformin 1000mg twice daily, Rosuvastatin 20mg daily, Aspirin 81mg daily",
                        notes="Claudication improving with exercise. ABI 0.7. Vascular surgery consult if worsens."),
                Patient(id=127, name="Iman Rashid", case_number="CASE-028", password="123",
                        age=48, gender="Female", blood_type="B-", phone="01078890333",
                        emergency_contact="Rashid Omar (husband) - 01079876444",
                        medical_history="Fibromyalgia, chronic fatigue syndrome, TMJ disorder",
                        allergies="Gabapentin (dizziness)",
                        current_medications="Duloxetine 60mg daily, Amitriptyline 10mg at night, Physiotherapy",
                        notes="Pain score averaging 5/10. Sleep study normal. Multidisciplinary pain clinic referral."),
                Patient(id=128, name="Wael Ibrahim", case_number="CASE-029", password="123",
                        age=65, gender="Male", blood_type="O+", phone="01189901444",
                        emergency_contact="Ibrahim Wael (son) - 01189876555",
                        medical_history="Recurrent kidney stones (calcium oxalate), gout, mild CKD stage 2",
                        allergies="None known",
                        current_medications="Potassium citrate 10mEq twice daily, Allopurinol 100mg daily, High fluid intake (3L/day)",
                        notes="Last stone passed 6 months ago. CT KUB clear. Low-oxalate diet counseling done."),
                Patient(id=129, name="Salma Fathy", case_number="CASE-030", password="123",
                        age=16, gender="Female", blood_type="A-", phone="01090012555",
                        emergency_contact="Fathy Salma (father) - 01099876666",
                        medical_history="Scoliosis (thoracolumbar, 28-degree curve), exercise-induced asthma",
                        allergies="None known",
                        current_medications="Salbutamol inhaler PRN (before exercise), Back brace (nighttime)",
                        notes="Curve stable on X-ray. Physiotherapy 3x/week. Brace compliance good. Surgical review if >35 degrees."),
            ]

            staff_members = [
                Staff(id=200, name="Staff Supervisor", role="Admin", password="123"),
                Staff(id=201, name="Nurse Mona Saad", role="Nurse", password="123"),
                Staff(id=202, name="Nurse Ahmed Hamdy", role="Nurse", password="123"),
                Staff(id=203, name="Receptionist Sara", role="Receptionist", password="123"),
                Staff(id=204, name="Admin Tarek Nour", role="Admin", password="123"),
            ]

            # Hash all seeded passwords before committing
            for u in patients + staff_members:
                u.password = generate_password_hash(u.password)
            db.session.add_all(patients + staff_members)
            db.session.commit()
            print("Seeded {} patients and {} staff.".format(len(patients), len(staff_members)))

        # One-time migration: rehash any remaining plaintext passwords
        try:
            needs_commit = False
            for p in Patient.query.all():
                if not p.password.startswith(('pbkdf2:', 'scrypt:', 'argon2')):
                    p.password = generate_password_hash(p.password)
                    needs_commit = True
            for s in Staff.query.all():
                if not s.password.startswith(('pbkdf2:', 'scrypt:', 'argon2')):
                    s.password = generate_password_hash(s.password)
                    needs_commit = True
            if needs_commit:
                db.session.commit()
                print("[SECURITY] Rehashed plaintext passwords in existing DB.")
        except Exception as _e:
            print(f"[SECURITY] Password migration skipped: {_e}")

        # 2. Populate Doctors/Departments from CSV if missing
        if Doctor.query.first() is None:
            print("Populating Medical Data from CSVs...")
            try:
                csv_dir = CURRENT_DIR if (CURRENT_DIR / "Doctors.csv").exists() else PARENT_DIR
                
                # Load Branches
                if (csv_dir / "Branches.csv").exists():
                    with open(csv_dir / "Branches.csv", mode='r', encoding='utf-8') as f:
                        for row in csv.DictReader(f):
                            db.session.add(Branch(name=row.get('Branch Name'), address=row.get('Address'), city=row.get('City'), notes=row.get('Notes')))
                
                # Load Departments
                if (csv_dir / "Departments.csv").exists():
                    with open(csv_dir / "Departments.csv", mode='r', encoding='utf-8') as f:
                        for row in csv.DictReader(f):
                            db.session.add(Department(name=row.get('Department / Service'), description=row.get('Description')))

                # Load Doctors
                if (csv_dir / "Doctors.csv").exists():
                    with open(csv_dir / "Doctors.csv", mode='r', encoding='utf-8') as f:
                        for row in csv.DictReader(f):
                            name = row.get('Name')
                            if name and "Clinic" not in name:
                                doc = Doctor(name=name, specialty=row.get('Specialty'), title=row.get('Title'), branches=row.get('Branches'))
                                db.session.add(doc)
                    db.session.commit()

                # Create Default Schedules
                for doc in Doctor.query.all():
                    # Mon 9-1, Wed 2-5
                    db.session.add(Schedule(doctor_id=doc.id, day_of_week=0, start_time=time_type(9,0), end_time=time_type(13,0)))
                    db.session.add(Schedule(doctor_id=doc.id, day_of_week=2, start_time=time_type(14,0), end_time=time_type(17,0)))
                
                db.session.commit()
                print("Database populated successfully.")
            except Exception as e:
                print(f"[ERROR] Database population failed: {e}")
                db.session.rollback()

        # ── Seed Realistic Doctor Schedules ──────────────────────────────────
        if Schedule.query.count() <= Doctor.query.count() * 2:
            print("[DB] Seeding realistic doctor schedules...")
            try:
                # Remove generic Mon/Wed-only schedules and add specialty-appropriate ones
                Schedule.query.delete()
                _sched_patterns = [
                    # (day_of_week, start_h, end_h)
                    (6, 9, 14), (0, 9, 14), (1, 14, 18), (3, 9, 14), (4, 14, 18),   # pattern A
                    (6, 10, 15), (1, 9, 13), (2, 14, 18), (4, 9, 13),               # pattern B
                    (6, 8, 13), (0, 14, 18), (2, 9, 14), (3, 14, 18),               # pattern C
                    (6, 9, 13), (0, 14, 17), (1, 9, 13), (3, 14, 18), (4, 9, 14),   # pattern D
                    (6, 10, 14), (1, 10, 15), (2, 9, 13), (4, 14, 18),              # pattern E
                ]
                _patterns = [
                    _sched_patterns[0:5], _sched_patterns[5:9],
                    _sched_patterns[9:13], _sched_patterns[13:18], _sched_patterns[18:22],
                ]
                for doc in Doctor.query.all():
                    pat = _patterns[doc.id % len(_patterns)]
                    for (dow, sh, eh) in pat:
                        db.session.add(Schedule(doctor_id=doc.id, day_of_week=dow, start_time=time_type(sh, 0), end_time=time_type(eh, 0)))
                db.session.commit()
                print(f"[DB] Seeded schedules for {Doctor.query.count()} doctors.")
            except Exception as _e:
                print(f"[DB] Schedule seeding error: {_e}")
                db.session.rollback()

        # ── Seed Vital Records ───────────────────────────────────────────────
        if VitalRecord.query.count() == 0:
            print("[DB] Seeding vital records...")
            import random as _rnd
            _rnd.seed(42)
            _now = datetime.now()
            _vitals = []

            # Per-patient vital profiles keyed by patient_id
            # Format: (base_sys, base_dia, base_hr, base_o2, base_rr, base_temp, base_glucose, base_pain, weight, height, notes_pool)
            _profiles = {
                100: (145, 88, 78, 97.0, 16, 36.8, 8.2,  2, 88, 175, ["BP slightly elevated", "Glucose needs tighter control", "Stable on current meds"]),
                101: (115, 72, 72, 98.5, 14, 36.6, 5.1,  0, 62, 165, ["Lung sounds clear", "Asthma well-controlled", "Peak flow normal"]),
                102: (132, 80, 62, 96.5, 16, 36.7, 5.5,  1, 78, 172, ["Heart rate well-controlled on bisoprolol", "INR 2.4 - within range", "Irregular pulse (AF)"]),
                103: (118, 74, 70, 99.0, 14, 36.5, 5.0,  0, 75, 180, ["Healthy young adult", "Mild seasonal congestion", "All vitals normal"]),
                104: (122, 78, 76, 98.0, 15, 36.6, 5.3,  5, 85, 178, ["Back pain 5/10 today", "Pain radiating to left leg", "Mobility improving with PT"]),
                105: (130, 82, 74, 97.5, 15, 36.7, 5.4,  4, 68, 160, ["Joint stiffness in hands", "Thyroid levels stable", "Weight stable"]),
                106: (112, 70, 80, 99.0, 14, 36.5, 12.5, 0, 70, 176, ["Glucose elevated post-meal", "Insulin pump functioning", "No hypo episodes this week"]),
                107: (118, 75, 82, 98.5, 14, 36.6, 5.2,  6, 64, 163, ["Migraine episode yesterday", "Aura reported", "Pain 6/10 during episode"]),
                108: (138, 85, 70, 92.0, 20, 36.8, 5.6,  2, 82, 170, ["O2 sat borderline", "Mild expiratory wheeze", "COPD stable on tiotropium"]),
                109: (100, 65, 90, 99.0, 18, 36.5, 4.8,  0, 28, 128, ["Pediatric vitals normal", "No seizure activity", "Alert and oriented"]),
                110: (148, 90, 72, 97.0, 16, 36.7, 5.8,  3, 90, 174, ["BP above target", "eGFR stable at 42", "Gout flare resolved"]),
                111: (116, 74, 76, 98.5, 14, 36.6, 6.0,  1, 82, 164, ["Insulin resistance noted", "Weight management ongoing", "Vitals stable"]),
                112: (120, 76, 78, 98.0, 15, 36.7, 5.2,  2, 76, 175, ["GI symptoms improved", "Anxiety managed", "GERD controlled on PPI"]),
                113: (118, 74, 80, 98.0, 15, 36.6, 5.1,  3, 65, 162, ["Post-mastectomy stable", "Lymphedema mild", "No new symptoms"]),
                114: (110, 68, 74, 98.5, 14, 36.7, 5.0,  4, 72, 177, ["Mild abdominal tenderness", "Crohn's partially controlled", "Weight stable"]),
                115: (152, 92, 76, 97.0, 16, 36.8, 5.7,  6, 105, 162, ["BP poorly controlled", "Knee pain bilateral 6/10", "Weight unchanged"]),
                116: (124, 78, 72, 97.5, 15, 36.7, 5.3,  1, 84, 176, ["Liver enzymes stable", "No jaundice", "Diet compliance good"]),
                117: (108, 68, 78, 98.0, 14, 36.6, 5.1,  2, 58, 160, ["SLE stable", "Renal function preserved", "Mild joint pain"]),
                118: (105, 62, 68, 97.5, 15, 36.7, 5.4,  3, 74, 172, ["Orthostatic BP drop noted", "Tremor stable", "Gait steady with walker"]),
                119: (108, 68, 82, 98.5, 14, 36.5, 4.9,  2, 55, 162, ["Mild pallor noted", "Hb improving on iron", "Fatigue reducing"]),
                120: (142, 88, 74, 94.0, 16, 36.8, 5.5,  1, 120, 180, ["Daytime SpO2 borderline", "CPAP compliance improving", "Neck circumference 44cm"]),
                121: (128, 78, 72, 95.0, 18, 36.7, 7.8,  3, 72, 158, ["Mild peripheral edema", "Weight up 1kg from last visit", "Lungs: bibasilar crackles"]),
                122: (118, 72, 74, 98.5, 14, 36.6, 5.0,  1, 78, 180, ["MS stable", "No new neurological deficits", "Vision normal"]),
                123: (114, 72, 78, 98.5, 14, 36.6, 5.2,  2, 60, 165, ["Thyroid stable on levothyroxine", "Mood improved", "IBS symptoms moderate"]),
                124: (136, 82, 68, 96.5, 16, 36.7, 5.6,  0, 70, 168, ["Oriented x1 (person only)", "Caregiver reports wandering", "PSA stable"]),
                125: (125, 78, 96, 98.5, 16, 36.8, 5.3,  1, 62, 164, ["Resting tachycardia (thyroid)", "Thyroid levels improving", "Tremor mild"]),
                126: (140, 86, 76, 97.0, 16, 36.7, 9.5,  3, 88, 176, ["Claudication at 200m walking", "Glucose poorly controlled", "Foot pulses diminished"]),
                127: (112, 70, 76, 98.5, 14, 36.6, 5.1,  5, 66, 166, ["Tender points positive", "Sleep quality poor", "Pain widespread 5/10"]),
                128: (138, 84, 72, 97.5, 15, 36.7, 6.2,  4, 82, 174, ["Mild flank tenderness", "Urate 0.42 mmol/L", "Hydration adequate"]),
                129: (110, 68, 78, 99.0, 15, 36.5, 4.9,  1, 52, 162, ["Scoliosis curve stable 28°", "No respiratory compromise", "Brace compliant"]),
            }

            _recorders = ["nurse", "robot", "patient"]
            for pid, (s_bp, d_bp, hr, o2, rr, temp, glu, pain, wt, ht, notes_list) in _profiles.items():
                n_records = _rnd.randint(5, 10)
                for i in range(n_records):
                    days_ago = _rnd.randint(1, 90)
                    hour = _rnd.choice([8, 9, 10, 11, 14, 15, 16])
                    rec_time = _now - timedelta(days=days_ago, hours=_rnd.randint(0, 3))
                    rec_time = rec_time.replace(hour=hour, minute=_rnd.choice([0, 15, 30, 45]))

                    v_sys = s_bp + _rnd.randint(-12, 12)
                    v_dia = d_bp + _rnd.randint(-8, 8)
                    v_hr  = hr  + _rnd.randint(-8, 8)
                    v_o2  = round(min(100.0, o2 + _rnd.uniform(-1.5, 1.0)), 1)
                    v_rr  = rr  + _rnd.randint(-2, 3)
                    v_temp = round(temp + _rnd.uniform(-0.3, 0.5), 1)
                    v_glu = round(glu + _rnd.uniform(-1.5, 2.5), 1)
                    v_pain = max(0, min(10, pain + _rnd.randint(-2, 2)))

                    alerts = []
                    if v_sys >= 140 or v_dia >= 90:
                        alerts.append("Hypertension alert")
                    if v_o2 < 94:
                        alerts.append("Low oxygen saturation")
                    if v_hr > 100:
                        alerts.append("Tachycardia")
                    if v_hr < 50:
                        alerts.append("Bradycardia")
                    if v_glu > 11.0:
                        alerts.append("Hyperglycemia")
                    if v_temp >= 37.5:
                        alerts.append("Low-grade fever")
                    if v_pain >= 7:
                        alerts.append("Significant pain")

                    _vitals.append(VitalRecord(
                        patient_id=pid, recorded_at=rec_time,
                        recorded_by=_rnd.choice(_recorders),
                        pain_scale=v_pain, temperature=v_temp,
                        systolic_bp=v_sys, diastolic_bp=v_dia,
                        heart_rate=v_hr, oxygen_sat=v_o2,
                        respiratory_rate=v_rr, blood_glucose=v_glu,
                        weight_kg=round(wt + _rnd.uniform(-1, 1), 1),
                        height_cm=ht,
                        notes=_rnd.choice(notes_list),
                        alerts=json.dumps(alerts) if alerts else None,
                    ))

            db.session.add_all(_vitals)
            db.session.commit()
            print(f"[DB] Seeded {len(_vitals)} vital records.")

        # ── Seed Triage History ──────────────────────────────────────────────
        if TriageHistory.query.count() == 0:
            print("[DB] Seeding triage history...")
            import random as _rnd
            _rnd.seed(43)
            _now = datetime.now()
            _triage = []

            _triage_data = [
                # (patient_id, name, complaints)
                # Each complaint: (chief_complaint, severity, severity_label, symptoms, dept, disposition, recommendation)
                (100, "Ahmed Ali", [
                    ("Dizziness and headache", 3, "Urgent", ["dizziness", "headache", "blurred vision"], "Cardiology", "discharged", "BP 162/95. Amlodipine dose increase recommended. Follow-up in 1 week."),
                    ("Routine diabetes follow-up", 5, "Non-urgent", ["fatigue", "increased thirst"], "Internal Medicine", "discharged", "HbA1c 7.2%. Continue current regimen. Dietary counseling provided."),
                    ("Chest tightness during exercise", 2, "Emergent", ["chest tightness", "shortness of breath", "sweating"], "Cardiology", "admitted", "ECG normal sinus. Troponin negative. Stress test ordered."),
                ]),
                (101, "Sara Hassan", [
                    ("Acute asthma exacerbation", 2, "Emergent", ["wheezing", "shortness of breath", "chest tightness", "cough"], "Pulmonology", "discharged", "Peak flow 65%. Nebulizer given. Prednisolone 5-day course. Step-up preventer."),
                    ("Allergic rhinitis flare", 4, "Less urgent", ["sneezing", "nasal congestion", "itchy eyes", "runny nose"], "ENT", "discharged", "Seasonal flare. Antihistamine added. Nasal spray continued."),
                ]),
                (102, "Mohamed Ibrahim", [
                    ("Palpitations and dizziness", 2, "Emergent", ["palpitations", "dizziness", "fatigue", "irregular heartbeat"], "Cardiology", "admitted", "AF with rapid ventricular response (HR 132). Bisoprolol dose increased. INR 2.1."),
                    ("Bruising on forearms", 3, "Urgent", ["easy bruising", "fatigue"], "Hematology", "discharged", "INR 3.8 - supratherapeutic. Warfarin held for 2 days. Recheck in 3 days."),
                    ("Routine cardiology follow-up", 5, "Non-urgent", ["none"], "Cardiology", "discharged", "Stable on current regimen. INR 2.4. Echo stable. Continue current meds."),
                ]),
                (104, "Omar Nabil", [
                    ("Severe back pain radiating to leg", 3, "Urgent", ["lower back pain", "leg numbness", "difficulty walking", "sciatica"], "Orthopedics", "discharged", "No red flags. Pregabalin dose adjusted. Physiotherapy intensified."),
                    ("Depressed mood and insomnia", 3, "Urgent", ["low mood", "insomnia", "loss of appetite", "fatigue"], "Psychiatry", "discharged", "Sertraline dose increased to 100mg. Sleep hygiene counseling. Follow-up in 2 weeks."),
                ]),
                (105, "Nadia Salem", [
                    ("Joint swelling in hands", 3, "Urgent", ["joint swelling", "morning stiffness", "pain in fingers", "reduced grip"], "Rheumatology", "discharged", "RA flare. ESR elevated. Short course prednisolone. Rheumatology follow-up."),
                    ("Fatigue and cold intolerance", 4, "Less urgent", ["fatigue", "cold intolerance", "weight gain", "dry skin"], "Endocrinology", "discharged", "TSH 8.2 - hypothyroid. Levothyroxine increased to 100mcg. Recheck in 6 weeks."),
                ]),
                (106, "Karim Farouk", [
                    ("Hypoglycemic episode", 2, "Emergent", ["sweating", "tremor", "confusion", "hunger", "palpitations"], "Endocrinology", "discharged", "BG 2.8 mmol/L. Glucose given. Insulin dose adjusted. CGM review done."),
                    ("Abdominal pain after eating", 4, "Less urgent", ["abdominal pain", "bloating", "diarrhea"], "Gastroenterology", "discharged", "Likely celiac-related. Dietary review. Strict gluten-free diet reinforced."),
                ]),
                (108, "Youssef Adel", [
                    ("Worsening breathlessness", 2, "Emergent", ["shortness of breath", "productive cough", "wheeze", "reduced exercise tolerance"], "Pulmonology", "admitted", "COPD exacerbation. SpO2 88%. Nebulizers, steroids, antibiotics started. Admission for monitoring."),
                    ("Difficulty urinating", 4, "Less urgent", ["urinary hesitancy", "weak stream", "nocturia", "incomplete voiding"], "Urology", "discharged", "BPH symptoms worsening. Tamsulosin continued. Urology referral for flow study."),
                ]),
                (109, "Mariam Tarek", [
                    ("Brief staring episode at school", 3, "Urgent", ["staring spell", "unresponsiveness", "lip smacking"], "Pediatric Neurology", "discharged", "Possible absence seizure breakthrough. Valproate level sub-therapeutic. Dose increased."),
                ]),
                (110, "Hassan Mostafa", [
                    ("Swollen painful big toe", 3, "Urgent", ["joint pain", "swelling", "redness", "warmth in toe"], "Rheumatology", "discharged", "Acute gout flare. Colchicine given. Febuxostat continued. Renal function checked."),
                    ("Elevated creatinine on labs", 3, "Urgent", ["fatigue", "reduced urine output", "nausea"], "Nephrology", "discharged", "eGFR dropped to 38. Medication review. Nephrology follow-up expedited."),
                ]),
                (115, "Noura Bassem", [
                    ("Knee pain and swelling", 3, "Urgent", ["knee pain", "joint swelling", "difficulty walking", "crepitus"], "Orthopedics", "discharged", "Severe bilateral OA. Joint aspiration done. Steroid injection given. Surgical consult."),
                    ("Headache and blurred vision", 2, "Emergent", ["headache", "blurred vision", "nausea"], "Emergency", "discharged", "BP 185/105. Hypertensive urgency. IV labetalol. Amlodipine dose maximized."),
                ]),
                (118, "Sherif Walid", [
                    ("Increased tremor and falls", 3, "Urgent", ["tremor", "unsteady gait", "falls", "muscle rigidity"], "Neurology", "discharged", "PD progression. Levodopa timing adjusted. Falls prevention program. OT assessment."),
                    ("Orthostatic dizziness", 3, "Urgent", ["dizziness on standing", "lightheadedness", "near-syncope"], "Neurology", "discharged", "Significant orthostatic drop (150/85 to 105/60). Fludrocortisone considered."),
                ]),
                (121, "Mona Sayed", [
                    ("Worsening shortness of breath", 2, "Emergent", ["shortness of breath", "orthopnea", "leg swelling", "weight gain"], "Cardiology", "admitted", "HF decompensation. Weight up 3kg. IV furosemide. Fluid restriction reinforced."),
                    ("Palpitations and fatigue", 3, "Urgent", ["palpitations", "fatigue", "dizziness"], "Cardiology", "discharged", "AF with controlled rate. Apixaban therapeutic. Echo unchanged EF 35%."),
                    ("High blood sugar readings", 3, "Urgent", ["polyuria", "polydipsia", "fatigue"], "Endocrinology", "discharged", "BG averaging 14 mmol/L. Metformin dose increased. Dapagliflozin continued."),
                ]),
                (124, "Samy Lotfy", [
                    ("Confusion and agitation", 3, "Urgent", ["confusion", "agitation", "wandering", "sleep disturbance"], "Neurology", "discharged", "Alzheimer's behavioral exacerbation. Memantine dose adjusted. Caregiver education."),
                    ("Urinary retention", 3, "Urgent", ["inability to urinate", "lower abdominal pain", "discomfort"], "Urology", "discharged", "Catheterized. Residual 450ml. Prostate evaluation. Alpha-blocker started."),
                ]),
                (126, "Tarek Samy", [
                    ("Leg pain when walking", 3, "Urgent", ["claudication", "leg pain", "numbness in feet", "cold feet"], "Vascular Surgery", "discharged", "ABI 0.65. Claudication worsening. Exercise program. Vascular referral expedited."),
                    ("Foot ulcer not healing", 2, "Emergent", ["non-healing wound", "redness", "swelling", "discharge"], "Vascular Surgery", "admitted", "Diabetic foot ulcer Wagner grade 2. IV antibiotics. Wound care. Vascular assessment."),
                ]),
                (127, "Iman Rashid", [
                    ("Widespread body pain", 3, "Urgent", ["widespread pain", "fatigue", "sleep disturbance", "brain fog"], "Rheumatology", "discharged", "Fibromyalgia flare. Pain score 7/10. Duloxetine increased. CBT referral."),
                ]),
                (129, "Salma Fathy", [
                    ("Back pain and posture concerns", 4, "Less urgent", ["back pain", "postural asymmetry", "fatigue after standing"], "Orthopedics", "discharged", "Scoliosis curve 28°. No progression. Brace compliant. Continue physiotherapy."),
                    ("Breathing difficulty during sports", 3, "Urgent", ["shortness of breath", "chest tightness", "cough after running"], "Pulmonology", "discharged", "Exercise-induced bronchoconstriction confirmed. Salbutamol 15 min pre-exercise."),
                ]),
            ]

            for pid, pname, complaints in _triage_data:
                for idx, (cc, sev, sev_label, symp, dept, disp, rec) in enumerate(complaints):
                    days_ago = 80 - idx * 25 + _rnd.randint(-5, 5)
                    assessed = _now - timedelta(days=max(1, days_ago))
                    assessed = assessed.replace(hour=_rnd.choice([8, 9, 10, 11, 13, 14, 15]), minute=_rnd.randint(0, 59))

                    v = {
                        "heart_rate": 70 + _rnd.randint(-10, 30),
                        "systolic_bp": 120 + _rnd.randint(-15, 40),
                        "diastolic_bp": 75 + _rnd.randint(-10, 20),
                        "oxygen_sat": round(96 + _rnd.uniform(-4, 3), 1),
                        "temperature": round(36.6 + _rnd.uniform(-0.2, 1.0), 1),
                        "respiratory_rate": 15 + _rnd.randint(-2, 6),
                    }

                    _triage.append(TriageHistory(
                        patient_id=pid, patient_name=pname,
                        assessed_at=assessed,
                        chief_complaint=cc, severity=sev, severity_label=sev_label,
                        symptoms_json=json.dumps(symp),
                        vitals_json=json.dumps(v),
                        ai_recommendation=rec,
                        department_referred=dept, disposition=disp,
                    ))

            db.session.add_all(_triage)
            db.session.commit()
            print(f"[DB] Seeded {len(_triage)} triage history records.")

        # ── Seed Symptom History ─────────────────────────────────────────────
        if SymptomHistory.query.count() == 0:
            print("[DB] Seeding symptom history...")
            import random as _rnd
            _rnd.seed(44)
            _now = datetime.now()
            _symptoms = []

            _symptom_data = [
                (100, [
                    (["headache", "dizziness", "fatigue"], "moderate", "voice", "Felt dizzy after skipping medication"),
                    (["thirst", "frequent urination", "blurred vision"], "mild", "chat", "Glucose running high this week"),
                    (["chest discomfort", "shortness of breath"], "severe", "triage", "During morning walk, felt chest tightness"),
                ]),
                (101, [
                    (["wheezing", "cough", "chest tightness"], "severe", "voice", "Asthma attack triggered by dust"),
                    (["sneezing", "runny nose", "itchy eyes"], "mild", "chat", "Spring allergies acting up"),
                ]),
                (102, [
                    (["palpitations", "dizziness", "fatigue"], "severe", "triage", "Heart racing, felt like skipping beats"),
                    (["bruising", "nosebleed"], "moderate", "voice", "Easy bruising on arms, INR was high"),
                ]),
                (104, [
                    (["lower back pain", "leg numbness", "sciatica"], "severe", "voice", "Pain shooting down left leg, can barely walk"),
                    (["insomnia", "low mood", "loss of appetite"], "moderate", "chat", "Haven't slept well in weeks"),
                    (["back stiffness", "reduced mobility"], "mild", "manual", "Morning stiffness improving with PT"),
                ]),
                (106, [
                    (["sweating", "tremor", "confusion"], "severe", "triage", "Hypoglycemic episode at university"),
                    (["bloating", "abdominal pain"], "mild", "chat", "Ate something with gluten accidentally"),
                ]),
                (108, [
                    (["productive cough", "breathlessness", "wheeze"], "severe", "triage", "Cough worse for 3 days, yellow sputum"),
                    (["fatigue", "reduced exercise tolerance"], "moderate", "voice", "Can't walk to the corner store anymore"),
                ]),
                (110, [
                    (["joint pain", "swelling", "warmth"], "severe", "triage", "Big toe red and swollen overnight"),
                    (["fatigue", "nausea", "reduced appetite"], "moderate", "chat", "Feeling unwell, labs showed high creatinine"),
                ]),
                (115, [
                    (["knee pain", "joint stiffness", "crepitus"], "severe", "voice", "Can barely get up from chair"),
                    (["headache", "blurred vision", "nausea"], "severe", "triage", "Worst headache of my life, vision blurry"),
                ]),
                (118, [
                    (["tremor", "muscle rigidity", "slow movement"], "moderate", "voice", "Tremor worse in the mornings"),
                    (["dizziness", "near-syncope"], "severe", "triage", "Almost fainted getting out of bed"),
                ]),
                (121, [
                    (["shortness of breath", "leg swelling", "weight gain"], "severe", "triage", "Gained 3kg in a week, ankles very swollen"),
                    (["fatigue", "palpitations"], "moderate", "voice", "Heart feels like it's fluttering"),
                    (["thirst", "frequent urination", "fatigue"], "moderate", "chat", "Blood sugar readings very high"),
                ]),
                (126, [
                    (["leg pain", "cramping", "cold feet"], "moderate", "voice", "Pain in calves when walking 100m"),
                    (["foot wound", "redness", "discharge"], "severe", "triage", "Cut on foot not healing, looks infected"),
                ]),
                (127, [
                    (["widespread pain", "fatigue", "brain fog"], "severe", "voice", "Everything hurts, can't concentrate"),
                    (["sleep disturbance", "jaw pain", "headache"], "moderate", "chat", "TMJ acting up, grinding teeth at night"),
                ]),
            ]

            for pid, entries in _symptom_data:
                for idx, (syms, severity, source, ctx) in enumerate(entries):
                    days_ago = 70 - idx * 20 + _rnd.randint(-5, 5)
                    rec_at = _now - timedelta(days=max(1, days_ago))
                    rec_at = rec_at.replace(hour=_rnd.choice([8, 9, 10, 14, 15, 16]), minute=_rnd.randint(0, 59))

                    ner = [{"entity": s, "label": "SYMPTOM"} for s in syms]

                    _symptoms.append(SymptomHistory(
                        patient_id=pid, recorded_at=rec_at,
                        symptoms=json.dumps(syms), severity=severity,
                        ner_results=json.dumps(ner),
                        context=ctx, source=source,
                    ))

            db.session.add_all(_symptoms)
            db.session.commit()
            print(f"[DB] Seeded {len(_symptoms)} symptom history records.")

        # ── Seed Appointments ────────────────────────────────────────────────
        if Appointment.query.count() < 5:
            print("[DB] Seeding appointments...")
            import random as _rnd
            _rnd.seed(45)
            _now = datetime.now()
            _appts = []

            # Map specialties to patient IDs who would see those doctors
            _specialty_patients = {
                "Cardiology": [(100, "Ahmed Ali"), (102, "Mohamed Ibrahim"), (121, "Mona Sayed")],
                "Internal Medicine": [(100, "Ahmed Ali"), (116, "Tamer Essam")],
                "Pulmonology": [(101, "Sara Hassan"), (108, "Youssef Adel"), (129, "Salma Fathy")],
                "Orthopedics": [(104, "Omar Nabil"), (115, "Noura Bassem"), (129, "Salma Fathy")],
                "Endocrinology": [(106, "Karim Farouk"), (123, "Yasmin Ashraf"), (125, "Hala Nasser")],
                "Rheumatology": [(105, "Nadia Salem"), (110, "Hassan Mostafa"), (117, "Rania Gamal"), (127, "Iman Rashid")],
                "Neurology": [(107, "Heba Mahmoud"), (118, "Sherif Walid"), (122, "George Hany"), (124, "Samy Lotfy")],
                "Dermatology": [(111, "Aya Mohamed"), (103, "Aly Lotfy")],
                "Gastroenterology": [(112, "Amr Sherif"), (114, "Khaled Hossam")],
                "Urology": [(108, "Youssef Adel"), (128, "Wael Ibrahim"), (124, "Samy Lotfy")],
                "Pediatrics": [(109, "Mariam Tarek")],
                "Psychiatry": [(104, "Omar Nabil"), (107, "Heba Mahmoud")],
                "Nephrology": [(110, "Hassan Mostafa")],
                "Oncology": [(113, "Dina Wael")],
                "Vascular Surgery": [(126, "Tarek Samy")],
            }

            doctors = Doctor.query.all()
            doc_by_specialty = {}
            for d in doctors:
                spec = d.specialty or "General"
                doc_by_specialty.setdefault(spec, []).append(d)

            for spec, patients_list in _specialty_patients.items():
                spec_docs = doc_by_specialty.get(spec, [])
                if not spec_docs:
                    continue
                for pid, pname in patients_list:
                    doc = _rnd.choice(spec_docs)
                    # 2-4 appointments per patient-specialty pair
                    n_appts = _rnd.randint(2, 4)
                    for i in range(n_appts):
                        # Mix of past and future appointments
                        day_offset = _rnd.randint(-60, 30)
                        appt_date = (_now + timedelta(days=day_offset)).date()
                        hour = _rnd.choice([9, 10, 11, 12, 14, 15, 16])
                        minute = _rnd.choice([0, 15, 30, 45])
                        _appts.append(Appointment(
                            doctor_id=doc.id,
                            patient_id=pid,
                            patient_name=pname,
                            appointment_date=appt_date,
                            time_slot=time_type(hour, minute),
                        ))

            db.session.add_all(_appts)
            db.session.commit()
            print(f"[DB] Seeded {len(_appts)} appointments.")

        # ── Seed Medication Reminders ────────────────────────────────────────
        if MedicationReminder.query.count() == 0:
            print("[DB] Seeding medication reminders...")
            _now = datetime.now()
            _reminders = []

            _reminder_data = [
                # (patient_id, medication_name, dosage, frequency, times_json, notes)
                (100, "Amlodipine", "5mg", "Once daily", '["08:00"]', "Take in the morning with water"),
                (100, "Metformin", "500mg", "Twice daily", '["08:00","20:00"]', "Take with meals"),
                (100, "Aspirin", "81mg", "Once daily", '["08:00"]', "Take with breakfast"),
                (102, "Warfarin", "5mg", "Once daily", '["18:00"]', "Take at same time daily. INR monitoring required"),
                (102, "Atorvastatin", "40mg", "Once daily", '["21:00"]', "Take at bedtime"),
                (102, "Bisoprolol", "2.5mg", "Once daily", '["08:00"]', "Do not stop abruptly"),
                (102, "Clopidogrel", "75mg", "Once daily", '["08:00"]', "Take with or without food"),
                (104, "Pregabalin", "75mg", "Twice daily", '["08:00","20:00"]', "For nerve pain. May cause drowsiness"),
                (104, "Sertraline", "50mg", "Once daily", '["08:00"]', "Takes 4-6 weeks for full effect"),
                (105, "Hydroxychloroquine", "200mg", "Twice daily", '["08:00","20:00"]', "Take with meals. Annual eye exam required"),
                (105, "Levothyroxine", "75mcg", "Once daily", '["06:30"]', "Take on empty stomach, 30 min before breakfast"),
                (106, "Insulin Glargine", "Basal dose", "Once daily", '["22:00"]', "Same time each night. Do not mix with other insulin"),
                (106, "Insulin Aspart", "Per carbs", "Three times daily", '["07:30","12:30","18:30"]', "Inject immediately before meals"),
                (108, "Tiotropium", "1 puff", "Once daily", '["08:00"]', "HandiHaler. Rinse mouth after use"),
                (110, "Losartan", "50mg", "Once daily", '["08:00"]', "Monitor potassium levels"),
                (117, "Mycophenolate", "500mg", "Twice daily", '["08:00","20:00"]', "Immunosuppressant. Avoid live vaccines"),
                (117, "Hydroxychloroquine", "200mg", "Once daily", '["08:00"]', "SLE maintenance therapy"),
                (117, "Prednisolone", "5mg", "Once daily", '["08:00"]', "Do not stop abruptly. Take with food"),
                (118, "Levodopa/Carbidopa", "100/25mg", "Three times daily", '["07:00","13:00","19:00"]', "Time doses carefully. Take 30 min before meals"),
                (121, "Sacubitril/Valsartan", "50mg", "Twice daily", '["08:00","20:00"]', "Heart failure therapy. Monitor BP"),
                (121, "Dapagliflozin", "10mg", "Once daily", '["08:00"]', "Stay hydrated. Watch for UTI signs"),
                (121, "Furosemide", "40mg", "Once daily", '["08:00"]', "Take in morning. Weigh daily"),
                (121, "Apixaban", "5mg", "Twice daily", '["08:00","20:00"]', "Anticoagulant. Report any unusual bleeding"),
                (123, "Levothyroxine", "100mcg", "Once daily", '["06:30"]', "Empty stomach. 4h before calcium/iron"),
                (123, "Fluoxetine", "20mg", "Once daily", '["08:00"]', "May take weeks for full benefit"),
                (124, "Donepezil", "10mg", "Once daily", '["21:00"]', "For Alzheimer's. Take at bedtime"),
                (124, "Memantine", "10mg", "Once daily", '["08:00"]', "Can be combined with donepezil"),
                (125, "Carbimazole", "15mg", "Once daily", '["08:00"]', "If sore throat or fever, stop and check blood count immediately"),
                (125, "Propranolol", "40mg", "Twice daily", '["08:00","20:00"]', "For palpitations. Do not stop abruptly"),
                (126, "Metformin", "1000mg", "Twice daily", '["08:00","20:00"]', "Take with meals. Hold before contrast dye"),
                (126, "Rosuvastatin", "20mg", "Once daily", '["21:00"]', "Check CK if muscle pain"),
                (126, "Aspirin", "81mg", "Once daily", '["08:00"]', "Cardiovascular protection"),
            ]

            for pid, med, dose, freq, times_j, note in _reminder_data:
                _reminders.append(MedicationReminder(
                    patient_id=pid, medication_name=med,
                    dosage=dose, frequency=freq,
                    times=times_j, active=True,
                    start_date=(_now - timedelta(days=90)).date(),
                    notes=note,
                ))

            db.session.add_all(_reminders)
            db.session.commit()
            print(f"[DB] Seeded {len(_reminders)} medication reminders.")

        # ── Seed Patient Memory (Conversation History) ───────────────────────
        if PatientMemory.query.count() < 5:
            print("[DB] Seeding patient conversation memory...")
            _now = datetime.now()
            _memories = []

            _memory_data = [
                (100, 5, "Ahmed is a 52-year-old male managing hypertension and Type 2 diabetes. He frequently asks about his blood pressure readings and glucose levels. Prefers Arabic language. Concerned about medication side effects.",
                 '{"chronic_conditions": ["hypertension", "type 2 diabetes"], "concerns": ["medication side effects", "diet for diabetes"], "preferences": {"language": "ar", "communication": "simple explanations"}, "last_topics": ["blood pressure", "HbA1c results"]}'),
                (101, 3, "Sara is a 34-year-old asthmatic who visits during seasonal flares. She is knowledgeable about her condition and asks specific questions about triggers and medication adjustments.",
                 '{"chronic_conditions": ["asthma", "allergic rhinitis"], "concerns": ["trigger avoidance", "inhaler technique"], "preferences": {"language": "en"}, "last_topics": ["peak flow readings", "allergy season"]}'),
                (102, 8, "Mohamed is a 67-year-old cardiac patient on warfarin. Very compliant with monitoring. His daughter Hoda often accompanies him. He asks about INR results and dietary restrictions (vitamin K foods).",
                 '{"chronic_conditions": ["CAD", "atrial fibrillation", "hyperlipidemia"], "concerns": ["INR levels", "vitamin K diet", "fall prevention"], "preferences": {"language": "ar", "communication": "detailed explanations"}, "last_topics": ["INR results", "warfarin dose"]}'),
                (104, 4, "Omar has chronic back pain and depression. He is frustrated with his slow recovery. Responds well to encouragement. Interested in non-pharmacological pain management options.",
                 '{"chronic_conditions": ["disc herniation L4-L5", "depression"], "concerns": ["pain management", "return to work", "sleep quality"], "preferences": {"language": "en"}, "last_topics": ["physiotherapy progress", "sertraline adjustment"]}'),
                (106, 6, "Karim is a 19-year-old Type 1 diabetic university student. Tech-savvy, uses insulin pump and CGM. Asks about carb counting and managing diabetes at university.",
                 '{"chronic_conditions": ["type 1 diabetes", "celiac disease"], "concerns": ["carb counting", "hypo prevention", "gluten-free options"], "preferences": {"language": "en", "communication": "quick and direct"}, "last_topics": ["CGM readings", "exam stress and glucose"]}'),
                (108, 7, "Youssef is a 72-year-old COPD patient. Hard of hearing — needs clear, loud communication. Former smoker. His son Adel helps with appointments. Concerned about his breathing getting worse.",
                 '{"chronic_conditions": ["COPD", "BPH", "hearing loss"], "concerns": ["breathing worsening", "oxygen needs", "urinary symptoms"], "preferences": {"language": "ar", "communication": "slow and clear, hearing impaired"}, "last_topics": ["inhaler technique", "pulmonary rehab"]}'),
                (121, 10, "Mona is a 70-year-old with heart failure and multiple comorbidities. Her son Sayed helps manage her care. She frequently asks about fluid and salt intake. Daily weight monitoring discussions.",
                 '{"chronic_conditions": ["HFrEF", "atrial fibrillation", "type 2 diabetes"], "concerns": ["fluid intake", "weight monitoring", "medication timing"], "preferences": {"language": "ar"}, "last_topics": ["weight gain", "furosemide dose", "blood sugar"]}'),
                (118, 4, "Sherif has Parkinson's disease. His tremor affects his ability to use the tablet. Needs patient interaction style. His son Walid assists with technology.",
                 '{"chronic_conditions": ["Parkinsons disease", "cognitive impairment", "orthostatic hypotension"], "concerns": ["falls", "medication timing", "tremor management"], "preferences": {"language": "ar", "communication": "patient and slow"}, "last_topics": ["levodopa timing", "fall prevention"]}'),
                (124, 6, "Samy has moderate Alzheimer's. Interactions are limited — he may not remember previous conversations. Caregiver (son Lotfy) often present. Focus on simple reassurance.",
                 '{"chronic_conditions": ["Alzheimers disease", "prostate cancer", "cataracts"], "concerns": ["cognitive decline", "caregiver support", "safety at home"], "preferences": {"language": "ar", "communication": "very simple, reassuring"}, "last_topics": ["medication taken today", "caregiver questions"]}'),
                (127, 3, "Iman has fibromyalgia and chronic fatigue. Pain levels fluctuate daily. She appreciates empathetic responses. Interested in multidisciplinary pain management approaches.",
                 '{"chronic_conditions": ["fibromyalgia", "chronic fatigue", "TMJ disorder"], "concerns": ["pain control", "sleep improvement", "cognitive function"], "preferences": {"language": "en", "communication": "empathetic and supportive"}, "last_topics": ["pain diary", "duloxetine dose"]}'),
            ]

            for pid, sessions, summary, facts in _memory_data:
                if not PatientMemory.query.filter_by(patient_id=pid).first():
                    _memories.append(PatientMemory(
                        patient_id=pid, session_count=sessions,
                        summary=summary, key_facts=facts,
                        updated_at=_now - timedelta(days=2),
                    ))

            if _memories:
                db.session.add_all(_memories)
                db.session.commit()
                print(f"[DB] Seeded {len(_memories)} patient memory records.")

# ===============================
# AI TOOLS & HELPERS
# ===============================
def get_patient_context(user_id):
    """Look up the logged-in patient's medical profile for chatbot/triage context."""
    if not user_id:
        return ""
    try:
        patient = Patient.query.get(user_id)
        if not patient:
            return ""
        parts = []
        parts.append(f"Patient: {patient.name} (ID {patient.id})")
        if patient.age:       parts.append(f"Age: {patient.age}")
        if patient.gender:    parts.append(f"Gender: {patient.gender}")
        if patient.blood_type:parts.append(f"Blood Type: {patient.blood_type}")
        if patient.medical_history: parts.append(f"Medical History: {patient.medical_history}")
        if patient.allergies: parts.append(f"Allergies: {patient.allergies}")
        if patient.current_medications: parts.append(f"Current Medications: {patient.current_medications}")
        if patient.notes:     parts.append(f"Clinical Notes: {patient.notes}")
        return "\n".join(parts)
    except Exception:
        return ""


CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
CLAUDE_MODEL   = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

# ---- OFFLINE MODE (Ollama) ----
OFFLINE_MODE    = os.environ.get("OFFLINE_MODE", "0") == "1"

# ---- VOICE CONVERSATION STORE ----
# Voice POSTs come from MainVoice.py (a subprocess) without Flask session
# cookies, so session['voice_history'] is always empty for voice calls.
# We keep history in a module-level dict keyed by patient_id so it persists
# across requests for the same patient within a server lifetime.
_voice_conv_store: dict = {}   # {(patient_id_or_'guest'):lang -> [history_turns]}
_VOICE_HISTORY_MAX = 10        # keep last 10 turns (5 exchanges) per key
# Cap the number of distinct (user, lang) conversation keys retained. Without
# this, the dict grows by one or two entries per patient for the entire server
# lifetime — on a robot left running for weeks across many patients that is an
# unbounded memory leak that eventually causes GC pauses / lag. We keep it
# bounded with simple LRU eviction (oldest-inserted key dropped first).
_VOICE_CONV_MAX_KEYS = 200
OLLAMA_URL      = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

if OFFLINE_MODE:
    print(f"[ENV] OFFLINE MODE enabled. Using Ollama model: {OLLAMA_MODEL}")
    # Warm up the model on startup so first request is fast
    try:
        requests.post(f"{OLLAMA_URL}/api/chat",
                      json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": "hi"}],
                            "stream": False, "options": {"num_predict": 1}}, timeout=30)
        print(f"[ENV] Ollama model {OLLAMA_MODEL} loaded into GPU memory.")
    except Exception as e:
        print(f"[WARN] Could not warm up Ollama: {e}. Make sure Ollama is running.")
else:
    if not CLAUDE_API_KEY:
        print("[WARN] CLAUDE_API_KEY not set! Add it to your .env file.")
    else:
        print(f"[ENV] Claude API key loaded. Model: {CLAUDE_MODEL}")

def call_claude(system_prompt, messages, max_tokens=256):
    """Low-level Claude API call. Returns reply text or raises."""
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": messages
    }
    response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=30)
    resp_json = response.json()
    if "content" not in resp_json:
        print(f"[CLAUDE ERROR] {resp_json}")
        error_msg = resp_json.get("error", {}).get("message", "Unknown error")
        raise RuntimeError(error_msg)
    return resp_json["content"][0]["text"]


def call_ollama(system_prompt, messages, max_tokens=256, tools=None, num_ctx=4096):
    """Low-level Ollama API call with native tool calling support."""
    ollama_messages = [{"role": "system", "content": system_prompt}]
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, list):
            # Convert Claude-style tool_result blocks to plain text
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    parts.append(block.get("content", ""))
                elif isinstance(block, str):
                    parts.append(block)
            content = "\n".join(parts) if parts else str(content)
        ollama_messages.append({"role": m["role"], "content": content})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": ollama_messages,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.3,
            "top_p": 0.9,
            "num_gpu": 99,      # offload all layers to GPU; Ollama caps at actual layer count
            "num_thread": 4,    # CPU threads for the layers that don't fit (usually none)
            "num_ctx": num_ctx,  # KV-cache window; smaller = faster prefill for short turns
        }
    }
    if tools:
        payload["tools"] = tools

    response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=60)
    resp_json = response.json()
    msg = resp_json.get("message", {})
    text = msg.get("content", "")
    tool_calls = msg.get("tool_calls", None)

    if tool_calls:
        return {"text": text, "tool_calls": tool_calls}

    if not text and not tool_calls:
        print(f"[OLLAMA ERROR] {resp_json}")
        raise RuntimeError("Empty response from Ollama")
    return text


def call_llm(system_prompt, messages, max_tokens=256):
    """Unified LLM call — routes to Ollama (offline) or Claude (online)."""
    if OFFLINE_MODE:
        return call_ollama(system_prompt, messages, max_tokens)
    return call_claude(system_prompt, messages, max_tokens)


def interact_with_gemini(user_text, history_list, user_name, lang="en", patient_context=""):
    """Main AI helper — powered by Claude Haiku (online) or Ollama (offline)."""
    greeting = f"The user is {user_name}." if user_name else "Guest user."

    # ---- FAISS RAG: retrieve relevant hospital knowledge ----
    rag_context = ""
    if rag_engine and rag_engine.is_ready():
        rag_context = rag_engine.retrieve_context_string(user_text, lang=lang, k=3)

    # Language-aware System Prompt with RAG grounding + Patient profile
    if lang == "ar":
        base = (
            f"أنت بيبر، روبوت طبي مساعد ودود في مستشفى أندلسية. {greeting}\n"
            "القواعد:\n"
            "- أجب بالعربية فقط باختصار (أقل من 40 كلمة)\n"
            "- كن دقيقاً ومفيداً وودوداً\n"
            "- لا تستخدم علامات Markdown أو نجوم\n"
            "- لا تذكر أسماء الدوال أو الأدوات الداخلية أبداً — فقط أجب بشكل طبيعي\n"
            "- إذا سُئلت عن شيء لا تعرفه، قل ذلك بصراحة"
        )
        if patient_context:
            base += "\n\nالملف الطبي للمريض (استخدمه لتخصيص إجابتك، وتنبيه بشأن الحساسية والتفاعلات الدوائية):\n" + patient_context
        if rag_context:
            system_prompt = base + "\n\nمعلومات مرجعية من قاعدة بيانات المستشفى (استخدمها في إجابتك):\n" + rag_context
        else:
            system_prompt = base
    else:
        base = (
            f"You are Pepper, a friendly medical robot assistant at Andalusia Hospital. {greeting}\n"
            "Rules:\n"
            "- Keep answers short (under 40 words)\n"
            "- Be accurate, helpful, and warm\n"
            "- Do NOT use markdown, asterisks, or bullet points\n"
            "- Write plain, natural sentences as if speaking aloud\n"
            "- NEVER mention function names, tool names, or describe internal actions — just respond naturally with the result\n"
            "- If you do not know something, say so honestly"
        )
        if patient_context:
            base += "\n\nPatient medical profile (use to personalize answers, flag allergy risks, and warn about drug interactions):\n" + patient_context
        if rag_context:
            system_prompt = base + "\n\nRelevant hospital knowledge (use this to ground your answer):\n" + rag_context
        else:
            system_prompt = base

    # Convert Gemini-style history [{role, parts:[{text}]}] to Claude format [{role, content}]
    claude_messages = []
    for msg in history_list:
        role = msg.get("role", "user")
        if role == "model":
            role = "assistant"
        text = ""
        if msg.get("parts"):
            text = msg["parts"][0].get("text", "")
        elif msg.get("content"):
            text = msg["content"]
        if text:
            claude_messages.append({"role": role, "content": text})
    claude_messages.append({"role": "user", "content": user_text})

    try:
        reply = call_llm(system_prompt, claude_messages)
        return _clean_llm_output(reply, lang=lang) if OFFLINE_MODE else reply
    except Exception as e:
        print(f"[LLM] interact error: {e}")
        return "I'm having trouble connecting to my brain."

# ===============================
# *** RAG API ROUTES ***
# ===============================
@app.route("/api/rag_status", methods=["GET"])
def api_rag_status():
    """Health check for the FAISS RAG engine."""
    return jsonify(rag_engine.status() if rag_engine else {"ready": False})

@app.route("/api/rag_query", methods=["POST"])
def api_rag_query():
    """Direct RAG retrieval endpoint (for debugging / staff dashboard)."""
    data = request.get_json(force=True) or {}
    query = data.get("query", "")
    lang  = data.get("lang", "en")
    k     = min(int(data.get("k", 3)), 10)
    if not query:
        return jsonify({"error": "No query provided"}), 400
    if not rag_engine or not rag_engine.is_ready():
        return jsonify({"error": "RAG engine not ready"}), 503
    results = rag_engine.retrieve(query, lang=lang, k=k)
    return jsonify({"query": query, "results": results})

@app.route("/api/rag_rebuild", methods=["POST"])
def api_rag_rebuild():
    """Force rebuild of the FAISS index from corpus (staff only)."""
    if not rag_engine:
        return jsonify({"error": "RAG engine not initialized"}), 503
    rag_engine.rebuild()
    return jsonify({"success": True, "total_chunks": rag_engine.status()["total_chunks"]})

# ===============================
# *** EMOTION DETECTION API ***
# ===============================
@app.route("/api/emotion_status", methods=["GET"])
def api_emotion_status():
    """Health check for the emotion detector."""
    return jsonify(emotion_detector.status() if emotion_detector else {"ready": False})

@app.route("/api/emotion_detect", methods=["POST"])
def api_emotion_detect():
    """
    Detect emotions from an uploaded image.
    Accepts: multipart/form-data with 'image' file field.
    Returns: {"faces": [...], "count": int}
    """
    if not emotion_detector or not emotion_detector.is_ready():
        return jsonify({"error": "Emotion detector not ready"}), 503

    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    image_file = request.files['image']
    image_bytes = image_file.read()
    if not image_bytes:
        return jsonify({"error": "Empty image"}), 400

    result = emotion_detector.detect_from_bytes(image_bytes)
    return jsonify(result)


# ===============================
# *** API ROUTES ***
# ===============================
@app.route("/")
def root():
    response = make_response(app.send_static_file("index.html"))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

# --- TABLET LIVENESS HEARTBEAT ---
# The loaded UI pings /api/tablet_alive once it has rendered VISIBLE content.
# The startup tablet loader (show_tablet.py) polls /api/tablet_status to confirm
# the page actually painted (vs a white screen) and reloads Pepper if it didn't.
_tablet_last_seen = [0.0]

@app.route("/api/tablet_alive", methods=["GET", "POST"])
def api_tablet_alive():
    _tablet_last_seen[0] = time.time()
    return jsonify({"ok": True})

@app.route("/api/tablet_status", methods=["GET"])
def api_tablet_status():
    age = time.time() - _tablet_last_seen[0]
    # 'alive' = the tablet reported a healthy render within the last 12s.
    return jsonify({"alive": (_tablet_last_seen[0] > 0 and age < 12.0),
                    "age": round(age, 1)})
# --- MISSING ROUTE: MY APPOINTMENTS ---
@app.route("/api/my_appointments", methods=["GET"])
def api_my_appointments():
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not logged in"})

    user_id   = session['user_id']
    user_name = session['user_name']

    # Prefer patient_id FK; fall back to name match for legacy rows
    apps = Appointment.query.filter(
        db.or_(
            Appointment.patient_id == user_id,
            db.and_(
                Appointment.patient_id.is_(None),
                db.func.lower(Appointment.patient_name) == db.func.lower(user_name)
            )
        )
    ).all()

    results = []
    for a in apps:
        doc = Doctor.query.get(a.doctor_id)
        results.append({
            "id":       a.id,
            "doctor":   doc.name if doc else "Unknown",
            "specialty": doc.specialty if doc else "",
            "date":     a.appointment_date.strftime("%Y-%m-%d"),
            "time":     a.time_slot.strftime("%H:%M")
        })

    return jsonify({"success": True, "appointments": results})


@app.route("/api/book_appointment", methods=["POST"])
def api_book_appointment():
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Please sign in to book an appointment."})

    user_id   = session['user_id']
    user_name = session['user_name']

    data        = request.get_json(silent=True) or request.form
    doctor_name = (data.get("doctor_name") or "").strip()
    date_str    = (data.get("date") or "").strip()
    time_str    = (data.get("time_slot") or data.get("time") or "").strip()

    if not doctor_name or not date_str or not time_str:
        return jsonify({"success": False, "error": "doctor_name, date, and time_slot are required."})

    clean_name = _clean_doctor_name(doctor_name)
    if not clean_name:
        return jsonify({"success": False, "error": f"Doctor '{doctor_name}' not found."})
    doctor = Doctor.query.filter(Doctor.name.ilike(f"%{clean_name}%")).first()
    if not doctor:
        return jsonify({"success": False, "error": f"Doctor '{doctor_name}' not found."})

    try:
        from datetime import datetime as _dt
        appt_date = _dt.strptime(date_str, "%Y-%m-%d").date()
        appt_time = _dt.strptime(time_str, "%H:%M").time()
    except ValueError:
        return jsonify({"success": False, "error": "Invalid date or time format. Use YYYY-MM-DD and HH:MM."})

    today    = date_type.today()
    now_time = datetime.now().time()
    if appt_date < today:
        return jsonify({"success": False, "error": f"Cannot book an appointment in the past ({date_str})."})
    if appt_date == today and appt_time <= now_time:
        return jsonify({"success": False, "error": f"Time slot {time_str} has already passed today."})

    # Check doctor schedule if available
    day_of_week = appt_date.weekday()
    slots     = Schedule.query.filter_by(doctor_id=doctor.id, day_of_week=day_of_week).all()
    all_slots = Schedule.query.filter_by(doctor_id=doctor.id).all()
    if all_slots:
        in_schedule = bool(slots) and any(
            s.start_time <= appt_time <= s.end_time for s in slots
        )
        if not in_schedule:
            days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
            avail = ", ".join(
                f"{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][s.day_of_week]} "
                f"{s.start_time.strftime('%H:%M')}-{s.end_time.strftime('%H:%M')}"
                for s in all_slots
            )
            return jsonify({"success": False,
                            "error": f"Dr. {doctor.name} is not available on {days[day_of_week]} "
                                     f"at {time_str}. Available: {avail or 'none listed'}."})

    # Duplicate slot guard
    conflict = Appointment.query.filter_by(
        doctor_id=doctor.id, appointment_date=appt_date, time_slot=appt_time
    ).first()
    if conflict:
        return jsonify({"success": False,
                        "error": f"Dr. {doctor.name} already has an appointment at {time_str} on {date_str}."})

    appt = Appointment(doctor_id=doctor.id, patient_id=user_id,
                       patient_name=user_name,
                       appointment_date=appt_date, time_slot=appt_time)
    db.session.add(appt)
    db.session.commit()
    _slog("appointment_booked", patient_name=user_name, patient_id=user_id,
          success=True, doctor=doctor.name, date=date_str, time=time_str,
          appointment_id=appt.id)
    return jsonify({"success": True, "appointment_id": appt.id,
                    "doctor": doctor.name, "specialty": doctor.specialty,
                    "date": date_str, "time": time_str})


@app.route("/api/appointments/<int:appt_id>", methods=["DELETE"])
def api_cancel_appointment(appt_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    appt = Appointment.query.get(appt_id)
    if not appt:
        return jsonify({"success": False, "error": "Appointment not found"}), 404
    user_id = session['user_id']
    # Ownership check: use patient_id FK if set, else fall back to name
    owns = (appt.patient_id == user_id) if appt.patient_id else \
           (appt.patient_name.lower() == session.get('user_name', '').lower())
    if not owns:
        return jsonify({"success": False, "error": "Not your appointment"}), 403
    db.session.delete(appt)
    db.session.commit()
    return jsonify({"success": True})

# --- 1. AI HEALTH TIPS ENDPOINT ---
@app.route("/api/ai_health_tips", methods=["GET"])
def api_ai_health_tips():
    if 'user_id' not in session or session.get('role') != 'patient':
        return jsonify({
            "success": False, 
            "error": "Please log in as a patient to see personalized tips."
        })

    user_id = session['user_id']
    patient = Patient.query.get(user_id)
    
    if not patient:
        return jsonify({"success": False, "error": "Patient record not found."})

    # Build detailed patient profile for personalized tips
    patient_ctx = get_patient_context(user_id)

    # AI Prompt
    prompt = f"""
    Generate 4 short, personalized health tips for a patient named {patient.name}.
    {('Patient profile: ' + patient_ctx) if patient_ctx else ''}
    Consider any allergies, current medications, and medical history when generating tips.
    If the patient has drug interactions or allergy risks, include a relevant safety tip.
    Return ONLY a valid JSON array. Format:
    [{{"icon": "🍎", "title": "Tip Title", "text": "Short advice."}}]
    """

    try:
        raw_response = interact_with_gemini(prompt, [], patient.name, patient_context=patient_ctx)
        
        # --- ROBUST JSON CLEANER ---
        # Find the first '[' and last ']' to ignore any extra text Gemini might add
        start = raw_response.find('[')
        end = raw_response.rfind(']')
        
        if start != -1 and end != -1:
            clean_json = raw_response[start:end+1]
            tips_data = json.loads(clean_json)
        else:
            # Fallback if no array found
            raise ValueError("No JSON array found in AI response")
        
        return jsonify({"success": True, "tips": tips_data, "patient_name": patient.name})
        
    except Exception as e:
        print(f"AI Tips Error: {e}")
        fallback_tips = [
            {"icon": "🩺", "title": "General Advice", "text": "Consult your doctor regularly."},
            {"icon": "💧", "title": "Stay Hydrated", "text": "Drink plenty of water."}
        ]
        return jsonify({"success": True, "tips": fallback_tips, "patient_name": patient.name})

# --- Voice trigger: tablet taps this HTTP endpoint to drop the flag file ---
# Using HTTP instead of WebSocket avoids connection-state timing issues on Pepper's old browser.
@app.route("/api/start_voice", methods=["POST"])
def start_voice():
    data    = request.get_json(silent=True) or {}
    lang    = data.get("lang", "en")
    user_id = str(data.get("user_id", "") or "")
    tap_id  = str(data.get("tap_id", "") or "")

    voice_dir = os.path.realpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "..", "..", "pepper_voice")
    )

    try:
        with open(os.path.join(voice_dir, "lang.flag"), "w") as f:
            f.write(lang)
    except Exception:
        pass
    try:
        with open(os.path.join(voice_dir, "user.flag"), "w") as f:
            f.write(user_id)
    except Exception:
        pass
    # A new start_voice supersedes any pending stop request from a prior turn.
    try:
        _stop = os.path.join(voice_dir, "voice_stop.flag")
        if os.path.exists(_stop):
            os.remove(_stop)
    except Exception:
        pass
    # Pre-emptively mark state as 'starting' (NOT 'recording') so the tablet's
    # status poll doesn't see a stale 'idle' from the previous turn, while also
    # not claiming the mic is live yet — MainVoice.py flips it to 'recording'
    # only once startMicrophonesRecording has actually run. This is what keeps
    # the tablet UI in lockstep with the robot instead of jumping ahead.
    try:
        with open(os.path.join(voice_dir, "voice_state.flag"), "w") as f:
            f.write("starting")
    except Exception:
        pass
    try:
        with open(os.path.join(voice_dir, "voice_start.flag"), "w") as f:
            # Write the tap id so MainVoice ignores the duplicate write from the
            # parallel WebSocket start path (same tap → no phantom extra turn).
            f.write(tap_id or "1")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# --- Voice state poll: tablet calls this every couple of seconds while it
# thinks the mic is busy, so it can recover if the WS 'result' broadcast
# was missed. Returns whatever MainVoice.py wrote to voice_state.flag. ---
@app.route("/api/voice_status", methods=["GET"])
def voice_status():
    voice_dir = os.path.realpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "..", "..", "pepper_voice")
    )
    state_path = os.path.join(voice_dir, "voice_state.flag")
    state = "unknown"
    try:
        if os.path.exists(state_path):
            with open(state_path, "r") as _sf:
                raw = _sf.read().strip()
                if raw in ("idle", "starting", "recording", "processing", "speaking"):
                    state = raw
    except Exception:
        pass
    # Also hand back the last transcript + reply so the tablet can render the
    # text even when the WS 'result' broadcast was dropped. This keeps the
    # on-screen text in lockstep with what Pepper is speaking — one never
    # happens without the other. MainVoice clears this file at the start of
    # each turn, so it can only carry the CURRENT turn's text.
    user_text, ai_text, result_ts = "", "", 0
    try:
        result_path = os.path.join(voice_dir, "voice_result.json")
        if os.path.exists(result_path):
            with open(result_path, "r") as _rf:
                res = json.load(_rf) or {}
            user_text = res.get("user_text", "") or ""
            ai_text   = res.get("ai_text", "") or ""
            result_ts = res.get("ts", 0) or 0
    except Exception:
        pass
    return jsonify({"state": state, "user_text": user_text,
                    "ai_text": ai_text, "result_ts": result_ts})


# --- Voice early-stop trigger: tablet taps this to end the current recording. ---
@app.route("/api/stop_voice", methods=["POST"])
def stop_voice():
    """Drop a 'voice_stop.flag' file; MainVoice.py polls for it during
    recording and stops as soon as it appears (after a 1s minimum)."""
    voice_dir = os.path.realpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "..", "..", "pepper_voice")
    )
    try:
        with open(os.path.join(voice_dir, "voice_stop.flag"), "w") as f:
            f.write("1")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# --- 2. VOICE ENDPOINT (full tool use, same as chatbot) ---
@app.route("/api/process_audio", methods=["POST"])
def process_audio():
    if 'file' not in request.files:
        return jsonify({"reply": "No audio received."})
    file    = request.files['file']
    ui_lang = request.form.get("lang", "")
    # Use a unique temp file per request to prevent race conditions
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_filename = tmp.name
    tmp.close()
    file.save(temp_filename)
    try:
        import concurrent.futures as _cf

        # 1a. Whisper transcription (faster-whisper)
        # beam_size=5 gives best accuracy; VAD filter strips silence so the model
        # never hallucinates on quiet segments; condition_on_previous_text=False
        # prevents prior-segment bias from corrupting medical term recognition.
        transcribe_opts = {
            "beam_size": 5,
            "no_speech_threshold": 0.45,
            "vad_filter": True,
            "vad_parameters": {"min_silence_duration_ms": 400},
            "condition_on_previous_text": False,
            # Temperature fallbacks: greedy first, then sample if the decoder
            # gets stuck — critical for dialectal Arabic where the greedy path
            # often produces low-probability loops.
            "temperature": [0.0, 0.2, 0.4, 0.6, 0.8],
            "compression_ratio_threshold": 2.4,
            "log_prob_threshold": -1.0,
        }
        if ui_lang == "ar":
            # Wider beam + Egyptian-dialect bias. Whisper uses initial_prompt
            # as a style primer: seeding it with colloquial Egyptian words
            # (عايز/عاوز, إزاي, فين, ليه, بكرة, ميعاد) makes the decoder
            # prefer dialect spellings over forced-MSA transliteration.
            transcribe_opts["language"] = "ar"
            transcribe_opts["task"] = "transcribe"
            transcribe_opts["beam_size"] = 8
            transcribe_opts["best_of"] = 5
            transcribe_opts["no_speech_threshold"] = 0.35
            # IMPORTANT: do NOT include a full example sentence with a specific
            # symptom ("عندي وجع في بطني من إمبارح") in the initial prompt —
            # Whisper uses initial_prompt as a strong style anchor, and a
            # specific example causes the decoder to bias every utterance
            # toward that template ("الباطنة" → "بطني", routing everything to
            # stomach pain). Keep the prompt vocabulary-only: a flat word list
            # primes the dialect without contaminating content.
            transcribe_opts["initial_prompt"] = (
                "محادثة باللهجة المصرية مع روبوت استقبال في مستشفى أندلسية. "
                "كلمات شائعة: عايز، عاوز، محتاج، ممكن، لو سمحت، إزيك، إزاي، "
                "فين، امتى، ليه، بكرة، النهارده، إمبارح، دلوقتي، يعني، عشان، "
                "الدكتور، دكتورة، ميعاد، حجز، كشف، عيادة، صيدلية، دوا، علاج، "
                "الباطنة، الجراحة، الأطفال، النساء، التوليد، الجلدية، الأسنان، "
                "العيون، الأنف، الأذن، القلب، العظام، الأعصاب، الكلى، الصدر، "
                "وجع، ألم، صداع، حرارة، سخونية، برد، كحة، ضغط، سكر."
            )
        elif ui_lang == "en":
            transcribe_opts["language"] = "en"
            transcribe_opts["task"] = "transcribe"
            transcribe_opts["initial_prompt"] = (
                "Patient speaking to Pepper, a hospital reception robot at Andalusia Hospital. "
                "Common medical terms: appointment, doctor, prescription, blood pressure, medication, symptoms."
            )

        # 1b. Acoustic biomarker analysis runs in parallel with Whisper
        def _transcribe_eager(model, path, **opts):
            segs, info = model.transcribe(path, **opts)
            return list(segs), info          # consume lazy generator in pool thread

        with _cf.ThreadPoolExecutor(max_workers=2) as pool:
            whisper_future  = pool.submit(
                _transcribe_eager, audio_model, temp_filename, **transcribe_opts
            )
            acoustic_future = pool.submit(
                acoustic_analyzer.analyze, temp_filename
            )
            segments, info = whisper_future.result()
            try:
                acoustic_result = acoustic_future.result()
            except Exception as ae:
                print(f"[ACOUSTIC] Analysis failed: {ae}")
                acoustic_result = {"error": str(ae)}

        user_text = " ".join(seg.text for seg in segments).strip()
        detected_lang = info.language if info else "en"

        # Whisper fallback: if the forced-language transcription is empty
        # (which happens when the user has toggled language but spoken in
        # the other language — Arabic prompt + English speech yields silence,
        # and vice versa), retry without forcing the language. This costs
        # an extra ~1-2s but rescues the turn instead of returning "I did
        # not hear anything." when the user actually spoke.
        if not user_text and ui_lang in ("ar", "en"):
            print("[VOICE] Forced-lang ({}) transcription empty — "
                  "retrying with auto-detect".format(ui_lang))
            try:
                fallback_opts = dict(transcribe_opts)
                fallback_opts.pop("language", None)
                fallback_opts.pop("initial_prompt", None)
                fallback_opts.pop("task", None)
                segs2, info2 = audio_model.transcribe(temp_filename, **fallback_opts)
                segs2_list = list(segs2)
                user_text_fb = " ".join(seg.text for seg in segs2_list).strip()
                if user_text_fb:
                    user_text = user_text_fb
                    detected_lang = info2.language if info2 else detected_lang
                    print("[VOICE] Auto-detect rescued: lang={} text={!r}".format(
                        detected_lang, user_text[:80]))
            except Exception as _e:
                print("[VOICE] Auto-detect fallback failed: {}".format(_e))

        # Trust the actual detected language when it strongly disagrees with
        # the UI toggle — the patient's spoken language is the ground truth.
        # This makes the pipeline robust to the user forgetting to toggle.
        if detected_lang in ("ar", "en") and detected_lang != ui_lang:
            print("[VOICE] UI lang={} but Whisper detected {} — using detected".format(
                ui_lang, detected_lang))
            lang = detected_lang
        else:
            lang = ui_lang if ui_lang in ("ar", "en") else ("ar" if detected_lang == "ar" else "en")
        print(f"[VOICE] User said ({lang}): {user_text}")

        # Short-circuit empty transcription BEFORE calling the LLM. Claude
        # rejects empty user messages with "user messages must have
        # non-empty content" — we don't need to round-trip to find that out.
        if not user_text:
            polite = (u"لم أسمعك جيداً. هل يمكنك إعادة ما قلته؟"
                      if lang == "ar"
                      else "I did not hear anything. Please try again.")
            print("[VOICE] Empty transcription — returning polite retry message without LLM call.")
            return jsonify({
                "text":  "",
                "reply": polite,
                "lang":  lang,
                "acoustic_analysis": {
                    "status": "error" if acoustic_result.get("error") else "ok",
                    "error":  acoustic_result.get("error"),
                    "cough_detected": acoustic_result.get("cough_detected", False),
                    "wheeze_detected": acoustic_result.get("wheeze_detected", False),
                    "breathlessness_score": acoustic_result.get("breathlessness_score", 0.0),
                    "pain_score_estimate":  acoustic_result.get("pain_score_estimate", 0),
                    "distress_score":       acoustic_result.get("distress_score", 0.0),
                    "alerts":               acoustic_result.get("alerts", []),
                },
            })

        # Log acoustic alerts if any were detected
        for alert_msg in acoustic_result.get("alerts", []):
            print(f"[ACOUSTIC ALERT] {alert_msg}")
        if acoustic_result.get("error"):
            print(f"[ACOUSTIC] {acoustic_result['error']}")

        # 2. Resolve identity: voice POSTs come from the PC subprocess (no session
        #    cookie), so the patient_id is forwarded explicitly in the form data
        #    by MainVoice.py (written by nav_bridge from the tablet WS message).
        form_pid  = request.form.get('patient_id', '').strip()
        if form_pid:
            try:
                _p = Patient.query.get(int(form_pid))
            except Exception:
                _p = None
            if _p:
                user_id   = _p.id
                user_name = _p.name
                role      = 'patient'
            else:
                user_id   = None
                user_name = 'Guest'
                role      = ''
        else:
            user_id   = session.get('user_id')
            user_name = session.get('user_name', 'Guest')
            role      = session.get('role', '')

        # 3. Safety pre-check: bypass LLM for life-threatening red flags (same as chatbot)
        emergency_reply, emergency_label = _detect_medical_emergency(user_text, lang=lang)
        if emergency_reply:
            _slog("voice_interaction", patient_name=user_name, patient_id=user_id,
                  success=True, lang=lang,
                  user_said=user_text[:200], ai_replied=emergency_reply[:300],
                  emergency=emergency_label, tools_used=[])
            return jsonify({
                "text":  user_text,
                "reply": emergency_reply,
                "lang":  lang,
                "emergency": emergency_label,
                "acoustic_analysis": {
                    "status": "error" if acoustic_result.get("error") else "ok",
                    "error":  acoustic_result.get("error"),
                    "cough_detected": acoustic_result.get("cough_detected", False),
                    "wheeze_detected": acoustic_result.get("wheeze_detected", False),
                    "breathlessness_score": acoustic_result.get("breathlessness_score", 0.0),
                    "pain_score_estimate":  acoustic_result.get("pain_score_estimate", 0),
                    "distress_score":       acoustic_result.get("distress_score", 0.0),
                    "alerts":               acoustic_result.get("alerts", []),
                },
            })

        # 4. Sentiment analysis (same as chatbot)
        sentiment = sentiment_analyzer.analyze(user_text, lang)
        if sentiment.get("alert"):
            print(f"[VOICE ALERT] Distress detected for {user_name}: {sentiment.get('reason')}")

        # 5. Medical NER (same as chatbot)
        ner_entities = medical_ner.extract(user_text)

        # 6. Conversation memory (same as chatbot)
        mem = ConversationMemory(db, PatientMemory)
        memory_ctx = mem.get_context(user_id) if user_id else ""

        # 7. Multi-agent consensus for high-stakes messages (same as chatbot)
        consensus = None
        if multi_agent_system.should_activate(user_text):
            try:
                patient_meds = []
                if user_id:
                    _pt = Patient.query.get(user_id)
                    if _pt and _pt.current_medications:
                        patient_meds = [m.strip() for m in _pt.current_medications.split(",") if m.strip()]
                dc = DrugChecker(db, Medication, DrugInteraction)
                consensus = multi_agent_system.consult(
                    patient_context=memory_ctx,
                    user_message=user_text,
                    drug_checker=dc,
                    medications=patient_meds,
                )
            except Exception as _e:
                print(f"[MULTI-AGENT VOICE] Error: {_e}")

        # 8. Voice conversation history — use module-level store (NOT Flask session)
        # because MainVoice.py is a subprocess that posts without a session cookie.
        #
        # KEY BY (user_id, lang) — mixing English and Arabic history into the
        # same conversation context confuses the LLM (it picks up cues from
        # the wrong-language exchanges and may reply in the wrong language).
        # Keeping per-language histories means switching language gives a clean
        # context for the new language, while the prior language's history is
        # preserved if the user switches back.
        _hist_key = "{}:{}".format(user_id if user_id else 'guest', lang)
        voice_history = list(_voice_conv_store.get(_hist_key, []))[-_VOICE_HISTORY_MAX:]

        # 9. Run full agentic loop with all features
        ai_reply, tool_results = run_agentic_loop(
            user_text, user_id, user_name, role,
            lang=lang, history=voice_history, voice_mode=True,
            sentiment=sentiment, ner_entities=ner_entities, memory_ctx=memory_ctx
        )

        # 10. Guard against fabricated booking/cancel confirmations (same as chatbot)
        ai_reply = _strip_fake_booking_claim(ai_reply, tool_results, lang=lang)
        ai_reply = _strip_fake_cancel_claim(ai_reply, tool_results, lang=lang)

        # 11. Multi-agent override when no side-effecting tools were used (same as chatbot)
        if consensus and consensus.get("final_recommendation") and not tool_results:
            ai_reply = consensus["final_recommendation"]

        # 11b. VOICE LENGTH CAP — server-side enforcement of the prompt's
        # "1-2 short sentences" rule. Claude sometimes ignores it (especially
        # for medical-history questions) and produces 3+ sentences, which on
        # NAOqi Arabic TTS can run 25+ seconds. That long TTS spike starves
        # the tablet renderer, freezes the FSM poller, and the UI looks
        # broken. Hard cap: first 2 sentences, or first 160 characters,
        # whichever is shorter. Arabic uses ؟ / . / ! / ، as terminators.
        def _voice_cap(text):
            if not text:
                return text
            # Find sentence boundaries (both Latin and Arabic punctuation)
            import re as _re
            sentences = _re.split(r'(?<=[\.!\?؟])\s+', text.strip())
            capped = ' '.join(sentences[:2]).strip()
            if len(capped) > 160:
                capped = capped[:157].rstrip() + '...'
            return capped
        ai_reply = _voice_cap(ai_reply)

        # 12. Persist voice history in module-level store (survives across requests)
        voice_history.append({"role": "user", "parts": [{"text": user_text}]})
        voice_history.append({"role": "model", "parts": [{"text": ai_reply}]})
        # pop-then-set makes this key the most-recently-used (moves it to the end
        # of the dict's insertion order) so LRU eviction below drops genuinely
        # stale keys, not the active conversation.
        _voice_conv_store.pop(_hist_key, None)
        _voice_conv_store[_hist_key] = voice_history[-_VOICE_HISTORY_MAX:]
        # LRU eviction: drop oldest keys once we exceed the cap so the store
        # never grows without bound over a long-running server.
        while len(_voice_conv_store) > _VOICE_CONV_MAX_KEYS:
            try:
                _oldest = next(iter(_voice_conv_store))
                del _voice_conv_store[_oldest]
            except (StopIteration, KeyError):
                break

        print(f"[VOICE] Reply: {ai_reply}")
        _slog("voice_interaction", patient_name=user_name, patient_id=user_id,
              success=True, lang=lang,
              user_said=user_text[:200],
              ai_replied=ai_reply[:300],
              sentiment=sentiment.get("label", "neutral") if sentiment else "neutral",
              tools_used=[r.get("tool") for r in tool_results if isinstance(r, dict) and r.get("tool")])
        return jsonify({
            "text":             user_text,
            "reply":            ai_reply,
            "lang":             lang,
            "acoustic_analysis": {
                "status":               "error" if acoustic_result.get("error") else "ok",
                "error":                acoustic_result.get("error"),
                "cough_detected":       acoustic_result.get("cough_detected", False),
                "wheeze_detected":      acoustic_result.get("wheeze_detected", False),
                "breathlessness_score": acoustic_result.get("breathlessness_score", 0.0),
                "pain_score_estimate":  acoustic_result.get("pain_score_estimate", 0),
                "distress_score":       acoustic_result.get("distress_score", 0.0),
                "alerts":               acoustic_result.get("alerts", []),
            },
        })

    except Exception as e:
        print(f"[VOICE ERROR] {e}")
        _slog("voice_interaction", success=False, error=str(e))
        return jsonify({"reply": "I could not understand. Please try again."})
    finally:
        try:
            os.unlink(temp_filename)
        except OSError:
            pass

# --- 3. LOGIN / AUTH ---
@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    role = data.get("role")
    user_id = data.get("id")
    password = data.get("password")

    if not user_id or not password or role not in ('patient', 'staff'):
        return jsonify({"success": False, "error": "Invalid input"}), 400

    user = None
    if role == 'staff': user = Staff.query.filter_by(id=user_id).first()
    elif role == 'patient': user = Patient.query.filter_by(id=user_id).first()
    
    if user and check_password_hash(user.password, password):
        session['user_id'] = user.id
        session['user_name'] = user.name
        session['role'] = role
        _slog("patient_login", patient_name=user.name, patient_id=user.id,
              success=True, role=role)
        resp = {"success": True, "name": user.name}
        if role == 'patient':
            resp["case_number"] = getattr(user, 'case_number', None) or ('CASE-' + str(user.id))
        return jsonify(resp)

    _slog("patient_login", success=False, role=role,
          attempted_id=user_id, error="Invalid credentials")
    return jsonify({"success": False, "error": "Invalid Credentials"})

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/me", methods=["GET"])
def api_me():
    if 'user_id' in session:
        return jsonify({"loggedIn": True, "name": session.get('user_name', ''),
                        "role": session.get('role', '')})
    return jsonify({"loggedIn": False})

# ===============================================================
# CHAT TOOL DEFINITIONS (Claude tool use)
# ===============================================================
CHAT_TOOLS = [
    {
        "name": "get_departments",
        "description": "Get all available medical departments in the hospital.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_doctors",
        "description": "Get doctors, optionally filtered by department/specialty.",
        "input_schema": {
            "type": "object",
            "properties": {
                "department": {"type": "string", "description": "Department name to filter by (optional)"}
            },
            "required": []
        }
    },
    {
        "name": "get_doctor_schedule",
        "description": "Get the weekly schedule and available time slots for a specific doctor.",
        "input_schema": {
            "type": "object",
            "properties": {
                "doctor_name": {"type": "string", "description": "Full or partial doctor name"}
            },
            "required": ["doctor_name"]
        }
    },
    {
        "name": "book_appointment",
        "description": "Book an appointment for the current patient with a doctor on a specific date and time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "doctor_name": {"type": "string", "description": "Doctor's full name"},
                "date":        {"type": "string", "description": "Appointment date in YYYY-MM-DD format"},
                "time_slot":   {"type": "string", "description": "Time slot in HH:MM format (24h)"}
            },
            "required": ["doctor_name", "date", "time_slot"]
        }
    },
    {
        "name": "get_my_appointments",
        "description": "Get all upcoming appointments for the current logged-in patient.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "cancel_appointment",
        "description": "Cancel an appointment by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "integer", "description": "The ID of the appointment to cancel"}
            },
            "required": ["appointment_id"]
        }
    },
    {
        "name": "get_patient_profile",
        "description": "Get the current patient's medical profile including history, allergies, and medications.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_navigation_targets",
        "description": (
            "Get the list of named rooms, departments, and doctor offices that Pepper "
            "can physically guide a patient to. Call this WHENEVER the user asks about "
            "navigation, guidance, hospital layout, room locations, 'where can you take "
            "me', 'where can you guide me', 'how do I get to X', or similar. Never answer "
            "these questions from memory — always call this tool first for real data."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []}
    }
]


# Common Arabic name transliteration aliases — maps phonetic variants to a
# canonical token so fuzzy matching isn't tripped by LLM transliteration drift
# (e.g. user says "Amany Yahya" but qwen writes "Amany Yehia").
_ARABIC_PHONETIC_ALIASES = {
    "yehia": "yahya", "yahia": "yahya", "yehya": "yahya", "yihia": "yahya",
    "mohamad": "mohamed", "muhammad": "mohamed", "mohammed": "mohamed", "mohamd": "mohamed",
    "aly": "ali",
    "elshami": "elshamy", "el-shamy": "elshamy",
    "fuad": "fouad",
    "samy": "sami",
    "zeyad": "ziad",
    "abdulla": "abdallah", "abdullah": "abdallah",
    "abdelrahman": "abdelrahman", "abdulrahman": "abdelrahman",
}

def _phonetic_normalize(name: str) -> str:
    """Map each token through the phonetic alias table and return the result."""
    return " ".join(_ARABIC_PHONETIC_ALIASES.get(t, t) for t in name.lower().split())


def _find_doctor_fuzzy(cleaned_name):
    """Find a Doctor row by name with graceful fuzzy fallback.

    Order:
      1. Substring ILIKE match (original behaviour).
      2. Phonetic-normalised ILIKE match — catches 'Amany Yehia' → 'Amany Yahya'.
      3. Token-overlap + difflib similarity ≥ 0.68, comparing both sides with
         honorifics stripped and phonetic normalization applied.

    Returns the Doctor row or None.
    """
    import difflib, re
    if not cleaned_name:
        return None

    # Pass 1: exact substring match
    doctor = Doctor.query.filter(Doctor.name.ilike(f"%{cleaned_name}%")).first()
    if doctor:
        return doctor

    # Pass 2: phonetic-normalised ILIKE — cheap, handles the common case
    norm = _phonetic_normalize(cleaned_name)
    if norm != cleaned_name.lower():
        norm_title = " ".join(t.capitalize() for t in norm.split())
        doctor = Doctor.query.filter(Doctor.name.ilike(f"%{norm_title}%")).first()
        if doctor:
            return doctor

    # Pass 3: fuzzy fallback — strip honorifics from DB names before comparison
    _hon_re = re.compile(r'^(?:Dr\.?\s*|Prof\.?\s*|Doctor\s+|Professor\s+)', re.IGNORECASE)
    target = _phonetic_normalize(cleaned_name)
    target_tokens = [t for t in re.split(r"\s+", target) if len(t) >= 3]
    if not target_tokens:
        return None

    best, best_score = None, 0.0
    for d in Doctor.query.all():
        dname_raw = (d.name or "").lower()
        dname_clean = _hon_re.sub("", dname_raw).strip()
        dname_norm = _phonetic_normalize(dname_clean)
        # Require at least one shared token as a cheap guard
        shared = sum(1 for t in target_tokens if t in dname_norm)
        if shared == 0:
            continue
        score = difflib.SequenceMatcher(None, target, dname_norm).ratio()
        if score > best_score:
            best_score, best = score, d
    return best if best_score >= 0.68 else None


def _clean_doctor_name(name):
    """Strip common prefixes like Dr., Doctor, etc. that models add.
    Returns empty string for names that look like injection payloads
    (SQL, XSS, control chars) so the DB lookup fails cleanly rather
    than fuzzy-matching or letting the LLM hallucinate a real doctor."""
    import re
    name = (name or "").strip()
    name = re.sub(r'^(Dr\.?\s*|Doctor\s+|Prof\.?\s*|Professor\s+)',
                  '', name, flags=re.IGNORECASE).strip()
    if not name or len(name) < 2 or len(name) > 80:
        return ""
    # Reject payloads that clearly aren't human names.
    # Doctor names are letters/spaces/hyphens/apostrophes/dots (+ Arabic).
    bad_markers = ("<", ">", ";", "--", "/*", "*/", "=", "\\", "|",
                   "script", "alert(", "drop ", "select ", " or ", " and 1",
                   "\x00", "\u200b", "\u200c", "\ufeff")
    low = name.lower()
    for m in bad_markers:
        if m in low:
            return ""
    if not re.match(r"^[\w\s\.\-'\u0600-\u06FF]+$", name, flags=re.UNICODE):
        return ""
    return name


def execute_tool(tool_name, tool_input, user_id, user_name, role):
    """Execute a chatbot tool and return result dict."""
    if tool_input is None:
        tool_input = {}
    try:
        if tool_name == "get_departments":
            depts = db.session.query(Doctor.specialty).distinct().all()
            dept_list = sorted([d[0] for d in depts if d[0]])
            return {"departments": dept_list}

        elif tool_name == "get_doctors":
            dept = tool_input.get("department", "").strip()
            if dept:
                # Split comma-separated specialties (qwen sometimes passes multiple
                # as one string e.g. "Endocrinology, Psychiatry, Gastroenterology").
                import random as _rnd
                dept_parts = [d.strip() for d in dept.replace("،", ",").split(",") if d.strip()]
                seen_ids = set()
                doctors = []
                for dp in dept_parts:
                    for doc in Doctor.query.filter(Doctor.specialty.ilike(f"%{dp}%")).all():
                        if doc.id not in seen_ids:
                            seen_ids.add(doc.id)
                            doctors.append(doc)
            else:
                import random as _rnd
                doctors = Doctor.query.all()
            # Shuffle so the LLM doesn't always recommend the first entry —
            # small models (qwen2.5:7b) otherwise fixate on one name.
            doc_list = [{"id": d.id, "name": d.name, "specialty": d.specialty} for d in doctors]
            _rnd.shuffle(doc_list)
            # Pre-built presentation strings in BOTH languages so qwen never
            # joins names itself (concatenation produces "Sameh RadwanNeveen Darwish").
            if doc_list:
                ar_items = "، ".join(f"د. {d['name']} ({d['specialty']})" for d in doc_list)
                en_items = ", ".join(f"Dr. {d['name']} ({d['specialty']})" for d in doc_list)
                presentation_ar = (
                    f"الأطباء المتاحون: {ar_items}. من تفضل؟"
                    if len(doc_list) > 1
                    else f"الطبيب المتاح: د. {doc_list[0]['name']}، تخصص {doc_list[0]['specialty']}."
                )
                presentation_en = (
                    f"Available doctors: {en_items}. Who would you prefer?"
                    if len(doc_list) > 1
                    else f"The available doctor is Dr. {doc_list[0]['name']}, specializing in {doc_list[0]['specialty']}."
                )
            else:
                presentation_ar = "لا يوجد أطباء متاحون في هذا التخصص حالياً."
                presentation_en = "No doctors are currently available for that specialty."
            return {
                "doctors": doc_list,
                "reply_ar": presentation_ar,
                "reply_en": presentation_en,
                "_instructions": (
                    "IMPORTANT: Reply in the SAME language the patient used. "
                    "If Arabic → use 'reply_ar' verbatim as the base of your reply. "
                    "If English → use 'reply_en' verbatim as the base of your reply. "
                    "Do NOT concatenate names yourself. "
                    "When recommending ONE doctor, pick ONE from the list and add a short reason "
                    "why they suit the patient's conditions."
                ),
            }

        elif tool_name == "get_doctor_schedule":
            name = _clean_doctor_name(tool_input.get("doctor_name", ""))
            if not name:
                return {"error": "Invalid or missing doctor name."}
            doctor = _find_doctor_fuzzy(name)
            if not doctor:
                return {"error": f"Doctor '{name}' not found."}
            slots = Schedule.query.filter_by(doctor_id=doctor.id).all()
            days = {0:"Monday",1:"Tuesday",2:"Wednesday",3:"Thursday",4:"Friday",5:"Saturday",6:"Sunday"}
            schedule = [{"day": days.get(s.day_of_week,""), "start": s.start_time.strftime("%H:%M"), "end": s.end_time.strftime("%H:%M")} for s in slots]
            return {"doctor": doctor.name, "specialty": doctor.specialty, "schedule": schedule}

        elif tool_name == "book_appointment":
            if role != 'patient':
                return {"error": "Only logged-in patients can book appointments."}
            doctor_name = _clean_doctor_name(tool_input.get("doctor_name", "") if tool_input else "")
            if not doctor_name:
                return {"error": "Invalid or missing doctor name."}
            date_str    = (tool_input or {}).get("date", "")
            time_str    = (tool_input or {}).get("time_slot", "")
            doctor = _find_doctor_fuzzy(doctor_name)
            if not doctor:
                return {"error": f"Doctor '{doctor_name}' not found."}
            try:
                from datetime import datetime as dt
                appt_date = dt.strptime(date_str, "%Y-%m-%d").date()
                appt_time = dt.strptime(time_str, "%H:%M").time()
            except ValueError:
                return {"error": "Invalid date or time format. Use YYYY-MM-DD and HH:MM."}

            # Past-date/time guard
            from datetime import datetime as _dt_now
            today = date_type.today()
            now_time = _dt_now.now().time()
            if appt_date < today:
                return {"error": f"Cannot book an appointment in the past ({date_str})."}
            if appt_date == today and appt_time <= now_time:
                return {"error": f"The time slot {time_str} has already passed today. Please choose a future time."}

            # Check the requested time falls within the doctor's schedule.
            # Drop any SQLAlchemy session cache first so we see the real row state
            # (prevents phantom "doctor works this day" results from a stale view).
            try:
                db.session.expire_all()
            except Exception:
                pass
            day_of_week = appt_date.weekday()  # 0=Monday … 6=Sunday
            all_slots = Schedule.query.filter_by(doctor_id=doctor.id).all()
            slots_today = [s for s in all_slots if int(s.day_of_week) == int(day_of_week)]
            print(f"[BOOK-CHECK] doctor={doctor.name!r} id={doctor.id} "
                  f"date={date_str} dow={day_of_week} "
                  f"all_dows={[int(s.day_of_week) for s in all_slots]} "
                  f"slots_today={[(s.start_time, s.end_time) for s in slots_today]}")
            if all_slots:
                in_schedule = bool(slots_today) and any(
                    s.start_time <= appt_time <= s.end_time for s in slots_today
                )
                if not in_schedule:
                    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
                    avail = ", ".join(
                        f"{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][int(s.day_of_week)]} "
                        f"{s.start_time.strftime('%H:%M')}-{s.end_time.strftime('%H:%M')}"
                        for s in all_slots
                    )
                    return {"error": f"Dr. {doctor.name} is not available on {days[day_of_week]} at {time_str}. "
                                     f"Available slots: {avail or 'none listed'}."}

            # Duplicate slot guard
            conflict = Appointment.query.filter_by(
                doctor_id=doctor.id,
                appointment_date=appt_date,
                time_slot=appt_time
            ).first()
            if conflict:
                return {"error": f"Dr. {doctor.name} already has an appointment at {time_str} on {date_str}. "
                                 "Please choose a different time."}

            appt = Appointment(doctor_id=doctor.id, patient_id=user_id,
                               patient_name=user_name,
                               appointment_date=appt_date, time_slot=appt_time)
            db.session.add(appt)
            db.session.commit()
            _slog("appointment_booked", patient_name=user_name, patient_id=user_id,
                  success=True, doctor=doctor.name, specialty=doctor.specialty,
                  date=date_str, time=time_str, appointment_id=appt.id)
            return {"success": True, "appointment_id": appt.id,
                    "doctor": doctor.name, "specialty": doctor.specialty,
                    "date": date_str, "time": time_str,
                    "message": f"Appointment booked with {doctor.name} on {date_str} at {time_str}."}

        elif tool_name == "get_my_appointments":
            if role != 'patient':
                return {"error": "Please log in as a patient to see appointments."}
            appts = Appointment.query.filter_by(patient_name=user_name).all()
            result = []
            for a in appts:
                doc = Doctor.query.get(a.doctor_id)
                result.append({"id": a.id, "doctor": doc.name if doc else "Unknown",
                                "specialty": doc.specialty if doc else "",
                                "date": a.appointment_date.strftime("%Y-%m-%d"),
                                "time": a.time_slot.strftime("%H:%M")})
            # Hard-label results with the logged-in patient name so the LLM
            # cannot re-attribute them to a different patient mentioned in the
            # conversation. Also add an explicit instruction.
            return {
                "appointments": result,
                "_for_patient": user_name,
                "_warning": (
                    f"These are the appointments for the logged-in patient "
                    f"'{user_name}' ONLY. Do NOT present them as belonging to any "
                    f"other person the user mentioned. If the user asked about "
                    f"another patient, reply that you can only show your own records."
                ),
            }

        elif tool_name == "cancel_appointment":
            appt_id = tool_input.get("appointment_id")
            appt = Appointment.query.get(appt_id)
            if not appt:
                return {"error": f"Appointment #{appt_id} not found."}
            if appt.patient_name != user_name:
                return {"error": "You can only cancel your own appointments."}
            doc = Doctor.query.get(appt.doctor_id)
            info = {"doctor": doc.name if doc else "Unknown",
                    "date": appt.appointment_date.strftime("%Y-%m-%d"),
                    "time": appt.time_slot.strftime("%H:%M")}
            db.session.delete(appt)
            db.session.commit()
            _slog("appointment_cancelled", patient_name=user_name, patient_id=user_id,
                  success=True, appointment_id=appt_id,
                  doctor=info["doctor"], date=info["date"], time=info["time"])
            return {"success": True, "cancelled": info}

        elif tool_name == "get_patient_profile":
            if role != 'patient' or not user_id:
                return {"error": "No patient profile available."}
            patient = Patient.query.get(user_id)
            if not patient:
                return {"error": "Patient not found."}
            return patient.to_profile()

        elif tool_name == "get_navigation_targets":
            # Return a structured split so the LLM knows which entries are
            # doctor offices vs. hospital facilities (pharmacy, ICU, ER, etc.).
            # Small models previously dumped the full doctor list when asked
            # "where is the pharmacy?" because every target looked the same.
            try:
                with open(str(_NAV_TARGETS_PATH), "r", encoding="utf-8") as f:
                    nav_data = json.load(f)
                all_targets = nav_data.get("targets", [])
                doctor_offices = []
                facilities = []
                for t in all_targets:
                    if t.get("facility"):
                        facilities.append({
                            "name": t.get("name"),
                            "facility_type": t.get("facility"),
                            "location": t.get("room_name", ""),
                        })
                    else:
                        doctor_offices.append({
                            "name": t.get("name"),
                            "specialty": t.get("specialty"),
                            "location": t.get("room_name", ""),
                        })
                return {
                    "doctor_offices": doctor_offices,
                    "facilities": facilities,
                    "_instructions": (
                        "Use 'facilities' to answer questions about pharmacy, "
                        "laboratory, radiology, ICU, emergency, bathroom, "
                        "reception, cafeteria, etc. Use 'doctor_offices' ONLY "
                        "when the patient asks about a specific doctor by "
                        "name. Do NOT list doctors in response to a facility "
                        "question. If the requested facility is NOT in the "
                        "'facilities' list, say you don't know and suggest "
                        "asking at reception."
                    ),
                }
            except Exception:
                return {"doctor_offices": [], "facilities": [],
                        "error": "Navigation targets file not loaded."}

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        print(f"[TOOL ERROR] {tool_name}: {e}")
        return {"error": str(e)}


# ===============================================================
# OFFLINE AGENTIC LOOP (Ollama — native tool calling)
# ===============================================================

# Convert Claude tool schema to Ollama/OpenAI tool format (done once at import)
OLLAMA_TOOLS = []
for _t in CHAT_TOOLS:
    OLLAMA_TOOLS.append({
        "type": "function",
        "function": {
            "name": _t["name"],
            "description": _t["description"],
            "parameters": _t["input_schema"]
        }
    })


def _strip_emojis(text):
    """Remove emoji and pictographic characters from a reply.

    Why: Pepper's tablet runs an old WebKit that renders supplementary-plane
    emoji (U+1F300+) poorly — Arabic + emoji especially seems to trip the
    renderer, dropping the WebSocket and locking up the UI for several
    seconds. Pepper's TTS also pronounces emojis as random sounds. Strip
    them defensively even when the system prompt forbids them, because
    Claude occasionally produces one anyway.
    """
    import re
    if not text:
        return text
    # Remove supplementary-plane characters (emojis + symbols) and dingbats
    return re.sub(
        u'[\U0001F300-\U0001FAFF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF'
        u'\U0001F900-\U0001F9FF\U00002600-\U000027BF\U0001F100-\U0001F1FF]+',
        '', text
    )


def _clean_llm_output(text, lang="en"):
    """Strip markdown artifacts and internal tool-call chatter that local
    models sometimes leak into user-facing text."""
    import re
    text = _strip_emojis(text or "")
    text = text.strip()
    # Strip leaked tool-result key prefixes that qwen sometimes echoes verbatim
    # (e.g. "_presentation_en ...", "\_presentation_en ...", "reply_en ...").
    # The \\ prefix variant occurs when qwen markdown-escapes the underscore.
    text = re.sub(r'^\\?(?:_presentation_(?:en|ar)|reply_(?:en|ar))\s+', '', text)

    # Strip template placeholder leakage: "[list of medications]",
    # "[your medications]", "[patient name]", "[insert X here]", etc.
    # These are artefacts of the model imitating a template reply rather than
    # using real data. Replace with a generic phrase so the sentence still flows.
    text = re.sub(
        r'\[(?:list|insert|your|the|patient|full)\s+[^\]\[]{0,40}\]',
        'the information on file',
        text, flags=re.IGNORECASE,
    )
    # Also strip obvious placeholders like "[XXX]" or "[TODO]" or "[...]"
    text = re.sub(r'\[(?:\.{3}|TODO|XXX|PLACEHOLDER|FILL(?:_IN)?)\]', '', text, flags=re.IGNORECASE)
    # Remove **bold** markers
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    # Remove *italic* markers
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # Remove markdown bullet points at line start
    text = re.sub(r'(?m)^[\-\*•]\s+', '', text)
    # Remove numbered list prefixes like "1. " at line start
    text = re.sub(r'(?m)^\d+\.\s+', '', text)
    # Remove markdown headers
    text = re.sub(r'(?m)^#+\s+', '', text)

    # Safety net: drop whole sentences that leak internal tool names,
    # parameter syntax, or tool-result narration. These should never reach the patient.
    tool_names = {t["name"] for t in CHAT_TOOLS}
    tool_alt   = "|".join(re.escape(n) for n in tool_names)
    # Patterns that indicate the model is narrating its tool-result context
    # to the patient (a common Ollama/qwen failure mode).
    leakage_patterns = [
        r"thank you for (?:providing|sharing|giving)",
        r"\bjson\b",
        r"\bthe\s+(?:dataset|data\s+you\s+provided|provided\s+data)\b",
        r"based on (?:this|the|your)\s+(?:provided\s+)?(?:information|data|json|dataset|list|entries)",
        r"\busing (?:this|the) data\b",
        r"\b(?:the|this) data(?:base)? shows\b",
        r"\blet'?s\s+break\s+(?:this|it|them)\s+down\b",
        r"\bhere are some (?:insights|observations|patterns|key points)\b",
        r"\bspecialties?\s+distribution\b",
        r"\bnames?\s+analysis\b",
        r"\bthe\s+(?:list|data)\s+contains\b",
        r"\b\d+\s+entries\b",
        r"\beach\s+entry\s+is\b",
        r"\bdictionary\s+with\b",
        r"(?:could|can|would) you (?:please\s+)?(?:specify|provide|clarify) "
        r"(?:what kind of|the task|more details about)",
        # Dataset-analysis narration (qwen failure mode: "Doctors' Names: ...")
        r"\bdoctors[''']?\s+names\s*:",
        r"\bspecialties\s+with\s+more\s+doctors\b",
        r"\bnames\s+(?:are\s+diverse|appear\s+multiple\s+times)\b",
        r"\b(?:no|any)\s+(?:clear\s+)?pattern\s+in\s+naming\b",
        r"\bnaming\s+conventions?\b",
        r"\bdifferent\s+genders\s+and\s+ethnic\s+backgrounds\b",
        r"\bcover(?:s|ing)?\s+a\s+wide\s+range\s+of\s+medical\s+fields\b",
        r"\b(?:filter|sort|count)\s+(?:doctors|the\s+list)\s+by\b",
        r"\bgenerate\s+statistics\b",
        # Extra variants observed in results.txt
        r"\bfor\s+example\s*:\s*(?:do\s+you|find\s+all|filter\s+doctors|count\s+how\s+many|sort\s+the\s+list)",
        r"\bif\s+you\s+need\s+to\s+perform\s+any\s+(?:specific\s+)?operations?\s+or\s+analys",
        r"\bthere\s+are\s+several\s+names\s+that\s+appear\s+multiple\s+times",
        r"\bthe\s+most\s+common\s+specialties\s+include\s*:",
        r"\b(?:generate|perform)\s+(?:some\s+)?(?:analys|statistics)",
        r"\bspecific\s+analysis\s+or\s+further\s+insights",
        r"\bhere\s+are\s+some\s+(?:insights|observations|statistics)",
        r"\bthe\s+(?:provided\s+)?list\s+(?:shows|contains|includes)\b",
    ]
    leakage_re = re.compile("|".join(leakage_patterns), re.IGNORECASE)

    # Split to sentences, drop any that look like internal narration.
    sentences = re.split(r'(?<=[\.\!\?؟])\s+', text)
    kept = []
    for s in sentences:
        if re.search(r"`\w+`", s):
            continue
        if re.search(r"\b(?:" + tool_alt + r")\b", s, re.IGNORECASE):
            continue
        if re.search(r"parameter\s+(?:set\s+to|value|named)", s, re.IGNORECASE):
            continue
        if re.search(r"\bfunction\s+call\b|\btool\s+call\b", s, re.IGNORECASE):
            continue
        if leakage_re.search(s):
            continue
        kept.append(s)

    if kept:
        text = " ".join(kept)
    else:
        # Everything was narration. Replace with a benign prompt for clarification
        # rather than leaking the original.
        if lang == "ar":
            text = "كيف أقدر أساعدك؟"
        else:
            text = "How can I help you?"

    # Strip scripts that should never appear in either English or Arabic
    # replies from this hospital bot. qwen2.5:7b occasionally switches
    # scripts mid-answer (seen: Chinese in an Arabic schedule reply).
    # Ranges: CJK Unified Ideographs, Hiragana/Katakana, Hangul, CJK symbols,
    # fullwidth forms, Cyrillic.
    text = re.sub(
        r'[\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u3400-\u4DBF\u4E00-\u9FFF'
        r'\uAC00-\uD7AF\uFF00-\uFFEF\u0400-\u04FF]+',
        '', text)

    # Arabic mode: also strip Hebrew (U+0590–U+05FF) which qwen occasionally
    # substitutes for Arabic. Arabic mode: drop any residual stretch that
    # is pure Latin (qwen sometimes falls back to English mid-sentence).
    if lang == "ar":
        text = re.sub(r'[\u0590-\u05FF]+', '', text)

    text = re.sub(r'\s{2,}', ' ', text).strip()
    # Collapse multiple newlines
    text = re.sub(r'\n{2,}', ' ', text)
    return text.strip()


def _detect_narrated_tool_name(text: str):
    """
    Detect when a model says 'I'll call get_doctors' (narrates a tool call in
    plain text) instead of actually calling it via the tool mechanism.
    Returns the matched tool name string, or None.
    """
    import re
    tool_names = {t["name"] for t in CHAT_TOOLS}

    # Catch many narration variants: "I'll call X", "let me call X",
    # "can you call X", "let's check with X", "we need to call X",
    # "first, let's use X", "by calling X", "via X", etc.
    intent_re = re.compile(
        r"(?:i(?:'ll| will| am going to| would| can| could)|let(?:'s|\s+me|\s+us)|"
        r"we(?:'ll| will| need to| should| can| could| can use| should use)|"
        r"you(?:'ll| can| should| could)|can you|could you|please|first[,\s]+|"
        r"by|via|through|going to|need to|have to|about to)[\s\w,]*?"
        r"(?:call|calling|use|using|invoke|invoking|run|running|execute|executing|"
        r"check(?:\s+with)?|trigger|querying|query)\s+"
        r"(?:the\s+)?[`'\"]?(\w+)[`'\"]?",
        re.IGNORECASE
    )
    m = intent_re.search(text)
    if m and m.group(1).lower() in tool_names:
        return m.group(1).lower()

    # "the get_doctors function/tool", "get_doctors() function"
    for bm in re.finditer(r"(\w+)\s*(?:\(\)|function|tool|method)", text, re.IGNORECASE):
        if bm.group(1).lower() in tool_names:
            return bm.group(1).lower()

    # Backtick-quoted tool name anywhere in the text: `get_doctors`
    for bm in re.finditer(r"`(\w+)`", text):
        if bm.group(1).lower() in tool_names:
            return bm.group(1).lower()

    # "parameter set to", "with the X parameter" — strong signal of tool narration
    if re.search(r"parameter\s+(?:set\s+to|value|named)", text, re.IGNORECASE):
        for tn in tool_names:
            if re.search(r"\b" + re.escape(tn) + r"\b", text, re.IGNORECASE):
                return tn

    # Semantic narration: model says it will check/find doctors without naming the tool.
    # e.g. "I'll check the doctors who specialize", "let me find a doctor for you",
    # "Let's see what doctor recommendations we have", "I'll look for a specialist"
    doctor_narrate_re = re.compile(
        r"(?:i(?:'ll| will| am going to| would| can)[\s\w,]*?|"
        r"let(?:'s|\s+me|\s+us)[\s\w,]*?|"
        r"let['']s see[\s\w,]*?)"
        r"(?:check|find|look\s+for|search\s+for|see|fetch|retrieve|get|pull|gather)"
        r"[\s\w,]*?(?:doctor|physician|specialist|recommendation)",
        re.IGNORECASE
    )
    if doctor_narrate_re.search(text):
        return "get_doctors"

    # "I'll retrieve your profile", "let me check your medical record/history"
    profile_narrate_re = re.compile(
        r"(?:i(?:'ll| will| am going to)[\s\w,]*?|let(?:'s|\s+me|\s+us)[\s\w,]*?)"
        r"(?:check|retrieve|fetch|get|look\s+(?:up|at)|pull)"
        r"[\s\w,]*?(?:profile|medical\s+(?:record|history|info)|patient\s+(?:record|info|data))",
        re.IGNORECASE
    )
    if profile_narrate_re.search(text):
        return "get_patient_profile"

    # Arabic narration: "سأتحقق من الأطباء", "دعني أبحث عن طبيب"
    if re.search(r"سأتحقق|سأبحث|دعني\s+(?:أتحقق|أبحث|أجد)\s+(?:عن\s+)?(?:طبيب|دكتور)", text):
        return "get_doctors"
    if re.search(r"سأتحقق|سأنظر|دعني\s+(?:أتحقق|أنظر)\s+(?:في\s+)?(?:ملفك|سجلك|تاريخك|بياناتك)", text):
        return "get_patient_profile"

    return None


def _detect_intent(user_text, lang="en"):
    """Return a tool name the user's message clearly demands, or None.

    Used to enforce tool calls on local (qwen) models that often skip them
    for navigation / patient-profile / booking queries. We only return a
    tool name when the signal is very strong — false positives hurt more
    than false negatives here.
    """
    import re
    t = (user_text or "").lower().strip()
    if not t:
        return None

    # List appointments: "show/what are my appointments", "do I have any appointments"
    list_appt_en = (
        r"\b(?:show|list|what are|check|see|view|tell me)\s+(?:me\s+)?(?:my|all|current|upcoming)\s+"
        r"(?:upcoming\s+)?appointments?\b|"
        r"\bdo i (?:still\s+)?have (?:any|upcoming|some) appointments?\b|"
        r"\bhow many appointments\b|"
        r"\bmy (?:upcoming|current|scheduled|remaining|existing) appointments?\b|"
        r"\bwhat appointments\b|"
        r"\bappointments?\s+(?:do|have)\s+i\s+(?:still\s+)?(?:have|got)\b|"
        r"\bremaining\s+appointments?\b|"
        r"\bappointments?\s+(?:i\s+still\s+have|left|remaining)\b|"
        r"\bany\s+(?:upcoming\s+)?appointments?\s+(?:i\s+have|left|remaining)\b|"
        r"\bremind\s+me\s+(?:of\s+)?(?:my\s+)?appointments?\b"
    )
    list_appt_ar = r"مواعيدي|مواعيدك|عرض المواعيد|ما هي مواعيدي|هل لدي مواعيد"
    if re.search(list_appt_en, t) or re.search(list_appt_ar, user_text or ""):
        return "get_my_appointments"

    # Cancel by context (no explicit numeric ID): fetch appointments first so the
    # model can identify the right one to cancel.
    cancel_no_id_en = (
        r"\bcancel\b(?!.*\b(?:appointment\s+)?(?:number|#|id|no\.?)\s*\d+\b)"
        r".*\b(?:appointment|visit|booking|slot)\b|"
        r"\bcancel\s+(?:my|the|that|this)\s+appointment\b(?!.*\b\d{3,}\b)|"
        r"\bcancel\s+(?:what|the one|it)\b"
    )
    cancel_no_id_ar = r"إلغاء\s+موعدي|الغِ\s+موعدي|أريد\s+إلغاء\s+الموعد"
    if re.search(cancel_no_id_en, t) or re.search(cancel_no_id_ar, user_text or ""):
        # Return get_my_appointments so the model fetches the list first, then cancels
        return "get_my_appointments"

    # Patient profile: questions about the user's own record (strengthened to catch
    # medication-specific questions that qwen skips the tool for)
    profile_en = (
        r"\bmy (?:medical )?record\b|\bmy (?:profile|history|allergies|medications?|"
        r"meds|prescription|blood type|age|date of birth|dob)\b|"
        r"\bhow old am i\b|\bwhen was i born\b|\bwhat (?:do )?you know about me\b|"
        r"\bam i (?:allergic|diabetic|on any)\b|\bdo i (?:have|take)\b.+(?:allerg|medic|condition)|"
        r"\bwhat medications?\s+am i\b|\bwhat(?:'m| am) i (?:currently\s+)?(?:taking|on)\b|"
        r"\bwhat meds am i\b|\bam i (?:currently\s+)?(?:taking|on)\s+any\b|"
        r"\bcurrently\s+(?:on|taking)\s+(?:any\s+)?medications?\b"
    )
    profile_ar = (
        r"ملفي الطبي|تاريخي الطبي|حساسيتي|أدويتي|دوائي|فصيلة دمي|عمري|"
        r"تاريخ ميلادي|ماذا تعرف عني|هل أعاني|هل أتناول"
    )
    if re.search(profile_en, t) or re.search(profile_ar, user_text or ""):
        return "get_patient_profile"

    # Navigation: guide / take me / where is X / where can I Y
    # Checked BEFORE departments so "I need the radiology department" routes to
    # navigation (the facility-name match fires) rather than to get_departments
    # (the word "department" alone is too broad a signal).
    nav_en = (
        r"\btake me to\b|\bguide me (?:to|toward)?\b|\blead me to\b|\bdirect me to\b|"
        r"\bhow do i (?:get|go|find) to\b|\bhow do i find\b|"
        r"\bwhere (?:is|are|can i find|'?s)\b|"
        r"\bwhere'?s\b|"                                   # contraction: "where's the ..."
        r"\bwhere can (?:you|i)\s+(?:take|guide|lead|pay|find|go|get)\b|"
        r"\bdirections? to\b|\bnavigate (?:me )?to\b|\b(?:show|point) me (?:the way|to)\b|"
        r"\bi need (?:to get to|to find|the)\s+(?:pharmacy|lab|laboratory|radiology|emergency|"
        r"icu|maternity|cafeteria|restroom|bathroom|toilet|reception|blood bank|operating|"
        r"elevator|elevators|billing|waiting area|nurse)\b|"
        r"\bi need to (?:get to|find|reach)\b|"            # "I need to find reception"
        r"\bcan you (?:take|bring|show|point|guide|direct) me\b|"
        r"\bi'?m hungry\b|"
        r"\bwhich (?:floor|level|way)\b"
    )
    nav_ar = (
        r"خذني إلى|دلني على|أرني|كيف أذهب|كيف أصل|أين هو|أين يقع|أين توجد|أين\s+الـ|"
        r"اذهب بي|اصطحبني|اريد الذهاب|فين\s+(?:الصيدلية|المختبر|الطوارئ|الاستقبال|الحمام)"
    )
    if re.search(nav_en, t) or re.search(nav_ar, user_text or ""):
        return "get_navigation_targets"

    # Bare facility name (without "where is") — "pharmacy?", "the cafeteria please"
    bare_facility_en = (
        r"^(?:the\s+)?(?:pharmacy|laboratory|lab|radiology|emergency\s+(?:room|department)|"
        r"icu|maternity|cafeteria|restroom|bathroom|toilet|reception|blood bank|"
        r"operating theatres?|elevators?|billing|waiting area)\s*\??$"
    )
    if re.search(bare_facility_en, t):
        return "get_navigation_targets"

    # Departments: "what departments do you have", "show hospital departments", etc.
    # Placed AFTER navigation so facility-specific queries are not misclassified.
    dept_en = (
        r"\b(?:what|which|show|list|tell me(?: about)?|do you have|see)\s+"
        r"(?:the\s+)?(?:medical\s+|hospital\s+)?departments?\b|"
        r"\bhospital\s+departments?\b|"
        r"\bdepartments?\s+(?:available|you have|at the hospital|in the hospital|here)\b|"
        r"\bwhat\s+(?:medical\s+)?(?:services|specialties|specializations)\s+(?:do you|does the hospital)\b"
    )
    dept_ar = (
        r"الأقسام|أقسام المستشفى|ما هي الأقسام|ما الأقسام|عرض الأقسام|"
        r"التخصصات|الخدمات الطبية"
    )
    if re.search(dept_en, t) or re.search(dept_ar, user_text or ""):
        return "get_departments"

    # Doctor recommendation / find a doctor
    recommend_en = (
        r"\b(?:recommend|suggest|find|show)(?: me)? (?:a |an )?(?:doctor|physician|specialist|"
        r"gp|general\s+practitioner|cardiologist|dermatologist|neurologist|psychiatrist|"
        r"psychologist|oncologist|pediatrician|orthopedist|gastroenterologist|"
        r"endocrinologist|urologist|gynecologist|surgeon|internist|rheumatologist|"
        r"pulmonologist|nephrologist|ophthalmologist|ent|dentist|radiologist)\b|"
        r"\bwho should i (?:see|visit|consult)\b|\bi need (?:a |to see )(?:a |an )?(?:doctor|specialist)\b|"
        r"\bcan you (?:recommend|suggest) (?:a |an )?(?:doctor|physician|specialist)\b"
    )
    recommend_ar = (
        r"أنصحني بطبيب|اقترح(?:ي)? طبيب|أريد طبيب|محتاج(?:ة)? طبيب|دكتور(?:ة)? (?:عام|متخصص)|"
        r"من أرى|أنصحني|انصحني|اقترح لي|"
        r"رشح لي|ارشح لي|ارشحلي|رشحيلي|رشحلي|وصيلي|وصّيلي|"
        r"رشّح|ارشح|نفسي محتاج|محتاج(?:ة)? دكتور|"
        r"(?:رشح|ارشح|وصي|اقترح).{0,15}دكتور|"
        r"حسب حالتي.{0,20}دكتور|دكتور.{0,20}حسب حالتي"
    )
    if re.search(recommend_en, t) or re.search(recommend_ar, user_text or ""):
        return "get_doctors"

    # Broad catch: "a doctor" + context phrase — handles bad STT transcriptions
    # like "To me, a doctor based on my patient" (mangled Arabic → English).
    has_doctor_word = bool(re.search(r"\b(?:a |an )?(?:doctor|physician|specialist)\b", t))
    has_context = bool(re.search(
        r"\bbased on\b|\bfor my\b|\baccording to\b|\bmatching my\b|\bsuitable for\b|"
        r"\bfor me\b|\brecommend\b|\bsuggest\b|\badvise\b", t))
    if has_doctor_word and has_context:
        return "get_doctors"

    # Booking: explicit date + time + booking verb. We intentionally do NOT
    # require the word "appointment" — natural phrasings like "book with Dr. X
    # on DATE at TIME" or "I'd like to schedule a visit on DATE at TIME" are
    # valid booking requests.
    has_date = bool(re.search(r"\b\d{4}-\d{1,2}-\d{1,2}\b", user_text or ""))
    has_time = bool(re.search(r"\b\d{1,2}:\d{2}\b", user_text or ""))
    book_en  = (
        r"\b(?:book|schedule|reserve|make)\b.*\bappointment\b"
        r"|\bbook (?:me|an appointment|a slot)\b"
        r"|\b(?:book|reserve)\s+(?:me\s+)?(?:with|for)\b"     # "book with Dr. X"
        r"|\b(?:i(?:'d| would) like to|i want to|please)\s+(?:book|schedule|reserve)\b"
        r"|\bschedule\s+(?:a\s+)?(?:visit|session|consultation|appointment|slot)\b"
    )
    book_ar  = r"احجز|احجزي|اريد حجز|عايز(?:ة)? حجز|محتاج(?:ة)? حجز"
    if has_date and has_time and (re.search(book_en, t) or re.search(book_ar, user_text or "")):
        return "book_appointment"

    return None


# High-priority red-flag patterns. If any hit, bypass the LLM entirely and
# return a hard-coded triage reply. The LLM is too unreliable for the
# handful of conditions where wrong advice can kill someone (anaphylaxis,
# stroke, overdose, severe chest pain).
_EMERGENCY_PATTERNS = [
    # (regex_en, regex_ar, reply_en, reply_ar, label)
    #
    # Witnessed / third-person emergency — matches "my husband had a seizure",
    # "she is unconscious", "someone collapsed", etc. Checked FIRST so it is
    # never shadowed by a more-specific pattern that fires on the wrong branch.
    (
        r"(?:he|she|they|my\s+\w+|someone|a\s+(?:man|woman|person|child|patient|visitor))"
        r".{0,80}"
        r"\b(?:seizure|convuls(?:ion|ing)|unconscious|unresponsive|not\s+breathing|"
        r"collapsed|passed\s+out|fainted|no\s+pulse)\b"
        r"|"
        r"\b(?:had|having|is\s+having)\s+a\s+seizure\b"
        r"|"
        r"\b(?:unconscious|unresponsive)\b.{0,40}\b(?:lobby|floor|corridor|waiting|entrance)\b",
        r"زوجي|زوجتي|ابني|ابنتي|شخص\s*(?:ما)?|أحد\s*(?:ما)?"
        r".{0,80}"
        r"(?:تشنج|فاقد\s*الوعي|لا\s*يستجيب|لا\s*يتنفس|انهار)",
        "This is a medical emergency. Call emergency services immediately "
        "(dial 122 or go to the Emergency Department on the Ground Floor right now). "
        "Stay with the person, clear the area around them, and flag any hospital "
        "staff nearby for immediate assistance. Do not leave them alone.",
        "هذه حالة طارئة. اتصل بالإسعاف فوراً (122) أو توجه إلى قسم الطوارئ في الدور "
        "الأرضي الآن. ابقَ مع الشخص وأزل أي أشياء حوله وأبلغ أي طاقم طبي قريب.",
        "witnessed_emergency",
    ),
    (
        r"\btongue\s+(?:is\s+|feels?\s+)?(?:swollen|swelling|numb|enlarged)|"
        r"\bthroat\s+(?:is\s+)?(?:closing|swelling|swollen|tight)|"
        r"\b(?:hives?|rash|welts?|urticaria)\b.{0,80}\b(?:breath|swelling|swollen|tongue|lips?|face)\b|"
        r"\b(?:lips?|face|tongue)\b.{0,60}\b(?:swollen|swelling)\b.{0,60}\b(?:hives?|rash|itch|breath)\b|"
        r"\bswollen\b.{0,40}\b(?:tongue|throat|lips?|face)\b|"
        r"\bbreaking\s+out\s+in\s+(?:hives?|rash)|"
        r"\banaphyla",
        r"لساني\s*(?:متورم|منتفخ)|حلقي\s*(?:يغلق|منتفخ)|تورم\s*(?:الشفاه|الوجه|اللسان)|"
        r"حساسية\s*مفرطة|anaphyla",
        "This sounds like a severe allergic reaction (anaphylaxis). Call emergency services "
        "immediately. If you have an epinephrine auto-injector (EpiPen), use it now. "
        "Go to the Emergency Department on the Ground Floor right away.",
        "يبدو أن هذه حساسية مفرطة خطيرة. اتصل بالطوارئ فوراً. "
        "إذا كان لديك حقنة إبينفرين، استخدمها الآن. توجه إلى قسم الطوارئ في الدور الأرضي حالاً.",
        "anaphylaxis",
    ),
    (
        r"\bfac(?:e|ial)\s+(?:is\s+)?dropping|face\s+drooping\b|\bcan'?t\s+(?:lift|raise|move)\s+(?:my\s+)?(?:arm|leg)\b|"
        r"\bsudden\s+(?:weakness|numbness)\b.*\b(?:arm|leg|face|side)\b|\bslurred\s+speech\b|"
        r"\bstroke\b.*\bsymptoms\b",
        r"وجهي\s*(?:مائل|منحرف)|لا\s*أستطيع\s*(?:رفع|تحريك)\s*(?:ذراعي|يدي|رجلي)|"
        r"نصف\s*جسمي\s*(?:ضعيف|مشلول)|كلامي\s*(?:متلعثم|غير واضح)",
        "These are warning signs of a stroke. Time is critical. Call emergency services now "
        "or go directly to the Emergency Department on the Ground Floor. Do not wait.",
        "هذه علامات سكتة دماغية. الوقت حرج جداً. اتصل بالطوارئ الآن أو توجه فوراً إلى قسم "
        "الطوارئ في الدور الأرضي. لا تنتظر.",
        "stroke",
    ),
    (
        r"\bsevere\s+chest\s+pain\b|\bcrushing\s+chest\b|\bchest\s+pain\b.*\b(?:radiat|left\s+arm|jaw|sweat|breath)\b|"
        r"\bheart\s+attack\b",
        r"ألم\s*(?:شديد\s*في\s*)?الصدر|ضغط\s*في\s*صدري|نوبة\s*قلبية",
        "Severe chest pain can mean a heart attack. Call emergency services immediately. "
        "Sit down, stay calm, and go to the Emergency Department on the Ground Floor.",
        "ألم الصدر الشديد قد يعني نوبة قلبية. اتصل بالطوارئ فوراً. اجلس، اهدأ، "
        "وتوجه إلى قسم الطوارئ في الدور الأرضي.",
        "chest_pain",
    ),
    (
        r"\b(?:double|twice|two)\s+(?:my\s+)?(?:dose|pill|tablet|medication)\b|"
        r"\b(?:took|swallowed)\s+(?:too\s+many|extra)\b|\boverdose\b|"
        r"\btook\s+double\b",
        r"جرعة\s*(?:مضاعفة|زائدة)|تناولت\s*(?:حبتين|جرعتين)|جرعة\s*زائدة",
        "A medication overdose can be dangerous. Call the poison control hotline or emergency "
        "services right now and tell them which medication and how much. Do not wait for symptoms. "
        "If you are at the hospital, go to the Emergency Department immediately.",
        "الجرعة الزائدة قد تكون خطيرة. اتصل بالطوارئ الآن وأخبرهم عن الدواء والكمية. "
        "لا تنتظر الأعراض. إذا كنت في المستشفى، توجه فوراً إلى قسم الطوارئ.",
        "overdose",
    ),
    (
        r"\b(?:can'?t|cannot|not\s+able\s+to)\s+breathe\b|\bchoking\b|\bturning\s+blue\b",
        r"لا\s*أستطيع\s*التنفس|أختنق|ضيق\s*(?:شديد\s*)?في\s*التنفس",
        "Severe breathing difficulty is a medical emergency. Call emergency services or go to "
        "the Emergency Department on the Ground Floor right now.",
        "صعوبة التنفس الشديدة حالة طارئة. اتصل بالطوارئ أو توجه فوراً إلى قسم الطوارئ "
        "في الدور الأرضي.",
        "respiratory",
    ),
    (
        r"\b(?:seizure|convuls(?:ion|ing))\b|"
        r"\b(?:unconscious|unresponsive|passed\s+out|collapsed|fainted)\b|"
        r"\b(?:not\s+breathing|no\s+pulse)\b|"
        r"\b(?:fell|fallen)\s+(?:down\s+)?and\s+(?:is|isn'?t|won'?t)\s+(?:respond|wake)",
        r"نوبة\s*(?:صرع|تشنج)|تشنج|فاقد\s*(?:الوعي|للوعي)|"
        r"غائب\s*عن\s*الوعي|لا\s*يستجيب|انهار|وقع\s*على\s*الأرض",
        "This is a medical emergency. Call emergency services immediately (911 or local equivalent). "
        "Keep the person safe — clear the area, do not restrain them, and turn them on their side "
        "if possible. Flag any hospital staff nearby and go to the Emergency Department on the "
        "Ground Floor for immediate assistance.",
        "هذه حالة طارئة. اتصل بالطوارئ فوراً. حافظ على سلامة المريض - أزل أي أشياء حوله، "
        "لا تحاول تقييده، وأدره على جانبه إن أمكن. أبلغ أي طاقم طبي قريب وتوجه إلى قسم "
        "الطوارئ في الدور الأرضي للمساعدة الفورية.",
        "seizure_unconscious",
    ),
    (
        r"\b(?:severe|heavy|uncontrolled|won'?t\s+stop|massive)\s+bleeding\b|"
        r"\bbleeding\s+(?:won'?t\s+stop|heavily|profusely|badly)\b|"
        r"\b(?:cut|cutting|stabbed|stab)\b.{0,40}\b(?:deep|deeply|artery|vein)\b|"
        r"\bhemorrhag",
        r"نزيف\s*(?:شديد|غزير|لا\s*يتوقف)|ينزف\s*بشدة",
        "This is a bleeding emergency. Apply firm direct pressure to the wound with a clean cloth, "
        "elevate the injured area if possible, and call emergency services immediately. "
        "Go to the Emergency Department on the Ground Floor right away.",
        "هذه حالة نزيف طارئة. اضغط بقوة مباشرة على الجرح بقماش نظيف، ارفع المنطقة المصابة إن "
        "أمكن، واتصل بالطوارئ فوراً. توجه إلى قسم الطوارئ في الدور الأرضي حالاً.",
        "severe_bleeding",
    ),
]


def _strip_fake_booking_claim(reply_text, tool_results, lang="en"):
    """Rewrite the reply if it claims a successful booking without a matching
    book_appointment tool success in this turn.

    tool_results is the list returned by run_agentic_loop — each entry is a
    dict like {"tool": "...", "output": {...}}.
    """
    import re
    if not reply_text:
        return reply_text

    # Did book_appointment succeed in this turn?
    booked_ok = False
    for tr in (tool_results or []):
        if not isinstance(tr, dict):
            continue
        if tr.get("tool") != "book_appointment":
            continue
        out = tr.get("result") or tr.get("output") or {}
        if isinstance(out, dict) and (out.get("success") is True or out.get("appointment_id")):
            booked_ok = True
            break
    if booked_ok:
        return reply_text

    # No successful booking — scrub any claim of one.
    claim_patterns_en = [
        r"(?:your\s+)?appointment\s+(?:has\s+been\s+|is\s+|was\s+)?(?:successfully\s+)?booked",
        r"(?:booking|appointment)\s+(?:has\s+been\s+)?confirmed",
        r"i(?:'ve| have)\s+(?:successfully\s+)?booked",
        r"i(?:'ve| have)\s+scheduled\s+your\s+appointment",
        r"you(?:'re| are)\s+(?:now\s+)?booked",
        r"done[,\.!]\s+you(?:'re| are)\s+booked",
    ]
    claim_patterns_ar = [
        r"تم\s*حجز\s*(?:الموعد|موعد)",
        r"تم\s*تأكيد\s*(?:الموعد|الحجز)",
        r"حجزت\s*لك",
        r"تمت\s*عملية\s*الحجز",
    ]
    hit = False
    for p in claim_patterns_en:
        if re.search(p, reply_text, re.IGNORECASE):
            hit = True
            break
    if not hit:
        for p in claim_patterns_ar:
            if re.search(p, reply_text):
                hit = True
                break
    if not hit:
        return reply_text

    # Replace with an honest prompt asking the patient to confirm.
    if lang == "ar":
        return ("لم يتم الحجز بعد. هل تؤكد أنك تريد حجز هذا الموعد "
                "مع الطبيب في التاريخ والوقت المذكورين؟")
    return ("The appointment is not booked yet. Please confirm the doctor, "
            "date, and time so I can complete the booking.")


def _strip_fake_cancel_claim(reply_text, tool_results, lang="en"):
    """Rewrite the reply if it claims a successful cancellation without a matching
    cancel_appointment tool success in this turn."""
    import re
    if not reply_text:
        return reply_text

    cancelled_ok = any(
        isinstance(tr, dict) and tr.get("tool") == "cancel_appointment"
        and isinstance(tr.get("result") or tr.get("output"), dict)
        and (tr.get("result") or tr.get("output") or {}).get("success") is True
        for tr in (tool_results or [])
    )
    if cancelled_ok:
        return reply_text

    cancel_patterns_en = [
        r"(?:all\s+)?appointments?\s+(?:for\s+Dr\.?\s+\w+\s+)?(?:have\s+been|has\s+been|were|was)\s+(?:successfully\s+)?cancell?ed",
        r"i(?:'ve| have)\s+cancell?ed\s+(?:your|the|all)",
        r"(?:your\s+)?appointment\s+(?:has\s+been|was)\s+(?:successfully\s+)?cancell?ed",
        r"cancell?ation\s+(?:was\s+)?(?:successful|confirmed|complete)",
        r"done[,\.!]\s+(?:the\s+)?appointment\s+(?:has\s+been\s+)?cancell?ed",
    ]
    cancel_patterns_ar = [
        r"تم\s*إلغاء\s*(?:جميع\s*)?المواعيد",
        r"تم\s*إلغاء\s*الموعد",
        r"ألغيت\s*(?:الموعد|مواعيد)",
    ]
    hit = any(re.search(p, reply_text, re.IGNORECASE) for p in cancel_patterns_en)
    if not hit:
        hit = any(re.search(p, reply_text) for p in cancel_patterns_ar)
    if not hit:
        return reply_text

    if lang == "ar":
        return "لم أتمكن من إلغاء الموعد. هل يمكنك تأكيد رقم الموعد؟"
    return "I was unable to cancel the appointment. Could you confirm the appointment details?"


def _detect_medical_emergency(user_text, lang="en"):
    """Pre-LLM safety check: if the user's message matches a known red-flag
    pattern, return a hard-coded triage reply that bypasses the agentic loop.
    Returns (reply_text, label) or (None, None)."""
    import re
    t = (user_text or "").strip()
    if not t:
        return None, None
    low = t.lower()
    for pat_en, pat_ar, reply_en, reply_ar, label in _EMERGENCY_PATTERNS:
        hit = False
        if pat_en and re.search(pat_en, low, re.IGNORECASE):
            hit = True
        elif pat_ar and re.search(pat_ar, t):
            hit = True
        if hit:
            return (reply_ar if lang == "ar" else reply_en), label
    return None, None


def _try_parse_raw_tool_call(text):
    """
    Some models (especially in Arabic mode) output raw JSON tool calls as text
    instead of using native tool calling. Detect and parse those.
    Pattern: {"name": "tool_name", "arguments": {...}}
    """
    import re
    # Strip any prefix text before the JSON object
    match = re.search(r'\{[^{}]*"name"\s*:\s*"(\w+)"[^{}]*"arguments"\s*:\s*(\{[^}]*\})', text, re.DOTALL)
    if not match:
        return None
    try:
        start = text.find('{', match.start())
        # Find matching closing brace
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    obj = json.loads(text[start:i+1])
                    if 'name' in obj and 'arguments' in obj:
                        return obj
                    break
    except Exception:
        pass
    return None


# Alias map: words a patient might use → canonical search terms that appear in
# navigation_targets.json facility names/types.  Used by _build_nav_directive.
_NAV_ALIASES = {
    "bathroom":       "restroom",
    "toilet":         "restroom",
    "washroom":       "restroom",
    "loo":            "restroom",
    " wc ":           "restroom",
    "icu":            "icu",
    "intensive care": "icu",
    "pay ":           "billing",
    "payment":        "billing",
    " bill ":         "billing",
    "my bill":        "billing",
    "billing":        "billing",
    "x-ray":          "radiology",
    "xray":           "radiology",
    "imaging":        "radiology",
    " scan":          "radiology",
    " lift":          "elevator",
    "operating room": "operating",
    "theatre":        "operating",
    "theater":        "operating",
    "hungry":         "cafeteria",
    " food":          "cafeteria",
    "blood bank":     "blood",
    "labour":         "maternity",
    "labor":          "maternity",
    "delivery":       "maternity",
    "waiting area":   "waiting",
    " er ":           "emergency",
    "emergency room": "emergency",
    "emergency dept": "emergency",
}


def _build_nav_directive(tool_result, user_q):
    """Pre-match a navigation query to the closest facility and return a
    SYSTEM DIRECTIVE string.  Called from both the fast-path (before any LLM
    inference) and the post-tool-call block inside the agentic loop."""
    facilities = tool_result.get("facilities", [])
    offices    = tool_result.get("doctor_offices", [])
    user_q_lc  = (user_q or "").lower()

    # Normalize using aliases so "bathroom"→"restroom", "icu"→"icu", etc.
    search_q = user_q_lc
    for alias, canonical in _NAV_ALIASES.items():
        if alias in user_q_lc:
            search_q = canonical
            break

    _matched = None
    for fac in facilities:
        fname = (fac.get("name") or "").lower()
        ftype = (fac.get("facility_type") or "").lower()
        # min-length 3 catches short but valid tokens like "icu", "lab", "er"
        kws = [w for w in (fname + " " + ftype).split() if len(w) >= 3]
        if any(kw in search_q or kw in user_q_lc for kw in kws):
            _matched = f"{fac['name']} is located at {fac.get('location', 'the hospital')}."
            break
    if not _matched:
        for off in offices:
            oname = (off.get("name") or "").lower()
            kws = [w for w in oname.split() if len(w) >= 3]
            if any(kw in search_q or kw in user_q_lc for kw in kws):
                _matched = (
                    f"{off['name']}'s office is at "
                    f"{off.get('location', 'the hospital')}."
                )
                break

    if _matched:
        return (
            f"[SYSTEM DIRECTIVE] Navigation result: {_matched} "
            f"Tell the patient exactly this location in one sentence. "
            f"Do NOT list other locations or mention doctors."
        )
    # Unknown location — graceful refusal
    _fac_lines = "; ".join(
        f"{f['name']}: {f.get('location', '')}" for f in facilities[:10]
    )
    return (
        f"[SYSTEM DIRECTIVE] The patient asked about a location that is not in our "
        f"list. Hospital locations: {_fac_lines}. "
        f"Tell the patient we do not have that specific location and suggest asking "
        f"at reception. Do NOT list all locations."
    )


def _run_agentic_loop_offline(system_prompt, messages, user_id, user_name, role,
                               voice_mode, tool_results_for_display, lang="en"):
    """Ollama-based agentic loop with native structured tool calls — mirrors Claude's loop."""
    # Intent-based token budget: simple lookups need far fewer tokens than
    # booking/symptom/multi-step flows, so set max_tokens per intent rather than
    # one global ceiling.  This alone saves 2-4 s per simple turn on GPU.
    # Only truly stateless, context-free lookups get the 200-token budget.
    # get_my_appointments is stateful (changes after every booking/cancel) —
    # the model must always call fresh.  get_departments is excluded because
    # the word "department" in nav queries (e.g. "I need the radiology
    # department") can false-positive as that intent, dropping max_tokens
    # to 200 and causing the model to answer from stale context.
    _SIMPLE_INTENTS = {
        "get_navigation_targets",
        "get_patient_profile",
    }
    detected_early = _detect_intent(
        next((m.get("content","") for m in reversed(messages)
              if m.get("role") == "user" and isinstance(m.get("content"), str)), ""),
        lang=lang,
    )
    if detected_early in _SIMPLE_INTENTS:
        max_tokens = 200
    elif voice_mode:
        max_tokens = 512
    else:
        max_tokens = 1024
    max_iterations = 5

    last_user_msg = next(
        (m.get("content", "") for m in reversed(messages)
         if m.get("role") == "user" and isinstance(m.get("content"), str)),
        ""
    )
    # detected_early was already computed for max_tokens; reuse it here.
    detected = detected_early

    # ── Fast-path: navigation skips Pass 1 (tool-decision LLM call) entirely ──
    # Detect nav intent → execute tool directly → single LLM call with the
    # pre-matched result.  Cuts nav turn time ~50% (20-25 s → 10-13 s).
    # History is trimmed to the last 3 messages because nav is stateless.
    if detected == "get_navigation_targets":
        tool_result = execute_tool("get_navigation_targets", {}, user_id, user_name, role)
        tool_results_for_display.append({"tool": "get_navigation_targets", "result": tool_result})
        nav_directive = _build_nav_directive(tool_result, last_user_msg)
        # Inject the directive via the system prompt so we never produce an
        # invalid message sequence (tool-role message without a preceding
        # assistant tool-call causes Ollama to mis-handle or ignore the result).
        nav_system = system_prompt + f"\n\n{nav_directive}"
        raw = call_ollama(nav_system, messages[-3:], max_tokens=200, num_ctx=2048)
        if isinstance(raw, dict):
            raw = raw.get("text", "")
        return _clean_llm_output(raw, lang=lang) or "Done.", tool_results_for_display

    # ── Fast-path: departments ──
    # Execute tool → inject dept list into system prompt → single LLM call.
    # History trimmed to 3 because dept listing is stateless.
    if detected == "get_departments":
        tool_result = execute_tool("get_departments", {}, user_id, user_name, role)
        tool_results_for_display.append({"tool": "get_departments", "result": tool_result})
        depts = tool_result.get("departments", [])
        if depts:
            dept_names = ", ".join(str(d) for d in depts if d)
            dept_directive = (
                f"[SYSTEM DIRECTIVE] Hospital departments: {dept_names}. "
                f"Answer the patient's question about departments using this list."
            )
        else:
            dept_directive = (
                "[SYSTEM DIRECTIVE] Department data is unavailable. "
                "Tell the patient to ask at the reception desk."
            )
        dept_system = system_prompt + f"\n\n{dept_directive}"
        raw = call_ollama(dept_system, messages[-3:], max_tokens=200, num_ctx=2048)
        if isinstance(raw, dict):
            raw = raw.get("text", "")
        return _clean_llm_output(raw, lang=lang) or "Done.", tool_results_for_display

    # ── Fast-path: patient profile ──
    # Execute tool → inject profile data into system prompt → single LLM call.
    if detected == "get_patient_profile":
        tool_result = execute_tool("get_patient_profile", {}, user_id, user_name, role)
        tool_results_for_display.append({"tool": "get_patient_profile", "result": tool_result})
        if not tool_result.get("error"):
            profile_directive = (
                f"[SYSTEM DIRECTIVE] Patient profile: {json.dumps(tool_result)}. "
                f"Present the relevant information to the patient concisely."
            )
        else:
            profile_directive = (
                "[SYSTEM DIRECTIVE] Patient profile not found. "
                "Tell the patient we couldn't retrieve their profile and suggest asking at reception."
            )
        profile_system = system_prompt + f"\n\n{profile_directive}"
        raw = call_ollama(profile_system, messages[-3:], max_tokens=200, num_ctx=2048)
        if isinstance(raw, dict):
            raw = raw.get("text", "")
        return _clean_llm_output(raw, lang=lang) or "Done.", tool_results_for_display
    # ──────────────────────────────────────────────────────────────────────────

    # History trimming for the main agentic loop: semi-stateless intents only
    # need recent context; complex multi-step flows need full history.
    # (Stateless intents are already handled by fast-paths above.)
    _SEMI_STATELESS = {"get_my_appointments"}
    if detected in _SEMI_STATELESS:
        messages = messages[-8:]
        loop_num_ctx = 3072
    else:
        loop_num_ctx = 4096

    # For other detected intents: inject a SYSTEM DIRECTIVE so qwen calls the
    # right tool on its first iteration (it often skips tools otherwise).
    forced_tool = None
    if detected:
        forced_tool = detected
        messages = messages + [{
            "role": "user",
            "content": (
                f"[SYSTEM DIRECTIVE] The patient's request requires the '{detected}' tool. "
                f"Your next response MUST be a call to '{detected}' via the tool-call mechanism. "
                f"Do NOT answer in plain text until you have the tool result."
            )
        }]

    for iteration in range(max_iterations):
        result = call_ollama(system_prompt, messages, max_tokens=max_tokens,
                             tools=OLLAMA_TOOLS, num_ctx=loop_num_ctx)

        # If result is a plain string, check for raw tool call JSON leaking into text
        if isinstance(result, str):
            raw_tc = _try_parse_raw_tool_call(result)
            if raw_tc:
                # Treat it the same as a native tool call
                t_name  = raw_tc.get("name", "")
                t_input = raw_tc.get("arguments") or {}
                if isinstance(t_input, str):
                    try:
                        t_input = json.loads(t_input)
                    except Exception:
                        t_input = {}
                if not isinstance(t_input, dict):
                    t_input = {}
                valid_tools = {t["name"] for t in CHAT_TOOLS}
                if t_name in valid_tools:
                    print(f"[TOOL-OFFLINE-RAW] {t_name}({t_input})")
                    tool_result = execute_tool(t_name, t_input, user_id, user_name, role)
                    tool_results_for_display.append({"tool": t_name, "result": tool_result})
                    messages.append({"role": "assistant", "content": ""})
                    messages.append({"role": "tool", "content": json.dumps(tool_result)})
                    continue

            # Model narrated a tool intent in plain English instead of calling it.
            # Inject a directive and retry so the tool actually executes.
            narrated = _detect_narrated_tool_name(result)
            if narrated:
                print(f"[TOOL-OFFLINE-NARRATED] Model narrated '{narrated}' — injecting directive")
                messages.append({"role": "assistant", "content": result})
                messages.append({
                    "role": "user",
                    "content": (
                        f"[SYSTEM DIRECTIVE] You described calling '{narrated}' in words but did not "
                        f"actually call it. You MUST call '{narrated}' NOW using the tool-call mechanism. "
                        f"Do NOT write any text — just emit the tool call."
                    )
                })
                continue

            # Forced-intent retry: the intent detector is certain a tool is required
            # but the model answered in plain text anyway. Force it once more.
            tools_called = {t.get("tool") for t in tool_results_for_display}
            if forced_tool and forced_tool not in tools_called and iteration <= 1:
                print(f"[TOOL-OFFLINE-FORCED] Forcing '{forced_tool}' — model answered without calling it")
                messages.append({"role": "assistant", "content": result})
                messages.append({
                    "role": "user",
                    "content": (
                        f"[SYSTEM DIRECTIVE] You answered in plain text but the patient's question "
                        f"requires calling '{forced_tool}' first. Call '{forced_tool}' NOW using the "
                        f"tool-call mechanism. Do NOT write any text — just emit the tool call."
                    )
                })
                continue

            return _clean_llm_output(result, lang=lang) or "Done.", tool_results_for_display

        # Native tool call response
        text = result.get("text", "")
        tool_calls = result.get("tool_calls", [])

        if tool_calls:
            # Record assistant message with tool calls
            messages.append({"role": "assistant", "content": text or ""})

            for tc in tool_calls:
                fn = tc.get("function", {})
                t_name  = fn.get("name", "")
                t_input = fn.get("arguments") or {}
                if isinstance(t_input, str):
                    try:
                        t_input = json.loads(t_input)
                    except json.JSONDecodeError:
                        t_input = {}
                if not isinstance(t_input, dict):
                    t_input = {}

                valid_tools = {t["name"] for t in CHAT_TOOLS}
                if t_name not in valid_tools:
                    print(f"[TOOL-OFFLINE] Unknown tool: {t_name}")
                    messages.append({"role": "tool", "content": json.dumps({"error": f"Unknown tool: {t_name}"})})
                    continue

                # Loop guard: if the same tool has already been called 2+ times in this
                # single user turn, the model is stuck in a repeat loop (observed in
                # results.txt: 5× get_navigation_targets for 'helicopter landing pad').
                # Stop executing, inject a directive, and force a final text answer.
                prior_calls = sum(
                    1 for tr in tool_results_for_display
                    if isinstance(tr, dict) and tr.get("tool") == t_name
                )
                if prior_calls >= 2:
                    print(f"[TOOL-OFFLINE-LOOP] '{t_name}' already called {prior_calls}x this turn — forcing final answer")
                    messages.append({"role": "tool", "content": json.dumps({
                        "error": f"Tool '{t_name}' already called {prior_calls} times. Use previous results."
                    })})
                    messages.append({"role": "user", "content": (
                        f"[SYSTEM DIRECTIVE] You have already called '{t_name}' multiple times. "
                        f"Do NOT call any more tools. Write a final plain-text answer to the "
                        f"patient using the information you already have. If the requested item "
                        f"wasn't found, say so and suggest asking at reception."
                    )})
                    # Force ONE final text-only call and return — prevents the
                    # model from calling the tool again in a subsequent iteration.
                    _final = call_ollama(system_prompt, messages, max_tokens=400, num_ctx=loop_num_ctx)
                    if isinstance(_final, dict):
                        _final = _final.get("text", "")
                    return _clean_llm_output(_final, lang=lang) or "Done.", tool_results_for_display

                print(f"[TOOL-OFFLINE] {t_name}({t_input})")
                tool_result = execute_tool(t_name, t_input, user_id, user_name, role)
                tool_results_for_display.append({"tool": t_name, "result": tool_result})
                messages.append({"role": "tool", "content": json.dumps(tool_result)})

                # Doctor list: pre-build formatted answer so qwen never echoes key names.
                if t_name == "get_doctors" and not tool_result.get("error"):
                    doc_list = tool_result.get("doctors", [])
                    if doc_list:
                        if lang == "ar":
                            _items = "، ".join(
                                f"د. {d['name']} ({d['specialty']})" for d in doc_list
                            )
                            _formatted = (
                                f"الأطباء المتاحون: {_items}. من تفضل؟"
                                if len(doc_list) > 1
                                else f"الطبيب المتاح: {_items}."
                            )
                        else:
                            _items = " | ".join(
                                f"Dr. {d['name']} ({d['specialty']})" for d in doc_list
                            )
                            _formatted = (
                                f"Available doctors: {_items}. Who would you prefer?"
                                if len(doc_list) > 1
                                else f"The available doctor is {_items}."
                            )
                        messages.append({
                            "role": "user",
                            "content": (
                                f"[SYSTEM DIRECTIVE] Doctor data loaded. Present this to the "
                                f"patient in their language. If the patient described symptoms, "
                                f"pick ONE doctor and briefly explain why they fit. "
                                f"Otherwise state exactly: {_formatted}"
                            )
                        })

                # Navigation: pre-compute matched location so model doesn't guess.
                elif t_name == "get_navigation_targets" and not tool_result.get("error"):
                    _nav_directive = _build_nav_directive(tool_result, last_user_msg)
                    messages.append({"role": "user", "content": _nav_directive})

                # Booking/cancellation error: block hallucinated success and block substitute booking.
                elif t_name == "book_appointment" and tool_result.get("error"):
                    messages.append({
                        "role": "user",
                        "content": (
                            f"[SYSTEM DIRECTIVE] The book_appointment tool returned this error: "
                            f"\"{tool_result['error']}\". "
                            f"You MUST tell the patient the booking FAILED and explain exactly why. "
                            f"Do NOT say the appointment was booked. "
                            f"Do NOT automatically try a different doctor or a different time — "
                            f"wait for the patient to tell you what they want to do next."
                        )
                    })
                elif t_name == "cancel_appointment" and tool_result.get("error"):
                    messages.append({
                        "role": "user",
                        "content": (
                            f"[SYSTEM DIRECTIVE] The cancel_appointment tool returned this error: "
                            f"\"{tool_result['error']}\". "
                            f"You MUST tell the patient the cancellation FAILED and explain why. "
                            f"Do NOT say the appointment was cancelled."
                        )
                    })
            continue

        # Text response with no tool calls — final answer
        return (_clean_llm_output(text, lang=lang) or "Done."), tool_results_for_display

    return "I processed your request.", tool_results_for_display


# ===============================================================
# SHARED AGENTIC LOOP (used by both chat and voice endpoints)
# ===============================================================
def run_agentic_loop(user_text, user_id, user_name, role, lang="en",
                     history=None, voice_mode=False,
                     sentiment=None, ner_entities=None, memory_ctx=""):
    """
    Run Claude with tool use. Returns (reply_text, tool_results_list).
    voice_mode=True: shorter prompt, suitable for text-to-speech.
    """
    patient_ctx = get_patient_context(user_id) if role == 'patient' else ""

    # Multilingual NLU: support Arabic dialects + auto-detect
    if lang == "ar":
        lang_note = (
            "Respond in Arabic. Accept Egyptian, Gulf, Levantine, or Modern Standard Arabic dialects. "
            "Always reply in the same dialect the patient used. Keep response under 60 words. "
            "NEVER use emojis, pictographs, or symbols (🤖, ❤️, 👋, etc.) — they break Pepper's TTS "
            "and crash the tablet's old WebKit. Plain Arabic + Latin letters only."
        ) if not voice_mode else (
            "Reply in Arabic in ONE short spoken sentence (max 20 words). Match the patient's "
            "Arabic dialect. NEVER use emojis, pictographs, or any symbol that isn't an Arabic "
            "letter, an Arabic digit, a Latin letter for proper names, or basic punctuation "
            "(؟ ، . ! ' \"). Emojis crash Pepper's tablet UI — ZERO emojis allowed. "
            "Tool calls do not count toward the word limit — call tools first, then speak a short reply."
        )
    else:
        lang_note = (
            "Respond in English (under 80 words). NEVER use emojis or pictographs."
        ) if not voice_mode else (
            "Reply in English in ONE short spoken sentence (max 20 words) suitable for text-to-speech. "
            "NEVER use emojis, pictographs, or any non-letter symbol — they break the tablet UI. "
            "Tool calls do not count toward the word limit — call tools first, then speak a short reply."
        )

    today = datetime.now().strftime('%Y-%m-%d')
    weekday = datetime.now().strftime('%A')
    current_time = datetime.now().strftime('%H:%M')

    system_prompt = (
        f"You are Pepper, a friendly medical robot assistant at Andalusia Hospital.\n"
        f"Patient name: {user_name}.\n"
        f"Today: {today} ({weekday}). Current time: {current_time}.\n"
        f"\n{lang_note}\n"
        f"\nCRITICAL RULES:\n"
        f"1. You MUST call the appropriate tool for ANY action. NEVER pretend you performed an action without calling the tool.\n"
        f"2. To book an appointment: call book_appointment. To check a schedule: call get_doctor_schedule. To list doctors: call get_doctors.\n"
        f"3. NEVER say 'I have booked' or 'appointment confirmed' unless you received a successful tool result.\n"
        f"4. When the user wants to book, first call get_doctors or get_doctor_schedule to verify the doctor exists, then call book_appointment.\n"
        f"5. Use doctor names WITHOUT 'Dr.' prefix in tool calls (e.g. 'Islam Mohamed' not 'Dr. Islam Mohamed').\n"
        f"6. Format dates as YYYY-MM-DD and times as HH:MM (24-hour).\n"
        f"7. Write plain spoken sentences. NO markdown, NO asterisks, NO bullet points.\n"
        f"8. Be warm, empathetic, and concise.\n"
        f"9. If you are unsure, ask the patient to clarify.\n"
        f"10. NEVER say 'I will call', 'I'll call', 'let me call', 'can you call', 'let's check with', "
        f"'we need to call', or describe any tool / parameter / function in words. "
        f"Just call the tool directly. The patient must never see internal function or parameter names.\n"
        f"11. NEVER guess a doctor's department from their name. If the user names a doctor, "
        f"call get_doctors WITH NO department filter, then find the matching doctor by name. "
        f"Only pass a department to get_doctors when the user explicitly names a department "
        f"(e.g. 'find a cardiologist' -> department='Cardiology'). A doctor's name is NOT evidence of their specialty.\n"
        f"12. When the user asks to book with a specific doctor by name, your FIRST tool call must be "
        f"get_doctors() with no arguments (or get_doctor_schedule(doctor_name=...)). Do NOT call "
        f"get_doctors with a guessed department.\n"
        f"13. For ANY question about hospital navigation, room or facility location — including "
        f"pharmacy, laboratory, lab, emergency room, ICU, maternity ward, cafeteria, café, "
        f"restroom, bathroom, toilet, reception, blood bank, operating theatres, theatres, "
        f"billing, radiology, X-ray, elevators, lifts, waiting area, any specific doctor's "
        f"office, 'where is X', 'where can you take / guide me', 'how do I get to X', 'take me "
        f"to X', 'lead me to X', or 'direct me to X' — your FIRST action MUST be "
        f"get_navigation_targets. ALWAYS call this tool even when you think you know the answer. "
        f"Never answer location questions from memory. Never invent room numbers or floors.\n"
        f"14. Tool results are PRIVATE context for YOU. NEVER say phrases like 'Thank you for "
        f"providing the JSON data', 'Based on this information', 'the dataset', 'the data you "
        f"provided', or similar. The patient does not see any JSON. Speak as if you already know "
        f"the answer, in plain natural language.\n"
        f"15. Take the patient's time and date LITERALLY. If they say '03:00' that means 3 AM — do "
        f"NOT silently change it to 15:00 (3 PM). If a time seems unlikely, ask the patient to "
        f"confirm rather than reinterpreting it.\n"
        f"16. For ANY question about the patient's OWN medical record — age, date of birth, blood "
        f"type, allergies, medications, prescriptions, medical history, chronic conditions, past "
        f"visits, 'what do you know about me', 'are my meds safe', 'can I continue my "
        f"prescriptions', or similar — your FIRST tool call MUST be get_patient_profile. "
        f"Never reply 'I don't have that information' without calling get_patient_profile first. "
        f"NEVER use placeholder text like '[list of medications]' — if the profile has no "
        f"medications on file, say so explicitly.\n"
        f"17. Booking intent is triggered by ANY of: 'book', 'schedule', 'reserve', 'make an "
        f"appointment', 'احجز', 'موعد' — regardless of whether the user wrote 'Dr.' or 'Doctor' or "
        f"no title at all, and regardless of the language. Arabic+English mixed names (e.g. "
        f"'د. Ahmed Fouad') are valid doctor names — strip the honorific and pass the rest.\n"
        f"18. After you see a tool result, reply in PLAIN natural language about what the patient "
        f"asked. Do not mention 'JSON', 'data', 'provided', 'dataset', 'list', or 'entries'. "
        f"Do not summarize the raw data structure. Answer the patient's actual question only.\n"
        f"19. When the patient asks you to RECOMMEND a doctor (e.g. 'recommend a doctor', "
        f"'suggest a specialist', 'who should I see', 'can you recommend a dermatologist'): "
        f"you MUST call get_doctors FIRST. If a specialty is implied by the request or by the "
        f"patient's medical profile, pass it as the department. Then pick a doctor FROM THE "
        f"RETURNED LIST by their real specialty — NEVER invent a name or a specialty. If the "
        f"returned list is empty, say so and offer a related specialty.\n"
        f"20. NEVER claim a doctor belongs to a specialty that does not match their 'specialty' "
        f"field in the tool result. The tool result is authoritative. If you have not called "
        f"get_doctors or get_doctor_schedule in the current turn, you do NOT know any doctor's "
        f"specialty — call the tool instead of guessing.\n"
        f"21. HARD RULE — NEVER invent doctor names. A name must come from a tool result in the "
        f"current turn. Do NOT pull names from memory, from the patient's history, or from "
        f"common Arabic/Egyptian name patterns. If you list multiple doctors, every name must "
        f"appear verbatim in the most recent get_doctors or get_navigation_targets result.\n"
        f"22. HARD RULE — If get_patient_profile returns an empty or missing field (allergies, "
        f"medications, medical history, blood type, age, DOB), say 'I don't have that on file' "
        f"and offer to update it. NEVER fabricate a value. NEVER say 'you are already taking X' "
        f"or 'your medications include X' unless X is literally in the tool result.\n"
        f"23. For navigation/location questions, use get_navigation_targets. Answer from the "
        f"'facilities' list for pharmacy/lab/ICU/ER/bathroom/reception/cafeteria questions, and "
        f"from 'doctor_offices' ONLY when the patient named a doctor. If a facility is NOT in "
        f"the result, say 'I'm not sure — please ask at reception' instead of guessing a room.\n"
        f"24. The current clock time is in the system header above. If asked 'what time is it', "
        f"use that value exactly. Do NOT invent a time.\n"
        f"25. NEVER say 'your appointment has been booked' or 'booking confirmed' unless the "
        f"MOST RECENT tool result in this turn was book_appointment with success=true. If you "
        f"only called get_doctor_schedule or get_doctors, you have NOT booked anything — "
        f"propose the time and ask the patient to confirm before calling book_appointment.\n"
        f"26. LANGUAGE PURITY — if replying in English, use only Latin script. If replying in "
        f"Arabic, use only Arabic script + Latin for doctor/place names. NEVER mix Chinese, "
        f"Japanese, Korean, Hebrew, or Cyrillic characters into the reply.\n"
        f"27. RECOMMEND WITH NO DELAY — when the patient says 'recommend a [specialty]' or names "
        f"ANY specialty (e.g. 'general practitioner', 'cardiologist', 'dermatologist', 'GP'), "
        f"do NOT ask for clarification. Immediately call get_doctors with that specialty as the "
        f"department, then pick the best match from the returned list and recommend them by name. "
        f"Only ask for clarification when the patient says only 'recommend a doctor' with NO "
        f"specialty AND their profile has no relevant conditions.\n"
        f"28. PROACTIVE RECOMMENDATION — when the patient asks 'recommend a doctor' without naming "
        f"a specialty, look at their medical profile (injected above) for chronic conditions, "
        f"then call get_doctors with the most relevant specialty (e.g. Hashimoto's → "
        f"'Endocrinology', depression → 'Psychiatry', IBS → 'Gastroenterology'). "
        f"Do NOT ask what specialty unless the profile is completely empty.\n"
        f"29. DOCTOR LIST FORMATTING — when get_doctors returns 'reply_ar' and "
        f"'reply_en' fields: use 'reply_ar' if replying in Arabic, use "
        f"'reply_en' if replying in English. NEVER join names yourself — doing so "
        f"produces runs like 'Sameh RadwanNeveen Darwish' with no spaces. NEVER reply in "
        f"Arabic when the patient spoke English, and vice versa.\n"
        f"30. DIALECT ARABIC — phrases like 'رشح لي'، 'ارشحلي'، 'وصيلي'، 'حسب حالتي' all mean "
        f"'recommend to me'. Treat them exactly like 'recommend a doctor' and call get_doctors "
        f"immediately using the patient's profile to choose the best specialty.\n"
        f"31. BOOKING FAILURE — if book_appointment returns an error for ANY reason (wrong "
        f"day, slot taken, past date, etc.), tell the patient exactly what failed and STOP. "
        f"Do NOT automatically try a different doctor or a different time slot. "
        f"Do NOT call book_appointment again until the patient explicitly tells you what "
        f"they want to change.\n"
        f"32. LISTING APPOINTMENTS — if the patient says anything like 'what are my "
        f"appointments', 'show me my appointments', 'do I have any appointments', "
        f"ALWAYS call get_my_appointments. This is NEVER a booking confirmation — "
        f"treat it as a fresh list request regardless of any prior booking context.\n"
        f"33. CANCEL WITHOUT ID — if the patient asks to cancel an appointment without "
        f"giving a numeric appointment ID, call get_my_appointments FIRST to find their "
        f"appointments, then identify the matching one by doctor/date/time from the "
        f"patient's description, then call cancel_appointment with that ID. "
        f"NEVER ask the patient for an appointment ID — they will not know it.\n"
        f"34. PAST DATE GUARD — before calling book_appointment, check that the requested "
        f"date is on or after today ({today}). If the date is in the past, tell the patient "
        f"that date has already passed and ask them to choose a future date. "
        f"Do NOT call book_appointment with a past date.\n"
        f"35. CANCEL HONESTY — NEVER say 'cancelled', 'deleted', 'removed', or any word "
        f"implying a cancellation was performed unless the most recent tool result is "
        f"cancel_appointment with success=true. If you only called get_doctor_schedule "
        f"or get_my_appointments, you have NOT cancelled anything.\n"
        f"36. SYMPTOM ROUTING — when a patient describes symptoms and asks which doctor "
        f"or department to see, identify the correct specialty (chest pain→Cardiology, "
        f"knee pain→Orthopedics, headache+dizziness→Neurology, skin issue→Dermatology, "
        f"etc.) then call get_doctors with that specialty. NEVER name a specific doctor "
        f"before you have called get_doctors and seen the result in this turn.\n"
        f"37. POST-CANCEL REFRESH — After any cancellation (confirmed or failed), if the "
        f"patient asks what appointments they have, what is left, or anything about their "
        f"current schedule, ALWAYS call get_my_appointments to get the live DB state. "
        f"Do NOT answer from conversation context — the list changed after the cancel.\n"
        f"38. WITNESSED EMERGENCY — If the patient describes ANYONE ELSE (husband, wife, "
        f"child, friend, stranger) having a medical emergency — seizure, unconscious, "
        f"not breathing, collapsing, stroke — respond with the same urgency as a first-person "
        f"emergency. You MUST use the words 'emergency' and 'immediately'. Direct them to the "
        f"Emergency Department on the Ground Floor. Do NOT book appointments or call any tool.\n"
        f"39. PREGNANCY + MEDICATIONS — If a patient mentions they are pregnant (or just found "
        f"out) and asks whether their medications or prescriptions are safe, you MUST: "
        f"(a) call get_patient_profile first, (b) NEVER use placeholder text like "
        f"'[list of medications]' — state what the profile actually shows, "
        f"(c) call get_doctors with department='Obstetrics & Gynecology' to recommend an "
        f"OB/GYN doctor by real name from the tool result.\n"
        f"40. MULTI-QUESTION TURNS — When the patient asks two or more distinct questions in "
        f"one message (e.g. blood type AND pharmacy location AND appointments), call ALL "
        f"required tools in sequence within the same turn. Do not skip any tool or answer "
        f"any sub-question from memory when a live tool answer is available.\n"
        f"41. NO STALE RECALL — Conversation history is NOT a source of truth. Even if you "
        f"saw a list of appointments, a profile, or a schedule earlier in the conversation, "
        f"you MUST re-call the tool whenever the patient asks again. State changes between "
        f"turns (cancellations, new bookings, profile edits). Specifically: every 'show / "
        f"list / what are / do I have' question about MY appointments, MY profile, MY "
        f"medications, MY blood type, OR MY anything personal triggers a fresh tool call — "
        f"NO EXCEPTIONS. Answering 'as you mentioned earlier' is a bug.\n"
        f"42. LANGUAGE-SWITCH RECALL — When the patient switches language (English↔Arabic) "
        f"and asks the SAME kind of question they asked before (e.g. 'show my appointments' "
        f"in EN after asking the same in AR), still call the tool. Language switch resets "
        f"context — never assume the prior tool result still applies."
    )

    # ---- FAISS RAG: inject relevant hospital knowledge ----
    if rag_engine and rag_engine.is_ready():
        rag_context = rag_engine.retrieve_context_string(user_text, lang=lang, k=3)
        if rag_context:
            if lang == "ar":
                system_prompt += "\n\nمعلومات مرجعية من قاعدة بيانات المستشفى:\n" + rag_context
            else:
                system_prompt += "\n\nRelevant hospital knowledge (use to ground your answer):\n" + rag_context

    if patient_ctx:
        system_prompt += f"\n\nPatient medical profile:\n{patient_ctx}"

    # Inject conversational memory
    if memory_ctx:
        system_prompt += f"\n\n{memory_ctx}"

    # Inject real-time sentiment context
    if sentiment and sentiment.get("sentiment") not in ("calm", ""):
        system_prompt += (
            f"\n\nSentiment alert: Patient appears {sentiment['sentiment']} "
            f"(score={sentiment.get('score',0):.1f}). "
            f"Respond with extra care and empathy."
        )
        if sentiment.get("alert"):
            system_prompt += " Consider recommending they speak to a nurse."

    # Inject NER medical entities
    if ner_entities:
        syms = ner_entities.get("symptoms", [])
        meds = ner_entities.get("medications", [])
        if syms:
            system_prompt += f"\n\nDetected symptoms in message: {', '.join(syms)}."
        if meds:
            system_prompt += f" Mentioned medications: {', '.join(meds)}."

    # Build message list
    claude_messages = []
    for msg in (history or []):
        r = msg.get("role", "user")
        if r == "model": r = "assistant"
        t = msg.get("parts", [{}])[0].get("text", "") if msg.get("parts") else msg.get("content", "")
        if t: claude_messages.append({"role": r, "content": t})
    claude_messages.append({"role": "user", "content": user_text})

    tool_results_for_display = []

    # ---- OFFLINE MODE: Ollama with text-based tool calling ----
    if OFFLINE_MODE:
        return _run_agentic_loop_offline(
            system_prompt, claude_messages, user_id, user_name, role,
            voice_mode, tool_results_for_display, lang=lang)

    # ---- ONLINE MODE: Claude with native tool use ----
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    max_iterations = 5

    def _call_claude_with_retry(payload):
        """POST to Anthropic with retry on transient errors (529 overloaded,
        429 rate-limit, 5xx, read timeout). Backoff: 1s, 2s, 4s.
        Raises RuntimeError on non-retryable error or after retries exhausted.
        """
        last_err = "no response"
        for attempt in range(4):
            try:
                resp = requests.post("https://api.anthropic.com/v1/messages",
                                     headers=headers, json=payload, timeout=45)
                # Retry on transient HTTP statuses
                if resp.status_code in (429, 500, 502, 503, 504, 529):
                    last_err = f"HTTP {resp.status_code}"
                    print(f"[CLAUDE-RETRY] {last_err} on attempt {attempt + 1}/4")
                    if attempt < 3:
                        time.sleep(2 ** attempt)
                        continue
                    raise RuntimeError(f"Claude API {last_err} after 4 attempts")
                rj = resp.json()
                if "error" in rj:
                    err_type = rj["error"].get("type", "")
                    err_msg  = rj["error"].get("message", "API error")
                    # Application-level transient errors
                    if err_type in ("overloaded_error", "rate_limit_error", "api_error"):
                        last_err = f"{err_type}: {err_msg}"
                        print(f"[CLAUDE-RETRY] {last_err} on attempt {attempt + 1}/4")
                        if attempt < 3:
                            time.sleep(2 ** attempt)
                            continue
                    raise RuntimeError(err_msg)
                return rj
            except requests.exceptions.Timeout:
                last_err = "read timeout (>45s)"
                print(f"[CLAUDE-RETRY] {last_err} on attempt {attempt + 1}/4")
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"Claude API {last_err}")
            except requests.exceptions.ConnectionError as ce:
                last_err = f"connection error: {ce}"
                print(f"[CLAUDE-RETRY] {last_err} on attempt {attempt + 1}/4")
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(last_err)
        raise RuntimeError(f"Claude API failed: {last_err}")

    for _ in range(max_iterations):
        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 512 if voice_mode else 1024,
            "system": system_prompt,
            "tools": CHAT_TOOLS,
            "messages": claude_messages
        }
        resp_json = _call_claude_with_retry(payload)

        stop_reason = resp_json.get("stop_reason", "")
        content     = resp_json.get("content", [])
        text_parts  = [b["text"] for b in content if b.get("type") == "text"]
        tool_blocks = [b for b in content if b.get("type") == "tool_use"]

        if stop_reason == "tool_use" and tool_blocks:
            claude_messages.append({"role": "assistant", "content": content})
            tool_result_contents = []
            for tb in tool_blocks:
                t_name  = tb["name"]
                t_input = tb.get("input", {})
                print(f"[TOOL] {t_name}({t_input})")

                # Loop guard: same tool called 3+ times in one turn → break the
                # loop and force a final answer (mirrors the offline loop guard).
                prior_calls = sum(
                    1 for tr in tool_results_for_display
                    if isinstance(tr, dict) and tr.get("tool") == t_name
                )
                if prior_calls >= 2:
                    print(f"[TOOL-ONLINE-LOOP] '{t_name}' already called {prior_calls}x — forcing final answer")
                    tool_result_contents.append({
                        "type": "tool_result",
                        "tool_use_id": tb["id"],
                        "content": json.dumps({
                            "error": (
                                f"Tool '{t_name}' already called {prior_calls} times this turn. "
                                f"Use the results you already have. Do NOT call any more tools — "
                                f"write a plain-text final answer to the patient. "
                                f"If the requested item was not found, say so and suggest asking at reception."
                            )
                        })
                    })
                    continue

                result = execute_tool(t_name, t_input, user_id, user_name, role)
                tool_results_for_display.append({"tool": t_name, "result": result})
                content_str = json.dumps(result)
                # If booking/cancellation failed, prepend a hard directive so
                # Claude cannot hallucinate a success message
                if t_name in ("book_appointment", "cancel_appointment") and result.get("error"):
                    content_str = (
                        f"ERROR: The action failed — {result['error']}. "
                        f"You MUST tell the patient the action failed and why. "
                        f"Do NOT say the appointment was booked or cancelled.\n" + content_str
                    )
                tool_result_contents.append({
                    "type": "tool_result",
                    "tool_use_id": tb["id"],
                    "content": content_str
                })
            claude_messages.append({"role": "user", "content": tool_result_contents})
            continue

        final_text = " ".join(text_parts).strip() or "Done."
        # Apply the same output-cleaning pipeline as the offline path:
        # strips placeholder text like [list of medications], markdown markers,
        # tool-name leakage, and dataset-narration sentences.
        final_text = _clean_llm_output(final_text, lang=lang)
        return final_text, tool_results_for_display

    return "I processed your request.", tool_results_for_display


# --- CHAT AI (with tool use) ---
@app.route("/api/chat_ai", methods=["POST"])
def api_chat_ai():
    data      = request.get_json()
    user_text = data.get("message", "")
    # Server-side cap: prevent context-window overflow for long-running sessions
    history   = data.get("history", [])[-20:]
    lang      = data.get("lang", "en")

    # Resolve identity: Flask session only (never trust payload for auth)
    user_id   = session.get('user_id')
    user_name = session.get('user_name', 'Guest')
    role      = session.get('role', 'guest')

    try:
        # --- Safety pre-check: short-circuit known medical emergencies ---
        # The LLM is unreliable for life-threatening red flags (anaphylaxis,
        # stroke, overdose). Give a hard-coded triage reply and skip the loop.
        emergency_reply, emergency_label = _detect_medical_emergency(user_text, lang=lang)
        if emergency_reply:
            _slog("chat_message", patient_name=user_name, patient_id=user_id,
                  success=True, lang=lang,
                  user_said=user_text[:200], ai_replied=emergency_reply[:300],
                  emergency=emergency_label, tools_used=[])
            return jsonify({
                "success": True,
                "answer": emergency_reply,
                "tool_results": [],
                "sentiment": {"sentiment": "urgent", "label": emergency_label},
                "ner": [],
                "consensus": None,
                "emergency": emergency_label,
            })

        # --- Run AI enrichment in parallel context ---
        # Each stage is independently guarded — a crash in sentiment must not
        # kill NER, and a crash in any enrichment must not kill the whole turn.

        # 1. Sentiment analysis
        try:
            sentiment = sentiment_analyzer.analyze(user_text, lang)
            if sentiment.get("alert"):
                print(f"[ALERT] Distress detected for {user_name}: {sentiment.get('reason')}")
        except Exception as _e:
            print(f"[ENRICH] sentiment failed: {_e}")
            sentiment = {"sentiment": "neutral", "label": "neutral", "score": 0.0}

        # 2. Medical NER — extract entities from message
        try:
            ner_entities = medical_ner.extract(user_text)
        except Exception as _e:
            print(f"[ENRICH] medical_ner failed: {_e}")
            ner_entities = {"symptoms": [], "medications": []}

        # 3. Load conversational memory
        try:
            mem = ConversationMemory(db, PatientMemory)
            memory_ctx = mem.get_context(user_id) if user_id else ""
        except Exception as _e:
            print(f"[ENRICH] conversation_memory failed: {_e}")
            memory_ctx = ""

        # 4. Multi-agent consensus for high-stakes messages
        consensus = None
        if multi_agent_system.should_activate(user_text):
            try:
                patient_meds = []
                if user_id:
                    pt = Patient.query.get(user_id)
                    if pt and pt.current_medications:
                        patient_meds = [m.strip() for m in pt.current_medications.split(",") if m.strip()]
                dc = DrugChecker(db, Medication, DrugInteraction)
                consensus = multi_agent_system.consult(
                    patient_context=memory_ctx,
                    user_message=user_text,
                    drug_checker=dc,
                    medications=patient_meds,
                )
            except Exception as _e:
                print(f"[MULTI-AGENT] Error: {_e}")

        final_text, tool_results = run_agentic_loop(
            user_text, user_id, user_name, role, lang=lang,
            history=history, voice_mode=False,
            sentiment=sentiment, ner_entities=ner_entities, memory_ctx=memory_ctx
        )

        # Guard against fabricated booking confirmations: if the reply claims
        # a successful booking but book_appointment wasn't actually invoked
        # with success, rewrite the reply. qwen sometimes hallucinates
        # "تم حجز موعد" / "your appointment has been booked" after only a
        # schedule lookup.
        final_text = _strip_fake_booking_claim(final_text, tool_results, lang=lang)
        # Similarly guard against false cancellation claims.
        final_text = _strip_fake_cancel_claim(final_text, tool_results, lang=lang)

        # If multi-agent produced a richer recommendation, prefer it —
        # but only when the agentic loop took no side-effecting actions,
        # otherwise the patient needs to see what tools actually did.
        if consensus and consensus.get("final_recommendation") and not tool_results:
            final_text = consensus["final_recommendation"]

        _slog("chat_message", patient_name=user_name, patient_id=user_id,
              success=True, lang=lang,
              user_said=user_text[:200],
              ai_replied=final_text[:300],
              sentiment=sentiment.get("label", "neutral") if sentiment else "neutral",
              tools_used=[r.get("tool") for r in tool_results if isinstance(r, dict) and r.get("tool")])
        return jsonify({
            "success": True,
            "answer": final_text,
            "tool_results": tool_results,
            "sentiment": sentiment,
            "ner": ner_entities,
            "consensus": consensus,
        })
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[CHAT ERROR] {type(e).__name__}: {e}\n{tb}")
        try:
            _slog("chat_message", patient_name=user_name, patient_id=user_id,
                  success=False, user_said=user_text[:200],
                  error=f"{type(e).__name__}: {e}",
                  traceback=tb[-2000:])
        except Exception:
            pass
        # Surface a hint about what failed so the patient/test can distinguish
        # transient overload from a real bug, without leaking internals.
        msg_low = str(e).lower()
        if any(s in msg_low for s in ("overload", "rate", "529", "429", "5xx", "timeout")):
            user_msg = ("I'm a little overloaded right now — please try again "
                        "in a few seconds." if lang != "ar"
                        else "أنا مشغول قليلاً الآن — حاول مرة أخرى بعد لحظات.")
        else:
            user_msg = ("I am having trouble thinking right now. Please try again."
                        if lang != "ar"
                        else "أواجه مشكلة في التفكير الآن. حاول مرة أخرى.")
        return jsonify({"success": False, "answer": user_msg})
    
# --- 4. SIGNUP ---
@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.get_json() or {}
    user_id = data.get("id")
    name = data.get("name")
    password = data.get("password")
    role = data.get("role")

    if not user_id or not name or not password or role not in ('patient', 'staff'):
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    hashed_pw = generate_password_hash(password)
    if role == 'patient':
        if Patient.query.get(user_id): return jsonify({"success": False, "error": "ID Taken"})
        case_num = data.get("case_number")
        db.session.add(Patient(id=user_id, name=name, password=hashed_pw, case_number=case_num))
    elif role == 'staff':
        if Staff.query.get(user_id): return jsonify({"success": False, "error": "ID Taken"})
        db.session.add(Staff(id=user_id, name=name, password=hashed_pw, role="Staff"))
    else:
        return jsonify({"success": False, "error": "Invalid Role"})
        
    db.session.commit()
    _slog("patient_signup", patient_name=name, patient_id=user_id,
          success=True, role=role)
    return jsonify({"success": True})

# --- 5. TRIAGE ASSESSMENT ---
@app.route("/api/triage_assess", methods=["POST"])
def api_triage_assess():
    """
    AI-powered triage assessment using Manchester Triage Scale logic.
    Accepts: { chiefComplaint, painScore, symptoms[] }
    Returns: { success, level (1-4), label, color, recommendation, department }
    """
    data = request.get_json(force=True) or {}
    try:
        pain = int(data.get("painScore") or 0)
    except (ValueError, TypeError):
        pain = 0
    symptoms = data.get("symptoms", [])
    complaint = str(data.get("chiefComplaint", "")).lower()
    lang = data.get("lang", "en")

    # ----- Danger sign classifiers -----
    L1_SIGNS = {
        "Cannot speak in full sentences",
        "Lips or fingertips turning blue",
        "Face drooping on one side",
        "Arm weakness / slurred speech",
        "Pain spreads to arm or jaw",
        "Deformity / bone visible",
        "Feeling faint / nearly collapsed",
    }
    L2_SIGNS = {
        "Chest tightens/squeezes",
        "Sweating heavily",
        "Using neck muscles to breathe",
        "Sudden thunderclap headache",
        "Cannot move the injured area",
        "Neck stiffness / cannot touch chin to chest",
        "Rash spreading rapidly",
        "Confused / unusual behavior",
        "Severe open wound",
        "Chest tightness",
        "Sudden deterioration",
    }

    symptom_set = set(symptoms)
    has_l1 = bool(symptom_set & L1_SIGNS)
    has_l2 = bool(symptom_set & L2_SIGNS)

    # ----- Triage level determination -----
    if has_l1 or pain >= 9:
        level, label, color = 1, "IMMEDIATE", "Red"
        rec_en = "Life-threatening emergency. Stay calm — staff have been alerted and are coming to you immediately."
        rec_ar = "حالة طارئة مهددة للحياة. ابقَ هادئاً — تم إبلاغ الطاقم الطبي وهم في طريقهم إليك."
        department = "Emergency Medicine"
    elif has_l2 or pain >= 7 or (complaint in ("heart", "breathing") and pain >= 5):
        level, label, color = 2, "VERY URGENT", "Orange"
        rec_en = "Your condition is serious. Please go directly to Emergency Reception — a nurse will assess you within 10 minutes."
        rec_ar = "حالتك خطيرة. يرجى التوجه فوراً إلى استقبال الطوارئ — سيتم تقييمك خلال 10 دقائق."
        department = "Emergency Medicine"
    elif pain >= 5 or len(symptoms) >= 2:
        level, label, color = 3, "URGENT", "Yellow"
        dept_map = {
            "heart": "Cardiology",
            "breathing": "Pulmonology",
            "neuro": "Neurology",
            "pain": "Orthopedics",
            "fever": "Internal Medicine",
            "other": "Internal Medicine",
        }
        department = dept_map.get(complaint, "Internal Medicine")
        rec_en = "Your symptoms need medical attention today. Please book an appointment with {dept} or speak to a nurse at reception.".format(dept=department)
        rec_ar = "تحتاج أعراضك إلى رعاية طبية اليوم. يرجى حجز موعد أو التحدث إلى ممرضة في الاستقبال."
    else:
        level, label, color = 4, "STANDARD", "Green"
        dept_map = {
            "heart": "Cardiology",
            "breathing": "Pulmonology",
            "neuro": "Neurology",
            "pain": "Orthopedics",
            "fever": "Internal Medicine",
            "other": "Internal Medicine",
        }
        department = dept_map.get(complaint, "Internal Medicine")
        rec_en = "Your condition is non-urgent. You may book a routine appointment with {dept} or check our health tips for self-care advice.".format(dept=department)
        rec_ar = "حالتك غير عاجلة. يمكنك حجز موعد روتيني أو الاطلاع على نصائحنا الصحية."

    recommendation = rec_ar if lang == "ar" else rec_en

    # ----- Use Claude to enrich the recommendation -----
    patient_ctx = get_patient_context(session.get('user_id')) if session.get('role') == 'patient' else ""
    try:
        ai_prompt = (
            "A patient at Andalusia Hospital has the following triage data:\n"
            "Chief complaint: {complaint}\nPain score: {pain}/10\n"
            "Reported symptoms: {syms}\n"
            "Initial triage level: {level} ({label})\n\n"
        ).format(
            complaint=data.get("chiefComplaint", ""),
            pain=pain,
            syms=", ".join(symptoms) if symptoms else "none",
            level=level,
            label=label,
        )
        if patient_ctx:
            ai_prompt += "Patient medical profile:\n" + patient_ctx + "\n\n"
            ai_prompt += (
                "In 1-2 short sentences ({lang}), give a warm, reassuring recommendation. "
                "IMPORTANT: If the patient has allergies or medications that interact with likely "
                "treatments for this complaint, mention them as a safety warning. "
                "Do NOT change the triage level. Keep it under 40 words."
            ).format(lang="Arabic" if lang == "ar" else "English")
        else:
            ai_prompt += (
                "In 1-2 short sentences ({lang}), give a warm, reassuring recommendation. "
                "Do NOT change the triage level. Keep it under 30 words."
            ).format(lang="Arabic" if lang == "ar" else "English")

        ai_rec = interact_with_gemini(ai_prompt, [], "", lang=lang, patient_context=patient_ctx)
        if ai_rec and len(ai_rec) > 5:
            recommendation = ai_rec
    except Exception:
        pass  # fall back to rule-based recommendation above

    _slog("triage_assessed",
          patient_name=session.get("user_name", "Guest"),
          patient_id=session.get("user_id"),
          success=True,
          complaint=complaint[:150], pain_score=pain,
          symptoms=symptoms, level=level, label=label,
          color=color, department=department)

    # Save to triage history
    try:
        th = TriageHistory(
            patient_id=session.get("user_id"),
            patient_name=session.get("user_name", "Guest"),
            chief_complaint=data.get("chiefComplaint", "")[:299],
            severity=level,
            severity_label=label,
            symptoms_json=json.dumps(symptoms),
            vitals_json=json.dumps({"pain_scale": pain}),
            ai_recommendation=recommendation,
            department_referred=department,
        )
        db.session.add(th)
        db.session.commit()
    except Exception:
        pass  # Never let history saving break the triage response

    return jsonify({
        "success": True,
        "level": level,
        "label": label,
        "color": color,
        "department": department,
        "recommendation": recommendation,
    })


# --- 6. TRIAGE PDF EXPORT ---
@app.route("/api/triage_export_pdf", methods=["POST"])
def api_triage_export_pdf():
    """Generate a PDF report of triage assessments sent from the staff dashboard."""
    try:
        from io import BytesIO
        from fpdf import FPDF
    except ImportError:
        return jsonify({"error": "fpdf2 not installed. Run: pip install fpdf2"}), 500

    data = request.get_json(force=True) or {}
    triages = data.get("triages", [])
    if not triages:
        return jsonify({"error": "No triage data provided"}), 400

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "Triage Assessment Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, "Andalusia Hospital - Generated: " + datetime.now().strftime("%Y-%m-%d %H:%M"), ln=True, align="C")
    pdf.ln(6)

    level_labels = {1: "IMMEDIATE (Red)", 2: "VERY URGENT (Orange)", 3: "URGENT (Yellow)", 4: "STANDARD (Green)"}

    for i, t in enumerate(reversed(triages)):
        lvl = t.get("level", 4)
        # Card header
        pdf.set_fill_color(200, 200, 200) if lvl > 2 else pdf.set_fill_color(255, 200, 200)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "#{} - {} - L{} {}".format(
            i + 1, t.get("patient", "Unknown"), lvl, level_labels.get(lvl, "")), ln=True, fill=True)

        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, "Chief Complaint: " + str(t.get("chiefComplaint", "")), ln=True)
        pdf.cell(0, 6, "Pain Score: {}/10".format(t.get("painScore", 0)), ln=True)

        symptoms = t.get("symptoms", [])
        if symptoms:
            pdf.cell(0, 6, "Danger Signs: " + ", ".join(symptoms), ln=True)

        pdf.cell(0, 6, "Recommendation: " + str(t.get("recommendation", "")), ln=True)
        pdf.cell(0, 6, "Time: " + str(t.get("time", "")), ln=True)
        pdf.ln(4)

    buf = BytesIO()
    pdf.output(buf)
    buf.seek(0)

    response = make_response(buf.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=triage_report.pdf"
    return response


# --- 7. LEGACY ROUTES (Doctors, Schedule, Departments) ---
@app.route("/api/doctors", methods=["GET"])
def api_get_doctors():
    return jsonify([{"id": d.id, "name": d.name, "specialty": d.specialty} for d in Doctor.query.all()])

@app.route("/api/departments", methods=["GET"])
def api_get_departments():
    depts = db.session.query(Doctor.specialty).distinct().all()
    return jsonify(departments=sorted([d[0] for d in depts if d[0]]))

@app.route("/api/doctors_by_department/<department_name>", methods=["GET"])
def api_get_doctors_by_department(department_name):
    doctors = Doctor.query.filter(Doctor.specialty == department_name).all()
    return jsonify(doctors=[{"id": d.id, "name": d.name} for d in doctors])

@app.route("/api/schedule/<int:doctor_id>", methods=["GET"])
def api_get_schedule(doctor_id):
    doctor = Doctor.query.get(doctor_id)
    if not doctor: return jsonify({"error": "Doctor not found"}), 404
    slots = Schedule.query.filter_by(doctor_id=doctor.id).all()
    days_map = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}
    formatted_schedule = []
    for s in slots:
        formatted_schedule.append({
            "day": days_map.get(s.day_of_week, "Unknown"),
            "start_time": s.start_time.strftime("%H:%M:%S"), 
            "end_time": s.end_time.strftime("%H:%M:%S")
        })
    return jsonify({"doctor": doctor.name, "schedule": formatted_schedule})

# ===============================
# NAVIGATION ROUTES
# ===============================

# Resolve path to navigation_targets.json:
# app.py is at: .../Pepper-Controller-main-2/pepper_ui/server/app/
# targets are at: .../Pepper-Controller-main-2/navigation/navigation_targets.json
_NAV_TARGETS_PATH = CURRENT_DIR.parent.parent.parent / "navigation" / "navigation_targets.json"

@app.route("/api/navigation_targets", methods=["GET"])
def api_navigation_targets():
    """
    Returns the list of navigation targets from navigation_targets.json.
    Each target contains: id, name, specialty, room_name, coordinates [x, y, theta].
    Consumed by guide.html to dynamically render navigation buttons.
    """
    try:
        with open(str(_NAV_TARGETS_PATH), "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data.get("targets", []))
    except FileNotFoundError:
        return jsonify({"error": "navigation_targets.json not found"}), 404
    except Exception as e:
        print(f"[NAV] Error serving navigation targets: {e}")
        return jsonify({"error": "Failed to load navigation targets"}), 500


# ===============================================================
# AI MODULE ENDPOINTS
# ===============================================================

# --- SENTIMENT ANALYSIS ---
@app.route("/api/sentiment", methods=["POST"])
def api_sentiment():
    data = request.get_json()
    text = data.get("text", "")
    lang = data.get("lang", "en")
    result = sentiment_analyzer.analyze(text, lang)
    # Auto-alert if distressed
    if result.get("alert") and session.get("user_name"):
        print(f"[ALERT] Patient '{session['user_name']}' distress detected: {result.get('reason')}")
    return jsonify(result)

# --- MEDICAL NER ---
@app.route("/api/ner", methods=["POST"])
def api_ner():
    data = request.get_json()
    text = data.get("text", "")
    result = medical_ner.extract(text)
    return jsonify(result)

# --- SYMPTOM CHECKER ---
@app.route("/api/symptom_check", methods=["POST"])
def api_symptom_check():
    data     = request.get_json()
    symptoms = data.get("symptoms", [])
    lang     = data.get("lang", "en")
    user_id  = session.get('user_id')
    patient_ctx = get_patient_context(user_id) if session.get('role') == 'patient' else ""
    result = symptom_checker.check(symptoms, patient_ctx=patient_ctx, lang=lang)
    return jsonify({"success": True, **result})

# --- PEPPER CAMERA SNAPSHOT (proxy to Python 2.7 camera_server.py) ---
# The camera server runs on Python 2.7 with NAOqi and serves JPEG snapshots.
# We proxy here so the tablet HTML pages use a single origin (no CORS issues).
CAM_SERVER_PORT = int(os.environ.get("CAM_PORT", "8082"))

@app.route("/api/camera/snapshot", methods=["GET"])
def api_camera_snapshot():
    """Proxy: return a JPEG frame from the camera server."""
    try:
        r = requests.get(f"http://127.0.0.1:{CAM_SERVER_PORT}/snapshot", timeout=3)
        if r.status_code == 200:
            return Response(r.content, mimetype="image/jpeg",
                            headers={"Cache-Control": "no-cache"})
        return jsonify({"error": "Camera server returned " + str(r.status_code)}), 503
    except Exception as e:
        return jsonify({"error": "Camera server not reachable: " + str(e)}), 503

@app.route("/api/camera/snapshot_b64", methods=["GET"])
def api_camera_snapshot_b64():
    """Proxy: return a base64 frame from the camera server.
    Longer timeout than /snapshot: this triggers an on-demand VGA still
    (resolution switch + settle on the robot) for face recognition."""
    try:
        r = requests.get(f"http://127.0.0.1:{CAM_SERVER_PORT}/snapshot_b64", timeout=8)
        if r.status_code == 200:
            return jsonify(r.json())
        return jsonify({"error": "Camera server returned " + str(r.status_code)}), 503
    except Exception as e:
        return jsonify({"error": "Camera server not reachable: " + str(e)}), 503

@app.route("/api/camera/mjpeg", methods=["GET"])
def api_camera_mjpeg():
    """Proxy: stream the camera server's MJPEG multipart feed.
    Using a persistent multipart stream removes the per-frame HTTP
    round-trip that made tablet preview laggy."""
    try:
        upstream = requests.get(
            f"http://127.0.0.1:{CAM_SERVER_PORT}/mjpeg",
            stream=True, timeout=(3, None))
    except Exception as e:
        return jsonify({"error": "Camera server not reachable: " + str(e)}), 503
    if upstream.status_code != 200:
        return jsonify({"error": "Camera server returned " + str(upstream.status_code)}), 503

    content_type = upstream.headers.get(
        "Content-Type", "multipart/x-mixed-replace; boundary=pepperframe")

    def _gen():
        try:
            for chunk in upstream.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        except Exception:
            return
        finally:
            try:
                upstream.close()
            except Exception:
                pass

    return Response(_gen(), mimetype=content_type, headers={
        "Cache-Control": "no-cache, no-store, must-revalidate, private",
        "Pragma": "no-cache",
        "Connection": "close",
    })

# --- FACE ENROLL ---
@app.route("/api/face_enroll", methods=["POST"])
def api_face_enroll():
    data       = request.get_json()
    patient_id = data.get("patient_id")
    images     = data.get("images", [])   # list of base64 strings
    if not patient_id or not images:
        return jsonify({"success": False, "error": "patient_id and images required."})
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({"success": False, "error": "Patient not found."})
    result = face_auth.enroll(patient_id, images)
    return jsonify(result)

# --- FACE LOGIN ---
@app.route("/api/face_login", methods=["POST"])
def api_face_login():
    data  = request.get_json()
    image = data.get("image")   # base64 string
    if not image:
        return jsonify({"success": False, "error": "No image provided."})
    result = face_auth.recognize(image)
    if result.get("success"):
        try:
            patient_id = int(result["patient_id"])
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid patient ID from face recognition."})
        patient = Patient.query.get(patient_id)
        if patient:
            session['user_id']   = patient.id
            session['user_name'] = patient.name
            session['role']      = 'patient'
            _slog("face_login", patient_name=patient.name, patient_id=patient.id,
                  success=True, confidence=result.get("confidence"))
            return jsonify({"success": True, "name": patient.name,
                            "confidence": result["confidence"]})
    _slog("face_login", success=False,
          error=result.get("error", "Not recognized"),
          confidence=result.get("confidence"))
    return jsonify({"success": False, "error": result.get("error", "Not recognized."),
                    "confidence": result.get("confidence")})

# --- FACE AUTH STATUS ---
@app.route("/api/face_status", methods=["GET"])
def api_face_status():
    return jsonify(face_auth.status())

# --- CONVERSATION MEMORY SAVE ---
@app.route("/api/memory/save", methods=["POST"])
def api_memory_save():
    data     = request.get_json()
    history  = data.get("history", [])
    user_id  = session.get('user_id')
    if not user_id or not history:
        return jsonify({"success": False})
    mem = ConversationMemory(db, PatientMemory)
    mem.summarize_and_save(user_id, history)
    return jsonify({"success": True})

# --- CONVERSATION MEMORY GET ---
@app.route("/api/memory/get", methods=["GET"])
def api_memory_get():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "context": ""})
    mem = ConversationMemory(db, PatientMemory)
    ctx = mem.get_context(user_id)
    return jsonify({"success": True, "context": ctx})

# --- VISION CHAT (Image + Text via Claude Vision) ---
@app.route("/api/vision_chat", methods=["POST"])
def api_vision_chat():
    data      = request.get_json()
    text      = data.get("message", "Describe this medical image and provide advice.")
    image_b64 = data.get("image")   # base64 data URL or raw base64
    lang      = data.get("lang", "en")
    user_id   = session.get('user_id')
    user_name = session.get('user_name', 'Guest')
    role      = session.get('role', 'guest')
    patient_ctx = get_patient_context(user_id) if role == 'patient' else ""

    if not image_b64:
        return jsonify({"success": False, "answer": "No image provided."})

    # Strip data URL prefix
    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]

    # Offline mode: vision not supported with local models
    if OFFLINE_MODE:
        return jsonify({"success": False,
                        "answer": "Image analysis is not available in offline mode. Please describe your concern and I can help."})

    lang_note = "Respond in Arabic." if lang == "ar" else "Respond in English."
    system_prompt = (
        f"You are Pepper, a medical robot assistant at Andalusia Hospital. "
        f"The patient's name is {user_name}. {lang_note} "
        f"Analyze the medical image and provide helpful observations and advice. "
        f"Always recommend seeing a doctor for proper diagnosis. "
        f"Keep response under 80 words. No markdown or asterisks."
    )
    if patient_ctx:
        system_prompt += f"\n\nPatient medical profile:\n{patient_ctx}"

    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 400,
        "system": system_prompt,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                                              "media_type": "image/jpeg",
                                              "data": image_b64}},
                {"type": "text", "text": text}
            ]
        }]
    }
    try:
        resp = requests.post("https://api.anthropic.com/v1/messages",
                             headers=headers, json=payload, timeout=30)
        resp_json = resp.json()
        if "content" not in resp_json:
            return jsonify({"success": False, "answer": "Vision analysis failed."})
        answer = resp_json["content"][0]["text"]
        return jsonify({"success": True, "answer": answer})
    except Exception as e:
        print(f"[VISION] Error: {e}")
        return jsonify({"success": False, "answer": "Could not analyze the image."})


# ── SESSION LOG ENDPOINTS ────────────────────────────────────────────────────

@app.route("/api/session/event", methods=["POST"])
def api_session_event():
    """Receive a session event from external processes (nav_bridge, MainVoice, etc.)."""
    data = request.get_json(silent=True) or {}
    _slog(
        action       = data.get("action", "event"),
        patient_name = data.get("patient_name"),
        patient_id   = data.get("patient_id"),
        success      = data.get("success", True),
        duration_ms  = data.get("duration_ms"),
        **{k: v for k, v in data.get("details", {}).items()}
    )
    return jsonify({"ok": True})


@app.route("/api/session/log", methods=["GET"])
def api_session_log():
    """Return session events for a given date (default: today). ?date=YYYY-MM-DD&last=N"""
    from session_logger import _resolve_log_dir
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    last_n   = int(request.args.get("last", 200))
    log_path = os.path.join(_resolve_log_dir(), "%s.jsonl" % date_str)
    if not os.path.exists(log_path):
        return jsonify({"date": date_str, "events": [], "total": 0})
    events = []
    with open(log_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass
    return jsonify({"date": date_str, "events": events[-last_n:], "total": len(events)})


@app.route("/api/session/summary", methods=["GET"])
def api_session_summary():
    """Return a counts summary for today's session."""
    from session_logger import _resolve_log_dir
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    log_path = os.path.join(_resolve_log_dir(), "%s.jsonl" % date_str)
    counts   = {}
    errors   = 0
    patients = set()
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    counts[ev["action"]] = counts.get(ev["action"], 0) + 1
                    if not ev.get("success"):
                        errors += 1
                    if ev.get("patient_name"):
                        patients.add(ev["patient_name"])
                except Exception:
                    pass
    return jsonify({"date": date_str, "counts": counts,
                    "unique_patients": len(patients), "total_errors": errors})


# ── DIAGNOSTIC ENDPOINTS ─────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def api_health():
    """Server health check — used by run_diagnostic.py and monitoring tools."""
    return jsonify({
        "status":          "ok",
        "uptime_seconds":  round(time.time() - SERVER_START_TIME, 1),
        "rag_ready":       True,
        "emotion_ready":   emotion_detector is not None,
        "whisper_ready":   audio_model is not None,
        "offline_mode":    OFFLINE_MODE,
        "timestamp":       datetime.now().isoformat(),
    })


@app.route("/api/diagnostic/report", methods=["GET"])
def api_diagnostic_report():
    """Return the most recent diagnostic report JSON from diagnostic_logs/."""
    import glob as _g
    log_base = Path(__file__).resolve().parents[3] / "diagnostic_logs"
    if not log_base.exists():
        return jsonify({"error": "No diagnostic_logs directory found"}), 404
    reports = sorted(_g.glob(str(log_base / "*/report.json")), reverse=True)
    if not reports:
        return jsonify({"error": "No diagnostic reports found — run run_diagnostic.py first"}), 404
    with open(reports[0], "r") as f:
        report = json.load(f)
    return jsonify(report)


# ══════════════════════════════════════════════════════════════════════════════
#  NEW FEATURE ROUTES
# ══════════════════════════════════════════════════════════════════════════════

# ── VITALS ────────────────────────────────────────────────────────────────────

@app.route("/api/vitals/record", methods=["POST"])
def api_vitals_record():
    """Record a vital signs reading for the logged-in patient. OFFLINE."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "error": "Not logged in."}), 401
    data = request.get_json(silent=True) or {}
    vital_fields = ["pain_scale","temperature","systolic_bp","diastolic_bp",
                    "heart_rate","oxygen_sat","respiratory_rate",
                    "blood_glucose","weight_kg","height_cm"]
    kwargs = {k: data.get(k) for k in vital_fields}
    # Run offline rule-based alerts
    alerts = check_vital_alerts(kwargs)
    record = VitalRecord(
        patient_id=user_id,
        recorded_by=data.get("recorded_by", "patient"),
        notes=data.get("notes", ""),
        alerts=json.dumps(alerts),
        **{k: v for k, v in kwargs.items() if v is not None},
    )
    db.session.add(record)
    db.session.commit()
    _slog("vital_recorded", patient_id=user_id, patient_name=session.get('user_name'),
          success=True, alerts=len(alerts))
    return jsonify({"success": True, "id": record.id, "alerts": alerts,
                    "critical": any("CRITICAL" in a for a in alerts)})


@app.route("/api/vitals/history", methods=["GET"])
def api_vitals_history():
    """Return vital sign history for logged-in patient. OFFLINE."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "error": "Not logged in."}), 401
    limit   = min(int(request.args.get("limit", 20)), 100)
    records = (VitalRecord.query
               .filter_by(patient_id=user_id)
               .order_by(VitalRecord.recorded_at.desc())
               .limit(limit).all())
    return jsonify({"success": True, "records": [r.to_dict() for r in records],
                    "total": len(records)})


@app.route("/api/vitals/analyze", methods=["GET"])
def api_vitals_analyze():
    """AI trend analysis of patient vitals. OFFLINE (Ollama) / ONLINE (Claude)."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "error": "Not logged in."}), 401
    records = (VitalRecord.query
               .filter_by(patient_id=user_id)
               .order_by(VitalRecord.recorded_at.asc())
               .limit(30).all())
    if not records:
        return jsonify({"success": True, "analysis": "No vital records found.",
                        "source": "rule_based"})
    record_dicts = [r.to_dict() for r in records]
    summary      = summarize_vitals(record_dicts)
    recent_alerts = []
    for r in record_dicts[-5:]:
        recent_alerts.extend(r.get("alerts", []))
    patient = Patient.query.get(user_id)
    result  = vital_analyzer.analyze_trends(
        patient_name=patient.name if patient else "Patient",
        summary=summary,
        recent_alerts=recent_alerts
    )
    return jsonify({"success": True, "summary": summary, **result})


# ── MEDICATION REMINDERS ──────────────────────────────────────────────────────

@app.route("/api/medications/reminders", methods=["GET"])
def api_reminders_get():
    """Return active medication reminders. OFFLINE."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "error": "Not logged in."}), 401
    mgr  = MedicationReminderManager(db, MedicationReminder)
    data = mgr.get_all(user_id, active_only=True)
    return jsonify({"success": True, "reminders": data})


@app.route("/api/medications/reminders", methods=["POST"])
def api_reminders_add():
    """Create a medication reminder. OFFLINE."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "error": "Not logged in."}), 401
    data = request.get_json(silent=True) or {}
    med  = data.get("medication_name", "").strip()
    if not med:
        return jsonify({"success": False, "error": "medication_name is required."}), 400
    mgr    = MedicationReminderManager(db, MedicationReminder)
    result = mgr.add(
        patient_id=user_id,
        medication_name=med,
        dosage=data.get("dosage", ""),
        frequency=data.get("frequency", ""),
        times=data.get("times", []),
        end_date=data.get("end_date"),
        notes=data.get("notes", ""),
    )
    return jsonify(result)


@app.route("/api/medications/reminders/<int:rid>", methods=["DELETE"])
def api_reminders_delete(rid):
    """Delete a medication reminder. OFFLINE."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "error": "Not logged in."}), 401
    mgr = MedicationReminderManager(db, MedicationReminder)
    return jsonify(mgr.delete(rid, user_id))


@app.route("/api/medications/due", methods=["GET"])
def api_reminders_due():
    """Return reminders due in the next 30 minutes. OFFLINE."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "error": "Not logged in."}), 401
    mgr = MedicationReminderManager(db, MedicationReminder)
    due = mgr.get_due(user_id, window_minutes=int(request.args.get("window", 30)))
    return jsonify({"success": True, "due": due, "count": len(due)})


# ── DRUG INTERACTIONS ─────────────────────────────────────────────────────────

@app.route("/api/medications/check_interactions", methods=["POST"])
def api_drug_interactions():
    """
    Check drug-drug interactions from local DB. OFFLINE.
    If a pair is unknown, optionally queries Claude for AI analysis.
    Body: {"drugs": ["warfarin", "aspirin", "metformin"]}
    """
    data  = request.get_json(silent=True) or {}
    drugs = data.get("drugs", [])
    if not drugs:
        # Auto-load from patient profile if logged in
        user_id = session.get('user_id')
        if user_id:
            patient = Patient.query.get(user_id)
            if patient and patient.current_medications:
                drugs = [d.strip() for d in patient.current_medications.split(",") if d.strip()]
    if not drugs:
        return jsonify({"success": False, "error": "No drugs provided."}), 400

    checker = DrugChecker(db, DrugInteraction, Medication)
    result  = checker.check(drugs)
    _slog("drug_interaction_check",
          patient_id=session.get('user_id'),
          patient_name=session.get('user_name'),
          success=True,
          drug_count=len(drugs),
          interactions_found=len(result["interactions"]),
          safe=result["safe"])
    return jsonify({"success": True, **result})


@app.route("/api/medications/catalog", methods=["GET"])
def api_drug_catalog():
    """Search the local drug catalog. OFFLINE. ?q=<name>&category=<cat>"""
    q        = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    query    = Medication.query
    if q:
        query = query.filter(
            (Medication.name.ilike(f"%{q}%")) |
            (Medication.generic_name.ilike(f"%{q}%"))
        )
    if category:
        query = query.filter(Medication.category.ilike(f"%{category}%"))
    meds = query.limit(20).all()
    result = []
    for m in meds:
        result.append({
            "id": m.id, "name": m.name, "generic_name": m.generic_name,
            "category": m.category, "dosage_forms": m.dosage_forms,
            "side_effects": m.common_side_effects,
            "contraindications": m.contraindications,
            "pregnancy_category": m.pregnancy_category,
            "requires_monitoring": m.requires_monitoring,
            "notes": m.notes,
        })
    return jsonify({"success": True, "medications": result, "total": len(result)})


# ── FALL DETECTION ────────────────────────────────────────────────────────────

@app.route("/api/fall/start", methods=["POST"])
def api_fall_start():
    """Start fall detection monitoring loop. OFFLINE."""
    data  = request.get_json(silent=True) or {}
    cam   = int(data.get("camera_index", 0))
    result = fall_detector.start(camera_index=cam)
    return jsonify(result)


@app.route("/api/fall/stop", methods=["POST"])
def api_fall_stop():
    """Stop fall detection. OFFLINE."""
    return jsonify(fall_detector.stop())


@app.route("/api/fall/status", methods=["GET"])
def api_fall_status():
    """Return fall detector status. OFFLINE."""
    return jsonify(fall_detector.status())


@app.route("/api/fall/alerts", methods=["GET"])
def api_fall_alerts():
    """Return accumulated fall alerts (clears the log). OFFLINE."""
    clear = request.args.get("clear", "true").lower() == "true"
    return jsonify({"success": True, "alerts": fall_detector.get_alerts(clear=clear)})


@app.route("/api/fall/analyze_frame", methods=["POST"])
def api_fall_analyze():
    """Analyze a single base64 JPEG for fall risk. OFFLINE."""
    data  = request.get_json(silent=True) or {}
    image = data.get("image", "")
    if not image:
        return jsonify({"success": False, "error": "No image provided."}), 400
    return jsonify({"success": True, **fall_detector.analyze_frame(image)})


# ── TRANSLATION ───────────────────────────────────────────────────────────────

@app.route("/api/translate", methods=["POST"])
def api_translate():
    """
    Translate text between Arabic and English.
    OFFLINE: argostranslate (if installed)
    ONLINE:  Claude API
    NO INTERNET: {"success": False, "source": "no_internet", "error": "..."}
    Body: {"text": "...", "from": "en", "to": "ar"}
    """
    data      = request.get_json(silent=True) or {}
    text      = data.get("text", "").strip()
    from_lang = data.get("from", "en").lower()
    to_lang   = data.get("to",   "ar").lower()
    if not text:
        return jsonify({"success": False, "error": "No text provided."}), 400
    if from_lang not in ("en", "ar") or to_lang not in ("en", "ar"):
        return jsonify({"success": False,
                        "error": "Only English (en) and Arabic (ar) supported."}), 400
    result = translator.translate(text, from_lang, to_lang)
    return jsonify(result)


@app.route("/api/translate/status", methods=["GET"])
def api_translate_status():
    """Return translator backend availability. OFFLINE."""
    return jsonify(translator.status())


# ── WAIT TIME ESTIMATOR ───────────────────────────────────────────────────────

@app.route("/api/wait_time", methods=["GET"])
def api_wait_time():
    """
    Estimate wait time for a doctor on a date/slot. OFFLINE.
    ?doctor_id=1&date=2026-04-20&slot=10:00
    """
    doctor_id = request.args.get("doctor_id")
    date_str  = request.args.get("date")
    slot      = request.args.get("slot")
    if not doctor_id or not date_str or not slot:
        return jsonify({"success": False, "error": "doctor_id, date, and slot are required."}), 400
    est = WaitEstimator(db, Appointment, Schedule, Doctor)
    result = est.estimate_wait(int(doctor_id), date_str, slot)
    return jsonify({"success": True, **result})


@app.route("/api/available_slots", methods=["GET"])
def api_available_slots():
    """
    Return available appointment slots for a doctor on a date. OFFLINE.
    ?doctor_id=1&date=2026-04-20
    """
    doctor_id = request.args.get("doctor_id")
    date_str  = request.args.get("date")
    if not doctor_id or not date_str:
        return jsonify({"success": False, "error": "doctor_id and date are required."}), 400
    est   = WaitEstimator(db, Appointment, Schedule, Doctor)
    slots = est.get_available_slots(int(doctor_id), date_str)
    return jsonify({"success": True, "slots": slots, "count": len(slots)})


@app.route("/api/doctor_load", methods=["GET"])
def api_doctor_load():
    """Return appointment count for a doctor on a given date. OFFLINE."""
    doctor_id = request.args.get("doctor_id")
    date_str  = request.args.get("date")
    est   = WaitEstimator(db, Appointment, Schedule, Doctor)
    if doctor_id:
        return jsonify({"success": True,
                        **est.doctor_load(int(doctor_id), date_str)})
    # No doctor_id → return busiest doctors
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    busiest  = est.busiest_doctors(date_str, top_n=10)
    return jsonify({"success": True, "date": date_str, "doctors": busiest})


# ── SYMPTOM PROGRESSION ───────────────────────────────────────────────────────

@app.route("/api/symptoms/record", methods=["POST"])
def api_symptoms_record():
    """
    Record a symptom entry for the logged-in patient. OFFLINE.
    Body: {"symptoms": ["chest pain", "shortness of breath"], "severity": "moderate",
           "context": "started this morning", "source": "voice"}
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "error": "Not logged in."}), 401
    data  = request.get_json(silent=True) or {}
    syms  = data.get("symptoms", [])
    if not syms:
        return jsonify({"success": False, "error": "symptoms required."}), 400

    # Also run NER if symptoms provided as text
    ner_result = None
    context    = data.get("context", "")
    if context:
        ner_result = medical_ner.extract(context)

    tracker = SymptomProgressionTracker(db, SymptomHistory)
    entry_id = tracker.record(
        patient_id=user_id,
        symptoms=syms,
        severity=data.get("severity"),
        context=context,
        ner_results=ner_result,
        source=data.get("source", "manual"),
    )
    _slog("symptom_recorded", patient_id=user_id, patient_name=session.get('user_name'),
          success=True, symptom_count=len(syms) if isinstance(syms, list) else 1)
    return jsonify({"success": True, "id": entry_id, "ner": ner_result})


@app.route("/api/symptoms/history", methods=["GET"])
def api_symptoms_history():
    """Return symptom history for the logged-in patient. OFFLINE."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "error": "Not logged in."}), 401
    limit   = min(int(request.args.get("limit", 15)), 50)
    tracker = SymptomProgressionTracker(db, SymptomHistory)
    history = tracker.get_history(user_id, limit=limit)
    return jsonify({"success": True, "history": history, "total": len(history)})


@app.route("/api/symptoms/analyze", methods=["GET"])
def api_symptoms_analyze():
    """
    Analyze symptom progression for the logged-in patient.
    OFFLINE (Ollama) / ONLINE (Claude) / NO INTERNET (rule-based fallback).
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "error": "Not logged in."}), 401
    patient = Patient.query.get(user_id)
    tracker = SymptomProgressionTracker(db, SymptomHistory)
    result  = tracker.analyze_progression(
        user_id, patient_name=patient.name if patient else "Patient"
    )
    return jsonify({"success": True, **result})


# ── TRIAGE HISTORY ────────────────────────────────────────────────────────────

@app.route("/api/triage/history", methods=["GET"])
def api_triage_history():
    """Return triage session history for the logged-in patient. OFFLINE."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "error": "Not logged in."}), 401
    limit   = min(int(request.args.get("limit", 10)), 50)
    records = (TriageHistory.query
               .filter_by(patient_id=user_id)
               .order_by(TriageHistory.assessed_at.desc())
               .limit(limit).all())
    result = []
    for t in records:
        result.append({
            "id":                  t.id,
            "assessed_at":         t.assessed_at.strftime("%Y-%m-%d %H:%M"),
            "chief_complaint":     t.chief_complaint,
            "severity":            t.severity,
            "severity_label":      t.severity_label,
            "symptoms":            json.loads(t.symptoms_json) if t.symptoms_json else [],
            "ai_recommendation":   t.ai_recommendation,
            "department_referred": t.department_referred,
            "disposition":         t.disposition,
        })
    return jsonify({"success": True, "history": result, "total": len(result)})


# ─────────────────────────────────────────────────────────────────────────────
# NEW ENDPOINTS — Feature 1: Acoustic Analysis (standalone)
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/acoustic/analyze", methods=["POST"])
def api_acoustic_analyze():
    """
    Analyse an uploaded .wav for vocal biomarkers.
    Accepts multipart/form-data with key 'file'.
    Returns cough, wheeze, breathlessness, pain, and distress scores.
    """
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No audio file provided."}), 400
    import tempfile as _tmp
    f   = request.files["file"]
    tmp = _tmp.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    f.save(tmp.name)
    try:
        result = acoustic_analyzer.analyze(tmp.name)
        return jsonify({"success": True, **result})
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# NEW ENDPOINTS — Feature 2: Pose Analysis
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/pose/analyze", methods=["POST"])
def api_pose_analyze():
    """
    One-shot pose analysis of a single base64 JPEG frame.
    Body: { "image": "<data-uri or raw base64>" }
    Returns distress_pose, stroke_risk, gait_analysis, and alerts.
    """
    data  = request.get_json(force=True) or {}
    image = data.get("image", "")
    if not image:
        return jsonify({"success": False, "error": "No image provided."}), 400
    result = pose_analyzer.analyze_frame(image)
    return jsonify({"success": True, **result})


@app.route("/api/pose/start", methods=["POST"])
def api_pose_start():
    """Start continuous pose monitoring on the server's camera."""
    if session.get("role") not in ("staff", "admin"):
        return jsonify({"success": False, "error": "Staff access required."}), 403
    data  = request.get_json(force=True) or {}
    cam   = int(data.get("camera_index", 0))
    return jsonify(pose_analyzer.start(cam))


@app.route("/api/pose/stop", methods=["POST"])
def api_pose_stop():
    """Stop continuous pose monitoring."""
    if session.get("role") not in ("staff", "admin"):
        return jsonify({"success": False, "error": "Staff access required."}), 403
    return jsonify(pose_analyzer.stop())


@app.route("/api/pose/alerts", methods=["GET"])
def api_pose_alerts():
    """Return accumulated pose alerts (clears log by default)."""
    clear = request.args.get("clear", "true").lower() != "false"
    return jsonify({"success": True, "alerts": pose_analyzer.get_alerts(clear=clear)})


@app.route("/api/pose/status", methods=["GET"])
def api_pose_status():
    return jsonify({"success": True, **pose_analyzer.status()})


# ─────────────────────────────────────────────────────────────────────────────
# NEW ENDPOINTS — Feature 4: Clinical Predictions
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/predict/readmission", methods=["POST"])
def api_predict_readmission():
    """
    Predict ER readmission risk for the logged-in patient (or arbitrary features).

    Body (all optional — missing values are imputed):
    {
      "triage_level":  int 1-4,
      "pain_score":    int 0-10,
      "heart_rate":    int bpm,
      "systolic_bp":   int mmHg,
      "diastolic_bp":  int mmHg,
      "oxygen_sat":    float %,
      "temperature":   float °C,
      "age":           int,
      "prior_visits":  int,
      "symptom_count": int
    }
    """
    data     = request.get_json(force=True) or {}
    user_id  = session.get("user_id")

    # Auto-fill age from patient record if logged in and not supplied
    if user_id and data.get("age") is None:
        pt = Patient.query.get(user_id)
        if pt and pt.age:
            data["age"] = pt.age

    # Auto-fill prior visit count
    if user_id and data.get("prior_visits") is None:
        data["prior_visits"] = TriageHistory.query.filter_by(
            patient_id=user_id
        ).count()

    result = readmission_predictor.predict(data)
    _slog("readmission_prediction", patient_id=user_id, success=True,
          risk_level=result.get("risk_level"), probability=result.get("probability"))
    return jsonify({"success": True, **result})


@app.route("/api/predict/wait", methods=["POST"])
def api_predict_wait():
    """
    ML-enhanced wait time prediction.

    Body:
    {
      "doctor_id":     int,
      "triage_level":  int 1-4,
      "specialty":     str  (optional — looked up from doctor if omitted)
    }
    """
    data       = request.get_json(force=True) or {}
    doctor_id  = data.get("doctor_id")
    triage     = int(data.get("triage_level", 3))
    specialty  = data.get("specialty", "")

    # Count appointments ahead right now
    ahead = 0
    if doctor_id:
        now  = datetime.now()
        ahead = Appointment.query.filter(
            Appointment.doctor_id        == doctor_id,
            Appointment.appointment_date == now.date(),
            Appointment.time_slot        >= now.time(),
        ).count()
        if not specialty:
            doc = Doctor.query.get(doctor_id)
            if doc:
                specialty = doc.specialty

    result = dynamic_wait_estimator.estimate(
        appointments_ahead=ahead,
        triage_level=triage,
        specialty=specialty,
    )
    return jsonify({"success": True, **result})


@app.route("/api/predict/retrain", methods=["POST"])
def api_predict_retrain():
    """
    Retrain prediction models on current DB data.
    Staff only.  Runs in a background thread — returns immediately.
    """
    if session.get("role") not in ("staff", "admin"):
        return jsonify({"success": False, "error": "Staff access required."}), 403

    import threading as _t
    def _retrain():
        with app.app_context():
            r_res = readmission_predictor.retrain(db, VitalRecord, TriageHistory, Patient)
            w_res = dynamic_wait_estimator.retrain(db, Appointment, Schedule, Doctor)
            print(f"[RETRAIN] Readmission: {r_res}  Wait: {w_res}")

    _t.Thread(target=_retrain, daemon=True).start()
    return jsonify({"success": True, "message": "Retraining started in background."})


if __name__ == "__main__":
    setup_database(app)
    # Init conversation memory after DB is ready
    conv_memory = ConversationMemory(db, PatientMemory)
    app.run(host="0.0.0.0", port=8080, threaded=True)