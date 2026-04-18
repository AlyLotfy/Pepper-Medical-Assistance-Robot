# bridge.py
# RUN THIS WITH PYTHON 2.7
import qi
import sys
import time
import cv2
import numpy as np
import requests

# --- CONFIGURATION ---
PEPPER_IP = "1.1.1.10"  # CHANGE THIS to Pepper's IP
SERVER_URL = "http://localhost:5001/upload_frame" # Flask Server URL

class PepperCamera:
    def __init__(self, ip):
        self.session = qi.Session()
        try:
            self.session.connect("tcp://" + ip + ":9559")
            print("[INFO] Connected to Pepper at " + ip)
        except RuntimeError:
            print("[ERROR] Could not connect to Pepper! Check IP.")
            sys.exit(1)

        self.video = self.session.service("ALVideoDevice")
        # Resolution 1 = 320x240 (Standard for streaming)
        # ColorSpace 11 = RGB
        # FPS = 15
        self.sub = self.video.subscribeCamera("flask_stream", 0, 1, 11, 15)
        self.running = True

    def start(self):
        print("[INFO] Sending images to Flask Server...")
        while self.running:
            try:
                # 1. Get Image from Robot
                img_raw = self.video.getImageRemote(self.sub)
                
                if img_raw:
                    width = img_raw[0]
                    height = img_raw[1]
                    array = img_raw[6]
                    
                    # 2. Process Image
                    img_data = np.frombuffer(array, dtype=np.uint8)
                    img_data = img_data.reshape((height, width, 3))
                    
                    # RGB (Pepper) -> BGR (OpenCV)
                    frame = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)
                    
                    # 3. Compress to JPEG (Quality 50)
                    ret, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                    
                    if ret:
                        # 4. POST to Flask Server
                        try:
                            requests.post(SERVER_URL, data=jpeg.tobytes(), timeout=0.5)
                        except:
                            pass # Ignore connection errors if server blips
                
                # Throttle slightly (approx 15 FPS)
                time.sleep(0.06)

            except KeyboardInterrupt:
                self.stop()
                break
            except Exception as e:
                print("[WARN] Error: " + str(e))
                time.sleep(1)

    def stop(self):
        self.running = False
        self.video.unsubscribe(self.sub)
        print("[INFO] Camera Unsubscribed.")

if __name__ == "__main__":
    cam = PepperCamera(PEPPER_IP)
    try:
        cam.start()
    except KeyboardInterrupt:
        cam.stop()