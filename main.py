import os
import subprocess
import sys
import time
import json

# ================================
# PATH CONFIGURATION
# ================================
BASE = os.path.abspath(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(BASE, "config.json")

PEPPER_SDK = r"C:\pynaoqi\pynaoqi-python2.7-2.8.6.23-win64-vs2015-20191127_152649"

# Backend Flask server
SERVER_DIR = os.path.join(BASE, "Pepper-Controller-main-2", "pepper_ui", "server", "app")
WS_BRIDGE = os.path.join(BASE, "Pepper-Controller-main-2", "pepper_voice", "ws_bridge.py")

# Tablet loader
TABLET_SCRIPT = os.path.join(BASE, "Pepper-Controller-main-2", "pepper_ui", "robot", "show_tablet.py")

# Voice module
VOICE_DIR = os.path.join(BASE, "Pepper-Controller-main-2", "pepper_voice")
VOICE_SCRIPT = os.path.join(VOICE_DIR, "MainVoice.py")

# Navigation bridge (Python 2.7, connects to WS bridge and executes navigate commands on robot)
NAV_DIR = os.path.join(BASE, "Pepper-Controller-main-2", "navigation")
NAV_BRIDGE_SCRIPT = os.path.join(NAV_DIR, "nav_bridge.py")

# Camera server (Python 2.7, serves JPEG snapshots from Pepper's camera)
CAM_SERVER_SCRIPT = os.path.join(BASE, "Pepper-Controller-main-2", "pepper_ui", "robot", "camera_server.py")

# Python versions
PY3 = sys.executable
PY2 = "python2"

# ================================
# CONFIGURATION MANAGEMENT
# ================================
DEFAULT_CONFIG = {
    "ROBOT_IP": "192.168.1.100",
    "ROBOT_PORT": "9559",
    "SERVER_IP": "192.168.1.50",
    "SERVER_PORT": "8000",
    "WS_PORT": "8765"
}

def load_or_create_config():
    """Loads config.json or creates a default one if it is missing."""
    if not os.path.exists(CONFIG_PATH):
        print("[INFO] config.json not found. Creating default configuration file.")
        with open(CONFIG_PATH, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG

    try:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
            print("[INFO] Successfully loaded config.json")
            return config
    except Exception as e:
        print(f"[ERROR] Failed to read config.json: {e}")
        sys.exit(1)

config_data = load_or_create_config()

# ================================
# ENVIRONMENT SETUP
# ================================
# Python 3 Environment (Backend & WS Bridge)
env_py3 = os.environ.copy()
env_py3["ROBOT_IP"] = str(config_data.get("ROBOT_IP", ""))
env_py3["SERVER_IP"] = str(config_data.get("SERVER_IP", ""))
env_py3["WS_PORT"] = str(config_data.get("WS_PORT", ""))

# NAOqi Python 2.7 Environment (Voice & Tablet)
env_py2 = os.environ.copy()
env_py2["PYTHONPATH"] = os.path.join(PEPPER_SDK, "lib")
env_py2["PATH"] = os.path.join(PEPPER_SDK, "bin") + ";" + env_py2["PATH"]
# Pass the config IPs into the Py2 environment as well
env_py2["ROBOT_IP"]   = str(config_data.get("ROBOT_IP", ""))
env_py2["ROBOT_PORT"] = str(config_data.get("ROBOT_PORT", ""))
env_py2["SERVER_IP"]  = str(config_data.get("SERVER_IP", ""))
env_py2["SERVER_PORT"] = str(config_data.get("SERVER_PORT", ""))
env_py2["WS_PORT"]    = str(config_data.get("WS_PORT", "8765"))
env_py2["VOICE_DIR"]  = VOICE_DIR

# ================================
# FIREWALL HELPER
# ================================
def ensure_firewall_rules():
    """Add Windows Firewall rules so Pepper's tablet can reach the Flask/WS servers."""
    ports = {
        "Pepper-Flask": int(config_data.get("SERVER_PORT", 8080)),
        "Pepper-WS":    int(config_data.get("WS_PORT", 8765)),
        "Pepper-Cam":   8082,
    }
    for name, port in ports.items():
        # Check if rule already exists
        check = subprocess.run(
            f'netsh advfirewall firewall show rule name="{name}"',
            shell=True, capture_output=True, text=True
        )
        if "No rules match" in check.stderr or check.returncode != 0:
            result = subprocess.run(
                f'netsh advfirewall firewall add rule name="{name}" dir=in action=allow protocol=TCP localport={port}',
                shell=True, capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"[FIREWALL] Opened port {port} ({name})")
            else:
                print(f"[FIREWALL] Could not open port {port} – run as Administrator if on Public WiFi/hotspot")
                print(f"           {result.stderr.strip()}")
        else:
            print(f"[FIREWALL] Port {port} ({name}) already open")


# ================================
# PROCESS STARTERS
# ================================
def start_backend():
    print(f"[INFO] Starting Flask backend from: {SERVER_DIR}")
    return subprocess.Popen([PY3, "app.py"], cwd=SERVER_DIR, env=env_py3)

def free_port(port):
    """Kill any process holding the given TCP port (Windows)."""
    try:
        out = subprocess.check_output(
            "netstat -ano | findstr :{}".format(port), shell=True
        ).decode(errors="ignore")
        pids = set()
        for line in out.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and ":{}".format(port) in parts[1]:
                pid = parts[-1]
                if pid.isdigit() and int(pid) != os.getpid():
                    pids.add(pid)
        for pid in pids:
            subprocess.call("taskkill /PID {} /F".format(pid), shell=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("[INFO] Freed port {} (killed PID {})".format(port, pid))
    except Exception:
        pass

def start_ws_bridge():
    print("[INFO] Starting WebSocket Bridge...")
    free_port(int(config_data.get("WS_PORT", 8765)))
    time.sleep(0.5)
    return subprocess.Popen([PY3, WS_BRIDGE], cwd=VOICE_DIR, env=env_py3)

def start_voice():
    print("[INFO] Starting Pepper Voice Module...")
    return subprocess.Popen([PY2, VOICE_SCRIPT], cwd=VOICE_DIR, env=env_py2)

def start_tablet():
    print("[INFO] Starting Pepper tablet script...")
    return subprocess.Popen([PY2, TABLET_SCRIPT], env=env_py2)

def start_nav_bridge():
    print("[INFO] Starting Navigation Bridge...")
    return subprocess.Popen([PY2, NAV_BRIDGE_SCRIPT], cwd=NAV_DIR, env=env_py2)

def start_camera_server():
    print("[INFO] Starting Camera Server...")
    return subprocess.Popen([PY2, CAM_SERVER_SCRIPT], env=env_py2)

# ================================
# SHUTDOWN HANDLER
# ================================
def safe_terminate(proc, name):
    if proc is None:
        return
    try:
        if proc.poll() is None:
            print(f"[INFO] Closing {name}...")
            proc.terminate()
            time.sleep(1)
            if proc.poll() is None:
                proc.kill()
    except Exception as e:
        print(f"[WARN] Failed to close {name}: {e}")

# ================================
# MAIN ENTRY
# ================================
if __name__ == "__main__":
    print("=== PEPPER MEDICAL ASSISTANCE ROBOT – MAIN LAUNCHER ===")

    # Check flags
    SERVER_ONLY  = "--server-only" in sys.argv
    OFFLINE_MODE = "--offline" in sys.argv

    if OFFLINE_MODE:
        env_py3["OFFLINE_MODE"] = "1"
        env_py3["OLLAMA_MODEL"] = "qwen2.5:7b"
        print("[MODE] *** OFFLINE MODE — using local Ollama LLM (no internet needed) ***")
        # Verify Ollama is running
        try:
            import urllib.request
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
            print("[MODE] Ollama server is running.")
        except Exception:
            print("[WARN] Ollama server not detected! Start it with: ollama serve")
    else:
        print("[MODE] Online mode — using Claude API (internet required)")

    print(f"[NETWORK] Targeting Robot IP: {config_data.get('ROBOT_IP')}")
    print(f"[NETWORK] Targeting Server IP: {config_data.get('SERVER_IP')}")

    # Ensure firewall allows Pepper tablet to reach our servers
    ensure_firewall_rules()

    # 1. Always start the backend components
    backend_proc = start_backend()
    # Flask + Whisper loading can take 30+ seconds;
    # show_tablet.py polls until the server is ready so we only need a short
    # delay here to let the process start before we launch dependents.
    time.sleep(2)

    ws_proc = start_ws_bridge()
    time.sleep(1)

    # 2. Conditionally start the robot hardware components
    if not SERVER_ONLY:
        voice_proc = start_voice()
        time.sleep(1)

        # Tablet script is a ONE-SHOT process: it loads the UI then exits.
        # We MUST wait for it to finish before starting nav_bridge, because
        # concurrent NAOqi sessions cause "Session closed" errors when the
        # tablet process exits and tears down its broker.
        print("[INFO] Starting Pepper tablet script (waiting for completion)...")
        tablet_proc = subprocess.Popen([PY2, TABLET_SCRIPT], env=env_py2)
        tablet_proc.wait()
        print("[INFO] Tablet script finished.")
        time.sleep(2)  # let NAOqi broker settle after tablet process exits

        cam_proc = start_camera_server()
        time.sleep(1)

        nav_proc = start_nav_bridge()
        print("\n[SYSTEM] All modules launched successfully.\n")
        tablet_proc = None  # Already completed; nothing to terminate later
    else:
        voice_proc = None
        tablet_proc = None
        nav_proc = None
        cam_proc = None
        print("\n[SYSTEM] Running in SERVER-ONLY mode. Robot hardware scripts bypassed.\n")

    print("--- PATH DIAGNOSTIC ---")
    print(f"Base Directory: {BASE}")
    print(f"Checking Server Dir: {SERVER_DIR} -> {'FOUND' if os.path.exists(SERVER_DIR) else 'NOT FOUND'}")
    print(f"Checking Voice Dir:  {VOICE_DIR}  -> {'FOUND' if os.path.exists(VOICE_DIR) else 'NOT FOUND'}")
    print(f"Checking Nav Dir:    {NAV_DIR}    -> {'FOUND' if os.path.exists(NAV_DIR) else 'NOT FOUND'}")
    print("-----------------------")
    
    try:
        # Keep the main thread alive while subprocesses run
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down gracefully...")
        safe_terminate(backend_proc, "Backend Server")
        safe_terminate(ws_proc, "WebSocket Bridge")
        safe_terminate(voice_proc, "Voice Module")
        safe_terminate(tablet_proc, "Tablet Script")
        safe_terminate(cam_proc, "Camera Server")
        safe_terminate(nav_proc, "Navigation Bridge")
        print("[INFO] Shutdown complete.")