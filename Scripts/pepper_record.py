# -*- coding: utf-8 -*-
# Capture video from Pepper's camera and save to a file
# Works with Python 2.7 and NAOqi SDK

from naoqi import ALProxy
import numpy as np
import cv2
import time

# ---- CONFIG ----
ROBOT_IP = "1.1.1.10"   # Pepper's IP address
PORT = 9559
CAMERA_ID = 0            # 0 = top camera, 1 = bottom
RESOLUTION = 2           # 2 = 640x480
COLORSPACE = 11          # 11 = RGB
FPS = 10                 # frames per second
DURATION = 10            # seconds to record
OUTPUT_FILE = "pepper_video.avi"
# -----------------

def main():
    try:
        # Connect to Pepper's video device
        videoProxy = ALProxy("ALVideoDevice", ROBOT_IP, PORT)
        subscriber = videoProxy.subscribeCamera(
            "python_client", CAMERA_ID, RESOLUTION, COLORSPACE, FPS)

        # Video writer
        frame_width, frame_height = 640, 480
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(OUTPUT_FILE, fourcc, FPS, (frame_width, frame_height))

        print("🎥 Recording video from Pepper...")
        start_time = time.time()

        while (time.time() - start_time) < DURATION:
            img = videoProxy.getImageRemote(subscriber)
            if img is None:
                continue

            width, height, array = img[0], img[1], img[6]
            frame = np.frombuffer(array, dtype=np.uint8).reshape((height, width, 3))

            # Write frame to file
            out.write(frame)

        print("✅ Video saved as '{}'".format(OUTPUT_FILE))

        # Cleanup
        videoProxy.unsubscribe(subscriber)
        out.release()

    except Exception as e:
        print("❌ Error capturing video:")
        print(str(e))

if __name__ == "__main__":
    main()
