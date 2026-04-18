# -*- coding: utf-8 -*-
# Control Pepper's arm using NAOqi
# Python 2.7 compatible

from naoqi import ALProxy
import time

# ---- CONFIG ----
ROBOT_IP = "1.1.1.10"   # Pepper's IP
PORT = 9559
# ----------------

def main():
    try:
        # Create a motion proxy
        motion = ALProxy("ALMotion", ROBOT_IP, PORT)

        # Wake up Pepper (if it’s in rest mode)
        motion.wakeUp()

        # List of available joints (for reference)
        # Right arm: RShoulderPitch, RShoulderRoll, RElbowYaw, RElbowRoll, RWristYaw
        # Left arm:  LShoulderPitch, LShoulderRoll, LElbowYaw, LElbowRoll, LWristYaw

        # Move the right arm up
        print("➡️ Moving right arm up...")
        motion.setAngles("RShoulderPitch", 0.5, 0.2)  # smaller angle = arm higher
        motion.setAngles("RShoulderRoll", -0.2, 0.2)
        time.sleep(2)

        # Bend elbow slightly
        print("➡️ Bending elbow...")
        motion.setAngles("RElbowRoll", 1.0, 0.2)
        time.sleep(2)

        # Move arm back down
        print("⬇️ Moving arm back down...")
        motion.setAngles("RShoulderPitch", 1.5, 0.2)
        motion.setAngles("RElbowRoll", 0.5, 0.2)
        time.sleep(2)

        # Return Pepper to rest
        print("💤 Returning to rest...")
        motion.rest()

        print("✅ Motion sequence completed!")

    except Exception as e:
        print("❌ Could not control Pepper:")
        print(str(e))

if __name__ == "__main__":
    main()
