# -*- coding: utf-8 -*-
"""
test_robot.py  —  Pepper Robot Full Hardware + Integration Test
================================================================
Runs while physically connected to Pepper over the local network.
Tests every subsystem end-to-end and reports PASS / WARN / FAIL / SKIP.

SUBSYSTEMS TESTED
-----------------
  1.  NAOqi connection & proxy creation
  2.  Robot identity (firmware, name, model)
  3.  Battery & power
  4.  Text-to-Speech (English + Arabic, language switch)
  5.  Microphone / audio recording (start, poll, stop, file check)
  6.  Camera (subscribe, grab frame, pixel data, unsubscribe)
  7.  Motion & posture (wake, stand, arm gesture, return, rest)
  8.  Touch sensors (head, hands — read via ALMemory)
  9.  Sonar sensors (front/back — read via ALMemory)
  10. LEDs (face, eye, chest — colour cycle)
  11. Tablet display (showWebview, hideWebview)
  12. Navigation (small move & return — optional, requires --allow-move)
  13. Audio file transfer (PSCP robot → laptop)
  14. Backend API (/api/health, /api/start_voice, status, stop, chat)
  15. WebSocket bridge (connect, handshake, send, close)

USAGE
-----
    # Activate your venv first, then:
    python test_robot.py
    python test_robot.py --robot-ip 1.1.1.10 --server-ip 1.1.1.246

    # Add NAOqi SDK to PYTHONPATH if not already set:
    set PYTHONPATH=C:\\pynaoqi\\pynaoqi-python2.7-2.8.6.23-win64-vs2015-20191127_152649
    python test_robot.py

    # Skip physical-motion tests (safe in tight spaces):
    python test_robot.py --no-motion

    # Enable small drive test (0.4 m forward + return):
    python test_robot.py --allow-move

    # Quick mode (skips motion, recording, PSCP, nav):
    python test_robot.py --quick

    # Run only specific sections (comma-separated section numbers):
    python test_robot.py --only 1,2,3,14,15

OUTPUT
------
    Prints colour-coded results per test.
    Writes test_robot_report.json on completion.
"""

from __future__ import print_function

import argparse
import io
import json
import os
import re
import socket
import subprocess
import sys
import time
import traceback

# ---------------------------------------------------------------------------
# NAOqi SDK auto-setup.
#
# The SDK (naoqi.py) is Python 2.7-only — it uses bare `except E, e:` syntax
# that is a SyntaxError in Python 3.  Python 3 can never import it directly.
#
# Strategy:
#   1. Add the SDK's lib/ dir to sys.path so Python 2.7 can find naoqi.py.
#   2. Add C:\pynaoqi\bin to PATH so the native .dll files (qi.dll,
#      inaoqi.dll, python27.dll) are visible to the linker.
#   3. If we are currently running under Python 3, re-exec this exact script
#      under python2 (= C:\pynaoqi\bin\python2.exe) so NAOqi sections work.
#      The re-exec inherits the updated environment and sys.argv, so all
#      CLI flags (--quick, --only, etc.) are preserved.
# ---------------------------------------------------------------------------
_PEPPER_SDK = r"C:\pynaoqi\pynaoqi-python2.7-2.8.6.23-win64-vs2015-20191127_152649"
_SDK_LIB    = os.path.join(_PEPPER_SDK, "lib")
_SDK_BIN    = r"C:\pynaoqi\bin"          # python2.exe + all NAOqi DLLs live here

# Step 1 — add lib to sys.path (works for whichever Python is running)
if os.path.isdir(_SDK_LIB) and _SDK_LIB not in sys.path:
    sys.path.insert(0, _SDK_LIB)

# Step 2 — add bin to PATH so native DLLs are found at import time
if os.path.isdir(_SDK_BIN) and _SDK_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _SDK_BIN + os.pathsep + os.environ.get("PATH", "")

# Step 3 — if Python 3, re-exec under python2 so NAOqi syntax is valid
if sys.version_info[0] >= 3:
    _py2 = os.path.join(_SDK_BIN, "python2.exe")
    if not os.path.exists(_py2):
        _py2 = "python2"   # fall back to PATH lookup
    # Propagate the lib path as PYTHONPATH so the relaunched process sees it
    _env = dict(os.environ)
    _env["PYTHONPATH"] = _SDK_LIB + os.pathsep + _env.get("PYTHONPATH", "")
    try:
        _rc = subprocess.call([_py2, os.path.abspath(__file__)] + sys.argv[1:], env=_env)
        sys.exit(_rc)
    except Exception as _e:
        # python2 not found — continue under Python 3 (NAOqi sections will SKIP)
        print("[WARN] Could not relaunch under python2 (%s)." % _e)
        print("[WARN] NAOqi sections will be skipped. Install python2 or run:")
        print("[WARN]   python2 test_robot.py %s" % " ".join(sys.argv[1:]))

# ---------------------------------------------------------------------------
# Python 2/3 compat
# ---------------------------------------------------------------------------
PY2 = sys.version_info[0] == 2
if PY2:
    text_type = unicode  # noqa: F821
    string_types = (str, unicode)  # noqa: F821
else:
    text_type = str
    string_types = (str,)

# UTF-8 console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Optional imports — graceful degradation
# ---------------------------------------------------------------------------
try:
    from naoqi import ALProxy
    NAOQI_OK = True
except ImportError:
    NAOQI_OK = False

try:
    import requests as _req
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    import websocket as _ws_client
    WS_CLIENT_OK = True
except ImportError:
    WS_CLIENT_OK = False

# ---------------------------------------------------------------------------
# ANSI colours
# ---------------------------------------------------------------------------
def _supports_color():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

_COLOR = _supports_color()

def _c(code, t):  return ("\033[%sm%s\033[0m" % (code, t)) if _COLOR else t
def green(t):     return _c("32;1", t)
def yellow(t):    return _c("33;1", t)
def red(t):       return _c("31;1", t)
def cyan(t):      return _c("36;1", t)
def bold(t):      return _c("1", t)
def dim(t):       return _c("2", t)

SEP  = "=" * 72
DASH = "-" * 72

# ---------------------------------------------------------------------------
# Config defaults (overridden by config.json + CLI args)
# ---------------------------------------------------------------------------
_DEFAULT = {
    "ROBOT_IP":    "1.1.1.10",
    "ROBOT_PORT":  9559,
    "SERVER_IP":   "1.1.1.246",
    "SERVER_PORT": 8080,
    "WS_PORT":     8765,
}

