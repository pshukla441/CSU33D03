import socket
from satellite_network import optimal_satellite_route, describe_route
import json
import time
import threading
from datetime import datetime, timezone

# Coordinates
CONTROL_LAT = 51.23
CONTROL_LON = -1.58
TURBINE_LAT = 48.76
TURBINE_LON = 2.34

MY_PORT = 6005
MY_ID = "CONTROL_1"
TURBINE_ID = "TURBINE_1"
TURBINE_ADDR = ("127.0.0.1", 6002)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", MY_PORT))   # 🔥 important: bind explicitly

message_count = 0


# -------------------- MESSAGE UTILS --------------------

def next_id():
    global message_count
    message_count += 1
    return message_count


def build_message(msg_type, service, payload=None):
    return {
        "type": msg_type,
        "msg_id": next_id(),
        "node_id": MY_ID,
        "destination": TURBINE_ID,
        "service": service,
        "timestamp": time.time(),
        "payload": payload or {},
    }


def send_message(message):
    data = json.dumps(message).encode()
    sock.sendto(data, TURBINE_ADDR)
    print(f"[SENT] {message['type']} (id {message['msg_id']})")


# -------------------- SATELLITE ROUTING --------------------

def pick_satellite():
    now = datetime.now(timezone.utc)
    route = optimal_satellite_route(
        CONTROL_LAT, CONTROL_LON,
        TURBINE_LAT, TURBINE_LON,
        at_time=now,
    )
    print(f"\n[ROUTE]\n{describe_route(route)}\n")


# -------------------- COMMANDS --------------------

def do_handshake():
    send_message(build_message("HELLO", "handshake"))


def ask_for_telemetry():
    send_message(build_message("TELEMETRY_REQUEST", "telemetry"))


def send_control_command(yaw=None, pitch=None):
    payload = {}
    if yaw is not None:
        payload["yaw_angle"] = yaw
    if pitch is not None:
        payload["pitch_angle"] = pitch

    if not payload:
        print("[INFO] Provide yaw or pitch")
        return

    send_message(build_message("CONTROL_COMMAND", "control", payload))


# -------------------- RECEIVE --------------------

def show_telemetry(data):
    print("\n----- Turbine Data -----")
    for k, v in data.items():
        print(f"{k}: {v}")
    print("------------------------\n")


def handle_reply(data):
    try:
        msg = json.loads(data.decode())
        print(f"[DEBUG] Full message: {msg}")   # 🔥 debug visibility
    except:
        print("[WARN] Bad message")
        return

    msg_type = msg.get("type")

    if msg_type == "TELEMETRY":
        show_telemetry(msg.get("payload", {}))

    elif msg_type == "ACK":
        print(f"[ACK] {msg.get('payload')}")

    else:
        print(f"[RECV] {msg_type}: {msg.get('payload')}")


def listener():
    print("[LISTENER] Started...")
    while True:
        data, addr = sock.recvfrom(4096)
        print(f"[DEBUG] Packet from {addr}")   # 🔥 critical debug
        handle_reply(data)


# -------------------- CLI --------------------

def parse_command(text):
    values = {}
    for part in text.split():
        if "=" in part:
            k, v = part.split("=")
            try:
                values[k] = float(v)
            except:
                pass
    return values


def main():
    print(f"[CONTROL] Running on port {MY_PORT}")

    # Start listener
    threading.Thread(target=listener, daemon=True).start()

    pick_satellite()
    do_handshake()

    print("\nCommands:")
    print("  telemetry")
    print("  yaw=30")
    print("  pitch=10")
    print("  yaw=30 pitch=10")
    print("  quit\n")

    while True:
        cmd = input("> ").strip()

        if cmd == "quit":
            break

        elif cmd == "telemetry":
            ask_for_telemetry()

        else:
            params = parse_command(cmd)
            if params:
                send_control_command(
                    yaw=params.get("yaw"),
                    pitch=params.get("pitch")
                )
            else:
                print("Invalid command")


if __name__ == "__main__":
    main()