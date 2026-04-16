# -*- coding: utf-8 -*-
# nav_bridge.py - Navigation Bridge for Pepper Robot
# Layer: Robot Layer (Python 2.7, NAOqi environment)
#
# NAVIGATION STRATEGY (v2 - Segmented navigateTo):
#   1. Uses ALNavigation.navigateTo() in segments of max 2.5m.
#      navigateTo() has built-in obstacle avoidance using ALL sensors
#      (sonar, depth camera, laser) — no SLAM map required.
#   2. After each segment, re-reads hardware odometry via
#      ALMotion.getRobotPosition(True) to compute remaining distance.
#   3. If navigateTo() fails for a segment, falls back to ALMotion.moveTo().
#   4. Each segment has a 45-second timeout to prevent hangs.
#   5. Shows "Guiding you to Doctor's Room" on the tablet during navigation.
#
# WHY NOT SLAM:
#   Pepper's built-in SLAM (navigateToInMap) is unreliable. The 15-beam
#   base LIDAR produces sparse data that yields poor maps. Academic research
#   confirms this. Segmented navigateTo() with real-time obstacle avoidance
#   is far more reliable for a 10m-radius environment.
#
# USAGE:
#   python nav_bridge.py
#
# ENVIRONMENT VARIABLES (set by main.py):
#   ROBOT_IP    - Pepper robot IP address (default: 127.0.0.1)
#   ROBOT_PORT  - NAOqi port              (default: 9559)
#   SERVER_IP   - Backend PC IP address   (default: 192.168.1.50)
#   SERVER_PORT - Flask server port       (default: 8080)
#   WS_PORT     - WebSocket bridge port   (default: 8765)

import json
import math
import threading
import time
import os
import sys

from websocket import create_connection

try:
    from naoqi import ALProxy
    NAOQI_AVAILABLE = True
except ImportError:
    NAOQI_AVAILABLE = False
    print("[WARN] NAOqi SDK not found. Running in simulation mode.")

# Python 2 URL encoding
try:
    from urllib import quote as url_quote
except ImportError:
    from urllib.parse import quote as url_quote

# =====================================================================
# Configuration
# =====================================================================
ROBOT_IP    = os.environ.get("ROBOT_IP",    "127.0.0.1")
ROBOT_PORT  = int(os.environ.get("ROBOT_PORT", "9559"))
SERVER_IP   = os.environ.get("SERVER_IP",   "192.168.1.50")
SERVER_PORT = os.environ.get("SERVER_PORT", "8080")
WS_PORT     = os.environ.get("WS_PORT",    "8765")
SERVER_WS   = "ws://" + SERVER_IP + ":" + WS_PORT
SERVER_URL  = "http://" + SERVER_IP + ":" + SERVER_PORT

# Voice flag files (shared with MainVoice.py)
VOICE_DIR       = os.environ.get("VOICE_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pepper_voice"))
VOICE_FLAG_FILE = os.path.join(VOICE_DIR, "voice_start.flag")
LANG_FLAG_FILE  = os.path.join(VOICE_DIR, "lang.flag")

# Navigation constants
MAX_SEGMENT     = 2.5     # meters per navigateTo() call (API limit is 3m)
ARRIVAL_THRESH  = 0.30    # meters — close enough to declare arrival
SEGMENT_TIMEOUT = 45.0    # seconds — max time per segment before abort
MAX_SEGMENTS    = 10      # safety cap — prevent infinite retry loops
SECURITY_ORTHO  = 0.15    # reduced orthogonal collision distance (default 0.4)
SECURITY_TAN    = 0.05    # reduced tangential collision distance (default 0.1)

# =====================================================================
# Global State
# =====================================================================
navigation_proxy = None
tts_proxy        = None
motion_proxy     = None
posture_proxy    = None
awareness_proxy  = None
battery_proxy    = None
tablet_proxy     = None
is_navigating    = False
ws_conn          = None
current_lang     = "en"
nav_lock         = threading.Lock()


