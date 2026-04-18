# -*- coding: utf-8 -*-
"""
main.py - Pepper Medical Assistant System Launcher
=====================================================
Orchestrates all subsystems and performs a welcome gesture on startup.

Usage:
    python main.py --robot-ip 10.0.0.10 --server-ip 192.168.1.5
    python main.py --robot-ip 10.0.0.10 --pre-check          # health check before launch
    python main.py --robot-ip 10.0.0.10 --pre-check --force  # launch even if warnings

Pre-check (--pre-check):
    Runs 5 checks before any subsystem starts:
      1. Network   — TCP connect latency to robot NAOqi port
      2. Battery   — level %, temperature; aborts if <= 10 %
      3. Core services   — TTS, Motion, Posture, Memory (abort if missing)
      4. Optional services — Nav, Tablet, Camera, Audio, LEDs (warn if missing)
      5. Temperatures — warns if any joint > 60 °C, aborts if > 75 °C

Subsystems launched:
    1. Flask backend   (pepper_ui/server/app/app.py)
    2. WebSocket bridge (pepper_voice/ws_bridge.py)
    3. Voice pipeline   (pepper_voice/MainVoice.py)
    4. Navigation bridge (navigation/nav_bridge.py)
    5. Tablet UI loader  (pepper_ui/robot/show_tablet.py)
"""

import os
import sys
import time
import socket
import subprocess
import argparse
import threading

# =====================================================================
# Configuration
# =====================================================================
ROBOT_IP    = "127.0.0.1"
ROBOT_PORT  = "9559"
SERVER_IP   = "127.0.0.1"
SERVER_PORT = "8080"
WS_PORT     = "8765"

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# =====================================================================
# Pre-Check — Run before any subsystem launches
# =====================================================================

# ANSI helpers (Windows 10+ supports VT codes in most terminals)
def _c(code, text):
    return "\033[%sm%s\033[0m" % (code, text)

def _green(t):  return _c("32;1", t)
def _yellow(t): return _c("33;1", t)
def _red(t):    return _c("31;1", t)
def _bold(t):   return _c("1", t)
def _dim(t):    return _c("2", t)

_PASS = _green("  PASS")
_WARN = _yellow("  WARN")
_FAIL = _red("  FAIL")
_SKIP = _dim("  SKIP")


def _pre_row(label, status, detail=""):
    """Print one pre-check result row."""
    pad = 32
    print("  %-*s %s  %s" % (pad, label, status, _dim(detail)))


