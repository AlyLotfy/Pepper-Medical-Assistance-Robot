# -*- coding: utf-8 -*-
"""
medication_reminder.py - Medication Reminder Scheduler
=======================================================
FULLY OFFLINE — pure SQLite scheduling.
No network required.

Features:
  - Create / update / delete reminders per patient
  - Check which reminders are due within the next 30 minutes
  - Return all active reminders for a patient
"""
import json
from datetime import datetime, date


class MedicationReminderManager:
    """
    Manages medication reminders stored in the MedicationReminder SQLite table.
    All operations are pure DB queries — no network required.
    """

    def __init__(self, db, reminder_model):
        self.db    = db
        self.Model = reminder_model

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def add(self, patient_id, medication_name, dosage, frequency,
            times, start_date=None, end_date=None, notes=None):
        """
        Create a new reminder.
        times: list of "HH:MM" strings, e.g. ["08:00", "20:00"]
        Returns {"success": True, "id": int, "medication": str}
        """
        times_json = json.dumps(times) if isinstance(times, list) else str(times)
        if start_date is None:
            start_date = date.today()
        r = self.Model(
            patient_id=patient_id,
            medication_name=medication_name,
            dosage=dosage or "",
            frequency=frequency or "",
            times=times_json,
            active=True,
            start_date=start_date,
            end_date=end_date,
            notes=notes or "",
        )
        self.db.session.add(r)
        self.db.session.commit()
        return {"success": True, "id": r.id, "medication": medication_name}

    def get_all(self, patient_id, active_only=True):
        """Return all (active) reminders for a patient as a list of dicts."""
        q = self.Model.query.filter_by(patient_id=patient_id)
        if active_only:
            q = q.filter_by(active=True)
        return [self._to_dict(r) for r in q.order_by(self.Model.created_at).all()]

    def deactivate(self, reminder_id, patient_id):
        """Soft-delete a reminder (keeps history)."""
        r = self.Model.query.filter_by(id=reminder_id, patient_id=patient_id).first()
        if not r:
            return {"success": False, "error": "Reminder not found."}
        r.active = False
        self.db.session.commit()
        return {"success": True}

    def delete(self, reminder_id, patient_id):
        """Hard-delete a reminder."""
        r = self.Model.query.filter_by(id=reminder_id, patient_id=patient_id).first()
        if not r:
            return {"success": False, "error": "Reminder not found."}
        self.db.session.delete(r)
        self.db.session.commit()
        return {"success": True}

    # ------------------------------------------------------------------
    # Due-check
    # ------------------------------------------------------------------
    def get_due(self, patient_id, window_minutes=30):
        """
        Return reminders due within the next `window_minutes` minutes.
        Compares current time against each stored HH:MM time slot.
        Fully offline.
        """
        now   = datetime.now()
        today = date.today()
        due   = []

        for r in self.get_all(patient_id, active_only=True):
            # Skip if past end_date
            if r["end_date"]:
                try:
                    if today > date.fromisoformat(r["end_date"]):
                        continue
                except Exception:
                    pass
            for t_str in r.get("times", []):
                try:
                    h, m   = map(int, t_str.split(":")[:2])
                    due_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    diff   = (due_dt - now).total_seconds()
                    if 0 <= diff <= window_minutes * 60:
                        entry = dict(r)
                        entry["due_in_minutes"] = int(diff / 60)
                        entry["due_time"]        = t_str
                        due.append(entry)
                except Exception:
                    pass
        return due

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _to_dict(self, r) -> dict:
        times = []
        try:
            times = json.loads(r.times) if r.times else []
        except Exception:
            times = [r.times] if r.times else []
        return {
            "id":         r.id,
            "medication": r.medication_name,
            "dosage":     r.dosage,
            "frequency":  r.frequency,
            "times":      times,
            "active":     r.active,
            "start_date": str(r.start_date) if r.start_date else None,
            "end_date":   str(r.end_date)   if r.end_date   else None,
            "notes":      r.notes,
        }
