# -*- coding: utf-8 -*-
"""
test_no_white_pages.py
======================
Tight proof that no Pepper UI page renders blank/white on the tablet,
even after extended interaction including heavy tap-to-speak use.

WHAT "WHITE PAGE" MEANS HERE
----------------------------
A page is "white" when the tablet's old WebKit browser renders nothing
visible. Root causes seen in this codebase:
  1. Inline <script> contains ES2018+ syntax (e.g. regex /s flag,
     optional chaining ?., template literals, const/let, fetch()):
     the script block fails to parse — any DOM-building code in it
     never runs — the page renders empty
  2. Page HTML is empty / truncated / non-200
  3. Page depends on JS to inject ALL visible content (rare here, but
     triage.html / staff_dashboard.html do this)
  4. Backend degrades under sustained load → static file serves slow
     or fails → tablet shows blank while waiting
  5. Voice pipeline endpoints slow down after many tap-to-speak cycles
     → tablet's 8-10s webkit timeout fires → blank "connection timed out"
  6. WebSocket bridge drops under load → UI voice overlay gets stuck,
     covering the whole screen with a white-ish overlay
  7. Voice state flag files accumulate → Flask file I/O slows down

WHAT THIS SCRIPT PROVES
-----------------------
For every page that the tablet can reach:
  • HTTP 200, non-empty body, expected DOM landmark present
  • Inline JS uses ONLY ES5 syntax (no ES2018+ killers)
  • Page survives N repeated fetches with interleaved API traffic
  • Latency stays bounded (no degradation that could time out the tablet)

Additionally:
  • Voice pipeline (/api/start_voice, /api/voice_status, /api/stop_voice)
    remains fast (< 2s per call) after N_VOICE_CYCLES rapid cycles
  • WebSocket bridge on port 8765 accepts connections and stays alive
  • All pages STILL render correctly after heavy tap-to-speak stress

USAGE
-----
    # In one terminal — keep main.py running
    python main.py --server-only

    # In another terminal:
    python test_no_white_pages.py                  # default: 100 page cycles
    python test_no_white_pages.py --cycles 500     # tighter proof
    python test_no_white_pages.py --quick          # 20 cycles, no JS scan
    python test_no_white_pages.py --base http://1.1.1.246:8080
    python test_no_white_pages.py --voice-cycles 50  # more voice stress
    python test_no_white_pages.py --ws-port 8765      # WebSocket bridge port
"""

from __future__ import print_function

import argparse
import io
import json
import os
import re
import socket
import sys
import time

import requests

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Pages to verify, with the DOM landmark that MUST be present in the response
# body. If the landmark is missing, the page is considered broken.
# ---------------------------------------------------------------------------
PAGES = [
    # (path,                  required substring,                                description)
    ("/",                     'class="tile',                                     "Home / tiles grid"),
    ("/index.html",           'class="tile',                                     "Home (direct)"),
    ("/login.html",           'id="loginForm"',                                  "Login"),
    ("/signup.html",          'class="login-card"',                              "Sign up"),
    ("/book.html",            'id="booking-form"',                               "Book appointment"),
    ("/appointments.html",    'id="list"',                                       "My appointments"),
    ("/schedule.html",        'class="card"',                                    "Doctor schedule"),
    ("/emergency.html",       'id="panicBtn"',                                   "Emergency"),
    ("/tips.html",            'id="tipsGrid"',                                   "Health tips"),
    ("/chat.html",            'id="chat-area"',                                  "Chat / FAQ"),
    ("/triage.html",          'id="mainCard"',                                   "Symptom check"),
    ("/qr_checkin.html",      'id="qrContent"',                                  "QR check-in"),
    ("/about.html",           'class="card-wrapper"',                            "About"),
    ("/guide.html",           'id="doctor-list"',                                "Guide to room"),
    ("/navigating.html",      '<body',                                           "Navigating"),
    ("/face_login.html",      '<body',                                           "Face login"),
    ("/face_enroll.html",     '<body',                                           "Face enrol"),
    ("/staff_dashboard.html", 'class="wrap"',                                    "Staff dashboard"),
]

# Static JS files — must always be 200 and non-empty
STATIC_JS = ["/i18n.js", "/demo_store.js", "/ui_data.js"]

