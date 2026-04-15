# -*- coding: utf-8 -*-
import qi
import time

PEPPER_IP = "1.1.1.10"
PEPPER_PORT = 9559
URL = "http://1.1.1.240:8080/?v=1"

session = qi.Session()
session.connect("tcp://{}:{}".format(PEPPER_IP, PEPPER_PORT))

tablet = session.service("ALTabletService")

tablet.resetTablet()      # ✅ correct cache reset
time.sleep(2)

tablet.loadUrl(URL)
tablet.showWebview()

print("Tablet cache cleared and UI reloaded.")
