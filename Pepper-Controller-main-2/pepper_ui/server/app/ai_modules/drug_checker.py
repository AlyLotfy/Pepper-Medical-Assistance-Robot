# -*- coding: utf-8 -*-
"""
drug_checker.py - Drug Interaction Checker
==========================================
OFFLINE:  Queries the local SQLite DrugInteraction table (seeded at startup).
          Supports exact match + case-insensitive partial match.
ONLINE:   If a pair is not in the local DB, optionally queries Claude for
          AI-generated interaction analysis.
FALLBACK: If no internet, returns "No internet — not found in local database."

Usage:
    checker = DrugChecker(db, DrugInteraction, Medication)
    result  = checker.check(["warfarin", "aspirin", "metformin"])
"""
import os
import requests


class DrugChecker:
    """Check drug-drug interactions using local SQLite DB."""

    def __init__(self, db, interaction_model, medication_model):
        self.db            = db
        self.Interaction   = interaction_model
        self.Medication    = medication_model
        self.api_key       = os.environ.get("CLAUDE_API_KEY", "")
        self.model         = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        self.claude_url    = "https://api.anthropic.com/v1/messages"
        self.offline       = os.environ.get("OFFLINE_MODE", "0") == "1"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def check(self, drug_list: list) -> dict:
        """
        Check all pairwise interactions in drug_list.
        Returns:
          {
            "interactions": [...],
            "severity_summary": {"severe": 1, ...},
            "safe": bool,
            "drug_count": int,
            "checked_pairs": int,
            "source": "local_db"
          }
        """
        if not drug_list or len(drug_list) < 2:
            return {"interactions": [], "severity_summary": {},
                    "safe": True, "drug_count": len(drug_list or []),
                    "checked_pairs": 0, "source": "local_db"}

        drugs    = [d.strip().lower() for d in drug_list if d and d.strip()]
        found    = []
        checked  = set()

        for i, a in enumerate(drugs):
            for b in drugs[i + 1:]:
                pair = tuple(sorted([a, b]))
                if pair in checked:
                    continue
                checked.add(pair)
                ix = self._lookup(a, b)
                if ix:
                    found.append(ix)

        sev_counts = {}
        for ix in found:
            s = ix["severity"]
            sev_counts[s] = sev_counts.get(s, 0) + 1

        safe = not any(ix["severity"] in ("severe", "contraindicated") for ix in found)
        return {
            "interactions":    found,
            "severity_summary": sev_counts,
            "safe":            safe,
            "drug_count":      len(drugs),
            "checked_pairs":   len(checked),
            "source":          "local_db",
        }

    def get_drug_info(self, drug_name: str) -> dict:
        """Return drug catalog entry for a drug name (partial match)."""
        try:
            med = self.Medication.query.filter(
                self.Medication.name.ilike(f"%{drug_name}%")
            ).first()
            if not med:
                med = self.Medication.query.filter(
                    self.Medication.generic_name.ilike(f"%{drug_name}%")
                ).first()
            if med:
                return {
                    "name":               med.name,
                    "generic_name":       med.generic_name,
                    "category":           med.category,
                    "dosage_forms":       med.dosage_forms,
                    "side_effects":       med.common_side_effects,
                    "contraindications":  med.contraindications,
                    "pregnancy_category": med.pregnancy_category,
                    "requires_monitoring": med.requires_monitoring,
                    "notes":              med.notes,
                    "found": True,
                }
        except Exception as e:
            print(f"[DRUG] DB lookup error: {e}")
        return {"name": drug_name, "found": False,
                "error": "Drug not found in local catalog."}

    def ai_interaction_check(self, drug_a: str, drug_b: str) -> dict:
        """
        Ask Claude (online) about a drug pair not in the local DB.
        Returns {"analysis": str, "source": str}
        """
        if self.offline:
            return {"analysis":
                    "Offline mode: this drug combination is not in the local database. "
                    "Please consult a pharmacist or physician.",
                    "source": "offline"}
        if not self._is_online():
            return {"analysis":
                    "No internet connection. This drug combination is not in the local database. "
                    "Please consult a pharmacist or physician.",
                    "source": "no_internet"}
        if not self.api_key:
            return {"analysis":
                    "AI analysis unavailable (no API key configured). "
                    "Please consult a pharmacist.",
                    "source": "no_api_key"}
        try:
            resp = requests.post(
                self.claude_url,
                headers={"x-api-key": self.api_key,
                         "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": self.model, "max_tokens": 200,
                      "system": "You are a clinical pharmacist. Concisely describe the interaction between two drugs, its severity, mechanism, and recommendation. Under 80 words.",
                      "messages": [{"role": "user",
                                    "content": f"Drug interaction: {drug_a} + {drug_b}"}]},
                timeout=15,
            )
            text = resp.json()["content"][0]["text"].strip()
            return {"analysis": text, "source": "claude"}
        except Exception as e:
            print(f"[DRUG] Claude error: {e}")
            return {"analysis": "AI analysis failed. Please consult a pharmacist.",
                    "source": "error"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _lookup(self, drug_a: str, drug_b: str):
        """Query SQLite for a drug pair (both orderings, partial match)."""
        try:
            # Exact match
            ix = self.Interaction.query.filter(
                ((self.Interaction.drug_a == drug_a) & (self.Interaction.drug_b == drug_b)) |
                ((self.Interaction.drug_a == drug_b) & (self.Interaction.drug_b == drug_a))
            ).first()
            if not ix:
                # Partial (LIKE) match for brand/generic name variants
                ix = self.Interaction.query.filter(
                    (self.Interaction.drug_a.ilike(f"%{drug_a}%") &
                     self.Interaction.drug_b.ilike(f"%{drug_b}%")) |
                    (self.Interaction.drug_a.ilike(f"%{drug_b}%") &
                     self.Interaction.drug_b.ilike(f"%{drug_a}%"))
                ).first()
            if ix:
                return {
                    "drug_a":          ix.drug_a,
                    "drug_b":          ix.drug_b,
                    "severity":        ix.severity,
                    "description":     ix.description,
                    "recommendation":  ix.recommendation or "",
                    "mechanism":       ix.mechanism or "",
                }
        except Exception as e:
            print(f"[DRUG] Lookup error: {e}")
        return None

    def _is_online(self):
        try:
            requests.get("https://api.anthropic.com", timeout=3)
            return True
        except Exception:
            return False
