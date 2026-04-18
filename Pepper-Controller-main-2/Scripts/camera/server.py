# server.py
# RUN THIS WITH PYTHON 3
from flask import Flask, request, render_template_string
from flask_socketio import SocketIO
import base64
import logging

# Disable logging spam to keep terminal clean
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
# cors_allowed_origins="*" allows the tablet to connect easily
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# 1. Endpoint for the Python 2 Script to upload images via HTTP POST
@app.route('/upload_frame', methods=['POST'])
def upload_frame():
    try:
        # Get raw JPEG bytes from the request body
        frame_bytes = request.data
        
        # Convert to Base64 String for the browser
        b64_string = base64.b64encode(frame_bytes).decode('utf-8')
        
        # Broadcast to all connected browsers immediately
        socketio.emit('video_frame', {'image': b64_string})
        return "OK", 200
    except Exception as e:
        print(f"Error processing frame: {e}")
        return "Error", 500

# 2. Serve the Camera Page directly (Simpler than a separate HTML file)
@app.route('/camera')
def camera_page():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Pepper Flask Stream</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
        <style>
            body { font-family: sans-serif; background: #f7f4f0; text-align: center; margin: 0; padding: 20px; }
            .card { background: white; padding: 20px; border-radius: 20px; max-width: 600px; margin: 0 auto; box-shadow: 0 10px 20px rgba(0,0,0,0.1); }
            h1 { color: #5a4a3b; }
            img { width: 100%; border-radius: 10px; border: 4px solid #b89a6c; background: black; min-height: 240px; }
            .status { color: #888; margin-top: 10px; font-size: 14px; }
            .back-btn { display: inline-block; margin-bottom: 15px; padding: 10px 20px; background: #b89a6c; color: white; text-decoration: none; border-radius: 20px; font-weight: bold; }
        </style>
    </head>
    <body>
        <a href="/" class="back-btn">&#8592; Back</a>
        <div class="card">
            <h1>Live Camera Feed</h1>
            <img id="stream" src="" alt="Waiting for Stream...">
            <p class="status" id="status">Connecting to Flask...</p>
        </div>

        <script>
            // Connect to Flask-SocketIO
            var socket = io();
            var img = document.getElementById("stream");
            var statusText = document.getElementById("status");

            socket.on('connect', function() {
                statusText.textContent = "Connected to Server. Waiting for Robot...";
                statusText.style.color = "orange";
            });

            // Receive new frame
            socket.on('video_frame', function(data) {
                img.src = "data:image/jpeg;base64," + data.image;
                statusText.textContent = "● Live Stream Active";
                statusText.style.color = "green";
            });

            socket.on('disconnect', function() {
                statusText.textContent = "Disconnected from Server.";
                statusText.style.color = "red";
            });
        </script>
    </body>
    </html>
    """

if __name__ == '__main__':
    print("[INFO] Starting Flask Server on Port 5001...")
    print("[INFO] Open http://localhost:5001/camera in your browser.")
    socketio.run(app, host='0.0.0.0', port=5001)