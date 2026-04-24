# -*- coding: utf-8 -*-
"""
pose_analyzer.py  —  Real-Time Pose Estimation & Behavioral Analysis
=====================================================================
Upgrades the existing FallDetector's visual pipeline with clinical-grade
behavioural analysis using MediaPipe Pose + Face Mesh:

  1. Distress pose detection  — chest-clutching, abdominal guarding, heavy lean
  2. Stroke FAST test         — facial asymmetry via Face Mesh landmarks
  3. Gait analysis            — limp / unsteadiness from multi-frame ankle tracking

Fully offline.  No network required.
"""

import os
import base64
import time
import threading
from datetime import datetime

try:
    import cv2
    import numpy as np
    _CV2 = True
except ImportError:
    _CV2 = False

try:
    import mediapipe as mp
    _mp_pose      = mp.solutions.pose
    _mp_face_mesh = mp.solutions.face_mesh
    _PL           = mp.solutions.pose.PoseLandmark
    _MP = True
except (ImportError, AttributeError):
    _MP = False

_CAMERA_URL = os.environ.get("PEPPER_CAMERA_URL", "http://127.0.0.1:8082/snapshot")


class PoseAnalyzer:
    """
    Clinical behavioral analysis from individual frames or a live camera feed.

    Public API
    ----------
    analyze_frame(image_b64)  -> dict          one-shot frame analysis
    start(camera_index=0)     -> dict          continuous background monitoring
    stop()                    -> dict
    add_alert_callback(fn)                     fn(alert_dict) called on each event
    get_alerts(clear=True)    -> list[dict]
    status()                  -> dict
    """

    ALERT_COOLDOWN  = 20   # seconds between same-type alerts (avoid spam)
    GAIT_WINDOW_S   = 3.0  # seconds of ankle history kept for gait analysis
    GAIT_MIN_FRAMES = 10   # minimum frames before gait judgement is made

    def __init__(self):
        self._pose         = None
        self._face         = None
        self._enabled      = False
        self._thread       = None
        self._lock         = threading.Lock()
        self._alert_cbs    = []
        self._last_alert   = {}   # type -> epoch
        self._alert_log    = []
        self._ankle_hist   = []   # list of {"t", "ly", "ry"} dicts

        if _MP and _CV2:
            try:
                self._pose = _mp_pose.Pose(
                    model_complexity=0,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                self._face = _mp_face_mesh.FaceMesh(
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
            except Exception as e:
                print(f"[POSE] MediaPipe init error: {e}")

    # ── Public API ────────────────────────────────────────────────────────────

    def status(self) -> dict:
        return {
            "available":  _MP and _CV2 and self._pose is not None,
            "mediapipe":  _MP,
            "opencv":     _CV2,
            "monitoring": self._enabled,
        }

    def add_alert_callback(self, fn):
        self._alert_cbs.append(fn)

    def start(self, camera_index: int = 0) -> dict:
        if not (_CV2 and _MP and self._pose):
            return {"success": False, "error": "MediaPipe or OpenCV not available."}
        if self._enabled:
            return {"success": True, "message": "Already running."}
        self._enabled = True
        self._thread = threading.Thread(
            target=self._run_loop, args=(camera_index,), daemon=True
        )
        self._thread.start()
        return {"success": True, "message": "Pose analysis started."}

    def stop(self) -> dict:
        self._enabled = False
        with self._lock:
            self._ankle_hist.clear()
        return {"success": True, "message": "Pose analysis stopped."}

    def get_alerts(self, clear: bool = True) -> list:
        with self._lock:
            out = list(self._alert_log)
            if clear:
                self._alert_log.clear()
        return out

    def analyze_frame(self, image_b64: str) -> dict:
        """One-shot analysis of a single base64-encoded JPEG frame."""
        if not _CV2:
            return {"error": "OpenCV not available."}
        if not (_MP and self._pose):
            return {"error": "MediaPipe not available."}
        frame = _decode_frame(image_b64)
        if frame is None:
            return {"error": "Could not decode image."}
        return self._analyze(frame)

    # ── Core analysis ────────────────────────────────────────────────────────

    def _analyze(self, frame) -> dict:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = frame.shape[:2]
        result = {
            "distress_pose": None,
            "stroke_risk":   None,
            "gait_analysis": None,
            "alerts":        [],
        }

        # 1. Pose landmarks → distress pose + gait
        pose_out = self._pose.process(rgb)
        if pose_out.pose_landmarks:
            lm = pose_out.pose_landmarks.landmark
            result["distress_pose"] = self._check_distress_pose(lm)
            result["gait_analysis"] = self._check_gait(lm)

        # 2. Face mesh → stroke FAST test
        face_out = self._face.process(rgb)
        if face_out.multi_face_landmarks:
            result["stroke_risk"] = self._check_stroke(
                face_out.multi_face_landmarks[0]
            )

        # 3. Aggregate alerts
        dp = result["distress_pose"]
        if dp and dp.get("detected"):
            result["alerts"].append({
                "type":      "distress_pose",
                "severity":  dp.get("severity", "moderate"),
                "detail":    dp.get("description", ""),
                "timestamp": datetime.now().isoformat(),
            })

        sr = result["stroke_risk"]
        if sr and sr.get("fast_positive"):
            result["alerts"].append({
                "type":      "stroke_indicator",
                "severity":  "critical",
                "detail":    sr.get("description", ""),
                "timestamp": datetime.now().isoformat(),
            })

        ga = result["gait_analysis"]
        if ga and ga.get("fall_risk"):
            result["alerts"].append({
                "type":      "gait_abnormality",
                "severity":  "moderate",
                "detail":    ga.get("description", ""),
                "timestamp": datetime.now().isoformat(),
            })

        return result

    # ── Distress pose ────────────────────────────────────────────────────────

    def _check_distress_pose(self, lm) -> dict:
        """
        Detect clinically meaningful pain postures.

        Rules (all in normalised 0-1 coordinates):
          - Chest clutching  : wrist Y within 0.12 of chest midpoint AND
                               wrist X within 0.25 of shoulder midpoint.
          - Abdominal guard  : wrist near abdomen region (between chest & hips).
          - Body lean        : lateral shoulder/hip tilt > 0.08 AND
                               horizontal body displacement > 0.15.

        Corner cases:
          - Occluded landmark (visibility < 0.3) → skip that check.
          - Both wrists at chest simultaneously → severity escalated to critical.
        """
        lw = lm[_PL.LEFT_WRIST];   rw = lm[_PL.RIGHT_WRIST]
        ls = lm[_PL.LEFT_SHOULDER]; rs = lm[_PL.RIGHT_SHOULDER]
        lh = lm[_PL.LEFT_HIP];     rh = lm[_PL.RIGHT_HIP]

        smy  = (ls.y + rs.y) / 2;   smx = (ls.x + rs.x) / 2
        hmy  = (lh.y + rh.y) / 2;   hmx = (lh.x + rh.x) / 2
        chest_y   = (smy + hmy) / 2
        abdomen_y = hmy - (hmy - smy) * 0.3

        def wrist_near(wrist, cy, cx_ref, y_margin=0.12, x_margin=0.25):
            if wrist.visibility < 0.30:
                return False
            return abs(wrist.y - cy) < y_margin and abs(wrist.x - cx_ref) < x_margin

        lw_chest = wrist_near(lw, chest_y, smx)
        rw_chest = wrist_near(rw, chest_y, smx)
        lw_abd   = wrist_near(lw, abdomen_y, hmx)
        rw_abd   = wrist_near(rw, abdomen_y, hmx)

        shoulder_tilt = abs(ls.y - rs.y)
        hip_tilt      = abs(lh.y - rh.y)
        body_lean     = abs(smx - hmx) > 0.15

        if lw_chest and rw_chest:
            return {
                "detected": True, "severity": "critical",
                "type": "bilateral_chest_clutching",
                "description": (
                    "Both hands on chest — BILATERAL chest clutching detected. "
                    "Possible cardiac event. Escalate to Level 1 triage immediately."
                ),
                "triage_escalation": True,
            }
        if lw_chest or rw_chest:
            return {
                "detected": True, "severity": "critical",
                "type": "chest_clutching",
                "description": (
                    "Patient clutching chest — possible cardiac distress. "
                    "Level 1 triage indicator."
                ),
                "triage_escalation": True,
            }
        if lw_abd or rw_abd:
            return {
                "detected": True, "severity": "urgent",
                "type": "abdominal_guarding",
                "description": (
                    "Abdominal guarding posture detected — possible acute abdominal pain."
                ),
                "triage_escalation": False,
            }
        if body_lean and (shoulder_tilt > 0.08 or hip_tilt > 0.08):
            return {
                "detected": True, "severity": "moderate",
                "type": "body_lean",
                "description": (
                    "Patient leaning heavily to one side — possible pain, weakness, "
                    "or balance impairment."
                ),
                "triage_escalation": False,
            }
        return {"detected": False, "type": "normal", "description": "Normal posture."}

    # ── Stroke FAST test ─────────────────────────────────────────────────────

    def _check_stroke(self, face_landmarks) -> dict:
        """
        Facial asymmetry via FAST (Face, Arms, Speech, Time) — Face component.

        MediaPipe Face Mesh landmark indices used:
          Mouth corners : 61 (left), 291 (right)
          Eye outer     : 33 (left), 263 (right)
          Brow peaks    : 70 (left), 300 (right)

        Asymmetry score = weighted Y-difference across three facial feature pairs.
        Threshold 0.040 for positive (derived from clinical literature on
        camera-based stroke screening precision).

        Corner case: if fewer than 400 landmarks returned (low-quality detection),
        the function returns inconclusive rather than a false positive.
        """
        lm = face_landmarks.landmark
        if len(lm) < 400:
            return {"asymmetry_score": 0.0, "fast_positive": False,
                    "description": "Insufficient landmark quality for FAST assessment."}
        try:
            ml = lm[61];  mr = lm[291]   # mouth corners
            el = lm[33];  er = lm[263]   # eye outer corners
            bl = lm[70];  br = lm[300]   # brow peaks

            mouth_asym = abs(ml.y - mr.y)
            eye_asym   = abs(el.y - er.y)
            brow_asym  = abs(bl.y - br.y)

            score = mouth_asym * 0.55 + eye_asym * 0.28 + brow_asym * 0.17
            droop_side = None
            if abs(ml.y - mr.y) > 0.025:
                droop_side = "left" if ml.y > mr.y else "right"

            if score > 0.040 or droop_side:
                side_str = f"{droop_side.title()}-side drooping. " if droop_side else ""
                desc = (
                    f"Significant facial asymmetry (score {score:.3f}). {side_str}"
                    "FAST stroke test POSITIVE — recommend immediate Level 1 triage "
                    "and neurological assessment."
                )
                severity = "critical"
            elif score > 0.025:
                desc = (
                    f"Mild facial asymmetry (score {score:.3f}). "
                    "Monitor for additional stroke signs."
                )
                severity = "moderate"
            else:
                desc = "No significant facial asymmetry detected."
                severity = "low"

            return {
                "asymmetry_score": round(score, 4),
                "mouth_droop":     droop_side is not None,
                "droop_side":      droop_side,
                "severity":        severity,
                "fast_positive":   score > 0.040 or droop_side is not None,
                "description":     desc,
            }
        except (IndexError, AttributeError) as e:
            return {"asymmetry_score": 0.0, "fast_positive": False,
                    "error": str(e)}

    # ── Gait analysis ────────────────────────────────────────────────────────

    def _check_gait(self, lm) -> dict:
        """
        Multi-frame gait analysis using ankle Y-trajectory.

        Detects:
          - Limp     : left/right step-height range asymmetry > 35 %
          - Unsteady : high standard deviation in ankle Y (erratic movement)

        Corner case: both ankles must have visibility > 0.3 for the frame to
        be included in history (occluded ankles would corrupt the range calc).
        """
        la = lm[_PL.LEFT_ANKLE];  ra = lm[_PL.RIGHT_ANKLE]
        now = time.time()

        # Only include high-visibility ankle frames
        if la.visibility > 0.30 and ra.visibility > 0.30:
            with self._lock:
                self._ankle_hist.append({"t": now, "ly": la.y, "ry": ra.y})
                # Keep only the recent time window
                cutoff = now - self.GAIT_WINDOW_S
                self._ankle_hist = [e for e in self._ankle_hist if e["t"] > cutoff]
                hist = list(self._ankle_hist)
        else:
            with self._lock:
                hist = list(self._ankle_hist)

        if len(hist) < self.GAIT_MIN_FRAMES:
            return {
                "status": "collecting_data",
                "frames_collected": len(hist),
                "frames_needed": self.GAIT_MIN_FRAMES,
            }

        lys = [e["ly"] for e in hist]
        rys = [e["ry"] for e in hist]
        l_range = max(lys) - min(lys)
        r_range = max(rys) - min(rys)
        max_range = max(l_range, r_range, 1e-6)
        asym = abs(l_range - r_range) / max_range

        l_std = float(np.std(lys));  r_std = float(np.std(rys))
        unsteady = max(l_std, r_std) > 0.040

        limp = asym > 0.35

        if limp:
            side = "left" if l_range < r_range else "right"
            desc = (
                f"Limp detected ({side} side — {asym:.0%} step asymmetry). "
                "High fall risk. Consider orthopaedic or neurological assessment."
            )
        elif unsteady:
            desc = (
                "Unsteady gait — elevated fall risk. "
                "Consider neurological or vestibular assessment."
            )
        else:
            desc = "Normal gait pattern."

        return {
            "limp_detected":   limp,
            "unsteadiness":    unsteady,
            "step_asymmetry":  round(asym, 3),
            "l_step_range":    round(l_range, 3),
            "r_step_range":    round(r_range, 3),
            "fall_risk":       limp or unsteady,
            "description":     desc,
        }

    # ── Background loop ──────────────────────────────────────────────────────

    def _run_loop(self, camera_index: int):
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            cap = cv2.VideoCapture(_CAMERA_URL)
        if not cap.isOpened():
            print("[POSE] Cannot open camera — pose analysis disabled.")
            self._enabled = False
            return

        while self._enabled:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.2)
                continue
            try:
                result = self._analyze(frame)
                for alert in result.get("alerts", []):
                    self._fire_alert(alert)
            except Exception as e:
                print(f"[POSE] Frame error: {e}")
            time.sleep(0.10)   # ~10 FPS

        cap.release()

    def _fire_alert(self, alert: dict):
        """Rate-limited alert dispatch."""
        atype = alert.get("type", "unknown")
        now   = time.time()
        if now - self._last_alert.get(atype, 0) < self.ALERT_COOLDOWN:
            return
        self._last_alert[atype] = now
        with self._lock:
            self._alert_log.append(alert)
        print(f"[POSE ALERT] {alert.get('severity','?').upper()}: {alert.get('detail','')}")
        for fn in self._alert_cbs:
            try:
                fn(alert)
            except Exception as e:
                print(f"[POSE] Callback error: {e}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _decode_frame(image_b64: str):
    """Decode a data-URI or raw base64 string to an OpenCV BGR frame."""
    if not _CV2:
        return None
    try:
        raw  = base64.b64decode(image_b64.split(",")[-1])
        arr  = np.frombuffer(raw, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None
