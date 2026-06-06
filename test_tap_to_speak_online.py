# -*- coding: utf-8 -*-
"""
test_tap_to_speak_online.py — ONLINE (Claude API) version of the
full patient interaction test for Pepper.

Same 16 scenarios as test_tap_to_speak.py, but adds pre-flight checks
that REFUSE to run unless the server is configured for online mode
(Anthropic Claude). Parallel in spirit to test_offline.py but for the
chat_ai / tap-to-speak post-Whisper pipeline.

PRE-FLIGHT CHECKS (run before any scenario)
-------------------------------------------
  1. Server reachable at /api/health
  2. Server reports offline_mode == False
  3. Outbound reachability to api.anthropic.com
  4. CLAUDE_API_KEY / ANTHROPIC_API_KEY visible in test env
     (advisory only — the server holds the real key)
  5. Smoke test: a single short /api/chat_ai turn returns under 20s
     (Claude is typically <5s; >20s suggests fall-through to offline
      or a misconfigured route)

If any HARD check fails, the test exits BEFORE running scenarios so the
user doesn't waste time on a misconfigured run.

HOW TO RUN
----------
    # Terminal 1 — start the server in ONLINE mode
    python main.py --server-only

    # Terminal 2 — run the online test
    python test_tap_to_speak_online.py
    python test_tap_to_speak_online.py --only new_patient,returning_patient
    python test_tap_to_speak_online.py --fast
    python test_tap_to_speak_online.py --save online_results.json

All other CLI flags are passed through to test_tap_to_speak.main().
"""

from __future__ import print_function
import os
import sys
import time

import requests

# NOTE: do not wrap sys.stdout/stderr here — importing test_tap_to_speak
# already does that on Windows. Wrapping twice closes the underlying buffer
# at GC time and produces "I/O operation on closed file" on exit.

# Reuse the entire scenario suite + main() from the agnostic test.
import test_tap_to_speak as base


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
SMOKE_TIMEOUT_S       = 20.0   # /api/chat_ai must answer within this on Claude
ANTHROPIC_REACH_HOST  = "https://api.anthropic.com"
ANTHROPIC_REACH_TIMEOUT_S = 5.0


# ---------------------------------------------------------------------------
# PRE-FLIGHT CHECKS
# ---------------------------------------------------------------------------
def _check_health(base_url):
    """Return (ok, health_dict_or_msg)."""
    try:
        r = requests.get(base_url + "/api/health", timeout=10)
        r.raise_for_status()
        return True, r.json()
    except Exception as e:
        return False, str(e)


def _check_anthropic_reachable():
    """Best-effort check for outbound HTTPS to api.anthropic.com.
    A 401 or 404 from the host counts as 'reachable' — we just want to
    know the network path is open, not that auth works.
    """
    try:
        r = requests.get(ANTHROPIC_REACH_HOST,
                         timeout=ANTHROPIC_REACH_TIMEOUT_S)
        return True, "HTTP %d" % r.status_code
    except requests.exceptions.SSLError as e:
        return False, "SSL error: %s" % e
    except requests.exceptions.ConnectionError as e:
        return False, "connection error: %s" % e
    except requests.exceptions.Timeout:
        return False, "timeout after %ss" % ANTHROPIC_REACH_TIMEOUT_S
    except Exception as e:
        return False, "error: %s" % e


def _check_smoke(c):
    """One-turn chat ping. Returns (ok, elapsed_s, detail)."""
    t0 = time.time()
    try:
        r = c.chat("hello", lang="en", history=[])
        elapsed = time.time() - t0
        ans = (r.get("answer") or "").strip()
        if not ans:
            return False, elapsed, "empty answer"
        if elapsed > SMOKE_TIMEOUT_S:
            return False, elapsed, "answer took %.1fs (> %.0fs limit)" % (
                elapsed, SMOKE_TIMEOUT_S)
        return True, elapsed, "answer in %.2fs" % elapsed
    except Exception as e:
        return False, time.time() - t0, "exception: %s" % e


def _print_banner(text):
    bar = "=" * 78
    print("\n" + bar)
    print(text)
    print(bar)


