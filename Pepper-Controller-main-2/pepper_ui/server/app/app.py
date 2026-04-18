# app.py
# Flask Server for Pepper Medical Assistance Robot
# *** COMPLETE: Database + Legacy Routes + Whisper Voice AI + Health Tips AI + FAISS RAG ***

import os
import json
import time
import tempfile
import requests
import csv
from faster_whisper import WhisperModel
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, session, make_response, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import time, datetime, date as date_type
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

# *** SECURITY KEY (Required for Session) ***
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "pepper_medical_secret_key_99")

# ====== Initialize Whisper (faster-whisper with CTranslate2) ======
print("[INFO] Loading Whisper Model (this may take a moment)...")
audio_model = WhisperModel("base", device="cpu", compute_type="int8")
print("[INFO] Whisper Model Loaded (faster-whisper, int8 quantized).")

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
sentiment_analyzer = SentimentAnalyzer()
medical_ner        = MedicalNER()
symptom_checker    = SymptomChecker()
face_auth          = FaceAuth()
print(f"[INFO] Face Auth status: {face_auth.status()}")
fall_detector      = FallDetector()
translator         = Translator()
vital_analyzer     = VitalAnalyzer()
print(f"[INFO] Fall Detector ready: {fall_detector.status()}")
print(f"[INFO] Translator ready: {translator.status()}")
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
                    db.session.add(Schedule(doctor_id=doc.id, day_of_week=0, start_time=time(9,0), end_time=time(13,0)))
                    db.session.add(Schedule(doctor_id=doc.id, day_of_week=2, start_time=time(14,0), end_time=time(17,0)))
                
                db.session.commit()
                print("Database populated successfully.")
            except Exception as e:
                print(f"[ERROR] Database population failed: {e}")
                db.session.rollback()

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


def call_ollama(system_prompt, messages, max_tokens=256, tools=None):
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
        return _clean_llm_output(reply) if OFFLINE_MODE else reply
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
        # 1. Whisper transcription (faster-whisper API)
        transcribe_opts = {"beam_size": 1, "no_speech_threshold": 0.4}
        if ui_lang == "ar":
            transcribe_opts["language"] = "ar"
            transcribe_opts["task"] = "transcribe"
            transcribe_opts["initial_prompt"] = "مرحبا، أنا أتحدث بالعربية في مستشفى أندلسية."
        elif ui_lang == "en":
            transcribe_opts["language"] = "en"
            transcribe_opts["task"] = "transcribe"
            transcribe_opts["initial_prompt"] = "Hello, I am speaking to Pepper at Andalusia Hospital."

        segments, info = audio_model.transcribe(temp_filename, **transcribe_opts)
        user_text = " ".join(seg.text for seg in segments).strip()
        detected_lang = info.language if info else "en"
        lang = ui_lang if ui_lang in ("ar", "en") else ("ar" if detected_lang == "ar" else "en")
        print(f"[VOICE] User said ({lang}): {user_text}")

        # 2. Resolve identity (Flask session set after tablet login)
        user_id   = session.get('user_id')
        user_name = session.get('user_name', 'Guest')
        role      = session.get('role', '')

        # 3. Sentiment analysis (same as chatbot)
        sentiment = sentiment_analyzer.analyze(user_text, lang)
        if sentiment.get("alert"):
            print(f"[VOICE ALERT] Distress detected for {user_name}: {sentiment.get('reason')}")

        # 4. Medical NER (same as chatbot)
        ner_entities = medical_ner.extract(user_text)

        # 5. Conversation memory (same as chatbot)
        mem = ConversationMemory(db, PatientMemory)
        memory_ctx = mem.get_context(user_id) if user_id else ""

        # 6. Voice conversation history — trim immediately to cap memory usage
        voice_history = session.get('voice_history', [])[-10:]

        # 7. Run full agentic loop with all features
        ai_reply, tool_results = run_agentic_loop(
            user_text, user_id, user_name, role,
            lang=lang, history=voice_history, voice_mode=True,
            sentiment=sentiment, ner_entities=ner_entities, memory_ctx=memory_ctx
        )

        # 8. Update voice conversation history in session
        voice_history.append({"role": "user", "parts": [{"text": user_text}]})
        voice_history.append({"role": "model", "parts": [{"text": ai_reply}]})
        session['voice_history'] = voice_history[-10:]

        print(f"[VOICE] Reply: {ai_reply}")
        _slog("voice_interaction", patient_name=user_name, patient_id=user_id,
              success=True, lang=lang,
              user_said=user_text[:200],
              ai_replied=ai_reply[:300],
              sentiment=sentiment.get("label", "neutral") if sentiment else "neutral",
              tools_used=[r.get("tool") for r in tool_results if isinstance(r, dict) and r.get("tool")])
        return jsonify({"text": user_text, "reply": ai_reply, "lang": lang})

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
        return jsonify({"success": True, "name": user.name})

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
        "description": "Get list of navigable rooms and doctor locations in the hospital.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    }
]


