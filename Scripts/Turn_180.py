from naoqi import ALProxy

PEPPER_IP = "192.168.1.15"   # ← replace with your robot's IP
PORT = 9559

motion = ALProxy("ALMotion", PEPPER_IP, PORT)
posture = ALProxy("ALRobotPosture", PEPPER_IP, PORT)

# Wake up and stand
motion.wakeUp()
posture.goToPosture("StandInit", 0.8)

# Turn 180 degrees (π radians)
motion.moveTo(0, 0, 3.14)

# Optional: return to sitting
posture.goToPosture("Sit", 0.8)
motion.rest()
