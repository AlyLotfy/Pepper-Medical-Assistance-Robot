# -*- coding: utf-8 -*-
# Python 2.7 - Tablet WebSocket Bridge
import json
import time
import os
import traceback
from websocket import create_connection
from naoqi import ALProxy

# --- DYNAMIC CONFIGURATION ---
PEPPER_IP = os.environ.get("ROBOT_IP", "127.0.0.1")
PEPPER_PORT = int(os.environ.get("ROBOT_PORT", "9559"))

SERVER_IP = os.environ.get("SERVER_IP", "127.0.0.1")
SERVER_PORT = os.environ.get("SERVER_PORT", "8080")

SERVER_WS = "ws://{}:{}/ws/pepper".format(SERVER_IP, SERVER_PORT)

def open_url_on_tablet(url):
    try:
        tablet = ALProxy('ALTabletService', PEPPER_IP, PEPPER_PORT)
        try:
            tablet.hideWebview()
        except Exception:
            pass
        tablet.loadUrl(url)
        tablet.showWebview()
    except Exception as e:
        print("[ERROR] Failed to open URL on tablet: {}".format(e))

def hide_webview():
    try:
        tablet = ALProxy('ALTabletService', PEPPER_IP, PEPPER_PORT)
        tablet.hideWebview()
    except Exception as e:
        print("[ERROR] Failed to hide webview: {}".format(e))

def run():
    print("[INFO] UI Bridge Starting. Target WS: {}".format(SERVER_WS))
    try:
        tts = ALProxy('ALTextToSpeech', PEPPER_IP, PEPPER_PORT)
        tts.setLanguage("English")
    except Exception:
        tts = None

    while True:
        try:
            ws = create_connection(SERVER_WS)
            ws.send(json.dumps({"type": "hello", "from": "pepper_bridge"}))
            print("[INFO] Connected successfully to server.")
            
            while True:
                msg = ws.recv()
                if not msg:
                    break
                try:
                    data = json.loads(msg)
                except Exception:
                    continue

                mtype = data.get("type", "")
                
                if mtype == "open_url":
                    url = data.get("url", "")
                    if url:
                        print("[INFO] Opening URL: {}".format(url))
                        open_url_on_tablet(url)
                elif mtype == "hide_webview":
                    print("[INFO] Hiding webview.")
                    hide_webview()

                # Keep connection alive
                try:
                    ws.send(json.dumps({"type": "pong"}))
                except Exception:
                    pass
                    
        except KeyboardInterrupt:
            print("\n[INFO] Stopping UI Bridge...")
            break
        except Exception as e:
            print("[WARN] Connection dropped: {}. Retrying in 2s...".format(e))
            time.sleep(2.0)
        finally:
            try:
                ws.close()
            except Exception:
                pass

if __name__ == "__main__":
    run()