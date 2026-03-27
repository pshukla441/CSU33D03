from reliable_send import ReliableUDP
from satellite_network import optimal_satellite_route, describe_route  # matches your teammate's filename

import json
import time
import threading
from datetime import datetime, timezone

# Ground station & turbine coordinates (randomly generated placeholders)
CONTROL_LAT =  51.23   # ground control station
CONTROL_LON =  -1.58
TURBINE_LAT  =  48.76  # wind turbine field
TURBINE_LON  =  2.34

MY_PORT    = 6004
MY_ID      = "CONTROL_1"
TURBINE_ID = "TURBINE_1"


def resolve_satellite_port(sat_id: str) -> int:
    """Map a satellite ID to a local UDP port for simulation purposes."""
    SAT_PORT_MAP = {
        "SAT-001": 5001,
        "SAT-002": 5002,
        "SAT-003": 5003,
        "SAT-004": 5004,
        "SAT-005": 5005,
        "SAT-006": 5006,
        "SAT-007": 5007,
        "SAT-008": 5008,
        "SAT-009": 5009,
        "SAT-010": 5010,
        "SAT-011": 5011,
        "SAT-012": 5012,
    }
    return SAT_PORT_MAP.get(sat_id, 5001)  # fall back to SAT-001 if unknown

def pick_satellite():
    """Use Dijkstra (via satellite_network) to find the best satellite right now."""
    now = datetime.now(timezone.utc)
    route = optimal_satellite_route(
        CONTROL_LAT, CONTROL_LON,
        TURBINE_LAT,  TURBINE_LON,
        at_time=now,
    )
    print(f"\n[ROUTE] {describe_route(route)}\n")

    # The path looks like: SRC -> SAT-XXX -> ... -> DST
    # First hop after SRC is the satellite we uplink through.
    for node in route.node_path:
        if node.startswith("SAT-"):
            return node
    raise RuntimeError("No satellite found in computed route")


message_count = 0

def next_id():
    global message_count
    message_count += 1
    return message_count

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

def make_rudp(sat_id: str) -> ReliableUDP:
    """Create a fresh ReliableUDP connection routed through the given satellite."""
    sat_port = resolve_satellite_port(sat_id)
    print(f"[ROUTE] Uplink via {sat_id} on port {sat_port}")
    return ReliableUDP(
        local_addr=("127.0.0.1", MY_PORT),
        peer_addr=("127.0.0.1", sat_port),
    )

def transmit(rudp, message):
    encoded = json.dumps(message).encode()
    rudp.send(encoded)
    print(f"[SENT] {message['type']}  (id {message['msg_id']})")

def do_handshake(rudp):
    transmit(rudp, build_message("HELLO", "handshake"))

def ask_for_telemetry(rudp):
    transmit(rudp, build_message("TELEMETRY_REQUEST", "telemetry"))

def send_control_command(rudp, yaw=None, pitch=None):
    payload = {}
    if yaw   is not None: payload["yaw_angle"]   = yaw
    if pitch is not None: payload["pitch_angle"] = pitch

    if not payload:
        print("[INFO] Please provide at least one value — e.g. yaw=30")
        return

    transmit(rudp, build_message("CONTROL_COMMAND", "control", payload))

def show_telemetry(data):
    print("\n┌------ Live Turbine Data --------------")
    for label, value in data.items():
        print(f"│  {label:<22} {value}")
    print("----------------------------------------\n")


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


def background_listener(rudp):
    while True:
        try:
            data = rudp.recv()
            handle_reply(data)
            print("> ", end="", flush=True)
        except Exception as e:
            print(f"[WARN] Receive error: {e}")

def parse_command(text):
    values = {}
    for part in text.split():
        if "=" not in part:
            continue
        key, _, raw_val = part.partition("=")
        try:
            values[key.strip()] = float(raw_val.strip())
        except ValueError:
            print(f"[WARN] Could not read '{key}' value — skipped")
    return values

def main():
    # Ask the satellite network which satellite to route through right now.
    sat_id = pick_satellite()

    rudp = make_rudp(sat_id)
    print(f"[GROUND] Station {MY_ID} online, listening on port {MY_PORT}")

    # Background listener for replies coming back from the turbine.
    listener = threading.Thread(target=background_listener, args=(rudp,), daemon=True)
    listener.start()

    do_handshake(rudp)

    print("\n----------- Ground Control Console -----------")
    print("  yaw=<degrees>             rotate the turbine")
    print("  pitch=<degrees>           adjust blade angle")
    print("  yaw=<val> pitch=<val>     set both at once")
    print("  telemetry                 request sensor snapshot")
    print("  reroute                   recompute best satellite now")
    print("  quit                      shut down\n")

    while True:
        entry = input("> ").strip()

        if not entry:
            continue

        if entry.lower() == "quit":
            print("Ground control shutting down. Goodbye.")
            rudp.close()
            break

        if entry.lower() == "reroute":
            # Recompute the best satellite and reconnect.
            rudp.close()
            sat_id = pick_satellite()
            rudp = make_rudp(sat_id)
            listener = threading.Thread(target=background_listener, args=(rudp,), daemon=True)
            listener.start()
            continue

        if entry.lower() == "telemetry":
            ask_for_telemetry(rudp)
            continue

        params = parse_command(entry)
        if params:
            send_control_command(rudp,
                yaw   = params.get("yaw"),
                pitch = params.get("pitch"))
        else:
            print("[INFO] Unknown command. Try:  yaw=45  or  pitch=-10")


if __name__ == "__main__":
    main()