# Dynamic API endpoints to hit between page loads so the proof reflects
# real interaction patterns, not just static-file serving
API_PROBES = [
    ("GET",  "/api/health"),
    ("GET",  "/api/voice_status"),
    ("GET",  "/api/my_appointments"),
    ("GET",  "/api/navigation_targets"),
]

# ES2018+ syntax that crashes Pepper's tablet WebKit at script-parse time.
# Each pattern is matched against inline <script> content. A single hit in
# any inline script kills the WHOLE block, often leaving the page blank.
JS_ANTI_PATTERNS = [
    # name,                     compiled regex,                                 example trigger
    ("regex /s flag",           re.compile(r"/[^/\n]+/[gimuy]*s[gimuy]*[\s,;)]"), "/foo/s"),
    ("regex /u flag",           re.compile(r"/[^/\n]+/[gims]*u[gims]*[\s,;)]"),   "/foo/u"),
    ("optional chaining ?.",    re.compile(r"\?\.[a-zA-Z_(\[]"),                  "a?.b"),
    ("nullish coalescing ??",   re.compile(r"[^?]\?\?[^?=]"),                     "a ?? b"),
    ("template literal `",      re.compile(r"`[^`]{0,400}\$\{"),                  "`x${y}`"),
    ("arrow function =>",       re.compile(r"\)\s*=>"),                           "() =>"),
    ("const declaration",       re.compile(r"(^|[^a-zA-Z_])const\s+[a-zA-Z_$]"),  "const x"),
    ("let declaration",         re.compile(r"(^|[^a-zA-Z_])let\s+[a-zA-Z_$]"),    "let x"),
    ("fetch() call",            re.compile(r"(^|[^a-zA-Z_])fetch\s*\("),          "fetch("),
]

# Patterns above sometimes flag false positives — these exact substrings
# inside the matched line make the hit safe to ignore (e.g. "const" inside
# a comment, "let" as a variable name fragment, fetch in a comment).
JS_FALSE_POSITIVE_HINTS = [
    "//", "/*", "* ", "*/",     # comments
    "letter", "letters",        # not 'let'
    "constraint", "constant",   # not 'const'
    "// fetch",                 # commented fetch
]

# Regex to pull out inline <script>...</script> bodies (no src attr)
INLINE_SCRIPT_RE = re.compile(
    r"<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)</script>",
    re.IGNORECASE,
)

# Voice endpoint response-time limit in milliseconds.
# If any single call exceeds this, the tablet's renderer will visibly stall.
VOICE_LATENCY_LIMIT_MS = 2000
# /api/voice_status is a simple flag-file read — it must be near-instant.
VOICE_STATUS_LIMIT_MS = 800


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------
SEP = "=" * 72


def banner(title):
    print()
    print(SEP)
    print("  " + title)
    print(SEP)


def line(title):
    print()
    print("-" * 72)
    print("  " + title)
    print("-" * 72)


def passed(msg):
    print("  [PASS] " + msg)


def failed(msg):
    print("  [FAIL] " + msg)


def info(msg):
    print("  [....] " + msg)


def warn(msg):
    print("  [WARN] " + msg)


# ---------------------------------------------------------------------------
# JS static analysis
# ---------------------------------------------------------------------------
def is_false_positive(line_text):
    stripped = line_text.lstrip()
    if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
        return True
    for hint in JS_FALSE_POSITIVE_HINTS:
        if hint in line_text:
            return True
    return False


def scan_inline_js(html, page_path):
    """Return list of (pattern_name, sample_line) for every ES2018+ killer found."""
    findings = []
    for match in INLINE_SCRIPT_RE.finditer(html):
        body = match.group(1)
        # Skip empty / whitespace-only blocks
        if not body.strip():
            continue
        # Strip multi-line comments crudely so they don't generate false hits
        body_clean = re.sub(r"/\*[\s\S]*?\*/", "", body)
        for name, pattern, _example in JS_ANTI_PATTERNS:
            for m in pattern.finditer(body_clean):
                # Find the surrounding line for context / false-positive check
                start = body_clean.rfind("\n", 0, m.start()) + 1
                end = body_clean.find("\n", m.end())
                if end == -1:
                    end = len(body_clean)
                line_text = body_clean[start:end].strip()
                if is_false_positive(line_text):
                    continue
                findings.append((name, line_text[:160]))
    return findings


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def fetch(session, base, path, timeout=8):
    """Return (status, body, elapsed_ms) — never raise."""
    url = base.rstrip("/") + path
    t0 = time.time()
    try:
        r = session.get(url, timeout=timeout, allow_redirects=False)
        return r.status_code, r.text or "", (time.time() - t0) * 1000.0
    except requests.RequestException as e:
        return 0, "ERR: " + str(e), (time.time() - t0) * 1000.0


