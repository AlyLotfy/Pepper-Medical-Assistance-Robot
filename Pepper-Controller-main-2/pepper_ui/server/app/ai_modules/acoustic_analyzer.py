# -*- coding: utf-8 -*-
"""
acoustic_analyzer.py  —  Acoustic AI & Vocal Biomarkers
========================================================
Analyzes a .wav recording to extract clinical signals beyond speech text:

  1. Cough & breathlessness detection  (ZCR + energy bursts + spectral shape)
  2. Wheeze / stridor detection        (narrow-band tonal content)
  3. Pain & distress estimation        (pitch, jitter, vocal energy patterns)

Runs entirely offline using librosa.  No network required.
"""

import os
import numpy as np

try:
    import librosa
    _LIBROSA = True
except ImportError:
    _LIBROSA = False


class AcousticAnalyzer:
    """
    Extracts vocal biomarkers from a .wav file.

    Return schema of analyze():
    {
      "cough_detected":         bool,
      "cough_score":            float  0-1,
      "wheeze_detected":        bool,
      "breathlessness_score":   float  0-1,
      "pain_score_estimate":    int    0-10  (acoustic proxy),
      "distress_score":         float  0-1,
      "features":               dict   (raw acoustic values),
      "alerts":                 list[str],
      "error":                  str | None,
    }
    """

    def __init__(self):
        self._available = _LIBROSA
        if not _LIBROSA:
            print("[ACOUSTIC] librosa not installed — acoustic analysis disabled. "
                  "Install with: pip install librosa soundfile")

    def status(self) -> dict:
        return {"available": self._available,
                "backend": "librosa" if _LIBROSA else "unavailable"}

    # ── Public API ────────────────────────────────────────────────────────────

    def analyze(self, wav_path: str) -> dict:
        """
        Analyze a WAV file for vocal biomarkers.
        Returns the result dict described in the class docstring.
        Gracefully returns an empty result if librosa is unavailable or the
        file is missing / too short.
        """
        if not self._available:
            return self._empty("librosa not installed")
        if not os.path.exists(wav_path):
            return self._empty(f"File not found: {wav_path}")

        try:
            y, sr = librosa.load(wav_path, sr=22050, mono=True)
        except Exception as e:
            return self._empty(f"Could not load audio: {e}")

        # Corner case: audio too short for meaningful analysis (< 150 ms)
        if len(y) < int(sr * 0.15):
            return self._empty("Audio too short for acoustic analysis")

        try:
            features          = self._extract_features(y, sr)
            cough_score       = self._detect_cough(features)
            wheeze_score      = self._detect_wheeze(features)
            pain_est, distress = self._estimate_pain_distress(features)

            breathlessness = min(1.0,
                wheeze_score * 0.55 + features.get("energy_irregularity", 0.0) * 0.45
            )

            alerts = []
            if cough_score > 0.65:
                alerts.append("Coughing detected — may indicate respiratory condition.")
            if wheeze_score > 0.65:
                alerts.append("Wheeze / stridor detected — possible airway obstruction or asthma.")
            if breathlessness > 0.72:
                alerts.append("Signs of breathlessness in vocal pattern.")
            if pain_est >= 7:
                alerts.append(
                    f"High acoustic pain indicators (~{pain_est}/10). "
                    "Cross-check against patient self-report."
                )
            if distress > 0.70:
                alerts.append("Elevated vocal distress — patient may be in significant discomfort.")

            return {
                "cough_detected":        cough_score > 0.5,
                "cough_score":           round(cough_score, 3),
                "wheeze_detected":       wheeze_score > 0.5,
                "breathlessness_score":  round(breathlessness, 3),
                "pain_score_estimate":   pain_est,
                "distress_score":        round(distress, 3),
                "features":              features,
                "alerts":                alerts,
                "error":                 None,
            }

        except Exception as e:
            print(f"[ACOUSTIC] Analysis error: {e}")
            return self._empty(str(e))

    # ── Feature extraction ───────────────────────────────────────────────────

    def _extract_features(self, y, sr) -> dict:
        f = {}

        # Zero-crossing rate — high in turbulent, noisy sounds (coughs)
        zcr = librosa.feature.zero_crossing_rate(y)[0]
        f["zcr_mean"] = float(np.mean(zcr))
        f["zcr_std"]  = float(np.std(zcr))

        # RMS energy
        rms = librosa.feature.rms(y=y)[0]
        f["rms_mean"] = float(np.mean(rms))
        f["rms_std"]  = float(np.std(rms))
        f["rms_max"]  = float(np.max(rms))
        # Irregular energy → uneven breathing / breathlessness
        f["energy_irregularity"] = float(
            min(1.0, np.std(rms) / (np.mean(rms) + 1e-8))
        )

        # Spectral centroid — indicates dominant frequency region
        sc = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        f["spectral_centroid_mean"] = float(np.mean(sc))

        # Spectral flatness — near 0 for tonal (wheeze), near 1 for noise
        sf = librosa.feature.spectral_flatness(y=y)[0]
        f["spectral_flatness_mean"] = float(np.mean(sf))

        # MFCCs (13 cepstral coefficients) — capture overall vocal timbre
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        f["mfcc_mean"] = [round(float(x), 4) for x in np.mean(mfcc, axis=1)]
        f["mfcc_std"]  = [round(float(x), 4) for x in np.std(mfcc, axis=1)]

        # Fundamental frequency (F0) via pyin — pitch tracking
        # Corner case: pyin can raise on very short clips; wrapped in try/except
        try:
            f0, voiced_flag, _ = librosa.pyin(
                y, fmin=librosa.note_to_hz("C2"),
                fmax=librosa.note_to_hz("C7"), sr=sr, fill_na=0.0
            )
            voiced = f0[voiced_flag > 0] if voiced_flag is not None else f0[f0 > 0]
            if voiced is not None and len(voiced) > 2:
                f["f0_mean"] = float(np.mean(voiced))
                f["f0_std"]  = float(np.std(voiced))
                # Jitter: cycle-to-cycle pitch variation — elevated in pain/stress
                f["jitter"]  = float(
                    np.mean(np.abs(np.diff(voiced))) / (np.mean(voiced) + 1e-8)
                )
            else:
                f["f0_mean"] = 0.0; f["f0_std"] = 0.0; f["jitter"] = 0.0
        except Exception:
            f["f0_mean"] = 0.0; f["f0_std"] = 0.0; f["jitter"] = 0.0

        return f

    # ── Classifiers ──────────────────────────────────────────────────────────

    def _detect_cough(self, f: dict) -> float:
        """
        Cough signature: explosive, turbulent, high-ZCR burst in mid-frequency range.
        Returns confidence 0.0 – 1.0.

        Thresholds are calibrated to avoid normal speech false positives:
          - Normal speech ZCR: 0.05–0.17; cough ZCR: > 0.22
          - Normal speech peak/mean RMS: 3–5 (silence gaps); cough: > 6
          - Speech spectral centroid: 1–3 kHz — so tighten to 1.5–3 kHz
        """
        score = 0.0
        if f["zcr_mean"] > 0.22:  score += 0.25
        if f["zcr_mean"] > 0.30:  score += 0.20
        ratio = f["rms_max"] / (f["rms_mean"] + 1e-8)
        if ratio > 6.0:   score += 0.30
        elif ratio > 4.5: score += 0.15
        sc = f["spectral_centroid_mean"]
        if 1500 < sc < 3000:  score += 0.20
        if f["spectral_flatness_mean"] > 0.15:  score += 0.10
        return min(1.0, score)

    def _detect_wheeze(self, f: dict) -> float:
        """
        Wheeze signature: narrow-band tonal sound, low spectral flatness,
        mid-high centroid, irregular energy from laboured breathing.
        Returns confidence 0.0 – 1.0.

        Voiced speech has flatness 0.001–0.01, so the threshold must be
        tighter than 0.005 to avoid flagging every vowel as a wheeze.
        Energy irregularity > 0.40 is normal for conversational speech
        (pauses/consonants); require > 0.60 for laboured-breathing evidence.
        """
        score = 0.0
        if f["spectral_flatness_mean"] < 0.0015:  score += 0.35
        if f["spectral_flatness_mean"] < 0.0005:  score += 0.20
        sc = f["spectral_centroid_mean"]
        if 400 < sc < 1200:  score += 0.25
        if f["energy_irregularity"] > 0.60:  score += 0.20
        return min(1.0, score)

    def _estimate_pain_distress(self, f: dict):
        """
        Acoustic pain/distress proxy:
          High jitter + elevated pitch + irregular energy → distress.
        Returns (pain_0_to_10, distress_0_to_1).

        Corner cases handled:
          - No voiced frames (f0=0): only energy/zcr signals contribute.
          - Very long recordings: features are already averaged, so no bias.
        """
        d = 0.0
        jitter = f.get("jitter", 0.0)
        if jitter > 0.05:  d += 0.20
        if jitter > 0.10:  d += 0.20

        f0 = f.get("f0_mean", 0.0)
        if f0 > 250:  d += 0.15   # elevated pitch (normal ~120–210 Hz)
        if f0 > 350:  d += 0.15

        # High pitch variance relative to mean
        if f0 > 0:
            coeff_var = f.get("f0_std", 0.0) / (f0 + 1e-8)
            if coeff_var > 0.30:  d += 0.15

        if f["energy_irregularity"] > 0.50:  d += 0.15

        # High ZCR in speech (not just noise) also signals tension
        if f["zcr_mean"] > 0.10:  d += 0.10

        d = min(1.0, d)
        pain_est = round(d * 10)
        return pain_est, d

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _empty(self, error: str = None) -> dict:
        return {
            "cough_detected": False, "cough_score": 0.0,
            "wheeze_detected": False, "breathlessness_score": 0.0,
            "pain_score_estimate": 0, "distress_score": 0.0,
            "features": {}, "alerts": [], "error": error,
        }
