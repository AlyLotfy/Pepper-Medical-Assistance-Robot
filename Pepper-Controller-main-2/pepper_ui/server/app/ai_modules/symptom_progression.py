# -*- coding: utf-8 -*-
"""
symptom_progression.py - Symptom Progression Tracker
=====================================================
Records per-patient symptom entries over time.
Provides trend analysis:
  OFFLINE (OFFLINE_MODE=1): Ollama qwen2.5:7b
  ONLINE:                   Claude API
  NO INTERNET:              Rule-based fallback text
"""
import os
import json
import requests
from datetime import datetime


class SymptomProgressionTracker:
    """
    Tracks how a patient's symptoms change over multiple sessions.
    Stores entries in the SymptomHistory SQLite table.
    Provides AI (or rule-based) trend summaries.
    """

    SEVERITY_ORDER = {"mild": 1, "moderate": 2, "severe": 3}

    def __init__(self, db, history_model):
        self.db    = db
        self.Model = history_model
        self.api_key      = os.environ.get("CLAUDE_API_KEY", "")
        self.model        = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        self.claude_url   = "https://api.anthropic.com/v1/messages"
        self.offline      = os.environ.get("OFFLINE_MODE", "0") == "1"
        self.ollama_url   = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------
    def record(self, patient_id, symptoms, severity=None,
               context=None, ner_results=None, source="manual") -> int:
        """
        Save a symptom entry.
        symptoms: list of strings or a comma-separated string.
        Returns the new entry's id.
        """
        if isinstance(symptoms, list):
            syms_json = json.dumps(symptoms)
        else:
            syms_json = json.dumps([s.strip() for s in str(symptoms).split(",") if s.strip()])

        entry = self.Model(
            patient_id=patient_id,
            symptoms=syms_json,
            severity=severity,
            ner_results=json.dumps(ner_results) if ner_results else None,
            context=context,
            source=source,
            recorded_at=datetime.utcnow(),
        )
        self.db.session.add(entry)
        self.db.session.commit()
        return entry.id

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def get_history(self, patient_id, limit=15) -> list:
        """Return recent symptom entries for a patient (newest first)."""
        entries = (
            self.Model.query
            .filter_by(patient_id=patient_id)
            .order_by(self.Model.recorded_at.desc())
            .limit(limit)
            .all()
        )
        result = []
        for e in entries:
            syms = []
            try:
                syms = json.loads(e.symptoms) if e.symptoms else []
            except Exception:
                syms = [e.symptoms] if e.symptoms else []
            result.append({
                "id":       e.id,
                "date":     e.recorded_at.strftime("%Y-%m-%d %H:%M"),
                "symptoms": syms,
                "severity": e.severity,
                "context":  e.context,
                "source":   e.source,
            })
        return result

    # ------------------------------------------------------------------
    # Analyze
    # ------------------------------------------------------------------
    def analyze_progression(self, patient_id, patient_name="Patient") -> dict:
        """
        Analyze symptom history and identify trends.
        Returns:
          {
            "analysis": str,
            "source":   "claude" | "ollama" | "no_internet" | "rule_based",
            "trend":    "improving" | "worsening" | "stable" | "unknown",
            "summary":  dict
          }
        """
        history = self.get_history(patient_id, limit=15)
        if not history:
            return {"analysis": "No symptom history recorded yet.",
                    "source": "rule_based", "trend": "unknown", "summary": {}}

        # Rule-based trend from severity
        rule_trend = self._severity_trend(history)

        # Symptom set analysis (oldest is last in list since newest-first)
        all_sets    = [set(h["symptoms"]) for h in history]
        newest_set  = all_sets[0]
        oldest_set  = all_sets[-1] if len(all_sets) > 1 else newest_set
        persistent  = newest_set & oldest_set
        resolved    = oldest_set - newest_set
        new_syms    = newest_set - oldest_set

        summary = {
            "sessions":    len(history),
            "trend":       rule_trend,
            "current":     sorted(newest_set),
            "persistent":  sorted(persistent),
            "resolved":    sorted(resolved),
            "new":         sorted(new_syms),
        }

        # Build AI prompt
        lines = []
        for h in reversed(history):   # chronological order for LLM
            lines.append(
                f"[{h['date']}] {', '.join(h['symptoms'])} "
                f"(severity: {h['severity'] or 'unknown'})"
            )
        prompt = (
            f"Patient: {patient_name}\n"
            f"Symptom history (oldest → newest):\n"
            + "\n".join(lines)
            + "\n\nAnalyze the progression: are symptoms improving, worsening, or stable? "
              "Note any persistent or newly appeared symptoms. Under 60 words."
        )

        if self.offline:
            text = self._call_ollama(prompt)
            if text:
                return {"analysis": text, "source": "ollama",
                        "trend": rule_trend, "summary": summary}
        else:
            if not self._is_online():
                fallback = self._rule_text(rule_trend, summary)
                return {"analysis": fallback + " (No internet for AI analysis.)",
                        "source": "no_internet", "trend": rule_trend, "summary": summary}
            text = self._call_claude(prompt)
            if text:
                return {"analysis": text, "source": "claude",
                        "trend": rule_trend, "summary": summary}

        return {"analysis": self._rule_text(rule_trend, summary),
                "source": "rule_based", "trend": rule_trend, "summary": summary}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _severity_trend(self, history: list) -> str:
        sevs = [h["severity"] for h in history if h["severity"] in self.SEVERITY_ORDER]
        if len(sevs) < 2:
            return "insufficient data"
        # history is newest-first; compare most recent vs oldest
        newest = self.SEVERITY_ORDER[sevs[0]]
        oldest = self.SEVERITY_ORDER[sevs[-1]]
        if newest < oldest:
            return "improving"
        if newest > oldest:
            return "worsening"
        return "stable"

    def _rule_text(self, trend: str, summary: dict) -> str:
        parts = [f"Symptom trend: {trend}."]
        if summary.get("persistent"):
            parts.append(f"Persistent: {', '.join(summary['persistent'])}.")
        if summary.get("resolved"):
            parts.append(f"Resolved: {', '.join(summary['resolved'])}.")
        if summary.get("new"):
            parts.append(f"New symptoms: {', '.join(summary['new'])}.")
        parts.append(f"Total sessions recorded: {summary.get('sessions', 0)}.")
        return " ".join(parts)

    def _is_online(self) -> bool:
        try:
            requests.get("https://api.anthropic.com", timeout=3)
            return True
        except Exception:
            return False

    def _call_ollama(self, prompt) -> str:
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/chat",
                json={"model": self.ollama_model, "stream": False,
                      "messages": [
                          {"role": "system",
                           "content": "You are a clinical assistant. Analyze patient symptom progression. Concise, under 60 words."},
                          {"role": "user", "content": prompt}
                      ]},
                timeout=30,
            )
            return resp.json()["message"]["content"].strip()
        except Exception as e:
            print(f"[PROGRESSION] Ollama error: {e}")
            return None

    def _call_claude(self, prompt) -> str:
        try:
            resp = requests.post(
                self.claude_url,
                headers={"x-api-key": self.api_key,
                         "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": self.model, "max_tokens": 200,
                      "system": "You are a clinical assistant. Analyze patient symptom progression. Be concise and accurate. Under 60 words.",
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=15,
            )
            return resp.json()["content"][0]["text"].strip()
        except Exception as e:
            print(f"[PROGRESSION] Claude error: {e}")
            return None
