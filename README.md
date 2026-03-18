# CSU33D03
Demonstration of a protocol enabling communication between users and off shore wind turbines via LEO satellites

# Wind Turbine Satellite Communication Network

## Project Overview

This project implements a **distributed communication system for remote wind turbine monitoring and control via a satellite relay network**.

The system simulates a realistic scenario where wind turbines operate in remote environments and communicate with a control station through a **Low Earth Orbit (LEO) satellite relay**.

The primary goal is to design and implement a **custom networking protocol and distributed architecture** capable of:

- Reliable communication over an **unreliable communication channel**
- Monitoring turbine telemetry data
- Sending control commands to turbines
- Simulating real-world network impairments such as latency, packet loss, and outages
- Managing multiple service interactions between system components

The system is built as a **multi-node distributed network application** composed of independent processes communicating over network sockets.

---

# System Architecture

The system consists of three primary nodes:

Control Station  <->  Satellite Relay  <->  Wind Turbine Node

### Control Station

Represents the **operator control centre** responsible for:

- Monitoring turbine telemetry
- Issuing turbine control commands
- Managing communication sessions
- Discovering available turbines and services

### Satellite Relay

Represents the **LEO satellite network layer** responsible for:

- Forwarding messages between nodes
- Simulating realistic communication impairments
- Acting as the intermediary routing node between turbines and control stations

### Wind Turbine Node

Represents a **remote wind turbine** responsible for:

- Simulating sensor telemetry
- Executing control commands
- Maintaining turbine operational state
- Communicating telemetry and status updates to the control station

---

# System Communication Model

All communication between nodes follows this path:

Control Station  
↓  
Satellite Relay  
↓  
Wind Turbine  

The satellite relay acts as an **intermediate network layer**, introducing simulated network conditions while forwarding messages between nodes.

Communication is implemented using **network sockets** and a **custom message protocol**.

---

# Protocol Design

The system implements a **custom application-layer protocol** designed to operate over an unreliable communication channel.

The protocol provides:

- Message identification
- Service-based communication
- Reliability mechanisms
- Session management
- Communication negotiation

---

# Message Structure

All messages follow a standardised structure.

Example message format:

```json
{
  "type": "MESSAGE_TYPE",
  "msg_id": 101,
  "node_id": "NODE_IDENTIFIER",
  "destination": "TARGET_NODE",
  "service": "SERVICE_NAME",
  "timestamp": 1710000000,
  "payload": {}
}
```

### Message Fields

| Field | Description |
|------|-------------|
| type | Type of protocol message |
| msg_id | Unique identifier for the message |
| node_id | Source node identifier |
| destination | Target node identifier |
| service | Target service |
| timestamp | Message creation timestamp |
| payload | Message data |

---

# Protocol Message Types

## Connection & Session Messages

| Message | Description |
|--------|-------------|
| HELLO | Node initialization handshake |
| DISCOVER | Request for available nodes/services |
| SERVICE_ADVERTISEMENT | Response listing available services |
| NEGOTIATE | Communication parameter negotiation |
| AGREEMENT | Confirmation of agreed parameters |
| HEARTBEAT | Connection health check |

---

## Operational Messages

| Message | Description |
|--------|-------------|
| TELEMETRY | Sensor data transmission |
| CONTROL_COMMAND | Actuator control commands |
| ACK | Message acknowledgement |

---

# Reliability Layer

The protocol implements a **lightweight reliability layer** to ensure correct message delivery despite unreliable channel conditions.

### Reliability Mechanisms

- Unique message identifiers
- Message acknowledgement (ACK)
- Timeout detection
- Retransmission of unacknowledged messages
- Duplicate message detection
- Heartbeat monitoring for connection health

These mechanisms ensure that **important control messages are reliably delivered** even in the presence of packet loss.

---

# Network Channel Simulation

The satellite relay simulates realistic communication conditions typical of satellite networks.

### Channel Characteristics

| Parameter | Description |
|---------|-------------|
| Latency | Simulated transmission delay |
| Packet Loss | Random packet drop probability |
| Jitter | Variable delay between messages |
| Outages | Temporary loss of communication |

### Example Simulation Parameters

| Parameter | Example Value |
|---------|-------------|
| Latency | 300–900 ms |
| Packet Loss | 5–10% |
| Outage Duration | 15–30 seconds |

These parameters allow the system to test protocol reliability and resilience.

---

# Turbine Simulation

The wind turbine node simulates a turbine’s operational state.

### Turbine State Variables

- Wind speed
- Rotor RPM
- Turbine temperature
- Structural vibration
- Yaw angle
- Blade pitch angle

Telemetry data is periodically transmitted to the control station.

---

# System Services

The system exposes multiple services to support turbine monitoring and control.

Each service operates on a **separate communication channel**.

## Telemetry Services

