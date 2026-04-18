import os
import requests
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import aiofiles
import whisper

# === Load environment variables ===
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_MODEL   = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

print("[INFO] Claude API key loaded.")

# === Initialize FastAPI app and Whisper model ===
app = FastAPI()
model = whisper.load_model("small.en")

SYSTEM_PROMPT = "You are Pepper, a medical robot assistant at Andalusia Hospital. Keep answers short and helpful (under 40 words)."

# === Claude Request Function ===
def ask_claude(prompt: str) -> str:
    """Send user text to Claude Haiku and return its reply."""
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 200,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=20)
        data = r.json()
        print("[DEBUG] Claude response:", data)

        if "content" in data and len(data["content"]) > 0:
            return data["content"][0]["text"]
        elif "error" in data:
            err_msg = data["error"].get("message", "Unknown error")
            print("[ERROR] Claude API returned:", err_msg)
            return "Sorry, I could not process that request."
        else:
            print("[ERROR] Unexpected Claude response structure.")
            return "Sorry, I received an unexpected response."

    except Exception as e:
        print("[EXCEPTION] Claude request failed:", e)
        return "Sorry, I could not reach the AI server."

# === Voice endpoint ===
@app.post("/api/voice")
async def process_audio(file: UploadFile = File(...)):
    """Receive voice file, transcribe it with Whisper, and ask Claude."""
    tmp = "temp.wav"

    async with aiofiles.open(tmp, "wb") as f:
        await f.write(await file.read())

    try:
        text = model.transcribe(tmp)["text"].strip()
        print("[USER]:", text)
    except Exception as e:
        print("[ERROR] Whisper failed:", e)
        return JSONResponse({"reply": "Sorry, I couldn't understand the audio."})

    reply = ask_claude(text)
    print("[CLAUDE]:", reply)

    return JSONResponse({"text": text, "reply": reply})
