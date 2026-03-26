import socket
import json
import time
import threading

TURBINE_HOST = "127.0.0.1"
TURBINE_PORT = 6002
MY_PORT = 6005
MY_ID = "LOCAL_CONTROLLER_1"

# Safety thresholds — if exceeded, local controller acts autonomously
VIBRATION_LIMIT = 0.8
TEMPERATURE_LIMIT = 80.0
WIND_SPEED_LIMIT = 25.0

# How long without a satellite message before we assume link is down
SATELLITE_TIMEOUT = 30

msg_counter = 0
last_satellite_msg = time.time()
autonomous_mode = False
lock = threading.Lock()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("", MY_PORT))
print(f"[{MY_ID}] Listening on port {MY_PORT}")


def next_id():
    global msg_counter
    msg_counter += 1
    return msg_counter


def send_to_turbine(msg_type, service, payload=None):
    message = {
        "type": msg_type,
        "msg_id": next_id(),
        "node_id": MY_ID,
        "destination": "TURBINE_1",
        "service": service,
        "timestamp": time.time(),
        "payload": payload or {},
    }
    data = json.dumps(message).encode()
    sock.sendto(data, (TURBINE_HOST, TURBINE_PORT))
    print(f"[{MY_ID}] Sent {msg_type} to TURBINE_1")


def watchdog():
    """
    Monitors satellite link. If no satellite message seen in SATELLITE_TIMEOUT
    seconds, switches to autonomous mode and applies safety controls.
    """
    global autonomous_mode
    while True:
        time.sleep(5)
        silence = time.time() - last_satellite_msg
        with lock:
            if silence > SATELLITE_TIMEOUT and not autonomous_mode:
                autonomous_mode = True
                print(f"[{MY_ID}] Satellite link lost ({silence:.0f}s silence) — AUTONOMOUS MODE")
                # Safe default: feather the blades to reduce load
                send_to_turbine(
                    msg_type="CONTROL_COMMAND",
                    service="control",
                    payload={"pitch_angle": 90.0, "yaw_angle": 0.0},
                )
            elif silence <= SATELLITE_TIMEOUT and autonomous_mode:
                autonomous_mode = False
                print(f"[{MY_ID}] Satellite link restored — returning to remote control")


def safety_monitor(sensor_data):
    """
    Checks incoming sensor readings against safety thresholds.
    Acts autonomously if limits are exceeded.
    """
    vibration = sensor_data.get("vibration", 0)
    temperature = sensor_data.get("temperature", 0)
    wind_speed = sensor_data.get("wind_speed", 0)

    if vibration > VIBRATION_LIMIT:
        print(f"[{MY_ID}] HIGH VIBRATION {vibration:.3f} — reducing pitch")
        send_to_turbine(
            msg_type="CONTROL_COMMAND",
            service="control",
            payload={"pitch_angle": 45.0},
        )

    if temperature > TEMPERATURE_LIMIT:
        print(f"[{MY_ID}] HIGH TEMPERATURE {temperature:.1f}°C — feathering blades")
        send_to_turbine(
            msg_type="CONTROL_COMMAND",
            service="control",
            payload={"pitch_angle": 90.0},
        )

    if wind_speed > WIND_SPEED_LIMIT:
        print(f"[{MY_ID}] HIGH WIND {wind_speed:.1f} m/s — emergency feather")
        send_to_turbine(
            msg_type="CONTROL_COMMAND",
            service="control",
            payload={"pitch_angle": 90.0, "yaw_angle": 0.0},
        )


def handle_message(message):
    global last_satellite_msg
    msg_type = message.get("type")

    if msg_type == "SATELLITE_MSG":
        # Any message forwarded from satellite resets the watchdog
        with lock:
            last_satellite_msg = time.time()

    elif msg_type == "SENSOR_DATA":
        # Sensor node is reporting — run safety checks
        safety_monitor(message.get("payload", {}))

    elif msg_type == "TELEMETRY":
        # Turbine pushed telemetry — also use for safety checks
        safety_monitor(message.get("payload", {}))

    elif msg_type == "HELLO":
        send_to_turbine(
            msg_type="ACK",
            service="handshake",
            payload={"ack_for": message["msg_id"]},
        )

    elif msg_type == "STATUS_REQUEST":
        with lock:
            mode = "AUTONOMOUS" if autonomous_mode else "REMOTE"
        send_to_turbine(
            msg_type="CONTROLLER_STATUS",
            service="status",
            payload={
                "mode": mode,
                "satellite_silence_s": time.time() - last_satellite_msg,
                "thresholds": {
                    "vibration": VIBRATION_LIMIT,
                    "temperature": TEMPERATURE_LIMIT,
                    "wind_speed": WIND_SPEED_LIMIT,
                },
            },
        )

    else:
        print(f"[{MY_ID}] Unknown message type: {msg_type}")


def run():
    threading.Thread(target=watchdog, daemon=True).start()
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