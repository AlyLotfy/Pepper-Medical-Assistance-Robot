# app.py
# Flask Server for Pepper Medical Assistance Robot
# *** COMPLETE: Database + Legacy Routes + Whisper Voice AI + Health Tips AI + FAISS RAG ***

import os
import json
import time
import requests
import csv
from faster_whisper import WhisperModel
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, session, make_response, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import time, datetime
from rag_engine import RAGEngine
from emotion_detector import EmotionDetector
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ai_modules.sentiment import SentimentAnalyzer
from ai_modules.medical_ner import MedicalNER
from ai_modules.symptom_checker import SymptomChecker
from ai_modules.face_auth import FaceAuth
from ai_modules.conversation_memory import ConversationMemory

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
app.secret_key = "pepper_medical_secret_key_99"

# ====== Initialize Whisper (faster-whisper with CTranslate2) ======
print("[INFO] Loading Whisper Model (this may take a moment)...")
audio_model = WhisperModel("base", device="cpu", compute_type="int8")
print("[INFO] Whisper Model Loaded (faster-whisper, int8 quantized).")

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
# ConversationMemory is initialized after DB is set up (needs db + model)

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

# ===============================
# DATABASE SETUP
# ===============================
def setup_database(app):
    with app.app_context():
        db.create_all()

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

            db.session.add_all(patients + staff_members)
            db.session.commit()
            print("Seeded {} patients and {} staff.".format(len(patients), len(staff_members)))

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
    # 1. Check Login
    if 'user_name' not in session: 
        return jsonify({"success": False, "error": "Not logged in"})
    
    user_name = session['user_name']
    
    # 2. Find appointments for this patient (Case Insensitive)
    apps = Appointment.query.filter(db.func.lower(Appointment.patient_name) == db.func.lower(user_name)).all()
    
    # 3. Format data
    results = []
    for a in apps:
        doc = Doctor.query.get(a.doctor_id)
        results.append({
            "doctor": doc.name if doc else "Unknown", 
            "date": a.appointment_date.strftime("%Y-%m-%d"), 
            "time": a.time_slot.strftime("%H:%M")
        })
        
    return jsonify({"success": True, "appointments": results})

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
    temp_filename = "temp_voice.wav"
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

        # 6. Voice conversation history (persist across turns via session)
        voice_history = session.get('voice_history', [])
        # Keep last 10 turns to stay within token limits
        voice_history = voice_history[-10:]

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
        return jsonify({"text": user_text, "reply": ai_reply, "lang": lang})

    except Exception as e:
        print(f"[VOICE ERROR] {e}")
        return jsonify({"reply": "I could not understand. Please try again."})

# --- 3. LOGIN / AUTH ---
@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    role = data.get("role")
    user_id = data.get("id")
    password = data.get("password")

    user = None
    if role == 'staff': user = Staff.query.filter_by(id=user_id).first()
    elif role == 'patient': user = Patient.query.filter_by(id=user_id).first()
    
    if user and user.password == password:
        session['user_id'] = user.id
        session['user_name'] = user.name
        session['role'] = role
        return jsonify({"success": True, "name": user.name})
    
    return jsonify({"success": False, "error": "Invalid Credentials"})

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/me", methods=["GET"])
def api_me():
    if 'user_name' in session:
        return jsonify({"loggedIn": True, "name": session['user_name']})
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
            doctor_name = _clean_doctor_name(tool_input.get("doctor_name", ""))
            date_str    = tool_input.get("date", "")
            time_str    = tool_input.get("time_slot", "")
            doctor = Doctor.query.filter(Doctor.name.ilike(f"%{doctor_name}%")).first()
            if not doctor:
                return {"error": f"Doctor '{doctor_name}' not found."}
            try:
                from datetime import datetime as dt
                appt_date = dt.strptime(date_str, "%Y-%m-%d").date()
                appt_time = dt.strptime(time_str, "%H:%M").time()
            except ValueError:
                return {"error": "Invalid date or time format. Use YYYY-MM-DD and HH:MM."}
            appt = Appointment(doctor_id=doctor.id, patient_name=user_name,
                               appointment_date=appt_date, time_slot=appt_time)
            db.session.add(appt)
            db.session.commit()
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


