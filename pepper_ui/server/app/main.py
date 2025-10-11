# Python 3.x (FastAPI)
from fastapi import FastAPI
from pydantic import BaseModel
import base64
from PIL import Image
from io import BytesIO
from datetime import datetime
import os

app = FastAPI()

class FrameIn(BaseModel):
    width: int
    height: int
    data_b64: str

@app.post("/api/pepper/frame")
def receive_frame(f: FrameIn):
    raw = base64.b64decode(f.data_b64)
    img = Image.frombytes("RGB", (f.width, f.height), raw)
    os.makedirs("frames", exist_ok=True)
    out = "frames/pepper_%s.jpg" % datetime.now().strftime("%Y%m%d_%H%M%S")
    img.save(out, "JPEG", quality=90)
    return {"ok": True, "saved": out}
