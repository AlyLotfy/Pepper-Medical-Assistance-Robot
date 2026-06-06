import os
import subprocess
import sys
import time
import json
import socket

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
# AUTO-DETECT SERVER IP
# ================================
def detect_server_ip(robot_ip=None):
    """Auto-detect this laptop's LAN IP — the address Pepper's tablet must hit.

    Opens a dummy UDP socket toward the robot's subnet and reads back which
    local interface the OS would route through; that interface is the one on
    the same network as Pepper, so its IP is the correct SERVER_IP. No packets
    are actually sent (UDP connect only sets the route). Falls back to the
    default-route interface, then to the hostname lookup.
    """
    targets = []
    if robot_ip:
        targets.append(robot_ip)   # prefer the NIC on Pepper's subnet
    targets.append("8.8.8.8")      # fallback: default internet-facing NIC
    for target in targets:
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect((target, 9))            # port 9 = discard; nothing sent
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127.") and ip != "0.0.0.0":
                return ip
        except Exception:
            pass
        finally:
            try:
                if s: s.close()
            except Exception:
                pass
    # Last resort: resolve the hostname.
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return None

_detected_ip = detect_server_ip(config_data.get("ROBOT_IP"))
if _detected_ip:
    _old_ip = config_data.get("SERVER_IP")
    if _old_ip != _detected_ip:
        print(f"[NETWORK] Auto-detected Server IP: {_detected_ip} (config had {_old_ip})")
        config_data["SERVER_IP"] = _detected_ip
        # Persist so the value is visible/consistent for other tools.
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(config_data, f, indent=4)
            print("[NETWORK] Updated config.json with detected Server IP.")
        except Exception as e:
            print(f"[NETWORK] (could not write config.json: {e}) — using detected IP for this run.")
    else:
        print(f"[NETWORK] Server IP confirmed: {_detected_ip}")
else:
    print(f"[NETWORK] Could not auto-detect Server IP — using config value: {config_data.get('SERVER_IP')}")

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

        # Check if Ollama is already running; if not, auto-start it with CUDA enabled.
        import urllib.request as _ur
        ollama_running = False
        try:
            _ur.urlopen("http://localhost:11434/api/tags", timeout=3)
            ollama_running = True
            print("[GPU] Ollama server already running.")
        except Exception:
            pass

        if not ollama_running:
            print("[GPU] Ollama not detected — starting with CUDA GPU support ...")
            ollama_env = os.environ.copy()
            ollama_env["CUDA_VISIBLE_DEVICES"]    = "0"          # use first GPU
            ollama_env["OLLAMA_GPU_OVERHEAD"]     = "512000000"  # 512 MB reserved for OS/other
            ollama_env["OLLAMA_FLASH_ATTENTION"]  = "1"          # O(n²)→O(n log n) attention; 20-40% faster on CUDA
            ollama_env["OLLAMA_KEEP_ALIVE"]       = "-1"         # never unload model; eliminates cold-start penalty
            try:
                subprocess.Popen(
                    ["ollama", "serve"],
                    env=ollama_env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                    if sys.platform == "win32" else 0,
                )
                # Wait up to 15s for it to come up
                for _i in range(15):
                    time.sleep(1)
                    try:
                        _ur.urlopen("http://localhost:11434/api/tags", timeout=2)
                        print("[GPU] Ollama started successfully.")
                        ollama_running = True
                        break
                    except Exception:
                        pass
                if not ollama_running:
                    print("[WARN] Ollama did not start in time. Run 'ollama serve' manually.")
            except FileNotFoundError:
                print("[WARN] 'ollama' not found in PATH. Install from https://ollama.com")

        # Verify GPU is actually being used after warmup call
        if ollama_running:
            import json as _json
            try:
                # Trigger model load with a tiny request so it appears in /api/ps
                _ur.urlopen(
                    _ur.Request(
                        "http://localhost:11434/api/generate",
                        data=_json.dumps({"model": "qwen2.5:7b", "prompt": "",
                                          "options": {"num_gpu": 99}}).encode(),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    ),
                    timeout=30,
                )
            except Exception:
                pass
            try:
                with _ur.urlopen("http://localhost:11434/api/ps", timeout=5) as _r:
                    _ps = _json.loads(_r.read())
                for _m in _ps.get("models", []):
                    _vram = _m.get("size_vram", 0)
                    _total = _m.get("size", 1)
                    _pct = int(100 * _vram / _total) if _total else 0
                    print(f"[GPU] {_m.get('name')} — "
                          f"{_vram // 1024 // 1024} MB on GPU "
                          f"/ {_total // 1024 // 1024} MB total ({_pct}% GPU)")
                    if _pct < 50:
                        print("[WARN] Model is mostly on CPU — response times will be slow. "
                              "Ensure CUDA drivers are installed and VRAM is sufficient.")
                    else:
                        print("[GPU] GPU acceleration confirmed.")
            except Exception:
                print("[GPU] Could not verify GPU usage via /api/ps (non-fatal).")
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