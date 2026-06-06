# -*- coding: utf-8 -*-
from naoqi import ALProxy
import time
import os
import json
import subprocess
import requests

try:
    from websocket import create_connection as _ws_connect
except ImportError:
    _ws_connect = None

# Python 2/3 compatible text type check
try:
    _text_type = unicode   # Python 2
except NameError:
    _text_type = str       # Python 3

# -------------------------------------------------------
# CONFIGURATION (DYNAMIC FROM MAIN.PY LAUNCHER)
# -------------------------------------------------------
# Grab IPs from environment variables, with local fallbacks
PEPPER_IP = os.environ.get("ROBOT_IP", "127.0.0.1")
PEPPER_PORT = int(os.environ.get("ROBOT_PORT", "9559"))

SERVER_IP = os.environ.get("SERVER_IP", "127.0.0.1")
SERVER_PORT = os.environ.get("SERVER_PORT", "8080")
WS_PORT   = os.environ.get("WS_PORT", "8765")

# Dynamically construct the backend URL
SERVER_URL = "http://{}:{}/api/process_audio".format(SERVER_IP, SERVER_PORT)
WS_URL     = "ws://{}:{}".format(SERVER_IP, WS_PORT)


def broadcast_voice_result(user_text, ai_text, lang):
    """Push transcript + reply to the WS bridge so the tablet UI can show
    it on-screen the instant TTS starts speaking. Never raises.
    """
    if _ws_connect is None:
        return
    payload = json.dumps({
        "type":      "result",
        "user_text": user_text or "",
        "ai_text":   ai_text or "",
        "lang":      lang or "en",
    })
    for attempt in range(2):
        try:
            ws = _ws_connect(WS_URL, timeout=3)
            ws.send(payload)
            # Give the bridge time to broadcast before we tear down the socket
            time.sleep(0.25)
            try:
                ws.close()
            except Exception:
                pass
            if attempt > 0:
                print("[WS] Voice result re-broadcast succeeded (attempt {}).".format(attempt + 1))
            return
        except Exception as e:
            print("[WS] Broadcast attempt {} failed: {}".format(attempt + 1, e))
            time.sleep(0.3)


def broadcast_recording_started():
    """Notify the tablet that the microphone is NOW live (called right after
    startMicrophonesRecording, i.e. after Pepper has said 'please speak now').

    This is the key UI<->voice synchronization signal: without it the tablet
    flips to 'Listening' the instant the user taps, ~1.5s before the mic is
    actually capturing — so the user speaks into a dead mic and the first
    words are lost. The tablet stays in a 'getting ready' state until this
    arrives. Never raises.
    """
    _broadcast_simple({"type": "recording_started"}, "recording_started")


def broadcast_speaking_start():
    """Notify the tablet that TTS audio is starting now, so the reply text and
    the spoken audio appear together. Sent right before the blocking tts.say().
    Never raises.
    """
    _broadcast_simple({"type": "speaking_start"}, "speaking_start")


def broadcast_speaking_done():
    """Notify the tablet that TTS has finished so the mic button re-enables.
    Called immediately after tts.say() returns. Never raises.
    """
    _broadcast_simple({"type": "speaking_done"}, "speaking_done")


def broadcast_voice_abort(reason=""):
    """Notify the tablet that the voice interaction failed at any phase, so
    the mic FSM can recover without waiting for the 30s watchdog. Never raises.
    """
    _broadcast_simple({"type": "voice_abort", "reason": reason or ""}, "voice_abort")


def _broadcast_simple(payload_dict, label):
    if _ws_connect is None:
        return
    payload = json.dumps(payload_dict)
    for attempt in range(2):
        try:
            ws = _ws_connect(WS_URL, timeout=3)
            ws.send(payload)
            time.sleep(0.1)
            try:
                ws.close()
            except Exception:
                pass
            return
        except Exception as e:
            print("[WS] {} broadcast attempt {} failed: {}".format(label, attempt + 1, e))
            time.sleep(0.2)

LOCAL_FILE = "voice.wav"
PEPPER_FILE = "/tmp/voice.wav"
FLAG_FILE = "voice_start.flag"  # Added for automated trigger
STOP_FLAG_FILE = "voice_stop.flag"   # Early-stop request from UI
STATE_FLAG_FILE = "voice_state.flag" # Current state for tablet HTTP polling
RESULT_FLAG_FILE = "voice_result.json" # Last transcript+reply for HTTP fallback
LANG_FLAG_FILE = "lang.flag"    # Language preference from UI (en/ar)
USER_FLAG_FILE = "user.flag"    # Logged-in patient ID written by nav_bridge

