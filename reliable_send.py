import socket
import struct
import random
import time
import zlib
from typing import Optional, Tuple


DROP_PROBABILITY = 0.0307
MAX_PAYLOAD = 1024
ACK_TIMEOUT = 0.3

# Packet types
TYPE_DATA = 1
TYPE_ACK = 2
TYPE_FIN = 3
TYPE_FIN_ACK = 4

# Header format:
#   type     : 1 byte
#   seq      : 4 bytes
#   length   : 2 bytes
#   checksum : 4 bytes
HEADER_FMT = "!BIHI"
HEADER_SIZE = struct.calcsize(HEADER_FMT)


def should_drop() -> bool:
    """Randomly decide whether to drop a packet."""
    return random.random() < DROP_PROBABILITY


def checksum(data: bytes) -> int:
    """Compute CRC32 checksum."""
    return zlib.crc32(data) & 0xFFFFFFFF


def make_packet(pkt_type: int, seq: int, payload: bytes = b"") -> bytes:
    """Build a packet with header + payload."""
    length = len(payload)
    csum = checksum(payload)
    header = struct.pack(HEADER_FMT, pkt_type, seq, length, csum)
    return header + payload


def parse_packet(packet: bytes) -> Tuple[int, int, bytes]:
    """Parse and validate a packet."""
    if len(packet) < HEADER_SIZE:
        raise ValueError("Packet too short")

    pkt_type, seq, length, csum = struct.unpack(HEADER_FMT, packet[:HEADER_SIZE])
    payload = packet[HEADER_SIZE:]

    if len(payload) != length:
        raise ValueError("Invalid payload length")

    if checksum(payload) != csum:
        raise ValueError("Checksum mismatch")

    return pkt_type, seq, payload


class UnreliableUDPSocket:
    """
    Wrapper around a UDP socket that randomly drops packets to simulate
    an unreliable channel.
    """

    def __init__(self, sock: socket.socket, drop_probability: float = DROP_PROBABILITY):
        self.sock = sock
        self.drop_probability = drop_probability

    def sendto(self, data: bytes, addr: Tuple[str, int]) -> int:
        if random.random() < self.drop_probability:
            # Simulate silent drop
            return len(data)
        return self.sock.sendto(data, addr)

    def recvfrom(self, bufsize: int) -> Tuple[bytes, Tuple[str, int]]:
        while True:
            data, addr = self.sock.recvfrom(bufsize)
            if random.random() < self.drop_probability:
                # Simulate dropped incoming packet by ignoring it
                continue
            return data, addr

    def settimeout(self, value: Optional[float]) -> None:
        self.sock.settimeout(value)

    def bind(self, addr: Tuple[str, int]) -> None:
        self.sock.bind(addr)

    def close(self) -> None:
        self.sock.close()


class ReliableUDP:
    """
    Stop-and-wait reliable transport over UDP.
    """

    def __init__(self, local_addr: Tuple[str, int], peer_addr: Optional[Tuple[str, int]] = None):
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock = UnreliableUDPSocket(raw_sock)
        self.sock.bind(local_addr)
        self.peer_addr = peer_addr

        self.send_seq = 0
        self.expected_seq = 0

    def _send_ack(self, seq: int, addr: Tuple[str, int]) -> None:
        ack = make_packet(TYPE_ACK, seq)
        self.sock.sendto(ack, addr)

    def _send_fin_ack(self, seq: int, addr: Tuple[str, int]) -> None:
        fin_ack = make_packet(TYPE_FIN_ACK, seq)
        self.sock.sendto(fin_ack, addr)

    def send(self, data: bytes) -> None:
        """
        Reliably send bytes to the peer.
        """
        if self.peer_addr is None:
            raise ValueError("peer_addr must be set before sending")

        for offset in range(0, len(data), MAX_PAYLOAD):
            chunk = data[offset:offset + MAX_PAYLOAD]
            packet = make_packet(TYPE_DATA, self.send_seq, chunk)

            while True:
                self.sock.sendto(packet, self.peer_addr)
                self.sock.settimeout(ACK_TIMEOUT)

                try:
                    raw, addr = self.sock.recvfrom(65535)
                    pkt_type, seq, _ = parse_packet(raw)

                    if addr != self.peer_addr:
                        continue

                    if pkt_type == TYPE_ACK and seq == self.send_seq:
                        self.send_seq += 1
                        break

                except socket.timeout:
                    # Retransmit
                    continue
                except ValueError:
                    # Corrupted packet; ignore and wait/retransmit
                    continue

        self._send_fin()

    def _send_fin(self) -> None:
        """Send end-of-stream marker reliably."""
        fin = make_packet(TYPE_FIN, self.send_seq)

        while True:
            self.sock.sendto(fin, self.peer_addr)
            self.sock.settimeout(ACK_TIMEOUT)

            try:
                raw, addr = self.sock.recvfrom(65535)
                pkt_type, seq, _ = parse_packet(raw)

                if addr != self.peer_addr:
                    continue

                if pkt_type == TYPE_FIN_ACK and seq == self.send_seq:
                    self.send_seq += 1
                    break

            except socket.timeout:
                continue
            except ValueError:
                continue

    def recv(self) -> bytes:
        """
        Reliably receive a byte stream until FIN is received.
        """
        received = bytearray()

        while True:
            self.sock.settimeout(None)
            raw, addr = self.sock.recvfrom(65535)

            if self.peer_addr is None:
                self.peer_addr = addr

            if addr != self.peer_addr:
                # Ignore packets from unknown peers
                continue

            try:
                pkt_type, seq, payload = parse_packet(raw)
            except ValueError:
                continue

            if pkt_type == TYPE_DATA:
                if seq == self.expected_seq:
                    received.extend(payload)
                    self._send_ack(seq, addr)
                    self.expected_seq += 1
                else:
                    # Duplicate or out-of-order: re-ACK last good packet
                    if self.expected_seq > 0:
                        self._send_ack(self.expected_seq - 1, addr)

            elif pkt_type == TYPE_FIN:
                if seq == self.expected_seq:
                    self._send_fin_ack(seq, addr)
                    self.expected_seq += 1
                    break
                else:
                    if self.expected_seq > 0:
                        self._send_ack(self.expected_seq - 1, addr)

        return bytes(received)

    def close(self) -> None:
        self.sock.close()


# ----------------------------
# Example usage
# ----------------------------

def run_server(host: str = "127.0.0.1", port: int = 9000) -> None:
    rudp = ReliableUDP((host, port))
    print(f"Server listening on {host}:{port}")
    data = rudp.recv()
    print("Received:")
    print(data.decode("utf-8", errors="replace"))
    rudp.close()


def run_client(server_host: str = "127.0.0.1", server_port: int = 9000) -> None:
    message = (
        "This message is sent over a reliable protocol built on top of UDP.\n"
        "Even though 3.07% of packets are randomly dropped, retransmissions ensure delivery.\n"
    ).encode("utf-8")

    # Bind client to any free UDP port
    rudp = ReliableUDP(("127.0.0.1", 0), (server_host, server_port))
    print(f"Client sending to {server_host}:{server_port}")
    rudp.send(message)
    print("Send complete")
    rudp.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python reliable_send.py server [host] [port]")
        print("  python reliable_send.py client [host] [port]")
        sys.exit(1)

    mode = sys.argv[1].lower()
    host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 9000

    if mode == "server":
        run_server(host, port)
    elif mode == "client":
        run_client(host, port)
    else:
        print("Mode must be 'server' or 'client'")