def tts_say(text, lang=None):
    """Speak text in the correct language."""
    if not tts_proxy:
        return
    if lang is None:
        lang = current_lang
    try:
        if lang == "ar":
            tts_proxy.setLanguage("Arabic")
        else:
            tts_proxy.setLanguage("English")
        tts_proxy.say(text.encode("utf-8") if isinstance(text, bytes) is False else text)
    except Exception as e:
        print("[WARN] TTS failed: " + str(e))


# =====================================================================
# Startup Greeting
# =====================================================================
def _startup_greeting():
    """Wave and introduce Pepper on boot."""
    if not motion_proxy or not tts_proxy:
        return
    try:
        print("[GREET] Pepper is waving and introducing itself...")
        names  = ["RShoulderPitch", "RShoulderRoll", "RElbowRoll", "RWristYaw"]
        angles = [-0.2, -0.3, 1.0, 0.0]
        motion_proxy.setAngles(names, angles, 0.15)
        time.sleep(0.6)

        for _ in range(3):
            motion_proxy.setAngles("RWristYaw", 0.5, 0.4)
            time.sleep(0.25)
            motion_proxy.setAngles("RWristYaw", -0.5, 0.4)
            time.sleep(0.25)

        tts_proxy.setLanguage("English")
        tts_proxy.say("Hello! I am Pepper, your medical assistant at Andalusia Hospital. "
                      "You can talk to me, or use the touchscreen to get started. "
                      "I am here to help!".encode("utf-8"))

        motion_proxy.setAngles(names, [1.5, 0.1, 0.5, 0.0], 0.15)
        time.sleep(0.5)
        print("[GREET] Startup greeting complete.")
    except Exception as e:
        print("[GREET] Greeting failed (non-critical): " + str(e))


# =====================================================================
# Robot Initialization
# =====================================================================
def init_robot():
    """
    Initialize NAOqi proxies. No SLAM map needed — we use segmented
    ALNavigation.navigateTo() which has real-time obstacle avoidance.
    """
    global navigation_proxy, tts_proxy, motion_proxy, posture_proxy
    global awareness_proxy, battery_proxy, tablet_proxy

    if not NAOQI_AVAILABLE:
        print("[WARN] Hardware initialization skipped (NAOqi not available).")
        return False

    try:
        print("[INIT] Connecting to NAOqi on " + ROBOT_IP + ":" + str(ROBOT_PORT))
        tts_proxy        = ALProxy("ALTextToSpeech", ROBOT_IP, ROBOT_PORT)
        motion_proxy     = ALProxy("ALMotion",       ROBOT_IP, ROBOT_PORT)
        navigation_proxy = ALProxy("ALNavigation",   ROBOT_IP, ROBOT_PORT)
        posture_proxy    = ALProxy("ALRobotPosture", ROBOT_IP, ROBOT_PORT)

        # Battery check
        try:
            battery_proxy = ALProxy("ALBattery", ROBOT_IP, ROBOT_PORT)
            charge = battery_proxy.getBatteryCharge()
            print("[INIT] Battery level: " + str(charge) + "%")
            if charge < 30:
                print("[WARN] Battery below 30% — navigation may be less accurate.")
        except Exception as e:
            print("[INIT] Could not read battery: " + str(e))

        # Tablet proxy (for showing navigation page)
        try:
            tablet_proxy = ALProxy("ALTabletService", ROBOT_IP, ROBOT_PORT)
            print("[INIT] ALTabletService connected.")
        except Exception as e:
            print("[INIT] Could not connect ALTabletService: " + str(e))
            tablet_proxy = None

        # Disable autonomous life (prevents behaviour takeover)
        try:
            life_proxy = ALProxy("ALAutonomousLife", ROBOT_IP, ROBOT_PORT)
            life_proxy.setState("disabled")
            print("[INIT] ALAutonomousLife disabled.")
        except Exception as e:
            print("[INIT] Could not disable ALAutonomousLife: " + str(e))

        # Pause basic awareness (intercepts motion commands silently)
        try:
            awareness_proxy = ALProxy("ALBasicAwareness", ROBOT_IP, ROBOT_PORT)
            awareness_proxy.pauseAwareness()
            print("[INIT] ALBasicAwareness paused.")
        except Exception as e:
            print("[INIT] Could not pause ALBasicAwareness: " + str(e))

        # Wake motors and stand
        motion_proxy.wakeUp()
        posture_proxy.goToPosture("Stand", 1.0)
        print("[INIT] Robot standing.")

        # Initialize odometry reference point
        motion_proxy.moveInit()
        print("[INIT] Odometry reference set (current position = origin).")

        # Set reduced collision distances (not disabled — just tighter for demo room)
        try:
            motion_proxy.setOrthogonalSecurityDistance(SECURITY_ORTHO)
            motion_proxy.setTangentialSecurityDistance(SECURITY_TAN)
            print("[INIT] Collision distances reduced: ortho={}, tan={}".format(
                SECURITY_ORTHO, SECURITY_TAN))
        except Exception as e:
            print("[INIT] Could not set security distances: " + str(e))

        print("[INIT] Hardware initialization complete.")
        print("[INIT] Using segmented ALNavigation.navigateTo() (no SLAM map needed).")
        _startup_greeting()
        return True

    except Exception as e:
        print("[ERROR] Hardware initialization failed: " + str(e))
        print("[INFO] Retrying in 5 seconds...")
        time.sleep(5)
        try:
            print("[INIT] Retrying NAOqi connection...")
            tts_proxy        = ALProxy("ALTextToSpeech", ROBOT_IP, ROBOT_PORT)
            motion_proxy     = ALProxy("ALMotion",       ROBOT_IP, ROBOT_PORT)
            navigation_proxy = ALProxy("ALNavigation",   ROBOT_IP, ROBOT_PORT)
            posture_proxy    = ALProxy("ALRobotPosture", ROBOT_IP, ROBOT_PORT)
            motion_proxy.wakeUp()
            posture_proxy.goToPosture("Stand", 1.0)
            motion_proxy.moveInit()
            print("[INIT] Retry succeeded.")
            return True
        except Exception as e2:
            print("[ERROR] Retry also failed: " + str(e2))
            return False


