# -*- coding: utf-8 -*-
# nav_bridge.py - Navigation Bridge for Pepper Robot
# Layer: Robot Layer (Python 2.7, NAOqi environment)
#
# HOW IT WORKS:
#   1. Connects to the WebSocket bridge (ws_bridge.py) running on the backend PC.
#   2. Listens for {"type": "navigate", "target": [x, y, theta], ...} messages.
#   3. Runs navigation in a daemon thread so the WebSocket heartbeat is never blocked.
#   4. If a SLAM map (prototype_room.explo) is present -> uses ALNavigation.navigateToInMap
#      which includes obstacle avoidance.
#   5. If no map is present -> falls back to ALMotion.moveTo (relative movement, no map needed).
#
# GRADUATION DEFENSE NOTE:
#   navigateToInMap() is a BLOCKING call. Running it on the main thread would freeze the
#   WebSocket loop, causing the backend router to drop the connection due to missed heartbeats.
#   We isolate it inside a daemon threading.Thread to avoid this critical failure.
#
# USAGE:
#   Run this script on the Pepper robot (or on the PC with pynaoqi SDK in PYTHONPATH):
#       python nav_bridge.py
#
# ENVIRONMENT VARIABLES (set by main.py):
#   ROBOT_IP    - Pepper robot IP address (default: 127.0.0.1)
#   ROBOT_PORT  - NAOqi port            (default: 9559)
#   SERVER_IP   - Backend PC IP address (default: 192.168.1.50)
#   WS_PORT     - WebSocket bridge port  (default: 8765)

import json
import threading
import time
import os
import sys

from websocket import create_connection

# NAOqi import with graceful fallback for development/testing without hardware
try:
    from naoqi import ALProxy
    NAOQI_AVAILABLE = True
except ImportError:
    NAOQI_AVAILABLE = False
    print("[WARN] NAOqi SDK not found. Running in simulation mode (no robot movement).")

# =====================================================================
# Configuration - read from environment variables (injected by main.py)
# =====================================================================
ROBOT_IP   = os.environ.get("ROBOT_IP",  "127.0.0.1")
ROBOT_PORT = int(os.environ.get("ROBOT_PORT", "9559"))
SERVER_IP  = os.environ.get("SERVER_IP", "192.168.1.50")
WS_PORT    = os.environ.get("WS_PORT",   "8765")
SERVER_WS  = "ws://" + SERVER_IP + ":" + WS_PORT

# Path to the voice flag file (MainVoice.py polls this to start recording)
VOICE_DIR      = os.environ.get("VOICE_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pepper_voice"))
VOICE_FLAG_FILE = os.path.join(VOICE_DIR, "voice_start.flag")

# Language flag file: MainVoice.py reads this to know which language to use for TTS
LANG_FLAG_FILE = os.path.join(VOICE_DIR, "lang.flag")

# Path to the pre-recorded SLAM exploration map.
# Generate this file once using map_exploration.py, then place it here.
NAV_DIR  = os.path.dirname(os.path.abspath(__file__))
MAP_PATH = os.path.join(NAV_DIR, "prototype_room.explo")

# =====================================================================
# Global NAOqi Proxies and State
# =====================================================================
navigation_proxy = None
tts_proxy        = None
motion_proxy     = None
posture_proxy    = None
awareness_proxy  = None
battery_proxy    = None
slam_map_loaded  = False
is_navigating    = False          # Guard: prevent overlapping navigation threads
ws_conn          = None           # Active WebSocket connection (set in run())
current_lang     = "en"           # Current UI language (en or ar)

# Accumulated pose from moveTo() calls (x_sum, y_sum, theta_sum)
# Used to convert absolute targets into relative deltas for moveTo().
current_pose     = [0.0, 0.0, 0.0]


def tts_say(text, lang=None):
    """Speak text in the correct language. Switches TTS engine language if needed."""
    if not tts_proxy:
        return
    if lang is None:
        lang = current_lang
    try:
        if lang == "ar":
            tts_proxy.setLanguage("Arabic")
        else:
            tts_proxy.setLanguage("English")
        tts_proxy.say(text.encode("utf-8"))
    except Exception as e:
        print("[WARN] TTS failed: " + str(e))

