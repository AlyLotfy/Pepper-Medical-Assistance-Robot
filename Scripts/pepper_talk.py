# -*- coding: utf-8 -*-
# Simple script to make Pepper speak using NAOqi SDK
# Compatible with Python 2.7

from naoqi import ALProxy

# ---- CONFIG ----
ROBOT_IP = "1.1.1.10"   # Pepper's IP address
PORT = 9559              # Default NAOqi port
# ----------------

def main():
    try:
        # Create a proxy to Pepper's Text-to-Speech module
        tts = ALProxy("ALTextToSpeech", ROBOT_IP, PORT)

        # Make Pepper talk
        tts.say("Hello, I am Pepper. Connection successful!")

        print("✅ Pepper spoke successfully!")

    except Exception as e:
        print("❌ Could not connect to Pepper:")
        print(str(e))

if __name__ == "__main__":
    main()