# =====================================================================
# Tablet Display Control
# =====================================================================
def show_navigating_screen(doctor_name, room_name):
    """Show 'Guiding you to Doctor's Room' on Pepper's tablet."""
    if not tablet_proxy:
        return
    try:
        doc_enc  = url_quote(doctor_name.encode("utf-8") if isinstance(doctor_name, bytes) is False else doctor_name)
        room_enc = url_quote(room_name.encode("utf-8") if isinstance(room_name, bytes) is False else room_name)
        url = "{}/static/navigating.html?doctor={}&room={}".format(
            SERVER_URL, doc_enc, room_enc)
        print("[TABLET] Showing navigation screen: " + url)
        tablet_proxy.loadUrl(url)
    except Exception as e:
        print("[TABLET] Could not show navigation screen: " + str(e))


def restore_home_screen():
    """Restore the default home page on the tablet."""
    if not tablet_proxy:
        return
    try:
        tablet_proxy.loadUrl(SERVER_URL)
        print("[TABLET] Restored home screen.")
    except Exception as e:
        print("[TABLET] Could not restore home screen: " + str(e))


# =====================================================================
# Coordinate Math
# =====================================================================
def world_to_robot(dx_world, dy_world, heading):
    """
    Transform a world-frame delta into robot-frame coordinates.
    Robot frame: x = forward, y = left.
    """
    cos_h = math.cos(-heading)
    sin_h = math.sin(-heading)
    dx_robot = dx_world * cos_h - dy_world * sin_h
    dy_robot = dx_world * sin_h + dy_world * cos_h
    return dx_robot, dy_robot


