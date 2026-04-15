# -*- coding: utf-8 -*-
# map_exploration.py - SLAM Map Builder for Prototype Room
# Layer: Robot Layer (Python 2.7, NAOqi environment)
#
# PURPOSE:
#   Guides Pepper to explore and record the prototype room layout as a
#   metrical .explo map file. This file is required by nav_bridge.py for
#   full SLAM-based navigation with obstacle avoidance.
#
#   If you skip this step, nav_bridge.py automatically falls back to
#   ALMotion.moveTo() (simple relative movement, no obstacle avoidance).
#
# HOW TO USE (run once before the demo):
#   1. Place Pepper at the starting position (the point that will be the map origin).
#   2. Run this script:
#         python map_exploration.py
#   3. Manually guide Pepper around the room using Choregraphe or tablet controls
#      so it can scan all areas with its LIDAR/sonar sensors.
#   4. Press ENTER when the room has been fully scanned.
#   5. The map is saved as prototype_room.explo in this folder.
#   6. Restart nav_bridge.py - it will detect and load the new map automatically.
#
# GRADUATION DEFENSE NOTE:
#   Pepper builds its map using SLAM (Simultaneous Localization and Mapping).
#   During exploration, the robot uses its base LIDAR and ultrasonic sonars
#   to construct a 2D probability grid where each pixel represents either:
#   free space, occupied space, or unknown territory. The resulting .explo
#   binary encodes this grid plus odometric calibration data.

import os
import sys
import time
import argparse
import json

try:
    from naoqi import ALProxy
except ImportError:
    print("[ERROR] NAOqi SDK not found. This script must run with pynaoqi in PYTHONPATH.")
    sys.exit(1)

# =====================================================================
# Configuration
# =====================================================================
ROBOT_IP   = os.environ.get("ROBOT_IP",   "127.0.0.1")
ROBOT_PORT = int(os.environ.get("ROBOT_PORT", "9559"))

# Save the map in the same folder as this script
NAV_DIR    = os.path.dirname(os.path.abspath(__file__))
MAP_PATH   = os.path.join(NAV_DIR, "prototype_room.explo")
META_PATH  = os.path.join(NAV_DIR, "map_metadata.json")

# =====================================================================
# Exploration Procedure
# =====================================================================
def explore_and_save():
    print("==============================================")
    print("   PEPPER SLAM MAP BUILDER")
    print("   Robot: " + ROBOT_IP + ":" + str(ROBOT_PORT))
    print("   Output: " + MAP_PATH)
    print("==============================================\n")

    try:
        navigation = ALProxy("ALNavigation",   ROBOT_IP, ROBOT_PORT)
        motion     = ALProxy("ALMotion",       ROBOT_IP, ROBOT_PORT)
        tts        = ALProxy("ALTextToSpeech", ROBOT_IP, ROBOT_PORT)
    except Exception as e:
        print("[ERROR] Cannot connect to NAOqi proxies: " + str(e))
        sys.exit(1)

    try:
        # Wake Pepper so motors are active
        motion.wakeUp()
        print("[INFO] Robot awake.")

        tts.say("Starting room mapping. Please clear the area of obstacles.")
        time.sleep(3)

        # Begin scanning the environment
        print("[INFO] Starting SLAM exploration...")
        tts.say("Begin exploration.")
        navigation.startExploration()

        print("\n[ACTION REQUIRED]")
        print("  Manually guide Pepper around the prototype room.")
        print("  Move slowly and cover all areas, including corners.")
        print("  The robot's sensors will build the map as it moves.")
        print("\n  Press ENTER when you have fully explored the room.")
        print("  (Or press Ctrl+C to cancel without saving.)\n")

        raw_input("  >> Press ENTER to stop exploration and save map: ")

        # Stop the exploration scan
        print("[INFO] Stopping exploration...")
        navigation.stopExploration()
        time.sleep(1)

        # Save the generated map to disk
        print("[INFO] Saving map to: " + MAP_PATH)
        navigation.saveExploration(MAP_PATH)

        # Verify the file was created
        if os.path.exists(MAP_PATH):
            file_size = os.path.getsize(MAP_PATH)
            print("[OK] Map saved successfully. File size: " + str(file_size) + " bytes.")
            tts.say("Map saved successfully. Navigation is now ready.")

            print("\n[NEXT STEPS]")
            print("  1. Start nav_bridge.py - it will load this map automatically.")
            print("  2. Make sure Pepper always starts at the SAME position and orientation.")
            print("     (The origin [0, 0, 0] in navigation_targets.json = this start point.)")
            print("  3. Update navigation_targets.json coordinates if needed.\n")
        else:
            print("[ERROR] Map file was not created. Exploration may have failed.")
            tts.say("Map saving failed. Please try again.")

    except KeyboardInterrupt:
        print("\n[INFO] Exploration cancelled. No map was saved.")
        try:
            navigation.stopExploration()
        except Exception:
            pass

    except Exception as e:
        print("[ERROR] Exploration failed: " + str(e))
        try:
            navigation.stopExploration()
        except Exception:
            pass

