# PHANTOMNET Data Audit (Gate 0)

**Audit Date:** 2026-11-03  
**Auditor:** Antigravity Autonomous Coding Agent  
**Audit Scope:** `backend/phantomnet/data/traces.py`, `backend/phantomnet/ml/ablation.py`, `evidence/ml/ablation.json`

---

## 1. Trace Origin & Provenance Statement

**Every trace used in the prior Phase 4 ablation study was 100% SYNTHETIC, generated purely by procedural generation in code.**

None of the traces in `evidence/ml/ablation.json` originated from:
- (a) A real browser session routed through the live tunnel, OR
- (b) A real browser session direct to the Internet.

All prior traces originated from:
- **(c) A synthetic pseudo-random procedural generator (`generate_synthetic_site_flow` in `backend/phantomnet/data/traces.py`).**

---

## 2. Forensic Code Breakdown & Flaws Identified

### 2.1 The Synthetic Generator
In `backend/phantomnet/data/traces.py`, traces were synthesized by:
```python
def generate_synthetic_site_flow(
    site_id: str,
    category: str,
    is_tunnel: bool,
    seed: int,
    num_packets: int = 120,
) -> FlowTrace: ...
```
This function generated synthetic packet sizes and delta timestamps from fixed heuristic loops (e.g., video: 85% RX MTU packets, tech: 60% RX chunks).

### 2.2 Severe Labeling Flaw in `ablation.py`
In `backend/phantomnet/ml/ablation.py` (lines 82–104):
1. `train_flows`, `val_flows`, and `test_flows` were ALL instantiated with `is_tunnel=False`:
   ```python
   train_flows = [
       generate_synthetic_site_flow(s["site_id"], s["category"], is_tunnel=False, seed=seed + i)
       for i, s in enumerate(train_sites)
   ]
   ```
2. Ground-truth labels were then assigned as arbitrary modulo-2 parity:
   ```python
   y_train = np.array([1 if i % 2 == 0 else 0 for i in range(len(train_flows))])
   y_test = np.array([1 if i % 2 == 0 else 0 for i in range(len(test_flows))])
   ```
3. Because the inputs were all non-tunnel synthetic flows from disjoint sites, the classifier was trained on arbitrary alternating labels against site-specific random seeds.

### 2.3 Statistical Sample Size
- Total unique sites in prior dataset: **30 sites**
- Total test flows evaluated per seed: **6 flows** (3 positive, 3 negative)
- Sample size of $N=6$ with disjoint sites resulted in meaningless AUC scores ($0.25 \pm 0.3725$), where a single misclassification swung the metric by $>16\%$.

---

## 3. Flow Counts Per Class Per Site in Prior Dataset

| Site Category | Site ID | Prior Trace Source | Tunnel Flows (Class 1) | Direct Flows (Class 0) | Total |
|---|---|---|:---:|:---:|:---:|
| Video Streaming | `video-stream-01` .. `06` | Synthetic Generator | 0 (assigned by `i%2`) | 1 (assigned by `i%2`) | 1/site |
| Tech / Dev | `tech-dev-01` .. `06` | Synthetic Generator | 0 (assigned by `i%2`) | 1 (assigned by `i%2`) | 1/site |
| News & Media | `news-media-01` .. `06` | Synthetic Generator | 0 (assigned by `i%2`) | 1 (assigned by `i%2`) | 1/site |
| E-Commerce | `shop-retail-01` .. `06` | Synthetic Generator | 0 (assigned by `i%2`) | 1 (assigned by `i%2`) | 1/site |
| Cloud / Chat | `cloud-chat-01` .. `06` | Synthetic Generator | 0 (assigned by `i%2`) | 1 (assigned by `i%2`) | 1/site |
| **Total** | **30 sites** | **100% Synthetic** | **15 pseudo-labels** | **15 pseudo-labels** | **30 total** |

---

## 4. Remediation Plan

1. **Gate 1:** Author rigorous unit tests validating that ROC-AUC is mathematically consistent:
   - Positive class = `"tunnel"` ($y = 1$)
   - Scorer probability = $P(\text{tunnel})$
   - Perfect classifier $\to \text{AUC} = 1.0$
   - Inverted classifier $\to \text{AUC} = 0.0$
   - Constant classifier $\to \text{AUC} = 0.5$
   - Permutation test ($1,000$ label shuffles) produces $\text{mean} \approx 0.5$ ($p > 0.05$).
2. **Gate 2:** Replace the synthetic generator with a real traffic capture pipeline capturing $\ge 60$ distinct sites/pages ($\ge 20$ flows per site per class for tunnel vs direct) using Playwright through the live tunnel proxy vs direct.
3. **Gate 3:** Prove that the random forest censor achieves $\text{AUC} \ge 0.90$ with a 95% bootstrap lower bound $> 0.80$ on held-out sites before any defense tuning.

