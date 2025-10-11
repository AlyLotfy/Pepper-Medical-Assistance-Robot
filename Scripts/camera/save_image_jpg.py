# -*- coding: utf-8 -*-
from PIL import Image
import StringIO

def save_jpg(raw_file):
    """Convert raw Pepper RGB bytes into a JPEG file."""
    try:
        # Read raw RGB data
        with open(raw_file, "rb") as f:
            data = f.read()

        # Pepper’s camera outputs 640x480 RGB images
        width, height = 640, 480

        # Create and save image
        img = Image.frombytes("RGB", (width, height), data)
        img.save("pepper_frame.jpg", "JPEG")
        print("✅  Image saved as pepper_frame.jpg")

    except Exception as e:
        print("❌  Error:", e)

if __name__ == "__main__":
    save_jpg("pepper_image_data.txt")
