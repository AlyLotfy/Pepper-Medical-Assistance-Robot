# -*- coding: utf-8 -*-
# Python 2.7 - Main Hardware WebSocket Bridge
import json
import time
import os
import traceback
from websocket import create_connection
from naoqi import ALProxy

# --- DYNAMIC CONFIGURATION ---
PEPPER_IP = os.environ.get("ROBOT_IP", "127.0.0.1")
PEPPER_PORT = int(os.environ.get("ROBOT_PORT", "9559"))

SERVER_IP = os.environ.get("SERVER_IP", "127.0.0.1")
# Note: Using WS_PORT specifically for the hardware communication channel
WS_PORT = os.environ.get("WS_PORT", "8765") 

SERVER_WS = "ws://{}:{}".format(SERVER_IP, WS_PORT)

def execute_hardware_command(data, tts, motion):
    command = data.get("command", "")
    
    if command == "say":
        text = data.get("text", "")
        if text:
            # Ensure UTF-8 encoding for Python 2.7 NAOqi compatibility
            if isinstance(text, unicode):
                text = text.encode("utf-8")
            print("[BRIDGE] Pepper says: {}".format(text))
            tts.say(text)
            
    elif command == "animate":
        anim = data.get("animation", "animations/Stand/Gestures/Hey_1")
        try:
            # Requires ALAnimationPlayer proxy if used, placeholder for logic
            print("[BRIDGE] Executing animation: {}".format(anim))
        except Exception as e:
            print("[ERROR] Animation failed: {}".format(e))

def run_bridge():
    print("[INFO] Main Hardware Bridge Starting. Target WS: {}".format(SERVER_WS))
    
    # Initialize Core Proxies
    try:
        tts = ALProxy("ALTextToSpeech", PEPPER_IP, PEPPER_PORT)
        motion = ALProxy("ALMotion", PEPPER_IP, PEPPER_PORT)
    except Exception as e:
        print("[ERROR] Could not bind NAOqi proxies. Is Pepper online? {}".format(e))
        return

    while True:
        try:
            ws = create_connection(SERVER_WS)
            ws.send(json.dumps({"type": "hello", "role": "hardware_bridge"}))
            print("[INFO] Hardware Bridge connected to Backend.")
            
            while True:
                msg = ws.recv()
                if not msg:
                    break
                
                try:
                    data = json.loads(msg)
                    execute_hardware_command(data, tts, motion)
                except Exception as e:
                    print("[WARN] Invalid JSON or command execution failed: {}".format(e))
                    
        except KeyboardInterrupt:
            print("\n[INFO] Shutting down Hardware Bridge...")
            break
        except Exception as e:
            print("[WARN] WebSocket connection failed: {}. Retrying in 3s...".format(e))
            time.sleep(3.0)
        finally:
            try:
                ws.close()
            except Exception:
                pass

if __name__ == "__main__":
    run_bridge()