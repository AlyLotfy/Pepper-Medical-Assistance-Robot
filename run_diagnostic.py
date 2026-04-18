#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PEPPER FULL DIAGNOSTIC SYSTEM
==============================
Comprehensive health, battery, temperature, service, and pipeline checks.
Saves full terminal output + structured JSON report to diagnostic_logs/.

Usage:
    python run_diagnostic.py               # Full diagnostic (all checks)
    python run_diagnostic.py --quick       # Skip motion + recording tests
    python run_diagnostic.py --robot-only  # Skip backend checks
    python run_diagnostic.py --backend-only# Skip robot NAOqi checks
    python run_diagnostic.py --stress N    # Run N-trial stress test after

Output saved to:
    diagnostic_logs/YYYY-MM-DD_HH-MM-SS/
        terminal.log   - Full terminal output (every line printed)
        report.json    - Structured machine-readable report
        summary.txt    - Human-readable summary

Requires (Python 2.7 or 3):
    pip install paramiko requests
    naoqi SDK on PYTHONPATH (for robot checks)
"""

from __future__ import print_function
import os
import sys
import json
import time
import socket
import datetime
import argparse
import traceback

# Optional imports — graceful fallback
try:
    import paramiko
    PARAMIKO_OK = True
except ImportError:
    PARAMIKO_OK = False

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    from naoqi import ALProxy
    NAOQI_OK = True
except ImportError:
    NAOQI_OK = False

# ============================================================
# ANSI COLOR HELPERS
# ============================================================

def _supports_color():
    """Return True if the terminal supports ANSI colors."""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # Enable VIRTUAL_TERMINAL_PROCESSING for Windows 10+
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
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
def bold(t):    return _c("1", t)
def dim(t):     return _c("2", t)

def status_str(ok, warn=False):
    if ok and not warn:
        return green("OK")
    elif warn:
        return yellow("WARN")
    else:
        return red("FAIL")

# ============================================================
# TEE LOGGER — writes to both terminal and log file
# ============================================================

class TeeLogger(object):
    """Mirror all stdout writes to a log file."""

    def __init__(self, log_path):
        self._terminal = sys.stdout
        self._log = open(log_path, "w", buffering=1)

    def write(self, message):
        # Strip ANSI codes from log file (clean text)
        import re
        clean = re.sub(r"\033\[[0-9;]*m", "", message)
        self._terminal.write(message)
        self._log.write(clean)
        self._log.flush()

    def flush(self):
        self._terminal.flush()
        self._log.flush()

    def close(self):
        self._log.close()

# ============================================================
# CONFIG LOADER
# ============================================================

def load_config():
    """Load config.json from several candidate locations."""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "Pepper-Controller-main-2", "conf.yaml"),
    ]
    for path in candidates:
        if os.path.exists(path):
            if path.endswith(".json"):
                with open(path, "r") as f:
                    return json.load(f)
    # Defaults
    return {
        "ROBOT_IP": "1.1.1.10",
        "ROBOT_PORT": 9559,
        "SERVER_IP": "127.0.0.1",
        "SERVER_PORT": 8080
    }

# ============================================================
# CONSTANTS
# ============================================================

PEPPER_JOINTS = [
    "HeadYaw", "HeadPitch",
    "LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll",
    "LWristYaw", "LHand",
    "RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll",
    "RWristYaw", "RHand",
    "HipRoll", "HipPitch", "KneePitch",
    "WheelFL", "WheelFR", "WheelB",
]

JOINT_TEMP_WARN     = 60.0   # °C — caution
JOINT_TEMP_CRITICAL = 75.0   # °C — dangerous, robot may shut down
BATTERY_LOW         = 20     # % — low battery warning
BATTERY_CRITICAL    = 10     # % — critical
BATTERY_TEMP_WARN   = 40.0   # °C — battery overheating

# NAOqi ALMemory keys
MEM_BATTERY_CHARGE  = "Device/SubDeviceList/Battery/Charge/Sensor/Value"
MEM_BATTERY_CURRENT = "Device/SubDeviceList/Battery/Current/Sensor/Value"
MEM_BATTERY_TEMP    = "Device/SubDeviceList/Battery/Temperature/Sensor/Value"
MEM_BATTERY_STATUS  = "Device/SubDeviceList/Battery/Status/Sensor/Value"

# ============================================================
# UTILITY
# ============================================================

def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def hr(char="=", width=68):
    print(char * width)

def section(title):
    hr()
    print(bold("  " + title))
    hr()

def row(label, status_ok, duration_s, detail, warn=False):
    """Print a single diagnostic row."""
    pad = 26
    label_str  = ("%-*s" % (pad, label + ":"))
    status     = status_str(status_ok, warn)
    dur_str    = dim("(%.3fs)" % duration_s)
    print("  %s %s  %s  %s" % (label_str, status, dur_str, detail))

def _proxy(service, ip, port, timeout=5):
    """Create ALProxy with a timeout guard."""
    start = time.time()
    p = ALProxy(service, ip, port)
    return p, time.time() - start

# ============================================================
# INDIVIDUAL CHECK FUNCTIONS
# Each returns: (ok: bool, warn: bool, duration: float, detail: str, data: dict)
# ============================================================

def check_network(ip, port):
    """TCP connect check — measures round-trip to robot NAOqi port."""
    start = time.time()
    try:
        s = socket.create_connection((ip, port), timeout=5)
        s.close()
        latency_ms = (time.time() - start) * 1000
        return True, False, time.time() - start, "latency %.1f ms" % latency_ms, {"latency_ms": round(latency_ms, 2)}
    except Exception as e:
        return False, False, time.time() - start, str(e), {}


def check_battery(ip, port):
    """Battery level, temperature, current, and charging state via ALMemory."""
    start = time.time()
    data  = {}
    try:
        batt = ALProxy("ALBattery", ip, port)
        mem  = ALProxy("ALMemory",  ip, port)

        # Charge level (0-100 %)
        charge = batt.getBatteryCharge()
        data["level_percent"] = charge

        # Charging flag — bit 7 of Status byte
        try:
            status_byte = int(mem.getData(MEM_BATTERY_STATUS))
            charging    = bool(status_byte & 0x80)
            data["charging"] = charging
        except Exception:
            charging = False
            data["charging"] = None

        # Battery temperature
        try:
            batt_temp = float(mem.getData(MEM_BATTERY_TEMP))
            data["temperature_c"] = round(batt_temp, 1)
        except Exception:
            batt_temp = None
            data["temperature_c"] = None

        # Current draw (negative = discharging)
        try:
            current_a = float(mem.getData(MEM_BATTERY_CURRENT))
            data["current_a"] = round(current_a, 3)
            # Rough runtime estimate (assume 26 Ah capacity for Pepper)
            if current_a < 0:
                capacity_ah   = 26.0
                remaining_ah  = capacity_ah * (charge / 100.0)
                runtime_hours = remaining_ah / abs(current_a)
                data["estimated_runtime_min"] = int(runtime_hours * 60)
            else:
                data["estimated_runtime_min"] = None
        except Exception:
            data["current_a"]           = None
            data["estimated_runtime_min"] = None

        # Determine status
        warn = False
        ok   = True
        if charge <= BATTERY_CRITICAL:
            ok   = False
            detail = "CRITICAL %d%% — charge immediately" % charge
        elif charge <= BATTERY_LOW:
            warn   = True
            detail = "%d%% (LOW)" % charge
        else:
            detail = "%d%%" % charge

        if batt_temp and batt_temp > BATTERY_TEMP_WARN:
            warn    = True
            detail += "  temp %.1f°C (HOT)" % batt_temp
        elif batt_temp:
            detail += "  temp %.1f°C" % batt_temp

        if charging:
            detail += "  [CHARGING]"

        if data.get("estimated_runtime_min"):
            detail += "  est. %d min remaining" % data["estimated_runtime_min"]

        return ok, warn, time.time() - start, detail, data

    except Exception as e:
        return False, False, time.time() - start, "ALBattery error: %s" % e, data


def check_temperatures(ip, port):
    """Read all joint temperatures from ALMemory."""
    start    = time.time()
    data     = {"joints": {}}
    max_temp = 0.0
    max_joint = None
    warn     = False
    ok       = True
    hot_joints = []

    try:
        mem = ALProxy("ALMemory", ip, port)

        for joint in PEPPER_JOINTS:
            key = "Device/SubDeviceList/%s/Temperature/Sensor/Value" % joint
            try:
                temp = float(mem.getData(key))
                status = "OK"
                if temp >= JOINT_TEMP_CRITICAL:
                    status = "CRITICAL"
                    ok     = False
                    hot_joints.append("%s=%.0f°C" % (joint, temp))
                elif temp >= JOINT_TEMP_WARN:
                    status = "WARN"
                    warn   = True
                    hot_joints.append("%s=%.0f°C" % (joint, temp))

                data["joints"][joint] = {"temp_c": round(temp, 1), "status": status}

                if temp > max_temp:
                    max_temp  = temp
                    max_joint = joint
            except Exception:
                data["joints"][joint] = {"temp_c": None, "status": "UNAVAILABLE"}

        data["max_temp_c"]    = round(max_temp, 1) if max_temp else None
        data["max_temp_joint"] = max_joint

        if hot_joints:
            detail = "HOT: " + ", ".join(hot_joints)
        elif max_joint:
            detail = "max %.1f°C @ %s — all nominal" % (max_temp, max_joint)
        else:
            detail = "no temp data available"

        return ok, warn, time.time() - start, detail, data

    except Exception as e:
        return False, False, time.time() - start, "ALMemory error: %s" % e, data


def check_system_info(ip, port, user, pwd):
    """Fetch robot firmware/OS version via SSH."""
    start = time.time()
    data  = {}
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=user, password=pwd, timeout=8)

        def run(cmd):
            _, out, _ = ssh.exec_command(cmd)
            return out.read().decode("utf-8", errors="replace").strip()

        data["naoqi_version"] = run("naoqi-bin --version 2>&1 | head -1")
        data["os_version"]    = run("cat /etc/nao-version 2>/dev/null || cat /etc/opennao-release 2>/dev/null || echo unknown")
        data["hostname"]      = run("hostname")
        data["uptime"]        = run("uptime -p 2>/dev/null || uptime")
        data["cpu_load"]      = run("cat /proc/loadavg | awk '{print $1\" \"$2\" \"$3}'")
        data["mem_free_mb"]   = run("free -m | awk 'NR==2{print $4}'")
        data["disk_free"]     = run("df -h / | awk 'NR==2{print $4\" free of \"$2}'")

        ssh.close()
        detail = "NAOqi %s | uptime: %s | cpu: %s | mem free: %s MB" % (
            data.get("naoqi_version", "?")[:30],
            data.get("uptime", "?")[:30],
            data.get("cpu_load", "?"),
            data.get("mem_free_mb", "?"),
        )
        return True, False, time.time() - start, detail, data

    except Exception as e:
        return False, False, time.time() - start, "SSH error: %s" % e, data


def check_service(service_name, ip, port):
    """Verify an ALProxy service is reachable."""
    start = time.time()
    try:
        ALProxy(service_name, ip, port)
        return True, False, time.time() - start, "connected", {}
    except Exception as e:
        return False, False, time.time() - start, str(e), {}


def check_tts(ip, port):
    """TTS: say a short diagnostic phrase."""
    start = time.time()
    try:
        tts = ALProxy("ALTextToSpeech", ip, port)
        tts.say("Diagnostic check.")
        return True, False, time.time() - start, "spoken OK", {}
    except Exception as e:
        return False, False, time.time() - start, str(e), {}


def check_memory_event(ip, port):
    """Raise an ALMemory event to verify the event bus."""
    start = time.time()
    try:
        mem = ALProxy("ALMemory", ip, port)
        mem.raiseEvent("Pepper/DiagnosticPing", 1)
        return True, False, time.time() - start, "event raised", {}
    except Exception as e:
        return False, False, time.time() - start, str(e), {}


def check_microphone(ip, port):
    """Record 2 s of audio from the front microphone."""
    remote = "/tmp/diag_test.wav"
    start  = time.time()
    try:
        audio = ALProxy("ALAudioRecorder", ip, port)
        try:
            audio.stopMicrophonesRecording()
        except Exception:
            pass
        audio.startMicrophonesRecording(remote, "wav", 16000, [0, 0, 1, 0])
        time.sleep(2.0)
        audio.stopMicrophonesRecording()
        return True, False, time.time() - start, "recorded to %s" % remote, {"remote_path": remote}
    except Exception as e:
        return False, False, time.time() - start, str(e), {}


def check_sftp(ip, user, pwd, remote_path, local_path):
    """Transfer a file from Pepper over SFTP."""
    start = time.time()
    try:
        transport = paramiko.Transport((ip, 22))
        transport.connect(username=user, password=pwd)
        sftp = paramiko.SFTPClient.from_transport(transport)
        sftp.get(remote_path, local_path)
        sftp.close()
        transport.close()
        size = os.path.getsize(local_path) if os.path.exists(local_path) else 0
        return True, False, time.time() - start, "transferred %d bytes" % size, {"size_bytes": size}
    except Exception as e:
        return False, False, time.time() - start, str(e), {}


def check_camera(ip, camera_port=8082):
    """Probe the camera HTTP snapshot server."""
    start = time.time()
    url   = "http://%s:%d/snapshot_b64" % (ip, camera_port)
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            body = r.json()
            w = body.get("width", "?")
            h = body.get("height", "?")
            return True, False, time.time() - start, "snapshot %sx%s" % (w, h), {"width": w, "height": h}
        return False, False, time.time() - start, "HTTP %d" % r.status_code, {}
    except Exception as e:
        return False, False, time.time() - start, str(e), {}


def check_backend(server_ip, server_port):
    """Check the Flask backend health endpoint."""
    start = time.time()
    url   = "http://%s:%d/api/health" % (server_ip, server_port)
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            body = r.json()
            uptime = body.get("uptime_seconds", "?")
            rag    = body.get("rag_ready", "?")
            return True, False, time.time() - start, "up %.0fs | rag=%s" % (uptime, rag), body
        return False, False, time.time() - start, "HTTP %d" % r.status_code, {}
    except Exception as e:
        return False, False, time.time() - start, str(e), {}


def check_posture(ip, port):
    """Tell Pepper to stand — tests motion and posture services."""
    start = time.time()
    try:
        motion  = ALProxy("ALMotion",       ip, port)
        posture = ALProxy("ALRobotPosture", ip, port)
        motion.wakeUp()
        posture.goToPosture("Stand", 0.5)
        return True, False, time.time() - start, "Stand posture OK", {}
    except Exception as e:
        return False, False, time.time() - start, str(e), {}


def check_leds(ip, port):
    """Flash eyes briefly to verify LED service."""
    start = time.time()
    try:
        leds = ALProxy("ALLeds", ip, port)
        leds.fadeRGB("FaceLeds", 0x00FF00, 0.3)    # green
        time.sleep(0.4)
        leds.fadeRGB("FaceLeds", 0xFFFFFF, 0.3)    # white (normal)
        return True, False, time.time() - start, "LED flash OK", {}
    except Exception as e:
        return False, False, time.time() - start, str(e), {}


def check_tablet(ip, port):
    """Verify the tablet service is reachable."""
    start = time.time()
    try:
        tab  = ALProxy("ALTabletService", ip, port)
        wifi = tab.getWifiStatus()
        return True, False, time.time() - start, "tablet wifi=%s" % wifi, {"wifi": wifi}
    except Exception as e:
        return False, False, time.time() - start, str(e), {}


# ============================================================
# MAIN DIAGNOSTIC RUNNER
# ============================================================

def run_full_diagnostic(cfg, args):
    robot_ip    = cfg["ROBOT_IP"]
    robot_port  = int(cfg.get("ROBOT_PORT", 9559))
    server_ip   = cfg.get("SERVER_IP", "127.0.0.1")
    server_port = int(cfg.get("SERVER_PORT", 8080))
    robot_user  = cfg.get("ROBOT_USER", "nao")
    robot_pwd   = cfg.get("ROBOT_PWD", "nao")

    report = {
        "timestamp":     now_str(),
        "robot_ip":      robot_ip,
        "robot_port":    robot_port,
        "server_ip":     server_ip,
        "server_port":   server_port,
        "overall_status": "OK",
        "checks":        {},
        "warnings":      [],
        "errors":        [],
    }

    any_fail = False
    any_warn = False

    def record(key, ok, warn, dur, detail, data):
        nonlocal any_fail, any_warn
        if not ok:
            any_fail = True
            report["errors"].append("%s: %s" % (key, detail))
        elif warn:
            any_warn = True
            report["warnings"].append("%s: %s" % (key, detail))
        report["checks"][key] = {
            "status":   "OK" if (ok and not warn) else ("WARN" if warn else "FAIL"),
            "duration_s": round(dur, 3),
            "detail":   detail,
            **data
        }
        row(key, ok, dur, detail, warn)

    # ── SECTION 1: NETWORK ──────────────────────────────────
    section("1 / NETWORK CONNECTIVITY")
    if not args.backend_only:
        ok, w, d, det, dat = check_network(robot_ip, robot_port)
        record("network_robot", ok, w, d, det, dat)
    if not args.robot_only and REQUESTS_OK:
        ok, w, d, det, dat = check_network(server_ip, server_port)
        record("network_backend", ok, w, d, det, dat)

    # ── SECTION 2: BATTERY ──────────────────────────────────
    if not args.backend_only and NAOQI_OK:
        section("2 / BATTERY STATUS")
        ok, w, d, det, dat = check_battery(robot_ip, robot_port)
        record("battery", ok, w, d, det, dat)

    # ── SECTION 3: TEMPERATURES ─────────────────────────────
    if not args.backend_only and NAOQI_OK:
        section("3 / JOINT & BATTERY TEMPERATURES")
        ok, w, d, det, dat = check_temperatures(robot_ip, robot_port)
        record("temperatures", ok, w, d, det, dat)

        # Print detailed temp table
        joints_data = dat.get("joints", {})
        if joints_data:
            print()
            print(dim("  Joint temperature map:"))
            for joint, info in sorted(joints_data.items()):
                temp  = info.get("temp_c")
                jstat = info.get("status", "?")
                if temp is None:
                    continue
                bar   = int(min(temp, 80) / 80.0 * 30)
                color = green if jstat == "OK" else (yellow if jstat == "WARN" else red)
                print("  %-22s %s  %.1f°C" % (joint, color("[" + "#" * bar + " " * (30 - bar) + "]"), temp))
            print()

    # ── SECTION 4: SYSTEM INFO ──────────────────────────────
    if not args.backend_only and PARAMIKO_OK:
        section("4 / ROBOT SYSTEM INFO (SSH)")
        ok, w, d, det, dat = check_system_info(robot_ip, robot_port, robot_user, robot_pwd)
        record("system_info", ok, w, d, det, dat)
        if ok:
            print()
            for k, v in dat.items():
                print("  %-20s %s" % (k + ":", dim(str(v))))
            print()

    # ── SECTION 5: NAOQI SERVICES ───────────────────────────
    if not args.backend_only and NAOQI_OK:
        section("5 / NAOQI SERVICES")
        for svc in [
            "ALTextToSpeech",
            "ALMotion",
            "ALRobotPosture",
            "ALNavigation",
            "ALBattery",
            "ALMemory",
            "ALLeds",
            "ALVideoDevice",
            "ALAudioRecorder",
            "ALAudioDevice",
            "ALFaceDetection",
            "ALBasicAwareness",
            "ALBehaviorManager",
            "ALTabletService",
            "ALSpeechRecognition",
            "ALAutonomousLife",
            "ALSystem",
            "ALAnimationPlayer",
        ]:
            ok, w, d, det, dat = check_service(svc, robot_ip, robot_port)
            record("svc_%s" % svc, ok, w, d, svc + " — " + det, dat)

    # ── SECTION 6: TTS TEST ─────────────────────────────────
    if not args.backend_only and NAOQI_OK and not args.quick:
        section("6 / VOICE — TTS")
        ok, w, d, det, dat = check_tts(robot_ip, robot_port)
        record("tts", ok, w, d, det, dat)

    # ── SECTION 7: MEMORY EVENT ─────────────────────────────
    if not args.backend_only and NAOQI_OK:
        section("7 / MEMORY EVENT BUS")
        ok, w, d, det, dat = check_memory_event(robot_ip, robot_port)
        record("memory_event", ok, w, d, det, dat)

    # ── SECTION 8: MICROPHONE ───────────────────────────────
    if not args.backend_only and NAOQI_OK and not args.quick:
        section("8 / MICROPHONE RECORDING TEST")
        ok, w, d, det, dat = check_microphone(robot_ip, robot_port)
        record("microphone", ok, w, d, det, dat)

    # ── SECTION 9: SFTP TRANSFER ────────────────────────────
    if not args.backend_only and PARAMIKO_OK and not args.quick:
        section("9 / SFTP FILE TRANSFER")
        local_dest = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "diagnostic_logs", "_last_diag_audio.wav"
        )
        ok, w, d, det, dat = check_sftp(robot_ip, robot_user, robot_pwd,
                                         "/tmp/diag_test.wav", local_dest)
        record("sftp", ok, w, d, det, dat)

    # ── SECTION 10: CAMERA ──────────────────────────────────
    if not args.backend_only and REQUESTS_OK:
        section("10 / CAMERA SNAPSHOT SERVER")
        ok, w, d, det, dat = check_camera(robot_ip)
        record("camera_server", ok, w, d, det, dat)

    # ── SECTION 11: FLASK BACKEND ───────────────────────────
    if not args.robot_only and REQUESTS_OK:
        section("11 / FLASK BACKEND HEALTH")
        ok, w, d, det, dat = check_backend(server_ip, server_port)
        record("backend_flask", ok, w, d, det, dat)

    # ── SECTION 12: MOTION / POSTURE ────────────────────────
    if not args.backend_only and NAOQI_OK and not args.quick:
        section("12 / MOTION & POSTURE")
        ok, w, d, det, dat = check_posture(robot_ip, robot_port)
        record("motion_posture", ok, w, d, det, dat)

    # ── SECTION 13: LED ─────────────────────────────────────
    if not args.backend_only and NAOQI_OK:
        section("13 / LED SUBSYSTEM")
        ok, w, d, det, dat = check_leds(robot_ip, robot_port)
        record("leds", ok, w, d, det, dat)

    # ── SECTION 14: TABLET ──────────────────────────────────
    if not args.backend_only and NAOQI_OK:
        section("14 / TABLET SERVICE")
        ok, w, d, det, dat = check_tablet(robot_ip, robot_port)
        record("tablet", ok, w, d, det, dat)

    # ── OVERALL STATUS ──────────────────────────────────────
    if any_fail:
        report["overall_status"] = "FAIL"
    elif any_warn:
        report["overall_status"] = "WARNING"
    else:
        report["overall_status"] = "OK"

    return report


# ============================================================
# STRESS TEST
# ============================================================

def run_stress_test(robot_ip, robot_port, trials, pause):
    section("END-TO-END STRESS TEST (%d trials)" % trials)
    success = 0
    for i in range(1, trials + 1):
        start = time.time()
        try:
            mem = ALProxy("ALMemory", robot_ip, robot_port)
            mem.raiseEvent("Pepper/StartListening", 1)
            ok  = True
            msg = "OK"
        except Exception as e:
            ok  = False
            msg = str(e)
        dur = time.time() - start
        indicator = green("OK  ") if ok else red("FAIL")
        print("  Trial %02d: %s  (%.3fs)  %s" % (i, indicator, dur, msg))
        if ok:
            success += 1
        time.sleep(pause)
    rate = 100.0 * success / trials
    color = green if rate == 100 else (yellow if rate >= 80 else red)
    print()
    print("  Result: %s — %d / %d  (%.0f%%)" % (color("%.0f%%" % rate), success, trials, rate))


# ============================================================
# REPORT SAVING
# ============================================================

def save_report(report, log_dir):
    json_path    = os.path.join(log_dir, "report.json")
    summary_path = os.path.join(log_dir, "summary.txt")

    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)

    with open(summary_path, "w") as f:
        f.write("PEPPER DIAGNOSTIC SUMMARY\n")
        f.write("=" * 50 + "\n")
        f.write("Timestamp:      %s\n" % report["timestamp"])
        f.write("Robot:          %s:%s\n" % (report["robot_ip"], report["robot_port"]))
        f.write("Backend:        %s:%s\n" % (report["server_ip"], report["server_port"]))
        f.write("Overall Status: %s\n\n" % report["overall_status"])

        f.write("CHECK RESULTS:\n")
        for k, v in sorted(report["checks"].items()):
            f.write("  %-35s %s  (%.3fs)\n" % (k + ":", v["status"], v["duration_s"]))

        if report["warnings"]:
            f.write("\nWARNINGS:\n")
            for w in report["warnings"]:
                f.write("  - %s\n" % w)

        if report["errors"]:
            f.write("\nERRORS:\n")
            for e in report["errors"]:
                f.write("  - %s\n" % e)

    return json_path, summary_path


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Pepper Full Diagnostic System")
    parser.add_argument("--quick",        action="store_true",
                        help="Skip TTS, recording, motion, and SFTP tests")
    parser.add_argument("--robot-only",   action="store_true",
                        help="Skip backend Flask checks")
    parser.add_argument("--backend-only", action="store_true",
                        help="Skip robot NAOqi/SSH checks")
    parser.add_argument("--stress",       type=int, default=0, metavar="N",
                        help="Run N-trial end-to-end stress test after diagnostics")
    parser.add_argument("--no-tts",       action="store_true",
                        help="Suppress TTS announce on robot during diagnostics")
    args = parser.parse_args()

    # Load config
    cfg = load_config()

    # Set up log directory
    ts       = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    root_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir  = os.path.join(root_dir, "diagnostic_logs", ts)
    os.makedirs(log_dir)

    # Redirect stdout → tee to terminal.log
    log_path = os.path.join(log_dir, "terminal.log")
    tee      = TeeLogger(log_path)
    sys.stdout = tee

    try:
        # ── Header ──────────────────────────────────────────
        hr("═")
        print(bold("  PEPPER FULL DIAGNOSTIC SYSTEM"))
        print(bold("  %s" % now_str()))
        hr("═")
        print("  Robot:    %s:%s" % (cfg["ROBOT_IP"], cfg.get("ROBOT_PORT", 9559)))
        print("  Backend:  %s:%s" % (cfg.get("SERVER_IP", "127.0.0.1"), cfg.get("SERVER_PORT", 8080)))
        print("  Log dir:  %s" % log_dir)
        print("  Modes:    naoqi=%s  paramiko=%s  requests=%s" % (
            green("OK") if NAOQI_OK else red("MISSING"),
            green("OK") if PARAMIKO_OK else yellow("MISSING"),
            green("OK") if REQUESTS_OK else yellow("MISSING"),
        ))
        hr("─")
        print()

        if not NAOQI_OK and not args.backend_only:
            print(yellow("  [WARN] naoqi SDK not found — robot checks will be skipped."))
            print(yellow("         Install the naoqi Python 2.7 SDK or run with --backend-only"))
            print()

        # ── Run diagnostic ──────────────────────────────────
        report = run_full_diagnostic(cfg, args)

        # ── Stress test ─────────────────────────────────────
        if args.stress > 0 and NAOQI_OK and not args.backend_only:
            run_stress_test(cfg["ROBOT_IP"], int(cfg.get("ROBOT_PORT", 9559)),
                            args.stress, pause=2.0)

        # ── Final summary ────────────────────────────────────
        hr("═")
        overall = report["overall_status"]
        color   = green if overall == "OK" else (yellow if overall == "WARNING" else red)
        print()
        print(bold("  OVERALL RESULT: %s" % color(overall)))
        print()

        total   = len(report["checks"])
        n_ok    = sum(1 for v in report["checks"].values() if v["status"] == "OK")
        n_warn  = sum(1 for v in report["checks"].values() if v["status"] == "WARN")
        n_fail  = sum(1 for v in report["checks"].values() if v["status"] == "FAIL")
        print("  Checks: %s pass  %s warn  %s fail  (total %d)" % (
            green(str(n_ok)), yellow(str(n_warn)), red(str(n_fail)), total))

        if report["warnings"]:
            print()
            print(yellow("  Warnings:"))
            for w in report["warnings"]:
                print(yellow("    * %s" % w))

        if report["errors"]:
            print()
            print(red("  Errors:"))
            for e in report["errors"]:
                print(red("    x %s" % e))

        # Battery quick-view
        batt = report["checks"].get("battery", {})
        if batt and batt.get("level_percent") is not None:
            lvl  = batt["level_percent"]
            bar  = int(lvl / 100.0 * 40)
            bcol = green if lvl > 40 else (yellow if lvl > BATTERY_LOW else red)
            print()
            print("  Battery: %s  %s%%" % (bcol("[" + "█" * bar + "░" * (40 - bar) + "]"), lvl))

        print()
        hr("═")

        # ── Save report ──────────────────────────────────────
        json_path, summary_path = save_report(report, log_dir)

        print()
        print(bold("  Files saved:"))
        print("    terminal.log → %s" % log_path)
        print("    report.json  → %s" % json_path)
        print("    summary.txt  → %s" % summary_path)
        print()
        print(dim("  [%s] Diagnostics complete." % now_str()))
        hr("═")

    except KeyboardInterrupt:
        print(yellow("\n  [INTERRUPTED] Diagnostic stopped by user."))
    except Exception as e:
        print(red("\n  [FATAL] Unexpected error: %s" % e))
        traceback.print_exc()
    finally:
        # Restore stdout and close log
        sys.stdout = tee._terminal
        tee.close()
        print()
        print(bold("Log saved to: %s" % log_path))


if __name__ == "__main__":
    main()
