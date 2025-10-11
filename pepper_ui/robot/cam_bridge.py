# -*- coding: utf-8 -*-  # Python 2.7
from naoqi import ALProxy
import vision_definitions, base64, json, urllib2

PEPPER_IP   = "192.168.1.XX"     # robot IP (NAOqi)
NAO_PORT    = 9559
BACKEND_URL = "http://<PC_IP>:8000/api/pepper/frame"  # your FastAPI server

def grab_frame():
    v = ALProxy("ALVideoDevice", PEPPER_IP, NAO_PORT)
    sub = v.subscribeCamera("py27_cam", 0, vision_definitions.kVGA,
                            vision_definitions.kRGBColorSpace, 10)
    try:
        img = v.getImageRemote(sub)
        if not img: raise RuntimeError("no frame")
        w, h, data = img[0], img[1], img[6]  # raw RGB bytes
        return w, h, data
    finally:
        v.unsubscribe(sub)

def post_frame(w, h, data):
    payload = {"width": w, "height": h, "data_b64": base64.b64encode(data)}
    req = urllib2.Request(BACKEND_URL, json.dumps(payload),
                          {"Content-Type": "application/json"})
    return urllib2.urlopen(req, timeout=5).read()

if __name__ == "__main__":
    w, h, data = grab_frame()
    print post_frame(w, h, data)