def run_pre_check(robot_ip, robot_port, force=False):
    """
    Quick pre-flight health check.  Returns True if safe to proceed,
    False if a critical issue was found (unless force=True).

    Checks (in order):
      1. Network — TCP connect to robot NAOqi port
      2. Battery — level + temperature (aborts if <= 10 %)
      3. Core NAOqi services — TTS, Motion, Posture, Memory
      4. Optional NAOqi services — Nav, Camera, Tablet, Audio
      5. Joint temperatures — warns if any joint > 60 °C
    """
    port = int(robot_port)

    print("")
    print("=" * 60)
    print(_bold("  PRE-FLIGHT DIAGNOSTIC"))
    print("  Robot: %s:%d" % (robot_ip, port))
    print("=" * 60)

    critical = []   # things that should stop launch
    warnings = []   # things to note but allow launch

    # ── 1. NETWORK ─────────────────────────────────────────
    print(_bold("\n  [1/5] Network"))
    t0 = time.time()
    try:
        s = socket.create_connection((robot_ip, port), timeout=5)
        s.close()
        latency = (time.time() - t0) * 1000
        _pre_row("TCP connect to robot", _PASS, "latency %.0f ms" % latency)
        network_ok = True
    except Exception as e:
        _pre_row("TCP connect to robot", _FAIL, str(e))
        critical.append("Cannot reach robot at %s:%d" % (robot_ip, port))
        network_ok = False

    if not network_ok:
        # No point continuing NAOqi checks
        _print_pre_summary(critical, warnings, force)
        return force

    # ── 2. BATTERY ─────────────────────────────────────────
    print(_bold("\n  [2/5] Battery"))
    try:
        from naoqi import ALProxy as _ALProxy

        batt = _ALProxy("ALBattery", robot_ip, port)
        mem  = _ALProxy("ALMemory",  robot_ip, port)
        level = batt.getBatteryCharge()

        # Charging flag (bit 7 of status byte)
        try:
            status_byte = int(mem.getData("Device/SubDeviceList/Battery/Status/Sensor/Value"))
            charging    = bool(status_byte & 0x80)
        except Exception:
            charging = False

        # Battery temperature
        try:
            btemp = float(mem.getData("Device/SubDeviceList/Battery/Temperature/Sensor/Value"))
            temp_str = "temp %.1f°C" % btemp
            if btemp > 40.0:
                warnings.append("Battery temperature %.1f°C (>40°C)" % btemp)
                temp_str = _yellow("temp %.1f°C HOT" % btemp)
        except Exception:
            btemp    = None
            temp_str = "temp N/A"

        # Build bar
        bar   = int(min(level, 100) / 100.0 * 20)
        bcol  = _green if level > 40 else (_yellow if level > 20 else _red)
        bar_s = bcol("[" + "█" * bar + "░" * (20 - bar) + "] %d%%" % level)

        charging_s = "  charging" if charging else ""

        if level <= 10:
            _pre_row("Battery level", _FAIL, "%d%% — CRITICAL, charge now" % level)
            critical.append("Battery at %d%% — too low to operate safely" % level)
        elif level <= 20:
            _pre_row("Battery level", _WARN, bar_s + charging_s)
            warnings.append("Battery low (%d%%)" % level)
        else:
            _pre_row("Battery level", _PASS, bar_s + charging_s)

        if btemp and btemp > 40.0:
            _pre_row("Battery temperature", _WARN, temp_str)
        elif btemp:
            _pre_row("Battery temperature", _PASS, temp_str)

    except ImportError:
        _pre_row("Battery (naoqi)", _SKIP, "naoqi SDK not on PYTHONPATH")
    except Exception as e:
        _pre_row("Battery", _WARN, "Could not read — %s" % e)
        warnings.append("Battery check failed: %s" % e)

    # ── 3. CORE NAOQI SERVICES ─────────────────────────────
    print(_bold("\n  [3/5] Core NAOqi Services"))
    CORE_SERVICES = [
        ("ALTextToSpeech", True),
        ("ALMotion",       True),
        ("ALRobotPosture", True),
        ("ALMemory",       True),
    ]
    try:
        from naoqi import ALProxy as _ALProxy
        for svc, required in CORE_SERVICES:
            t0 = time.time()
            try:
                _ALProxy(svc, robot_ip, port)
                _pre_row(svc, _PASS, "%.0f ms" % ((time.time() - t0) * 1000))
            except Exception as e:
                if required:
                    _pre_row(svc, _FAIL, str(e))
                    critical.append("%s unavailable: %s" % (svc, e))
                else:
                    _pre_row(svc, _WARN, str(e))
                    warnings.append("%s unavailable" % svc)
    except ImportError:
        _pre_row("Core services (naoqi)", _SKIP, "naoqi SDK not on PYTHONPATH")

    # ── 4. OPTIONAL NAOQI SERVICES ─────────────────────────
    print(_bold("\n  [4/5] Optional NAOqi Services"))
    OPTIONAL_SERVICES = [
        "ALNavigation",
        "ALTabletService",
        "ALVideoDevice",
        "ALAudioRecorder",
        "ALLeds",
        "ALBasicAwareness",
        "ALAutonomousLife",
        "ALBehaviorManager",
        "ALSpeechRecognition",
    ]
    try:
        from naoqi import ALProxy as _ALProxy
        for svc in OPTIONAL_SERVICES:
            t0 = time.time()
            try:
                _ALProxy(svc, robot_ip, port)
                _pre_row(svc, _PASS, "%.0f ms" % ((time.time() - t0) * 1000))
            except Exception as e:
                _pre_row(svc, _WARN, str(e))
                warnings.append("%s unavailable" % svc)
    except ImportError:
        _pre_row("Optional services (naoqi)", _SKIP, "naoqi SDK not on PYTHONPATH")

    # ── 5. JOINT TEMPERATURES ──────────────────────────────
    print(_bold("\n  [5/5] Joint Temperatures"))
    JOINTS = [
        "HeadYaw", "HeadPitch",
        "LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll",
        "RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll",
        "HipRoll", "HipPitch", "KneePitch",
    ]
    try:
        from naoqi import ALProxy as _ALProxy
        mem     = _ALProxy("ALMemory", robot_ip, port)
        hot     = []
        max_t   = 0.0
        max_j   = None
        readable = 0
        for joint in JOINTS:
            key = "Device/SubDeviceList/%s/Temperature/Sensor/Value" % joint
            try:
                t = float(mem.getData(key))
                readable += 1
                if t > max_t:
                    max_t = t
                    max_j = joint
                if t >= 75.0:
                    hot.append(_red("%s=%.0f°C" % (joint, t)))
                    critical.append("Joint %s at %.0f°C — CRITICAL" % (joint, t))
                elif t >= 60.0:
                    hot.append(_yellow("%s=%.0f°C" % (joint, t)))
                    warnings.append("Joint %s at %.0f°C — warm" % (joint, t))
            except Exception:
                pass

        if readable == 0:
            _pre_row("Joint temperatures", _SKIP, "no sensor data available")
        elif hot:
            _pre_row("Joint temperatures", _WARN if not critical else _FAIL,
                     "HOT: " + ", ".join(hot))
        else:
            _pre_row("Joint temperatures", _PASS,
                     "max %.1f°C @ %s — all nominal" % (max_t, max_j) if max_j else "all nominal")

    except ImportError:
        _pre_row("Joint temperatures (naoqi)", _SKIP, "naoqi SDK not on PYTHONPATH")
    except Exception as e:
        _pre_row("Joint temperatures", _WARN, str(e))

    # ── SUMMARY ────────────────────────────────────────────
    return _print_pre_summary(critical, warnings, force)


