# -*- coding: utf-8 -*-
"""
wait_estimator.py - Patient Wait Time Estimator
================================================
FULLY OFFLINE — pure SQLite queries.
No network required.

Estimates wait time by counting earlier appointments for the same doctor on
the same day, multiplied by average consultation duration.
"""
from datetime import date, datetime, time as time_type, timedelta

AVG_CONSULT_MINUTES = 15   # average time per consultation slot


class WaitEstimator:
    """
    Estimates patient wait times and lists available appointment slots.
    All operations are pure DB queries — no network required.
    """

    def __init__(self, db, appointment_model, schedule_model, doctor_model):
        self.db          = db
        self.Appointment = appointment_model
        self.Schedule    = schedule_model
        self.Doctor      = doctor_model

    # ------------------------------------------------------------------
    def estimate_wait(self, doctor_id: int, appointment_date, time_slot) -> dict:
        """
        Estimate wait time for a specific doctor/date/slot.
        Returns:
          {
            "queue_position": int,        # 1-based position in the queue
            "appointments_ahead": int,
            "estimated_wait_minutes": int,
            "note": str
          }
        """
        try:
            appt_date = _to_date(appointment_date)
            appt_time = _to_time(time_slot)

            ahead = self.Appointment.query.filter(
                self.Appointment.doctor_id       == doctor_id,
                self.Appointment.appointment_date == appt_date,
                self.Appointment.time_slot        < appt_time,
            ).count()

            wait = ahead * AVG_CONSULT_MINUTES
            return {
                "queue_position":          ahead + 1,
                "appointments_ahead":      ahead,
                "estimated_wait_minutes":  wait,
                "avg_consult_minutes":     AVG_CONSULT_MINUTES,
                "note": f"Estimated {wait} min wait ({ahead} patient{'s' if ahead != 1 else ''} ahead).",
            }
        except Exception as e:
            return {"error": str(e), "estimated_wait_minutes": None}

    def get_available_slots(self, doctor_id: int, target_date) -> list:
        """
        Return list of available "HH:MM" slots for a doctor on a given date.
        Generates 15-min slots within the doctor's schedule windows,
        then subtracts already-booked slots.
        """
        try:
            d          = _to_date(target_date)
            dow        = d.weekday()           # 0 = Monday
            schedules  = self.Schedule.query.filter_by(
                doctor_id=doctor_id, day_of_week=dow
            ).all()
            if not schedules:
                return []

            booked = {
                _fmt_time(a.time_slot)
                for a in self.Appointment.query.filter_by(
                    doctor_id=doctor_id, appointment_date=d
                ).all()
            }

            slots = []
            for sched in schedules:
                cur = datetime.combine(d, sched.start_time)
                end = datetime.combine(d, sched.end_time)
                while cur < end:
                    s = cur.strftime("%H:%M")
                    if s not in booked:
                        slots.append(s)
                    cur += timedelta(minutes=AVG_CONSULT_MINUTES)
            return slots
        except Exception as e:
            print(f"[WAIT] get_available_slots error: {e}")
            return []

    def doctor_load(self, doctor_id: int, target_date=None) -> dict:
        """Return appointment count and estimated session length for a doctor."""
        if target_date is None:
            target_date = date.today()
        d     = _to_date(target_date)
        count = self.Appointment.query.filter_by(
            doctor_id=doctor_id, appointment_date=d
        ).count()
        doc   = self.Doctor.query.get(doctor_id)
        return {
            "doctor_id":              doctor_id,
            "doctor_name":            doc.name if doc else "Unknown",
            "date":                   str(d),
            "total_appointments":     count,
            "estimated_total_hours":  round(count * AVG_CONSULT_MINUTES / 60, 1),
        }

    def busiest_doctors(self, target_date=None, top_n=5) -> list:
        """Return top N busiest doctors by appointment count for a given date."""
        if target_date is None:
            target_date = date.today()
        d = _to_date(target_date)
        try:
            from sqlalchemy import func
            rows = (
                self.db.session.query(
                    self.Appointment.doctor_id,
                    func.count(self.Appointment.id).label("cnt")
                )
                .filter(self.Appointment.appointment_date == d)
                .group_by(self.Appointment.doctor_id)
                .order_by(func.count(self.Appointment.id).desc())
                .limit(top_n)
                .all()
            )
            result = []
            for doctor_id, cnt in rows:
                doc = self.Doctor.query.get(doctor_id)
                result.append({
                    "doctor_id":    doctor_id,
                    "doctor_name":  doc.name if doc else "Unknown",
                    "specialty":    doc.specialty if doc else "",
                    "appointments": cnt,
                    "est_wait_last_patient_min": cnt * AVG_CONSULT_MINUTES,
                })
            return result
        except Exception as e:
            print(f"[WAIT] busiest_doctors error: {e}")
            return []


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _to_date(val):
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        return date.fromisoformat(val[:10])
    raise ValueError(f"Cannot convert {val!r} to date")


def _to_time(val):
    if isinstance(val, time_type):
        return val
    if isinstance(val, str):
        parts = val.split(":")
        return time_type(int(parts[0]), int(parts[1]))
    raise ValueError(f"Cannot convert {val!r} to time")


def _fmt_time(t) -> str:
    if isinstance(t, time_type):
        return t.strftime("%H:%M")
    return str(t)[:5]