# =====================================================================
# Startup Greeting – Wave and Self-Introduction
# =====================================================================
def _startup_greeting():
    """Make Pepper wave its right hand and introduce itself after boot."""
    if not motion_proxy or not tts_proxy:
        return
    try:
        print("[GREET] Pepper is waving and introducing itself...")
        # Raise right arm for a wave
        names  = ["RShoulderPitch", "RShoulderRoll", "RElbowRoll", "RWristYaw"]
        # Arm up, slightly outward, elbow bent, wrist neutral
        angles = [-0.2,             -0.3,            1.0,          0.0]
        speed  = 0.15
        motion_proxy.setAngles(names, angles, speed)
        time.sleep(0.6)

        # Small wave motion (rotate wrist back and forth)
        for _ in range(3):
            motion_proxy.setAngles("RWristYaw", 0.5, 0.4)
            time.sleep(0.25)
            motion_proxy.setAngles("RWristYaw", -0.5, 0.4)
            time.sleep(0.25)

        # Speak introduction while arm is still up
        tts_proxy.setLanguage("English")
        tts_proxy.say("Hello! I am Pepper, your medical assistant at Andalusia Hospital. "
                      "You can talk to me, or use the touchscreen to get started. "
                      "I am here to help!".encode("utf-8"))

        # Return arm to rest position
        motion_proxy.setAngles(names, [1.5, 0.1, 0.5, 0.0], 0.15)
        time.sleep(0.5)
        print("[GREET] Startup greeting complete.")
    except Exception as e:
        print("[GREET] Greeting failed (non-critical): " + str(e))


