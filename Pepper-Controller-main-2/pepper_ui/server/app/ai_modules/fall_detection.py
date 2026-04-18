# -*- coding: utf-8 -*-
"""
fall_detection.py - Real-time Fall Detection for Pepper Robot
TIER 1 (fully offline): MediaPipe Pose (if installed) for accurate skeletal tracking.
TIER 2 (offline fallback): OpenCV background subtraction + motion centroid tracking.
No network required.

Usage:
    from ai_modules.fall_detection import FallDetector
    fd = FallDetector()
    fd.add_alert_callback(my_fn)
    fd.start(camera_index=0)
    ...
    fd.stop()
"""
import os
import time
import json
import threading
import base64
from datetime import datetime

try:
    import cv2
    import numpy as np
    _CV2 = True
except ImportError:
    _CV2 = False

try:
    import mediapipe as mp
    _MP_AVAILABLE = True
    _mp_pose = mp.solutions.pose
    _mp_pose_landmark = mp.solutions.pose.PoseLandmark
except ImportError:
    _MP_AVAILABLE = False

# Pepper camera URL (fallback when no local camera)
_CAMERA_URL = os.environ.get("PEPPER_CAMERA_URL", "http://127.0.0.1:8082/snapshot")


class FallDetector:
    """
    Monitors a video feed for patient fall events.

    Detection strategy:
      1. MediaPipe Pose: tracks hip/nose landmarks across frames.
         Fall = hips drop rapidly (>18% frame height/frame) AND nose is in lower 60% of frame.
      2. OpenCV MOG2 fallback: tracks motion centroid.
         Fall = centroid drops >18% of frame height in one frame.

    Rate-limited to one alert per `alert_cooldown` seconds to avoid spam.
    """

    FALL_THRESHOLD   = 0.18    # normalised frame-height drop per frame
    ALERT_COOLDOWN   = 30      # seconds between repeat alerts
    CONSECUTIVE_REQ  = 3       # consecutive fall frames needed to trigger

    def __init__(self):
        self.enabled            = False
        self._thread            = None
        self._lock              = threading.Lock()
        self._alert_callbacks   = []
        self._last_alert_time   = 0
        self._fall_log          = []
        self._prev_hip_y        = None
        self._prev_cent_y       = None

        # Background subtractor (OpenCV fallback)
        self._bg_sub = cv2.createBackgroundSubtractorMOG2(
            history=80, varThreshold=20, detectShadows=False
        ) if _CV2 else None

        # MediaPipe pose (lazy-init in start())
        self._pose = None
        if _MP_AVAILABLE:
            try:
                self._pose = _mp_pose.Pose(
                    model_complexity=0,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5
                )
            except Exception as e:
                print(f"[FALL] MediaPipe init error: {e}")
                self._pose = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_alert_callback(self, fn):
        """Register a callable fn(alert_dict) invoked on each fall event."""
        self._alert_callbacks.append(fn)

    def start(self, camera_index=0):
        """Start the background monitoring thread."""
        if self.enabled:
            return {"success": True, "message": "Already running.", "method": self._method()}
        if not _CV2:
            return {"success": False,
                    "error": "OpenCV (cv2) is not installed. Install it with: pip install opencv-python"}
        self.enabled = True
        self._thread = threading.Thread(
            target=self._run_loop, args=(camera_index,), daemon=True
        )
        self._thread.start()
        return {
            "success": True,
            "message": "Fall detection started.",
            "method":  self._method()
        }

    def stop(self):
        """Stop the monitoring thread."""
        self.enabled = False
        self._prev_hip_y  = None
        self._prev_cent_y = None
        return {"success": True, "message": "Fall detection stopped."}

    def analyze_frame(self, image_b64):
        """
        One-shot fall risk assessment for a single base64 JPEG.
        Returns: {"fall_risk": bool, "posture": str, "confidence": float}
        Fully offline.
        """
        if not _CV2:
            return {"fall_risk": False, "posture": "unknown", "confidence": 0.0,
                    "error": "OpenCV not available."}
        try:
            data  = base64.b64decode(image_b64.split(",")[-1])
            arr   = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                return {"fall_risk": False, "posture": "unknown", "confidence": 0.0,
                        "error": "Could not decode image."}

            if _MP_AVAILABLE and self._pose:
                return self._analyze_mediapipe(frame)
            return {"fall_risk": False, "posture": "unknown", "confidence": 0.0,
                    "note": "Continuous monitoring required (MediaPipe unavailable)."}
        except Exception as e:
            return {"fall_risk": False, "posture": "unknown", "confidence": 0.0,
                    "error": str(e)}

    def get_alerts(self, clear=True):
        """Return accumulated fall alerts, optionally clearing the log."""
        with self._lock:
            alerts = list(self._fall_log)
            if clear:
                self._fall_log.clear()
        return alerts

    def status(self):
        """Return the current status dict."""
        return {
            "enabled":       self.enabled,
            "method":        self._method(),
            "mediapipe":     _MP_AVAILABLE and self._pose is not None,
            "opencv":        _CV2,
            "total_alerts":  len(self._fall_log),
            "cooldown_secs": self.ALERT_COOLDOWN,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _method(self):
        return "mediapipe" if (self._pose is not None) else ("opencv" if _CV2 else "unavailable")

    def _run_loop(self, camera_index):
        """Background thread: open camera, read frames, detect falls."""
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            cap = cv2.VideoCapture(_CAMERA_URL)
        if not cap.isOpened():
            print("[FALL] Cannot open camera — fall detection disabled.")
            self.enabled = False
            return

        consecutive = 0
        while self.enabled:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.2)
                continue
            h = frame.shape[0]

            fell = (self._check_mediapipe(frame, h)
                    if (self._pose is not None) else
                    self._check_opencv(frame, h))

            if fell:
                consecutive += 1
                if consecutive >= self.CONSECUTIVE_REQ:
                    self._on_fall()
                    consecutive = 0
            else:
                consecutive = max(0, consecutive - 1)

            time.sleep(0.10)   # ~10 FPS to save CPU

        cap.release()

    def _check_mediapipe(self, frame, h):
        """True when MediaPipe detects a rapid hip-drop (fall motion)."""
        try:
            import mediapipe as mp
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self._pose.process(rgb)
            if not result.pose_landmarks:
                return False
            lm        = result.pose_landmarks.landmark
            PL        = _mp_pose_landmark
            hip_y     = (lm[PL.LEFT_HIP].y + lm[PL.RIGHT_HIP].y) / 2  # 0=top, 1=bottom
            nose_y    = lm[PL.NOSE].y
            if self._prev_hip_y is None:
                self._prev_hip_y = hip_y
                return False
            delta             = hip_y - self._prev_hip_y
            self._prev_hip_y  = hip_y
            # Hips dropped fast AND head is in lower 60% (person is on the floor)
            return delta > self.FALL_THRESHOLD and nose_y > 0.60
        except Exception:
            return False

    def _check_opencv(self, frame, h):
        """True when the MOG2 motion centroid drops rapidly (simpler heuristic)."""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            fg   = self._bg_sub.apply(gray)
            contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                self._prev_cent_y = None
                return False
            largest = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest) < 800:
                return False
            M = cv2.moments(largest)
            if M["m00"] == 0:
                return False
            cy = int(M["m01"] / M["m00"]) / h
            if self._prev_cent_y is None:
                self._prev_cent_y = cy
                return False
            delta             = cy - self._prev_cent_y
            self._prev_cent_y = cy
            return delta > self.FALL_THRESHOLD
        except Exception:
            return False

    def _analyze_mediapipe(self, frame):
        """Classify posture from a single frame using MediaPipe."""
        try:
            import mediapipe as mp
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self._pose.process(rgb)
            if not result.pose_landmarks:
                return {"fall_risk": False, "posture": "no_person", "confidence": 0.0}
            lm     = result.pose_landmarks.landmark
            PL     = _mp_pose_landmark
            nose_y = lm[PL.NOSE].y
            hip_y  = (lm[PL.LEFT_HIP].y + lm[PL.RIGHT_HIP].y) / 2
            ankle_y = (lm[PL.LEFT_ANKLE].y + lm[PL.RIGHT_ANKLE].y) / 2
            hip_ankle_diff = abs(hip_y - ankle_y)
            if nose_y > 0.55 and hip_ankle_diff < 0.20:
                return {"fall_risk": True,  "posture": "fallen",   "confidence": 0.85}
            if nose_y > 0.45:
                return {"fall_risk": True,  "posture": "crouching","confidence": 0.55}
            return   {"fall_risk": False, "posture": "standing",  "confidence": 0.90}
        except Exception as e:
            return {"fall_risk": False, "posture": "unknown", "confidence": 0.0, "error": str(e)}

    def _on_fall(self):
        """Fire fall alerts (rate-limited)."""
        now = time.time()
        if now - self._last_alert_time < self.ALERT_COOLDOWN:
            return
        self._last_alert_time = now
        alert = {
            "type":      "fall_detected",
            "timestamp": datetime.now().isoformat(),
            "message":   "FALL DETECTED — Immediate assistance required!",
            "severity":  "critical",
        }
        with self._lock:
            self._fall_log.append(alert)
        print(f"[FALL ALERT] {alert['message']}")
        for fn in self._alert_callbacks:
            try:
                fn(alert)
            except Exception as e:
                print(f"[FALL] Callback error: {e}")
