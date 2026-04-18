"""
session_logger.py
=================
Thread-safe, append-only session event logger for the Pepper robot system.

Each robot action (voice interaction, appointment booking, triage, login,
navigation, etc.) is recorded as a single JSON line in:

    <project_root>/session_logs/YYYY-MM-DD.jsonl

One file per day.  Readable by show_session_log.py.

Usage inside app.py:
    from session_logger import log_event

    log_event(
        action       = "appointment_booked",
        patient_name = "Ahmed",
        patient_id   = "P001",
        success      = True,
        duration_ms  = 45,
        details      = {"doctor": "Dr. Smith", "date": "2026-04-20", "time": "10:00",
                        "appointment_id": 42}
    )
"""

import os
import json
import uuid
import threading
import datetime

_lock    = threading.Lock()
_LOG_DIR = None


# ── Canonical action labels ─────────────────────────────────
VOICE_INTERACTION   = "voice_interaction"
CHAT_MESSAGE        = "chat_message"
APPOINTMENT_BOOKED  = "appointment_booked"
APPOINTMENT_CANCEL  = "appointment_cancelled"
TRIAGE_ASSESSED     = "triage_assessed"
PATIENT_LOGIN       = "patient_login"
PATIENT_LOGOUT      = "patient_logout"
PATIENT_SIGNUP      = "patient_signup"
FACE_LOGIN          = "face_login"
FACE_ENROLL         = "face_enroll"
NAVIGATION_STARTED  = "navigation_started"
NAVIGATION_DONE     = "navigation_done"
NAVIGATION_FAILED   = "navigation_failed"
VOICE_RECORDED      = "voice_recorded"
TOOL_CALL           = "tool_call"
GENERIC             = "event"


def _resolve_log_dir():
    """Walk up from this file to find the project root and return session_logs/ path."""
    global _LOG_DIR
    if _LOG_DIR is not None:
        return _LOG_DIR

    # app.py → app/ → server/ → pepper_ui/ → Pepper-Controller-main-2/ → project_root/
    here = os.path.dirname(os.path.abspath(__file__))
    # Go 4 levels up to reach "Gradution Project/"
    root = here
    for _ in range(4):
        root = os.path.dirname(root)

    log_dir = os.path.join(root, "session_logs")
    try:
        os.makedirs(log_dir)
    except OSError:
        pass  # already exists

    _LOG_DIR = log_dir
    return _LOG_DIR


def log_event(action, patient_name=None, patient_id=None, success=True,
              duration_ms=None, details=None, error=None):
    """
    Append one event to today's session log.

    Parameters
    ----------
    action       : str   — one of the constants above, or any descriptive string
    patient_name : str   — display name of the patient / user
    patient_id   : str   — ID from the DB, or None for guests
    success      : bool  — did the function achieve its intended goal?
    duration_ms  : int   — how long the operation took (optional)
    details      : dict  — action-specific payload (see examples in app.py)
    error        : str   — error message on failure (optional)

    Never raises — all exceptions are silently swallowed so logging never
    breaks the actual robot function.
    """
    try:
        entry = {
            "id":           str(uuid.uuid4())[:8],
            "ts":           datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:23],
            "action":       action,
            "patient_name": patient_name,
            "patient_id":   str(patient_id) if patient_id is not None else None,
            "success":      bool(success),
            "duration_ms":  int(duration_ms) if duration_ms is not None else None,
            "details":      details or {},
        }
        if error:
            entry["error"] = str(error)

        today    = datetime.datetime.now().strftime("%Y-%m-%d")
        log_path = os.path.join(_resolve_log_dir(), "%s.jsonl" % today)

        with _lock:
            with open(log_path, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    except Exception:
        pass  # logging must never interrupt robot operation