# Recording duration bounds
MAX_RECORD_SECS = 8.0   # hard cap (was hard-coded 6s)
MIN_RECORD_SECS = 1.0   # ignore stop taps that fire faster than this


def write_state(state):
    """Write the current voice-loop state to a flag file the tablet can poll
    via /api/voice_status. Acts as an HTTP fallback for the WS broadcast so
    the tablet button is never stuck if the WS message is missed.
    """
    try:
        with open(STATE_FLAG_FILE, "w") as _sf:
            _sf.write(state)
    except Exception:
        pass


def write_result(user_text, ai_text, lang):
    """Persist the latest transcript + reply so /api/voice_status can hand it
    back as an HTTP fallback. This binds the on-screen text to the spoken
    reply: even if the ephemeral WS 'result' broadcast is dropped, the tablet's
    state poll still sees the text and renders it. The UI and the voice are
    never one-without-the-other.
    """
    try:
        with open(RESULT_FLAG_FILE, "w") as _rf:
            json.dump({
                "user_text": user_text or "",
                "ai_text":   ai_text or "",
                "lang":      lang or "en",
                "ts":        time.time(),
            }, _rf)
    except Exception:
        pass


def clear_result():
    """Drop any result from the previous turn so a stale transcript can't be
    shown while a new turn is starting/recording."""
    try:
        if os.path.exists(RESULT_FLAG_FILE):
            os.remove(RESULT_FLAG_FILE)
    except Exception:
        pass

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
for _stale in (FLAG_FILE, STOP_FLAG_FILE):
    if os.path.exists(_stale):
        try:
            os.remove(_stale)
            print("[INIT] Removed stale flag '{}' from previous run.".format(_stale))
        except Exception:
            pass
write_state("idle")
clear_result()
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

def get_ui_user_id():
    """Read logged-in patient ID from flag file written by nav_bridge."""
    try:
        if os.path.exists(USER_FLAG_FILE):
            with open(USER_FLAG_FILE, "r") as f:
                uid = f.read().strip()
            if uid:
                return uid
    except Exception:
        pass
    return ""

def set_tts_language(lang):
    """Switch Pepper TTS engine to Arabic or English.

    NAOqi ALTextToSpeech is stateful: setLanguage() can silently fail if
    the requested voice pack is not installed, leaving Pepper speaking
    the new text in the OLD voice (e.g. Arabic glyphs read with English
    phonemes — unintelligible). To make language switches reliable:
      1. Verify available languages first
      2. Try setLanguage, then read back .getLanguage() to confirm
      3. Tiny sleep so NAOqi has time to commit the voice change before
         the immediately-following tts.say() call uses the new voice
    """
    target = "Arabic" if lang == "ar" else "English"
    try:
        # Verify the requested voice is installed. If not, fall back to the
        # other language with a warning — better than speaking the wrong
        # phonemes for the wrong script.
        try:
            available = tts.getAvailableLanguages()
            if available and target not in available:
                print("[TTS] {} voice not available on this Pepper. "
                      "Available: {}. Falling back to English.".format(
                          target, available))
                target = "English"
        except Exception:
            pass   # getAvailableLanguages not supported on some NAOqi builds

        tts.setLanguage(target)
        # Small commit window — NAOqi sometimes hasn't fully switched voices
        # by the time the next .say() call hits the queue.
        time.sleep(0.1)
        try:
            current = tts.getLanguage()
            if current != target:
                print("[TTS] WARN: setLanguage({}) didn't stick — "
                      "current={}".format(target, current))
        except Exception:
            pass
    except Exception as e:
        print("[WARN] Could not set TTS language: {}".format(e))