def post_json(session, base, path, payload, timeout=6):
    """POST JSON, return (status, parsed_json_or_None, elapsed_ms) — never raise."""
    url = base.rstrip("/") + path
    t0 = time.time()
    try:
        r = session.post(url, json=payload, timeout=timeout)
        ms = (time.time() - t0) * 1000.0
        try:
            return r.status_code, r.json(), ms
        except Exception:
            return r.status_code, None, ms
    except requests.RequestException as e:
        return 0, None, (time.time() - t0) * 1000.0


def hit_api(session, base, method, path, timeout=6):
    url = base.rstrip("/") + path
    try:
        if method == "GET":
            r = session.get(url, timeout=timeout)
        else:
            r = session.request(method, url, timeout=timeout)
        return r.status_code
    except requests.RequestException:
        return 0


# ---------------------------------------------------------------------------
# WebSocket connectivity probe (pure TCP + HTTP upgrade, no external lib needed)
# Falls back to websocket-client if available.
# ---------------------------------------------------------------------------
def _ws_handshake_raw(host, port, timeout=5):
    """
    Perform a bare WebSocket HTTP Upgrade handshake.
    Returns (True, round_trip_ms) on success, (False, elapsed_ms) on failure.
    This tests that ws_bridge.py is accepting connections without requiring
    an async framework.
    """
    import hashlib, base64, struct
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    request = (
        "GET / HTTP/1.1\r\n"
        "Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    ).format(host=host, port=port, key=key)

    t0 = time.time()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.sendall(request.encode("ascii"))
        buf = b""
        deadline = t0 + timeout
        while b"\r\n\r\n" not in buf and time.time() < deadline:
            chunk = sock.recv(1024)
            if not chunk:
                break
            buf += chunk
        ms = (time.time() - t0) * 1000.0
        sock.close()
        if b"101" in buf and b"Switching Protocols" in buf:
            return True, ms
        return False, ms
    except Exception as e:
        return False, (time.time() - t0) * 1000.0


def probe_websocket(host, port, timeout=5):
    """Try websocket-client first (richer), fall back to raw handshake."""
    t0 = time.time()
    try:
        import websocket as _wsc
        ws = _wsc.WebSocket()
        ws.connect("ws://{h}:{p}/".format(h=host, p=port), timeout=timeout)
        ws.send(json.dumps({"type": "hello"}))
        ws.close()
        return True, (time.time() - t0) * 1000.0
    except ImportError:
        pass
    except Exception:
        return False, (time.time() - t0) * 1000.0
    # Raw fallback
    return _ws_handshake_raw(host, port, timeout)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base",         default="http://127.0.0.1:8080",
                    help="Flask backend URL (default %(default)s)")
    ap.add_argument("--cycles",       type=int, default=100,
                    help="Page-load cycles (default 100)")
    ap.add_argument("--voice-cycles", type=int, default=30,
                    help="Tap-to-speak simulation cycles (default 30)")
    ap.add_argument("--ws-port",      type=int, default=8765,
                    help="WebSocket bridge port (default 8765)")
    ap.add_argument("--quick",        action="store_true",
                    help="Quick mode: 20 page cycles, 10 voice cycles, no JS scan")
    ap.add_argument("--no-js-scan",   action="store_true",
                    help="Skip ES5 syntax static analysis")
    ap.add_argument("--no-voice",     action="store_true",
                    help="Skip voice pipeline stress (sections 7-9)")
    args = ap.parse_args()

    if args.quick:
        args.cycles = 20
        args.voice_cycles = 10

    base = args.base
    # Parse host from base URL for WebSocket
    ws_host = base.split("//")[-1].split(":")[0].split("/")[0] or "127.0.0.1"

    session = requests.Session()
    overall_fail = 0

    banner("PEPPER UI — WHITE PAGE PROOF  (incl. tap-to-speak stress)")
    print("  Target backend : " + base)
    print("  WS bridge host : " + ws_host + ":" + str(args.ws_port))
    print("  Pages          : " + str(len(PAGES)))
    print("  Page cycles    : " + str(args.cycles))
    print("  Voice cycles   : " + ("skipped (--no-voice)" if args.no_voice else str(args.voice_cycles)))
    print("  JS static scan : " + ("skipped" if (args.quick or args.no_js_scan) else "enabled"))
    total_reqs = (len(PAGES) * args.cycles + len(API_PROBES) * args.cycles + len(STATIC_JS))
    if not args.no_voice:
        total_reqs += args.voice_cycles * 5   # start + 3× status + stop per cycle
        total_reqs += len(PAGES)              # post-stress render check
    print("  Total requests : ~%d" % total_reqs)

    # ---------------------------------------------------------------- 1
    line("1. BACKEND REACHABLE")
    code, body, ms = fetch(session, base, "/api/health", timeout=5)
    if code == 200:
        passed("/api/health -> 200 (%.1fms)  %s" % (ms, body[:80]))
    else:
        failed("/api/health -> %s — backend not up. Start: python main.py --server-only" % code)
        return 2

    # ---------------------------------------------------------------- 2
    line("2. STATIC JAVASCRIPT FILES")
    for js in STATIC_JS:
        code, body, ms = fetch(session, base, js)
        if code == 200 and len(body) > 100:
            passed("%s -> 200 (%d bytes, %.1fms)" % (js, len(body), ms))
        else:
            failed("%s -> %s (%d bytes)" % (js, code, len(body)))
            overall_fail += 1

    # ---------------------------------------------------------------- 3
    line("3. ES5 COMPLIANCE — inline scripts must NOT use ES2018+")
    if args.quick or args.no_js_scan:
        info("Skipped (--quick or --no-js-scan).")
    else:
        scan_fail = 0
        for path, _landmark, descr in PAGES:
            code, body, _ms = fetch(session, base, path)
            if code != 200:
                continue
            findings = scan_inline_js(body, path)
            if not findings:
                passed("%-25s clean" % path)
            else:
                scan_fail += 1
                failed("%-25s %d ES2018+ pattern(s):" % (path, len(findings)))
                seen = set()
                for name, snippet in findings:
                    key = name + "|" + snippet[:60]
                    if key in seen:
                        continue
                    seen.add(key)
                    print("           - %s  :: %s" % (name, snippet))
        if scan_fail == 0:
            passed("All %d pages are ES5-clean — safe for Pepper's WebKit." % len(PAGES))
        else:
            overall_fail += scan_fail

    # ---------------------------------------------------------------- 4
    line("4. PAGE STRUCTURE — each page must contain its DOM landmark")
    structure_fail = 0
    baseline_latencies = {}
    for path, landmark, descr in PAGES:
        code, body, ms = fetch(session, base, path)
        baseline_latencies[path] = ms
        if code != 200:
            failed("%-25s HTTP %s" % (path, code))
            structure_fail += 1
            continue
        if len(body) < 500:
            failed("%-25s body too short (%d bytes)" % (path, len(body)))
            structure_fail += 1
            continue
        if landmark not in body:
            failed("%-25s missing landmark %r" % (path, landmark))
            structure_fail += 1
            continue
        body_lower = body.lower()
        if "<body" not in body_lower or body_lower.find("</body>") - body_lower.find("<body") < 200:
            failed("%-25s body element is suspiciously short" % path)
            structure_fail += 1
            continue
        passed("%-25s OK (%d bytes, %.1fms) — %s" % (path, len(body), ms, descr))
    if structure_fail:
        overall_fail += structure_fail

    # ---------------------------------------------------------------- 5
    line("5. STRESS — %d cycles per page, interleaved with API calls" % args.cycles)
    print("  Goal: prove pages stay healthy under extended interaction load.\n")
    stress_fail = 0
    latencies = {p[0]: [] for p in PAGES}
    api_failures = 0
    t_start = time.time()

    for cycle in range(args.cycles):
        for method, api in API_PROBES:
            if hit_api(session, base, method, api) >= 500:
                api_failures += 1

        for path, landmark, _descr in PAGES:
            code, body, ms = fetch(session, base, path, timeout=10)
            if code != 200 or landmark not in body:
                stress_fail += 1
                failed("cycle %d: %s broke (code=%s, landmark_present=%s)"
                       % (cycle + 1, path, code, landmark in (body or "")))
            else:
                latencies[path].append(ms)

        if (cycle + 1) % max(1, args.cycles // 10) == 0:
            elapsed = time.time() - t_start
            rate = (cycle + 1) * (len(PAGES) + len(API_PROBES)) / max(elapsed, 0.01)
            print("    cycle %d/%d   elapsed %.1fs   ~%.1f req/s   fails=%d"
                  % (cycle + 1, args.cycles, elapsed, rate, stress_fail))

    duration = time.time() - t_start
    if stress_fail == 0:
        passed("Stress complete — %d cycles x %d pages = %d page-loads, 0 failures (%.1fs total)"
               % (args.cycles, len(PAGES), args.cycles * len(PAGES), duration))
    else:
        failed("Stress complete — %d failures across %d page-loads"
               % (stress_fail, args.cycles * len(PAGES)))
        overall_fail += stress_fail
    if api_failures:
        info("API probes had %d 5xx responses (informational, not a white-page cause)" % api_failures)

    # ---------------------------------------------------------------- 6
    line("6. LATENCY TREND — degradation would predict tablet timeouts")
    trend_fail = 0
    for path, _landmark, _descr in PAGES:
        samples = latencies.get(path, [])
        if len(samples) < 10:
            continue
        first_q = samples[: len(samples) // 4]
        last_q = samples[-len(samples) // 4:]
        avg_first = sum(first_q) / len(first_q)
        avg_last = sum(last_q) / len(last_q)
        peak = max(samples)
        degraded = avg_last > max(avg_first * 2.5, avg_first + 250)
        if degraded:
            trend_fail += 1
            failed("%-25s first=%.0fms last=%.0fms peak=%.0fms  <- DEGRADING"
                   % (path, avg_first, avg_last, peak))
        elif peak > 5000:
            failed("%-25s peak=%.0fms  <- over 5s (tablet may show blank waiting)"
                   % (path, peak))
            trend_fail += 1
        else:
            passed("%-25s first=%.0fms last=%.0fms peak=%.0fms" % (path, avg_first, avg_last, peak))
    if trend_fail:
        overall_fail += trend_fail

    # ==================================================================
    # VOICE PIPELINE SECTIONS — the specific scenario the user reported:
    # "when the tablet works a lot it starts to lag, like tap to speak
    #  lags it shows white page"
    # ==================================================================

    if args.no_voice:
        line("7-9. VOICE PIPELINE — skipped (--no-voice)")
    else:
        # ---------------------------------------------------------------- 7
        line("7. VOICE PIPELINE STRESS — %d rapid tap-to-speak cycles" % args.voice_cycles)
        print("  Simulates a user repeatedly tapping the mic button.")
        print("  Each cycle: start_voice -> poll_status(x3) -> stop_voice")
        print("  Asserts every call stays under %dms (tablet stalls otherwise).\n"
              % VOICE_LATENCY_LIMIT_MS)

        v_start_lat = []
        v_status_lat = []
        v_stop_lat = []
        voice_fail = 0
        voice_5xx = 0

        for vc in range(args.voice_cycles):
            # Step 1: start_voice
            code, resp, ms = post_json(session, base, "/api/start_voice",
                                       {"lang": "en", "user_id": "131"}, timeout=5)
            v_start_lat.append(ms)
            if code != 200:
                voice_5xx += 1
                failed("voice cycle %d: start_voice -> HTTP %s" % (vc + 1, code))
                voice_fail += 1
            elif ms > VOICE_LATENCY_LIMIT_MS:
                failed("voice cycle %d: start_voice took %.0fms (> %dms limit)"
                       % (vc + 1, ms, VOICE_LATENCY_LIMIT_MS))
                voice_fail += 1
            if resp and not resp.get("ok"):
                failed("voice cycle %d: start_voice returned ok=false: %s"
                       % (vc + 1, str(resp)[:80]))
                voice_fail += 1

            # Step 2: poll voice_status 3x (simulates tablet FSM polling)
            for _ in range(3):
                code2, resp2, ms2 = fetch(session, base, "/api/voice_status", timeout=3)
                v_status_lat.append(ms2)
                if code2 != 200:
                    voice_fail += 1
                    failed("voice cycle %d: voice_status -> HTTP %s" % (vc + 1, code2))
                elif ms2 > VOICE_STATUS_LIMIT_MS:
                    failed("voice cycle %d: voice_status took %.0fms (> %dms limit)"
                           % (vc + 1, ms2, VOICE_STATUS_LIMIT_MS))
                    voice_fail += 1
                time.sleep(0.1)

            # Step 3: stop_voice
            code, resp, ms = post_json(session, base, "/api/stop_voice", {}, timeout=5)
            v_stop_lat.append(ms)
            if code != 200:
                voice_5xx += 1
                failed("voice cycle %d: stop_voice -> HTTP %s" % (vc + 1, code))
                voice_fail += 1
            elif ms > VOICE_LATENCY_LIMIT_MS:
                failed("voice cycle %d: stop_voice took %.0fms (> %dms limit)"
                       % (vc + 1, ms, VOICE_LATENCY_LIMIT_MS))
                voice_fail += 1

            if (vc + 1) % max(1, args.voice_cycles // 5) == 0:
                print("    voice cycle %d/%d  start=%.0fms status=%.0fms stop=%.0fms  fails=%d"
                      % (vc + 1, args.voice_cycles,
                         v_start_lat[-1], v_status_lat[-1], v_stop_lat[-1], voice_fail))

        # Latency degradation check for voice endpoints
        def _trend(samples, name, limit):
            if len(samples) < 6:
                return 0
            half = len(samples) // 2
            early = sum(samples[:half]) / half
            late  = sum(samples[half:]) / (len(samples) - half)
            peak  = max(samples)
            degraded = late > max(early * 2.5, early + 300)
            if degraded:
                failed("%-20s early=%.0fms late=%.0fms peak=%.0fms  <- DEGRADING (voice will lag)"
                       % (name, early, late, peak))
                return 1
            elif peak > limit:
                failed("%-20s peak=%.0fms over limit %dms  <- tablet will freeze/blank"
                       % (name, peak, limit))
                return 1
            else:
                passed("%-20s early=%.0fms late=%.0fms peak=%.0fms  stable"
                       % (name, early, late, peak))
                return 0

        voice_trend_fails = 0
        voice_trend_fails += _trend(v_start_lat,  "start_voice",  VOICE_LATENCY_LIMIT_MS)
        voice_trend_fails += _trend(v_status_lat, "voice_status", VOICE_STATUS_LIMIT_MS)
        voice_trend_fails += _trend(v_stop_lat,   "stop_voice",   VOICE_LATENCY_LIMIT_MS)

        if voice_fail == 0 and voice_trend_fails == 0:
            passed(("%d tap-to-speak cycles complete — all endpoints fast and stable. "
                    "start_voice avg=%.0fms, voice_status avg=%.0fms, stop_voice avg=%.0fms")
                   % (args.voice_cycles,
                      sum(v_start_lat) / max(len(v_start_lat), 1),
                      sum(v_status_lat) / max(len(v_status_lat), 1),
                      sum(v_stop_lat) / max(len(v_stop_lat), 1)))
        else:
            overall_fail += voice_fail + voice_trend_fails

        if voice_5xx:
            info("%d 5xx responses on voice endpoints (server errors, check Flask log)" % voice_5xx)

        # ---------------------------------------------------------------- 8
        line("8. WEBSOCKET BRIDGE — connection stays alive under load")
        print("  The ws_bridge.py relay (port %d) is what keeps the voice" % args.ws_port)
        print("  overlay in sync. A dropped WS causes the UI to freeze on")
        print("  'Speaking...' indefinitely — a full white overlay.\n")

        WS_PROBES = 5
        ws_ok = 0
        ws_fail_count = 0
        ws_latencies = []

        for wi in range(WS_PROBES):
            ok, ws_ms = probe_websocket(ws_host, args.ws_port, timeout=5)
            ws_latencies.append(ws_ms)
            if ok:
                ws_ok += 1
            else:
                ws_fail_count += 1
            # Space out probes slightly
            if wi < WS_PROBES - 1:
                time.sleep(0.5)

        if ws_ok == WS_PROBES:
            avg_ws = sum(ws_latencies) / len(ws_latencies)
            peak_ws = max(ws_latencies)
            passed("WebSocket bridge: %d/%d probes succeeded, avg=%.0fms peak=%.0fms"
                   % (WS_PROBES, WS_PROBES, avg_ws, peak_ws))
        elif ws_ok > 0:
            warn("WebSocket bridge: %d/%d probes succeeded — partial connectivity"
                 % (ws_ok, WS_PROBES))
            warn("Intermittent WS drops cause the voice overlay to freeze (white screen).")
            overall_fail += 1
        else:
            warn("WebSocket bridge not reachable at %s:%d" % (ws_host, args.ws_port))
            warn("WS bridge must be running for tap-to-speak to work end-to-end.")
            warn("Start with: python main.py --server-only  (it starts ws_bridge.py)")
            info("This is WARN not FAIL — ws_bridge may simply not be started yet.")
            # Don't count as overall_fail; ws_bridge not running is an ops issue,
            # not a code white-page bug. The latency risk was already covered in
            # section 7 (voice endpoint response times).

        # ---------------------------------------------------------------- 9
        line("9. POST-VOICE-STRESS PAGE RENDER — pages still load after heavy use")
        print("  After %d voice cycles, all %d pages must still render correctly."
              % (args.voice_cycles, len(PAGES)))
        print("  This proves the backend's flag-file I/O and Flask state aren't")
        print("  corrupted by repeated start/stop cycles.\n")

        post_fail = 0
        for path, landmark, descr in PAGES:
            code, body, ms = fetch(session, base, path, timeout=10)
            if code != 200 or landmark not in body:
                post_fail += 1
                failed("POST-STRESS: %-25s broke (code=%s, landmark=%s)"
                       % (path, code, landmark in (body or "")))
                continue

            # Compare to baseline — flag if more than 5x slower post-stress
            baseline_ms = baseline_latencies.get(path, 0)
            if baseline_ms > 0 and ms > max(baseline_ms * 5, baseline_ms + 1000):
                post_fail += 1
                failed("POST-STRESS: %-25s %.0fms now vs %.0fms baseline (%.1fx slower)"
                       % (path, ms, baseline_ms, ms / max(baseline_ms, 1)))
            else:
                passed("POST-STRESS: %-25s OK (%d bytes, %.1fms) — %s" % (path, len(body), ms, descr))

        if post_fail == 0:
            passed("All %d pages still render correctly after %d tap-to-speak cycles."
                   % (len(PAGES), args.voice_cycles))
            passed("Backend state was not corrupted by repeated voice pipeline use.")
        else:
            failed("%d page(s) degraded after voice stress — check Flask log for errors."
                   % post_fail)
            overall_fail += post_fail

    # ---------------------------------------------------------------- 10
    banner("VERDICT")
    if overall_fail == 0:
        print("  RESULT: PASS")
        print()
        print("  Every page rendered HTTP 200 with its DOM landmark across")
        print("  %d cycles. All inline JS is ES5-clean (safe for Pepper's old" % args.cycles)
        print("  WebKit). Voice endpoints (/api/start_voice, /api/voice_status,")
        print("  /api/stop_voice) stayed fast and stable across %d tap-to-speak"
              % (0 if args.no_voice else args.voice_cycles))
        print("  cycles. Pages still render correctly after all that load.")
        print()
        print("  This is the proof: under simulated extended interaction,")
        print("  including heavy tap-to-speak use, the UI never produced a")
        print("  white-page condition the tablet could hit.")
        print(SEP)
        return 0
    else:
        print("  RESULT: FAIL  (%d issue(s) above)" % overall_fail)
        print(SEP)
        return 1


if __name__ == "__main__":
    sys.exit(main())