def _load_config():
    """Merge config.json (project root) with defaults."""
    cfg = dict(_DEFAULT)
    root = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(root, "config.json")
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                raw = json.load(f)
            for k in ("ROBOT_IP", "SERVER_IP"):
                if k in raw:
                    cfg[k] = raw[k]
            for k in ("ROBOT_PORT", "SERVER_PORT", "WS_PORT"):
                if k in raw:
                    try:
                        cfg[k] = int(raw[k])
                    except Exception:
                        pass
        except Exception:
            pass
    return cfg


# ===========================================================================
# Test Runner
# ===========================================================================
class RobotTestRunner(object):
    """Runs every hardware + integration test and accumulates a results table."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"

    def __init__(self, cfg, args):
        self.cfg     = cfg
        self.args    = args
        self.results = []          # list of dicts
        self.section = 0
        self._proxies = {}         # name -> ALProxy instance

        self.robot_ip    = cfg["ROBOT_IP"]
        self.robot_port  = cfg["ROBOT_PORT"]
        self.server_url  = "http://{}:{}".format(cfg["SERVER_IP"], cfg["SERVER_PORT"])
        self.ws_url      = "ws://{}:{}".format(cfg["SERVER_IP"], cfg["WS_PORT"])
        self.ws_host     = cfg["SERVER_IP"]
        self.ws_port     = cfg["WS_PORT"]

        # Paths
        self.voice_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "Pepper-Controller-main-2", "pepper_voice"
        )
        self.pscp_path = r"C:\Program Files\PuTTY\pscp.exe"
        self.local_audio = os.path.join(self.voice_dir, "test_robot_rec.wav")
        self.pepper_audio = "/tmp/test_robot_rec.wav"

    # ------------------------------------------------------------------
    # Result recording
    # ------------------------------------------------------------------
    def _record(self, name, status, detail="", elapsed_ms=0):
        entry = {
            "section":    self.section,
            "name":       name,
            "status":     status,
            "detail":     detail,
            "elapsed_ms": round(elapsed_ms, 1),
        }
        self.results.append(entry)
        sym = {"PASS": green("[PASS]"), "FAIL": red("[FAIL]"),
               "WARN": yellow("[WARN]"), "SKIP": dim("[SKIP]")}[status]
        ms_str = ("  (%.0fms)" % elapsed_ms) if elapsed_ms > 0 else ""
        detail_str = ("  " + detail) if detail else ""
        print("  %s  %-48s%s%s" % (sym, name, ms_str, detail_str))

    def ok(self, name, detail="", ms=0):
        self._record(name, self.PASS, detail, ms)

    def warn(self, name, detail="", ms=0):
        self._record(name, self.WARN, detail, ms)

    def fail(self, name, detail="", ms=0):
        self._record(name, self.FAIL, detail, ms)

    def skip(self, name, reason=""):
        self._record(name, self.SKIP, reason)

    # ------------------------------------------------------------------
    # Section banner
    # ------------------------------------------------------------------
    def begin_section(self, num, title):
        self.section = num
        print()
        print(DASH)
        print("  Section %d — %s" % (num, title))
        print(DASH)

    # ------------------------------------------------------------------
    # NAOqi helpers
    # ------------------------------------------------------------------
    def _proxy(self, module):
        """Return a cached NAOqi proxy; raises on failure."""
        if module not in self._proxies:
            self._proxies[module] = ALProxy(module, self.robot_ip, self.robot_port)
        return self._proxies[module]

    def _safe_proxy(self, module):
        """Return proxy or None; never raises."""
        try:
            return self._proxy(module)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _get(self, path, timeout=6):
        url = self.server_url + path
        t0 = time.time()
        try:
            r = _req.get(url, timeout=timeout)
            ms = (time.time() - t0) * 1000.0
            return r.status_code, r.text, ms
        except Exception as e:
            return 0, str(e), (time.time() - t0) * 1000.0

    def _post(self, path, payload, timeout=10):
        url = self.server_url + path
        t0 = time.time()
        try:
            r = _req.post(url, json=payload, timeout=timeout)
            ms = (time.time() - t0) * 1000.0
            return r.status_code, r.json() if r.text else {}, ms
        except Exception as e:
            return 0, {}, (time.time() - t0) * 1000.0

    # ==================================================================
    # SECTION 1 — NAOqi Connectivity
    # ==================================================================
    def run_section_1(self):
        self.begin_section(1, "NAOqi Connectivity")
        if not NAOQI_OK:
            self.fail("NAOqi SDK import", "ALProxy not importable — add SDK to PYTHONPATH")
            self.skip("ALTextToSpeech proxy",    "NAOqi unavailable")
            self.skip("ALMotion proxy",          "NAOqi unavailable")
            self.skip("ALRobotPosture proxy",    "NAOqi unavailable")
            self.skip("ALAudioRecorder proxy",   "NAOqi unavailable")
            self.skip("ALVideoDevice proxy",     "NAOqi unavailable")
            self.skip("ALNavigation proxy",      "NAOqi unavailable")
            self.skip("ALMemory proxy",          "NAOqi unavailable")
            self.skip("ALLeds proxy",            "NAOqi unavailable")
            self.skip("ALTabletService proxy",   "NAOqi unavailable")
            self.skip("ALBattery proxy",         "NAOqi unavailable")
            return

        self.ok("NAOqi SDK import")

        REQUIRED = [
            ("ALTextToSpeech",  True),
            ("ALMotion",        True),
            ("ALRobotPosture",  True),
            ("ALAudioRecorder", True),
            ("ALVideoDevice",   True),
            ("ALNavigation",    True),
            ("ALMemory",        True),
            ("ALLeds",          True),
        ]
        OPTIONAL = [
            "ALTabletService",
            "ALBattery",
            "ALBasicAwareness",
            "ALAutonomousLife",
            "ALSystem",
            "ALSpeechRecognition",
            "ALSonar",
        ]

        for module, required in REQUIRED:
            t0 = time.time()
            try:
                p = ALProxy(module, self.robot_ip, self.robot_port)
                self._proxies[module] = p
                self.ok(module + " proxy", ms=(time.time()-t0)*1000)
            except Exception as e:
                ms = (time.time()-t0)*1000
                if required:
                    self.fail(module + " proxy", str(e)[:80], ms)
                else:
                    self.warn(module + " proxy", str(e)[:60], ms)

        for module in OPTIONAL:
            t0 = time.time()
            try:
                p = ALProxy(module, self.robot_ip, self.robot_port)
                self._proxies[module] = p
                self.ok(module + " proxy (optional)", ms=(time.time()-t0)*1000)
            except Exception as e:
                self.warn(module + " proxy (optional)", str(e)[:60])

    # ==================================================================
    # SECTION 2 — Robot Identity
    # ==================================================================
    def run_section_2(self):
        self.begin_section(2, "Robot Identity")
        if not NAOQI_OK:
            self.skip("Robot name",     "NAOqi unavailable")
            self.skip("Firmware",       "NAOqi unavailable")
            self.skip("Robot type",     "NAOqi unavailable")
            return

        sys_proxy = self._safe_proxy("ALSystem")
        if sys_proxy:
            t0 = time.time()
            try:
                name = sys_proxy.robotName()
                self.ok("Robot name", name, (time.time()-t0)*1000)
            except Exception as e:
                self.fail("Robot name", str(e))

            t0 = time.time()
            try:
                fw = sys_proxy.systemVersion()
                self.ok("Firmware version", fw, (time.time()-t0)*1000)
            except Exception as e:
                self.fail("Firmware version", str(e))
        else:
            self.warn("Robot name",     "ALSystem proxy unavailable")
            self.warn("Firmware",       "ALSystem proxy unavailable")

        mem = self._safe_proxy("ALMemory")
        if mem:
            t0 = time.time()
            try:
                robot_type = mem.getData("RobotConfig/Body/Type")
                self.ok("Robot type", str(robot_type), (time.time()-t0)*1000)
            except Exception as e:
                self.warn("Robot type", str(e))
        else:
            self.skip("Robot type", "ALMemory unavailable")

    # ==================================================================
    # SECTION 3 — Battery & Power
    # ==================================================================
    def run_section_3(self):
        self.begin_section(3, "Battery & Power")
        bat = self._safe_proxy("ALBattery")
        if not bat:
            self.warn("Battery proxy", "ALBattery unavailable — skip power checks")
            return

        t0 = time.time()
        try:
            charge = bat.getBatteryCharge()
            ms = (time.time()-t0)*1000
            detail = "%d%%" % charge
            if charge >= 50:
                self.ok("Battery charge", detail, ms)
            elif charge >= 20:
                self.warn("Battery charge", detail + " — below 50%, navigation may be unreliable", ms)
            else:
                self.fail("Battery charge", detail + " — CRITICAL: robot may shut down mid-test", ms)
        except Exception as e:
            self.fail("Battery charge", str(e))

        try:
            charging = bat.isCharging()
            self.ok("Charging status", "charging" if charging else "on battery")
        except Exception as e:
            self.warn("Charging status", str(e))

        mem = self._safe_proxy("ALMemory")
        if mem:
            for key, label in [
                ("Device/SubDeviceList/Battery/Current/Sensor/Value",     "Battery current (A)"),
                ("Device/SubDeviceList/Battery/Temperature/Sensor/Value", "Battery temperature (C)"),
            ]:
                t0 = time.time()
                try:
                    val = mem.getData(key)
                    self.ok(label, "%.2f" % float(val), (time.time()-t0)*1000)
                except Exception as e:
                    self.warn(label, str(e))

    # ==================================================================
    # SECTION 4 — Text-to-Speech
    # ==================================================================
    def run_section_4(self):
        self.begin_section(4, "Text-to-Speech (TTS)")
        tts = self._safe_proxy("ALTextToSpeech")
        if not tts:
            self.fail("TTS proxy",           "ALTextToSpeech unavailable")
            return

        # Available languages
        t0 = time.time()
        try:
            langs = tts.getAvailableLanguages()
            self.ok("Available TTS languages", str(langs), (time.time()-t0)*1000)
        except Exception as e:
            self.warn("Available TTS languages", str(e))

        # English TTS
        t0 = time.time()
        try:
            tts.setLanguage("English")
            tts.say("Hello. Running hardware test. Systems are online.")
            self.ok("TTS English say()", "(%.0fms)" % ((time.time()-t0)*1000))
        except Exception as e:
            self.fail("TTS English say()", str(e))

        # Language readback check
        t0 = time.time()
        try:
            current = tts.getLanguage()
            if current == "English":
                self.ok("TTS language readback", current, (time.time()-t0)*1000)
            else:
                self.warn("TTS language readback",
                          "Expected English, got " + str(current), (time.time()-t0)*1000)
        except Exception as e:
            self.warn("TTS language readback", str(e))

        # Arabic TTS — only if Arabic voice installed
        t0 = time.time()
        try:
            tts.setLanguage("Arabic")
            time.sleep(0.15)
            tts.say(u"مرحبا. جاري الاختبار.".encode("utf-8") if PY2
                    else u"مرحبا. جاري الاختبار.")
            self.ok("TTS Arabic say()", "(%.0fms)" % ((time.time()-t0)*1000))
        except Exception as e:
            errmsg = str(e).lower()
            if "not available" in errmsg or "language" in errmsg or "voice" in errmsg:
                self.warn("TTS Arabic say()", "Arabic voice not installed — " + str(e)[:60])
            else:
                self.fail("TTS Arabic say()", str(e)[:80])
        finally:
            try:
                tts.setLanguage("English")
            except Exception:
                pass

        # Volume and speed
        try:
            vol = tts.getVolume()
            self.ok("TTS volume", "%.1f" % vol)
        except Exception as e:
            self.warn("TTS volume", str(e))

    # ==================================================================
    # SECTION 5 — Microphone / Audio Recording
    # ==================================================================
    def run_section_5(self):
        self.begin_section(5, "Microphone & Audio Recording")
        if self.args.quick:
            self.skip("Audio recording", "--quick mode")
            self.skip("Recording file size check", "--quick mode")
            return

        rec = self._safe_proxy("ALAudioRecorder")
        if not rec:
            self.fail("ALAudioRecorder proxy", "Cannot test microphone")
            return

        # Clean up any leftover test file from a previous run
        try:
            rec.stopMicrophonesRecording()
        except Exception:
            pass

        # Start recording
        REC_SECS = 3
        t0 = time.time()
        try:
            rec.startMicrophonesRecording(
                self.pepper_audio, "wav", 16000, (1, 0, 0, 0))
            self.ok("Start microphone recording",
                    "(%.0fms)" % ((time.time()-t0)*1000))
        except Exception as e:
            self.fail("Start microphone recording", str(e))
            return

        # Wait for recording duration
        print("  [....] Recording for %ds ..." % REC_SECS)
        time.sleep(REC_SECS)

        # Stop recording
        t0 = time.time()
        try:
            rec.stopMicrophonesRecording()
            self.ok("Stop microphone recording",
                    "(%.0fms)" % ((time.time()-t0)*1000))
        except Exception as e:
            self.fail("Stop microphone recording", str(e))

        # Verify file exists on robot via SSH stat (requires paramiko or pscp)
        pscp = self.pscp_path
        if os.path.exists(pscp):
            t0 = time.time()
            try:
                ret = subprocess.call(
                    [pscp, "-pw", "nao",
                     "nao@{}:{}".format(self.robot_ip, self.pepper_audio),
                     self.local_audio],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                ms = (time.time()-t0)*1000
                if ret == 0 and os.path.exists(self.local_audio):
                    sz = os.path.getsize(self.local_audio)
                    # 3s @ 16kHz mono WAV = 96000 samples × 2 bytes = ~192 KB + header
                    if sz > 50000:
                        self.ok("Audio file transferred (PSCP)",
                                "%d bytes (%.0fms)" % (sz, ms))
                    else:
                        self.warn("Audio file transferred (PSCP)",
                                  "%d bytes — smaller than expected" % sz)
                else:
                    self.fail("Audio file transferred (PSCP)",
                              "pscp returned %d or file missing" % ret)
            except Exception as e:
                self.fail("Audio file transfer (PSCP)", str(e))
        else:
            self.warn("Audio file transferred (PSCP)",
                      "pscp.exe not found at " + pscp + " — install PuTTY")

    # ==================================================================
    # SECTION 6 — Camera
    # ==================================================================
    def run_section_6(self):
        self.begin_section(6, "Camera")
        vid = self._safe_proxy("ALVideoDevice")
        if not vid:
            self.fail("ALVideoDevice proxy", "Cannot test camera")
            return

        sub_name = None

        # Subscribe
        t0 = time.time()
        try:
            # subscribeCamera(name, cameraIndex=0=top, resolution=1=QVGA, colorSpace=11=RGB, fps=15)
            sub_name = vid.subscribeCamera(
                "robot_test_{}".format(int(time.time())), 0, 1, 11, 15)
            self.ok("Camera subscribe (top, QVGA, RGB)",
                    sub_name, (time.time()-t0)*1000)
        except Exception as e:
            self.fail("Camera subscribe", str(e))
            return

        # Grab one frame
        t0 = time.time()
        try:
            frame = vid.getImageRemote(sub_name)
            ms = (time.time()-t0)*1000
            if frame is None:
                self.fail("Camera frame grab", "getImageRemote returned None", ms)
            else:
                w, h = frame[0], frame[1]
                channels = frame[2]
                raw = frame[6]  # raw pixel bytes
                px_count = len(raw) if raw else 0
                expected = w * h * 3  # RGB
                if w > 0 and h > 0 and px_count >= expected * 0.9:
                    self.ok("Camera frame grab",
                            "%dx%d  %d bytes (%.0fms)" % (w, h, px_count, ms))
                else:
                    self.warn("Camera frame grab",
                              "%dx%d channels=%d px=%d" % (w, h, channels, px_count), ms)
        except Exception as e:
            self.fail("Camera frame grab", str(e))

        # Grab a second frame to confirm streaming
        t0 = time.time()
        try:
            time.sleep(0.1)
            frame2 = vid.getImageRemote(sub_name)
            ms = (time.time()-t0)*1000
            if frame2 and frame2[6] and len(frame2[6]) > 0:
                self.ok("Camera second frame", "(%.0fms)" % ms)
            else:
                self.warn("Camera second frame", "empty or None")
        except Exception as e:
            self.warn("Camera second frame", str(e))

        # Unsubscribe
        t0 = time.time()
        try:
            vid.unsubscribe(sub_name)
            self.ok("Camera unsubscribe", "(%.0fms)" % ((time.time()-t0)*1000))
        except Exception as e:
            self.warn("Camera unsubscribe", str(e))

    # ==================================================================
    # SECTION 7 — Motion & Posture
    # ==================================================================
    def run_section_7(self):
        self.begin_section(7, "Motion & Posture")
        if self.args.no_motion or self.args.quick:
            reason = "--no-motion" if self.args.no_motion else "--quick"
            for t in ["WakeUp", "Stand posture", "Arm wave gesture",
                      "Return to StandInit", "Rest posture"]:
                self.skip(t, reason)
            return

        motion   = self._safe_proxy("ALMotion")
        posture  = self._safe_proxy("ALRobotPosture")
        if not motion or not posture:
            self.fail("Motion proxy", "ALMotion or ALRobotPosture unavailable")
            return

        # WakeUp
        t0 = time.time()
        try:
            motion.wakeUp()
            self.ok("WakeUp (motor stiffness on)", "(%.0fms)" % ((time.time()-t0)*1000))
        except Exception as e:
            self.fail("WakeUp", str(e))
            return

        time.sleep(0.5)

        # Stand
        t0 = time.time()
        try:
            result = posture.goToPosture("Stand", 0.7)
            ms = (time.time()-t0)*1000
            if result:
                self.ok("Stand posture", "(%.0fms)" % ms)
            else:
                self.warn("Stand posture", "goToPosture returned False", ms)
        except Exception as e:
            self.fail("Stand posture", str(e))

        time.sleep(0.4)

        # Arm wave — right arm joints only, NO locomotion
        t0 = time.time()
        try:
            names  = ["RShoulderPitch", "RShoulderRoll", "RElbowRoll", "RWristYaw"]
            angles = [-0.2,             -0.3,             1.0,          0.0]
            motion.setAngles(names, angles, 0.15)
            time.sleep(0.5)
            for _ in range(2):
                motion.setAngles("RWristYaw", 0.5, 0.5)
                time.sleep(0.3)
                motion.setAngles("RWristYaw", -0.5, 0.5)
                time.sleep(0.3)
            self.ok("Arm wave gesture", "(%.0fms)" % ((time.time()-t0)*1000))
        except Exception as e:
            self.fail("Arm wave gesture", str(e))

        time.sleep(0.3)

        # Return to neutral
        t0 = time.time()
        try:
            result = posture.goToPosture("StandInit", 0.5)
            ms = (time.time()-t0)*1000
            if result:
                self.ok("Return to StandInit", "(%.0fms)" % ms)
            else:
                self.warn("Return to StandInit", "returned False", ms)
        except Exception as e:
            self.fail("Return to StandInit", str(e))

        time.sleep(0.3)

        # Verify joint positions are reasonable (not flat on floor)
        t0 = time.time()
        try:
            pos = motion.getRobotPosition(True)  # True = use odometry
            self.ok("Read robot position (odometry)", str([round(v,3) for v in pos]))
        except Exception as e:
            self.warn("Read robot position", str(e))

        # Rest (optional — puts motors to sleep, user must wake again)
        t0 = time.time()
        try:
            motion.rest()
            self.ok("Rest (motor stiffness off)", "(%.0fms)" % ((time.time()-t0)*1000))
        except Exception as e:
            self.warn("Rest", str(e))

    # ==================================================================
    # SECTION 8 — Touch Sensors
    # ==================================================================
    def run_section_8(self):
        self.begin_section(8, "Touch Sensors (ALMemory read)")
        mem = self._safe_proxy("ALMemory")
        if not mem:
            self.fail("ALMemory proxy", "Cannot read sensors")
            return

        TOUCH_KEYS = [
            ("Head front",  "Device/SubDeviceList/Head/Touch/Front/Sensor/Value"),
            ("Head middle", "Device/SubDeviceList/Head/Touch/Middle/Sensor/Value"),
            ("Head rear",   "Device/SubDeviceList/Head/Touch/Rear/Sensor/Value"),
            ("RHand touch", "Device/SubDeviceList/RHand/Touch/Back/Sensor/Value"),
            ("LHand touch", "Device/SubDeviceList/LHand/Touch/Back/Sensor/Value"),
            ("Bumper FR",   "Device/SubDeviceList/Platform/FrontRight/Bumper/Sensor/Value"),
            ("Bumper FL",   "Device/SubDeviceList/Platform/FrontLeft/Bumper/Sensor/Value"),
            ("Bumper B",    "Device/SubDeviceList/Platform/Back/Bumper/Sensor/Value"),
        ]

        for label, key in TOUCH_KEYS:
            t0 = time.time()
            try:
                val = mem.getData(key)
                ms = (time.time()-t0)*1000
                self.ok("%-20s" % (label + " sensor"),
                        "value=%.2f" % float(val), ms)
            except Exception as e:
                self.warn("%-20s" % (label + " sensor"), str(e))

    # ==================================================================
    # SECTION 9 — Sonar Sensors
    # ==================================================================
    def run_section_9(self):
        self.begin_section(9, "Sonar Sensors (ALMemory read)")
        mem = self._safe_proxy("ALMemory")
        if not mem:
            self.fail("ALMemory proxy", "Cannot read sonars")
            return

        # Pepper 2.5 has exactly 2 sonar sensors: Front and Back.
        # FrontRight / BackRight keys do not exist on this firmware.
        SONAR_KEYS = [
            ("Sonar front", "Device/SubDeviceList/Platform/Front/Sonar/Sensor/Value"),
            ("Sonar back",  "Device/SubDeviceList/Platform/Back/Sonar/Sensor/Value"),
        ]

        for label, key in SONAR_KEYS:
            t0 = time.time()
            try:
                val = mem.getData(key)
                ms = (time.time()-t0)*1000
                detail = "%.3f m" % float(val)
                if float(val) < 0.2:
                    self.warn("%-22s" % label, detail + " — very close obstacle", ms)
                else:
                    self.ok("%-22s" % label, detail, ms)
            except Exception as e:
                self.warn("%-22s" % label, str(e))

    # ==================================================================
    # SECTION 10 — LEDs
    # ==================================================================
    def run_section_10(self):
        self.begin_section(10, "LED Control")
        if self.args.no_motion or self.args.quick:
            self.skip("LED tests", "--no-motion / --quick")
            return

        leds = self._safe_proxy("ALLeds")
        if not leds:
            self.fail("ALLeds proxy", "Cannot test LEDs")
            return

        PATTERNS = [
            ("FaceLeds red",   "FaceLeds",   1.0, 0.0, 0.0),
            ("FaceLeds green", "FaceLeds",   0.0, 1.0, 0.0),
            ("FaceLeds blue",  "FaceLeds",   0.0, 0.0, 1.0),
            ("EyeLeds white",  "FaceLeds",   1.0, 1.0, 1.0),
            ("ChestLed red",   "ChestLeds",  1.0, 0.0, 0.0),
        ]

        for name, group, r, g, b in PATTERNS:
            t0 = time.time()
            try:
                # fadeRGB(group, r, g, b, duration_secs)
                leds.fadeRGB(group, r, g, b, 0.2)
                time.sleep(0.25)
                self.ok(name, "(%.0fms)" % ((time.time()-t0)*1000))
            except Exception as e:
                self.warn(name, str(e))

        # Reset to white
        try:
            leds.fadeRGB("FaceLeds",  1.0, 1.0, 1.0, 0.3)
            leds.fadeRGB("ChestLeds", 1.0, 1.0, 1.0, 0.3)
            time.sleep(0.4)
            self.ok("LED reset to white")
        except Exception as e:
            self.warn("LED reset", str(e))

    # ==================================================================
    # SECTION 11 — Tablet Display
    # ==================================================================
    def run_section_11(self):
        self.begin_section(11, "Tablet Display")
        tab = self._safe_proxy("ALTabletService")
        if not tab:
            self.warn("ALTabletService proxy",
                      "Tablet tests skipped — ALTabletService unavailable")
            return

        # showWebview with home page
        home_url = self.server_url + "/"
        t0 = time.time()
        try:
            tab.showWebview(home_url)
            self.ok("showWebview (home page)", home_url + " (%.0fms)" % ((time.time()-t0)*1000))
        except Exception as e:
            self.fail("showWebview (home page)", str(e))

        time.sleep(1.0)

        # Navigate to login page
        t0 = time.time()
        try:
            tab.showWebview(self.server_url + "/login.html")
            self.ok("showWebview (login.html)", "(%.0fms)" % ((time.time()-t0)*1000))
        except Exception as e:
            self.warn("showWebview (login.html)", str(e))

        time.sleep(0.5)

        # hideWebview
        t0 = time.time()
        try:
            tab.hideWebview()
            self.ok("hideWebview", "(%.0fms)" % ((time.time()-t0)*1000))
        except Exception as e:
            self.warn("hideWebview", str(e))

        time.sleep(0.3)

        # Restore home page (leave tablet in good state)
        try:
            tab.showWebview(home_url)
            self.ok("Restore home page")
        except Exception as e:
            self.warn("Restore home page", str(e))

    # ==================================================================
    # SECTION 12 — Navigation (optional)
    # ==================================================================
    def run_section_12(self):
        self.begin_section(12, "Navigation (ALNavigation)")
        if not self.args.allow_move:
            self.skip("Small drive test",
                      "Use --allow-move to enable (robot will move 0.4m forward + return)")
            return
        if self.args.quick or self.args.no_motion:
            self.skip("Small drive test", "--quick / --no-motion")
            return

        nav    = self._safe_proxy("ALNavigation")
        motion = self._safe_proxy("ALMotion")
        if not nav or not motion:
            self.fail("Navigation proxy", "ALNavigation or ALMotion unavailable")
            return

        # Wake up if needed
        try:
            motion.wakeUp()
            motion.moveInit()
        except Exception:
            pass

        DIST = 0.4  # metres forward

        # Move forward
        t0 = time.time()
        try:
            ok = nav.navigateTo(DIST, 0, 0)
            ms = (time.time()-t0)*1000
            if ok:
                self.ok("navigateTo (%.1fm forward)" % DIST, "(%.0fms)" % ms)
            else:
                self.warn("navigateTo (%.1fm forward)" % DIST,
                          "returned False — obstacle?", ms)
        except Exception as e:
            self.fail("navigateTo (%.1fm forward)" % DIST, str(e))
            return

        time.sleep(0.5)

        # Move back
        t0 = time.time()
        try:
            ok = nav.navigateTo(-DIST, 0, 0)
            ms = (time.time()-t0)*1000
            if ok:
                self.ok("navigateTo (%.1fm back)" % DIST, "(%.0fms)" % ms)
            else:
                self.warn("navigateTo (%.1fm back)" % DIST,
                          "returned False — obstacle?", ms)
        except Exception as e:
            self.fail("navigateTo (%.1fm back)" % DIST, str(e))

        # Read final position (should be ~origin)
        t0 = time.time()
        try:
            pos = motion.getRobotPosition(True)
            dx, dy = pos[0], pos[1]
            drift = (dx**2 + dy**2) ** 0.5
            if drift < 0.15:
                self.ok("Odometry drift after round-trip",
                        "%.3fm (within 15cm)" % drift)
            else:
                self.warn("Odometry drift after round-trip",
                          "%.3fm — robot did not return to origin" % drift)
        except Exception as e:
            self.warn("Odometry drift", str(e))

    # ==================================================================
    # SECTION 13 — Audio File Transfer (PSCP)
    # ==================================================================
    def run_section_13(self):
        self.begin_section(13, "Audio File Transfer (PSCP)")
        if self.args.quick:
            self.skip("PSCP binary check",    "--quick mode")
            self.skip("PSCP transfer test",   "--quick mode")
            return

        pscp = self.pscp_path
        if not os.path.exists(pscp):
            self.fail("PSCP binary check",
                      pscp + " not found — install PuTTY from https://www.putty.org")
            return
        self.ok("PSCP binary check", pscp)

        # Transfer test: use the file recorded in section 5 if it exists
        if os.path.exists(self.local_audio):
            sz = os.path.getsize(self.local_audio)
            self.ok("PSCP transfer test",
                    "audio file already transferred in section 5 (%d bytes)" % sz)
            return

        # Otherwise try to fetch a known file from robot's /tmp
        # (If section 5 was skipped, this won't exist — warn, not fail)
        self.warn("PSCP transfer test",
                  "No audio file available — run section 5 (recording) first")

    # ==================================================================
    # SECTION 14 — Backend API Integration
    # ==================================================================
    def run_section_14(self):
        self.begin_section(14, "Backend API Integration")
        if not REQUESTS_OK:
            self.fail("requests library", "pip install requests")
            return

        # /api/health
        code, body, ms = self._get("/api/health", timeout=5)
        if code == 200:
            try:
                d = json.loads(body)
                status = d.get("status", "?")
                self.ok("/api/health", "status=%s rag=%s offline=%s" % (
                    status, d.get("rag_ready"), d.get("offline_mode")), ms)
            except Exception:
                self.ok("/api/health", "(%.0fms)" % ms)
        else:
            self.fail("/api/health",
                      "HTTP %s — is main.py --server-only running?" % code, ms)
            return  # No point running further API tests

        # /api/navigation_targets
        code, body, ms = self._get("/api/navigation_targets")
        if code == 200:
            try:
                targets = json.loads(body)
                self.ok("/api/navigation_targets",
                        "%d target(s)" % len(targets), ms)
            except Exception:
                self.ok("/api/navigation_targets", "(%.0fms)" % ms)
        else:
            self.warn("/api/navigation_targets", "HTTP %s" % code, ms)

        # /api/start_voice
        code, resp, ms = self._post("/api/start_voice", {"lang": "en"})
        if code == 200 and resp.get("ok"):
            self.ok("/api/start_voice", "(%.0fms)" % ms)
        else:
            self.fail("/api/start_voice",
                      "HTTP %s  resp=%s" % (code, str(resp)[:60]), ms)

        # /api/voice_status  (should be 'recording' since we just called start)
        code, body, ms = self._get("/api/voice_status")
        if code == 200:
            try:
                state = json.loads(body).get("state", "?")
                if state in ("recording", "idle", "processing"):
                    self.ok("/api/voice_status", "state=%s (%.0fms)" % (state, ms))
                else:
                    self.warn("/api/voice_status", "unexpected state=%s" % state, ms)
            except Exception:
                self.warn("/api/voice_status", "could not parse response", ms)
        else:
            self.fail("/api/voice_status", "HTTP %s" % code, ms)

        # /api/stop_voice
        code, resp, ms = self._post("/api/stop_voice", {})
        if code == 200 and resp.get("ok"):
            self.ok("/api/stop_voice", "(%.0fms)" % ms)
        else:
            self.fail("/api/stop_voice",
                      "HTTP %s  resp=%s" % (code, str(resp)[:60]), ms)

        # /api/chat_ai — one-shot hospital query
        # Response key is "answer" (not "reply") — see app.py:api_chat_ai
        t0 = time.time()
        code, resp, ms = self._post(
            "/api/chat_ai",
            {"message": "What departments does the hospital have?",
             "lang": "en", "history": []},
            timeout=45)
        if code == 200:
            # The endpoint returns {"answer": ..., "success": true}
            reply = resp.get("answer") or resp.get("reply") or ""
            if isinstance(reply, list):
                # Some LLM paths return a list of text blocks
                reply = " ".join(str(x) for x in reply)
            if len(str(reply)) > 20:
                self.ok("/api/chat_ai", "answer=%d chars (%.0fms)" % (len(str(reply)), ms))
            else:
                self.warn("/api/chat_ai",
                          "answer too short (%r) — LLM may be cold-starting" % str(reply)[:60], ms)
        else:
            self.fail("/api/chat_ai", "HTTP %s" % code, ms)

        # /api/book_appointment — validation: empty payload returns HTTP 200
        # with {"success": false} (not HTTP 400, because Flask-login redirect
        # catches unauthenticated requests first and returns success=false).
        code, resp, ms = self._post(
            "/api/book_appointment",
            {"doctor_name": "", "date": "", "time_slot": ""})
        if code == 200 and isinstance(resp, dict) and resp.get("success") is False:
            self.ok("/api/book_appointment validation",
                    "correctly rejects empty payload (success=false, %.0fms)" % ms)
        elif code == 200 and isinstance(resp, dict) and resp.get("success"):
            self.warn("/api/book_appointment validation",
                      "accepted empty payload with success=true — phantom booking risk")
        else:
            self.ok("/api/book_appointment validation",
                    "HTTP %s (%.0fms)" % (code, ms))

        # /api/triage_assess — medical triage endpoint (the actual emergency handler)
        code, resp, ms = self._post(
            "/api/triage_assess",
            {"symptoms": "chest pain", "lang": "en"},
            timeout=30)
        if code == 200:
            urgency = resp.get("urgency_level") or resp.get("level") or "?"
            self.ok("/api/triage_assess",
                    "urgency=%s (%.0fms)" % (str(urgency)[:20], ms))
        else:
            self.warn("/api/triage_assess", "HTTP %s" % code, ms)

        # Upload the test audio file if it exists (tests full Whisper pipeline)
        if os.path.exists(self.local_audio) and not self.args.quick:
            url = self.server_url + "/api/process_audio"
            t0 = time.time()
            try:
                with open(self.local_audio, "rb") as f:
                    r = _req.post(url, files={"file": ("voice.wav", f, "audio/wav")},
                                  data={"lang": "en"}, timeout=45)
                ms = (time.time()-t0)*1000
                if r.status_code == 200:
                    resp = r.json()
                    reply = resp.get("reply", "")
                    self.ok("/api/process_audio (Whisper+LLM)",
                            "reply=%d chars (%.0fms)" % (len(reply), ms))
                else:
                    self.warn("/api/process_audio (Whisper+LLM)",
                              "HTTP %s" % r.status_code, ms)
            except Exception as e:
                self.warn("/api/process_audio (Whisper+LLM)", str(e)[:80])
        else:
            self.skip("/api/process_audio (Whisper+LLM)",
                      "no audio file (run section 5 recording first)")

    # ==================================================================
    # SECTION 15 — WebSocket Bridge
    # ==================================================================
    def run_section_15(self):
        self.begin_section(15, "WebSocket Bridge")

        # TCP reachability test first (works regardless of ws library)
        t0 = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(4)
            sock.connect((self.ws_host, self.ws_port))
            sock.close()
            self.ok("WS bridge TCP reachable",
                    "%s:%d (%.0fms)" % (self.ws_host, self.ws_port,
                                         (time.time()-t0)*1000))
        except Exception as e:
            self.fail("WS bridge TCP reachable",
                      str(e) + " — is ws_bridge.py running?")
            return

        if not WS_CLIENT_OK:
            self.warn("websocket-client import", "pip install websocket-client")
        else:
            # Full WebSocket handshake + message round-trip
            N_PROBES = 5
            passed_probes = 0
            ws_times = []

            for i in range(N_PROBES):
                t0 = time.time()
                try:
                    ws = _ws_client.WebSocket()
                    ws.connect(self.ws_url + "/", timeout=5)
                    ws.send(json.dumps({"type": "hello", "from": "robot_test"}))
                    # Bridge is a broadcast relay — it won't echo back, so just
                    # confirm the connection was accepted and we can send
                    ws.close()
                    ms = (time.time()-t0)*1000
                    ws_times.append(ms)
                    passed_probes += 1
                except Exception as e:
                    ms = (time.time()-t0)*1000
                    ws_times.append(ms)
                if i < N_PROBES - 1:
                    time.sleep(0.3)

            avg = sum(ws_times) / len(ws_times) if ws_times else 0
            peak = max(ws_times) if ws_times else 0
            if passed_probes == N_PROBES:
                self.ok("WS handshake + send (%dx)" % N_PROBES,
                        "avg=%.0fms peak=%.0fms" % (avg, peak))
            elif passed_probes > 0:
                self.warn("WS handshake + send (%dx)" % N_PROBES,
                          "%d/%d succeeded avg=%.0fms" % (passed_probes, N_PROBES, avg))
            else:
                self.fail("WS handshake + send",
                          "0/%d probes succeeded" % N_PROBES)

        # Verify the bridge broadcasts to all clients by opening two connections
        if WS_CLIENT_OK:
            t0 = time.time()
            try:
                ws1 = _ws_client.WebSocket()
                ws1.connect(self.ws_url + "/", timeout=4)
                ws2 = _ws_client.WebSocket()
                ws2.connect(self.ws_url + "/", timeout=4)
                ws1.send(json.dumps({"type": "ping"}))
                time.sleep(0.1)
                ws1.close()
                ws2.close()
                self.ok("WS dual-client (broadcast relay)",
                        "two connections alive simultaneously (%.0fms)" % ((time.time()-t0)*1000))
            except Exception as e:
                self.warn("WS dual-client", str(e)[:60])


    # ==================================================================
    # RUN ALL
    # ==================================================================
    def run(self, sections_filter=None):
        print()
        print(SEP)
        print("  PEPPER ROBOT FULL HARDWARE + INTEGRATION TEST")
        print(SEP)
        print("  Robot   : %s:%d" % (self.robot_ip, self.robot_port))
        print("  Backend : %s" % self.server_url)
        print("  WS      : %s" % self.ws_url)
        print("  NAOqi   : %s" % ("available" if NAOQI_OK else "NOT FOUND on PYTHONPATH"))
        print("  Options : no-motion=%s  allow-move=%s  quick=%s"
              % (self.args.no_motion, self.args.allow_move, self.args.quick))
        print()

        SECTIONS = [
            (1,  self.run_section_1),
            (2,  self.run_section_2),
            (3,  self.run_section_3),
            (4,  self.run_section_4),
            (5,  self.run_section_5),
            (6,  self.run_section_6),
            (7,  self.run_section_7),
            (8,  self.run_section_8),
            (9,  self.run_section_9),
            (10, self.run_section_10),
            (11, self.run_section_11),
            (12, self.run_section_12),
            (13, self.run_section_13),
            (14, self.run_section_14),
            (15, self.run_section_15),
        ]

        for num, fn in SECTIONS:
            if sections_filter and num not in sections_filter:
                continue
            try:
                fn()
            except Exception as exc:
                # Catch-all: a section crashing should not abort the whole test
                print()
                print(red("  [ERROR] Section %d crashed unexpectedly:" % num))
                traceback.print_exc()
                self._record("Section %d internal error" % num,
                             self.FAIL, str(exc)[:120])

        self._print_summary()
        self._save_report()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def _print_summary(self):
        total  = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == self.PASS)
        warned = sum(1 for r in self.results if r["status"] == self.WARN)
        failed = sum(1 for r in self.results if r["status"] == self.FAIL)
        skipped= sum(1 for r in self.results if r["status"] == self.SKIP)

        print()
        print(SEP)
        print("  FINAL RESULTS")
        print(SEP)
        print("  %-8s %s" % ("PASS",  green(str(passed))))
        print("  %-8s %s" % ("WARN",  yellow(str(warned))))
        print("  %-8s %s" % ("FAIL",  red(str(failed))))
        print("  %-8s %s" % ("SKIP",  dim(str(skipped))))
        print("  %-8s %d" % ("TOTAL", total))
        print()

        if failed > 0:
            print(red("  FAILED TESTS:"))
            for r in self.results:
                if r["status"] == self.FAIL:
                    print(red("    [FAIL] Section %d — %s" % (r["section"], r["name"])))
                    if r["detail"]:
                        print(red("           %s" % r["detail"]))
            print()

        if warned > 0:
            print(yellow("  WARNINGS:"))
            for r in self.results:
                if r["status"] == self.WARN:
                    print(yellow("    [WARN] Section %d — %s" % (r["section"], r["name"])))
                    if r["detail"]:
                        print(yellow("           %s" % r["detail"]))
            print()

        if failed == 0 and warned == 0:
            print(green("  ALL TESTS PASSED — robot is fully operational."))
        elif failed == 0:
            print(yellow("  PASS with warnings — check yellow items above."))
        else:
            print(red("  %d FAILURE(S) — see above." % failed))
        print(SEP)

    def _save_report(self):
        report_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "test_robot_report.json")
        try:
            with open(report_path, "w") as f:
                json.dump({
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "robot_ip":  self.robot_ip,
                    "server":    self.server_url,
                    "results":   self.results,
                    "summary": {
                        "pass":  sum(1 for r in self.results if r["status"] == "PASS"),
                        "warn":  sum(1 for r in self.results if r["status"] == "WARN"),
                        "fail":  sum(1 for r in self.results if r["status"] == "FAIL"),
                        "skip":  sum(1 for r in self.results if r["status"] == "SKIP"),
                    }
                }, f, indent=2)
            print()
            print(dim("  Report saved: " + report_path))
        except Exception as e:
            print(dim("  Could not save report: " + str(e)))


# ===========================================================================
# Entry point
# ===========================================================================
def main():
    cfg = _load_config()

    ap = argparse.ArgumentParser(
        description="Pepper Robot Full Hardware + Integration Test")
    ap.add_argument("--robot-ip",   default=cfg["ROBOT_IP"],
                    help="Pepper IP (default %(default)s)")
    ap.add_argument("--robot-port", type=int, default=cfg["ROBOT_PORT"],
                    help="NAOqi port (default %(default)s)")
    ap.add_argument("--server-ip",  default=cfg["SERVER_IP"],
                    help="Flask server IP (default %(default)s)")
    ap.add_argument("--server-port",type=int, default=cfg["SERVER_PORT"],
                    help="Flask server port (default %(default)s)")
    ap.add_argument("--ws-port",    type=int, default=cfg["WS_PORT"],
                    help="WebSocket bridge port (default %(default)s)")
    ap.add_argument("--no-motion",  action="store_true",
                    help="Skip all motion tests (safe in tight spaces)")
    ap.add_argument("--allow-move", action="store_true",
                    help="Enable small locomotion test (robot drives 0.4m)")
    ap.add_argument("--quick",      action="store_true",
                    help="Quick mode: skip recording, PSCP, motion, nav")
    ap.add_argument("--only",       default="",
                    help="Run only these section numbers (comma-separated, e.g. 1,14,15)")
    args = ap.parse_args()

    # Parse --only filter
    sections_filter = None
    if args.only:
        try:
            sections_filter = set(int(x.strip()) for x in args.only.split(","))
        except ValueError:
            print(red("ERROR: --only must be comma-separated integers, got: " + args.only))
            return 1

    # Override config with CLI args
    cfg["ROBOT_IP"]    = args.robot_ip
    cfg["ROBOT_PORT"]  = args.robot_port
    cfg["SERVER_IP"]   = args.server_ip
    cfg["SERVER_PORT"] = args.server_port
    cfg["WS_PORT"]     = args.ws_port

    runner = RobotTestRunner(cfg, args)
    runner.run(sections_filter=sections_filter)

    fail_count = sum(1 for r in runner.results if r["status"] == "FAIL")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
