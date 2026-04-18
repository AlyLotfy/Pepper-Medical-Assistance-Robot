# -*- coding: utf-8 -*-
"""
PEPPER ADVANCED DIAGNOSTICS & STRESS TEST

Features:
- Repeated health checks (TTS, ALMemory, Mic, SFTP, Backend)
- Performance timings per stage
- Optional stress test of end-to-end voice pipeline
"""

import time
import os
import paramiko
import requests
from naoqi import ALProxy

# =============================
# CONFIGURATION
# =============================
ROBOT_IP   = "1.1.1.10"
ROBOT_PORT = 9559
ROBOT_USER = "nao"
ROBOT_PWD  = "nao"

EVENT_NAME = "Pepper/StartListening"

REMOTE_AUDIO_PATH = "/tmp/diag_record.wav"
LOCAL_AUDIO_FILE  = "diag_record_pc.wav"

# Backend (Flask) health endpoint – adjust if needed
BACKEND_HEALTH_URL = "http://127.0.0.1:8080/api/health"   # if you have one
# If no /api/health exists, you can point to / or /api/process_audio and just check status_code


# =============================
# UTILITY
# =============================

def header(title):
    print("\n" + "=" * 60)
    print(" " + title)
    print("=" * 60)


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


# =============================
# CHECK FUNCTIONS
# =============================

def check_tts():
    start = time.time()
    ok = True
    msg = "OK"
    try:
        tts = ALProxy("ALTextToSpeech", ROBOT_IP, ROBOT_PORT)
        tts.say("Diagnostics test.")
    except Exception as e:
        ok = False
        msg = "TTS error: %s" % e
    duration = time.time() - start
    return ok, duration, msg


def check_memory_event():
    start = time.time()
    ok = True
    msg = "OK"
    try:
        mem = ALProxy("ALMemory", ROBOT_IP, ROBOT_PORT)
        mem.raiseEvent(EVENT_NAME, 1)
    except Exception as e:
        ok = False
        msg = "ALMemory error: %s" % e
    duration = time.time() - start
    return ok, duration, msg


def check_recording():
    start = time.time()
    ok = True
    msg = "OK"
    try:
        audio = ALProxy("ALAudioRecorder", ROBOT_IP, ROBOT_PORT)
        channels = [0, 0, 1, 0]  # front mic

        try:
            audio.stopMicrophonesRecording()
        except:
            pass

        audio.startMicrophonesRecording(REMOTE_AUDIO_PATH, "wav", 16000, channels)
        time.sleep(2.0)
        audio.stopMicrophonesRecording()

        # simple existence check on robot side is not trivial from here,
        # but we will rely on SFTP in the next step
    except Exception as e:
        ok = False
        msg = "Recording error: %s" % e
    duration = time.time() - start
    return ok, duration, msg


def check_sftp():
    start = time.time()
    ok = True
    msg = "OK"
    try:
        if os.path.exists(LOCAL_AUDIO_FILE):
            try:
                os.remove(LOCAL_AUDIO_FILE)
            except:
                pass

        transport = paramiko.Transport((ROBOT_IP, 22))
        transport.connect(username=ROBOT_USER, password=ROBOT_PWD)
        sftp = paramiko.SFTPClient.from_transport(transport)
        sftp.get(REMOTE_AUDIO_PATH, LOCAL_AUDIO_FILE)
        sftp.close()
        transport.close()

        if not os.path.exists(LOCAL_AUDIO_FILE):
            ok = False
            msg = "Local file not found after transfer."
    except Exception as e:
        ok = False
        msg = "SFTP error: %s" % e
    duration = time.time() - start
    return ok, duration, msg


def check_backend():
    start = time.time()
    ok = True
    msg = "OK"
    try:
        r = requests.get(BACKEND_HEALTH_URL, timeout=5)
        if r.status_code != 200:
            ok = False
            msg = "Backend returned status %s" % r.status_code
    except Exception as e:
        ok = False
        msg = "Backend error: %s" % e
    duration = time.time() - start
    return ok, duration, msg


def end_to_end_trigger():
    """Trigger the same event the tablet uses, to test full pipeline."""
    start = time.time()
    ok = True
    msg = "OK"
    try:
        mem = ALProxy("ALMemory", ROBOT_IP, ROBOT_PORT)
        mem.raiseEvent(EVENT_NAME, 1)
    except Exception as e:
        ok = False
        msg = "End-to-end trigger error: %s" % e
    duration = time.time() - start
    return ok, duration, msg


# =============================
# DASHBOARD LOOP
# =============================

def run_single_cycle(cycle_id=None):
    if cycle_id is None:
        cycle_id = 1

    print("\n[%s] --- DIAGNOSTIC CYCLE %d ---" % (now(), cycle_id))

    results = {}

    ok_tts, t_tts, msg_tts = check_tts()
    print("TTS:           %s (%.3fs) - %s" % ("OK" if ok_tts else "FAIL", t_tts, msg_tts))
    results["tts"] = ok_tts

    ok_mem, t_mem, msg_mem = check_memory_event()
    print("ALMemory:      %s (%.3fs) - %s" % ("OK" if ok_mem else "FAIL", t_mem, msg_mem))
    results["memory"] = ok_mem

    ok_rec, t_rec, msg_rec = check_recording()
    print("Recording:     %s (%.3fs) - %s" % ("OK" if ok_rec else "FAIL", t_rec, msg_rec))
    results["record"] = ok_rec

    ok_sftp, t_sftp, msg_sftp = check_sftp()
    print("SFTP:          %s (%.3fs) - %s" % ("OK" if ok_sftp else "FAIL", t_sftp, msg_sftp))
    results["sftp"] = ok_sftp

    ok_back, t_back, msg_back = check_backend()
    print("Backend:       %s (%.3fs) - %s" % ("OK" if ok_back else "FAIL", t_back, msg_back))
    results["backend"] = ok_back

    return results


def run_dashboard(cycles=5, delay_between=5.0):
    header("PEPPER DIAGNOSTICS DASHBOARD")
    print("Robot IP:   %s" % ROBOT_IP)
    print("Backend URL:%s" % BACKEND_HEALTH_URL)
    print("Cycles:     %d" % cycles)
    print("Delay:      %.1fs between cycles" % delay_between)

    for i in range(1, cycles + 1):
        res = run_single_cycle(cycle_id=i)
        overall_ok = all(res.values())
        print("SUMMARY CYCLE %d → %s" % (i, "ALL OK" if overall_ok else "SOME FAILED"))
        if i < cycles:
            time.sleep(delay_between)


# =============================
# STRESS TEST (END-TO-END)
# =============================

def run_stress_test(trials=10, pause=2.0):
    header("END-TO-END STRESS TEST (Tablet Event → Full Pipeline)")
    print("Trials: %d, Pause: %.1fs" % (trials, pause))
    print("NOTE: Requires bridge + backend running.")

    success = 0
    for i in range(1, trials + 1):
        ok, t, msg = end_to_end_trigger()
        print("Trial %02d: %s (%.3fs) - %s" % (i, "OK" if ok else "FAIL", t, msg))
        if ok:
            success += 1
        time.sleep(pause)

    print("\nStress test finished. Success: %d / %d" % (success, trials))


# =============================
# MAIN
# =============================

if __name__ == "__main__":
    # 1) Run dashboard diagnostics a few times
    run_dashboard(cycles=3, delay_between=5.0)

    # 2) Optional: uncomment to run a stress test of the full pipeline
    # run_stress_test(trials=10, pause=3.0)

    print("\n[%s] Diagnostics complete." % now())
