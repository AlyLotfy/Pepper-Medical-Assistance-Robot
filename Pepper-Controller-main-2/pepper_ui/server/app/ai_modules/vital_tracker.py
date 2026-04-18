# -*- coding: utf-8 -*-
"""
vital_tracker.py - Patient Vital Signs Analysis
=============================================
OFFLINE:  Rule-based alert generation for dangerous vital values.
          Statistical summary (average, min/max, trend) — pure Python.
ONLINE:   AI narrative trend analysis via Claude API.
OFFLINE:  Same analysis via Ollama (OFFLINE_MODE=1).
FALLBACK: If no internet and not offline mode → returns rule-based text.
"""
import os
import json
import requests
from datetime import datetime

# ─── Clinical normal/critical ranges ─────────────────────────────────────────
VITAL_RANGES = {
    "temperature": {
        "label": "Temperature", "unit": "°C",
        "low": 36.1,  "high": 37.9,
        "critical_low": 35.0, "critical_high": 39.5,
    },
    "systolic_bp": {
        "label": "Systolic BP", "unit": "mmHg",
        "low": 90,    "high": 139,
        "critical_low": 80,   "critical_high": 180,
    },
    "diastolic_bp": {
        "label": "Diastolic BP", "unit": "mmHg",
        "low": 60,    "high": 89,
        "critical_low": 50,   "critical_high": 120,
    },
    "heart_rate": {
        "label": "Heart Rate", "unit": "bpm",
        "low": 60,    "high": 100,
        "critical_low": 40,   "critical_high": 150,
    },
    "oxygen_sat": {
        "label": "Oxygen Saturation", "unit": "%",
        "low": 95,    "high": 100,
        "critical_low": 90,   "critical_high": None,
    },
    "respiratory_rate": {
        "label": "Respiratory Rate", "unit": "br/min",
        "low": 12,    "high": 20,
        "critical_low": 8,    "critical_high": 30,
    },
    "blood_glucose": {
        "label": "Blood Glucose", "unit": "mmol/L",
        "low": 4.0,   "high": 7.8,
        "critical_low": 3.0,  "critical_high": 13.9,
    },
    "pain_scale": {
        "label": "Pain Scale", "unit": "/10",
        "low": 0,     "high": 4,
        "critical_low": None, "critical_high": 8,
    },
}


def check_vital_alerts(vitals: dict) -> list:
    """
    Pure offline rule-based vital alert generator.
    vitals: dict with optional keys matching VITAL_RANGES.
    Returns list of alert strings (empty = all normal).
    """
    alerts = []
    for key, val in vitals.items():
        if val is None or key not in VITAL_RANGES:
            continue
        r = VITAL_RANGES[key]
        unit   = r["unit"]
        label  = r["label"]
        # Critical thresholds checked first
        if r["critical_low"] is not None and val < r["critical_low"]:
            alerts.append(
                f"CRITICAL LOW {label}: {val}{unit} — Immediate attention required!"
            )
        elif r["critical_high"] is not None and val > r["critical_high"]:
            alerts.append(
                f"CRITICAL HIGH {label}: {val}{unit} — Immediate attention required!"
            )
        # Abnormal (but not critical)
        elif val < r["low"]:
            alerts.append(
                f"Low {label}: {val}{unit} (normal {r['low']}–{r['high']}{unit})"
            )
        elif r["high"] is not None and val > r["high"]:
            alerts.append(
                f"High {label}: {val}{unit} (normal {r['low']}–{r['high']}{unit})"
            )
    return alerts


def summarize_vitals(records: list) -> dict:
    """
    Compute average, min, max, trend for each vital from a list of records.
    Each record is a dict with optional vital-key fields.
    Fully offline — pure Python math.
    """
    if not records:
        return {}
    keys = list(VITAL_RANGES.keys())
    result = {}
    for k in keys:
        vals = [r[k] for r in records if isinstance(r.get(k), (int, float))]
        if not vals:
            continue
        latest = vals[-1]
        oldest = vals[0]
        avg    = round(sum(vals) / len(vals), 1)
        if len(vals) >= 2:
            if latest < oldest * 0.97:
                trend = "improving" if k in ("pain_scale", "temperature", "systolic_bp",
                                              "diastolic_bp", "blood_glucose") else "decreasing"
            elif latest > oldest * 1.03:
                trend = "worsening" if k in ("pain_scale",) else "increasing"
            else:
                trend = "stable"
        else:
            trend = "single reading"
        result[k] = {
            "label":   VITAL_RANGES[k]["label"],
            "unit":    VITAL_RANGES[k]["unit"],
            "latest":  latest,
            "average": avg,
            "min":     min(vals),
            "max":     max(vals),
            "count":   len(vals),
            "trend":   trend,
        }
    return result


