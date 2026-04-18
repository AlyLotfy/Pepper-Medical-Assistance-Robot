# -*- coding: utf-8 -*-
"""
PEPPER SYSTEM SELF-TEST SCRIPT (FIXED)
"""

import time
import os                   # <-- FIXED: needed for file existence check
import paramiko
from naoqi import ALProxy

# =============================
# CONFIGURATION
# =============================
ROBOT_IP = "1.1.1.10"
ROBOT_PORT = 9559
ROBOT_USER = "nao"
ROBOT_PWD  = "nao"

REMOTE_AUDIO_PATH = "/tmp/test_record.wav"
LOCAL_AUDIO_FILE  = "test_record_pc.wav"

EVENT_NAME = "Pepper/StartListening"


# =============================
# UTILITY FUNCTIONS
# =============================

def header(title):
    print("\n" + "="*60)
    print(" TEST:", title)
    print("="*60)


def test_tts():
    header("ALTextToSpeech")
    try:
        tts = ALProxy("ALTextToSpeech", ROBOT_IP, ROBOT_PORT)
        tts.say("Testing speech. I am Pepper.")
        print("✔ TTS working.")
    except Exception as e:
        print("✘ TTS FAILED:", e)


def test_memory_event():
    header("ALMemory Event")
    try:
        mem = ALProxy("ALMemory", ROBOT_IP, ROBOT_PORT)
        mem.raiseEvent(EVENT_NAME, 1)
        print("✔ Memory event raised:", EVENT_NAME)
        print("Check your bridge logs to confirm it was received.")
    except Exception as e:
        print("✘ Memory event FAILED:", e)


def test_record_audio():
    header("Microphone Recording (ALAudioRecorder)")
    try:
        audio = ALProxy("ALAudioRecorder", ROBOT_IP, ROBOT_PORT)

        channels = [0,0,1,0]  # front mic

        try: audio.stopMicrophonesRecording()
        except: pass

        audio.startMicrophonesRecording(REMOTE_AUDIO_PATH, "wav", 16000, channels)
        print("Recording for 3 seconds...")
        time.sleep(3)
        audio.stopMicrophonesRecording()
        print("✔ Audio recorded:", REMOTE_AUDIO_PATH)
    except Exception as e:
        print("✘ Recording FAILED:", e)


def test_sftp_transfer():
    header("SFTP Transfer Pepper → PC")
    try:
        transport = paramiko.Transport((ROBOT_IP, 22))
        transport.connect(username=ROBOT_USER, password=ROBOT_PWD)
        sftp = paramiko.SFTPClient.from_transport(transport)

        sftp.get(REMOTE_AUDIO_PATH, LOCAL_AUDIO_FILE)
        sftp.close()
        transport.close()

        if not os.path.exists(LOCAL_AUDIO_FILE):
            raise Exception("File not found after transfer")

        print("✔ File transferred successfully:", LOCAL_AUDIO_FILE)
    except Exception as e:
        print("✘ SFTP FAILED:", e)


def test_end_to_end():
    header("END-TO-END SYSTEM TEST")
    try:
        mem = ALProxy("ALMemory", ROBOT_IP, ROBOT_PORT)
        mem.raiseEvent(EVENT_NAME, 1)
        print("✔ Event raised. If bridge is running, Pepper should:")
        print("- Say 'Listening'")
        print("- Record audio")
        print("- Send to backend")
        print("- Speak Claude reply")
    except Exception as e:
        print("✘ End-to-end FAILED:", e)


# =============================
# RUN ALL TESTS
# =============================
if __name__ == "__main__":
    test_tts()
    test_memory_event()
    test_record_audio()
    test_sftp_transfer()
    test_end_to_end()

    print("\nALL TESTS COMPLETED.")
