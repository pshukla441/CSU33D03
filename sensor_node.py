import socket
import json
import time
import threading
import random

TURBINE_HOST = "127.0.0.1"
TURBINE_PORT = 6002
MY_PORT = 6004
MY_ID = "SENSOR_NODE_1"
REPORT_INTERVAL = 3  # send readings to turbine every 3 seconds

msg_counter = 0
lock = threading.Lock()

# Sensor state
sensors = {
    "vibration": 0.3,
    "temperature": 45.0,
    "rotor_speed": 1500,
    "wind_speed": 12.5,
    "blade_stress": 0.15,
}

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


def simulate_sensors():
    """Drift sensor values realistically over time."""
    while True:
        with lock:
            sensors["vibration"] = max(0, round(sensors["vibration"] + random.uniform(-0.05, 0.05), 3))
            sensors["temperature"] = max(0, sensors["temperature"] + random.uniform(-0.5, 0.5))
            sensors["rotor_speed"] = max(0, sensors["rotor_speed"] + random.uniform(-50, 50))
            sensors["wind_speed"] = max(0, sensors["wind_speed"] + random.uniform(-1.0, 1.0))
            sensors["blade_stress"] = max(0, round(sensors["blade_stress"] + random.uniform(-0.01, 0.01), 4))
        time.sleep(1)


def report_loop():
    """Periodically push sensor readings to the turbine node."""
    while True:
        time.sleep(REPORT_INTERVAL)
        with lock:
            reading = sensors.copy()
        print(f"[{MY_ID}] Reporting sensors to turbine")
        send_message(
            msg_type="SENSOR_DATA",
            destination="TURBINE_1",
            service="sensors",
            payload=reading,
        )


def handle_message(message):
    msg_type = message.get("type")

    if msg_type == "SENSOR_REQUEST":
        with lock:
            reading = sensors.copy()
        send_message(
            msg_type="SENSOR_DATA",
            destination=message["node_id"],
            service="sensors",
            payload=reading,
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
    threading.Thread(target=simulate_sensors, daemon=True).start()
    threading.Thread(target=report_loop, daemon=True).start()
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