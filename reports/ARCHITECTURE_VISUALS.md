# 🖼️ FL-DDoS System Architecture (Visuals)

**Purpose:** Pictorial representation of the 12-Phase System for your presentation slides.

---

## 1. High-Level Hub & Spoke Design

This diagram shows how the **Central Server** orchestrates multiple **Edge Clients** while keeping data private.

```mermaid
graph TB
    subgraph Cloud Layer ["☁️ Aggregation Server (Cloud)"]
        Server[Global Aggregator]
        Agents[Multi-Agent Brain]
        Dashboard[Live Dashboard]
    end

    subgraph Edge Layer ["🔒 Edge Clients (Private Data)"]
        C1[Client 1: IoT Node]
        C2[Client 2: Bank Server]
        C3[Client 3: Hospital Net]
    end

    C1 <-->|Encrypted Updates| Server
    C2 <-->|Encrypted Updates| Server
    C3 <-->|Encrypted Updates| Server

    Server <--> Agents
    Server --> Dashboard

    style Server fill:#f9f,stroke:#333,stroke-width:2px
    style C1 fill:#bbf,stroke:#333,stroke-width:2px
    style C2 fill:#bbf,stroke:#333,stroke-width:2px
    style C3 fill:#bbf,stroke:#333,stroke-width:2px
```

---

## 2. The Hybrid Conv-Transformer (Internal Logic)

This is what happens inside the **AI Model** when a packet arrives.

```mermaid
graph LR
    Input[Packet Flow Input] --> Conv[1D CNN Layer]
    Conv -->|Micro-Patterns| Pos[Positional Encoding]
    Pos -->|Time Sequence| Trans[Transformer Encoder]
    Trans -->|Global Context| Attn[Attention Pooling]
    Attn -->|Critical Signal| Class[Classifier Head]
    Class --> Output[Attack / Benign]

    style Input fill:#eee,stroke:#333
    style Conv fill:#ff9,stroke:#333
    style Trans fill:#9f9,stroke:#333
    style Output fill:#f99,stroke:#333
```

---

## 3. Real-Time Attack Response Flow

From **Attacker** to **Defense** in milliseconds.

```mermaid
sequenceDiagram
    participant Attacker
    participant Network as Mininet Switch
    participant Node as AI Node (Client)
    participant Server as FL Server
    participant Admin as Dashboard

    Attacker->>Network: flood_attack()
    Network->>Node: Incoming Packets
    Node->>Node: Hybrid Model Inference
    Node->>Node: ⚠️ Attack Detected!
    Node->>Server: Encrypted Alert
    Server->>Admin: WebSocket Push
    Admin-->>Admin: 🚨 Display RED ALERT
    Server->>Node: Update Policy (Block IP)
```

---

## 4. Zero Trust Security Layers

How we protect the system at every level.

```mermaid
block-beta
    columns 1
    block:L1
        space
        L1Text["Layer 1: Network Isolation (Mininet Namespaces)"]
        space
    end
    down
    block:L2
        space
        L2Text["Layer 2: Local AI (Data stays on device)"]
        space
    end
    down
    block:L3
        space
        L3Text["Layer 3: Homomorphic Encryption (Server blind)"]
        space
    end
    down
    block:L4
        space
        L4Text["Layer 4: Multi-Agent Validation (Anti-Poisoning)"]
        space
    end

    style L1 fill:#dfd
    style L2 fill:#ffd
    style L3 fill:#fed
    style L4 fill:#fdd
```

---

## 📸 For Your Slides:

- **Slide 1 (Overview):** Use Diagram #1 to show the distributed nature.
- **Slide 2 (Innovation):** Use Diagram #2 to explain why your model is better than basic LSTM.
- **Slide 3 (Demo):** Use Diagram #3 to walk through your live demo steps.
