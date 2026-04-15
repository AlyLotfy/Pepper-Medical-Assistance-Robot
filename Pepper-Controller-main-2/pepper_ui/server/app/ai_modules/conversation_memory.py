# -*- coding: utf-8 -*-
"""
conversation_memory.py - Long-term Conversational Memory
Summarizes each chat session with Claude and stores per-patient.
On next chat, injects relevant past context into system prompt.
"""
import os
import json
import requests
from datetime import datetime


class ConversationMemory:
    def __init__(self, db, model_class):
        """
        db          - SQLAlchemy db instance
        model_class - the PatientMemory SQLAlchemy model
        """
        self.db    = db
        self.Model = model_class
        self.api_key     = os.environ.get("CLAUDE_API_KEY", "")
        self.claude      = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        self.claude_url  = "https://api.anthropic.com/v1/messages"
        self.offline     = os.environ.get("OFFLINE_MODE", "0") == "1"
        self.ollama_url  = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

    def _call_llm(self, prompt, max_tokens=300):
        """Call Ollama (offline) or Claude (online) with a plain user prompt."""
        if self.offline:
            try:
                resp = requests.post(
                    f"{self.ollama_url}/api/chat",
                    json={"model": self.ollama_model, "stream": False,
                          "messages": [{"role": "user", "content": prompt}]},
                    timeout=30
                )
                return resp.json()["message"]["content"].strip()
            except Exception as e:
                print(f"[MEMORY] Ollama error: {e}")
                return ""
        else:
            try:
                resp = requests.post(
                    self.claude_url,
                    headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                             "content-type": "application/json"},
                    json={"model": self.claude, "max_tokens": max_tokens,
                          "messages": [{"role": "user", "content": prompt}]},
                    timeout=15
                )
                return resp.json()["content"][0]["text"].strip()
            except Exception as e:
                print(f"[MEMORY] Claude error: {e}")
                return ""

    def summarize_and_save(self, patient_id, conversation_history):
        """
        Summarize a completed chat session and store in DB.
        conversation_history: list of {role, parts:[{text}]} dicts
        """
        if not patient_id or not conversation_history or (not self.api_key and not self.offline):
            return

        # Build conversation text
        lines = []
        for msg in conversation_history:
            role = msg.get("role", "user")
            text = msg.get("parts", [{}])[0].get("text", "") if msg.get("parts") else msg.get("content", "")
            if text:
                lines.append(f"{'Patient' if role == 'user' else 'Pepper'}: {text}")

        if len(lines) < 2:
            return

        conv_text = "\n".join(lines)
        prompt = (
            f"Summarize this hospital chatbot conversation in 2-3 sentences, "
            f"focusing on: symptoms mentioned, appointments booked/cancelled, concerns raised, "
            f"and any important medical preferences or information shared by the patient.\n\n"
            f"Conversation:\n{conv_text}"
        )
        summary = self._call_llm(prompt, max_tokens=200)
        if not summary:
            return

        # Extract key facts
        facts_prompt = (
            f"From this conversation summary, extract key medical facts as JSON:\n{summary}\n\n"
            '{"symptoms_mentioned": [], "appointments": [], "concerns": [], "preferences": []}'
        )
        facts_text = self._call_llm(facts_prompt, max_tokens=200)
        try:
            start = facts_text.find("{"); end = facts_text.rfind("}") + 1
            key_facts = json.loads(facts_text[start:end])
        except Exception:
            key_facts = {}

        # Save or update in DB
        existing = self.Model.query.filter_by(patient_id=patient_id).first()
        if existing:
            # Append to history
            existing.summary   = summary
            existing.key_facts = json.dumps(key_facts)
            existing.updated_at = datetime.utcnow()
            existing.session_count = (existing.session_count or 0) + 1
        else:
            record = self.Model(
                patient_id=patient_id,
                summary=summary,
                key_facts=json.dumps(key_facts),
                session_count=1
            )
            self.db.session.add(record)

        self.db.session.commit()
        print(f"[MEMORY] Saved memory for patient {patient_id}.")

    def get_context(self, patient_id):
        """
        Return a context string to inject into Claude system prompt.
        Empty string if no memory exists.
        """
        if not patient_id:
            return ""
        record = self.Model.query.filter_by(patient_id=patient_id).first()
        if not record or not record.summary:
            return ""
        ctx = f"Previous interaction summary: {record.summary}"
        try:
            facts = json.loads(record.key_facts or "{}")
            if facts.get("symptoms_mentioned"):
                ctx += f" Previously reported symptoms: {', '.join(facts['symptoms_mentioned'])}."
            if facts.get("concerns"):
                ctx += f" Patient concerns: {', '.join(facts['concerns'])}."
        except Exception:
            pass
        return ctx
