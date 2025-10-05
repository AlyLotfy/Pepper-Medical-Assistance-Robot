import json, time
from ws4py.client.threadedclient import WebSocketClient
from naoqi import ALProxy
import ConfigParser

cfg = ConfigParser.ConfigParser()
cfg.read("config.ini")
ROBOT_IP = cfg.get("pepper","ip")
PORT     = int(cfg.get("pepper","port"))

tts = ALProxy("ALTextToSpeech", ROBOT_IP, PORT)
tab = ALProxy("ALTabletService", ROBOT_IP, PORT)

class Bridge(WebSocketClient):
    def received_message(self, m):
        msg = json.loads(str(m))
        if msg["type"] == "tts":
            tts.say(msg["text"])
        elif msg["type"] == "tablet":
            tab.showWebview(msg["url"])
        elif msg["type"] == "alert":
            tts.say("Urgent case! Please call a nurse.")

if __name__ == "__main__":
    ws = Bridge(cfg.get("pepper","server").replace("http","ws")+"/ws/robot")
    ws.connect()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        ws.close()
