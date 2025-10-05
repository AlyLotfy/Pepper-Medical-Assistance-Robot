# app.py
# Flask server for Pepper UI (tablet web app + simple APIs)
# Folder layout:
# pepper_ui/
# └─ server/
#    ├─ app.py
#    └─ static/ (index.html, styles.css, app.js, qimessaging/...)

import os
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = Flask(
    __name__,
    static_folder=str(STATIC_DIR),
    static_url_path=""  # so / serves from /static directly
)
app.config["JSON_SORT_KEYS"] = False

# ---------- Static UI ----------
@app.route("/")
def root():
    # Serve tablet UI
    return app.send_static_file("index.html")

@app.after_request
def add_cache_headers(resp):
    # Cache static assets; avoid caching API/HTML
    if request.path.startswith("/api") or request.path == "/":
        resp.headers["Cache-Control"] = "no-store"
    else:
        resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp

# Optional: serve files from /static explicitly (e.g., /static/app.js)
@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)

# ---------- Health ----------
@app.route("/health")
def health():
    return jsonify(status="ok")

# ---------- Example APIs (extend/replace with real logic) ----------
@app.route("/api/faq", methods=["POST"])
def api_faq():
    """
    Request JSON:
      { "q": "What are visiting hours?" }
    Response JSON:
      { "answer": "Visiting hours are 10:00–20:00." }
    """
    data = request.get_json(silent=True) or {}
    q = (data.get("q") or "").strip()
    # TODO: hook your RAG/FAQ backend here
    if not q:
        return jsonify(error="Missing 'q'"), 400
    # Dummy answer for now
    return jsonify(answer="Visiting hours are 10:00–20:00.")

@app.route("/api/queue", methods=["GET"])
def api_queue():
    """
    Example queue payload for the UI.
    """
    # TODO: Replace with real queue source
    return jsonify(
        departments=[
            {"name": "Family Medicine", "eta_min": 12, "tickets_waiting": 3},
            {"name": "Radiology",       "eta_min": 25, "tickets_waiting": 6},
            {"name": "Pharmacy",        "eta_min": 7,  "tickets_waiting": 2},
        ]
    )

@app.route("/api/nurse", methods=["POST"])
def api_nurse():
    """
    Trigger nurse alert (from tablet button).
    Request JSON (optional):
      { "room": "A-104", "note": "Wheelchair assistance" }
    """
    data = request.get_json(silent=True) or {}
    room = data.get("room")
    note = data.get("note")

    # TODO: Integrate with your alert pipeline (MQTT/HTTP/SMS)
    # For now, just acknowledge.
    return jsonify(status="sent", room=room, note=note or "")

# ---------- Error handlers ----------
@app.errorhandler(404)
def not_found(_e):
    # If UI tries to deep-link a route, serve index.html (SPA-like)
    if request.path.startswith("/api"):
        return jsonify(error="Not found"), 404
    return app.send_static_file("index.html")

@app.errorhandler(500)
def server_error(e):
    return jsonify(error="server_error", detail=str(e)), 500

# ---------- Entrypoint ----------
if __name__ == "__main__":
    # Host/port can be overridden via env vars
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    debug = os.environ.get("DEBUG", "true").lower() == "true"
    app.run(host=host, port=port, debug=debug)