def get_remaining(target_x, target_y, target_theta):
    """
    Compute remaining distance and robot-frame deltas from current
    hardware odometry to the target.
    Returns: (dx_robot, dy_robot, remaining_theta, distance, current_pos)
    """
    pos = motion_proxy.getRobotPosition(True)  # [x, y, theta] in world frame
    cx, cy, ch = pos[0], pos[1], pos[2]

    dx_world = target_x - cx
    dy_world = target_y - cy
    dx_robot, dy_robot = world_to_robot(dx_world, dy_world, ch)

    distance = math.sqrt(dx_robot ** 2 + dy_robot ** 2)
    remaining_theta = target_theta - ch

    # Normalize theta to [-pi, pi]
    while remaining_theta > math.pi:
        remaining_theta -= 2 * math.pi
    while remaining_theta < -math.pi:
        remaining_theta += 2 * math.pi

    return dx_robot, dy_robot, remaining_theta, distance, (cx, cy, ch)


# =====================================================================
# Navigation Execution (runs in daemon thread)
# =====================================================================
def send_nav_status(msg_type, room_name, doctor_name):
    """Send navigation status back through WebSocket."""
    if ws_conn is None:
        return
    try:
        ws_conn.send(json.dumps({
            "type":        msg_type,
            "room_name":   room_name,
            "doctor_name": doctor_name
        }))
    except Exception as e:
        print("[WARN] Could not send nav status: " + str(e))


def _navigate_segment(dx, dy, use_nav=True):
    """
    Move one segment. Returns True if successful.
    Uses navigateTo() with obstacle avoidance, falls back to moveTo().
    Has a per-segment timeout to prevent hangs.
    """
    timed_out = [False]

    def on_timeout():
        timed_out[0] = True
        print("[NAV] Segment timed out after {}s — stopping.".format(SEGMENT_TIMEOUT))
        try:
            navigation_proxy.stopNavigation()
        except Exception:
            pass
        try:
            motion_proxy.stopMove()
        except Exception:
            pass

    timer = threading.Timer(SEGMENT_TIMEOUT, on_timeout)
    timer.daemon = True
    timer.start()

    success = False
    try:
        if use_nav and navigation_proxy:
            # navigateTo() has built-in obstacle avoidance
            print("[NAV]   navigateTo({:.2f}, {:.2f})".format(dx, dy))
            navigation_proxy.navigateTo(dx, dy)
            success = not timed_out[0]
        else:
            raise RuntimeError("Skipping navigateTo — using moveTo fallback")
    except Exception as e:
        if not timed_out[0]:
            print("[NAV]   navigateTo failed: {}. Trying moveTo...".format(str(e)))
            timer.cancel()
            # Reset timeout for moveTo attempt
            timed_out[0] = False
            timer = threading.Timer(SEGMENT_TIMEOUT, on_timeout)
            timer.daemon = True
            timer.start()
            try:
                motion_proxy.moveTo(dx, dy, 0)
                success = not timed_out[0]
            except Exception as e2:
                print("[NAV]   moveTo also failed: " + str(e2))
    finally:
        timer.cancel()

    return success