# -------------------------------------------------------
# RECORD AUDIO
# -------------------------------------------------------
def record_audio():
    lang = get_ui_lang()
    # State is 'starting' until the mic is actually live. The tablet shows a
    # "getting ready" UI during this window instead of "Listening", so the
    # user doesn't start talking before Pepper is recording.
    # Drop the previous turn's result first so the tablet poll can't render
    # stale text while this new turn is still starting/recording.
    clear_result()
    write_state("starting")
    set_tts_language(lang)
    if lang == "ar":
        tts.say(u"\u062a\u0641\u0636\u0644 \u0628\u0627\u0644\u062a\u062d\u062f\u062b \u0627\u0644\u0622\u0646.".encode("utf-8"))
    else:
        tts.say("Please speak now.")
    print("[INFO] Recording (max {:.0f}s, tap stop to end early)...".format(MAX_RECORD_SECS))

    # Clear any leftover stop flag from a previous turn so the user must
    # actively tap to end this recording early.
    if os.path.exists(STOP_FLAG_FILE):
        try:
            os.remove(STOP_FLAG_FILE)
        except Exception:
            pass

    rec.startMicrophonesRecording(PEPPER_FILE, "wav", 16000, (1, 0, 0, 0))
    # Mic is live NOW \u2014 flip the tablet to 'Listening' in lockstep with reality.
    write_state("recording")
    broadcast_recording_started()

    # Poll for early-stop flag instead of a fixed sleep; honour MIN/MAX bounds
    started_at  = time.time()
    poll_period = 0.1
    stopped_early = False
    while True:
        elapsed = time.time() - started_at
        if elapsed >= MAX_RECORD_SECS:
            break
        if elapsed >= MIN_RECORD_SECS and os.path.exists(STOP_FLAG_FILE):
            stopped_early = True
            break
        time.sleep(poll_period)

    rec.stopMicrophonesRecording()
    write_state("processing")
    if os.path.exists(STOP_FLAG_FILE):
        try:
            os.remove(STOP_FLAG_FILE)
        except Exception:
            pass

    if stopped_early:
        print("[INFO] Recording stopped early at {:.1f}s by user. Transferring...".format(elapsed))
    else:
        print("[INFO] Recording done ({:.1f}s). Transferring audio...".format(elapsed))

    # Use a list — never a shell string — to prevent command injection.
    # subprocess.call() is used (not .run()) for Python 2.7 / NAOqi compatibility.
    # -batch: never prompt interactively. Without it, an unknown/changed SSH
    # host key makes PSCP block forever on a stdin "Store key? (y/n)" prompt,
    # wedging MainVoice so NO further taps are ever serviced (Pepper goes
    # permanently silent). -batch makes it fail fast instead, and the failed
    # transfer is handled downstream (process_backend sees no file -> offline).
    subprocess.call(
        [PSCP, "-batch", "-pw", "nao",
         "nao@{}:{}".format(PEPPER_IP, PEPPER_FILE), LOCAL_FILE]
    )

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
    """Send the recorded audio to Flask and return (user_text, reply).

    reply is None when the backend is unreachable so the caller can fall
    back to offline recognition.
    """
    if not os.path.exists(LOCAL_FILE):
        print("[ERROR] File was not transferred.")
        return ("", "Audio transfer failed.")

    lang    = get_ui_lang()
    user_id = get_ui_user_id()
    with open(LOCAL_FILE, "rb") as f:
        files = {"file": ("voice.wav", f, "audio/wav")}
        form_data = {"lang": lang}
        if user_id:
            form_data["patient_id"] = user_id
        try:
            # (connect, read) timeout: fail fast (5s) if the backend is down so
            # we drop to offline quickly, but allow up to 120s for the read —
            # Whisper STT + Claude can legitimately take that long.
            r = requests.post(SERVER_URL, files=files, data=form_data, timeout=(5, 120))
            data = r.json()

            text = data.get("text", "").strip()
            reply = data.get("reply", "").strip()

            if text == "":
                print("[WARN] Empty transcription received.")
                return ("", "I did not hear anything. Please repeat.")

            if reply == "":
                return (text, "I am having trouble processing your request.")

            return (text, reply)

        except Exception as e:
            print("[ERROR] Backend failure:", e)
            print("[INFO] Falling back to offline voice recognition...")
            return ("", None)  # Signal to use offline fallback

# -------------------------------------------------------
# MAIN LOOP – FILE-FLAG IPC MECHANISM
# -------------------------------------------------------
# Id of the last tap we actually serviced. A single tap writes voice_start.flag
# TWICE (WebSocket bridge + HTTP /api/start_voice, for redundancy) with the
# SAME id. The faster write starts the turn; the slower one lands mid-turn and
# would, when the turn ends, be picked up as a brand-new turn — auto-reopening
# the mic and saying "speak now" with no tap. We dedupe by id so each tap runs
# exactly once.
LAST_TAP_ID = None

