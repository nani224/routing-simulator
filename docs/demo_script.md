# RouteLab — Live Demonstration & Viva Presentation Script

**Project**: RouteLab — Distance Vector, Link State & BGP: A Comparative Routing Simulator  
**Team 20**: Aakarsh, Sravan, Sneha  
**Aesthetic**: Cartographer's Atlas / Drafting Table (Parchment Light & Nautical Blueprint Dark)

---

## Act 1: Introduction & Architecture Walkthrough (1.5 min)

1. **Launch the Application**:
   - Backend: `uvicorn routelab.api.server:create_app --factory --port 8000`
   - Frontend: `http://localhost:4173/` (or `npm run dev`)
2. **Present the Drafting Table Aesthetic**:
   - Explain the "Cartographer's Atlas" visual design: warm antique parchment, compass rose watermark, copper/brass instrumentation, and hand-drawn link textures.
   - Click the **Theme Toggle** in the top instrument bar to demonstrate the **Nautical Blueprint (Dark Mode)** with cyanotype lines and amber sextant needles.
3. **Highlight Zero Protocol Hardcoding**:
   - Mention that the core engine (`SimulationEngine`), dual clocks (`VirtualClock` / `RealtimeClock`), and localhost UDP sockets are completely decoupled from any routing protocol. All protocols run as isolated sandboxed plugins.

---

## Act 2: Course Scenario 1 — Distance Vector vs Link State Convergence (2.0 min)

1. In the top instrument bar, select **Course 6-Node**.
2. Select **Distance Vector (RIP / Bellman-Ford)**.
3. Click **Run**.
   - Observe traveling packet courier particles traversing links.
   - Point out the **Convergence Seal**: Converged in ~0.620s with ~142 control messages.
4. Click the **Compare** button on the instrument bar.
   - Protocol A: `Distance Vector` vs Protocol B: `Link State`.
   - Click **Run Benchmark**.
   - Show the comparative finding: Link State converged in **0.180s** (3.4x faster) with only **88 messages**, demonstrating Dijkstra SPF superiority over iterative vector relaxation.

---

## Act 3: Course Scenario 2 — 8-Node Mesh Failover & Golden Quill Path Tracer (2.0 min)

1. Select **Course 8-Node Mesh** in the topology dropdown.
2. In the **Golden Quill Path Tracer** panel on the left:
   - Source: `R1`, Destination: `R5`.
   - Observe the illuminated golden path: `R1 -> R2 -> R3 -> R4 -> R5`.
3. Click on link `R2 <-> R3` on the canvas to simulate a physical fiber cut.
   - Notice the link instantly transforms into a **dashed severed road** with a red 'X' break icon.
   - The engine automatically detects the topology change and recalculates routes.
   - Watch the Golden Quill path immediately fail over to the redundant bottom ring: `R1 -> R8 -> R7 -> R6 -> R5`!
   - Highlight: Zero routing loops, verified by the NetworkX correctness oracle.

---

## Act 4: Course Scenario 3 — Count-to-Infinity & Poison-Reverse Remedy (2.0 min)

1. Click **Scenarios** in the instrument bar.
2. Click **Launch Scenario: Count-to-Infinity Flaw (RIP Vulnerability)**.
   - A 3-node linear topology (`A - B - C`) loads with link `B - C` severed at t=1.0s and split-horizon disabled.
   - Open the **Node Inspector Drawer** on Router `B`.
   - Show the routing table metric bouncing upward: `2 -> 3 -> 4 -> 5 ... 16 (Infinity)`.
   - In the **Path Tracer**, point out the flashing red alarm: **LOOP DETECTED: [B, A, B]**.
3. Now launch **Count-to-Infinity Remedy: Poison Reverse**:
   - Split Horizon and Poison Reverse are enabled.
   - Show that upon link failure, `A` advertises metric 16 (&infin;) back to `B` immediately.
   - Loop is prevented in 1 single step without any metric explosion!

---

## Act 5: Course Scenario 4 — BGP Tier-1 Peering & Policy Routing (1.5 min)

1. Click **Scenarios** -> **BGP Tier-1 Peering & Policy Routing**.
2. Select **BGP-Lite (Path Vector)**.
3. Click on Router `R1` (AS100) and open the **BGP RIB** tab in the Node Inspector.
   - Show the full `AS_PATH = [100, 200, 300]`.
   - Demonstrate `LOCAL_PREF` routing: Traffic preferentially routes through preferred commercial peers rather than the lowest hop-count path.
   - Point out that BGP loop prevention operates on autonomous system sequences rather than numeric distance metrics.

---

## Act 6: Course Scenario 5 — Route Poisoning Attack & Secure DV Defense (1.5 min)

1. Click **Attacks** on the instrument bar.
2. Under **Route Poisoning Attack**, select victim destination `R6` and click **Inject Poison**.
   - Notice Router `R6` route is poisoned across the network with a forged metric 1.
   - Traffic is redirected to the adversary node.
3. In the Attack modal, click **Activate Defense** (Secure Distance Vector).
   - Cryptographic origin validation and rate-limiting reject the forged advertisement.
   - The network instantly recovers its legitimate shortest paths.

---

## Act 7: Data Export & Conclusion (1.0 min)

1. Click **Export** on the instrument bar:
   - Click **CSV** to download run metrics.
   - Click **JSON** to download machine-readable evaluation data.
   - Click **Print PDF** to show the formatted course summary report.
2. Open the **Simulation Event Stream (Logs)** to display every timestamped event recorded in the append-only event store.
3. Conclude by reiterating:
   - 62 automated tests passing at 87% coverage.
   - Mypy `--strict` compliant.
   - 60 FPS verified on 100-node networks.
