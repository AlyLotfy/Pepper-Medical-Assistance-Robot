# -*- coding: utf-8 -*-
# Set UTF-8 output on Windows before anything else
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
"""
test_offline.py - Pepper Medical Assistance Robot
Comprehensive offline system test suite.

Run from project root:
    python test_offline.py

Tests every subsystem with real-life hospital inputs and shows
actual outputs so you can evaluate accuracy qualitatively.
"""

import os
import sys
import json
import time
import requests

# ─────────────────────────────────────────────
# Force offline mode BEFORE importing any module
# ─────────────────────────────────────────────
os.environ["OFFLINE_MODE"]  = "1"
os.environ["OLLAMA_MODEL"]  = "qwen2.5:7b"
os.environ["OLLAMA_URL"]    = "http://localhost:11434"
os.environ["CLAUDE_API_KEY"] = ""

# Add app directory to path
APP_DIR = os.path.join(os.path.dirname(__file__),
                       "Pepper-Controller-main-2", "pepper_ui", "server", "app")
sys.path.insert(0, APP_DIR)

# ─────────────────────────────────────────────
# Output helpers
# ─────────────────────────────────────────────
PASS  = " PASS "
FAIL  = " FAIL "
INFO  = " INFO "
WARN  = " WARN "
SEP   = "-" * 65

results = []   # (test_name, passed, duration_s, note)

def section(title):
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)

def result(name, passed, duration, output_preview=""):
    tag = PASS if passed else FAIL
    print(f"  [{tag}] {name}  ({duration:.2f}s)")
    if output_preview:
        # Indent preview lines
        for line in str(output_preview)[:400].splitlines():
            print(f"         {line}")
    results.append((name, passed, duration, output_preview))

def show_value(label, value):
    """Print a labelled output value (not a pass/fail)."""
    print(f"\n  {INFO} {label}:")
    for line in str(value)[:600].splitlines():
        print(f"         {line}")


# ═══════════════════════════════════════════════════════════════
# 0. PREREQUISITES
# ═══════════════════════════════════════════════════════════════
section("0. PREREQUISITES")

# 0a. Ollama running?
t0 = time.time()
try:
    r = requests.get("http://localhost:11434/api/tags", timeout=4)
    models = [m["name"] for m in r.json().get("models", [])]
    ollama_ok = True
    result("Ollama server reachable", True, time.time()-t0,
           f"Available models: {models}")
except Exception as e:
    ollama_ok = False
    result("Ollama server reachable", False, time.time()-t0, str(e))
    print(f"\n  {WARN} Ollama is not running! Start it with: ollama serve")
    print(f"  {WARN} Skipping all AI tests.\n")

# 0b. qwen2.5:7b available?
qwen_ok = False
if ollama_ok:
    t0 = time.time()
    qwen_ok = any("qwen2.5:7b" in m for m in models)
    result("qwen2.5:7b model present", qwen_ok, time.time()-t0,
           "Run: ollama pull qwen2.5:7b" if not qwen_ok else "Ready")

# 0c. RAG index exists?
t0 = time.time()
faiss_path = os.path.join(APP_DIR, "rag_index.faiss")
rag_ready = os.path.exists(faiss_path)
result("FAISS index file exists", rag_ready, time.time()-t0,
       faiss_path if rag_ready else "Run: python rag_engine.py")

# 0d. Hospital DB exists?
t0 = time.time()
db_path = os.path.join(APP_DIR, "hospital.db")
db_ready = os.path.exists(db_path)
result("hospital.db exists", db_ready, time.time()-t0,
       db_path if db_ready else "DB will be auto-created on first app.py run")


# ═══════════════════════════════════════════════════════════════
# 1. RAG ENGINE
# ═══════════════════════════════════════════════════════════════
section("1. RAG ENGINE — Hospital Knowledge Retrieval")

