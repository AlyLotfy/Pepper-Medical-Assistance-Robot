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
        self.api_key      = os.environ.get("CLAUDE_API_KEY", "")
        self.model        = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        self.claude_url   = "https://api.anthropic.com/v1/messages"
        self.offline      = os.environ.get("OFFLINE_MODE", "0") == "1"
        self.ollama_url   = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

    def _call_llm(self, system, prompt, max_tokens=300):
        """Call Ollama (offline) or Claude (online)."""
        if self.offline:
            try:
                resp = requests.post(
                    f"{self.ollama_url}/api/chat",
                    json={"model": self.ollama_model, "stream": False,
                          "messages": [{"role": "system", "content": system},
                                       {"role": "user", "content": prompt}]},
                    timeout=20
                )
                return resp.json()["message"]["content"].strip()
            except Exception as e:
                print(f"[NER] Ollama error: {e}")
                return ""
        else:
            try:
                resp = requests.post(
                    self.claude_url,
                    headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                             "content-type": "application/json"},
                    json={"model": self.model, "max_tokens": max_tokens,
                          "system": system, "messages": [{"role": "user", "content": prompt}]},
                    timeout=10
                )
                return resp.json()["content"][0]["text"].strip()
            except Exception as e:
                print(f"[NER] Claude error: {e}")
                return ""

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
        if not text or (not self.api_key and not self.offline):
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
            text_out = self._call_llm(system, prompt, max_tokens=300)
            start = text_out.find("{")
            end   = text_out.rfind("}") + 1
            return json.loads(text_out[start:end])
        except Exception as e:
            print(f"[NER] Error: {e}")
            return self._empty()

    def _empty(self):
        return {"symptoms": [], "body_parts": [], "conditions": [],
                "medications": [], "severity": "unknown"}
