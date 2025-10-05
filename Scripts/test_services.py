# test_services.py  (Python 2.7)
from naoqi import ALProxy
ip, port = "1.1.1.10", 9559
for s in ["ALTextToSpeech","ALMotion","ALTabletService"]:
    try:
        ALProxy(s, ip, port)
        print("[OK]", s)
    except Exception as e:
        print("[X]", s, "-", e)
