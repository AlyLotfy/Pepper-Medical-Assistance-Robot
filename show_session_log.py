#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
show_session_log.py
===================
Terminal viewer for Pepper's session event log.

Shows what each robot function actually did — what the patient said,
what Pepper replied, whether bookings landed in the database, triage
urgency levels, login outcomes, navigation results, etc.

Usage:
    python show_session_log.py                    # today's log
    python show_session_log.py --date 2026-04-18  # specific date
    python show_session_log.py --last 20          # last 20 events
    python show_session_log.py --filter booking   # only booking events
    python show_session_log.py --follow           # live tail (refresh every 3 s)
    python show_session_log.py --summary          # counts only, no detail
    python show_session_log.py --list             # list all available log dates
"""

from __future__ import print_function
import os
import sys
import json
import time
import argparse
import datetime

# ─────────────────────────── ANSI COLORS ────────────────────────────────────

def _supports_color():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

_COLOR = _supports_color()

def _c(code, text):
    return ("\033[%sm%s\033[0m" % (code, text)) if _COLOR else text

def green(t):   return _c("32;1", t)
def yellow(t):  return _c("33;1", t)
def red(t):     return _c("31;1", t)
def cyan(t):    return _c("36;1", t)
def magenta(t): return _c("35;1", t)
def blue(t):    return _c("34;1", t)
def bold(t):    return _c("1",    t)
def dim(t):     return _c("2",    t)

# ─────────────────────────── PATHS ──────────────────────────────────────────

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR  = os.path.join(ROOT_DIR, "session_logs")

# ─────────────────────────── ACTION DISPLAY CONFIG ──────────────────────────

# Maps action name → (label, color_fn)
ACTION_META = {
    "voice_interaction":    ("[VOICE]",       cyan),
    "chat_message":         ("[CHAT]",        blue),
    "appointment_booked":   ("[BOOKING]",     green),
    "appointment_cancelled":("[CANCELLED]",   yellow),
    "triage_assessed":      ("[TRIAGE]",      magenta),
    "patient_login":        ("[LOGIN]",       cyan),
    "patient_logout":       ("[LOGOUT]",      dim),
    "patient_signup":       ("[SIGNUP]",      green),
    "face_login":           ("[FACE LOGIN]",  cyan),
    "face_enroll":          ("[FACE ENROLL]", green),
    "navigation_started":   ("[NAV START]",   blue),
    "navigation_done":      ("[NAV DONE]",    green),
    "navigation_failed":    ("[NAV FAIL]",    red),
    "voice_recorded":       ("[MIC]",         dim),
    "tool_call":            ("[TOOL]",        dim),
}

def _action_label(action):
    meta = ACTION_META.get(action)
    if meta:
        label, color = meta
        return color("%-14s" % label)
    return dim("%-14s" % ("[%s]" % action[:12]))

# ─────────────────────────── EVENT RENDERER ─────────────────────────────────

def _ts(ts_str):
    """Return HH:MM:SS from ISO timestamp string."""
    try:
        return ts_str[11:19]
    except Exception:
        return "??:??:??"


def _patient(ev):
    name = ev.get("patient_name") or ""
    pid  = ev.get("patient_id")  or ""
    if name and pid:
        return "%-20s" % ("%s [%s]" % (name, pid))
    elif name:
        return "%-20s" % name
    return "%-20s" % dim("Guest")


def _ok(ev):
    return green("✓") if ev.get("success") else red("✗")


def _dur(ev):
    ms = ev.get("duration_ms")
    if ms is None:
        return ""
    return dim("  %.0f ms" % ms)


def render_event(ev, verbose=True):
    """Return a list of lines for one event."""
    lines   = []
    action  = ev.get("action", "event")
    details = ev.get("details", {})
    ts      = _ts(ev.get("ts", ""))
    ok      = _ok(ev)
    eid     = dim("#%s" % ev.get("id", "?"))

    # ── Header line ──────────────────────────────────────────
    header = "  %s  %s  %s  %s  %s" % (
        dim(ts), _action_label(action), _patient(ev), ok, eid)
    lines.append(header)

    if not verbose:
        return lines

    # ── Detail lines (action-specific) ───────────────────────
    indent = "           "  # align under the action label

    if action in ("voice_interaction", "chat_message"):
        said    = details.get("user_said", "")
        replied = details.get("ai_replied", "")
        lang    = details.get("lang", "")
        sent    = details.get("sentiment", "")
        tools   = details.get("tools_used") or []

        if said:
            lines.append("%s  Said:    %s" % (indent, bold('"%s"' % said)))
        if replied:
            lines.append("%s  Replied: %s" % (indent, '"%s"' % replied))

        meta_parts = []
        if lang:    meta_parts.append("lang=%s" % lang)
        if sent:    meta_parts.append("sentiment=%s" % sent)
        if tools:   meta_parts.append("tools: %s" % " → ".join(t for t in tools if t))
        if meta_parts:
            lines.append("%s  %s%s" % (indent, dim("  ·  ".join(meta_parts)), _dur(ev)))

        if not ev.get("success"):
            err = ev.get("error", "unknown error")
            lines.append("%s  %s" % (indent, red("Error: %s" % err)))

    elif action == "appointment_booked":
        doctor  = details.get("doctor", "?")
        spec    = details.get("specialty", "")
        date    = details.get("date", "?")
        t       = details.get("time", "?")
        appt_id = details.get("appointment_id")
        db_tag  = green("  DB #%s" % appt_id) if appt_id else ""
        lines.append("%s  Doctor:  %s  %s" % (indent, bold(doctor), dim("(%s)" % spec) if spec else ""))
        lines.append("%s  Date:    %s  %s%s" % (indent, date, t, db_tag))

    elif action == "appointment_cancelled":
        doctor  = details.get("doctor", "?")
        date    = details.get("date", "?")
        t       = details.get("time", "?")
        appt_id = details.get("appointment_id", "?")
        lines.append("%s  Cancelled: %s  on %s at %s  %s" % (
            indent, bold(doctor), date, t, dim("(was #%s)" % appt_id)))

    elif action == "triage_assessed":
        complaint = details.get("complaint", "")
        pain      = details.get("pain_score", "")
        level     = details.get("level", "?")
        label     = details.get("label", "?")
        color_tag = details.get("color", "")
        dept      = details.get("department", "")
        symptoms  = details.get("symptoms", [])

        # Color-code the triage level
        triage_colors = {1: red, 2: red, 3: yellow, 4: green}
        lcol = triage_colors.get(int(level) if str(level).isdigit() else 0, dim)

        if complaint:
            lines.append('%s  "%s"' % (indent, bold(complaint)))
        if symptoms:
            lines.append("%s  Symptoms: %s" % (indent, ", ".join(symptoms[:5])))
        lines.append("%s  Level %s — %s  [%s]  →  %s" % (
            indent,
            lcol(str(level)),
            lcol(label),
            color_tag.upper() if color_tag else "?",
            bold(dept) if dept else dim("dept unknown")))
        if pain:
            lines.append("%s  Pain score: %s/10" % (indent, pain))

    elif action in ("patient_login", "face_login"):
        if ev.get("success"):
            role = details.get("role", "")
            conf = details.get("confidence")
            tag  = ""
            if conf is not None:
                tag = "  confidence %.0f%%" % (float(conf) * 100)
            if role:
                lines.append("%s  Role: %s%s" % (indent, role, tag))
            elif tag:
                lines.append("%s  %s" % (indent, green(tag.strip())))
        else:
            err  = ev.get("error") or details.get("error", "failed")
            conf = details.get("confidence")
            tag  = ""
            if conf is not None:
                tag = "  (confidence %.0f%%)" % (float(conf) * 100)
            lines.append("%s  %s%s" % (indent, red(err), dim(tag)))

    elif action == "patient_signup":
        role = details.get("role", "")
        lines.append("%s  New %s registered" % (indent, role if role else "user"))

    elif action in ("navigation_started", "navigation_done", "navigation_failed"):
        dest    = details.get("destination", details.get("target", "?"))
        dist    = details.get("distance_m")
        elapsed = details.get("elapsed_s")
        reason  = details.get("reason", "")

        if dest:
            lines.append("%s  Destination: %s" % (indent, bold(dest)))
        info_parts = []
        if dist is not None:
            info_parts.append("distance %.1f m" % float(dist))
        if elapsed is not None:
            info_parts.append("%.0f s" % float(elapsed))
        if info_parts:
            lines.append("%s  %s" % (indent, dim("  ·  ".join(info_parts))))
        if action == "navigation_failed" and reason:
            lines.append("%s  %s" % (indent, red("Reason: %s" % reason)))

    else:
        # Generic: just dump non-empty detail values
        for k, v in sorted(details.items()):
            if v not in (None, "", [], {}):
                val = str(v)
                if len(val) > 120:
                    val = val[:117] + "..."
                lines.append("%s  %s: %s" % (indent, dim(k), val))
        if not ev.get("success"):
            err = ev.get("error", "")
            if err:
                lines.append("%s  %s" % (indent, red("Error: %s" % err)))

    lines.append("")  # blank separator
    return lines


# ─────────────────────────── SUMMARY ────────────────────────────────────────

def render_summary(events, date_str):
    """Print a counts-only summary of the session."""
    from collections import Counter
    counts   = Counter(ev.get("action", "?") for ev in events)
    errors   = sum(1 for ev in events if not ev.get("success"))
    patients = set(ev.get("patient_name") for ev in events if ev.get("patient_name"))

    lines = []
    lines.append("")
    lines.append(bold("  SESSION SUMMARY — %s" % date_str))
    lines.append("  " + "─" * 50)
    lines.append("  Total events  : %s" % bold(str(len(events))))
    lines.append("  Unique patients: %s" % bold(str(len(patients))))
    lines.append("  Errors        : %s" % (red(str(errors)) if errors else green("0")))
    lines.append("")
    lines.append("  Event breakdown:")
    for action, count in sorted(counts.items(), key=lambda x: -x[1]):
        meta  = ACTION_META.get(action)
        label = meta[0] if meta else action
        lines.append("    %-26s %s" % (label, bold(str(count))))
    lines.append("")

    if patients:
        lines.append("  Patients seen:")
        for name in sorted(patients):
            lines.append("    · %s" % name)
    lines.append("")
    return lines


# ─────────────────────────── LOG READING ────────────────────────────────────

def read_log(date_str):
    path = os.path.join(LOG_DIR, "%s.jsonl" % date_str)
    if not os.path.exists(path):
        return [], path
    events = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass
    return events, path


def list_logs():
    if not os.path.isdir(LOG_DIR):
        print(red("  No session_logs directory found at: %s" % LOG_DIR))
        return
    files = sorted(
        f for f in os.listdir(LOG_DIR) if f.endswith(".jsonl")
    )
    if not files:
        print(yellow("  No session logs found yet."))
        return
    print(bold("\n  Available session logs:"))
    for f in files:
        date = f.replace(".jsonl", "")
        path = os.path.join(LOG_DIR, f)
        size = os.path.getsize(path)
        # Count lines quickly
        with open(path, "r") as fh:
            n = sum(1 for l in fh if l.strip())
        print("    %s  —  %s events  (%d bytes)" % (bold(date), n, size))
    print()


# ─────────────────────────── FILTER ─────────────────────────────────────────

FILTER_MAP = {
    "booking":    ["appointment_booked"],
    "cancel":     ["appointment_cancelled"],
    "voice":      ["voice_interaction"],
    "chat":       ["chat_message"],
    "triage":     ["triage_assessed"],
    "login":      ["patient_login", "face_login"],
    "signup":     ["patient_signup"],
    "face":       ["face_login", "face_enroll"],
    "nav":        ["navigation_started", "navigation_done", "navigation_failed"],
    "navigation": ["navigation_started", "navigation_done", "navigation_failed"],
    "error":      None,   # special — show only failures
    "fail":       None,
}

def apply_filter(events, filter_str):
    if not filter_str:
        return events
    lower = filter_str.lower()
    if lower in ("error", "fail"):
        return [ev for ev in events if not ev.get("success")]
    actions = FILTER_MAP.get(lower)
    if actions:
        return [ev for ev in events if ev.get("action") in actions]
    # Fallback: substring match on action name
    return [ev for ev in events if lower in ev.get("action", "")]


# ─────────────────────────── MAIN DISPLAY ───────────────────────────────────

def display(date_str, last_n, filter_str, summary_only, verbose):
    events, log_path = read_log(date_str)

    if not events:
        print(yellow("\n  No events logged for %s" % date_str))
        print(dim("  (Log path: %s)" % log_path))
        print()
        return 0

    events = apply_filter(events, filter_str)
    if last_n:
        events = events[-last_n:]

    # ── Header ──────────────────────────────────────────────
    total    = len(events)
    errors   = sum(1 for ev in events if not ev.get("success"))
    patients = len(set(ev.get("patient_name") for ev in events if ev.get("patient_name")))
    bookings = sum(1 for ev in events if ev.get("action") == "appointment_booked" and ev.get("success"))
    triages  = sum(1 for ev in events if ev.get("action") == "triage_assessed")

    print("")
    print("═" * 68)
    print(bold("  PEPPER SESSION LOG — %s" % date_str))

    stats = []
    stats.append("%d events" % total)
    if patients:   stats.append("%d patient%s" % (patients, "s" if patients != 1 else ""))
    if bookings:   stats.append("%s bookings confirmed" % green(str(bookings)))
    if triages:    stats.append("%d triage%s" % (triages, "s" if triages != 1 else ""))
    if errors:     stats.append("%s error%s" % (red(str(errors)), "s" if errors != 1 else ""))
    else:          stats.append(green("0 errors"))
    if filter_str: stats.append("filter: %s" % yellow(filter_str))

    print("  " + dim("  ·  ".join(stats)))
    print("═" * 68)

    if summary_only:
        for line in render_summary(events, date_str):
            print(line)
        return total

    # ── Event list ───────────────────────────────────────────
    print()
    for ev in events:
        for line in render_event(ev, verbose=verbose):
            print(line)

    # ── Footer summary ───────────────────────────────────────
    print("─" * 68)
    if errors:
        print(red("  %d error%s found — rerun with --filter error to focus on failures" % (
            errors, "s" if errors != 1 else "")))
    else:
        print(green("  All %d events completed successfully" % total))
    print()
    return total


# ─────────────────────────── FOLLOW MODE ────────────────────────────────────

def follow_mode(date_str, filter_str, verbose):
    """Tail the log live, printing new events as they arrive."""
    log_path = os.path.join(LOG_DIR, "%s.jsonl" % date_str)
    print(bold("\n  [FOLLOW] Watching %s  (Ctrl+C to stop)\n" % log_path))

    seen = 0
    try:
        while True:
            if os.path.exists(log_path):
                with open(log_path, "r") as f:
                    all_lines = [l.strip() for l in f if l.strip()]
                new_lines = all_lines[seen:]
                for line in new_lines:
                    try:
                        ev = json.loads(line)
                        if not filter_str or apply_filter([ev], filter_str):
                            for out_line in render_event(ev, verbose=verbose):
                                print(out_line)
                    except Exception:
                        pass
                seen = len(all_lines)
            time.sleep(2.0)
    except KeyboardInterrupt:
        print(dim("\n  [FOLLOW] Stopped."))


# ─────────────────────────── ENTRY POINT ────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Show Pepper session log — what the robot did and whether it worked")
    parser.add_argument("--date",    default=datetime.date.today().strftime("%Y-%m-%d"),
                        help="Log date (YYYY-MM-DD, default: today)")
    parser.add_argument("--last",    type=int, default=0,
                        help="Show only the last N events")
    parser.add_argument("--filter",  default="",
                        help="Filter by type: booking, voice, chat, triage, login, nav, face, error")
    parser.add_argument("--follow",  action="store_true",
                        help="Live-tail the log (refresh every 2 s)")
    parser.add_argument("--summary", action="store_true",
                        help="Show counts summary only, no event detail")
    parser.add_argument("--list",    action="store_true",
                        help="List all available log dates")
    parser.add_argument("--compact", action="store_true",
                        help="One-line per event, no detail block")
    args = parser.parse_args()

    if args.list:
        list_logs()
        return

    if not os.path.isdir(LOG_DIR):
        print(yellow("\n  session_logs/ directory not found at: %s" % LOG_DIR))
        print(dim("  It will be created automatically when the Flask server logs its first event."))
        print()
        return

    if args.follow:
        follow_mode(args.date, args.filter, verbose=not args.compact)
    else:
        display(args.date, args.last, args.filter,
                summary_only=args.summary, verbose=not args.compact)


if __name__ == "__main__":
    main()