rag_engine = None
if rag_ready:
    try:
        from rag_engine import RAGEngine
        t0 = time.time()
        rag_engine = RAGEngine()
        load_time = time.time() - t0
        result("RAG engine loads", rag_engine.is_ready(), load_time,
               str(rag_engine.status()))
    except Exception as e:
        result("RAG engine loads", False, 0, str(e))

RAG_QUERIES = [
    ("en", "What departments does Andalusia Hospital have?"),
    ("en", "What are the visiting hours?"),
    ("en", "How do I book an appointment?"),
    ("ar", "ما هي أقسام مستشفى أندلسية؟"),
    ("en", "Is there a cardiology department?"),
    ("en", "What is the emergency number?"),
]

if rag_engine and rag_engine.is_ready():
    for lang, query in RAG_QUERIES:
        t0 = time.time()
        try:
            hits = rag_engine.retrieve(query, lang=lang, k=2)
            ctx  = rag_engine.retrieve_context_string(query, lang=lang, k=2)
            passed = bool(hits and ctx)
            result(f"RAG [{lang}]: {query[:45]}", passed, time.time()-t0,
                   ctx[:300] if ctx else "No results")
        except Exception as e:
            result(f"RAG [{lang}]: {query[:45]}", False, time.time()-t0, str(e))
else:
    print(f"  {WARN} Skipping RAG tests — index not ready.")


# ═══════════════════════════════════════════════════════════════
# 2. SENTIMENT ANALYZER
# ═══════════════════════════════════════════════════════════════
section("2. SENTIMENT ANALYZER — Patient Emotional State")

SENTIMENT_CASES = [
    ("calm",      "en", "I would like to book an appointment please."),
    ("anxious",   "en", "I am very worried about my test results, I can't sleep."),
    ("pain",      "en", "I have severe chest pain and I can't breathe properly."),
    ("frustrated","en", "I have been waiting for 2 hours and no one is helping me!"),
    ("distressed","en", "I feel dizzy and I think I'm going to faint right now."),
    ("calm",      "ar", "أريد حجز موعد مع الدكتور."),
    ("anxious",   "ar", "أنا قلق جداً من نتائج التحاليل."),
]

if ollama_ok and qwen_ok:
    from ai_modules.sentiment import SentimentAnalyzer
    sa = SentimentAnalyzer()
    for expected, lang, text in SENTIMENT_CASES:
        t0 = time.time()
        try:
            res = sa.analyze(text, lang=lang)
            detected = res.get("sentiment", "?")
            score    = res.get("score", 0)
            alert    = res.get("alert", False)
            passed   = isinstance(res, dict) and "sentiment" in res
            label    = f"expected≈{expected} → got={detected} score={score:.2f} alert={alert}"
            result(f"Sentiment [{lang}]: \"{text[:40]}\"", passed,
                   time.time()-t0, label)
        except Exception as e:
            result(f"Sentiment [{lang}]: \"{text[:40]}\"", False, time.time()-t0, str(e))
else:
    print(f"  {WARN} Skipping — Ollama not ready.")


# ═══════════════════════════════════════════════════════════════
# 3. MEDICAL NER
# ═══════════════════════════════════════════════════════════════
section("3. MEDICAL NER — Entity Extraction from Patient Text")

NER_CASES = [
    "I have chest pain and shortness of breath since yesterday.",
    "My left knee hurts badly, I'm allergic to penicillin and I take metformin daily.",
    "I feel severe headache behind my eyes and I have a fever of 39 degrees.",
    "عندي ألم في البطن وغثيان منذ يومين.",
    "Patient has hypertension, takes amlodipine 5mg, no known allergies.",
]

