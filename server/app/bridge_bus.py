import json
from fastapi import WebSocket

clients = []

async def robot_ws(ws: WebSocket):
    await ws.accept()
    clients.append(ws)
    try:
        while True:
            await ws.receive_text()  # robot doesn’t send much
    except:
        clients.remove(ws)

def publish(msg: dict):
    for ws in clients:
        try:
            ws.send_text(json.dumps(msg))
        except:
            pass
