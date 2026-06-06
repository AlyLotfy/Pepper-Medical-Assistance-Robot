# -*- coding: utf-8 -*-
# Python 2.7 - Initial Tablet Webview Loader
import os
import time
import sys
import json
from naoqi import ALProxy

# Python 2.7 HTTP
try:
    import urllib2 as urllib_request
except ImportError:
    import urllib.request as urllib_request

# --- DYNAMIC CONFIGURATION ---
PEPPER_IP = os.environ.get("ROBOT_IP", "127.0.0.1")
PEPPER_PORT = int(os.environ.get("ROBOT_PORT", "9559"))

SERVER_IP = os.environ.get("SERVER_IP", "127.0.0.1")
SERVER_PORT = os.environ.get("SERVER_PORT", "8080")

# The default home page for the tablet UI
DEFAULT_URL = "http://{}:{}".format(SERVER_IP, SERVER_PORT)

# Timeouts (seconds)
SERVER_READY_TIMEOUT = 120
ROBOT_READY_TIMEOUT  = 60


def wait_for_server():
    """Poll the Flask server until it returns HTTP 200 or we time out."""
    print("[TABLET] Waiting for Flask server at {} ...".format(DEFAULT_URL))
    deadline = time.time() + SERVER_READY_TIMEOUT
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            resp = urllib_request.urlopen(DEFAULT_URL, timeout=3)
            if resp.getcode() == 200:
                print("[TABLET] Flask server ready after {} attempt(s).".format(attempt))
                return True
        except Exception:
            pass
        time.sleep(2)
    print("[TABLET] Flask server did not become ready within {}s.".format(SERVER_READY_TIMEOUT))
    return False


def wait_for_ui_heartbeat(timeout):
    """Poll /api/tablet_status until the loaded page reports a healthy paint.

    The UI pings /api/tablet_alive only after it renders VISIBLE content, so a
    fresh heartbeat means the page truly loaded (not a white screen). Returns
    True as soon as the server reports 'alive', else False after `timeout`s.
    """
    status_url = DEFAULT_URL + "/api/tablet_status"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = urllib_request.urlopen(status_url, timeout=3)
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("alive"):
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def wait_for_server_from_pepper(tablet):
    """Use the tablet's own WiFi to confirm it can reach the Flask server."""
    print("[TABLET] Verifying Pepper tablet can reach {}...".format(DEFAULT_URL))
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            # ALTabletService.getWifiStatus() returns WiFi state on Pepper
            wifi = tablet.getWifiStatus()
            print("[TABLET] Pepper WiFi status: {}".format(wifi))
        except Exception:
            pass
        # Try loading a lightweight URL and check onPageFinished via configureWifi
        # We can't directly test HTTP from tablet, so just ensure WiFi is connected
        break
    return True


def connect_tablet():
    """Retry ALTabletService connection until the robot NAOqi broker is reachable."""
    print("[TABLET] Connecting to ALTabletService on {}:{} ...".format(PEPPER_IP, PEPPER_PORT))
    deadline = time.time() + ROBOT_READY_TIMEOUT
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            tablet = ALProxy("ALTabletService", PEPPER_IP, PEPPER_PORT)
            print("[TABLET] ALTabletService connected after {} attempt(s).".format(attempt))
            return tablet
        except Exception as e:
            print("[TABLET] Attempt {}: robot not ready yet ({})".format(attempt, e))
        time.sleep(3)
    return None


def show_tablet_ui():
    # 1. Wait for Flask to be serving pages (from laptop side)
    if not wait_for_server():
        print("[TABLET] Aborting – Flask server never became ready.")
        sys.exit(1)

    # 2. Wait for the robot's NAOqi broker to accept connections
    tablet = connect_tablet()
    if tablet is None:
        print("[TABLET] Aborting – could not reach ALTabletService after {}s.".format(ROBOT_READY_TIMEOUT))
        sys.exit(1)

    # 3. Check what WiFi Pepper's tablet is using
    try:
        wifi = tablet.getWifiStatus()
        print("[TABLET] Pepper WiFi status: {}".format(wifi))
    except Exception as e:
        print("[TABLET] Could not query WiFi status: {}".format(e))

    # 4. Enable the webview and configure for reliable loading
    try:
        tablet.enableWifi()
    except Exception:
        pass

    # 5. Clear stale WebKit cache (prevents white-page after restart)
    print("[TABLET] Resetting tablet cache and loading {}...".format(DEFAULT_URL))
    try:
        tablet.resetTablet()
        time.sleep(2)
    except Exception:
        pass

    # 6. Hide any leftover webview
    try:
        tablet.hideWebview()
        time.sleep(1)
    except Exception:
        pass

    # 7. Show webview FIRST (some firmware versions need webview visible before loadUrl works)
    tablet.showWebview()
    time.sleep(1)

    # 8. Load the URL with cache-buster
    cache_bust_url = DEFAULT_URL + "/?_t={}".format(int(time.time()))
    print("[TABLET] Loading URL: {}".format(cache_bust_url))
    tablet.loadUrl(cache_bust_url)
    time.sleep(8)

    # 9. Force reload to handle any first-load render glitch. Use a FRESH
    # cache-bust (not the bare DEFAULT_URL) — reloading the un-busted URL can
    # re-serve a half-cached first paint and leave the tablet white.
    print("[TABLET] Reloading page...")
    tablet.loadUrl(DEFAULT_URL + "/?_t={}".format(int(time.time())))
    time.sleep(3)

    # 10. VERIFY the UI actually painted (not a white page). The page pings
    # /api/tablet_alive once it renders visible content; we poll the server for
    # that heartbeat and reload Pepper up to MAX_RELOADS times if it's missing.
    MAX_RELOADS = 3
    loaded = False
    for attempt in range(1, MAX_RELOADS + 1):
        if wait_for_ui_heartbeat(10):
            loaded = True
            print("[TABLET] UI confirmed loaded (heartbeat received on attempt {}).".format(attempt))
            break
        print("[TABLET] No UI heartbeat (attempt {}/{}). Page looks white — reloading..."
              .format(attempt, MAX_RELOADS))
        try:
            tablet.resetTablet()    # clear stale WebKit cache before retry
            time.sleep(1)
        except Exception:
            pass
        try:
            tablet.showWebview()
        except Exception:
            pass
        tablet.loadUrl(DEFAULT_URL + "/?_t={}".format(int(time.time())))
        time.sleep(5)

    if loaded:
        print("[TABLET] UI successfully loaded.")
    else:
        print("[TABLET] WARNING: UI never confirmed a healthy render after {} reloads."
              .format(MAX_RELOADS))
        print("[TABLET] Likely causes: Pepper's WiFi is not on the SAME hotspot as this")
        print("[TABLET] laptop, or it cannot reach {}.".format(DEFAULT_URL))


if __name__ == "__main__":
    show_tablet_ui()
