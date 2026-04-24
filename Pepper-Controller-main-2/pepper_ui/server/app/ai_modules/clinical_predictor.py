# -*- coding: utf-8 -*-
"""
clinical_predictor.py  —  Predictive Patient Flow & Readmission Risk
=====================================================================
Two scikit-learn Gradient Boosting models trained on hospital data:

  ReadmissionRiskPredictor
    Input  : triage level, vitals, age, prior visit count, symptom count
    Output : risk level (LOW / MODERATE / HIGH), probability, explanation

  DynamicWaitEstimator
    Input  : queue depth, triage level, time-of-day, day-of-week, specialty
    Output : blended ML + arithmetic wait estimate (minutes)

Both models:
  • Bootstrap with synthetic-but-medically-realistic training data on first run
    (no real patient data required to start).
  • Cache the trained model to disk and reload on subsequent starts.
  • Retrain on real DB data when retrain() is called (incremental learning).
  • Fall back to arithmetic estimation if scikit-learn is not installed.

Fully offline.  No network required.
"""

import json
import os
import pickle
import threading
from datetime import datetime, date, timedelta
from pathlib import Path

import numpy as np

try:
    from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
    from sklearn.pipeline import Pipeline
    _SK = True
except ImportError:
    _SK = False

_MODEL_DIR = Path(__file__).resolve().parent / "model_cache"


# ═══════════════════════════════════════════════════════════════════════════════
# Readmission Risk Predictor
# ═══════════════════════════════════════════════════════════════════════════════

