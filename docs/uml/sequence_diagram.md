# RouteLab — Sequence Diagram

This document illustrates the execution lifecycle: scheduled link failure, triggered protocol response, LinkEmulator packet delivery, and convergence detection.

```mermaid
sequenceDiagram
    autonumber
    actor User as User / ScenarioRunner
    participant Engine as SimulationEngine
    participant Clock as Clock (Virtual/Real)
    participant NodeA as RouterNode (R1)
    participant RunnerA as IsolatedProtocolRunner (R1)
    participant ProtocolA as RoutingProtocol (R1)
    participant Link as LinkEmulator (R1<->R2)
    participant NodeB as RouterNode (R2)
    participant RunnerB as IsolatedProtocolRunner (R2)
    participant ProtocolB as RoutingProtocol (R2)
    participant Store as EventStore

    %% Step 1: Link Failure Mutation
    Note over User, Engine: At simulation time t = 1.0s
    User->>Engine: inject_link_state(R1, R2, up=False)
    Engine->>Link: is_up = False
    Engine->>Store: append(LINK_STATE, "R1<->R2", is_up=False)
    Engine->>NodeA: notify_link_change("R2", cost=999999, up=False)
    Engine->>NodeB: notify_link_change("R1", cost=999999, up=False)

    %% Step 2: Protocol Reaction at Node A
    NodeA->>RunnerA: on_link_change("R2", cost=999999, up=False)
    RunnerA->>ProtocolA: on_link_change("R2", 999999, False)
    Note over ProtocolA: Compute new routes.<br/>Triggered update needed!
    ProtocolA->>NodeA: ctx.broadcast(poisoned_update)

    %% Step 3: Link Transmission & Queueing
    loop For each neighbor of R1 (e.g. R3)
        NodeA->>Store: append(PACKET_SENT, "R1", payload)
        NodeA->>Link: transmit(packet, delivery_callback)
        Link->>Clock: schedule(total_delay, deliver_callback)
    end

    %% Step 4: Virtual / Real-time Progression
    Note over Clock: Clock advances by latency + jitter
    Clock->>Link: execute deliver_callback()
    Link->>NodeB: receive_packet(packet)
    NodeB->>Store: append(PACKET_DELIVERED, "R2", packet)

    %% Step 5: Neighbor Protocol Update
    NodeB->>RunnerB: on_message("R1", payload)
    RunnerB->>ProtocolB: on_message("R1", payload)
    Note over ProtocolB: Table updated.<br/>No further flaps.

    %% Step 6: Convergence Detection
    loop Engine periodic monitor
        Engine->>Engine: check_convergence()
        Note over Engine: In-flight messages == 0 &<br/>Quiescence window satisfied
        Engine->>Store: append(CONVERGENCE, "engine", record)
        Engine-->>User: Broadcast WebSocket delta (CONVERGED)
    end
```
