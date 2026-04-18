# -*- coding: utf-8 -*-
import subprocess, sys, time, threading, os, shlex

# === Base paths ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_SCRIPT = os.path.join(BASE_DIR, "backend_api.py")
PEPPER_SCRIPT  = os.path.join(BASE_DIR, "pepper_voice.py")

# === NAOqi SDK paths ===
NAOQI_SDK = r"C:\pynaoqi\pynaoqi-python2.7-2.8.6.23-win64-vs2015-20191127_152649"
NAOQI_LIB = os.path.join(NAOQI_SDK, "lib")
NAOQI_BIN = os.path.join(NAOQI_SDK, "bin")

# === Full path to uvicorn.exe ===
UVICORN_PATH = r"C:\Users\ADMIN\AppData\Roaming\Python\Python313\Scripts\uvicorn.exe"


def set_pepper_env():
    """Configure NAOqi environment variables before launching Pepper code."""
    os.environ["PYTHONPATH"] = NAOQI_LIB
    os.environ["PATH"] = NAOQI_BIN + ";" + os.environ["PATH"]
    print("[INFO] NAOqi environment configured.")


def run_backend():
    """Start FastAPI backend using uvicorn (non-blocking)."""
    print("[INFO] Starting FastAPI backend...")
    # Run uvicorn in background (safe for spaces in path)
    cmd = f'"{UVICORN_PATH}" backend_api:app --host 0.0.0.0 --port 8000'
    subprocess.Popen(cmd, cwd=BASE_DIR, shell=True)


def run_pepper():
    """Launch Pepper voice client (Python 2.7)."""
    time.sleep(5)  # Wait for backend to start
    print("[INFO] Starting Pepper voice client...")
    set_pepper_env()

    # Safely quote the command (works even with spaces in path)
    cmd = f'python2 "{PEPPER_SCRIPT}"'
    print("[DEBUG] Running:", cmd)
    os.system(cmd)


def main():
    """Launch backend + Pepper voice client together."""
    backend_thread = threading.Thread(target=run_backend)
    backend_thread.daemon = True
    backend_thread.start()
    run_pepper()


if __name__ == "__main__":
    main()
