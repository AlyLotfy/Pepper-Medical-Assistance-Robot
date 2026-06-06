#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
create_aly_lotfy_case.py
========================
One-time script: populate a full, realistic medical case for patient Aly Lotfy (id=131).

Inserts / updates:
  - Patient profile (enriched medical history)
  - 8 vital sign records (spanning 3 months)
  - 4 triage history entries
  - 3 medication reminders
  - Conversation memory
  - 3 appointments (pulmonology, dermatology, allergy follow-up)

Run once while the Flask server is NOT running:
    python create_aly_lotfy_case.py
"""

import sys
import os
import json
from datetime import datetime, date, timedelta
from pathlib import Path

# ── Point Python at the Flask app ─────────────────────────────────────────────
APP_DIR = Path(__file__).resolve().parent / \
          "Pepper-Controller-main-2" / "pepper_ui" / "server" / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

# Minimal env so app.py initialises without crashing
os.environ.setdefault("OFFLINE_MODE", "1")
os.environ.setdefault("OLLAMA_MODEL",  "qwen2.5:7b")

from app import app, db, Patient, VitalRecord, TriageHistory, \
                MedicationReminder, PatientMemory, Appointment, Doctor
from werkzeug.security import generate_password_hash

# ── Helpers ───────────────────────────────────────────────────────────────────
def days_ago(n):
    return datetime.now() - timedelta(days=n)

def date_from_now(n):
    return (date.today() + timedelta(days=n))

# ══════════════════════════════════════════════════════════════════════════════
with app.app_context():

    # ── 1. Patient profile ────────────────────────────────────────────────────
    p = Patient.query.get(131)
    if not p:
        p = Patient(id=131)
        db.session.add(p)

    p.name              = "Aly Lotfy"
    p.case_number       = "CASE-ALY-2003"
    p.password          = generate_password_hash("aly2003")
    p.age               = 23
    p.gender            = "Male"
    p.blood_type        = "AB+"
    p.phone             = "01034567890"
    p.emergency_contact = "Lotfy Senior (Father) — 01039876543"
    p.medical_history   = (
        "Mild persistent asthma (diagnosed age 15, well-controlled on ICS). "
        "Allergic rhinitis (perennial — dust mites, tree pollen, cat dander). "
        "Atopic dermatitis (childhood onset, now mostly quiescent — occasional flares on forearms). "
        "Pre-hypertension (borderline readings since 2024, under 12-month observation — no pharmacotherapy yet). "
        "Vitamin D deficiency (corrected 2024). "
        "History: appendectomy 2019 (uncomplicated). No hospitalisation for asthma in past 3 years."
    )
    p.allergies         = (
        "Dust mites (rhinitis + asthma trigger), "
        "Tree pollen (seasonal rhinitis), "
        "Cat dander (bronchospasm), "
        "Aspirin (mild sensitivity — avoid NSAIDs, use paracetamol), "
        "Latex (contact urticaria — documented 2022)"
    )
    p.current_medications = (
        "Fluticasone propionate 125 mcg inhaler — 1 puff BID (controller). "
        "Salbutamol 100 mcg inhaler — 2 puffs PRN up to 4x/day (reliever). "
        "Montelukast 10 mg — once nightly (leukotriene modifier). "
        "Cetirizine 10 mg — once daily during allergy season. "
        "Vitamin D3 2000 IU — once daily (maintenance after deficiency correction). "
        "Emollient cream (Eucerin) — apply to forearms BID PRN for eczema."
    )
    p.notes = (
        "Final-year computer engineering student — high academic stress periods (Jan, May). "
        "Asthma well-controlled; last spirometry FEV1 88% predicted (Mar 2026). "
        "Pre-hypertension: avoid stimulants (caffeine excess, energy drinks). Lifestyle counselling given. "
        "BP target: < 130/80. Next BP check in 6 months. "
        "Dermatology follow-up for eczema: low-potency topical steroid if flare. "
        "Allergist recommended house dust mite immunotherapy — patient considering."
    )

    db.session.commit()
    print(f"[OK] Patient profile updated: {p.name} (id={p.id})")

    # ── 2. Vital records ──────────────────────────────────────────────────────
    # Delete old ones so we start clean
    VitalRecord.query.filter_by(patient_id=131).delete()
    db.session.commit()

    vitals_data = [
        # (days_ago, by, pain, temp, sys, dia, hr, spo2, rr, glucose, wt, ht, notes)
        (90, "nurse",   0, 36.7, 128, 82, 74, 98, 15, None, 78.0, 178, "Routine pre-exam check. BP slightly elevated — stress noted."),
        (75, "nurse",   1, 36.5, 125, 80, 70, 99, 14, None, 78.5, 178, "Follow-up BP. Improving trend. Advised reduce caffeine."),
        (60, "patient", 2, 37.0, 130, 84, 88, 97, 18, None, 77.5, 178, "Mild asthma symptoms during pollen season. Used reliever x2."),
        (45, "nurse",   0, 36.6, 122, 78, 68, 99, 14, None, 78.0, 178, "Post-allergy-season check. BP normalising. Good adherence to meds."),
        (30, "nurse",   0, 36.8, 126, 80, 72, 98, 15, 4.8,  78.2, 178, "Routine. Fasting glucose normal. Vitamin D levels rechecked — normal."),
        (14, "patient", 3, 37.2, 134, 86, 90, 96, 20, None, 77.8, 178, "Exam stress week. Increased BP + HR. Used reliever inhaler. SpO2 96%."),
        ( 7, "nurse",   1, 36.6, 127, 81, 75, 98, 15, None, 78.0, 178, "Post-exam. BP settling. Reinforced inhaler technique."),
        ( 2, "patient", 0, 36.7, 124, 79, 71, 99, 14, None, 78.0, 178, "Self-monitoring. Feeling well. No rescue inhaler use in 7 days."),
    ]

    for (d_ago, by, pain, temp, sys, dia, hr, spo2, rr, gluc, wt, ht, note) in vitals_data:
        vr = VitalRecord(
            patient_id       = 131,
            recorded_at      = days_ago(d_ago),
            recorded_by      = by,
            pain_scale       = pain,
            temperature      = temp,
            systolic_bp      = sys,
            diastolic_bp     = dia,
            heart_rate       = hr,
            oxygen_sat       = spo2,
            respiratory_rate = rr,
            blood_glucose    = gluc,
            weight_kg        = wt,
            height_cm        = ht,
            notes            = note,
            alerts           = json.dumps([]),
        )
        db.session.add(vr)

    db.session.commit()
    print(f"[OK] Inserted 8 vital records")

    # ── 3. Triage history ─────────────────────────────────────────────────────
    TriageHistory.query.filter_by(patient_id=131).delete()
    db.session.commit()

    triage_data = [
        dict(
            days_ago_=180,
            chief_complaint="Acute asthma attack — wheezing and shortness of breath after visiting friend's home with cat",
            severity=2,
            triage_level="VERY URGENT",
            pain_score=3,
            symptoms=["wheezing", "shortness of breath", "chest tightness"],
            vitals={"spo2": 93, "hr": 102, "rr": 24, "bp": "132/86"},
            outcome="Nebulised salbutamol x2 doses. SpO2 recovered to 98%. Discharged with 5-day prednisolone course. Controller inhaler stepping up to medium-dose ICS.",
            follow_up="Pulmonology review in 4 weeks.",
        ),
        dict(
            days_ago_=120,
            chief_complaint="Allergic rhinitis flare — severe nasal congestion, sneezing, itchy eyes",
            severity=4,
            triage_level="STANDARD",
            pain_score=1,
            symptoms=["nasal congestion", "sneezing", "itchy eyes", "mild headache"],
            vitals={"spo2": 99, "hr": 74, "rr": 14, "bp": "122/78"},
            outcome="Cetirizine increased to twice daily during peak pollen. Nasal saline irrigation advised. Intranasal mometasone added for 2 weeks.",
            follow_up="Allergy specialist referral for immunotherapy assessment.",
        ),
        dict(
            days_ago_=60,
            chief_complaint="Eczema flare on bilateral forearms — intense itch, broken skin",
            severity=4,
            triage_level="STANDARD",
            pain_score=2,
            symptoms=["itch", "dry skin", "erythema forearms", "excoriation"],
            vitals={"spo2": 99, "hr": 72, "rr": 15, "bp": "125/80"},
            outcome="Hydrocortisone 1% cream prescribed for 7 days. Emollient BID reinforced. Trigger review: new laundry detergent identified.",
            follow_up="Dermatology follow-up in 6 weeks.",
        ),
        dict(
            days_ago_=14,
            chief_complaint="Chest tightness and mild breathlessness during exam period",
            severity=3,
            triage_level="URGENT",
            pain_score=2,
            symptoms=["chest tightness", "breathlessness on exertion", "mild wheeze"],
            vitals={"spo2": 96, "hr": 91, "rr": 20, "bp": "134/86"},
            outcome="PEFR 72% predicted — moderate obstruction. Salbutamol nebulisation. PEFR post-treatment 88%. Stress-asthma link discussed. Step-up plan if PEFR < 70% again.",
            follow_up="Pulmonology reassessment after exam season.",
        ),
    ]

    _triage_label_map = {
        "VERY URGENT": "Very Urgent", "URGENT": "Urgent",
        "STANDARD": "Standard", "NON-URGENT": "Non-Urgent",
    }
    for t in triage_data:
        th = TriageHistory(
            patient_id          = 131,
            patient_name        = "Aly Lotfy",
            assessed_at         = days_ago(t["days_ago_"]),
            chief_complaint     = t["chief_complaint"],
            severity            = t["severity"],
            severity_label      = _triage_label_map.get(t["triage_level"], t["triage_level"]),
            symptoms_json       = json.dumps(t["symptoms"]),
            vitals_json         = json.dumps(t["vitals"]),
            ai_recommendation   = t["outcome"] + (" Follow-up: " + t["follow_up"] if t.get("follow_up") else ""),
            disposition         = "discharged",
        )
        db.session.add(th)

    db.session.commit()
    print(f"[OK] Inserted 4 triage history records")

    # ── 4. Medication reminders ───────────────────────────────────────────────
    MedicationReminder.query.filter_by(patient_id=131).delete()
    db.session.commit()

    reminders = [
        dict(
            medication_name = "Fluticasone 125 mcg inhaler",
            dosage          = "1 puff",
            frequency       = "Twice daily",
            times           = json.dumps(["08:00", "20:00"]),
            notes           = "Controller inhaler — MUST use even when feeling well. Rinse mouth after use to prevent oral thrush.",
            active          = True,
            start_date      = date.today() - timedelta(days=180),
        ),
        dict(
            medication_name = "Montelukast 10 mg",
            dosage          = "10 mg (1 tablet)",
            frequency       = "Once nightly",
            times           = json.dumps(["22:00"]),
            notes           = "Take at bedtime. Do not stop abruptly. Helps with both asthma and allergic rhinitis.",
            active          = True,
            start_date      = date.today() - timedelta(days=180),
        ),
        dict(
            medication_name = "Vitamin D3 2000 IU",
            dosage          = "2000 IU (1 tablet)",
            frequency       = "Once daily",
            times           = json.dumps(["08:00"]),
            notes           = "Take with breakfast. Maintenance dose after deficiency correction. Recheck levels in 6 months.",
            active          = True,
            start_date      = date.today() - timedelta(days=120),
        ),
        dict(
            medication_name = "Cetirizine 10 mg",
            dosage          = "10 mg (1 tablet)",
            frequency       = "Once daily (seasonal)",
            times           = json.dumps(["08:00"]),
            notes           = "Use during allergy season (March–May, Sep–Oct). Can cause mild drowsiness.",
            active          = False,   # currently off-season
            start_date      = date.today() - timedelta(days=60),
            end_date        = date.today() - timedelta(days=10),
        ),
    ]

    for r in reminders:
        mr = MedicationReminder(
            patient_id      = 131,
            medication_name = r["medication_name"],
            dosage          = r["dosage"],
            frequency       = r["frequency"],
            times           = r["times"],
            notes           = r.get("notes", ""),
            active          = r.get("active", True),
            start_date      = r.get("start_date"),
            end_date        = r.get("end_date"),
        )
        db.session.add(mr)

    db.session.commit()
    print(f"[OK] Inserted 4 medication reminders")

    # ── 5. Conversation memory ────────────────────────────────────────────────
    mem = PatientMemory.query.filter_by(patient_id=131).first()
    if not mem:
        mem = PatientMemory(patient_id=131)
        db.session.add(mem)

    mem.session_count = 7
    mem.updated_at    = days_ago(2)
    mem.summary       = (
        "Aly is a 23-year-old male engineering student managing mild persistent asthma and allergic rhinitis. "
        "He is well-informed about his conditions and uses a controller inhaler (Fluticasone) and Montelukast daily. "
        "Recent concern: exam-period stress triggering asthma exacerbations. He tracks PEFR at home. "
        "Interested in allergen immunotherapy for dust mites. "
        "Pre-hypertension noted — lifestyle advice given, avoiding energy drinks and caffeine excess. "
        "Eczema is mostly controlled with emollients; occasional flares on forearms. "
        "Prefers brief, direct responses. Uses the app mainly for appointment booking and inhaler reminders."
    )
    mem.key_facts = json.dumps({
        "chronic_conditions": ["asthma", "allergic rhinitis", "atopic dermatitis", "pre-hypertension"],
        "allergens":          ["dust mites", "tree pollen", "cat dander", "aspirin", "latex"],
        "controllers":        ["Fluticasone 125 mcg BID", "Montelukast 10 mg nightly"],
        "relievers":          ["Salbutamol 100 mcg PRN"],
        "concerns":           ["exam stress triggering asthma", "pre-hypertension monitoring", "immunotherapy interest"],
        "preferences":        {"language": "en", "communication": "direct and brief"},
        "last_topics":        ["PEFR readings", "stress-asthma link", "allergen immunotherapy", "BP monitoring"],
        "lifestyle_notes":    "Final-year engineering student, moderate activity level, avoids cats and high-pollen areas",
    })

    db.session.commit()
    print(f"[OK] Conversation memory written (7 sessions)")

    # ── 6. Appointments ───────────────────────────────────────────────────────
    # Find appropriate doctors
    def find_doc(specialty):
        return Doctor.query.filter(
            Doctor.specialty.ilike(f"%{specialty}%")
        ).first()

    pulm_doc  = find_doc("Pulmonology")
    derm_doc  = find_doc("Dermatology")
    allergy_doc = find_doc("Allergy") or find_doc("Internal Medicine")

    new_appts = []
    if pulm_doc:
        new_appts.append(Appointment(
            doctor_id        = pulm_doc.id,
            patient_id       = 131,
            patient_name     = "Aly Lotfy",
            appointment_date = date_from_now(7),
            time_slot        = __import__('datetime').time(10, 0),
        ))
        print(f"[OK] Pulmonology appointment -> Dr. {pulm_doc.name} in 7 days")
    if derm_doc:
        new_appts.append(Appointment(
            doctor_id        = derm_doc.id,
            patient_id       = 131,
            patient_name     = "Aly Lotfy",
            appointment_date = date_from_now(21),
            time_slot        = __import__('datetime').time(11, 30),
        ))
        print(f"[OK] Dermatology appointment -> Dr. {derm_doc.name} in 21 days")
    if allergy_doc:
        new_appts.append(Appointment(
            doctor_id        = allergy_doc.id,
            patient_id       = 131,
            patient_name     = "Aly Lotfy",
            appointment_date = date_from_now(35),
            time_slot        = __import__('datetime').time(9, 0),
        ))
        print(f"[OK] Allergy/Internal Medicine appointment -> Dr. {allergy_doc.name} in 35 days")

    for a in new_appts:
        db.session.add(a)
    db.session.commit()

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  PATIENT CASE CREATED SUCCESSFULLY")
    print("=" * 60)
    print(f"  Name        : Aly Lotfy")
    print(f"  ID          : 131")
    print(f"  Case Number : CASE-ALY-2003")
    print(f"  Login       : name='Aly Lotfy'  password='aly2003'")
    print(f"  Conditions  : Asthma, Allergic Rhinitis, Atopic Dermatitis, Pre-HTN")
    print(f"  Vitals      : 8 records (90 days history)")
    print(f"  Triage      : 4 visits (asthma attack, rhinitis flare, eczema, chest tightness)")
    print(f"  Medications : 4 reminders (Fluticasone, Montelukast, Vit D3, Cetirizine)")
    print(f"  Memory      : 7 AI sessions summarised")
    print(f"  Appointments: {len(new_appts)} upcoming")
    print("=" * 60)
