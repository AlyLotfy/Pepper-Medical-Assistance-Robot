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
FLAG_FILE = "voice_start.flag"  # Added for automated trigger
LANG_FLAG_FILE = "lang.flag"    # Language preference from UI (en/ar)

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

# Clean up stale flag/recording from a previous run
if os.path.exists(FLAG_FILE):
    try:
        os.remove(FLAG_FILE)
        print("[INIT] Removed stale voice flag from previous run.")
    except Exception:
        pass
try:
    rec.stopMicrophonesRecording()
    print("[INIT] Stopped stale recording from previous run.")
except Exception:
    pass  # No recording in progress — expected

print("")
print("==============================================")
print("   PEPPER VOICE CHAT – AUTOMATED FLAG MODE")
print("   Robot IP:   {}".format(PEPPER_IP))
print("   Server URL: {}".format(SERVER_URL))
print("   Polling for '{}' to start recording...".format(FLAG_FILE))
print("==============================================")
print("")

# -------------------------------------------------------
# LANGUAGE HELPER
# -------------------------------------------------------
def get_ui_lang():
    """Read UI language from flag file written by nav_bridge."""
    try:
        if os.path.exists(LANG_FLAG_FILE):
            with open(LANG_FLAG_FILE, "r") as f:
                lang = f.read().strip()
            if lang in ("ar", "en"):
                return lang
    except Exception:
        pass
    return "en"

def set_tts_language(lang):
    """Switch Pepper TTS engine to Arabic or English."""
    try:
        if lang == "ar":
            tts.setLanguage("Arabic")
        else:
            tts.setLanguage("English")
    except Exception as e:
        print("[WARN] Could not set TTS language: {}".format(e))

# -------------------------------------------------------
# RECORD AUDIO
# -------------------------------------------------------
def record_audio():
    lang = get_ui_lang()
    set_tts_language(lang)
    if lang == "ar":
        tts.say(u"\u062a\u0641\u0636\u0644 \u0628\u0627\u0644\u062a\u062d\u062f\u062b \u0627\u0644\u0622\u0646.".encode("utf-8"))
    else:
        tts.say("Please speak now.")
    print("[INFO] Recording...")

    rec.startMicrophonesRecording(PEPPER_FILE, "wav", 16000, (1,0,0,0))
    time.sleep(6)
    rec.stopMicrophonesRecording()

    print("[INFO] Recording done. Transferring audio...")

    cmd = '"{}" -pw nao nao@{}:{} {}'.format(
        PSCP, PEPPER_IP, PEPPER_FILE, LOCAL_FILE
    )
    os.system(cmd)

# -------------------------------------------------------
# OFFLINE VOICE FALLBACK (ALSpeechRecognition)
# -------------------------------------------------------
OFFLINE_KEYWORDS_EN = [
    "hello", "help", "emergency", "doctor", "appointment",
    "room", "schedule", "nurse", "pain", "thank you", "goodbye"
]
OFFLINE_KEYWORDS_AR = [
    "مرحبا", "مساعدة", "طوارئ", "دكتور", "موعد",
    "غرفة", "جدول", "ممرضة", "ألم", "شكرا", "مع السلامة"
]
OFFLINE_REPLIES_EN = {
    "hello":       "Hello! I am Pepper, your hospital assistant. How can I help?",
    "help":        "I can help you find a doctor, book an appointment, or guide you to a room. What do you need?",
    "emergency":   "If you have an emergency, please use the Emergency button on my screen or ask any staff member.",
    "doctor":      "You can use the Guide to Room feature on my screen to find a doctor.",
    "appointment": "You can book an appointment using the Book Appointment option on my home screen.",
    "room":        "Use the Guide to Room tile on my screen and I will take you there.",
    "schedule":    "Check the Schedule page on my screen to see doctor availability.",
    "nurse":       "I will alert a nurse for you. Please wait a moment.",
    "pain":        "I am sorry you are in pain. Please use the Symptom Check on my screen for triage.",
    "thank you":   "You are welcome! I am happy to help.",
    "goodbye":     "Goodbye! Take care and feel better soon.",
}
OFFLINE_REPLIES_AR = {
    "مرحبا":      "مرحبا! أنا بيبر، مساعدك في المستشفى. كيف يمكنني مساعدتك؟",
    "مساعدة":     "يمكنني مساعدتك في إيجاد طبيب أو حجز موعد. ماذا تحتاج؟",
    "طوارئ":      "إذا كانت لديك حالة طارئة، استخدم زر الطوارئ على شاشتي.",
    "دكتور":      "يمكنك استخدام خاصية الدليل إلى الغرفة لإيجاد طبيب.",
    "موعد":       "يمكنك حجز موعد من خلال شاشتي الرئيسية.",
    "غرفة":       "استخدم الدليل إلى الغرفة وسأرشدك.",
    "جدول":       "تحقق من صفحة الجدول على شاشتي لمعرفة أوقات الأطباء.",
    "ممرضة":      "سأنبه ممرضة لك. يرجى الانتظار.",
    "ألم":        "آسف لأنك تعاني من الألم. استخدم فحص الأعراض على شاشتي.",
    "شكرا":       "على الرحب والسعة! سعيد بمساعدتك.",
    "مع السلامة": "مع السلامة! اعتنِ بنفسك وأتمنى لك الشفاء العاجل.",
}

