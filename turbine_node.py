import socket
import json
import time
import threading
import random


class TurbineNode:
    def __init__(self, node_id, listen_port, satellite_addr, telemetry_interval=5):
        # Identity
        self.node_id = node_id

        # Network config
        self.listen_port = listen_port
        self.satellite_addr = satellite_addr  # (host, port) tuple

        # Turbine state
        self.state = {
            "wind_speed": 12.5,
            "rpm": 1500,
            "temperature": 45.0,
            "vibration": 0.3,
            "yaw_angle": 0.0,
            "pitch_angle": 5.0,
        }

        # Message counter for unique IDs
        self.msg_counter = 0

        # Telemetry config
        self.telemetry_interval = telemetry_interval

        # Create and bind UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", self.listen_port))

        print(f"[{self.node_id}] Listening on port {self.listen_port}")

    def _next_msg_id(self):
        self.msg_counter += 1
        return self.msg_counter

    def send_message(self, msg_type, destination, service, payload=None):
        message = {
            "type": msg_type,
            "msg_id": self._next_msg_id(),
            "node_id": self.node_id,
            "destination": destination,
            "service": service,
            "timestamp": time.time(),
            "payload": payload or {},
        }
        data = json.dumps(message).encode()
        self.sock.sendto(data, self.satellite_addr)
        print(f"[{self.node_id}] Sent {msg_type} to {destination}")

    def send_telemetry(self, destination="CONTROL_1"):
        self.send_message(
            msg_type="TELEMETRY",
            destination=destination,
            service="telemetry",
            payload=self.state.copy(),
        )

    # ---- Dynamic state simulation ----

    def simulate_state(self):
        """Runs in a background thread. Updates turbine state with realistic drift."""
        while True:
            self.state["wind_speed"] = max(0, self.state["wind_speed"] + random.uniform(-1.0, 1.0))
            self.state["rpm"] = max(0, self.state["rpm"] + random.uniform(-50, 50))
            self.state["temperature"] = max(0, self.state["temperature"] + random.uniform(-0.5, 0.5))
            self.state["vibration"] = max(0, round(self.state["vibration"] + random.uniform(-0.05, 0.05), 3))
            time.sleep(1)

    # ---- Automatic telemetry ----

    def telemetry_loop(self):
        """Runs in a background thread. Sends telemetry at a fixed interval."""
        while True:
            time.sleep(self.telemetry_interval)
            print(f"[{self.node_id}] Auto telemetry | wind={self.state['wind_speed']:.1f} rpm={self.state['rpm']:.0f} temp={self.state['temperature']:.1f}")
            self.send_telemetry()

    # ---- Message handling ----

    def handle_control_command(self, message):
        payload = message.get("payload", {})
        updated = {}

        if "yaw_angle" in payload:
            self.state["yaw_angle"] = payload["yaw_angle"]
            updated["yaw_angle"] = payload["yaw_angle"]

        if "pitch_angle" in payload:
            self.state["pitch_angle"] = payload["pitch_angle"]
            updated["pitch_angle"] = payload["pitch_angle"]

        print(f"[{self.node_id}] State updated: {updated}")

        self.send_message(
            msg_type="ACK",
            destination=message["node_id"],
            service="control",
            payload={
                "ack_for": message["msg_id"],
                "applied": updated,
            },
        )

    def handle_message(self, message, addr):
        msg_type = message.get("type")

        if msg_type == "HELLO":
            print(f"[{self.node_id}] Received HELLO from {message['node_id']}")
            self.send_message(
                msg_type="ACK",
                destination=message["node_id"],
                service="handshake",
                payload={"ack_for": message["msg_id"]},
            )

        elif msg_type == "TELEMETRY_REQUEST":
            print(f"[{self.node_id}] Telemetry requested by {message['node_id']}")
            self.send_telemetry(destination=message["node_id"])

        elif msg_type == "CONTROL_COMMAND":
            print(f"[{self.node_id}] Control command from {message['node_id']}")
            self.handle_control_command(message)

        else:
            print(f"[{self.node_id}] Unknown message type: {msg_type}")

    def run(self):
        print(f"[{self.node_id}] Running...")

        # Start background threads
        threading.Thread(target=self.simulate_state, daemon=True).start()
        threading.Thread(target=self.telemetry_loop, daemon=True).start()

        # Main receive loop
        while True:
            data, addr = self.sock.recvfrom(4096)
            try:
                message = json.loads(data.decode())
                self.handle_message(message, addr)
            except json.JSONDecodeError:
                print(f"[{self.node_id}] Received malformed message")


if __name__ == "__main__":
    turbine = TurbineNode(
        node_id="TURBINE_1",
        listen_port=6001,
        satellite_addr=("127.0.0.1", 5001),
        telemetry_interval=5,
    )
    turbine.run()