def preflight(base_url):
    """Run all pre-flight checks. Exits the process on any HARD failure."""
    _print_banner("ONLINE-MODE PRE-FLIGHT — %s" % base_url)

    # 1. Server reachable
    ok, health = _check_health(base_url)
    if not ok:
        print("[FAIL] /api/health unreachable: %s" % health)
        print("       Start the server with: python main.py --server-only")
        sys.exit(2)
    print("[PASS] /api/health reachable")

    # 2. Server in online mode
    if not isinstance(health, dict):
        print("[FAIL] /api/health did not return JSON")
        sys.exit(2)
    offline_mode = bool(health.get("offline_mode", False))
    if offline_mode:
        print("[FAIL] Server is in OFFLINE mode (offline_mode=True).")
        print("       Restart WITHOUT the --offline flag, or unset OFFLINE_MODE.")
        print("       For offline coverage use test_offline.py.")
        sys.exit(2)
    print("[PASS] Server reports offline_mode=False (online / Claude path)")

    # 3. Whisper readiness (advisory) — affects /api/process_audio path,
    # not /api/chat_ai, but a healthy online run should have it loaded.
    if not health.get("whisper_ready"):
        print("[WARN] whisper_ready=False — /api/process_audio (real-audio "
              "tap-to-speak) will fail. /api/chat_ai (text path) still works.")
    else:
        print("[PASS] whisper_ready=True")

    # 4. Outbound to api.anthropic.com (hard — without this Claude won't work)
    ok, detail = _check_anthropic_reachable()
    if not ok:
        print("[FAIL] Cannot reach api.anthropic.com from this host: %s" % detail)
        print("       The SERVER must reach Claude. If the server is on a")
        print("       different machine and that machine has internet, you can")
        print("       skip this check by exporting SKIP_ANTHROPIC_REACH=1.")
        if os.environ.get("SKIP_ANTHROPIC_REACH") != "1":
            sys.exit(2)
        print("       SKIP_ANTHROPIC_REACH=1 set — continuing anyway.")
    else:
        print("[PASS] api.anthropic.com reachable (%s)" % detail)

    # 5. API key visibility (advisory)
    has_key = bool(os.environ.get("CLAUDE_API_KEY") or
                   os.environ.get("ANTHROPIC_API_KEY"))
    if has_key:
        print("[PASS] CLAUDE_API_KEY / ANTHROPIC_API_KEY visible in test env")
    else:
        print("[WARN] No CLAUDE_API_KEY in test env — server may still have it "
              "loaded from its own .env. The smoke test below will confirm.")

    # 6. Smoke test — one short turn, must return non-empty under SMOKE_TIMEOUT_S
    print("[INFO] Running smoke test: one-turn chat 'hello' ...")
    c = base.PepperClient(base_url)
    ok, elapsed, detail = _check_smoke(c)
    if not ok:
        print("[FAIL] Smoke test failed: %s" % detail)
        print("       This usually means the server has no working Claude key,")
        print("       or chat_ai silently fell back to an error reply.")
        sys.exit(2)
    print("[PASS] Smoke test: %s" % detail)
    if elapsed > 8.0:
        print("[WARN] Response took %.1fs — Claude usually answers in 1-5s. "
              "Server may be cold-starting or rate-limited." % elapsed)

    print("[INFO] All pre-flight checks passed. Starting full scenario suite.\n")


# ---------------------------------------------------------------------------
# ENTRY
# ---------------------------------------------------------------------------
def main():
    # If the user just wants --help / -h, defer entirely to base.main()
    # so they see usage without having to start a server first.
    if "--help" in sys.argv or "-h" in sys.argv:
        base.main()
        return

    # Parse only the URL out of argv ahead of time so we can preflight
    # against the same URL the suite will use; leave the full argv for
    # base.main() to re-parse.
    base_url = base._load_base_url()
    for i, a in enumerate(sys.argv):
        if a == "--url" and i + 1 < len(sys.argv):
            base_url = sys.argv[i + 1]
        elif a.startswith("--url="):
            base_url = a.split("=", 1)[1]

    preflight(base_url)

    # Hand off to the comprehensive scenario runner. main() calls sys.exit().
    base.main()


if __name__ == "__main__":
    main()
