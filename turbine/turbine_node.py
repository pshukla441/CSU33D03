import socket
import json
import time


class TurbineNode:
    def __init__(self, node_id, listen_port, satellite_addr):
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