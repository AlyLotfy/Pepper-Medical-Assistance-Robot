# -*- coding: utf-8 -*-
from naoqi import ALProxy
import time
import os
import requests

# -------------------------------------------------------
# CONFIGURATION (DYNAMIC FROM MAIN.PY LAUNCHER)
# -------------------------------------------------------
# Grab IPs from environment variables, with local fallbacks
PEPPER_IP = os.environ.get("ROBOT_IP", "127.0.0.1")
PEPPER_PORT = int(os.environ.get("ROBOT_PORT", "9559"))

SERVER_IP = os.environ.get("SERVER_IP", "127.0.0.1")
SERVER_PORT = os.environ.get("SERVER_PORT", "8080")

# Dynamically construct the backend URL
SERVER_URL = "http://{}:{}/api/process_audio".format(SERVER_IP, SERVER_PORT)

LOCAL_FILE = "voice.wav"
PEPPER_FILE = "/tmp/voice.wav"
FLAG_FILE = "voice_start.flag"  # IPC Flag described in your architecture

PSCP = r"C:\Program Files\PuTTY\pscp.exe"

# -------------------------------------------------------
# INITIALIZE NAOQI PROXIES
# -------------------------------------------------------
try:
    tts = ALProxy("ALTextToSpeech", PEPPER_IP, PEPPER_PORT)
    rec = ALProxy("ALAudioRecorder", PEPPER_IP, PEPPER_PORT)
except Exception as e:
    print("[ERROR] Could not connect to Pepper at {}:{}. Is the robot on?".format(PEPPER_IP, PEPPER_PORT))
    print(e)
    exit(1)

print("")
print("==============================================")
print("   PEPPER VOICE CHAT – AUTOMATED FLAG MODE")
print("   Robot IP:   {}".format(PEPPER_IP))
print("   Server URL: {}".format(SERVER_URL))
print("   Polling for '{}' to start recording...".format(FLAG_FILE))
print("==============================================")
print("")

# -------------------------------------------------------
# RECORD AUDIO
# -------------------------------------------------------
def record_audio():
    tts.say("Please speak now.")
    print("[INFO] Recording...")

    rec.startMicrophonesRecording(PEPPER_FILE, "wav", 16000, (0,0,1,0))
    time.sleep(4)
    rec.stopMicrophonesRecording()

    print("[INFO] Recording done. Transferring audio...")

    cmd = '"{}" -pw nao nao@{}:{} {}'.format(
        PSCP, PEPPER_IP, PEPPER_FILE, LOCAL_FILE
    )
    os.system(cmd)

# -------------------------------------------------------
# SEND AUDIO TO BACKEND
# -------------------------------------------------------
def process_backend():
    if not os.path.exists(LOCAL_FILE):
        print("[ERROR] File was not transferred.")
        return "Audio transfer failed."

    with open(LOCAL_FILE, "rb") as f:
        files = {"file": ("voice.wav", f, "audio/wav")}
        try:
            r = requests.post(SERVER_URL, files=files, timeout=60)
            data = r.json()

            text = data.get("text", "").strip()
            reply = data.get("reply", "").strip()

            if text == "":
                print("[WARN] Empty transcription received.")
                return "I did not hear anything. Please repeat."

            if reply == "":
                return "I am having trouble processing your request."

            return reply

        except Exception as e:
            print("[ERROR] Backend failure:", e)
            return "The medical server is unreachable at the moment."

# -------------------------------------------------------
# MAIN LOOP – FILE-FLAG IPC MECHANISM
# -------------------------------------------------------
while True:
    # 1. Poll for the flag file created by the tablet UI / WebSocket bridge
    if os.path.exists(FLAG_FILE):
        print("\n[INFO] Trigger flag detected! Starting interaction...")
        
        # 2. Immediately remove the flag so it doesn't loop infinitely
        try:
            os.remove(FLAG_FILE)
        except Exception as e:
            print("[WARN] Could not remove flag file: {}".format(e))
            
        # 3. Execute the voice pipeline
        record_audio()

        print("[INFO] Processing speech...")
        reply = process_backend()

        print("[PEPPER REPLY]: {}".format(reply))

        # ALWAYS convert to UTF-8 to prevent NAOqi crash
        if isinstance(reply, unicode):
            reply = reply.encode("utf-8")

        tts.say(reply)
        print("[INFO] Interaction complete. Returning to polling state...")
        
    else:
        # Sleep briefly to prevent high CPU usage while waiting
        time.sleep(0.5)