def _print_pre_summary(critical, warnings, force):
    """Print summary block and return True (proceed) / False (abort)."""
    print("")
    print("=" * 60)

    if critical:
        print(_red("  PRE-CHECK RESULT: CRITICAL ISSUES FOUND"))
        for c in critical:
            print(_red("    ✗ %s" % c))
    elif warnings:
        print(_yellow("  PRE-CHECK RESULT: WARNINGS — proceed with caution"))
        for w in warnings:
            print(_yellow("    ! %s" % w))
    else:
        print(_green("  PRE-CHECK RESULT: ALL CLEAR — ready to launch"))

    print("=" * 60)
    print("")

    if critical:
        if force:
            print(_yellow("  [--force] Ignoring critical issues and launching anyway."))
            print("")
            return True
        else:
            print(_red("  Launch aborted. Fix the issues above, then retry."))
            print(_dim("  To launch anyway:  python main.py --pre-check --force"))
            print("")
            return False

    return True

# =====================================================================
# Welcome Gesture - Wave + Greeting
# =====================================================================
def welcome_gesture(robot_ip, robot_port):
    """
    Pepper waves and introduces herself when the system starts.
    Uses NAOqi ALMotion for a custom wave and ALTextToSpeech for greeting.
    """
    try:
        from naoqi import ALProxy
    except ImportError:
        print("[WELCOME] NAOqi not available - skipping welcome gesture.")
        print("[WELCOME] (Robot gestures only work with Python 2.7 + pynaoqi)")
        return

    ip = str(robot_ip)
    port = int(robot_port)

    try:
        motion  = ALProxy("ALMotion",        ip, port)
        posture = ALProxy("ALRobotPosture",  ip, port)
        tts     = ALProxy("ALTextToSpeech",  ip, port)
        anim    = ALProxy("ALAnimationPlayer", ip, port)
        leds    = ALProxy("ALLeds",          ip, port)
    except Exception as e:
        print("[WELCOME] Cannot connect to Pepper at {}:{} - {}".format(ip, port, e))
        return

    print("[WELCOME] Performing welcome gesture...")

    try:
        # 1. Wake up and stand
        motion.wakeUp()
        posture.goToPosture("StandInit", 0.5)
        time.sleep(0.5)

        # 2. Eye LEDs: warm white fade-in
        try:
            leds.fadeRGB("FaceLeds", 0xFFCC66, 1.0)
        except Exception:
            pass

        # 3. Wave animation + greeting in parallel
        #    Use ALAnimationPlayer for the built-in wave gesture
        def play_wave():
            try:
                anim.run("animations/Stand/Gestures/Hey_3")
            except Exception:
                # Fallback: manual right arm wave
                try:
                    manual_wave(motion)
                except Exception as e2:
                    print("[WELCOME] Wave fallback failed: {}".format(e2))

        wave_thread = threading.Thread(target=play_wave)
        wave_thread.start()

        # Small delay so arm starts raising before speech
        time.sleep(0.8)

        # 4. Greeting speech
        tts.setLanguage("English")
        tts.say("Hello! I am Pepper, your personal medical assistant at Andalusia Hospital. "
                "I can help you book appointments, find doctors, guide you to rooms, "
                "and answer your health questions. "
                "Tap my screen or speak to me to get started!")

        wave_thread.join(timeout=5)

        # 5. Return to neutral standing pose
        time.sleep(0.3)
        posture.goToPosture("StandInit", 0.5)

        # 6. Reset eye LEDs to default white
        try:
            leds.fadeRGB("FaceLeds", 0xFFFFFF, 0.5)
        except Exception:
            pass

        print("[WELCOME] Welcome gesture complete.")

    except Exception as e:
        print("[WELCOME] Gesture error: {}".format(e))
        # Try at least to say the greeting
        try:
            tts.say("Hello! I am Pepper, your personal medical assistant.")
        except Exception:
            pass