def execute_navigation(target_coords, doctor_name, room_name):
    """
    Navigate to target using segmented approach:
    1. Show "Guiding you" on tablet
    2. Loop: compute remaining distance, move up to 2.5m per segment
    3. Adjust final heading
    4. Announce arrival, restore tablet
    """
    global is_navigating

    try:
        tx = float(target_coords[0])
        ty = float(target_coords[1])
        ttheta = float(target_coords[2])

        # Show navigation screen on tablet
        show_navigating_screen(doctor_name, room_name)

        # Pause awareness during navigation
        if awareness_proxy:
            try:
                awareness_proxy.pauseAwareness()
            except Exception:
                pass

        # Announce
        if current_lang == "ar":
            announcement = u"\u062a\u0627\u0628\u0639\u0646\u064a \u0625\u0644\u0649 " + str(room_name)
        else:
            announcement = "Please follow me to " + str(doctor_name) + "'s room."
        print("[NAV] " + announcement)
        tts_say(announcement)

        # Ensure robot is standing and ready
        try:
            motion_proxy.moveInit()
        except Exception:
            pass

        # Log battery
        if battery_proxy:
            try:
                charge = battery_proxy.getBatteryCharge()
                print("[NAV] Battery: {}%".format(charge))
            except Exception:
                pass

        # ---------------------------------------------------------------
        # SEGMENTED NAVIGATION LOOP
        # ---------------------------------------------------------------
        segment_count = 0
        while segment_count < MAX_SEGMENTS:
            dx_r, dy_r, dtheta, dist, pos = get_remaining(tx, ty, ttheta)
            print("[NAV] Segment {}: dist={:.2f}m, pos=({:.2f}, {:.2f}, {:.2f}rad)".format(
                segment_count + 1, dist, pos[0], pos[1], pos[2]))

            # Close enough — stop moving
            if dist < ARRIVAL_THRESH:
                print("[NAV] Within arrival threshold ({:.2f}m < {:.2f}m).".format(
                    dist, ARRIVAL_THRESH))
                break

            # Clamp segment to MAX_SEGMENT meters
            if dist > MAX_SEGMENT:
                ratio = MAX_SEGMENT / dist
                seg_x = dx_r * ratio
                seg_y = dy_r * ratio
            else:
                seg_x = dx_r
                seg_y = dy_r

            success = _navigate_segment(seg_x, seg_y, use_nav=True)
            segment_count += 1

            if not success:
                print("[NAV] Segment {} failed. Attempting one retry...".format(segment_count))
                # Small pause and retry the same segment once
                time.sleep(1.0)
                dx_r, dy_r, dtheta, dist, pos = get_remaining(tx, ty, ttheta)
                if dist < ARRIVAL_THRESH:
                    break
                if dist > MAX_SEGMENT:
                    ratio = MAX_SEGMENT / dist
                    seg_x = dx_r * ratio
                    seg_y = dy_r * ratio
                else:
                    seg_x = dx_r
                    seg_y = dy_r
                success2 = _navigate_segment(seg_x, seg_y, use_nav=False)
                segment_count += 1
                if not success2:
                    print("[NAV] Retry also failed. Stopping navigation.")
                    raise RuntimeError("Navigation blocked after retry.")

            time.sleep(0.3)  # Brief pause between segments

        # ---------------------------------------------------------------
        # FINAL HEADING ADJUSTMENT
        # ---------------------------------------------------------------
        _, _, dtheta, _, _ = get_remaining(tx, ty, ttheta)
        if abs(dtheta) > 0.15:  # > ~8 degrees
            print("[NAV] Adjusting heading by {:.2f} rad".format(dtheta))
            try:
                motion_proxy.moveTo(0, 0, dtheta)
            except Exception:
                pass

        # ---------------------------------------------------------------
        # ARRIVAL
        # ---------------------------------------------------------------
        if current_lang == "ar":
            arrival_msg = u"\u0644\u0642\u062f \u0648\u0635\u0644\u0646\u0627. \u0647\u0630\u0627 \u0647\u0648 " + str(room_name) + "."
        else:
            arrival_msg = "We have arrived at " + str(room_name) + ". The doctor will see you shortly."
        tts_say(arrival_msg)
        print("[NAV] Arrived at " + room_name)
        send_nav_status("nav_complete", room_name, doctor_name)

        # Wait a moment then restore the home screen
        time.sleep(3)
        restore_home_screen()

    except Exception as e:
        print("[ERROR] Navigation failed: " + str(e))

        # Safety: stop all movement
        try:
            if navigation_proxy:
                navigation_proxy.stopNavigation()
            if motion_proxy:
                motion_proxy.stopMove()
        except Exception:
            pass

        # Inform patient
        if current_lang == "ar":
            tts_say(u"\u0639\u0630\u0631\u0627\u060c \u062a\u0645 \u0625\u0644\u063a\u0627\u0621 \u0627\u0644\u062a\u0648\u062c\u064a\u0647.", "ar")
        else:
            tts_say("I'm sorry, navigation was interrupted. Please ask staff for assistance.", "en")

        send_nav_status("nav_failed", room_name, doctor_name)

        # Restore home screen after failure too
        time.sleep(2)
        restore_home_screen()

    finally:
        # Resume awareness
        if awareness_proxy:
            try:
                awareness_proxy.resumeAwareness()
            except Exception:
                pass
        with nav_lock:
            is_navigating = False


