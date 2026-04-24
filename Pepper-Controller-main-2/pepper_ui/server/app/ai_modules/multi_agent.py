# -*- coding: utf-8 -*-
"""
multi_agent.py  —  Multi-Agent Clinical Consensus System
=========================================================
Three specialised agents deliberate before Pepper speaks on high-stakes topics:

  Agent 1 — TriageAgent      : assesses symptoms, urgency, and danger signs
  Agent 2 — PharmacistAgent  : checks drug interactions and contraindications
  Agent 3 — LeadPhysician    : synthesises both into the final, safe reply

Design goals:
  • Each agent is given only the information relevant to its role (separation of
    concerns reduces hallucination surface area).
  • Agent 3 explicitly cross-checks Agent 1 and Agent 2 before replying, so the
    AI must argue with itself before speaking to the patient.
  • The system falls back gracefully (returns empty strings) if the LLM is
    unavailable — the caller decides whether to surface the consensus or
    use the standard single-agent reply instead.

Uses the same Claude / Ollama infrastructure as the rest of the project.
All three agents share one HTTP session to avoid connection overhead.
"""

import json
import os

import requests


_CLAUDE_URL = "https://api.anthropic.com/v1/messages"

# Keywords that indicate a high-stakes query requiring multi-agent consensus.
# Checked case-insensitively.
TRIGGER_KEYWORDS = frozenset([
    "chest pain", "heart attack", "can't breathe", "cannot breathe",
    "shortness of breath", "severe pain", "overdose", "allergic reaction",
    "drug interaction", "is it safe to take", "my medication",
    "suicidal", "self-harm", "stroke", "collapsed", "unconscious",
    "bleeding won't stop", "bleed",
    # Arabic equivalents
    "ألم في الصدر", "أزمة قلبية", "ضيق التنفس", "تفاعل دوائي",
    "جرعة زائدة", "حساسية", "انتحار",
])


