# PHANTOMNET: Threat Model, Assumptions, and Operational Limitations

This document provides an explicit, adversarial assessment of PHANTOMNET's threat model, security guarantees, and operational limits. Rigorous circumspection is mandatory: overstating security claims in anti-censorship systems puts users at direct risk.

---

## 1. Threat Model

PHANTOMNET models an **on-path, active network adversary** (e.g., a state-level censor, ISP inspection gateway, or hostile transit autonomous system) situated between the client (`YOU`) and the edge relay or tunnel egress (`SERVER`).

### Adversary Capabilities
- **Full Eavesdropping:** Can observe all packet transmissions in both directions (client-to-server TX and server-to-client RX).
- **Metadata Inspection:** Can accurately measure packet sizes (byte lengths), inter-packet arrival gaps (timing in milliseconds), burst sequences, and total flow duration.
- **Active Traffic Manipulation:** Can selectively inject drops, throttle throughput via token-bucket rate limits, delay packets (jitter injection), or terminate connections via TCP RST / link severance.
- **Machine Learning Classification:** Employs statistical classifiers (Random Forests with metadata feature vectors) and deep neural architectures (1D Convolutional Neural Networks on packet sequences) trained to identify target application services or visited destinations.
- **Adversarial Retraining:** Periodically retrains detection models on observed traffic, including traffic shaped by defense mechanisms.

### Adversary Limitations (Out of Scope for Censor)
- The adversary **cannot break modern cryptographic primitives** (X25519, ChaCha20-Poly1305, BLAKE2s).
- The adversary does **not possess endpoint compromise** (no access to client or server memory, unencrypted socket buffers, or private keys).

---

## 2. Security Guarantees & Defenses

1. **Cryptographic Confidentiality & Integrity:**
   - Driven by the audited Noise Protocol Framework (Noise XX handshake).
   - Mutual public-key authentication ensures the client only talks to the authenticated server and vice versa.
   - Ephemeral Diffie-Hellman exchanges ensure Perfect Forward Secrecy (PFS).
   - Authenticated Encryption with Associated Data (AEAD) ChaCha20-Poly1305 guarantees payload confidentiality and bit-tamper detection. Any 1-bit corruption immediately rejects the frame.
   - Strict sliding-window replay protection (RFC 6479 / RFC 4303) ensures resent packets are rejected without decryption.
   - Monotonic packet-count and temporal rekeying prevents nonce reuse across long-lived flows.

2. **Metadata Obfuscation (Mask Engine):**
   - Reshapes packet length barcodes and inter-arrival timing via bucketized padding, random jitter, dummy packet injection, and burst slicing.
   - CMA-ES evolutionary parameter optimization tunes the defense against active classifiers while balancing bandwidth overhead and latency penalty.

---

## 3. Operational Limitations & Non-Goals

PHANTOMNET is an experimental research platform, adversarial testbed, and protocol prototype. **It is NOT a drop-in commercial VPN replacement.**

### 3.1 What the Simulator & Testbed Do Not Capture
- **OS TCP/IP Stack Fingerprinting:** Real-world middleboxes may analyze OS-specific TCP options, SYN packet window sizes, TCP timestamps, and initial TTL values. PHANTOMNET operates above the transport layer (via user-space loopback sockets) and does not normalize low-level kernel TCP headers.
- **AS-Level BGP Hijacking & Route Poisoning:** The simulation models link latency, loss, and throttle, but does not simulate global inter-domain routing attacks (BGP prefix hijacking or DNS cache poisoning at authoritative root servers).
- **Active Flow Watermarking:** Advanced active censors that intentionally modulate packet timing to trace flows across multiple hops (timing watermarking) are not currently modeled in the Censor Lab.

### 3.2 Evaluation Scope: Results Hold Against Tested Models Only
- Detection metrics (AUC, F1-score, accuracy) reported in `/evidence/ml/ablation.json` and `/evidence/REPORT.md` reflect performance against the implemented Censor suite:
  1. `RuleBasedCensor`: MTU-packing, burst ratio, and cadence heuristics.
  2. `RandomForestCensor`: 42-dimensional statistical metadata feature extractor.
  3. `OneDCNNCensor`: Temporal convolutional sequence classifier.
  4. `AdaptiveCensor`: Online moving-average score accumulator with dynamic retraining.
- **No claim of universal stealth is made (unsupported; evidence/ml).** A censor deploying an unmodeled classifier does not guarantee evasion and may detect shaped flows (e.g., deep Transformer models trained on terabytes of live ISP captures, or multi-modal timing-volume correlations).

### 3.3 No Kernel Killswitch (Fail-Open Risk)
- Commercial VPN clients install kernel network filter drivers (WFP on Windows, `iptables`/`nftables` on Linux, pf on macOS) that hard-block all outgoing traffic if the tunnel drops.
- PHANTOMNET is a user-space application. If the tunnel disconnects, unproxied client processes may fail open or leak packets directly to the default gateway unless an external firewall rule is enforced.

### 3.4 No DNS or IPv6 Leak Mitigation
- The SOCKS5 interface accepts hostname-based connection requests (`ATYP = 0x03`), passing domain names through the encrypted tunnel for remote resolution.
- However, client operating systems or misconfigured applications may issue local UDP DNS queries (port 53) to host resolvers before routing to SOCKS5.
- PHANTOMNET does not intercept or encapsulate native IPv6 packets unless explicitly forwarded through the SOCKS5 proxy.
- WebRTC STUN/TURN queries executed within client browsers can bypass SOCKS5 proxies and reveal the client's public IP address.

### 3.5 The Retrained Censor Arms Race
- As demonstrated in our 10-seed ablation study (evidence/ml, ROOT_CAUSE.md):
  - Against a **static** censor, the learned empirical morphing policy achieves modest variation in detection metrics (`AUC = 0.9981`, `TPR@1%FPR = 0.9950`), but does not achieve statistically significant evasion over random shaping (paired t-test $p = 0.194$).
  - When the adversary **retrains** on shaped flows, the censor recovers full detection accuracy (`AUC = 1.0000`, `TPR@1%FPR = 1.0000`).
- Traffic morphing is an **arms race**, not a static victory. Static feature masking provides transient evasion against frozen models, but does not survive adversarial retraining.

