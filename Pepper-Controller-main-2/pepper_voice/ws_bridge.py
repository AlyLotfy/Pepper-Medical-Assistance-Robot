import asyncio
import websockets
import json
import os

# -------------------------------------------------------
# DYNAMIC CONFIGURATION
# -------------------------------------------------------
HOST = "0.0.0.0"
WS_PORT = int(os.environ.get("WS_PORT", 8765))

# Flag-file paths — must match MainVoice.py. The WS bridge writes these as a
# non-blocking second path for start/stop tap events, so the tablet UI is
# never stuck waiting on a Flask round-trip when the dev server is busy.
# Working dir of this script is Pepper-Controller-main-2/pepper_voice/, same
# as MainVoice.py, so a relative path resolves to the same file.
_VOICE_START_FLAG = "voice_start.flag"
_VOICE_STOP_FLAG  = "voice_stop.flag"
_LANG_FLAG        = "lang.flag"
_USER_FLAG        = "user.flag"

def _write_flag(path, content=""):
    try:
        with open(path, "w") as f:
            f.write(content or "")
    except Exception as e:
        print(f"[WS_SERVER] Failed to write {path}: {e}")

# Maintain a set of all active connections
connected_clients = set()

async def ws_handler(websocket):
    connected_clients.add(websocket)
    print(f"[WS_SERVER] New client connected. Total active clients: {len(connected_clients)}")

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type", "unknown")

                # Ignore ping/pong keep-alives in the console to reduce noise
                if msg_type not in ["ping", "pong", "hello"]:
                    print(f"[WS_SERVER] Routing message: {data}")

                # Side-effect: tap-event fallback path.
                # The tablet sends start/stop via HTTP POST AND via WS in
                # parallel. Flask's /api/start_voice and /api/stop_voice
                # write these same flag files. If either path lands first
                # MainVoice sees the flag and acts. This keeps the button
                # responsive even when Flask's single-threaded dev server
                # is busy processing the previous /api/process_audio call.
                if msg_type == "start_recording":
                    lang = (data.get("lang") or "").strip()
                    user_id = (data.get("user_id") or "")
                    tap_id = data.get("tap_id") or ""
                    if lang in ("en", "ar"):
                        _write_flag(_LANG_FLAG, lang)
                    if user_id:
                        _write_flag(_USER_FLAG, str(user_id))
                    # Stamp the tap id so MainVoice can ignore the duplicate
                    # write from the parallel HTTP /api/start_voice path.
                    _write_flag(_VOICE_START_FLAG, str(tap_id) or "1")
                elif msg_type == "stop_recording":
                    _write_flag(_VOICE_STOP_FLAG)

                # Broadcast the message to all OTHER connected clients.
                # Iterate over a SNAPSHOT (list copy): MainVoice opens and
                # closes a fresh WS connection for every 'result' /
                # 'speaking_done' broadcast, so connected_clients mutates
                # constantly. Iterating the live set while `await client.send`
                # yields control raises "Set changed size during iteration",
                # which aborts the whole broadcast and strands the tablet FSM
                # (missed 'result' / 'speaking_done' = stuck mic button).
                # A per-client guard also stops one dead/slow socket from
                # killing delivery to the others; dead sockets are pruned.
                dead = []
                for client in list(connected_clients):
                    if client is websocket:
                        continue
                    try:
                        await client.send(message)
                    except Exception:
                        dead.append(client)
                for d in dead:
                    connected_clients.discard(d)

            except json.JSONDecodeError:
                print(f"[WARN] Received invalid JSON format: {message}")
                
    except websockets.exceptions.ConnectionClosed:
        print("[WS_SERVER] Connection closed by client.")
    except Exception as e:
        print(f"[ERROR] WebSocket handler exception: {e}")
    finally:
        # Clean up disconnected clients. Use discard (not remove): this socket
        # may already have been pruned by the broadcast dead-client sweep, and
        # remove() would raise KeyError on a missing element.
        connected_clients.discard(websocket)
        print(f"[WS_SERVER] Client disconnected. Total active clients: {len(connected_clients)}")

async def main():
    print("==============================================")
    print(f"   BACKEND WEBSOCKET SERVER")
    print(f"   Listening on ws://{HOST}:{WS_PORT}")
    print("==============================================")
    
    async with websockets.serve(ws_handler, HOST, WS_PORT, ping_interval=None):
        # Run forever
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] WebSocket server shut down gracefully.")