def manual_wave(motion):
    """
    Fallback wave using direct joint control if ALAnimationPlayer
    doesn't have the Hey_3 animation installed.
    Raises the right arm and waves side to side.
    """
    names  = ["RShoulderPitch", "RShoulderRoll", "RElbowRoll", "RElbowYaw", "RWristYaw"]

    # Raise arm up and out
    angles_up   = [-0.5, -0.3, 1.0, 1.2, 0.0]
    motion.setAngles(names, angles_up, 0.2)
    time.sleep(0.8)

    # Wave: rotate wrist back and forth
    for _ in range(3):
        motion.setAngles(["RWristYaw"], [0.6], 0.3)
        time.sleep(0.3)
        motion.setAngles(["RWristYaw"], [-0.6], 0.3)
        time.sleep(0.3)

    # Lower arm back
    angles_down = [1.4, 0.1, 0.5, 0.0, 0.0]
    motion.setAngles(names, angles_down, 0.15)
    time.sleep(0.8)


# =====================================================================
# Subsystem Launchers
# =====================================================================
def build_env():
    """Build environment variables dict for child processes."""
    env = os.environ.copy()
    env["ROBOT_IP"]    = ROBOT_IP
    env["ROBOT_PORT"]  = ROBOT_PORT
    env["SERVER_IP"]   = SERVER_IP
    env["SERVER_PORT"] = SERVER_PORT
    env["WS_PORT"]     = WS_PORT
    return env


def launch_subprocess(name, cmd, cwd=None):
    """Launch a subprocess and return its Popen handle."""
    env = build_env()
    print("[MAIN] Starting {} ...".format(name))
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd or PROJECT_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        print("[MAIN] {} started (PID {})".format(name, proc.pid))
        return proc
    except Exception as e:
        print("[MAIN] Failed to start {}: {}".format(name, e))
        return None


def stream_output(name, proc):
    """Stream subprocess output line by line in a background thread."""
    if proc is None or proc.stdout is None:
        return
    try:
        for line in iter(proc.stdout.readline, b''):
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                print("[{}] {}".format(name, text))
    except Exception:
        pass