# =====================================================================
# WebSocket Message Handler
# =====================================================================
def handle_navigate(data):
    """Validate navigate payload and dispatch daemon thread."""
    global is_navigating

    with nav_lock:
        if is_navigating:
            print("[NAV] Already navigating. Ignoring duplicate request.")
            return
        is_navigating = True

    target      = data.get("target")
    doctor_name = data.get("doctor_name", "the doctor")
    room_name   = data.get("room_name",   "the destination")

    if not target or not isinstance(target, list) or len(target) != 3:
        print("[ERROR] Invalid target coordinates: " + str(target))
        with nav_lock:
            is_navigating = False
        return

    nav_thread = threading.Thread(
        target=execute_navigation,
        args=(target, doctor_name, room_name)
    )
    nav_thread.daemon = True
    nav_thread.start()


# =====================================================================
# Main WebSocket Client Loop
# =====================================================================
def run():
    print("==============================================")
    print("   PEPPER NAVIGATION BRIDGE v2")
    print("   Strategy: Segmented navigateTo()")
    print("   Target WS: " + SERVER_WS)
    print("==============================================")

    ws = None
    hardware_initialized = False

    while True:
        try:
            ws = create_connection(SERVER_WS)
            global ws_conn, current_lang
            ws_conn = ws
            ws.send(json.dumps({"type": "hello", "role": "nav_bridge"}))
            print("[INFO] Connected to WebSocket bridge.")

            if not hardware_initialized:
                init_robot()
                hardware_initialized = True

            while True:
                msg = ws.recv()
                if not msg:
                    break

                try:
                    data     = json.loads(msg)
                    msg_type = data.get("type", "")

                    if msg_type == "navigate":
                        handle_navigate(data)

                    elif msg_type == "say":
                        text = data.get("text", "")
                        lang = data.get("lang", current_lang)
                        if tts_proxy and text:
                            try:
                                tts_say(text, lang)
                                print("[TTS] Said (" + lang + "): " + text)
                            except Exception as e:
                                print("[WARN] TTS failed: " + str(e))

                    elif msg_type == "look_up":
                        if motion_proxy:
                            try:
                                motion_proxy.setAngles("HeadPitch", -0.30, 0.15)
                                print("[HEAD] Looking up for face capture.")
                            except Exception as e:
                                print("[WARN] Head tilt failed: " + str(e))

                    elif msg_type == "look_reset":
                        if motion_proxy:
                            try:
                                motion_proxy.setAngles("HeadPitch", 0.0, 0.15)
                                print("[HEAD] Head reset to neutral.")
                            except Exception as e:
                                print("[WARN] Head reset failed: " + str(e))

                    elif msg_type == "start_recording":
                        lang = data.get("lang", "en")
                        current_lang = lang
                        try:
                            with open(LANG_FLAG_FILE, "w") as _lf:
                                _lf.write(lang)
                        except Exception:
                            pass
                        try:
                            with open(VOICE_FLAG_FILE, "w") as _f:
                                _f.write("1")
                            print("[VOICE] Flag file created (" + lang + ")")
                        except Exception as e:
                            print("[WARN] Could not create voice flag: " + str(e))

                    elif msg_type not in ["ping", "pong", "hello", "heartbeat",
                                          "stop_recording", "nav_complete", "nav_failed"]:
                        print("[INFO] Received message type: " + msg_type)

                except ValueError:
                    print("[WARN] Invalid JSON payload received.")
                except Exception as e:
                    print("[ERROR] Message handling error: " + str(e))

        except KeyboardInterrupt:
            print("\n[INFO] Navigation Bridge shutting down gracefully...")
            break

        except Exception as e:
            print("[WARN] Connection failed: " + str(e) + ". Retrying in 3s...")
            time.sleep(3.0)

        finally:
            ws_conn = None
            if ws:
                try:
                    ws.close()
                except Exception:
                    pass


if __name__ == "__main__":
    run()