if ollama_ok and qwen_ok:
    from ai_modules.medical_ner import MedicalNER
    ner = MedicalNER()
    for text in NER_CASES:
        t0 = time.time()
        try:
            res = ner.extract(text)
            passed = isinstance(res, dict) and "symptoms" in res
            preview = (
                f"symptoms={res.get('symptoms',[])} "
                f"body={res.get('body_parts',[])} "
                f"meds={res.get('medications',[])} "
                f"severity={res.get('severity','?')}"
            )
            result(f"NER: \"{text[:45]}\"", passed, time.time()-t0, preview)
        except Exception as e:
            result(f"NER: \"{text[:45]}\"", False, time.time()-t0, str(e))
else:
    print(f"  {WARN} Skipping — Ollama not ready.")


# ═══════════════════════════════════════════════════════════════
# 4. SYMPTOM CHECKER
# ═══════════════════════════════════════════════════════════════
section("4. SYMPTOM CHECKER — Differential Diagnosis")

SYMPTOM_CASES = [
    ("en", ["chest pain", "shortness of breath", "sweating"],
     "Expected: cardiac differential, urgency=immediate"),
    ("en", ["headache", "fever", "stiff neck"],
     "Expected: meningitis in differential, urgency=urgent/immediate"),
    ("en", ["fatigue", "frequent urination", "increased thirst"],
     "Expected: diabetes/hyperglycemia, urgency=routine/urgent"),
    ("ar", ["ألم في البطن", "غثيان", "قيء"],
     "Expected: GI differential in Arabic"),
    ("en", ["mild cough", "runny nose", "slight fever"],
     "Expected: common cold/flu, urgency=self-care/routine"),
]

if ollama_ok and qwen_ok:
    from ai_modules.symptom_checker import SymptomChecker
    sc = SymptomChecker()
    for lang, symptoms, note in SYMPTOM_CASES:
        t0 = time.time()
        try:
            res = sc.check(symptoms, lang=lang)
            passed = isinstance(res, dict) and "urgency" in res and "conditions" in res
            conds = [c.get("name","?") for c in res.get("conditions", [])[:3]]
            preview = (
                f"urgency={res.get('urgency','?')} "
                f"dept={res.get('recommended_department','?')}\n"
                f"         conditions={conds}\n"
                f"         {note}"
            )
            result(f"Symptoms {lang}: {symptoms[:3]}", passed, time.time()-t0, preview)
        except Exception as e:
            result(f"Symptoms {lang}: {symptoms[:3]}", False, time.time()-t0, str(e))
else:
    print(f"  {WARN} Skipping — Ollama not ready.")


# ═══════════════════════════════════════════════════════════════
# 5. DATABASE — Doctors / Departments / Appointments
# ═══════════════════════════════════════════════════════════════
section("5. DATABASE — Doctors, Departments, Appointments")

flask_app = None
if db_ready:
    try:
        # Import app but suppress the startup Ollama warm-up print noise
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            from app import app as flask_app, db, Doctor, Schedule, Appointment, Patient, Department
        result("Flask app imports cleanly", True, 0)
    except Exception as e:
        result("Flask app imports cleanly", False, 0, str(e))