def autonomous_explore(radius=3.0, duration=120):
    """
    Autonomous exploration mode: Pepper navigates on its own within a radius.
    Uses ALNavigation.explore() which performs autonomous SLAM exploration.

    Args:
        radius: Maximum exploration radius in meters (default 3.0m)
        duration: Maximum exploration time in seconds (default 120s)
    """
    print("==============================================")
    print("   PEPPER AUTONOMOUS EXPLORATION")
    print("   Robot: " + ROBOT_IP + ":" + str(ROBOT_PORT))
    print("   Radius: " + str(radius) + "m, Duration: " + str(duration) + "s")
    print("   Output: " + MAP_PATH)
    print("==============================================\n")

    try:
        navigation = ALProxy("ALNavigation",    ROBOT_IP, ROBOT_PORT)
        motion     = ALProxy("ALMotion",        ROBOT_IP, ROBOT_PORT)
        posture    = ALProxy("ALRobotPosture",  ROBOT_IP, ROBOT_PORT)
        tts        = ALProxy("ALTextToSpeech",  ROBOT_IP, ROBOT_PORT)
    except Exception as e:
        print("[ERROR] Cannot connect to NAOqi proxies: " + str(e))
        sys.exit(1)

    try:
        motion.wakeUp()
        posture.goToPosture("StandInit", 0.5)
        time.sleep(1)
        tts.say("Starting autonomous exploration for " + str(duration) + " seconds.")
        print("[INFO] Starting autonomous SLAM exploration (radius=" + str(radius) + "m)...")

        # explore() autonomously navigates and builds the map
        error_code = navigation.explore(radius)

        if error_code == 0:
            print("[INFO] Autonomous exploration completed successfully.")
        else:
            print("[INFO] Exploration ended with code: " + str(error_code))

        # Save the map
        print("[INFO] Saving map to: " + MAP_PATH)
        navigation.saveExploration(MAP_PATH)

        # Save metadata
        meta = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "autonomous",
            "radius": radius,
            "duration": duration,
            "robot_ip": ROBOT_IP,
            "map_file": "prototype_room.explo",
        }

        # Try to get metrical map info
        try:
            map_data = navigation.getMetricalMap()
            if map_data:
                meta["resolution"] = map_data[0]
                meta["meters_per_pixel"] = map_data[1]
                meta["origin"] = list(map_data[2]) if map_data[2] else [0, 0]
        except Exception:
            pass

        # Get robot position
        try:
            pos = navigation.getRobotPositionInMap()
            if pos:
                meta["final_position"] = {
                    "x": pos[0][0], "y": pos[0][1], "theta": pos[0][2]
                }
        except Exception:
            pass

        with open(META_PATH, "w") as f:
            json.dump(meta, f, indent=2)
        print("[INFO] Metadata saved to: " + META_PATH)

        if os.path.exists(MAP_PATH):
            print("[OK] Map saved. Size: " + str(os.path.getsize(MAP_PATH)) + " bytes.")
            tts.say("Exploration complete. Map saved.")
        else:
            print("[WARN] Map file not found after save.")
            tts.say("Map saving may have failed.")

        posture.goToPosture("StandInit", 0.5)

    except KeyboardInterrupt:
        print("\n[INFO] Exploration interrupted.")
        try:
            navigation.stopExploration()
        except Exception:
            pass
    except Exception as e:
        print("[ERROR] " + str(e))
        try:
            navigation.stopExploration()
        except Exception:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pepper SLAM Exploration & Mapping")
    parser.add_argument("--mode", choices=["manual", "auto"], default="manual",
                        help="Exploration mode: 'manual' (guided) or 'auto' (autonomous)")
    parser.add_argument("--radius", type=float, default=3.0,
                        help="Autonomous mode: max exploration radius in meters")
    parser.add_argument("--duration", type=int, default=120,
                        help="Autonomous mode: max exploration time in seconds")
    args = parser.parse_args()

    if args.mode == "auto":
        autonomous_explore(radius=args.radius, duration=args.duration)
    else:
        explore_and_save()
