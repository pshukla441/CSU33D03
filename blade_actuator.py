import socket
import json
import time
import threading
import random

TURBINE_HOST = "127.0.0.1"
TURBINE_PORT = 6002
MY_PORT = 6003
MY_ID = "BLADE_ACTUATOR_1"

YAW_RATE = 2.0    # degrees per second
PITCH_RATE = 3.0  # degrees per second

current_yaw = 0.0
current_pitch = 5.0
target_yaw = 0.0
target_pitch = 5.0
msg_counter = 0
lock = threading.Lock()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("", MY_PORT))
print(f"[{MY_ID}] Listening on port {MY_PORT}")


def next_id():
    global msg_counter
    msg_counter += 1
    return msg_counter


def send_message(msg_type, destination, service, payload=None):
    message = {
        "type": msg_type,
        "msg_id": next_id(),
        "node_id": MY_ID,
        "destination": destination,
        "service": service,
        "timestamp": time.time(),
        "payload": payload or {},
    }
    data = json.dumps(message).encode()
    sock.sendto(data, (TURBINE_HOST, TURBINE_PORT))
    print(f"[{MY_ID}] Sent {msg_type} to {destination}")


def actuator_loop():
    """Simulates physical blade movement — moves toward target at a fixed rate."""
    global current_yaw, current_pitch
    while True:
        with lock:
            # Move yaw toward target
            yaw_diff = target_yaw - current_yaw
            if abs(yaw_diff) > 0.1:
                step = min(YAW_RATE, abs(yaw_diff)) * (1 if yaw_diff > 0 else -1)
                current_yaw += step

            # Move pitch toward target
            pitch_diff = target_pitch - current_pitch
            if abs(pitch_diff) > 0.1:
                step = min(PITCH_RATE, abs(pitch_diff)) * (1 if pitch_diff > 0 else -1)
                current_pitch += step

        time.sleep(1)


def handle_message(message):
    global target_yaw, target_pitch
    msg_type = message.get("type")

    if msg_type == "CONTROL_COMMAND":
        payload = message.get("payload", {})
        updated = {}
        with lock:
            if "yaw_angle" in payload:
                target_yaw = payload["yaw_angle"]
                updated["yaw_angle"] = target_yaw
            if "pitch_angle" in payload:
                target_pitch = payload["pitch_angle"]
                updated["pitch_angle"] = target_pitch

        print(f"[{MY_ID}] Moving blades → yaw={target_yaw} pitch={target_pitch}")
        send_message(
            msg_type="ACK",
            destination=message["node_id"],
            service="control",
            payload={
                "ack_for": message["msg_id"],
                "applied": updated,
                "current_yaw": current_yaw,
                "current_pitch": current_pitch,
                "status": "MOVING",
            },
        )

    elif msg_type == "STATUS_REQUEST":
        with lock:
            send_message(
                msg_type="BLADE_STATUS",
                destination=message["node_id"],
                service="blade_status",
                payload={
                    "current_yaw": current_yaw,
                    "current_pitch": current_pitch,
                    "target_yaw": target_yaw,
                    "target_pitch": target_pitch,
                    "moving": abs(target_yaw - current_yaw) > 0.1 or abs(target_pitch - current_pitch) > 0.1,
                },
            )

    elif msg_type == "HELLO":
        send_message(
            msg_type="ACK",
            destination=message["node_id"],
            service="handshake",
            payload={"ack_for": message["msg_id"]},
        )

    else:
        print(f"[{MY_ID}] Unknown message type: {msg_type}")


def run():
    threading.Thread(target=actuator_loop, daemon=True).start()
    print(f"[{MY_ID}] Running...")
    while True:
        data, addr = sock.recvfrom(4096)
        try:
            message = json.loads(data.decode())
            handle_message(message)
        except json.JSONDecodeError:
            print(f"[{MY_ID}] Malformed message")


if __name__ == "__main__":
    run()