| Service | Description |
|-------|-------------|
| Wind Sensor Service | Reports wind speed measurements |
| Vibration & Temperature Service | Reports turbine structural and thermal conditions |

---

## Actuator Services

| Service | Description |
|-------|-------------|
| Yaw Control Service | Adjusts turbine orientation |
| Pitch Control Service | Adjusts blade pitch angle |

Each service communicates over **separate ports or socket instances**.

---

# System Functionality

The complete system supports the following operational capabilities.

### Monitoring

- Continuous telemetry transmission
- Real-time monitoring of turbine state
- Sensor data logging

### Control

- Remote yaw control
- Remote pitch control
- Command acknowledgement

### Communication Management

- Node discovery
- Service advertisement
- Communication negotiation
- Session agreement

### Fault Handling

- Network latency handling
- Packet loss recovery
- Connection timeout detection
- Recovery from communication outages

---

# Development Roadmap

The implementation follows a staged development process.

---

# Phase 1 – Project Initialization

### Repository Setup

- Create project repository
- Define project directory structure
- Create configuration files
- Define dependency requirements
- Establish logging utilities

### Base Project Files

- Configuration module
- Protocol message definitions
- Serialization utilities
- Network utility functions

---

# Phase 2 – Core Communication Layer

### Message Protocol

Tasks:

- Implement message schema
- Implement message serialization/deserialization
- Implement message ID generation
- Implement message validation

### Socket Communication

Tasks:

- Implement socket initialization
- Implement message send/receive functions
- Implement basic message routing

---

# Phase 3 – Satellite Relay Node

Tasks:

- Implement relay server
- Receive incoming messages
- Identify destination nodes
- Forward messages to appropriate targets
- Implement logging for packet flow

Initial version should only perform **basic message forwarding**.

---

# Phase 4 – Basic Node Communication

### Control Station

Tasks:

- Implement message sender
- Implement HELLO handshake
- Implement ACK reception

### Turbine Node

Tasks:

- Implement message listener
- Process incoming HELLO messages
- Respond with acknowledgement

Goal of this phase:

Control Station → Satellite → Turbine → Satellite → Control Station

This establishes the **basic network backbone**.

---

# Phase 5 – Telemetry Services

Tasks:

- Implement wind sensor simulation
- Implement vibration and temperature simulation
- Generate periodic telemetry messages
- Send telemetry to control station

Telemetry should be transmitted at **regular intervals**.

---

# Phase 6 – Control Command Services

Tasks:

- Implement yaw control commands
- Implement pitch control commands
- Validate command parameters
- Update turbine state variables
- Send command acknowledgement messages

---

# Phase 7 – Reliability Mechanisms

Tasks:

- Implement ACK tracking
- Implement message timeout detection
- Implement retransmission logic
- Implement duplicate message filtering

These features allow the protocol to function reliably over an unreliable network.

---

# Phase 8 – Channel Impairment Simulation

Tasks:

- Introduce latency simulation
- Introduce packet loss simulation
- Introduce jitter variation
- Introduce temporary network outages

These impairments are implemented within the **satellite relay node**.

---

# Phase 9 – Discovery and Negotiation

Tasks:

- Implement node discovery messages
- Implement service advertisement
- Implement negotiation of communication parameters
- Implement session agreement confirmation

These mechanisms enable **dynamic system coordination**.

---

# Phase 10 – System Integration

Tasks:

- Integrate all nodes into a unified system
- Verify service communication across nodes
- Verify telemetry flow
- Verify command execution
- Verify reliability mechanisms

---

# Phase 11 – Resilience Testing

Test scenarios include:

- High latency communication
- Packet loss conditions
- Temporary communication outages
- Command retransmission
- Telemetry recovery after reconnection

---

# Phase 12 – Demonstration Scenario

A full system demonstration should include:

1. Control station discovery of turbine  
2. Negotiation of communication parameters  
3. Continuous telemetry transmission  
4. Remote yaw and pitch control commands  
5. Satellite relay introducing latency and packet loss  
6. Protocol reliability mechanisms ensuring message delivery  
7. Recovery from simulated communication outage  

---

# Logging and Monitoring

Each node should maintain logs including:

- Message transmission
- Message reception
- Retransmissions
- Channel impairments
- Command execution

Logs assist debugging and system validation.

---

# Expected Deliverables

The completed system should demonstrate:

- A functioning distributed turbine monitoring network
- Reliable protocol behaviour over an unreliable channel
- Multiple service-based communication interactions
- Realistic network channel simulation
- Control and telemetry functionality
- Robust system behaviour under communication impairments

---

# Repository Structure

project-root

config  
protocol  
nodes  
services  
channel  
utils  
tests  
docs  

---

# Conclusion

This project demonstrates the design and implementation of a **custom distributed networking system for remote wind turbine control** operating over a simulated satellite communication network.

By combining protocol design, distributed architecture, and realistic network simulation, the system explores **reliable communication over unreliable networks**.