if flask_app:
    with flask_app.app_context():
        # 5a. Count doctors
        t0 = time.time()
        try:
            doc_count = Doctor.query.count()
            passed = doc_count > 0
            result("Doctors in DB", passed, time.time()-t0, f"{doc_count} doctors found")
        except Exception as e:
            result("Doctors in DB", False, time.time()-t0, str(e))

        # 5b. Count departments
        t0 = time.time()
        try:
            depts = db.session.query(Doctor.specialty).distinct().all()
            dept_names = sorted([d[0] for d in depts if d[0]])
            passed = len(dept_names) > 0
            result("Departments in DB", passed, time.time()-t0,
                   f"{len(dept_names)} departments: {dept_names[:6]}")
        except Exception as e:
            result("Departments in DB", False, time.time()-t0, str(e))

        # 5c. List first 5 doctors
        t0 = time.time()
        try:
            doctors = Doctor.query.limit(5).all()
            passed = len(doctors) > 0
            show_value("First 5 doctors",
                       "\n".join(f"  ID={d.id}  {d.name}  ({d.specialty})" for d in doctors))
            result("Query first 5 doctors", passed, time.time()-t0)
        except Exception as e:
            result("Query first 5 doctors", False, time.time()-t0, str(e))

        # 5d. Doctor schedule lookup
        t0 = time.time()
        try:
            first_doc = Doctor.query.first()
            if first_doc:
                slots = Schedule.query.filter_by(doctor_id=first_doc.id).all()
                days = {0:"Mon",1:"Tue",2:"Wed",3:"Thu",4:"Fri",5:"Sat",6:"Sun"}
                sched = [f"{days.get(s.day_of_week,'?')} {s.start_time.strftime('%H:%M')}-{s.end_time.strftime('%H:%M')}" for s in slots]
                result(f"Schedule for Dr. {first_doc.name}", True, time.time()-t0,
                       f"Slots: {sched}")
            else:
                result("Doctor schedule lookup", False, time.time()-t0, "No doctors found")
        except Exception as e:
            result("Doctor schedule lookup", False, time.time()-t0, str(e))

        # 5e. Book + read + cancel an appointment (full cycle)
        t0 = time.time()
        try:
            from datetime import date, time as dtime
            first_doc = Doctor.query.first()
            test_appt = Appointment(
                doctor_id=first_doc.id,
                patient_name="Test Patient",
                appointment_date=date(2026, 5, 10),
                time_slot=dtime(10, 0)
            )
            db.session.add(test_appt)
            db.session.commit()
            appt_id = test_appt.id

            # Read it back
            fetched = Appointment.query.get(appt_id)
            booked_ok = fetched and fetched.patient_name == "Test Patient"

            # Cancel it
            db.session.delete(fetched)
            db.session.commit()
            cancelled_ok = Appointment.query.get(appt_id) is None

            passed = booked_ok and cancelled_ok
            result("Appointment book → read → cancel cycle", passed, time.time()-t0,
                   f"Booked ID={appt_id} with {first_doc.name} → cancelled={cancelled_ok}")
        except Exception as e:
            result("Appointment book → read → cancel cycle", False, time.time()-t0, str(e))


# ═══════════════════════════════════════════════════════════════
# 6. FULL CHAT AI — Agentic Loop via Flask Test Client
# ═══════════════════════════════════════════════════════════════
section("6. FULL CHAT AI — Offline Agentic Loop (qwen2.5:7b + Tools)")

CHAT_CASES = [
    # (description, message, user_id, user_name, role, lang)
    ("Greeting",
     "Hello, can you help me?",
     None, "Guest", "guest", "en"),

    ("Ask for departments",
     "What departments does Andalusia Hospital have?",
     None, "Ahmed", "guest", "en"),

    ("Ask for cardiologist",
     "I need to see a cardiologist. Who is available?",
     None, "Ahmed", "guest", "en"),

    ("Ask doctor schedule",
     "What is the schedule of the cardiology doctor?",
     None, "Ahmed", "guest", "en"),

    ("Emergency — chest pain",
     "I have severe chest pain and I can't breathe!",
     None, "Ahmed", "guest", "en"),

    ("Arabic greeting",
     "مرحبا، أريد حجز موعد.",
     None, "أحمد", "guest", "ar"),

    ("Arabic — ask departments",
     "ما هي التخصصات الطبية المتاحة في المستشفى؟",
     None, "أحمد", "guest", "ar"),

    ("Health tip request",
     "Can you give me a health tip for diabetes?",
     None, "Sara", "guest", "en"),
]

