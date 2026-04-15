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
        self.api_key = os.environ.get("CLAUDE_API_KEY", "")
        self.model   = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        self.url     = "https://api.anthropic.com/v1/messages"

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
        if not text or not self.api_key:
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
            resp = requests.post(
                self.url,
                headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": self.model, "max_tokens": 150,
                      "system": system, "messages": [{"role": "user", "content": prompt}]},
                timeout=10
            )
            text_out = resp.json()["content"][0]["text"].strip()
            # Extract JSON from response
            start = text_out.find("{")
            end   = text_out.rfind("}") + 1
            result = json.loads(text_out[start:end])
            return result
        except Exception as e:
            print(f"[SENTIMENT] Error: {e}")
            return self._neutral()

    def _neutral(self):
        return {"sentiment": "calm", "score": 0.0, "alert": False, "reason": ""}
