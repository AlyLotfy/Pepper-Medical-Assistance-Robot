import sys
import os
import cv2
import numpy as np
import pkg_resources
import subprocess
import threading
import time

sys.path.append(pkg_resources.resource_filename("ciircgym", "yolact_vision"))
#sys.path.append(pkg_resources.resource_filename("ciircgym", "pepper_controller"))

from inference_tool import InfTool

isFinished = False
last_hand_announcement_time = 0
ANNOUNCEMENT_COOLDOWN = 5  # seconds between hand-raising announcements

def streamPepperCamera():
    subprocess.run(["python2", fileName, '--speak_constantly=True'])
    global isFinished
    isFinished = True

def announce_raised_hands(num_hands):
    """
    Announce the number of raised hands using Pepper's text-to-speech.
    In this simplified version, we just print the announcement.
    """
    global last_hand_announcement_time
    current_time = time.time()
    
    # Only announce if enough time has passed since the last announcement
    if current_time - last_hand_announcement_time >= ANNOUNCEMENT_COOLDOWN:
        if num_hands == 1:
            message = "I see 1 person with a raised hand."
        else:
            message = f"I see {num_hands} people with raised hands."
        
        print(f"PEPPER SAYS: {message}")
        # In a real implementation, this would call Pepper's TTS:
        # tts.say(message)
        
        last_hand_announcement_time = current_time

def clean(image):
    if os.path.exists(image):
        os.remove(image)

if __name__ == "__main__":
    fileDir = os.path.dirname(os.path.realpath('__file__'))
    fileName = os.path.join(fileDir, "yolactDemo.py")
    fileName = os.path.abspath(os.path.realpath(fileName))
    name = "camera.jpg"
    
    try:
        # Initialize the pose detector
        print("Initializing pose detector...")
        detector = InfTool(score_threshold=0.35)
        
        # Create a test image if it doesn't exist
        if not os.path.exists(name):
            print(f"Creating test image {name}")
            test_img = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(test_img, "Test Image", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.imwrite(name, test_img)
        
        pepperThread = threading.Thread(target=streamPepperCamera)
        pepperThread.start()
        
        while not isFinished:
            img = cv2.imread(name)
            if img is None:
                print(f"Warning: Could not read image {name}, creating a test image")
                test_img = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(test_img, "Test Image", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                cv2.imwrite(name, test_img)
                img = test_img
            
            # Hand-raising detection
            num_hands, hand_ids, _ = detector.detect_raised_hands(img)
            
            # Announce raised hands if any are detected
            if num_hands > 0:
                announce_raised_hands(num_hands)
            
            # Display image with pose detection and hand-raising indicators
            img_numpy = detector.label_image(img)
            cv2.imshow('Pepper Hand Detection', img_numpy)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
        
        clean(name)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()