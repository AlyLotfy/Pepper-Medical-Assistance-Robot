from fastapi import FastAPI
from pydantic import BaseModel
from rag import ask_faq
from triage import triage_score
from bridge_bus import publish
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount("/", StaticFiles(directory="../pepper_ui", html=True), name="ui")

class SpeakReq(BaseModel):
    text: str

@app.post("/api/speak")
def speak(req: SpeakReq):
    publish({"type":"tts","text":req.text})
    return {"ok": True}

class FAQReq(BaseModel):
    question: str

@app.post("/api/faq/search")
def faq(req: FAQReq):
    return {"answers": ask_faq(req.question)}

class TriageReq(BaseModel):
    answers: dict

@app.post("/api/triage/submit")
def triage(req: TriageReq):
    score, level = triage_score(req.answers)
    if level == "urgent":
        publish({"type":"alert"})
    return {"score": score, "level": level}
