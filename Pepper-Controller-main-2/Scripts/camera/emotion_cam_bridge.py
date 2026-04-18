# -*- coding: utf-8 -*-
# Python 2.7 - Pepper Camera Emotion Bridge
# Captures frames from Pepper's camera and sends them to the
# backend emotion detection API, then optionally reacts via TTS.
"""
Usage:
    python emotion_cam_bridge.py

Environment variables:
    ROBOT_IP   - Pepper's IP address (default: 127.0.0.1)
    ROBOT_PORT - NAOqi port (default: 9559)
    SERVER_IP  - Backend server IP (default: 127.0.0.1)
    SERVER_PORT - Backend server port (default: 8080)
"""

import os
import sys
import time
import cv2
import numpy as np

try:
    import requests
except ImportError:
    print("[ERROR] requests library not found. Install with: pip install requests")
    sys.exit(1)

from naoqi import ALProxy

# --- Configuration ---
PEPPER_IP   = os.environ.get("ROBOT_IP", "127.0.0.1")
PEPPER_PORT = int(os.environ.get("ROBOT_PORT", "9559"))
SERVER_IP   = os.environ.get("SERVER_IP", "127.0.0.1")
SERVER_PORT = os.environ.get("SERVER_PORT", "8080")

EMOTION_API = "http://{}:{}/api/emotion_detect".format(SERVER_IP, SERVER_PORT)
CAPTURE_INTERVAL = 5  # seconds between emotion checks

# Emotion -> TTS reaction mapping
EMOTION_REACTIONS = {
    "happy":    {"en": "You look happy! That's wonderful.", "ar": "تبدو سعيدا! هذا رائع."},
    "sad":      {"en": "You seem a bit down. Is there anything I can help with?", "ar": "تبدو حزينا قليلا. هل يمكنني المساعدة؟"},
    "angry":    {"en": "I sense some frustration. Please let me know how I can assist you.", "ar": "أشعر ببعض الإحباط. أخبرني كيف يمكنني مساعدتك."},
    "surprise": {"en": "Oh! You look surprised!", "ar": "يبدو أنك متفاجئ!"},
    "fear":     {"en": "Don't worry, you are in safe hands here at the hospital.", "ar": "لا تقلق، أنت في أيد أمينة هنا في المستشفى."},
    "neutral":  None,  # No reaction for neutral
    "disgust":  None,
}


def connect_camera():
    """Connect to Pepper's top camera via ALVideoDevice."""
    video = ALProxy("ALVideoDevice", PEPPER_IP, PEPPER_PORT)
    # Resolution 1 = 320x240, ColorSpace 11 = RGB, FPS = 5
    sub_id = video.subscribeCamera("emotion_cam", 0, 1, 11, 5)
    print("[EMOTION_CAM] Subscribed to Pepper camera: {}".format(sub_id))
    return video, sub_id


def capture_frame(video, sub_id):
    """Capture a single frame from Pepper's camera and return as JPEG bytes."""
    img_raw = video.getImageRemote(sub_id)
    if not img_raw:
        return None

    width  = img_raw[0]
    height = img_raw[1]
    array  = img_raw[6]

    img_data = np.frombuffer(array, dtype=np.uint8)
    img_data = img_data.reshape((height, width, 3))

    # RGB (Pepper) -> BGR (OpenCV)
    frame = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)

    # Encode as JPEG
    _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return jpeg.tobytes()


def send_to_api(jpeg_bytes):
    """POST the frame to the emotion detection API."""
    try:
        resp = requests.post(
            EMOTION_API,
            files={"image": ("frame.jpg", jpeg_bytes, "image/jpeg")},
            timeout=5
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            print("[EMOTION_CAM] API returned status {}".format(resp.status_code))
    except Exception as e:
        print("[EMOTION_CAM] API error: {}".format(e))
    return None


def react_to_emotion(emotion, tts, lang="en"):
    """Make Pepper speak a reaction based on detected emotion."""
    reaction = EMOTION_REACTIONS.get(emotion)
    if reaction is None:
        return
    text = reaction.get(lang, reaction.get("en", ""))
    if text:
        try:
            tts.setLanguage("Arabic" if lang == "ar" else "English")
            tts.say(text)
        except Exception as e:
            print("[EMOTION_CAM] TTS error: {}".format(e))


def get_ui_lang():
    """Read current UI language from flag file."""
    flag_path = os.path.join(os.path.dirname(__file__), "..", "..", "pepper_voice", "lang.flag")
    try:
        with open(flag_path, "r") as f:
            lang = f.read().strip()
            return lang if lang in ("ar", "en") else "en"
    except Exception:
        return "en"


def main():
    print("[EMOTION_CAM] Starting Pepper Emotion Camera Bridge")
    print("[EMOTION_CAM] Robot: {}:{} | Server: {}".format(PEPPER_IP, PEPPER_PORT, EMOTION_API))

    video, sub_id = connect_camera()
    tts = ALProxy("ALTextToSpeech", PEPPER_IP, PEPPER_PORT)

    last_emotion = None
    last_react_time = 0

    try:
        while True:
            jpeg = capture_frame(video, sub_id)
            if jpeg:
                result = send_to_api(jpeg)
                if result and result.get("count", 0) > 0:
                    face = result["faces"][0]
                    emotion = face.get("emotion", "neutral")
                    confidence = face.get("confidence", 0)
                    print("[EMOTION_CAM] Detected: {} (conf={:.2f})".format(emotion, confidence))

                    # React only if emotion changed and enough time passed (avoid spam)
                    now = time.time()
                    if emotion != last_emotion and confidence > 0.5 and (now - last_react_time) > 15:
                        lang = get_ui_lang()
                        react_to_emotion(emotion, tts, lang)
                        last_emotion = emotion
                        last_react_time = now

            time.sleep(CAPTURE_INTERVAL)

    except KeyboardInterrupt:
        print("\n[EMOTION_CAM] Shutting down...")
    finally:
        try:
            video.unsubscribe(sub_id)
        except Exception:
            pass


if __name__ == "__main__":
    main()
