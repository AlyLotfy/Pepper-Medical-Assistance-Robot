import asyncio
import websockets
import json
import os

# -------------------------------------------------------
# DYNAMIC CONFIGURATION
# -------------------------------------------------------
HOST = "0.0.0.0" 
WS_PORT = int(os.environ.get("WS_PORT", 8765))

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

                # Broadcast the message to all OTHER connected clients
                for client in connected_clients:
                    if client != websocket:
                        await client.send(message)
                        
            except json.JSONDecodeError:
                print(f"[WARN] Received invalid JSON format: {message}")
                
    except websockets.exceptions.ConnectionClosed:
        print("[WS_SERVER] Connection closed by client.")
    except Exception as e:
        print(f"[ERROR] WebSocket handler exception: {e}")
    finally:
        # Clean up disconnected clients
        connected_clients.remove(websocket)
        print(f"[WS_SERVER] Client disconnected. Total active clients: {len(connected_clients)}")

async def main():
    print("==============================================")
    print(f"   BACKEND WEBSOCKET SERVER")
    print(f"   Listening on ws://{HOST}:{WS_PORT}")
    print("==============================================")
    
    async with websockets.serve(ws_handler, HOST, WS_PORT):
        # Run forever
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] WebSocket server shut down gracefully.")