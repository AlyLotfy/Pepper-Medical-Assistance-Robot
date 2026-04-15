# -*- coding: utf-8 -*-
import time
import os
from naoqi import ALProxy

class PepperVoiceWrapper:
    def __init__(self):
        # Dynamically pull IPs from environment
        self.ip = os.environ.get("ROBOT_IP", "127.0.0.1")
        self.port = int(os.environ.get("ROBOT_PORT", "9559"))
        self.tts = None
        self.rec = None
        self._initialize_proxies()

    def _initialize_proxies(self):
        try:
            self.tts = ALProxy("ALTextToSpeech", self.ip, self.port)
            self.rec = ALProxy("ALAudioRecorder", self.ip, self.port)
            print("[INFO] PepperVoiceWrapper initialized successfully on {}:{}".format(self.ip, self.port))
        except Exception as e:
            print("[ERROR] Failed to bind NAOqi voice proxies. Is Pepper online?")
            print("Details: {}".format(e))

    def say(self, text):
        if self.tts:
            # ALWAYS convert to UTF-8 to prevent NAOqi crash
            if isinstance(text, unicode):
                text = text.encode("utf-8")
            self.tts.say(text)
        else:
            print("[WARN] TTS Proxy not available. Cannot say: {}".format(text))

    def record(self, filepath, duration=4):
        if self.rec:
            print("[INFO] Microphones listening for {} seconds...".format(duration))
            try:
                self.rec.startMicrophonesRecording(filepath, "wav", 16000, (0, 0, 1, 0))
                time.sleep(duration)
                self.rec.stopMicrophonesRecording()
                print("[INFO] Recording saved to robot at {}".format(filepath))
            except Exception as e:
                print("[ERROR] Audio recording failed: {}".format(e))
        else:
            print("[WARN] AudioRecorder Proxy not available.")