if ollama_ok and qwen_ok and flask_app:
    client = flask_app.test_client()
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False

    for desc, message, uid, uname, role, lang in CHAT_CASES:
        t0 = time.time()
        try:
            payload = {
                "message": message,
                "history": [],
                "lang": lang,
                "user_id": uid,
                "user_name": uname,
                "role": role,
                "voice_mode": False
            }
            resp = client.post(
                "/api/chat_ai",
                data=json.dumps(payload),
                content_type="application/json"
            )
            data = resp.get_json()
            elapsed = time.time() - t0

            # API returns "answer" key (not "reply")
            if resp.status_code == 200 and data and data.get("answer"):
                reply = data["answer"]
                tools_used = [r["tool"] for r in data.get("tool_results", [])]
                passed = True
                preview = f"reply: \"{reply[:200]}\""
                if tools_used:
                    preview += f"\n         tools_used: {tools_used}"
            else:
                passed = False
                preview = f"HTTP {resp.status_code}: {str(data)[:200]}"

            result(f"Chat [{lang}]: {desc}", passed, elapsed, preview)

        except Exception as e:
            result(f"Chat [{lang}]: {desc}", False, time.time()-t0, str(e))
else:
    print(f"  {WARN} Skipping — Ollama or Flask app not ready.")


# ═══════════════════════════════════════════════════════════════
# 7. CONVERSATION MEMORY
# ═══════════════════════════════════════════════════════════════
section("7. CONVERSATION MEMORY — Session Summarization")

if ollama_ok and qwen_ok and flask_app:
    from ai_modules.conversation_memory import ConversationMemory
    from app import PatientMemory

    with flask_app.app_context():
        mem = ConversationMemory(db, PatientMemory)

        fake_history = [
            {"role": "user",      "parts": [{"text": "I have chest pain and shortness of breath."}]},
            {"role": "assistant", "parts": [{"text": "Please go to the emergency department immediately."}]},
            {"role": "user",      "parts": [{"text": "Can you book me an appointment with a cardiologist?"}]},
            {"role": "assistant", "parts": [{"text": "I have booked you with Dr. Ahmed on Monday at 10am."}]},
            {"role": "user",      "parts": [{"text": "I'm also allergic to penicillin."}]},
            {"role": "assistant", "parts": [{"text": "Noted. I will flag that in your profile."}]},
        ]

        # 7a. Summarize
        t0 = time.time()
        try:
            # Use a fake patient id that won't conflict
            mem.summarize_and_save(patient_id=9999, conversation_history=fake_history)
            elapsed = time.time() - t0
            # Read back
            ctx = mem.get_context(patient_id=9999)
            passed = bool(ctx)
            result("Memory: summarize 6-turn conversation", passed, elapsed,
                   ctx[:400] if ctx else "Empty context returned")

            # Cleanup
            record = PatientMemory.query.filter_by(patient_id=9999).first()
            if record:
                db.session.delete(record)
                db.session.commit()
        except Exception as e:
            result("Memory: summarize 6-turn conversation", False, time.time()-t0, str(e))

        # 7b. Empty context for unknown patient
        t0 = time.time()
        ctx = mem.get_context(patient_id=0)
        result("Memory: empty context for unknown patient", ctx == "", time.time()-t0,
               f"returned: '{ctx}'")
else:
    print(f"  {WARN} Skipping — Ollama or app not ready.")


# ═══════════════════════════════════════════════════════════════
# 8. TRIAGE ASSESSMENT
# ═══════════════════════════════════════════════════════════════
section("8. TRIAGE ASSESSMENT — API Endpoint")

# Triage API uses: chiefComplaint, painScore, symptoms (specific danger-sign strings), lang
# Returns: { level (1-4), label (IMMEDIATE/VERY URGENT/URGENT/STANDARD), color, department, recommendation }
TRIAGE_CASES = [
    {
        "chiefComplaint": "heart",
        "painScore": 8,
        "symptoms": ["Chest tightens/squeezes", "Sweating heavily"],
        "lang": "en",
        "note": "Expect: level=2, VERY URGENT, Emergency"
    },
    {
        "chiefComplaint": "other",
        "painScore": 2,
        "symptoms": [],
        "lang": "en",
        "note": "Expect: level=4, STANDARD"
    },
    {
        "chiefComplaint": "neuro",
        "painScore": 9,
        "symptoms": ["Sudden thunderclap headache", "Neck stiffness / cannot touch chin to chest"],
        "lang": "en",
        "note": "Expect: level=1 or 2, Emergency"
    },
]