# =====================================================================
# Main Orchestrator
# =====================================================================
def main():
    global ROBOT_IP, ROBOT_PORT, SERVER_IP, SERVER_PORT, WS_PORT

    parser = argparse.ArgumentParser(description="Pepper Medical Assistant - System Launcher")
    parser.add_argument("--robot-ip",   default=ROBOT_IP,   help="Pepper robot IP (default: 127.0.0.1)")
    parser.add_argument("--robot-port", default=ROBOT_PORT, help="NAOqi port (default: 9559)")
    parser.add_argument("--server-ip",  default=SERVER_IP,  help="Backend server IP (default: 127.0.0.1)")
    parser.add_argument("--server-port",default=SERVER_PORT, help="Flask server port (default: 8080)")
    parser.add_argument("--ws-port",    default=WS_PORT,    help="WebSocket port (default: 8765)")
    parser.add_argument("--no-gesture",  action="store_true", help="Skip welcome gesture")
    parser.add_argument("--no-voice",    action="store_true", help="Don't start voice pipeline")
    parser.add_argument("--no-nav",      action="store_true", help="Don't start navigation bridge")
    parser.add_argument("--no-tablet",   action="store_true", help="Don't load tablet UI")
    parser.add_argument("--pre-check",   action="store_true",
                        help="Run pre-flight diagnostic before launching subsystems")
    parser.add_argument("--force",       action="store_true",
                        help="Launch even if --pre-check finds critical issues")
    args = parser.parse_args()

    ROBOT_IP    = args.robot_ip
    ROBOT_PORT  = args.robot_port
    SERVER_IP   = args.server_ip
    SERVER_PORT = args.server_port
    WS_PORT     = args.ws_port

    print("")
    print("==============================================")
    print("   PEPPER MEDICAL ASSISTANT - SYSTEM LAUNCHER")
    print("   Robot:   {}:{}".format(ROBOT_IP, ROBOT_PORT))
    print("   Server:  {}:{}".format(SERVER_IP, SERVER_PORT))
    print("   WS:      {}:{}".format(SERVER_IP, WS_PORT))
    print("==============================================")
    print("")

    processes = []

    # --- 0. Pre-flight diagnostic (--pre-check) ---
    if args.pre_check:
        ok = run_pre_check(ROBOT_IP, ROBOT_PORT, force=args.force)
        if not ok:
            sys.exit(1)

    # --- 1. Welcome Gesture ---
    if not args.no_gesture:
        welcome_gesture(ROBOT_IP, ROBOT_PORT)
    else:
        print("[MAIN] Skipping welcome gesture (--no-gesture)")

    # --- 2. Start Flask Backend (Python 3) ---
    flask_proc = launch_subprocess(
        "FLASK",
        [sys.executable, "app.py"],
        cwd=os.path.join(PROJECT_DIR, "pepper_ui", "server", "app"),
    )
    if flask_proc:
        processes.append(("FLASK", flask_proc))
        t = threading.Thread(target=stream_output, args=("FLASK", flask_proc))
        t.daemon = True
        t.start()

    # --- 3. Start WebSocket Bridge (Python 3) ---
    ws_proc = launch_subprocess(
        "WS_BRIDGE",
        [sys.executable, "ws_bridge.py"],
        cwd=os.path.join(PROJECT_DIR, "pepper_voice"),
    )
    if ws_proc:
        processes.append(("WS_BRIDGE", ws_proc))
        t = threading.Thread(target=stream_output, args=("WS_BRIDGE", ws_proc))
        t.daemon = True
        t.start()

    # Allow servers to start before launching robot-side scripts
    print("[MAIN] Waiting for servers to initialize...")
    time.sleep(3)

    # --- 4. Start Voice Pipeline (Python 2.7 on robot env) ---
    if not args.no_voice:
        voice_proc = launch_subprocess(
            "VOICE",
            [sys.executable, "MainVoice.py"],
            cwd=os.path.join(PROJECT_DIR, "pepper_voice"),
        )
        if voice_proc:
            processes.append(("VOICE", voice_proc))
            t = threading.Thread(target=stream_output, args=("VOICE", voice_proc))
            t.daemon = True
            t.start()

    # --- 5. Start Navigation Bridge (Python 2.7 on robot env) ---
    if not args.no_nav:
        nav_proc = launch_subprocess(
            "NAV",
            [sys.executable, "nav_bridge.py"],
            cwd=os.path.join(PROJECT_DIR, "navigation"),
        )
        if nav_proc:
            processes.append(("NAV", nav_proc))
            t = threading.Thread(target=stream_output, args=("NAV", nav_proc))
            t.daemon = True
            t.start()

    # --- 6. Load Tablet UI ---
    if not args.no_tablet:
        tablet_proc = launch_subprocess(
            "TABLET",
            [sys.executable, "show_tablet.py"],
            cwd=os.path.join(PROJECT_DIR, "pepper_ui", "robot"),
        )
        if tablet_proc:
            processes.append(("TABLET", tablet_proc))
            t = threading.Thread(target=stream_output, args=("TABLET", tablet_proc))
            t.daemon = True
            t.start()

    # --- Keep running until Ctrl+C ---
    print("")
    print("[MAIN] All subsystems launched. Press Ctrl+C to shut down.")
    print("")

    try:
        while True:
            # Check if any critical process died
            for name, proc in processes:
                if proc.poll() is not None:
                    print("[MAIN] WARNING: {} exited with code {}".format(name, proc.returncode))
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n[MAIN] Shutting down all subsystems...")
        for name, proc in processes:
            try:
                proc.terminate()
                print("[MAIN] Terminated {}".format(name))
            except Exception:
                pass

        # Wait briefly for clean shutdown
        time.sleep(2)
        for name, proc in processes:
            if proc.poll() is None:
                try:
                    proc.kill()
                    print("[MAIN] Killed {}".format(name))
                except Exception:
                    pass

        print("[MAIN] All subsystems stopped. Goodbye!")


if __name__ == "__main__":
    main()