def _run_agentic_loop_offline(system_prompt, messages, user_id, user_name, role,
                               voice_mode, tool_results_for_display):
    """Ollama-based agentic loop with native structured tool calls — mirrors Claude's loop."""
    max_tokens = 512 if voice_mode else 1024
    max_iterations = 5

    for iteration in range(max_iterations):
        result = call_ollama(system_prompt, messages, max_tokens=max_tokens, tools=OLLAMA_TOOLS)

        # If result is a plain string, no tool call — return it
        if isinstance(result, str):
            return _clean_llm_output(result) or "Done.", tool_results_for_display

        # Native tool call response
        text = result.get("text", "")
        tool_calls = result.get("tool_calls", [])

        if tool_calls:
            # Record assistant message with tool calls
            messages.append({"role": "assistant", "content": text or ""})

            for tc in tool_calls:
                fn = tc.get("function", {})
                t_name = fn.get("name", "")
                t_input = fn.get("arguments", {})
                if isinstance(t_input, str):
                    try:
                        t_input = json.loads(t_input)
                    except json.JSONDecodeError:
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
                tool_result_contents.append({
                    "type": "tool_result",
                    "tool_use_id": tb["id"],
                    "content": json.dumps(result)
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
    history   = data.get("history", [])
    lang      = data.get("lang", "en")

    # Resolve identity: Flask session > payload
    user_id   = session.get('user_id')   or data.get("patient_id")
    user_name = session.get('user_name') or data.get("user_name", "Guest")
    role      = session.get('role')      or data.get("role", "guest")

    if not session.get('user_id') and user_id and role == 'patient':
        patient = Patient.query.get(user_id)
        if patient:
            session['user_id']   = patient.id
            session['user_name'] = patient.name
            session['role']      = 'patient'

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
        return jsonify({
            "success": True,
            "answer": final_text,
            "tool_results": tool_results,
            "sentiment": sentiment,
            "ner": ner_entities
        })
    except Exception as e:
        print(f"[CHAT ERROR] {e}")
        return jsonify({"success": False, "answer": "I am having trouble thinking right now. Please try again."})
    
# --- 4. SIGNUP ---
@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.get_json()
    user_id = data.get("id")
    name = data.get("name")
    password = data.get("password")
    role = data.get("role")
    
    if role == 'patient':
        if Patient.query.get(user_id): return jsonify({"success": False, "error": "ID Taken"})
        case_num = data.get("case_number")
        db.session.add(Patient(id=user_id, name=name, password=password, case_number=case_num))
    elif role == 'staff':
        if Staff.query.get(user_id): return jsonify({"success": False, "error": "ID Taken"})
        db.session.add(Staff(id=user_id, name=name, password=password, role="Staff"))
    else:
        return jsonify({"success": False, "error": "Invalid Role"})
        
    db.session.commit()
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
    pain = int(data.get("painScore", 0))
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
    elif pain >= 5 or len(symptoms) >= 1:
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
    return json.dumps([{"name": d.name, "specialty": d.specialty} for d in Doctor.query.all()])

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
    user_id  = session.get('user_id') or data.get("patient_id")
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
        patient_id = result["patient_id"]
        patient = Patient.query.get(int(patient_id))
        if patient:
            session['user_id']   = patient.id
            session['user_name'] = patient.name
            session['role']      = 'patient'
            return jsonify({"success": True, "name": patient.name,
                            "confidence": result["confidence"]})
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
    user_id  = session.get('user_id') or data.get("patient_id")
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
    user_id   = session.get('user_id') or data.get("patient_id")
    user_name = session.get('user_name') or data.get("user_name", "Guest")
    role      = session.get('role') or data.get("role", "guest")
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


if __name__ == "__main__":
    setup_database(app)
    # Init conversation memory after DB is ready
    conv_memory = ConversationMemory(db, PatientMemory)
    app.run(host="0.0.0.0", port=8080, threaded=True)