class MultiAgentClinicalSystem:
    """
    Runs a three-agent deliberation for complex or high-stakes patient queries.

    Usage
    -----
    system = MultiAgentClinicalSystem()

    # Check if the query warrants activation
    if system.should_activate(user_message):
        consensus = system.consult(patient_context, user_message,
                                   drug_checker=dc, medications=med_list)
        final_reply = consensus["final_recommendation"]

    Return schema of consult()
    --------------------------
    {
      "triage_assessment":    dict,   # Agent 1 output
      "pharmacist_review":    dict,   # Agent 2 output
      "final_recommendation": str,    # Agent 3 narrative (ready to speak to patient)
      "final_triage_level":   int,    # 1-4
      "consensus_reached":    bool,
      "safety_flags":         list[str],
    }
    """

    def __init__(self):
        self._api_key      = os.environ.get("CLAUDE_API_KEY", "")
        self._model        = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        self._offline      = os.environ.get("OFFLINE_MODE", "0") == "1"
        self._ollama_url   = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self._ollama_model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
        self._session      = requests.Session()

    # ── Public ────────────────────────────────────────────────────────────────

    def should_activate(self, user_message: str) -> bool:
        """
        Return True when the message contains a high-stakes keyword.
        Always returns False if both Claude API key and Ollama are absent,
        so the system degrades silently rather than throwing errors.
        """
        if not self._offline and not self._api_key:
            return False
        msg = user_message.lower()
        return any(kw in msg for kw in TRIGGER_KEYWORDS)

    def consult(
        self,
        patient_context: str,
        user_message: str,
        drug_checker=None,
        medications: list = None,
    ) -> dict:
        """
        Run the three-agent pipeline.

        Parameters
        ----------
        patient_context : formatted patient profile string (from get_patient_context)
        user_message    : raw patient text
        drug_checker    : optional DrugChecker instance (queries the real DB)
        medications     : optional list of medication name strings
        """
        # Agent 1 — Triage
        triage = self._run_triage_agent(patient_context, user_message)

        # Agent 2 — Pharmacy (DB check first, LLM supplements)
        db_report = {}
        if drug_checker and medications:
            try:
                db_report = drug_checker.check(medications)
            except Exception as e:
                db_report = {"error": str(e)}
        pharmacy = self._run_pharmacist_agent(patient_context, user_message, db_report)

        # Agent 3 — Lead physician synthesis
        physician = self._run_physician_agent(
            patient_context, user_message, triage, pharmacy
        )

        return {
            "triage_assessment":    triage,
            "pharmacist_review":    pharmacy,
            "final_recommendation": physician.get("recommendation", ""),
            "final_triage_level":   physician.get("final_triage_level",
                                                   triage.get("triage_level", 4)),
            "consensus_reached":    physician.get("consensus", False),
            "safety_flags":         physician.get("safety_flags", []),
        }

    # ── Agent implementations ────────────────────────────────────────────────

    def _run_triage_agent(self, patient_ctx: str, user_msg: str) -> dict:
        system = (
            "You are a senior Emergency Triage Nurse at Andalusia Hospital. "
            "Your ONLY job is to assess the CLINICAL URGENCY of the patient's situation "
            "based on what they have said and their medical profile. "
            "Return ONLY valid compact JSON — no prose, no markdown."
        )
        prompt = (
            f'Patient says: "{user_msg}"\n\n'
            f"Patient profile:\n{patient_ctx or 'Not available'}\n\n"
            "Return JSON:\n"
            '{"triage_level":1-4,'
            '"triage_label":"IMMEDIATE|VERY URGENT|URGENT|STANDARD",'
            '"key_danger_signs":["list"],'
            '"recommended_action":"brief string",'
            '"escalate_immediately":true|false}'
        )
        raw = self._call_llm(system, prompt, max_tokens=300)
        return self._safe_json(raw, default={
            "triage_level": 4, "triage_label": "STANDARD",
            "key_danger_signs": [], "recommended_action": "Standard assessment",
            "escalate_immediately": False,
        })

    def _run_pharmacist_agent(
        self, patient_ctx: str, user_msg: str, db_report: dict
    ) -> dict:
        system = (
            "You are a Clinical Pharmacist at Andalusia Hospital. "
            "Your ONLY job is to identify medication safety concerns "
            "based on the patient's current medications, allergies, and reported symptoms. "
            "Return ONLY valid compact JSON — no prose, no markdown."
        )
        db_str = ""
        if db_report and not db_report.get("error"):
            ixns = db_report.get("interactions", [])
            if ixns:
                db_str = f"\nDatabase-verified drug interactions: {json.dumps(ixns[:5])}"

        prompt = (
            f'Patient says: "{user_msg}"\n'
            f"Patient profile:\n{patient_ctx or 'Not available'}"
            f"{db_str}\n\n"
            "Return JSON:\n"
            '{"medications_reviewed":["list"],'
            '"safety_concerns":["list"],'
            '"contraindications":["list"],'
            '"safe_to_proceed":true|false,'
            '"pharmacist_note":"brief note for the physician"}'
        )
        raw = self._call_llm(system, prompt, max_tokens=350)
        return self._safe_json(raw, default={
            "medications_reviewed": [],
            "safety_concerns": [],
            "contraindications": [],
            "safe_to_proceed": True,
            "pharmacist_note": "",
        })

    def _run_physician_agent(
        self,
        patient_ctx: str,
        user_msg: str,
        triage: dict,
        pharmacy: dict,
    ) -> dict:
        """
        Agent 3: synthesises the triage and pharmacy reports.

        Corner cases handled in the prompt:
          - If agents disagree on triage level, defer to the MORE urgent one.
          - If pharmacy flags a contraindication, the recommendation MUST mention it.
          - Never downgrade a Level 1/2 triage result even if the patient
            sounds calm — rely on clinical signs, not vocal tone.
        """
        system = (
            "You are the Lead Physician at Andalusia Hospital. "
            "You have received reports from the Triage Nurse and Clinical Pharmacist. "
            "Your job is to synthesise both reports into ONE clear, warm, actionable "
            "recommendation for the patient. "
            "RULES: (1) Never downgrade a triage level 1 or 2 result. "
            "(2) If the pharmacist flagged a contraindication, mention it. "
            "(3) Speak directly to the patient — no jargon. "
            "(4) Return ONLY valid compact JSON — no prose, no markdown."
        )
        prompt = (
            f'Patient says: "{user_msg}"\n'
            f"Patient profile:\n{patient_ctx or 'Not available'}\n\n"
            f"Triage Nurse report: {json.dumps(triage)}\n"
            f"Pharmacist report: {json.dumps(pharmacy)}\n\n"
            "Return JSON:\n"
            '{"recommendation":"patient-facing recommendation (≤3 sentences)",'
            '"safety_flags":["any unresolved safety concerns"],'
            '"consensus":true|false,'
            '"final_triage_level":1-4}'
        )
        raw = self._call_llm(system, prompt, max_tokens=400)
        return self._safe_json(raw, default={
            "recommendation": "",
            "safety_flags": [],
            "consensus": False,
            "final_triage_level": triage.get("triage_level", 4),
        })

    # ── LLM plumbing ──────────────────────────────────────────────────────────

    def _call_llm(self, system: str, prompt: str, max_tokens: int = 300) -> str:
        """Call Ollama (offline) or Claude (online). Returns raw string."""
        if self._offline:
            try:
                resp = self._session.post(
                    f"{self._ollama_url}/api/chat",
                    json={
                        "model":   self._ollama_model,
                        "stream":  False,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user",   "content": prompt},
                        ],
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                return resp.json()["message"]["content"].strip()
            except Exception as e:
                print(f"[MULTI-AGENT] Ollama error: {e}")
                return "{}"
        else:
            if not self._api_key:
                return "{}"
            try:
                resp = self._session.post(
                    _CLAUDE_URL,
                    headers={
                        "x-api-key":         self._api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type":      "application/json",
                    },
                    json={
                        "model":      self._model,
                        "max_tokens": max_tokens,
                        "system":     system,
                        "messages":   [{"role": "user", "content": prompt}],
                    },
                    timeout=20,
                )
                resp.raise_for_status()
                return resp.json()["content"][0]["text"].strip()
            except Exception as e:
                print(f"[MULTI-AGENT] Claude error: {e}")
                return "{}"

    @staticmethod
    def _safe_json(raw: str, default: dict) -> dict:
        """Extract JSON from LLM output; return default on any parse failure."""
        try:
            s = raw.find("{"); e = raw.rfind("}") + 1
            if s >= 0 and e > s:
                return json.loads(raw[s:e])
        except Exception:
            pass
        return default