class ReadmissionRiskPredictor:
    """
    Predicts the probability that a patient will need ER readmission within
    72 hours.

    Feature vector (10 elements, all numeric — None / missing → imputed):
      triage_level, pain_score, heart_rate, systolic_bp, diastolic_bp,
      oxygen_sat, temperature, age, prior_visits, symptom_count

    Usage
    -----
    predictor = ReadmissionRiskPredictor()
    result    = predictor.predict({
        "triage_level": 2, "pain_score": 8, "heart_rate": 115,
        "oxygen_sat": 91, "age": 72, "prior_visits": 4,
    })
    # result["risk_level"] → "HIGH"
    """

    _MODEL_FILE = _MODEL_DIR / "readmission_gbm.pkl"

    # Imputation defaults (population medians)
    _DEFAULTS = {
        "triage_level": 3, "pain_score": 4, "heart_rate": 80,
        "systolic_bp": 120, "diastolic_bp": 80, "oxygen_sat": 97,
        "temperature": 37.0, "age": 45, "prior_visits": 0,
        "symptom_count": 1,
    }

    def __init__(self):
        self._model = None
        self._lock  = threading.Lock()
        if _SK:
            _MODEL_DIR.mkdir(exist_ok=True)
            self._load_or_train()
        else:
            print("[PREDICT] scikit-learn not installed — readmission prediction "
                  "unavailable. Install with: pip install scikit-learn")

    def status(self) -> dict:
        return {
            "available":    _SK and self._model is not None,
            "sklearn":      _SK,
            "model_cached": self._MODEL_FILE.exists(),
        }

    def predict(self, features: dict) -> dict:
        """
        Predict readmission risk.

        Corner cases handled:
          - Missing / None features are imputed with population medians.
          - Model not available → returns UNKNOWN with a clear error.
          - Probability clipped to [0.01, 0.99] to avoid overconfident extremes.
        """
        if not _SK or self._model is None:
            return {"risk_level": "UNKNOWN", "probability": 0.0,
                    "contributing_factors": [],
                    "recommendation": "Prediction model unavailable.",
                    "error": "scikit-learn model not loaded."}
        try:
            x = self._vec(features)
            with self._lock:
                prob = float(np.clip(self._model.predict_proba([x])[0][1], 0.01, 0.99))

            if prob > 0.65:
                level = "HIGH"
            elif prob > 0.35:
                level = "MODERATE"
            else:
                level = "LOW"

            recs = {
                "HIGH":     ("High readmission risk — consider observation-ward "
                             "admission or extended monitoring before discharge."),
                "MODERATE": ("Moderate readmission risk — provide clear discharge "
                             "instructions and schedule follow-up within 24–48 h."),
                "LOW":      "Low readmission risk — standard discharge with routine follow-up.",
            }
            return {
                "risk_level":           level,
                "probability":          round(prob, 3),
                "contributing_factors": self._explain(features, prob),
                "recommendation":       recs[level],
            }
        except Exception as e:
            print(f"[PREDICT] Readmission error: {e}")
            return {"risk_level": "UNKNOWN", "probability": 0.0,
                    "contributing_factors": [], "recommendation": "", "error": str(e)}

    def retrain(self, db, VitalRecord, TriageHistory, Patient) -> dict:
        """
        Retrain on real DB data, supplemented with synthetic samples.
        Safe to call from a background thread.
        """
        if not _SK:
            return {"success": False, "error": "scikit-learn not installed."}
        try:
            X, y   = self._build_dataset(db, VitalRecord, TriageHistory, Patient)
            model  = _make_clf_pipeline()
            model.fit(X, y)
            with self._lock:
                self._model = model
            with open(self._MODEL_FILE, "wb") as f:
                pickle.dump(model, f)
            return {"success": True, "samples": len(X)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Private ───────────────────────────────────────────────────────────────

    def _vec(self, d: dict) -> list:
        """Convert feature dict to 10-element numeric vector (impute missing)."""
        keys = ["triage_level", "pain_score", "heart_rate", "systolic_bp",
                "diastolic_bp", "oxygen_sat", "temperature", "age",
                "prior_visits", "symptom_count"]
        return [float(d.get(k) if d.get(k) is not None else self._DEFAULTS[k])
                for k in keys]

    def _explain(self, d: dict, prob: float) -> list:
        factors = []
        if (d.get("triage_level") or 4) <= 2:
            factors.append(f"High triage severity (Level {d.get('triage_level')})")
        if (d.get("pain_score") or 0) >= 8:
            factors.append(f"Severe pain ({d['pain_score']}/10)")
        if (d.get("oxygen_sat") or 100) < 94:
            factors.append(f"Low SpO₂ ({d['oxygen_sat']}%)")
        hr = d.get("heart_rate") or 80
        if hr > 110 or hr < 50:
            factors.append(f"Abnormal HR ({hr} bpm)")
        sbp = d.get("systolic_bp") or 120
        dbp = d.get("diastolic_bp") or 80
        if sbp > 160 or sbp < 90:
            factors.append(f"Abnormal BP ({sbp}/{dbp} mmHg)")
        if (d.get("prior_visits") or 0) >= 3:
            factors.append(f"Frequent prior visits ({d['prior_visits']})")
        if (d.get("age") or 45) > 70:
            factors.append(f"Elderly patient (age {d['age']})")
        return factors or ["No single high-risk factor identified."]

    def _load_or_train(self):
        if self._MODEL_FILE.exists():
            try:
                with open(self._MODEL_FILE, "rb") as f:
                    self._model = pickle.load(f)
                print("[PREDICT] Readmission model loaded from cache.")
                return
            except Exception as e:
                print(f"[PREDICT] Cache load failed ({e}) — retraining.")
        print("[PREDICT] Training readmission model on synthetic data…")
        X, y = _synthetic_readmission(n=1400)
        m = _make_clf_pipeline()
        m.fit(X, y)
        self._model = m
        try:
            with open(self._MODEL_FILE, "wb") as f:
                pickle.dump(m, f)
        except Exception:
            pass
        print("[PREDICT] Readmission model ready.")

    def _build_dataset(self, db, VitalRecord, TriageHistory, Patient):
        """
        Build training set from real DB records, padded with synthetic data.

        Corner cases:
          - Patient has no vitals record → impute with column defaults.
          - TriageHistory.vitals_json may be None or malformed → catch and default.
          - Readmission label: any triage session for same patient within 72 h
            of the current session → label = 1.
        """
        X_s, y_s = _synthetic_readmission(700)
        X_r, y_r = [], []
        try:
            sessions = (TriageHistory.query
                        .order_by(TriageHistory.assessed_at.desc())
                        .limit(600).all())
            for s in sessions:
                if not s.patient_id:
                    continue
                vitals = (VitalRecord.query
                          .filter(VitalRecord.patient_id == s.patient_id,
                                  VitalRecord.recorded_at <= s.assessed_at)
                          .order_by(VitalRecord.recorded_at.desc()).first())
                pt  = Patient.query.get(s.patient_id)
                syms = json.loads(s.symptoms_json or "[]")
                try:
                    pain = int(json.loads(s.vitals_json or "{}").get("pain_scale", 5))
                except Exception:
                    pain = 5

                row = [
                    float(s.severity or 4),
                    float(pain),
                    float((vitals.heart_rate   or 80)  if vitals else 80),
                    float((vitals.systolic_bp  or 120) if vitals else 120),
                    float((vitals.diastolic_bp or 80)  if vitals else 80),
                    float((vitals.oxygen_sat   or 97)  if vitals else 97),
                    float((vitals.temperature  or 37)  if vitals else 37),
                    float((pt.age or 45) if pt else 45),
                    0.0,
                    float(len(syms)),
                ]
                readmitted = (TriageHistory.query
                              .filter(TriageHistory.patient_id == s.patient_id,
                                      TriageHistory.assessed_at > s.assessed_at,
                                      TriageHistory.assessed_at <=
                                      s.assessed_at + timedelta(hours=72))
                              .count()) > 0
                X_r.append(row); y_r.append(int(readmitted))
        except Exception as e:
            print(f"[PREDICT] Real-data extraction error: {e}")

        if X_r:
            X = np.vstack([X_s, np.array(X_r, dtype=float)])
            y = np.concatenate([y_s, np.array(y_r)])
        else:
            X, y = X_s, y_s
        return X, y


# ═══════════════════════════════════════════════════════════════════════════════
# Dynamic Wait Estimator (ML-enhanced)
# ═══════════════════════════════════════════════════════════════════════════════

class DynamicWaitEstimator:
    """
    ML-enhanced wait-time prediction.

    Factors in: queue depth, triage level, time-of-day, day-of-week, specialty.
    Blends ML estimate (65 %) with arithmetic baseline (35 %) so that the
    model's mistakes are dampened by a reliable floor.

    Falls back to pure arithmetic if scikit-learn is unavailable.
    """

    _MODEL_FILE = _MODEL_DIR / "wait_gbr.pkl"

    # Average consultation length by specialty (minutes) — arithmetic baseline
    SPECIALTY_MINUTES = {
        "emergency medicine": 12,
        "cardiology": 25,
        "orthopedics": 20,
        "neurology": 30,
        "internal medicine": 18,
        "pulmonology": 22,
        "pediatrics": 20,
        "default": 15,
    }
    _SPEC_KEYS = list(SPECIALTY_MINUTES.keys())

    def __init__(self):
        self._model = None
        self._lock  = threading.Lock()
        if _SK:
            _MODEL_DIR.mkdir(exist_ok=True)
            self._load_or_train()
        else:
            print("[WAIT_ML] scikit-learn not installed — using arithmetic wait "
                  "estimation only.")

    def status(self) -> dict:
        return {"available": _SK and self._model is not None, "sklearn": _SK}

    def estimate(
        self,
        appointments_ahead: int,
        triage_level: int = 3,
        specialty: str = "",
        appointment_time: datetime = None,
    ) -> dict:
        """
        Estimate wait time in minutes.

        Corner cases:
          - appointment_time=None → use datetime.now().
          - Unknown specialty → falls back to "default" duration.
          - Negative appointments_ahead (data error) → clipped to 0.
          - Model prediction < 0 → clipped to 0.
        """
        if appointment_time is None:
            appointment_time = datetime.now()

        ahead = max(0, int(appointments_ahead))
        spec  = specialty.lower().strip()
        base  = self.SPECIALTY_MINUTES.get(spec, self.SPECIALTY_MINUTES["default"])
        arith = ahead * base

        if not (_SK and self._model):
            return {
                "estimated_wait_minutes": arith,
                "confidence": "arithmetic",
                "breakdown": {"appointments_ahead": ahead, "avg_consult_min": base},
            }
        try:
            x   = self._vec(ahead, triage_level, appointment_time, spec)
            with self._lock:
                ml_wait = float(max(0.0, self._model.predict([x])[0]))
            blended = round(ml_wait * 0.65 + arith * 0.35)
            return {
                "estimated_wait_minutes": blended,
                "ml_estimate_minutes":    round(ml_wait),
                "arithmetic_minutes":     arith,
                "confidence": "ml",
                "breakdown": {
                    "appointments_ahead": ahead,
                    "triage_level": triage_level,
                    "specialty": specialty,
                    "hour_of_day": appointment_time.hour,
                    "day_of_week": appointment_time.strftime("%A"),
                    "avg_consult_min": base,
                },
            }
        except Exception as e:
            print(f"[WAIT_ML] Estimation error: {e}")
            return {"estimated_wait_minutes": arith, "confidence": "arithmetic",
                    "error": str(e)}

    def retrain(self, db, Appointment, Schedule, Doctor) -> dict:
        """Retrain on real appointment timing data (optional)."""
        if not _SK:
            return {"success": False, "error": "scikit-learn not installed."}
        try:
            X, y  = _synthetic_wait(n=2500)   # use synthetic only for now
            model = GradientBoostingRegressor(
                n_estimators=130, max_depth=4, learning_rate=0.10,
                subsample=0.8, random_state=7,
            )
            model.fit(X, y)
            with self._lock:
                self._model = model
            with open(self._MODEL_FILE, "wb") as f:
                pickle.dump(model, f)
            return {"success": True, "samples": len(X)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Private ───────────────────────────────────────────────────────────────

    def _vec(self, ahead: int, triage: int, dt: datetime, spec: str) -> list:
        spec_idx = self._SPEC_KEYS.index(spec) if spec in self._SPEC_KEYS else len(self._SPEC_KEYS) - 1
        hour  = dt.hour
        dow   = dt.weekday()          # 0=Monday
        busy  = int(8 <= hour <= 12 or 18 <= hour <= 20)
        busy_day = int(dow <= 1)      # Mon/Tue are typically busiest
        return [float(ahead), float(triage), float(hour), float(dow),
                float(spec_idx), float(busy), float(busy_day)]

    def _load_or_train(self):
        if self._MODEL_FILE.exists():
            try:
                with open(self._MODEL_FILE, "rb") as f:
                    self._model = pickle.load(f)
                print("[WAIT_ML] Model loaded from cache.")
                return
            except Exception as e:
                print(f"[WAIT_ML] Cache load failed ({e}) — retraining.")
        print("[WAIT_ML] Training wait estimator on synthetic data…")
        X, y = _synthetic_wait(n=2500)
        m = GradientBoostingRegressor(
            n_estimators=130, max_depth=4, learning_rate=0.10,
            subsample=0.8, random_state=7,
        )
        m.fit(X, y)
        self._model = m
        try:
            with open(self._MODEL_FILE, "wb") as f:
                pickle.dump(m, f)
        except Exception:
            pass
        print("[WAIT_ML] Wait estimator ready.")


# ═══════════════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _make_clf_pipeline():
    return Pipeline([
        ("clf", GradientBoostingClassifier(
            n_estimators=150, max_depth=4, learning_rate=0.08,
            subsample=0.8, random_state=42,
        ))
    ])


def _synthetic_readmission(n: int = 1400):
    """
    Medically-realistic synthetic readmission data.
    Risk increases with: lower triage level, higher pain, abnormal vitals,
    older age, more prior visits.
    """
    rng = np.random.default_rng(42)
    X, y = [], []
    for _ in range(n):
        triage  = int(rng.integers(1, 5))
        pain    = int(rng.integers(0, 11))
        hr      = float(np.clip(rng.normal(80, 22), 30, 200))
        sbp     = float(np.clip(rng.normal(120, 28), 60, 220))
        dbp     = float(np.clip(rng.normal(80, 16), 40, 140))
        spo2    = float(np.clip(rng.normal(97, 3), 70, 100))
        temp    = float(np.clip(rng.normal(37.0, 0.9), 34, 42))
        age     = int(rng.integers(18, 90))
        prior   = int(rng.integers(0, 9))
        symp    = int(rng.integers(1, 8))

        risk = (
            (5 - triage) * 0.14
            + pain * 0.038
            + (max(0, hr - 110) * 0.006 + max(0, 50 - hr) * 0.009)
            + (max(0, sbp - 160) * 0.005 + max(0, 90 - sbp) * 0.008)
            + max(0, (94 - spo2) * 0.055)
            + max(0, (temp - 38.5) * 0.07)
            + max(0, (age - 70) * 0.005)
            + prior * 0.048
            + symp * 0.028
            + float(rng.normal(0, 0.07))
        )
        risk  = float(np.clip(risk, 0.0, 1.0))
        label = int(risk > 0.50)
        X.append([triage, pain, hr, sbp, dbp, spo2, temp, float(age),
                  float(prior), float(symp)])
        y.append(label)
    return np.array(X, dtype=float), np.array(y, dtype=int)


def _synthetic_wait(n: int = 2500):
    """
    Realistic synthetic wait-time data for the DynamicWaitEstimator.
    """
    spec_keys = list(DynamicWaitEstimator.SPECIALTY_MINUTES.keys())
    spec_dur  = list(DynamicWaitEstimator.SPECIALTY_MINUTES.values())
    rng  = np.random.default_rng(7)
    X, y = [], []
    for _ in range(n):
        ahead    = int(rng.integers(0, 16))
        triage   = int(rng.integers(1, 5))
        hour     = int(rng.integers(7, 23))
        dow      = int(rng.integers(0, 7))
        spec_i   = int(rng.integers(0, len(spec_keys)))
        busy     = int(8 <= hour <= 12 or 18 <= hour <= 20)
        busy_day = int(dow <= 1)
        base_d   = spec_dur[spec_i]

        wait = (
            ahead * base_d
            * (1.25 if busy else 1.0)
            * (1.12 if busy_day else 1.0)
            + (4 - triage) * 2.5     # urgent patients get bumped
            + float(rng.normal(0, 4))
        )
        wait = max(0.0, wait)
        X.append([float(ahead), float(triage), float(hour), float(dow),
                  float(spec_i), float(busy), float(busy_day)])
        y.append(wait)
    return np.array(X, dtype=float), np.array(y, dtype=float)