class VitalAnalyzer:
    """
    AI-powered vital trend narrative.
    OFFLINE_MODE=1 → Ollama.
    Online → Claude API.
    No internet → rule-based fallback text.
    """

    def __init__(self):
        self.api_key      = os.environ.get("CLAUDE_API_KEY", "")
        self.model        = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        self.claude_url   = "https://api.anthropic.com/v1/messages"
        self.offline      = os.environ.get("OFFLINE_MODE", "0") == "1"
        self.ollama_url   = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

    def _is_online(self):
        try:
            requests.get("https://api.anthropic.com", timeout=3)
            return True
        except Exception:
            return False

    def _call_llm(self, prompt, max_tokens=250):
        """Route to Ollama (offline) or Claude (online)."""
        if self.offline:
            try:
                resp = requests.post(
                    f"{self.ollama_url}/api/chat",
                    json={"model": self.ollama_model, "stream": False,
                          "messages": [
                              {"role": "system",
                               "content": "You are a clinical assistant analyzing vital sign trends. Be concise and clinically accurate. Under 80 words."},
                              {"role": "user", "content": prompt}
                          ]},
                    timeout=30
                )
                return resp.json()["message"]["content"].strip(), "ollama"
            except Exception as e:
                print(f"[VITALS] Ollama error: {e}")
                return None, "error"
        else:
            if not self.api_key or not self._is_online():
                return None, "no_internet"
            try:
                resp = requests.post(
                    self.claude_url,
                    headers={"x-api-key": self.api_key,
                             "anthropic-version": "2023-06-01",
                             "content-type": "application/json"},
                    json={"model": self.model, "max_tokens": max_tokens,
                          "system": "You are a clinical assistant analyzing vital sign trends. Be concise and clinically accurate. Under 80 words.",
                          "messages": [{"role": "user", "content": prompt}]},
                    timeout=15
                )
                return resp.json()["content"][0]["text"].strip(), "claude"
            except Exception as e:
                print(f"[VITALS] Claude error: {e}")
                return None, "error"

    def analyze_trends(self, patient_name: str, summary: dict,
                       recent_alerts: list) -> dict:
        """
        Generate a narrative for vital trends.
        Returns {"analysis": str, "source": str}
        """
        if not summary:
            return {"analysis": "No vital history available to analyze.", "source": "rule_based"}

        # Build rule-based notes regardless of LLM availability
        notes = []
        for k, v in summary.items():
            if v["trend"] not in ("stable", "single reading"):
                notes.append(f"{v['label']}: {v['trend']} (latest {v['latest']}{v['unit']})")
        if recent_alerts:
            prefix = "Active alerts: " + "; ".join(recent_alerts[:3]) + ". "
        else:
            prefix = ""

        prompt = (
            f"Patient: {patient_name}\n"
            f"Vital sign trend summary:\n{json.dumps(summary, indent=2)}\n"
            f"Recent alerts: {recent_alerts or 'none'}\n\n"
            f"Provide a brief clinical assessment of these trends. "
            f"Note concerns and any recommended actions."
        )
        text, source = self._call_llm(prompt)
        if text:
            return {"analysis": text, "source": source}
        if source == "no_internet":
            fallback = prefix + (
                f"Vital trends: {', '.join(notes)}." if notes
                else "All monitored vitals appear stable."
            ) + " (Internet unavailable for AI analysis.)"
            return {"analysis": fallback, "source": "no_internet"}
        fallback = prefix + (
            f"Vital trends: {', '.join(notes)}." if notes
            else "All monitored vitals appear stable."
        )
        return {"analysis": fallback, "source": "rule_based"}
