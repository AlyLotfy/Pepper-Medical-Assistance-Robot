# -*- coding: utf-8 -*-
"""
Tiny HTTP server (Python 2.7 + NAOqi) that serves JPEG snapshots
from Pepper's top camera.

Runs on a configurable port (default 8082) so the Flask backend
(Python 3) can proxy /api/camera/* requests here.

Endpoints:
    GET /snapshot      -> raw JPEG image
    GET /snapshot_b64  -> JSON {"data_url": "data:image/jpeg;base64,...", "width":..., "height":...}
"""
from __future__ import print_function
import os
import sys
import json
import base64
import time
import threading
from io import BytesIO

try:
    from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
    from SocketServer import ThreadingMixIn
except ImportError:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from socketserver import ThreadingMixIn

from naoqi import ALProxy
from PIL import Image

# ---------- CONFIG ----------
PEPPER_IP   = os.environ.get("ROBOT_IP", "1.1.1.10")
PEPPER_PORT = int(os.environ.get("ROBOT_PORT", "9559"))
CAM_PORT    = int(os.environ.get("CAM_PORT", "8082"))

# ---------- CAMERA SETUP ----------
video = ALProxy("ALVideoDevice", PEPPER_IP, PEPPER_PORT)
# subscribeCamera(name, cameraIndex, resolution, colorSpace, fps)
# cameraIndex: 0=top, 1=bottom
# resolution:  1=QVGA(320x240)  -- fast enough for streaming
# colorSpace: 11=RGB
SUB_NAME = video.subscribeCamera("cam_server", 0, 1, 11, 10)
print("[CAMERA] Subscribed to Pepper top camera (QVGA, RGB, 10fps)")

# ---------- FRAME CACHE ----------
# Grab frames in a background thread so HTTP requests never block on NAOqi.
_frame_lock = threading.Lock()
_cached_jpeg = None
_cached_w = 0
_cached_h = 0


def _frame_grabber():
    """Background thread: grab a frame every ~200ms and cache it."""
    global _cached_jpeg, _cached_w, _cached_h
    error_count = 0
    while True:
        try:
            img = video.getImageRemote(SUB_NAME)
            if img:
                w, h, raw = img[0], img[1], img[6]
                pil_img = Image.frombytes("RGB", (w, h), bytes(raw))
                buf = BytesIO()
                pil_img.save(buf, format="JPEG", quality=70)
                jpeg = buf.getvalue()
                with _frame_lock:
                    _cached_jpeg = jpeg
                    _cached_w = w
                    _cached_h = h
                error_count = 0
            time.sleep(0.2)
        except Exception as e:
            error_count += 1
            if error_count <= 3:
                print("[CAMERA] Frame grab error: " + str(e))
            elif error_count == 4:
                print("[CAMERA] Suppressing further errors. Will retry silently...")
            # Back off: wait longer when NAOqi session is down
            time.sleep(min(5.0, 0.5 * error_count))


t = threading.Thread(target=_frame_grabber)
t.daemon = True
t.start()

# Give the grabber a moment to cache the first frame
time.sleep(0.5)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle each request in a new thread so slow clients don't block."""
    daemon_threads = True


class CamHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence per-request logs

    def do_GET(self):
        try:
            if self.path.startswith("/snapshot_b64"):
                self._serve_b64()
            elif self.path.startswith("/snapshot"):
                self._serve_jpeg()
            else:
                self.send_error(404)
        except Exception:
            pass  # client disconnected mid-response, ignore

    def _serve_jpeg(self):
        with _frame_lock:
            jpeg = _cached_jpeg
        if jpeg is None:
            self.send_error(503, "No frame")
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(jpeg)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(jpeg)

    def _serve_b64(self):
        with _frame_lock:
            jpeg = _cached_jpeg
            w = _cached_w
            h = _cached_h
        if jpeg is None:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "No frame"}).encode("utf-8"))
            return
        b64 = base64.b64encode(jpeg)
        if isinstance(b64, bytes):
            b64 = b64.decode("ascii")
        body = json.dumps({
            "data_url": "data:image/jpeg;base64," + b64,
            "width": w,
            "height": h
        })
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode("utf-8") if isinstance(body, str) else body)


if __name__ == "__main__":
    server = ThreadedHTTPServer(("0.0.0.0", CAM_PORT), CamHandler)
    print("=" * 46)
    print("   PEPPER CAMERA SERVER")
    print("   Serving on http://0.0.0.0:{}".format(CAM_PORT))
    print("=" * 46)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[CAMERA] Shutting down...")
        video.unsubscribe(SUB_NAME)
        server.server_close()
