# -*- coding: utf-8 -*-
"""
emotion_detector.py - Facial Emotion Recognition for Pepper Robot
=================================================================
Uses OpenCV Haar cascades for face detection and a lightweight
CNN-based approach (FER library) for emotion classification.

Emotions detected: angry, disgust, fear, happy, sad, surprise, neutral

Usage (from app.py):
    from emotion_detector import EmotionDetector
    detector = EmotionDetector()
    result = detector.detect_from_bytes(jpeg_bytes)
    # result = {"faces": [{"emotion": "happy", "confidence": 0.92, "box": [x,y,w,h]}]}
"""

import os
import cv2
import numpy as np

# Attempt to import FER; fall back to cascade-only mode
_FER_AVAILABLE = False
try:
    from fer import FER
    _FER_AVAILABLE = True
except ImportError:
    pass


class EmotionDetector:
    """
    Detects faces and classifies emotions from images.
    Falls back to Haar cascade face detection if FER is not installed.
    """

    def __init__(self):
        self._fer = None
        self._cascade = None
        self._ready = False
        self._load()

    def _load(self):
        """Initialize the detection models."""
        if _FER_AVAILABLE:
            try:
                self._fer = FER(mtcnn=False)  # Use OpenCV cascade (faster, no GPU needed)
                self._ready = True
                print("[EMOTION] FER emotion detector loaded.")
                return
            except Exception as e:
                print(f"[EMOTION] FER init failed ({e}), falling back to cascade-only.")

        # Fallback: OpenCV Haar cascade (face detection only, no emotion)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        if os.path.exists(cascade_path):
            self._cascade = cv2.CascadeClassifier(cascade_path)
            self._ready = True
            print("[EMOTION] Haar cascade loaded (face detection only, no emotion classification).")
        else:
            print("[EMOTION] No face detection model available. Emotion detection disabled.")

    def is_ready(self):
        return self._ready

    def detect_from_bytes(self, image_bytes):
        """
        Detect faces and emotions from raw JPEG/PNG bytes.
        Returns: {"faces": [{"emotion": str, "confidence": float, "box": [x,y,w,h]}], "count": int}
        """
        if not self._ready:
            return {"faces": [], "count": 0, "error": "Detector not ready"}

        try:
            # Decode image
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return {"faces": [], "count": 0, "error": "Could not decode image"}

            return self.detect_from_frame(img)
        except Exception as e:
            return {"faces": [], "count": 0, "error": str(e)}

    def detect_from_frame(self, frame):
        """
        Detect faces and emotions from an OpenCV BGR frame.
        Returns: {"faces": [{"emotion": str, "confidence": float, "box": [x,y,w,h]}], "count": int}
        """
        if not self._ready:
            return {"faces": [], "count": 0, "error": "Detector not ready"}

        faces = []

        if self._fer is not None:
            # Full emotion detection with FER
            results = self._fer.detect_emotions(frame)
            for r in results:
                box = r.get("box", [0, 0, 0, 0])
                emotions = r.get("emotions", {})
                if emotions:
                    top_emotion = max(emotions, key=emotions.get)
                    confidence = emotions[top_emotion]
                else:
                    top_emotion = "unknown"
                    confidence = 0.0
                faces.append({
                    "emotion": top_emotion,
                    "confidence": round(confidence, 3),
                    "all_emotions": {k: round(v, 3) for k, v in emotions.items()},
                    "box": list(box),
                })
        elif self._cascade is not None:
            # Cascade-only: detect faces, assign "neutral" as default
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            detected = self._cascade.detectMultiScale(gray, 1.3, 5, minSize=(30, 30))
            for (x, y, w, h) in detected:
                faces.append({
                    "emotion": "neutral",
                    "confidence": 1.0,
                    "all_emotions": {"neutral": 1.0},
                    "box": [int(x), int(y), int(w), int(h)],
                })

        return {"faces": faces, "count": len(faces)}

    def status(self):
        """Return detector health info."""
        return {
            "ready": self._ready,
            "backend": "FER" if self._fer else ("Haar" if self._cascade else "none"),
            "fer_available": _FER_AVAILABLE,
        }