# =====================================================================
# Robot Initialization and SLAM Boot Sequence
# =====================================================================
def init_robot():
    """
    GRADUATION DEFENSE NOTE:
    Initializes NAOqi hardware proxies and loads the SLAM exploration map
    if one has been generated. The sequence follows the mandatory ALNavigation API:
      1. loadExploration(path)      - Load .explo binary into memory
      2. relocalizeInMap([0,0,0])   - Assume robot is at map origin on boot
      3. startLocalization()        - Start LIDAR/sonar alignment background loop
    """
    global navigation_proxy, tts_proxy, motion_proxy, posture_proxy, awareness_proxy, battery_proxy, slam_map_loaded

    if not NAOQI_AVAILABLE:
        print("[WARN] Hardware initialization skipped (NAOqi not available).")
        return False

    try:
        print("[INIT] Connecting to NAOqi on " + ROBOT_IP + ":" + str(ROBOT_PORT))
        tts_proxy        = ALProxy("ALTextToSpeech", ROBOT_IP, ROBOT_PORT)
        motion_proxy     = ALProxy("ALMotion",       ROBOT_IP, ROBOT_PORT)
        navigation_proxy = ALProxy("ALNavigation",   ROBOT_IP, ROBOT_PORT)
        posture_proxy    = ALProxy("ALRobotPosture", ROBOT_IP, ROBOT_PORT)
        try:
            battery_proxy = ALProxy("ALBattery", ROBOT_IP, ROBOT_PORT)
            charge = battery_proxy.getBatteryCharge()
            print("[INIT] Battery level: " + str(charge) + "%")
            if charge < 30:
                print("[WARN] Battery below 30% — movement distance may be inaccurate.")
        except Exception as e:
            print("[INIT] Could not read battery level: " + str(e))

        # Step 1: Disable autonomous life (prevents behaviour takeover)
        try:
            life_proxy = ALProxy("ALAutonomousLife", ROBOT_IP, ROBOT_PORT)
            life_proxy.setState("disabled")
            print("[INIT] ALAutonomousLife disabled.")
        except Exception as e:
            print("[INIT] Could not disable ALAutonomousLife: " + str(e))

        # Step 2: Pause basic awareness (mirrors peppergui.py set_awareness(False))
        # ALBasicAwareness intercepts motion commands silently when active
        try:
            awareness_proxy = ALProxy("ALBasicAwareness", ROBOT_IP, ROBOT_PORT)
            awareness_proxy.pauseAwareness()
            print("[INIT] ALBasicAwareness paused.")
        except Exception as e:
            print("[INIT] Could not pause ALBasicAwareness: " + str(e))

        # Step 3: Wake motors and stand (mirrors peppergui.py stand())
        motion_proxy.wakeUp()
        posture_proxy.goToPosture("Stand", 1.0)
        print("[INIT] Robot standing.")

        motion_proxy.moveInit()

        # Try to load the pre-recorded SLAM map
        if os.path.exists(MAP_PATH):
            print("[INIT] SLAM map found. Loading: " + MAP_PATH)
            navigation_proxy.loadExploration(MAP_PATH)

            # Assert robot starts at map origin [0, 0, 0]
            navigation_proxy.relocalizeInMap([0.0, 0.0, 0.0])

            # Engage the background localization loop (LIDAR/sonar vs map)
            navigation_proxy.startLocalization()

            slam_map_loaded = True
            print("[INIT] SLAM localization active. Using navigateToInMap().")
        else:
            print("[INIT] No SLAM map at: " + MAP_PATH)
            print("[INIT] Falling back to ALMotion.moveTo() (relative movement).")
            print("[INIT] Run map_exploration.py to build a map for full SLAM support.")
            slam_map_loaded = False

        print("[INIT] Hardware initialization complete.")
        # Greet users with a wave and self-introduction
        _startup_greeting()
        return True

    except Exception as e:
        print("[ERROR] Hardware initialization failed: " + str(e))
        print("[INFO] Will retry hardware init in 5 seconds...")
        time.sleep(5)
        # Retry once — the most common cause is a session collision with
        # show_tablet.py that has now exited and freed the broker.
        try:
            print("[INIT] Retrying NAOqi connection...")
            tts_proxy        = ALProxy("ALTextToSpeech", ROBOT_IP, ROBOT_PORT)
            motion_proxy     = ALProxy("ALMotion",       ROBOT_IP, ROBOT_PORT)
            navigation_proxy = ALProxy("ALNavigation",   ROBOT_IP, ROBOT_PORT)
            posture_proxy    = ALProxy("ALRobotPosture", ROBOT_IP, ROBOT_PORT)
            motion_proxy.wakeUp()
            posture_proxy.goToPosture("Stand", 1.0)
            motion_proxy.moveInit()
            print("[INIT] Retry succeeded. Hardware ready.")
            return True
        except Exception as e2:
            print("[ERROR] Retry also failed: " + str(e2))
            return False

# =====================================================================
# Navigation Execution - runs inside a daemon thread
# =====================================================================
def send_nav_status(msg_type, room_name, doctor_name):
    """Send a navigation status message back through the WebSocket so guide.html can update."""
    global ws_conn
    if ws_conn is None:
        return
    try:
        payload = json.dumps({
            "type":        msg_type,
            "room_name":   room_name,
            "doctor_name": doctor_name
        })
        ws_conn.send(payload)
    except Exception as e:
        print("[WARN] Could not send nav status: " + str(e))