if flask_app:
    client = flask_app.test_client()
    for case in TRIAGE_CASES:
        note = case.pop("note")
        t0 = time.time()
        try:
            resp = client.post(
                "/api/triage_assess",
                data=json.dumps(case),
                content_type="application/json"
            )
            data = resp.get_json()
            elapsed = time.time() - t0
            if resp.status_code == 200 and data:
                level  = data.get("level", "?")
                label  = data.get("label", "?")
                dept   = data.get("department", "?")
                passed = data.get("success", False) and label != "?"
                result(f"Triage: pain={case['painScore']} syms={len(case['symptoms'])}",
                       passed, elapsed,
                       f"level={level} label={label} dept={dept}\n         {note}")
            else:
                result(f"Triage: pain={case['painScore']}", False, elapsed,
                       f"HTTP {resp.status_code}: {str(data)[:200]}")
            case["note"] = note
        except Exception as e:
            result(f"Triage: pain={case.get('painScore','?')}", False, time.time()-t0, str(e))


# ═══════════════════════════════════════════════════════════════
# 9. HEALTH TIPS AI
# ═══════════════════════════════════════════════════════════════
section("9. AI HEALTH TIPS")

# Note: /api/ai_health_tips requires patient session — tested via the chat endpoint instead.
# We verify the underlying interact_with_gemini() function directly here.
if ollama_ok and qwen_ok and flask_app:
    with flask_app.app_context():
        from app import interact_with_gemini
        for lang in ["en", "ar"]:
            t0 = time.time()
            try:
                prompt = (
                    "Generate 1 short health tip for a general patient. "
                    "Return ONLY a plain sentence." if lang == "en" else
                    "اكتب نصيحة صحية واحدة قصيرة لمريض. أجب بجملة واحدة فقط."
                )
                tip = interact_with_gemini(prompt, [], "Test", lang=lang)
                elapsed = time.time() - t0
                passed = bool(tip and len(tip) > 5)
                result(f"Health tip AI [{lang}]", passed, elapsed,
                       f"\"{tip[:200]}\"" if tip else "Empty")
            except Exception as e:
                result(f"Health tip AI [{lang}]", False, time.time()-t0, str(e))
else:
    print(f"  {WARN} Skipping — Ollama or app not ready.")


# ═══════════════════════════════════════════════════════════════
# 10. DOCTOR / DEPARTMENT API ROUTES
# ═══════════════════════════════════════════════════════════════
section("10. DOCTOR & DEPARTMENT API ROUTES")

if flask_app:
    client = flask_app.test_client()

    # GET /api/doctors — returns JSON array
    t0 = time.time()
    try:
        resp = client.get("/api/doctors")
        # Route uses jsonify() now, so get_json() works
        data = resp.get_json()
        passed = resp.status_code == 200 and isinstance(data, list) and len(data) > 0
        result("GET /api/doctors", passed, time.time()-t0,
               f"{len(data)} doctors returned" if isinstance(data, list) else str(data)[:100])
    except Exception as e:
        result("GET /api/doctors", False, time.time()-t0, str(e))

    # GET /api/departments — returns {"departments": [...]}
    t0 = time.time()
    try:
        resp = client.get("/api/departments")
        data = resp.get_json()
        depts = data.get("departments", []) if isinstance(data, dict) else []
        passed = resp.status_code == 200 and len(depts) > 0
        result("GET /api/departments", passed, time.time()-t0,
               f"{len(depts)} depts: {depts[:5]}")
    except Exception as e:
        result("GET /api/departments", False, time.time()-t0, str(e))

    # GET /api/doctors_by_department/Cardiology
    t0 = time.time()
    try:
        resp = client.get("/api/doctors_by_department/Cardiology")
        data = resp.get_json()
        passed = resp.status_code == 200
        result("GET /api/doctors_by_department/Cardiology", passed, time.time()-t0,
               str(data)[:200])
    except Exception as e:
        result("GET /api/doctors_by_department/Cardiology", False, time.time()-t0, str(e))

    # GET /api/navigation_targets
    t0 = time.time()
    try:
        resp = client.get("/api/navigation_targets")
        data = resp.get_json()
        passed = resp.status_code == 200
        result("GET /api/navigation_targets", passed, time.time()-t0, str(data)[:200])
    except Exception as e:
        result("GET /api/navigation_targets", False, time.time()-t0, str(e))


