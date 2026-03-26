import socket
import json
import time
import threading
import random
from satellite_network import closest_satellite_to_point, optimal_satellite_route


class TurbineNode:
    def __init__(self, node_id, listen_port, satellite_addr, telemetry_interval=5):
        self.node_id = node_id
        self.listen_port = listen_port
        self.satellite_addr = satellite_addr

        self.state = {
            "wind_speed": 12.5,
            "rpm": 1500,
            "temperature": 45.0,
            "vibration": 0.3,
            "yaw_angle": 0.0,
            "pitch_angle": 5.0,
        }

        # Offshore turbine location (Irish Sea)
        self.latitude = 53.5
        self.longitude = -5.0

        # Control station location
        self.control_lat = 51.5
        self.control_lon = -0.1

        # Satellite routing cache
        self._best_satellite = None
        self._best_satellite_id = "unknown"
        self._satellite_last_updated = 0
        self.SATELLITE_REFRESH_INTERVAL = 30

        self.msg_counter = 0
        self.telemetry_interval = telemetry_interval

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", self.listen_port))

        print(f"[{self.node_id}] Listening on port {self.listen_port}")

    def _next_msg_id(self):
        self.msg_counter += 1
        return self.msg_counter

    def _get_best_satellite_addr(self):
        """
        Use Dijkstra via satellite_network to find the optimal satellite
        relay between this turbine and the control station.
        Falls back to configured satellite_addr if routing fails.
        """
        now = time.time()
        if self._best_satellite and (now - self._satellite_last_updated) < self.SATELLITE_REFRESH_INTERVAL:
            return self._best_satellite

        try:
            route = optimal_satellite_route(
                self.latitude,
                self.longitude,
                self.control_lat,
                self.control_lon,
            )
            # node_path looks like ['SRC', 'SAT-003', ..., 'DST']
            first_sat_id = route.node_path[1]
            print(f"[{self.node_id}] Optimal route via {first_sat_id} ({route.total_distance_km:.0f} km total)")
            self._best_satellite = self.satellite_addr
            self._best_satellite_id = first_sat_id
            self._satellite_last_updated = now
        except Exception as e:
            print(f"[{self.node_id}] Satellite routing failed: {e} — using default")
            self._best_satellite = self.satellite_addr
            self._best_satellite_id = "unknown"

        return self._best_satellite

    def _raw_send(self, message):
        """Send to the best satellite, tagging the message with the chosen route."""
        addr = self._get_best_satellite_addr()
        message["route_via"] = self._best_satellite_id
        data = json.dumps(message).encode()
        self.sock.sendto(data, addr)

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
        self._raw_send(message)
        print(f"[{self.node_id}] Sent {msg_type} to {destination} via {self._best_satellite_id}")

    def send_telemetry(self, destination="CONTROL_1"):
        self.send_message(
            msg_type="TELEMETRY",
            destination=destination,
            service="telemetry",
            payload=self.state.copy(),
        )

    def satellite_route_updater(self):
        """Periodically recalculates the optimal satellite route in the background."""
        while True:
            self._get_best_satellite_addr()
            time.sleep(self.SATELLITE_REFRESH_INTERVAL)

    def simulate_state(self):
        while True:
            self.state["wind_speed"] = max(0, self.state["wind_speed"] + random.uniform(-1.0, 1.0))
            self.state["rpm"] = max(0, self.state["rpm"] + random.uniform(-50, 50))
            self.state["temperature"] = max(0, self.state["temperature"] + random.uniform(-0.5, 0.5))
            self.state["vibration"] = max(0, round(self.state["vibration"] + random.uniform(-0.05, 0.05), 3))
            time.sleep(1)

    def telemetry_loop(self):
        while True:
            time.sleep(self.telemetry_interval)
            print(f"[{self.node_id}] Auto telemetry | wind={self.state['wind_speed']:.1f} rpm={self.state['rpm']:.0f} temp={self.state['temperature']:.1f}")
            self.send_telemetry()

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
            payload={"ack_for": message["msg_id"], "applied": updated},
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
        elif msg_type == "DISCOVERY":
            print(f"[{self.node_id}] DISCOVERY from {message['node_id']}")
            self.send_message(
                msg_type="DISCOVERY_RESPONSE",
                destination=message["node_id"],
                service="discovery",
                payload={
                    "node_id": self.node_id,
                    "node_type": "TURBINE",
                    "listen_port": self.listen_port,
                    "services": ["telemetry", "control", "handshake"],
                    "sensors": list(self.state.keys()),
                    "protocol_version": "1.0",
                },
            )
        elif msg_type == "SENSOR_DATA":
            payload = message.get("payload", {}) # Sensor node is reporting — merge into turbine state
            for key in ["vibration", "temperature", "wind_speed"]:
                if key in payload:
                    self.state[key] = payload[key]
            print(f"[{self.node_id}] Sensor update received from {message['node_id']}")

        elif msg_type == "BLADE_STATUS":
        # Blade actuator reporting current position
            payload = message.get("payload", {})
            print(f"[{self.node_id}] Blade status — yaw={payload.get('current_yaw')} pitch={payload.get('current_pitch')} moving={payload.get('moving')}")
        
        elif msg_type == "NEGOTIATE":
            print(f"[{self.node_id}] NEGOTIATE from {message['node_id']}")
            self.send_message(
                msg_type="NEGOTIATE_RESPONSE",
                destination=message["node_id"],
                service="negotiation",
                payload={
                    "node_id": self.node_id,
                    "telemetry_interval_s": self.telemetry_interval,
                    "controllable": ["yaw_angle", "pitch_angle"],
                    "sensor_data": list(self.state.keys()),
                    "supports_buffering": True,
                    "channel_model": "LEO_satellite",
                },
            )
        elif msg_type == "AGREE":
            print(f"[{self.node_id}] AGREEMENT with {message['node_id']}: {message.get('payload', {})}")
            self.send_message(
                msg_type="ACK",
                destination=message["node_id"],
                service="agreement",
                payload={"ack_for": message["msg_id"], "status": "ACCEPTED"},
            )
        else:
            print(f"[{self.node_id}] Unknown message type: {msg_type}")

    def run(self):
        print(f"[{self.node_id}] Running...")
        threading.Thread(target=self.simulate_state, daemon=True).start()
        threading.Thread(target=self.telemetry_loop, daemon=True).start()
        threading.Thread(target=self.satellite_route_updater, daemon=True).start()

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
        listen_port=6002,
        satellite_addr=("127.0.0.1", 6001),
        telemetry_interval=5,
    )
    turbine.run()