def execute_navigation(target_coords, doctor_name, room_name):
    """
    GRADUATION DEFENSE NOTE:
    This function is dispatched to a daemon threading.Thread.
    navigateToInMap() is a blocking call that halts execution for the entire
    navigation duration (potentially 20-60+ seconds). Running it here keeps
    the main thread free to process WebSocket PING/PONG heartbeats, preventing
    the backend router from declaring the connection dead and severing it.

    Error codes from navigateToInMap():
      0 = OK:             Robot reached exact target coordinates.
      1 = KO:             Path blocked or target outside mapped area.
      2 = Constraint KO:  Target reached but spatial constraints unfulfilled.
    """
    global is_navigating

    try:
        x     = float(target_coords[0])
        y     = float(target_coords[1])
        theta = float(target_coords[2])

        # Announce the navigation to the patient
        announcement = "Please follow me to " + str(doctor_name) + " in " + str(room_name) + "."
        print("[NAV] " + announcement)
        if tts_proxy:
            tts_proxy.say(announcement.encode("utf-8"))

        # ---------------------------------------------------------------
        # PRIMARY PATH: SLAM-based navigation (requires prototype_room.explo)
        # ---------------------------------------------------------------
        if navigation_proxy and slam_map_loaded:
            print("[NAV] Using SLAM: navigateToInMap([" + str(x) + ", " + str(y) + ", " + str(theta) + "])")
            result_code = navigation_proxy.navigateToInMap([x, y, theta])

            if result_code == 0:
                success_msg = "We have arrived at " + str(room_name) + ". The doctor will see you shortly."
                if tts_proxy:
                    tts_proxy.say(success_msg.encode("utf-8"))
                print("[NAV] Destination reached. Code: 0 (OK)")
                send_nav_status("nav_complete", room_name, doctor_name)

            else:
                # Code 1 (KO) or Code 2 (Constraint KO) - both indicate failure
                raise RuntimeError("SLAM engine aborted. Error code: " + str(result_code))

        # ---------------------------------------------------------------
        # FALLBACK PATH: Direct relative movement (no map required)
        # ---------------------------------------------------------------
        elif motion_proxy:
            # navigation_targets.json stores ABSOLUTE coordinates.
            # moveTo() is RELATIVE to the robot's current pose.
            # Compute the delta from our tracked cumulative pose.
            global current_pose
            dx     = x     - current_pose[0]
            dy     = y     - current_pose[1]
            dtheta = theta - current_pose[2]

            print("[NAV] Target absolute: ({}, {}, {})".format(x, y, theta))
            print("[NAV] Current  pose:   ({}, {}, {})".format(*current_pose))
            print("[NAV] Relative moveTo:  ({}, {}, {})".format(dx, dy, dtheta))

            # Log battery level so we can spot power-related short movements
            if battery_proxy:
                try:
                    charge = battery_proxy.getBatteryCharge()
                    print("[NAV] Battery: " + str(charge) + "%")
                    if charge < 30:
                        print("[WARN] Low battery — movement may be cut short.")
                except Exception:
                    pass

            # Pause awareness before moving
            if awareness_proxy:
                try:
                    awareness_proxy.pauseAwareness()
                except Exception:
                    pass

            # Disable external collision protection so sonar false-positives
            # (e.g. furniture in the demo room) do not cut the movement short.
            # Re-enabled immediately after moveTo returns.
            try:
                motion_proxy.setExternalCollisionProtectionEnabled("Move", False)
            except Exception:
                pass

            motion_proxy.moveInit()
            # RELATIVE delta: move from current tracked pose to target pose.
            # Blocking call — safe because this runs inside a daemon thread.
            motion_proxy.moveTo(dx, dy, dtheta)

            # Update tracked pose so next delta is correct
            current_pose = [x, y, theta]

            # Re-enable collision protection after arriving
            try:
                motion_proxy.setExternalCollisionProtectionEnabled("Move", True)
            except Exception:
                pass

            # Resume awareness after arriving (mirrors peppergui set_awareness(True))
            if awareness_proxy:
                try:
                    awareness_proxy.resumeAwareness()
                except Exception:
                    pass

            if current_lang == "ar":
                arrival_msg = u"\u0644\u0642\u062f \u0648\u0635\u0644\u0646\u0627. \u0647\u0630\u0627 \u0647\u0648 " + str(room_name) + "."
            else:
                arrival_msg = "We have arrived. This is " + str(room_name) + "."
            tts_say(arrival_msg)
            print("[NAV] moveTo complete.")
            send_nav_status("nav_complete", room_name, doctor_name)

        # ---------------------------------------------------------------
        # SIMULATION: No hardware available
        # ---------------------------------------------------------------
        else:
            print("[SIM] Simulating navigation to: " + str(target_coords))
            time.sleep(3)
            print("[SIM] Navigation simulation complete.")

    except Exception as e:
        print("[ERROR] Navigation failed: " + str(e))

        # SAFETY MITIGATION: Immediately stop all motor commands
        try:
            if navigation_proxy:
                navigation_proxy.stopNavigation()
            if motion_proxy:
                motion_proxy.stopMove()
        except Exception:
            pass

        # Verbally inform the patient of the failure
        try:
            if current_lang == "ar":
                tts_say(u"\u062a\u0645 \u0625\u0644\u063a\u0627\u0621 \u0627\u0644\u062a\u0648\u062c\u064a\u0647.", "ar")
            else:
                tts_say("Navigation cancelled.", "en")
        except Exception:
            pass
        send_nav_status("nav_failed", room_name, doctor_name)

    finally:
        # Always release the navigation lock so future requests are accepted
        is_navigating = False

