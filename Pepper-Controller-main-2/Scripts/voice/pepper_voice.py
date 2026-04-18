# -*- coding: utf-8 -*-
from naoqi import ALProxy
import time, requests, os

# === Configuration ===
PEPPER_IP   = "1.1.1.10"              # Pepper’s IP
SERVER_URL  = "http://1.1.1.245:8000/api/voice"  # backend URL
AUDIO_FILE  = "voice.wav"             # local filename
PSCP_PATH   = r"C:\Program Files\PuTTY\pscp.exe"  # full path to pscp.exe

def greet():
    """Pepper greets the user."""
    tts = ALProxy("ALTextToSpeech", PEPPER_IP, 9559)
    tts.say("Welcome to Andalusia Hospital, how can I help you?")

def record_from_mic():
    """Record from Pepper's mic and copy file to this computer."""
    tts = ALProxy("ALTextToSpeech", PEPPER_IP, 9559)
    rec = ALProxy("ALAudioRecorder", PEPPER_IP, 9559)

    tts.say("Please speak now.")
    pepper_path = "/tmp/voice.wav"
    rec.startMicrophonesRecording(pepper_path, "wav", 16000, (0, 0, 1, 0))
    time.sleep(4)
    rec.stopMicrophonesRecording()
    tts.say("Thank you.")

    # Copy via PuTTY SCP
    if not os.path.exists(PSCP_PATH):
        print("[ERROR] pscp.exe not found! Please check PSCP_PATH.")
        return None

    ftp_cmd = '"{}" -pw nao nao@{}:{} {}'.format(PSCP_PATH, PEPPER_IP, pepper_path, AUDIO_FILE)
    print("[DEBUG] Running:", ftp_cmd)
    os.system(ftp_cmd)

    if not os.path.exists(AUDIO_FILE):
        print("[ERROR] File transfer failed: {} not found.".format(AUDIO_FILE))
        return None

    return AUDIO_FILE

def send_audio_to_server(path):
    """Send audio to FastAPI backend and get Claude reply."""
    if not path or not os.path.exists(path):
        return "Audio file missing, please try again."

    with open(path, "rb") as f:
        files = {"file": ("voice.wav", f, "audio/wav")}
        try:
            r = requests.post(SERVER_URL, files=files, timeout=60)
            if r.status_code == 200:
                return r.json()["reply"]
        except Exception as e:
            print("[ERROR] While sending to backend:", e)
    return "Sorry, I could not reach the server."

def speak(text):
    """Safely make Pepper speak UTF-8 text."""
    if text is None:
        text = "Sorry, I have no response."
    if not isinstance(text, str):
        try:
            text = text.encode("utf-8")  # convert unicode→bytes
        except Exception:
            text = str(text)
    tts = ALProxy("ALTextToSpeech", PEPPER_IP, 9559)
    tts.say(text)

def run_pepper_loop():
    """Main loop."""
    speak("Voice assistant ready.")
    while True:
        cmd = raw_input("Press Enter to talk or q to quit: ").strip().lower()
        if cmd == "q":
            speak("Goodbye.")
            break

        greet()
        path = record_from_mic()
        if path:
            speak("Processing your request.")
            reply = send_audio_to_server(path)
            print("Claude:", reply)
            speak(reply)
        else:
            speak("Sorry, I could not record your voice. Please try again.")

if __name__ == "__main__":
    print("[INFO] pepper_voice.py started")
    run_pepper_loop()