# ═══════════════════════════════════════════════════════════════
# 11. SIGNUP / LOGIN
# ═══════════════════════════════════════════════════════════════
section("11. PATIENT SIGNUP & LOGIN")

if flask_app:
    client = flask_app.test_client()

    # Signup requires: id (integer), name, password, role ("patient"|"staff")
    test_id = 99999
    test_user = {
        "id": test_id,
        "name": "Test Patient Offline",
        "password": "TestPass123",
        "role": "patient",
        "case_number": "TEST-001"
    }

    # Clean up any leftover test patient first
    with flask_app.app_context():
        p = Patient.query.get(test_id)
        if p:
            db.session.delete(p)
            db.session.commit()

    # Signup
    t0 = time.time()
    try:
        resp = client.post(
            "/api/signup",
            data=json.dumps(test_user),
            content_type="application/json"
        )
        data = resp.get_json()
        passed = resp.status_code == 200 and data.get("success") == True
        result("POST /api/signup (patient)", passed, time.time()-t0, str(data)[:200])
    except Exception as e:
        result("POST /api/signup (patient)", False, time.time()-t0, str(e))

    # Login
    t0 = time.time()
    try:
        resp = client.post(
            "/api/login",
            data=json.dumps({"id": test_id, "password": test_user["password"], "role": "patient"}),
            content_type="application/json"
        )
        data = resp.get_json()
        passed = resp.status_code == 200 and data.get("success") == True
        result("POST /api/login (correct password)", passed, time.time()-t0, str(data)[:200])
    except Exception as e:
        result("POST /api/login (correct password)", False, time.time()-t0, str(e))

    # Wrong password
    t0 = time.time()
    try:
        resp = client.post(
            "/api/login",
            data=json.dumps({"id": test_id, "password": "wrongpassword", "role": "patient"}),
            content_type="application/json"
        )
        data = resp.get_json()
        passed = resp.status_code in (401, 403) or (data and not data.get("success"))
        result("POST /api/login (wrong password — expect reject)", passed, time.time()-t0,
               str(data)[:100])
    except Exception as e:
        result("POST /api/login (wrong password)", False, time.time()-t0, str(e))

    # Cleanup
    with flask_app.app_context():
        p = Patient.query.get(test_id)
        if p:
            db.session.delete(p)
            db.session.commit()


# ═══════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("  FINAL RESULTS")
print(SEP)

passed_list = [r for r in results if r[1]]
failed_list = [r for r in results if not r[1]]
total = len(results)
passed_n = len(passed_list)
failed_n = len(failed_list)

print(f"\n  Total tests : {total}")
print(f"  {PASS} Passed   : {passed_n}")
print(f"  {FAIL} Failed   : {failed_n}")

if failed_list:
    print(f"\n  Failed tests:")
    for name, _, dur, note in failed_list:
        print(f"    x  {name}")
        if note:
            print(f"       {str(note)[:120]}")

pct = (passed_n / total * 100) if total else 0
print(f"\n  Score: {passed_n}/{total} ({pct:.0f}%)")
print(f"\n{SEP}\n")
