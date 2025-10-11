# -*- coding: utf-8 -*-
from naoqi import ALProxy
import vision_definitions
import time
import base64

PEPPER_IP = "1.1.1.10"  # Replace with your Pepper’s actual IP
PORT = 9559

def capture_image():
    """Capture one frame from Pepper’s top camera and save as JPEG."""
    video_proxy = ALProxy("ALVideoDevice", PEPPER_IP, PORT)

    # Subscribe to the top camera (camera 0)
    resolution = vision_definitions.kVGA        # 640x480
    color_space = vision_definitions.kRGBColorSpace
    fps = 10
    name_id = video_proxy.subscribeCamera("python_client", 0, resolution, color_space, fps)

    # Grab one image frame
    image = video_proxy.getImageRemote(name_id)
    video_proxy.unsubscribe(name_id)

    if image is None:
        print("❌  Could not capture image from Pepper.")
        return None

    width, height = image[0], image[1]
    array = image[6]

    # Save to a temporary file for the next script
    filename = "pepper_image_data.txt"
    with open(filename, "wb") as f:
        f.write(array)
    print("✅  Raw image data saved to", filename)
    return filename

if __name__ == "__main__":
    capture_image()
