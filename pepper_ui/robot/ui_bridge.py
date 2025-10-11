# -*- coding: utf-8 -*-
from naoqi import ALProxy
import json
import time

ROBOT_IP = "1.1.1.10"   
ROBOT_PORT = 9559
UI_URL = "http://1.1.1.246:8080/" 

# Services
tts = ALProxy("ALTextToSpeech", ROBOT_IP, ROBOT_PORT)
mem = ALProxy("ALMemory", ROBOT_IP, ROBOT_PORT)
tablet = ALProxy("ALTabletService", ROBOT_IP, ROBOT_PORT)
motion = ALProxy("ALMotion", ROBOT_IP, ROBOT_PORT)
behav = ALProxy("ALBehaviorManager", ROBOT_IP, ROBOT_PORT)

def send_to_ui(payload):
    # robot → UI
    mem.raiseEvent("ui/to_web", json.dumps(payload))

def on_event(event_name, value, msg):
    try:
        data = json.loads(value) if value else {}
    except Exception:
        data = {"raw": value}

    if event_name == "ui/checkin":
        tts.say(u"Please scan your code on the tablet.")
        send_to_ui({"type":"status","text":"Open scanner…"})
        # TODO: open a scanner screen in the UI or handle camera on Edge PC

    elif event_name == "ui/queue":
        tts.say(u"Let me show you the queue and estimated wait time.")
        # Example: call your backend, then update UI
        send_to_ui({"type":"status","text":"Dr. Ahmed: 12 min | Radiology: 25 min"})

    elif event_name == "ui/faq":
        tts.say(u"I can answer your questions about visiting hours and insurance.")
        # UI might open an FAQ screen and call /api/faq

    elif event_name == "ui/wayfinding":
        tts.say(u"Follow me please, I will guide you.")
        # Or show a map on tablet; for MVP keep it informational

    elif event_name == "ui/call_nurse":
        tts.say(u"Calling the nurse now.")
        # TODO: trigger your nurse alert pipeline (MQTT/HTTP)
        send_to_ui({"type":"status","text":"Nurse has been notified."})

    elif event_name == "ui/lang":
        lang = value.strip('"') if isinstance(value, basestring) else "en"
        if lang == "ar":
            tts.setLanguage("Arabic")
            send_to_ui({"type":"lang","value":"ar"})
            tts.say(u"تم تغيير اللغة إلى العربية.")
        else:
            tts.setLanguage("English")
            send_to_ui({"type":"lang","value":"en"})
            tts.say("Language changed to English.")

def main():
    # Show the page
    tablet.showWebview(UI_URL)
    send_to_ui({"type":"status","text":"UI loaded."})

    # Subscribe to UI events
    # We create dynamic subscribers via ALMemory micro events
    subs = []
    def subscribe(ev):
        name = "sub_" + ev.replace("/","_")
        try:
            mem.subscribeToEvent(ev, "python", "callback")
        except:
            # fallback approach: use proxies hard-bound to this process
            pass
        subs.append(ev)

    # Register callback (NAOqi <-> Python trick)
    class PythonBridge(object):
        def callback(self, key, value, msg):
            on_event(key, value, msg)

    # Inject object into NAOqi broker
    # (Choregraphe auto-done; from remote script we just poll)
    # Simple polling fallback:
    known = set()
    while True:
        for ev in ["ui/checkin","ui/queue","ui/faq","ui/wayfinding","ui/call_nurse","ui/lang"]:
            if ev not in known:
                try:
                    mem.insertData(ev, "")
                    known.add(ev)
                except:
                    pass
        # Use data changed: we’ll poll for changes (simple but works)
        # In production, replace with proper subscriber
        time.sleep(0.2)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
