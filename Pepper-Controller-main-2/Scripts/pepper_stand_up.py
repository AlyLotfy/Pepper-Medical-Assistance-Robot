# -*- coding: utf-8 -*-
# Make Pepper stand up using NAOqi SDK
# Python 2.7 compatible

from naoqi import ALProxy

# ---- CONFIG ----
ROBOT_IP = "1.1.1.10"   # Pepper's IP
PORT = 9559
# ----------------

def main():
    try:
        # Connect to motion and posture modules
        motion = ALProxy("ALMotion", ROBOT_IP, PORT)
        posture = ALProxy("ALRobotPosture", ROBOT_IP, PORT)

        # Wake up motors (activate stiffness)
        motion.wakeUp()

        # Ask Pepper to go to "Stand" posture
        print("🦾 Making Pepper stand up...")
        posture.goToPosture("Stand", 0.6)  # 0.6 = speed fraction (safe & smooth)

        print("✅ Pepper is now standing!")

    except Exception as e:
        print("❌ Could not make Pepper stand:")
        print(str(e))

if __name__ == "__main__":
    main()
