# RouteLab — Use Case Model

This document outlines the core actors and interactions supported by RouteLab for students, instructors, and network algorithm researchers.

```mermaid
flowchart LR
    classDef actorStyle fill:#2A5298,stroke:#B87333,stroke-width:2px,color:#FFFFFF
    classDef usecaseStyle fill:#FCFAF6,stroke:#B87333,stroke-width:1.5px,color:#1E1E1E

    Student("Student / Researcher"):::actorStyle
    Instructor("Instructor / Evaluator"):::actorStyle
    Adversary("Adversary Node"):::actorStyle

    subgraph RouteLab System
        UC1(["Select Course Topology<br/>(6, 8, 10-node, WAN)"]):::usecaseStyle
        UC2(["Load Protocol Plugin<br/>(DV, LS, BGP, Custom)"]):::usecaseStyle
        UC3(["Control Simulation Timeline<br/>(Run, Pause, Step, Speed)"]):::usecaseStyle
        UC4(["Inject Dynamic Perturbations<br/>(Sever Link, Cost, Crash)"]):::usecaseStyle
        UC5(["Trace Golden Quill Path &<br/>Detect Loops/Blackholes"]):::usecaseStyle
        UC6(["Side-by-Side Algorithm Benchmark<br/>(DV vs LS vs Flooding)"]):::usecaseStyle
        UC7(["Export Evaluation Artifacts<br/>(CSV, JSON, PDF Report)"]):::usecaseStyle
        UC8(["Run Interactive Guided Demo"]):::usecaseStyle
        UC9(["Inject Route Poisoning Attack"]):::usecaseStyle
        UC10(["Activate Cryptographic Defense"]):::usecaseStyle
        UC11(["Grade Convergence & Overhead"]):::usecaseStyle
    end

    Student --> UC1
    Student --> UC2
    Student --> UC3
    Student --> UC4
    Student --> UC5
    Student --> UC6
    Student --> UC7
    Student --> UC8

    Adversary --> UC9
    Student --> UC10

    Instructor --> UC6
    Instructor --> UC7
    Instructor --> UC11
```

## Actor Descriptions

- **Student / Researcher**:
  - Tests distance vector, link state, and BGP routing convergence under identical network conditions.
  - Interactively severs links or crashes nodes to observe failover behavior.
  - Inspects per-node routing tables, Link State Databases (LSDB), and AS_PATH attributes.
  - Develops custom protocol plugins adhering to the `RoutingProtocol` ABC.

- **Instructor / Evaluator**:
  - Executes standardized course scenarios (6/8/10 node topologies).
  - Grades protocol correctness against the NetworkX shortest-path oracle.
  - Evaluates message overhead, convergence duration, byte footprint, and route flaps.

- **Adversary Node**:
  - Simulates a compromised router injecting forged distance vectors with cost 1 to poison routing tables and hijack traffic.
