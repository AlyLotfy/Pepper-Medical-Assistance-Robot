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
# Keep the proxy + subscription in mutable globals so the grabber can
# rebuild them when NAOqi reports "module destroyed" / "Session closed".
video = None
SUB_NAME = None
_proxy_lock = threading.Lock()


def _connect_camera():
    """Create the ALVideoDevice proxy and subscribe to the top camera.

    subscribeCamera(name, cameraIndex, resolution, colorSpace, fps)
      cameraIndex: 0=top, 1=bottom
      resolution:  1=QVGA(320x240) -- fast enough for streaming
      colorSpace:  11=RGB
    """
    global video, SUB_NAME
    with _proxy_lock:
        new_video = ALProxy("ALVideoDevice", PEPPER_IP, PEPPER_PORT)
        # Unsubscribe any stale handle from a previous session, best-effort.
        try:
            if SUB_NAME:
                new_video.unsubscribe(SUB_NAME)
        except Exception:
            pass
        # Use a unique name per attempt so stale robot-side state never
        # collides with the new subscription.
        sub_name = new_video.subscribeCamera(
            "cam_server_{}".format(int(time.time())), 0, 1, 11, 15)
        video = new_video
        SUB_NAME = sub_name
        print("[CAMERA] Subscribed to Pepper top camera (QVGA, RGB, 15fps) "
              "as '{}'".format(sub_name))


_connect_camera()

# ---------- FRAME CACHE ----------
# Grab frames in a background thread so HTTP requests never block on NAOqi.
# A condition variable lets the MJPEG handler block until a fresh frame is
# available, instead of busy-polling the cache.
_frame_lock = threading.Lock()
_frame_cond = threading.Condition(_frame_lock)
_frame_id   = [0]     # mutable int so nested scopes can bump it
_cached_jpeg = None
_cached_w = 0
_cached_h = 0


def _frame_grabber():
    """Background thread: grab a frame every ~200ms and cache it.

    Auto-reconnects when the underlying NAOqi module is destroyed (happens
    when the robot reboots a service, or when another subscriber invalidates
    ours). Without reconnect, every subsequent getImageRemote would fail.
    """
    global _cached_jpeg, _cached_w, _cached_h
    error_count = 0
    while True:
        try:
            with _proxy_lock:
                v, sub = video, SUB_NAME
            img = v.getImageRemote(sub)
            if img:
                w, h, raw = img[0], img[1], img[6]
                pil_img = Image.frombytes("RGB", (w, h), bytes(raw))
                buf = BytesIO()
                pil_img.save(buf, format="JPEG", quality=65, optimize=False)
                jpeg = buf.getvalue()
                with _frame_lock:
                    _cached_jpeg = jpeg
                    _cached_w = w
                    _cached_h = h
                    _frame_id[0] += 1
                    _frame_cond.notify_all()
                error_count = 0
            time.sleep(0.066)  # ~15fps grabber
        except Exception as e:
            error_count += 1
            msg = str(e)
            if error_count <= 3:
                print("[CAMERA] Frame grab error: " + msg)
            elif error_count == 4:
                print("[CAMERA] Suppressing further errors. Will retry silently...")
            # Reconnect when the NAOqi module/session is gone — plain sleeping
            # won't help because the proxy handle itself is dead.
            if ("module destroyed" in msg or "Session closed" in msg
                    or "getImageRemote" in msg):
                try:
                    print("[CAMERA] Reconnecting to ALVideoDevice...")
                    _connect_camera()
                    error_count = 0
                except Exception as ce:
                    print("[CAMERA] Reconnect failed: " + str(ce))
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
            elif self.path.startswith("/mjpeg"):
                self._serve_mjpeg()
            else:
                self.send_error(404)
        except Exception:
            pass  # client disconnected mid-response, ignore

    def _serve_mjpeg(self):
        """Stream multipart JPEG frames; browser <img> tags render this
        natively with no client-side polling."""
        boundary = "pepperframe"
        try:
            self.send_response(200)
            self.send_header("Content-Type",
                             "multipart/x-mixed-replace; boundary=" + boundary)
            self.send_header("Cache-Control",
                             "no-cache, no-store, must-revalidate, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Connection", "close")
            self.end_headers()
        except Exception:
            return

        last_id = -1
        while True:
            with _frame_cond:
                # Block until a newer frame is ready (cap wait at 1s so we
                # notice dead clients on reconnect / error frames).
                while _frame_id[0] == last_id and _cached_jpeg is None:
                    _frame_cond.wait(1.0)
                while _frame_id[0] == last_id:
                    if not _frame_cond.wait(1.0):
                        break
                jpeg = _cached_jpeg
                last_id = _frame_id[0]
            if not jpeg:
                continue
            try:
                header = ("--" + boundary + "\r\n"
                          "Content-Type: image/jpeg\r\n"
                          "Content-Length: " + str(len(jpeg)) + "\r\n\r\n")
                self.wfile.write(header.encode("ascii"))
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
            except Exception:
                return  # client disconnected — drop out cleanly

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
        try:
            if video and SUB_NAME:
                video.unsubscribe(SUB_NAME)
        except Exception:
            pass
        server.server_close()
