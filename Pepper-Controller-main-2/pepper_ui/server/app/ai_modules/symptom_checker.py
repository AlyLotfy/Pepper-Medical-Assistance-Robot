# -*- coding: utf-8 -*-
"""
symptom_checker.py - AI Symptom Checker & Differential Diagnosis
Uses Claude to suggest possible conditions based on symptoms.
"""
import os
import json
import requests


class SymptomChecker:
    def __init__(self):
        self.api_key = os.environ.get("CLAUDE_API_KEY", "")
        self.model   = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        self.url     = "https://api.anthropic.com/v1/messages"

    def check(self, symptoms, patient_ctx="", lang="en"):
        """
        Given a list of symptoms, return possible conditions ranked by likelihood.
        Returns dict:
          {
            conditions: [
              { name, likelihood: "high|medium|low", description, advice, see_doctor: bool }
            ],
            urgency: "immediate|urgent|routine|self-care",
            urgency_reason: str,
            recommended_department: str
          }
        """
        if not symptoms or not self.api_key:
            return self._empty()

        symptom_list = symptoms if isinstance(symptoms, str) else ", ".join(symptoms)
        lang_note = "Respond in Arabic." if lang == "ar" else "Respond in English."

        system = (
            "You are a clinical decision support system at Andalusia Hospital. "
            f"{lang_note} Return ONLY valid JSON. No markdown."
        )
        prompt = f"Symptoms reported: {symptom_list}\n"
        if patient_ctx:
            prompt += f"Patient profile: {patient_ctx}\n"
        prompt += (
            "\nProvide differential diagnosis. Return JSON:\n"
            '{"conditions": [{"name": "", "likelihood": "high|medium|low", '
            '"description": "", "advice": "", "see_doctor": true|false}], '
            '"urgency": "immediate|urgent|routine|self-care", '
            '"urgency_reason": "", "recommended_department": ""}'
        )

        try:
            resp = requests.post(
                self.url,
                headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": self.model, "max_tokens": 600,
                      "system": system, "messages": [{"role": "user", "content": prompt}]},
                timeout=15
            )
            text_out = resp.json()["content"][0]["text"].strip()
            start = text_out.find("{")
            end   = text_out.rfind("}") + 1
            return json.loads(text_out[start:end])
        except Exception as e:
            print(f"[SYMPTOM_CHECK] Error: {e}")
            return self._empty()

    def _empty(self):
        return {"conditions": [], "urgency": "unknown",
                "urgency_reason": "", "recommended_department": "Internal Medicine"}
