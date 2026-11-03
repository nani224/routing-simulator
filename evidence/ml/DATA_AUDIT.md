# PHANTOMNET Data Audit: Provenance & Experimental Baseline (Gate 0 & Gate A)

**Audit Date:** 2026-11-03  
**Auditor:** Antigravity Autonomous Coding Agent  
**Dataset Name:** `PHANTOMNET_REAL_TRAFFIC_60SITES_TLS13`  
**Storage Location:** `/evidence/ml/captures/flows_dataset.json`  
**Manifest:** `/evidence/ml/manifest.json`  

---

## 1. Trace Origin & Honest Provenance Statement

In strict adherence to Gate A and scientific honesty standards:

1. **Not External Websites:** None of the traces in the dataset represent live web browsing to external public Internet destinations (e.g. youtube.com, cnn.com). There was no external WAN capture.
2. **Locally Served Site Profiles:** All 2,400 traces in the dataset are generated using **60 locally served site profiles** running over genuine loopback TCP sockets (`127.0.0.1`).
3. **Genuine Protocol Exchanges:** The traffic is NOT synthetic tabular data or random numbers. Every flow is produced by real network sockets sending real bytes over the wire, captured via an intercepting TCP tap:
   - **Direct Class (Negative Class):** Genuine **TLS 1.3 HTTPS (`RFC 8446`)** served via Python's standard `ssl` library using an ephemeral elliptic-curve (SECP256R1) self-signed X.509 certificate. The client and server perform a real TLS 1.3 handshake (`ClientHello`, `ServerHello`, `EncryptedExtensions`, `Certificate`, `CertificateVerify`, `Finished`), followed by encrypted application data records.
   - **Tunnel Class (Positive Class):** Genuine **Noise XX mutual authentication handshake** (Curve25519, ChaCha20-Poly1305, BLAKE2s) followed by framed, encrypted application records carrying the identical HTTP payloads over loopback TCP sockets.

---

## 2. Category & Site Profile Distribution

The dataset spans **60 distinct site profiles** partitioned evenly across 5 real-world traffic archetypes:

| Category | Sites Count | Profile IDs | Response Size Range | Traffic Characteristics |
|---|:---:|---|:---:|---|
| **Video Streaming** | 12 | `video-profile-01` .. `12` | 40,000 – 80,000 bytes | Large payload chunks, high MTU RX packet density, burst downloads |
| **Tech / Developer** | 12 | `tech-profile-01` .. `12` | 2,000 – 8,000 bytes | Mixed JSON/code assets, bidirectional small requests, medium responses |
| **News & Media** | 12 | `news-profile-01` .. `12` | 8,000 – 25,000 bytes | Text + image multi-part chunking, staggered RX bursts |
| **E-Commerce / Shopping** | 12 | `shop-profile-01` .. `12` | 3,000 – 12,000 bytes | Catalog payloads, image thumbnails, frequent small requests |
| **Cloud & Real-Time Chat** | 12 | `chat-profile-01` .. `12` | 200 – 1,500 bytes | Interactive small packets, bidirectional messaging, short inter-arrival gaps |

---

## 3. Flow Counts Per Class Per Site

For every one of the 60 site profiles, exactly 20 Direct TLS 1.3 flows and 20 Tunnel flows are captured:

| Category | Site IDs | Direct TLS 1.3 Flows ($y = 0$) | Noise XX Tunnel Flows ($y = 1$) | Total Flows |
|---|---|:---:|:---:|:---:|
| Video Streaming | `video-profile-01` to `video-profile-12` (12 sites) | 240 (20/site) | 240 (20/site) | 480 |
| Tech / Dev | `tech-profile-01` to `tech-profile-12` (12 sites) | 240 (20/site) | 240 (20/site) | 480 |
| News & Media | `news-profile-01` to `news-profile-12` (12 sites) | 240 (20/site) | 240 (20/site) | 480 |
| E-Commerce | `shop-profile-01` to `shop-profile-12` (12 sites) | 240 (20/site) | 240 (20/site) | 480 |
| Cloud Chat | `chat-profile-01` to `chat-profile-12` (12 sites) | 240 (20/site) | 240 (20/site) | 480 |
| **Total** | **60 Distinct Profiles** | **1,200 flows** | **1,200 flows** | **2,400 flows** |

---

## 4. Disjoint Site Split Strategy

To guarantee that classifiers cannot memorize site-specific artifact signatures or size constants, evaluations use **disjoint site-level splits**:

- **Train Set:** 40 sites (8 per category) $\to$ **1,600 flows** (800 direct, 800 tunnel)
- **Validation Set:** 10 sites (2 per category) $\to$ **400 flows** (200 direct, 200 tunnel)
- **Test Set:** 10 sites (2 per category) $\to$ **400 flows** (200 direct, 200 tunnel)

Zero sites in the test or validation sets appear in the training partition. All statistical confidence intervals are computed using **1,000-iteration site-level cluster bootstrapping** to account for intra-site correlations.

---

## 5. Prior Flaw & Remediation Summary

| Issue in Phase 4 Initial Run | Root Cause | Remediation in Gate A & Rework 2 |
|---|---|---|
| **Negative class was plaintext HTTP/1.1** | Test server served cleartext HTTP | Replaced with TLS 1.3 HTTPS with EC certificate |
| **Handshake bin shortcut** | Noise handshake (96/144/128B) vs HTTP GET | TLS 1.3 handshake provides realistic encrypted negative class baseline |
| **Synthetic modulo-2 labels** | `y = i % 2` applied to identical site traces | Real label mapping: Direct TLS 1.3 ($y=0$), Tunnel ($y=1$) |
| **Sample size of $N=6$ flows** | Only 6 flows tested per seed | Expanded to 2,400 real flows across 60 sites |
| **Fixed-threshold evasion claim** | F1 shift reported as evasion | Switched to threshold-free metrics (ROC-AUC, TPR @ 1% FPR) |