_speech_reco = None

def init_offline_recognition():
    """Initialize ALSpeechRecognition for offline keyword detection."""
    global _speech_reco
    try:
        _speech_reco = ALProxy("ALSpeechRecognition", PEPPER_IP, PEPPER_PORT)
        _speech_reco.setLanguage("English")
        print("[OFFLINE] ALSpeechRecognition initialized.")
    except Exception as e:
        print("[WARN] Could not initialize ALSpeechRecognition: {}".format(e))
        _speech_reco = None

def offline_voice_recognition():
    """
    Use ALSpeechRecognition for offline keyword-based voice interaction.
    Returns a reply string based on the matched keyword.
    """
    global _speech_reco
    if _speech_reco is None:
        init_offline_recognition()
    if _speech_reco is None:
        return "I cannot process voice offline right now."

    lang = get_ui_lang()
    keywords = OFFLINE_KEYWORDS_EN if lang == "en" else OFFLINE_KEYWORDS_AR
    replies = OFFLINE_REPLIES_EN if lang == "en" else OFFLINE_REPLIES_AR

    try:
        _speech_reco.setLanguage("Arabic" if lang == "ar" else "English")
        _speech_reco.setVocabulary(keywords, False)
        _speech_reco.subscribe("PepperOffline")

        # Listen for a keyword (the robot listens through its microphones)
        memory = ALProxy("ALMemory", PEPPER_IP, PEPPER_PORT)
        time.sleep(4)  # Listen for 4 seconds

        # Check what was recognized
        result = memory.getData("WordRecognized")
        _speech_reco.unsubscribe("PepperOffline")

        if result and len(result) >= 2:
            word = result[0]
            confidence = result[1]
            print("[OFFLINE] Recognized: '{}' (conf={:.2f})".format(word, confidence))

            if confidence > 0.3 and word in replies:
                return replies[word]

        if lang == "ar":
            return "لم أفهم. يرجى المحاولة مرة أخرى أو استخدام الشاشة."
        return "I did not catch that. Please try again or use the touchscreen."

    except Exception as e:
        print("[OFFLINE] Recognition error: {}".format(e))
        try:
            _speech_reco.unsubscribe("PepperOffline")
        except Exception:
            pass
        return "Voice recognition encountered an error."

# -------------------------------------------------------
# CHECK IF BACKEND IS REACHABLE
# -------------------------------------------------------
def is_backend_reachable():
    """Quick check if the Flask backend is responding."""
    try:
        check_url = "http://{}:{}/".format(SERVER_IP, SERVER_PORT)
        r = requests.get(check_url, timeout=3)
        return r.status_code == 200
    except Exception:
        return False

# -------------------------------------------------------
# SEND AUDIO TO BACKEND
# -------------------------------------------------------
def process_backend():
    if not os.path.exists(LOCAL_FILE):
        print("[ERROR] File was not transferred.")
        return "Audio transfer failed."

    lang = get_ui_lang()
    with open(LOCAL_FILE, "rb") as f:
        files = {"file": ("voice.wav", f, "audio/wav")}
        form_data = {"lang": lang}
        try:
            r = requests.post(SERVER_URL, files=files, data=form_data, timeout=120)
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
            print("[INFO] Falling back to offline voice recognition...")
            return None  # Signal to use offline fallback

# -------------------------------------------------------
# MAIN LOOP – FILE-FLAG IPC MECHANISM
# -------------------------------------------------------
while True:
    # Check for the trigger flag instead of raw_input()
    if os.path.exists(FLAG_FILE):
        print("\n[INFO] Trigger flag detected! Starting interaction...")

        # Remove the flag so it doesn't loop infinitely
        try:
            os.remove(FLAG_FILE)
        except Exception as e:
            print("[WARN] Could not remove flag file: {}".format(e))

        try:
            print("[INFO] Starting voice interaction...")

            # Check if backend is reachable; choose online or offline path
            if is_backend_reachable():
                record_audio()
                print("[INFO] Processing speech via backend...")
                reply = process_backend()

                # If backend call failed mid-request, fall back to offline
                if reply is None:
                    print("[INFO] Backend failed. Using offline fallback...")
                    reply = offline_voice_recognition()
            else:
                print("[INFO] Backend unreachable. Using offline voice recognition...")
                reply = offline_voice_recognition()

            try:
                print("[PEPPER REPLY]: {}".format(reply))
            except UnicodeEncodeError:
                print("[PEPPER REPLY]: (non-ASCII reply, cannot display in console)")

            # ALWAYS convert to UTF-8 to prevent NAOqi crash
            if isinstance(reply, unicode):
                reply = reply.encode("utf-8")

            # Set TTS language based on UI preference before speaking reply
            set_tts_language(get_ui_lang())
            tts.say(reply)
            print("[INFO] Interaction complete. Returning to polling state...\n")

        except Exception as e:
            print("[ERROR] Voice interaction failed: {}".format(e))
            # Ensure recording is stopped so next interaction works
            try:
                rec.stopMicrophonesRecording()
            except Exception:
                pass
            print("[INFO] Recovered. Returning to polling state...\n")

    else:
        # Sleep briefly to prevent high CPU usage while waiting
        time.sleep(0.5)