def _clean_doctor_name(name):
    """Strip common prefixes like Dr., Doctor, etc. that models add."""
    import re
    name = name.strip()
    name = re.sub(r'^(Dr\.?\s*|Doctor\s+|Prof\.?\s*|Professor\s+)', '', name, flags=re.IGNORECASE).strip()
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
                doctors = Doctor.query.filter(Doctor.specialty.ilike(f"%{dept}%")).all()
            else:
                doctors = Doctor.query.all()
            return {"doctors": [{"id": d.id, "name": d.name, "specialty": d.specialty} for d in doctors]}

        elif tool_name == "get_doctor_schedule":
            name = _clean_doctor_name(tool_input.get("doctor_name", ""))
            doctor = Doctor.query.filter(Doctor.name.ilike(f"%{name}%")).first()
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
            date_str    = (tool_input or {}).get("date", "")
            time_str    = (tool_input or {}).get("time_slot", "")
            doctor = Doctor.query.filter(Doctor.name.ilike(f"%{doctor_name}%")).first()
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

            # Check the requested time falls within the doctor's schedule
            day_of_week = appt_date.weekday()  # 0=Monday
            slots = Schedule.query.filter_by(doctor_id=doctor.id, day_of_week=day_of_week).all()
            if slots:
                in_schedule = any(s.start_time <= appt_time <= s.end_time for s in slots)
                if not in_schedule:
                    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
                    avail = ", ".join(
                        f"{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][s.day_of_week]} "
                        f"{s.start_time.strftime('%H:%M')}-{s.end_time.strftime('%H:%M')}"
                        for s in Schedule.query.filter_by(doctor_id=doctor.id).all()
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
            return {"appointments": result}

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
            try:
                with open(str(_NAV_TARGETS_PATH), "r", encoding="utf-8") as f:
                    nav_data = json.load(f)
                return {"targets": nav_data.get("targets", [])}
            except Exception:
                doctors = Doctor.query.all()
                return {"targets": [{"name": d.name, "specialty": d.specialty} for d in doctors]}

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


def _clean_llm_output(text):
    """Strip markdown artifacts that local models sometimes produce."""
    import re
    text = text.strip()
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
    # Collapse multiple newlines
    text = re.sub(r'\n{2,}', ' ', text)
    return text.strip()


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


def _run_agentic_loop_offline(system_prompt, messages, user_id, user_name, role,
                               voice_mode, tool_results_for_display):
    """Ollama-based agentic loop with native structured tool calls — mirrors Claude's loop."""
    max_tokens = 512 if voice_mode else 1024
    max_iterations = 5

    for iteration in range(max_iterations):
        result = call_ollama(system_prompt, messages, max_tokens=max_tokens, tools=OLLAMA_TOOLS)

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
            return _clean_llm_output(result) or "Done.", tool_results_for_display

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

                print(f"[TOOL-OFFLINE] {t_name}({t_input})")
                tool_result = execute_tool(t_name, t_input, user_id, user_name, role)
                tool_results_for_display.append({"tool": t_name, "result": tool_result})
                messages.append({"role": "tool", "content": json.dumps(tool_result)})
                # If booking/cancellation failed, inject a directive so the model
                # cannot hallucinate a success message
                if t_name in ("book_appointment", "cancel_appointment") and tool_result.get("error"):
                    messages.append({
                        "role": "user",
                        "content": f"[SYSTEM DIRECTIVE] The {t_name} tool returned this error: \"{tool_result['error']}\". "
                                   f"You MUST tell the patient that the action FAILED and explain exactly why. "
                                   f"Do NOT say the appointment was booked or cancelled."
                    })
            continue

        # Text response with no tool calls — final answer
        return (_clean_llm_output(text) or "Done."), tool_results_for_display

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
            "Always reply in the same dialect the patient used. Keep response under 60 words."
        ) if not voice_mode else (
            "Reply in Arabic in 1-2 short spoken sentences. Match the patient's Arabic dialect."
        )
    else:
        lang_note = ("Respond in English (under 80 words)." if not voice_mode else
                     "Reply in English in 1-2 short spoken sentences suitable for text-to-speech.")

    today = datetime.now().strftime('%Y-%m-%d')
    weekday = datetime.now().strftime('%A')

    system_prompt = (
        f"You are Pepper, a friendly medical robot assistant at Andalusia Hospital.\n"
        f"Patient name: {user_name}.\n"
        f"Today: {today} ({weekday}).\n"
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
        f"9. If you are unsure, ask the patient to clarify."
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
            voice_mode, tool_results_for_display)

    # ---- ONLINE MODE: Claude with native tool use ----
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    max_iterations = 5

    for _ in range(max_iterations):
        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 512 if voice_mode else 1024,
            "system": system_prompt,
            "tools": CHAT_TOOLS,
            "messages": claude_messages
        }
        resp = requests.post("https://api.anthropic.com/v1/messages",
                             headers=headers, json=payload, timeout=30)
        resp_json = resp.json()

        if "error" in resp_json:
            raise RuntimeError(resp_json["error"].get("message", "API error"))

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
        # --- Run AI enrichment in parallel context ---
        # 1. Sentiment analysis
        sentiment = sentiment_analyzer.analyze(user_text, lang)
        if sentiment.get("alert"):
            print(f"[ALERT] Distress detected for {user_name}: {sentiment.get('reason')}")

        # 2. Medical NER — extract entities from message
        ner_entities = medical_ner.extract(user_text)

        # 3. Load conversational memory
        mem = ConversationMemory(db, PatientMemory)
        memory_ctx = mem.get_context(user_id) if user_id else ""

        final_text, tool_results = run_agentic_loop(
            user_text, user_id, user_name, role, lang=lang,
            history=history, voice_mode=False,
            sentiment=sentiment, ner_entities=ner_entities, memory_ctx=memory_ctx
        )
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
            "ner": ner_entities
        })
    except Exception as e:
        print(f"[CHAT ERROR] {e}")
        _slog("chat_message", patient_name=user_name, patient_id=user_id,
              success=False, user_said=user_text[:200], error=str(e))
        return jsonify({"success": False, "answer": "I am having trouble thinking right now. Please try again."})
    
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
    """Proxy: return a base64 frame from the camera server."""
    try:
        r = requests.get(f"http://127.0.0.1:{CAM_SERVER_PORT}/snapshot_b64", timeout=3)
        if r.status_code == 200:
            return jsonify(r.json())
        return jsonify({"error": "Camera server returned " + str(r.status_code)}), 503
    except Exception as e:
        return jsonify({"error": "Camera server not reachable: " + str(e)}), 503

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


if __name__ == "__main__":
    setup_database(app)
    # Init conversation memory after DB is ready
    conv_memory = ConversationMemory(db, PatientMemory)
    app.run(host="0.0.0.0", port=8080, threaded=True)