# =====================================================================
# WebSocket Message Handler
# =====================================================================
def handle_navigate(data):
    """
    Validates the incoming navigate payload and dispatches a daemon thread.
    """
    global is_navigating

    if is_navigating:
        print("[NAV] Already navigating. Ignoring duplicate request.")
        return

    target      = data.get("target")
    doctor_name = data.get("doctor_name", "the doctor")
    room_name   = data.get("room_name",   "the destination")

    # Validate the spatial coordinate array
    if not target or not isinstance(target, list) or len(target) != 3:
        print("[ERROR] Invalid or missing target coordinates: " + str(target))
        return

    is_navigating = True

    nav_thread = threading.Thread(
        target=execute_navigation,
        args=(target, doctor_name, room_name)
    )
    nav_thread.daemon = True   # Daemon thread exits when main thread exits
    nav_thread.start()

# =====================================================================
# Main WebSocket Client Loop
# =====================================================================
def run():
    print("==============================================")
    print("   PEPPER NAVIGATION BRIDGE")
    print("   Target WS: " + SERVER_WS)
    print("==============================================")

    ws = None
    hardware_initialized = False

    while True:
        try:
            ws = create_connection(SERVER_WS)
            global ws_conn, current_lang
            ws_conn = ws
            # Identify this client to the bridge router
            ws.send(json.dumps({"type": "hello", "role": "nav_bridge"}))
            print("[INFO] Connected to WebSocket bridge.")

            # Initialize hardware AFTER connecting so messages sent during
            # startup are buffered in TCP and processed once the inner loop
            # starts — instead of being lost while nav_bridge wasn't connected.
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
                        # TTS command from emergency.html or other pages
                        text = data.get("text", "")
                        lang = data.get("lang", current_lang)
                        if tts_proxy and text:
                            try:
                                tts_say(text, lang)
                                print("[TTS] Said (" + lang + "): " + text)
                            except Exception as e:
                                print("[WARN] TTS failed: " + str(e))

                    elif msg_type == "look_up":
                        # Tilt head up so the top camera faces the user standing in front
                        if motion_proxy:
                            try:
                                # HeadPitch: negative = look up, positive = look down
                                motion_proxy.setAngles("HeadPitch", -0.30, 0.15)
                                print("[HEAD] Looking up for face capture.")
                            except Exception as e:
                                print("[WARN] Head tilt failed: " + str(e))

                    elif msg_type == "look_reset":
                        # Return head to neutral position
                        if motion_proxy:
                            try:
                                motion_proxy.setAngles("HeadPitch", 0.0, 0.15)
                                print("[HEAD] Head reset to neutral.")
                            except Exception as e:
                                print("[WARN] Head reset failed: " + str(e))

                    elif msg_type == "start_recording":
                        # Update language from UI
                        lang = data.get("lang", "en")
                        current_lang = lang
                        # Write language flag for MainVoice.py
                        try:
                            with open(LANG_FLAG_FILE, "w") as _lf:
                                _lf.write(lang)
                        except Exception:
                            pass
                        # Signal MainVoice.py to start recording via flag file
                        try:
                            with open(VOICE_FLAG_FILE, "w") as _f:
                                _f.write("1")
                            print("[VOICE] Flag file created (" + lang + "): " + VOICE_FLAG_FILE)
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
            # DEFENSE NOTE: stopLocalization frees significant CPU overhead
            # consumed by the continuous LIDAR/sonar comparison loop.
            if navigation_proxy and slam_map_loaded:
                try:
                    navigation_proxy.stopLocalization()
                    print("[INFO] SLAM localization stopped.")
                except Exception:
                    pass
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
