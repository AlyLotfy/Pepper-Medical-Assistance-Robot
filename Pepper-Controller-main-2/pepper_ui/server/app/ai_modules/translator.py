# -*- coding: utf-8 -*-
"""
translator.py - Arabic <-> English Medical Translation
=======================================================
TIER 1 (fully offline): argostranslate (if installed + language packages downloaded)
TIER 2 (online):        Claude API
TIER 3 (no internet):   Returns {"success": False, "source": "no_internet",
                                  "error": "No internet connection. Translation unavailable."}

Install argostranslate for offline use:
    pip install argostranslate
    python -c "
    import argostranslate.package, argostranslate.translate
    argostranslate.package.update_package_index()
    pkgs = argostranslate.package.get_available_packages()
    for p in pkgs:
        if (p.from_code in ('en','ar') and p.to_code in ('en','ar')):
            p.install()
    "
"""
import os
import requests

_ARGOS = False
try:
    import argostranslate.package
    import argostranslate.translate
    _ARGOS = True
except ImportError:
    pass


class Translator:
    """
    Translates between Arabic and English.
    Auto-selects best available backend; always returns a standard dict.
    """

    def __init__(self):
        self.api_key    = os.environ.get("CLAUDE_API_KEY", "")
        self.model      = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        self.claude_url = "https://api.anthropic.com/v1/messages"
        self.offline    = os.environ.get("OFFLINE_MODE", "0") == "1"
        self._en_ar     = None
        self._ar_en     = None
        self._argos_ok  = False
        if _ARGOS:
            self._init_argos()

    # ------------------------------------------------------------------
    def translate(self, text: str, from_lang: str, to_lang: str) -> dict:
        """
        Translate text.
        from_lang / to_lang: "en" or "ar"
        Returns:
          {
            "translated": str,
            "success": bool,
            "source": "argos" | "claude" | "no_internet" | "passthrough",
            "error": str (only on failure)
          }
        """
        if not text or not text.strip():
            return {"translated": text or "", "success": True, "source": "passthrough"}
        if from_lang == to_lang:
            return {"translated": text, "success": True, "source": "passthrough"}

        # 1. Argostranslate (offline)
        if _ARGOS and self._argos_ok:
            result = self._argos_translate(text, from_lang, to_lang)
            if result is not None:
                return {"translated": result, "success": True, "source": "argos"}

        # 2. Offline mode with no argos
        if self.offline:
            return {
                "translated": "",
                "success": False,
                "source": "no_internet",
                "error": (
                    "Offline translation requires argostranslate. "
                    "Install it with: pip install argostranslate"
                ),
            }

        # 3. Check internet
        if not self._is_online():
            return {
                "translated": "",
                "success": False,
                "source": "no_internet",
                "error": "No internet connection. Translation is currently unavailable.",
            }

        # 4. Claude API
        result = self._claude_translate(text, from_lang, to_lang)
        if result is not None:
            return {"translated": result, "success": True, "source": "claude"}

        return {
            "translated": "",
            "success": False,
            "source": "error",
            "error": "Translation failed. Please try again.",
        }

    def status(self) -> dict:
        return {
            "argostranslate_installed": _ARGOS,
            "argostranslate_loaded":    self._argos_ok,
            "en_ar_package":            self._en_ar is not None,
            "ar_en_package":            self._ar_en is not None,
            "claude_key_set":           bool(self.api_key),
            "offline_mode":             self.offline,
        }

    # ------------------------------------------------------------------
    def _init_argos(self):
        try:
            installed = argostranslate.package.get_installed_packages()
            pkg_map   = {(p.from_code, p.to_code): p for p in installed}
            self._en_ar = pkg_map.get(("en", "ar"))
            self._ar_en = pkg_map.get(("ar", "en"))
            self._argos_ok = bool(self._en_ar or self._ar_en)
            if self._argos_ok:
                print(f"[TRANSLATE] Argostranslate loaded. "
                      f"en→ar: {bool(self._en_ar)}, ar→en: {bool(self._ar_en)}")
        except Exception as e:
            print(f"[TRANSLATE] Argostranslate init error: {e}")

    def _argos_translate(self, text, from_lang, to_lang):
        try:
            return argostranslate.translate.translate(text, from_lang, to_lang)
        except Exception as e:
            print(f"[TRANSLATE] Argos error: {e}")
            return None

    def _claude_translate(self, text, from_lang, to_lang):
        if not self.api_key:
            return None
        lang_names = {"en": "English", "ar": "Arabic"}
        src  = lang_names.get(from_lang, from_lang)
        tgt  = lang_names.get(to_lang,   to_lang)
        try:
            resp = requests.post(
                self.claude_url,
                headers={"x-api-key": self.api_key,
                         "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={
                    "model": self.model,
                    "max_tokens": 600,
                    "system": (
                        f"You are a medical translator. Translate the given text from {src} to {tgt}. "
                        f"Return ONLY the translation. No explanations, no prefixes."
                    ),
                    "messages": [{"role": "user", "content": text}],
                },
                timeout=15,
            )
            return resp.json()["content"][0]["text"].strip()
        except Exception as e:
            print(f"[TRANSLATE] Claude error: {e}")
            return None

    def _is_online(self):
        try:
            requests.get("https://api.anthropic.com", timeout=3)
            return True
        except Exception:
            return False