while True:
    # Check for the trigger flag instead of raw_input()
    if os.path.exists(FLAG_FILE):
        # Read the tap id stamped into the flag BEFORE removing it.
        tap_id = ""
        try:
            with open(FLAG_FILE, "r") as _ff:
                tap_id = _ff.read().strip()
        except Exception:
            pass

        # Remove the start flag so it doesn't loop infinitely. Also wipe any
        # pre-existing stop flag — a leftover stop from a previous turn must
        # not abort the new recording before it begins.
        for _f in (FLAG_FILE, STOP_FLAG_FILE):
            if os.path.exists(_f):
                try:
                    os.remove(_f)
                except Exception as e:
                    print("[WARN] Could not remove '{}': {}".format(_f, e))

        # Duplicate write from the dual WS+HTTP start path for a tap we already
        # handled -> ignore it so the mic does NOT auto-reopen after speaking.
        if tap_id and tap_id == LAST_TAP_ID:
            print("[INFO] Ignoring duplicate start (tap '{}' already handled).".format(tap_id))
            write_state("idle")
            continue
        LAST_TAP_ID = tap_id

        print("\n[INFO] Trigger flag detected! Starting interaction...")
        try:
            print("[INFO] Starting voice interaction...")

            user_text = ""

            # ALWAYS announce + record first. record_audio() is what says
            # "Please speak now" and gives the user the recording window, so it
            # must run on every single tap — otherwise the user taps and Pepper
            # stays silent. We no longer gate this behind an is_backend_reachable()
            # pre-check: that 3s blocking health GET could time out transiently
            # (GPU Whisper / Claude holding Flask worker threads) and silently
            # drop into offline keyword mode WITHOUT ever saying "speak now",
            # which is exactly the "stops saying speak now after a few taps"
            # failure. Instead we record, try the backend, and only fall back to
            # offline keyword recognition if the POST itself fails.
            record_audio()
            print("[INFO] Processing speech via backend...")
            user_text, reply = process_backend()

            # If the backend call failed (connection refused / timeout / error),
            # fall back to offline keyword recognition so the turn still ends
            # with a spoken reply.
            if reply is None:
                print("[INFO] Backend unreachable. Using offline voice recognition...")
                reply = offline_voice_recognition()

            try:
                print("[PEPPER REPLY]: {}".format(reply))
            except UnicodeEncodeError:
                print("[PEPPER REPLY]: (non-ASCII reply, cannot display in console)")

            # Push the transcript + reply to the tablet BEFORE speaking so
            # the UI shows the text while Pepper talks. Persist it to the
            # result file FIRST so the HTTP state poll can serve it even if the
            # WS broadcast below is dropped — the text is bound to the reply.
            ui_lang = get_ui_lang()
            write_result(user_text, reply, ui_lang)
            broadcast_voice_result(user_text, reply, ui_lang)

            # ALWAYS convert to UTF-8 to prevent NAOqi crash (Python 2/3 safe)
            if isinstance(reply, _text_type):
                reply = reply.encode("utf-8")

            # Set TTS language based on UI preference before speaking reply.
            # Wrap tts.say in try/finally so the tablet ALWAYS gets a
            # 'speaking_done' notification, even if NAOqi raises mid-speech
            # (Arabic phonemes occasionally cause ALTextToSpeech exceptions).
            # Without this, the tablet mic button stays disabled until the
            # 45s fallback timer expires.
            set_tts_language(ui_lang)
            # Mark the shared state as 'speaking' so the tablet's status poll
            # (the reliable source of truth) reflects it even if the WS event is
            # lost — keeps the UI in lockstep with the actual speech.
            write_state("speaking")
            # Signal speech-start so the tablet shows the reply text exactly as
            # the audio begins (tts.say blocks until speech ends, so the
            # following speaking_done marks the precise end).
            broadcast_speaking_start()
            try:
                tts.say(reply)
            except Exception as _tts_err:
                print("[WARN] tts.say failed: {}".format(_tts_err))
            finally:
                broadcast_speaking_done()
            # Always return to idle after a turn. A genuinely-new tap (different
            # id) left in the flag will be picked up by the next loop iteration;
            # a duplicate of THIS tap is rejected by the id check. The mic never
            # auto-reopens on its own — every turn needs a deliberate tap.
            write_state("idle")
            print("[INFO] Interaction complete. Returning to polling state...\n")

        except Exception as e:
            print("[ERROR] Voice interaction failed: {}".format(e))
            # Ensure recording is stopped so next interaction works
            try:
                rec.stopMicrophonesRecording()
            except Exception:
                pass
            # Tell the tablet the interaction is aborted so the mic FSM can
            # recover without waiting for the 30s watchdog.
            try:
                broadcast_voice_abort(str(e))
            except Exception:
                pass
            write_state("idle")
            print("[INFO] Recovered. Returning to polling state...\n")

    else:
        # Poll the trigger flag at 50ms. UI research puts the "instant"
        # threshold at ~100ms; the old 0.5s sleep meant every tap waited up to
        # half a second before Pepper even reacted. 50ms is imperceptible and
        # the idle busy-wait cost is negligible (a single file existence check).
        time.sleep(0.05)