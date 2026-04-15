# -*- coding: utf-8 -*-
"""
face_auth.py - Face Recognition for Auto Login
Uses OpenCV LBPH face recognizer (no external heavy libs needed).
Stores trained model and label map in app/ai_modules/face_data/.
"""
import os
import json
import base64
import numpy as np

try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

FACE_DATA_DIR = os.path.join(os.path.dirname(__file__), "face_data")
MODEL_PATH    = os.path.join(FACE_DATA_DIR, "face_model.xml")
LABELS_PATH   = os.path.join(FACE_DATA_DIR, "labels.json")
CASCADE_PATH  = cv2.data.haarcascades + "haarcascade_frontalface_default.xml" if CV2_OK else ""

os.makedirs(FACE_DATA_DIR, exist_ok=True)


class FaceAuth:
    def __init__(self):
        self.ready = False
        self.recognizer = None
        self.detector   = None
        self.labels     = {}
        self.threshold  = 80

        if not CV2_OK:
            print("[FACE_AUTH] OpenCV not available — face login disabled.")
            return

        if not hasattr(cv2, 'face'):
            print("[FACE_AUTH] cv2.face missing. Install opencv-contrib-python.")
            return

        try:
            self.detector = cv2.CascadeClassifier(CASCADE_PATH)
            self._load_model()
            self.ready = True
        except Exception as e:
            print(f"[FACE_AUTH] Init error: {e}")

    # ------------------------------------------------------------------
    def _load_model(self):
        """Load existing model and labels if available."""
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        if os.path.exists(MODEL_PATH) and os.path.exists(LABELS_PATH):
            self.recognizer.read(MODEL_PATH)
            with open(LABELS_PATH, "r") as f:
                raw = json.load(f)
                self.labels = {int(k): v for k, v in raw.items()}
            print(f"[FACE_AUTH] Loaded model with {len(self.labels)} enrolled patients.")
        else:
            print("[FACE_AUTH] No existing model. Enroll patients to enable face login.")

    def _decode_image(self, image_input):
        """Accept base64 string or raw bytes, return BGR numpy array."""
        if isinstance(image_input, str):
            # Strip data URL prefix if present
            if "," in image_input:
                image_input = image_input.split(",", 1)[1]
            image_bytes = base64.b64decode(image_input)
        else:
            image_bytes = image_input
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    def _get_face(self, image_input):
        """Detect largest face and return grayscale crop, or None."""
        img = self._decode_image(image_input)
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = self.detector.detectMultiScale(gray, scaleFactor=1.1,
                                               minNeighbors=5, minSize=(60, 60))
        if len(faces) == 0:
            return None
        # Use largest face
        x, y, w, h = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)[0]
        face_crop = gray[y:y+h, x:x+w]
        return cv2.resize(face_crop, (200, 200))

    # ------------------------------------------------------------------
    def enroll(self, patient_id, images):
        """
        Enroll a patient with one or more face images (base64 or bytes).
        Returns {"success": bool, "enrolled": int (face count)}
        """
        if not self.ready:
            return {"success": False, "error": "OpenCV not available."}

        patient_id = str(patient_id)
        faces  = []
        labels_list = []

        # Assign numeric label for this patient
        reverse = {v: k for k, v in self.labels.items()}
        if patient_id in reverse:
            label = reverse[patient_id]
        else:
            label = max(self.labels.keys(), default=-1) + 1
            self.labels[label] = patient_id

        for img in (images if isinstance(images, list) else [images]):
            face = self._get_face(img)
            if face is not None:
                faces.append(face)
                labels_list.append(label)

        if not faces:
            return {"success": False, "error": "No face detected in provided images."}

        # Retrain with all existing + new faces (load existing samples first)
        # For simplicity, just update the model with new samples
        self.recognizer.update(faces, np.array(labels_list))
        self.recognizer.save(MODEL_PATH)
        with open(LABELS_PATH, "w") as f:
            json.dump({str(k): v for k, v in self.labels.items()}, f)

        print(f"[FACE_AUTH] Enrolled patient {patient_id} with {len(faces)} face(s).")
        return {"success": True, "enrolled": len(faces), "patient_id": patient_id}

    def recognize(self, image_input):
        """
        Identify a patient from a face image.
        Returns {"success": bool, "patient_id": str, "confidence": float}
        """
        if not self.ready:
            return {"success": False, "error": "OpenCV not available."}
        if not self.labels:
            return {"success": False, "error": "No patients enrolled yet."}

        face = self._get_face(image_input)
        if face is None:
            return {"success": False, "error": "No face detected in image."}

        try:
            label, confidence = self.recognizer.predict(face)
            # LBPH: lower confidence = better match
            if confidence <= self.threshold and label in self.labels:
                patient_id = self.labels[label]
                print(f"[FACE_AUTH] Recognized patient {patient_id} (confidence={confidence:.1f})")
                return {"success": True, "patient_id": patient_id,
                        "confidence": round(float(confidence), 2)}
            else:
                return {"success": False, "error": "Face not recognized.",
                        "confidence": round(float(confidence), 2)}
        except Exception as e:
            print(f"[FACE_AUTH] Recognition error: {e}")
            return {"success": False, "error": str(e)}

    def status(self):
        return {
            "ready": self.ready,
            "enrolled_patients": len(self.labels),
            "model_exists": os.path.exists(MODEL_PATH)
        }
