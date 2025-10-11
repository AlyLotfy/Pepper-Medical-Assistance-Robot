from naoqi import ALProxy

# Replace with your Pepper's IP address
PEPPER_IP = "1.1.1.10"
PORT = 9559

# Create motion proxy
motion = ALProxy("ALMotion", PEPPER_IP, PORT)
posture = ALProxy("ALRobotPosture", PEPPER_IP, PORT)

# Wake up Pepper
motion.wakeUp()

# Stand up
posture.goToPosture("StandInit", 0.8)

# Move forward 0.3 m
motion.moveTo(0.3, 0, 0)

# Turn left 90 degrees (1.57 rad)
motion.moveTo(0, 0, 1.57)

