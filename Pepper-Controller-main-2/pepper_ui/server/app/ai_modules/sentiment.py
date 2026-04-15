# -*- coding: utf-8 -*-
"""
sentiment.py - Sentiment & Distress Analyzer
Uses Claude to detect patient emotional state from chat messages.
Returns sentiment label, distress score, and whether to alert staff.
"""
import os
import json
import requests


class SentimentAnalyzer:
    def __init__(self):
        self.api_key      = os.environ.get("CLAUDE_API_KEY", "")
        self.model        = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        self.claude_url   = "https://api.anthropic.com/v1/messages"
        self.offline      = os.environ.get("OFFLINE_MODE", "0") == "1"
        self.ollama_url   = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

    def _call_llm(self, system, prompt, max_tokens=150):
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
                print(f"[SENTIMENT] Ollama error: {e}")
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
                print(f"[SENTIMENT] Claude error: {e}")
                return ""

    def analyze(self, text, lang="en"):
        """
        Analyze emotional state of a patient message.
        Returns dict:
          {
            sentiment: "calm" | "anxious" | "frustrated" | "distressed" | "pain",
            score: 0.0-1.0  (1.0 = most severe),
            alert: bool     (True if staff should be notified),
            reason: str
          }
        """
        if not text or (not self.api_key and not self.offline):
            return self._neutral()

        system = (
            "You are a medical sentiment analyzer. Analyze the patient's message and return ONLY valid JSON. "
            "No explanation, no markdown, just the JSON object."
        )
        prompt = (
            f'Patient message: "{text}"\n\n'
            "Return JSON with these exact fields:\n"
            '{"sentiment": "calm|anxious|frustrated|distressed|pain", '
            '"score": 0.0-1.0, '
            '"alert": true|false, '
            '"reason": "one sentence explanation"}'
        )

        try:
            text_out = self._call_llm(system, prompt, max_tokens=150)
            start = text_out.find("{")
            end   = text_out.rfind("}") + 1
            return json.loads(text_out[start:end])
        except Exception as e:
            print(f"[SENTIMENT] Error: {e}")
            return self._neutral()

    def _neutral(self):
        return {"sentiment": "calm", "score": 0.0, "alert": False, "reason": ""}
