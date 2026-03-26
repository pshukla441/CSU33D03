# libraries we need to talk to the satellite and handle messages
import socket       # for network communication
import json         # for encoding and decoding messages
import time         # for timestamps and delays
import threading    # to listen for incoming messages without blocking the main thread

# Settings
SATELLITE_IP      = "127.0.0.1"
SATELLITE_PORT    = 6001
MY_PORT           = 6004
MY_ID             = "CONTROL_1"
TURBINE_ID        = "TURBINE_1"

# Running counter so every message gets a unique number
message_count = 0

# Each call returns the next message number: 1, 2, 3 ...n
def next_id():
    global message_count
    message_count += 1
    return message_count

# Packages data into the format everyone agreed on.Every message in the system looks like this.
def build_message(msg_type, service, payload=None):
    return {
        "type":        msg_type,
        "msg_id":      next_id(),
        "node_id":     MY_ID,
        "destination": TURBINE_ID,
        "service":     service,
        "timestamp":   time.time(),
        "payload":     payload if payload else {},
    }

# Convert message dict to bytes and fire it at the satellite.
def transmit(sock, message):
    encoded = json.dumps(message).encode()
    sock.sendto(encoded, (SATELLITE_IP, SATELLITE_PORT))
    print(f"[SENT] {message['type']}  (id {message['msg_id']})")

# Outgoing messages: says hello so the turbine knows we are online.
def do_handshake(sock):
    transmit(sock, build_message("HELLO", "handshake"))

# Request an immediate sensor snapshot from the turbine.
def ask_for_telemetry(sock):
    transmit(sock, build_message("TELEMETRY_REQUEST", "telemetry"))

# Tell the turbine to move, you can set yaw, pitch, or both in a single command.
def send_control_command(sock, yaw=None, pitch=None):
    payload = {}
    if yaw   is not None: payload["yaw_angle"]   = yaw
    if pitch is not None: payload["pitch_angle"] = pitch

    if not payload:
        print("[INFO] Please provide at least one value — e.g. yaw=30")
        return

    transmit(sock, build_message("CONTROL_COMMAND", "control", payload))

# Incoming messages, display sensor readings in a clean block.
def show_telemetry(data):
    print("\n┌------ Live Turbine Data --------------")
    for label, value in data.items():
        print(f"│  {label:<22} {value}")
    print("----------------------------------------\n")

#Work out what kind of message arrived and display it.
def handle_reply(raw_bytes):
    try:
        msg = json.loads(raw_bytes.decode())
    except json.JSONDecodeError:
        print("[WARN] Garbled message received — skipping")
        return

    kind = msg.get("type", "UNKNOWN")

    if kind == "TELEMETRY":
        show_telemetry(msg.get("payload", {}))

    elif kind == "ACK":
        confirmed_id = msg["payload"].get("ack_for", "?")
        changes      = msg["payload"].get("applied", {})
        print(f"[ACK] Command {confirmed_id} applied — {changes}")

    else:
        print(f"[RECV] {kind} from {msg.get('node_id', '?')}: {msg.get('payload', {})}")


# Runs in a separate thread and sits quietly in the background waiting for anything the turbine sends back.
def background_listener(sock):
    while True:
        data, _ = sock.recvfrom(4096)
        handle_reply(data)
        print("> ", end="", flush=True)   # keep the prompt visible

# Input parsing: turn "yaw=45 pitch=-10" into {"yaw": 45.0, "pitch": -10.0}
def parse_command(text):
    values = {}
    for part in text.split():
        if "=" not in part:
            continue
        key, _, raw_val = part.partition("=")
        try:
            values[key.strip()] = float(raw_val.strip())
        except ValueError:
            print(f"[WARN] Could not read '{key}' value — skipped")     # Skips any token it cannot understand.
    return values

def main():
    # Open one socket — used for both sending and receiving.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", MY_PORT))
    print(f"[GROUND] Station {MY_ID} online, listening on port {MY_PORT}")

    # Kick off the background listener.
    listener = threading.Thread(target=background_listener, args=(sock,), daemon=True)
    listener.start()

    do_handshake(sock)

    print("\n----------- Ground Control Console -----------")
    print("  yaw=<degrees>             rotate the turbine")
    print("  pitch=<degrees>           adjust blade angle")
    print("  yaw=<val> pitch=<val>     set both at once")
    print("  telemetry                 request sensor snapshot")
    print("  quit                      shut down\n")

    # Operator input loop
    while True:
        entry = input("> ").strip()

        if not entry:
            continue
        if entry.lower() == "quit":
            print("Ground control shutting down. Goodbye.")
            break
        if entry.lower() == "telemetry":
            ask_for_telemetry(sock)
            continue
        params = parse_command(entry)
        if params:
            send_control_command(sock,
                yaw   = params.get("yaw"),
                pitch = params.get("pitch"))
        else:
            print("[INFO] Unknown command. Try:  yaw=45  or  pitch=-10")

if __name__ == "__main__":
    main()