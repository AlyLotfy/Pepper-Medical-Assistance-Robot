# -*- coding: utf-8 -*-
"""
medical_ner.py - Medical Named Entity Recognition
Uses Claude to extract medical entities from patient text:
  symptoms, body parts, conditions, medications, allergies.
"""
import os
import json
import requests


class MedicalNER:
    def __init__(self):
        self.api_key = os.environ.get("CLAUDE_API_KEY", "")
        self.model   = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        self.url     = "https://api.anthropic.com/v1/messages"

    def extract(self, text):
        """
        Extract medical entities from patient message.
        Returns dict:
          {
            symptoms:    ["chest pain", "shortness of breath"],
            body_parts:  ["chest", "left arm"],
            conditions:  ["hypertension"],
            medications: ["aspirin"],
            severity:    "mild|moderate|severe"
          }
        """
        if not text or not self.api_key:
            return self._empty()

        system = (
            "You are a clinical NLP system. Extract medical entities from patient text. "
            "Return ONLY valid JSON. No markdown, no explanation."
        )
        prompt = (
            f'Patient text: "{text}"\n\n'
            "Extract and return JSON:\n"
            '{"symptoms": [], "body_parts": [], "conditions": [], "medications": [], '
            '"severity": "mild|moderate|severe|unknown"}'
        )

        try:
            resp = requests.post(
                self.url,
                headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": self.model, "max_tokens": 300,
                      "system": system, "messages": [{"role": "user", "content": prompt}]},
                timeout=10
            )
            text_out = resp.json()["content"][0]["text"].strip()
            start = text_out.find("{")
            end   = text_out.rfind("}") + 1
            return json.loads(text_out[start:end])
        except Exception as e:
            print(f"[NER] Error: {e}")
            return self._empty()

    def _empty(self):
        return {"symptoms": [], "body_parts": [], "conditions": [],
                "medications": [], "severity": "unknown"}
