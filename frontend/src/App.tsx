import React, { useState, useEffect, useCallback, useRef } from 'react';
import type {
  TopologyData,
  ProtocolType,
  RouteEntry,
  PacketCourier,
  SimEventItem,
  ConvergenceRecord,
  TopologyLink,
} from './types';
import { RouteLabApi } from './services/api';
import { TopologyCanvas } from './components/TopologyCanvas';
import { InstrumentBar } from './components/InstrumentBar';
import { NodeInspectorDrawer } from './components/NodeInspectorDrawer';
import { TimelineScrubber } from './components/TimelineScrubber';
import { FailureAttackModal } from './components/FailureAttackModal';
import { CompareWorkbench } from './components/CompareWorkbench';
import { PathTracerPanel } from './components/PathTracerPanel';
import { ScenarioBuilderModal } from './components/ScenarioBuilderModal';
import { VirtualizedPacketLog } from './components/VirtualizedPacketLog';
import { ExportModal } from './components/ExportModal';
import { ExplainModeModal } from './components/ExplainModeModal';
import { SettingsModal } from './components/SettingsModal';

interface HistoricalSnapshot {
  time: number;
  routes: Record<string, RouteEntry[]>;
  telemetry: Record<string, { tx: number; rx: number; flaps: number; isCrashed: boolean }>;
  links: TopologyLink[];
}

export const App: React.FC = () => {
  // Theme state
  const [theme, setTheme] = useState<'light' | 'dark'>('light');

  // Topology & Protocol state
  const [currentTopologyName, setCurrentTopologyName] = useState<string>('course-6-node');
  const [topology, setTopology] = useState<TopologyData>(() =>
    RouteLabApi.getFallbackTopology('course-6-node')
  );
  const [currentProtocol, setCurrentProtocol] = useState<ProtocolType>('distance_vector');

  // Simulation execution state
  const [isRunning, setIsRunning] = useState<boolean>(true);
  const [simTime, setSimTime] = useState<number>(0.0);
  const [speed, setSpeed] = useState<number>(1.0);
  const [isConverged, setIsConverged] = useState<boolean>(false);
  const [convTime, setConvTime] = useState<number>(0.0);
  const [fps, setFps] = useState<number>(60);
  const [isPhysicsActive, setIsPhysicsActive] = useState<boolean>(false);

  // Per-node state & telemetry
  const [selectedNode, setSelectedNode] = useState<string | null>('R1');
  const [allRoutes, setAllRoutes] = useState<Record<string, RouteEntry[]>>({});
  const [nodeTelemetry, setNodeTelemetry] = useState<
    Record<string, { tx: number; rx: number; flaps: number; isCrashed: boolean }>
  >({});
  const [packets, setPackets] = useState<PacketCourier[]>([]);
  const [events, setEvents] = useState<SimEventItem[]>([]);

  // Historical state replay scrubbing
  const stateHistory = useRef<HistoricalSnapshot[]>([]);
  const isScrubbing = useRef<boolean>(false);

  // Path tracer state
  const [activePath, setActivePath] = useState<string[]>([]);
  const [loopDetected, setLoopDetected] = useState<boolean>(false);

  // Modals state
  const [isCompareOpen, setIsCompareOpen] = useState<boolean>(false);
  const [isAttacksOpen, setIsAttacksOpen] = useState<boolean>(false);
  const [isScenariosOpen, setIsScenariosOpen] = useState<boolean>(false);
  const [isLogsOpen, setIsLogsOpen] = useState<boolean>(false);
  const [isExportOpen, setIsExportOpen] = useState<boolean>(false);
  const [isExplainOpen, setIsExplainOpen] = useState<boolean>(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

  // Settings
  const [quiescenceWindow, setQuiescenceWindow] = useState<number>(0.5);
  const [soundEnabled, setSoundEnabled] = useState<boolean>(true);
  const [clockMode, setClockMode] = useState<'virtual' | 'realtime'>('realtime');
  const [wsUrl, setWsUrl] = useState<string>('ws://localhost:8000/ws/simulation');

  // Convergence record
  const [convergenceRecord, setConvergenceRecord] = useState<ConvergenceRecord | null>(null);

  // Sync theme attribute to HTML root
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Sound synthesis utility (Web Audio API)
  const playChime = useCallback(
    (type: 'click' | 'converge' | 'attack') => {
      if (!soundEnabled) return;
      try {
        const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);

        if (type === 'click') {
          osc.frequency.setValueAtTime(600, audioCtx.currentTime);
          gain.gain.setValueAtTime(0.04, audioCtx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.05);
          osc.start();
          osc.stop(audioCtx.currentTime + 0.05);
        } else if (type === 'converge') {
          osc.frequency.setValueAtTime(523.25, audioCtx.currentTime);
          osc.frequency.exponentialRampToValueAtTime(659.25, audioCtx.currentTime + 0.15);
          gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.4);
          osc.start();
          osc.stop(audioCtx.currentTime + 0.4);
        } else if (type === 'attack') {
          osc.type = 'sawtooth';
          osc.frequency.setValueAtTime(150, audioCtx.currentTime);
          gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.3);
          osc.start();
          osc.stop(audioCtx.currentTime + 0.3);
        }
      } catch {
        // AudioContext disabled or blocked by browser policy
      }
    },
    [soundEnabled]
  );

  // Fallback client-side routing calculation when backend is unreachable
  const recalculateClientRoutes = useCallback((targetTopo?: TopologyData) => {
    const activeTopo = targetTopo || topology;
    const nodeIds = Object.keys(activeTopo.nodes);
    const newRoutes: Record<string, RouteEntry[]> = {};

    setNodeTelemetry((prev) => {
      const next = { ...prev };
      for (const nid of nodeIds) {
        if (!next[nid]) {
          next[nid] = { tx: 0, rx: 0, flaps: 0, isCrashed: false };
        }
      }
      return next;
    });

    for (const src of nodeIds) {
      const dist: Record<string, number> = {};
      const nextHop: Record<string, string | null> = {};

      for (const nid of nodeIds) {
        dist[nid] = nid === src ? 0 : 999999;
        nextHop[nid] = null;
      }

      for (let iter = 0; iter < nodeIds.length - 1; iter++) {
        for (const link of activeTopo.links) {
          if (!link.is_up) continue;
          const u = link.source;
          const v = link.target;

          if (dist[u] + link.cost < dist[v]) {
            dist[v] = dist[u] + link.cost;
            nextHop[v] = nextHop[u] || (u === src ? v : nextHop[u]);
          }
          if (dist[v] + link.cost < dist[u]) {
            dist[u] = dist[v] + link.cost;
            nextHop[u] = nextHop[v] || (v === src ? u : nextHop[v]);
          }
        }
      }

      newRoutes[src] = nodeIds
        .filter((dst) => dst !== src)
        .map((dst) => ({
          destination: dst,
          next_hop: dist[dst] < 999999 ? nextHop[dst] : null,
          metric: dist[dst] < 999999 ? dist[dst] : 9999,
          protocol: currentProtocol,
          as_path:
            currentProtocol === 'bgp_lite'
              ? [activeTopo.nodes[src]?.as_number || 100, activeTopo.nodes[dst]?.as_number || 200]
              : undefined,
        }));
    }

    setAllRoutes(newRoutes);
  }, [topology, currentProtocol]);

  // Stable ref for simTime to avoid tearing and effect re-triggers
  const simTimeRef = useRef<number>(0.0);
  useEffect(() => {
    simTimeRef.current = simTime;
  }, [simTime]);

  const lastWsFrameTime = useRef<number>(0);

  // Initialize or restart backend simulation when topology or protocol switches
  useEffect(() => {
    const topo = RouteLabApi.getFallbackTopology(currentTopologyName);
    setTopology(topo);
    setSimTime(0.0);
    setIsConverged(false);
    setConvTime(0.0);
    setPackets([]);
    stateHistory.current = [];

    // Boot real simulation engine on backend
    RouteLabApi.startSimulation(topo, currentProtocol, quiescenceWindow, clockMode, speed).then(
      (res) => {
        if (res.status === 'offline') {
          recalculateClientRoutes(topo);
        }
      }
    );
  }, [currentTopologyName, currentProtocol, quiescenceWindow, clockMode, speed]);

  // Hook directly to backend WebSocket live event stream
  useEffect(() => {
    const handleDeltaBatch = (batch: any[]) => {
      let latestFrame: any = null;
      const newPackets: PacketCourier[] = [];
      const telemetryDelta: Record<string, { txDelta: number; rxDelta: number }> = {};
      let convergedUpdate: { converged: boolean; duration: number; record?: any } | null = null;
      const linkUpdates: { u: string; v: string; is_up: boolean }[] = [];
      const nodeStateUpdates: { node_id: string; status: string }[] = [];

      for (const delta of batch) {
        if (!delta) continue;
        if (delta.type === 'frame') {
          latestFrame = delta;
        } else if (delta.type === 'packet') {
          if (delta.event === 'PACKET_SENT' || delta.event === 'PACKET_FORWARDED') {
            newPackets.push({
              id: `${delta.src}->${delta.dst}-${Date.now()}-${Math.random()}`,
              src: delta.src,
              dst: delta.dst,
              progress: 0.0,
              speed: 1.5,
              protocol: delta.proto || currentProtocol,
              payloadType: 'control',
            });
            const cur = telemetryDelta[delta.src] || { txDelta: 0, rxDelta: 0 };
            cur.txDelta += 1;
            telemetryDelta[delta.src] = cur;
          } else if (delta.event === 'PACKET_DELIVERED') {
            const cur = telemetryDelta[delta.dst] || { txDelta: 0, rxDelta: 0 };
            cur.rxDelta += 1;
            telemetryDelta[delta.dst] = cur;
          }
        } else if (delta.type === 'node_state') {
          nodeStateUpdates.push({ node_id: delta.node_id, status: delta.status });
        } else if (delta.type === 'link_state') {
          const parts = delta.link_id.split('<->');
          if (parts.length === 2) {
            linkUpdates.push({ u: parts[0], v: parts[1], is_up: delta.is_up });
          }
        } else if (delta.type === 'convergence') {
          convergedUpdate = {
            converged: true,
            duration: delta.duration_s || simTimeRef.current,
            record: delta.record,
          };
        }
      }

      // 1. Batch packet couriers update
      if (newPackets.length > 0) {
        setPackets((prev) => [...prev.filter((p) => p.progress < 1.0).slice(-25), ...newPackets]);
      }

      // 2. Batch node state / telemetry updates
      if (Object.keys(telemetryDelta).length > 0 || nodeStateUpdates.length > 0) {
        setNodeTelemetry((prev) => {
          const next = { ...prev };
          for (const [nid, d] of Object.entries(telemetryDelta)) {
            const cur = next[nid] || { tx: 0, rx: 0, flaps: 0, isCrashed: false };
            next[nid] = { ...cur, tx: cur.tx + d.txDelta, rx: cur.rx + d.rxDelta };
          }
          for (const ns of nodeStateUpdates) {
            const cur = next[ns.node_id] || { tx: 0, rx: 0, flaps: 0, isCrashed: false };
            next[ns.node_id] = { ...cur, isCrashed: ns.status === 'crashed' };
          }
          return next;
        });
      }

      // 3. Link updates
      if (linkUpdates.length > 0) {
        setTopology((prev) => ({
          ...prev,
          links: prev.links.map((lnk) => {
            const match = linkUpdates.find(
              (lu) =>
                (lnk.source === lu.u && lnk.target === lu.v) ||
                (lnk.source === lu.v && lnk.target === lu.u)
            );
            return match ? { ...lnk, is_up: match.is_up } : lnk;
          }),
        }));
      }

      // 4. Convergence update
      if (convergedUpdate) {
        setIsConverged(true);
        setConvTime(convergedUpdate.duration);
        playChime('converge');
        if (convergedUpdate.record) {
          setConvergenceRecord({
            is_converged: true,
            convergence_time_s: convergedUpdate.duration,
            total_control_messages: convergedUpdate.record.messages || 0,
            total_control_bytes: convergedUpdate.record.bytes || 0,
            total_flaps: convergedUpdate.record.flaps || 0,
          });
        }
      }

      // 5. Apply only single latest frame from batch
      if (latestFrame) {
        lastWsFrameTime.current = performance.now();
        if (typeof latestFrame.time === 'number') setSimTime(latestFrame.time);
        if (typeof latestFrame.converged === 'boolean') setIsConverged(latestFrame.converged);
        if (latestFrame.nodes) {
          const nextRoutes: Record<string, RouteEntry[]> = {};
          const nextTelemetry: Record<string, { tx: number; rx: number; flaps: number; isCrashed: boolean }> = {};

          for (const [nid, n] of Object.entries(latestFrame.nodes) as [string, any][]) {
            nextTelemetry[nid] = {
              tx: n.packets_sent || 0,
              rx: n.packets_received || 0,
              flaps: n.flaps_count || 0,
              isCrashed: n.status === 'crashed',
            };
            if (n.routes && Array.isArray(n.routes)) {
              nextRoutes[nid] = n.routes.map((r: any) => ({
                destination: r.destination,
                next_hop: r.next_hop,
                metric: r.cost,
                protocol: currentProtocol,
              }));
            }
          }
          setNodeTelemetry((prev) => ({ ...prev, ...nextTelemetry }));
          setAllRoutes(nextRoutes);
        }
      }
    };

    const ws = RouteLabApi.connectWebSocket((msg: any) => {
      if (msg.type === 'init' || msg.type === 'state') {
        const state = msg.state;
        if (!state) return;
        if (typeof state.current_time === 'number') setSimTime(state.current_time);
        if (typeof state.is_converged === 'boolean') setIsConverged(state.is_converged);
        if (state.nodes) {
          const initRoutes: Record<string, RouteEntry[]> = {};
          const initTelemetry: Record<string, { tx: number; rx: number; flaps: number; isCrashed: boolean }> = {};
          for (const [nid, n] of Object.entries(state.nodes) as [string, any][]) {
            initTelemetry[nid] = {
              tx: n.packets_sent || 0,
              rx: n.packets_received || 0,
              flaps: n.flaps || 0,
              isCrashed: n.status === 'crashed',
            };
            if (n.routing_table && Array.isArray(n.routing_table)) {
              initRoutes[nid] = n.routing_table.map((r: any) => ({
                destination: r.dst,
                next_hop: r.next_hop,
                metric: r.cost,
                protocol: currentProtocol,
              }));
            }
          }
          setNodeTelemetry(initTelemetry);
          setAllRoutes(initRoutes);
        }
      } else if (msg.type === 'delta_batch') {
        handleDeltaBatch(msg.deltas || []);
      } else {
        handleDeltaBatch([msg]);
      }
    });

    return () => ws.close();
  }, [currentProtocol, playChime]);

  // Record historical state snapshots for scrubber replay (throttled to at most every 0.25s)
  const lastSnapshotTimeRef = useRef<number>(0);
  useEffect(() => {
    if (isScrubbing.current) return;
    if (Math.abs(simTime - lastSnapshotTimeRef.current) < 0.25) return;
    lastSnapshotTimeRef.current = simTime;
    stateHistory.current.push({
      time: simTime,
      routes: JSON.parse(JSON.stringify(allRoutes)),
      telemetry: JSON.parse(JSON.stringify(nodeTelemetry)),
      links: JSON.parse(JSON.stringify(topology.links)),
    });
    if (stateHistory.current.length > 200) {
      stateHistory.current.shift();
    }
  }, [simTime, allRoutes, nodeTelemetry, topology.links]);

  // Main simulation tick loop: updates packet courier positions and FPS
  useEffect(() => {
    if (!isRunning) return;

    let animId: number;
    let lastTime = performance.now();
    let frameCount = 0;
    let lastFpsUpdate = performance.now();

    const tick = (now: DOMHighResTimeStamp) => {
      const dt = (now - lastTime) / 1000.0;
      lastTime = now;

      // Update FPS counter
      frameCount++;
      if (now - lastFpsUpdate >= 1000) {
        setFps(frameCount);
        frameCount = 0;
        lastFpsUpdate = now;
      }

      // Advance simulation clock when backend frames are not arriving
      if (now - lastWsFrameTime.current > 400) {
        const simDelta = dt * speed;
        setSimTime((t) => Number((t + simDelta).toFixed(3)));
      }

      // Advance event-driven traveling packet animations
      setPackets((prevPackets) => {
        if (prevPackets.length === 0) return prevPackets;
        const nextPackets: PacketCourier[] = [];

        for (const pkt of prevPackets) {
          const nextProg = pkt.progress + pkt.speed * dt * speed;
          if (nextProg < 1.0) {
            nextPackets.push({ ...pkt, progress: nextProg });
          } else if (pkt.remainingHops && pkt.remainingHops.length > 0) {
            const nextDst = pkt.remainingHops[0];
            nextPackets.push({
              ...pkt,
              id: `probe-${pkt.dst}->${nextDst}-${Date.now()}`,
              src: pkt.dst,
              dst: nextDst,
              progress: 0.0,
              speed: 1.2,
              remainingHops: pkt.remainingHops.slice(1),
            });
          }
        }
        return nextPackets;
      });

      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [isRunning, speed]);

  // Actions
  const handleTogglePlay = () => {
    playChime('click');
    setIsRunning((r) => {
      const nextState = !r;
      if (nextState) {
        RouteLabApi.resumeSimulation();
      } else {
        RouteLabApi.pauseSimulation();
      }
      return nextState;
    });
  };

  const handleStep = () => {
    playChime('click');
    setSimTime((t) => t + 0.1);
    RouteLabApi.stepSimulation(0.1);
  };

  const handleReset = () => {
    playChime('click');
    setSimTime(0.0);
    setIsConverged(false);
    setConvTime(0.0);
    setPackets([]);
    setNodeTelemetry({});
    stateHistory.current = [];
    isScrubbing.current = false;
    RouteLabApi.startSimulation(topology, currentProtocol, quiescenceWindow, clockMode, speed);
  };

  // Historical state replay scrubbing
  const handleSeek = (targetTime: number) => {
    isScrubbing.current = true;
    setSimTime(targetTime);

    if (stateHistory.current.length > 0) {
      let closest = stateHistory.current[0];
      for (const snap of stateHistory.current) {
        if (snap.time <= targetTime) {
          closest = snap;
        } else {
          break;
        }
      }
      if (closest) {
        setAllRoutes(closest.routes);
        setNodeTelemetry(closest.telemetry);
        setTopology((prev) => ({ ...prev, links: closest.links }));
      }
    }

    setTimeout(() => {
      isScrubbing.current = false;
    }, 200);
  };

  const handleMutateLink = (u: string, v: string, up: boolean, cost: number) => {
    playChime('click');
    setTopology((prev) => ({
      ...prev,
      links: prev.links.map((lnk) =>
        (lnk.source === u && lnk.target === v) || (lnk.source === v && lnk.target === u)
          ? { ...lnk, is_up: up, cost }
          : lnk
      ),
    }));

    setIsConverged(false);
    setEvents((evs) => [
      ...evs,
      {
        seq: evs.length + 1,
        ts: simTime,
        type: up ? 'link_up' : 'link_down',
        src: `${u}<->${v}`,
        data: { cost, is_up: up },
      },
    ]);

    // Send real event injection to backend
    RouteLabApi.injectEvent(up ? 'link_up' : 'link_down', { u, v, cost });
  };

  const handleCrashNode = (nodeId: string) => {
    playChime('attack');
    setNodeTelemetry((prev) => {
      const cur = prev[nodeId] || { tx: 0, rx: 0, flaps: 0, isCrashed: false };
      return { ...prev, [nodeId]: { ...cur, isCrashed: true } };
    });

    setTopology((prev) => ({
      ...prev,
      links: prev.links.map((lnk) =>
        lnk.source === nodeId || lnk.target === nodeId ? { ...lnk, is_up: false } : lnk
      ),
    }));

    setIsConverged(false);
    setEvents((evs) => [
      ...evs,
      {
        seq: evs.length + 1,
        ts: simTime,
        type: 'node_crash',
        src: nodeId,
        data: { status: 'crashed' },
      },
    ]);

    RouteLabApi.injectEvent('node_crash', { node_id: nodeId });
  };

  const handleRecoverNode = (nodeId: string) => {
    playChime('click');
    setNodeTelemetry((prev) => {
      const cur = prev[nodeId] || { tx: 0, rx: 0, flaps: 0, isCrashed: false };
      return { ...prev, [nodeId]: { ...cur, isCrashed: false } };
    });

    setTopology((prev) => ({
      ...prev,
      links: prev.links.map((lnk) =>
        lnk.source === nodeId || lnk.target === nodeId ? { ...lnk, is_up: true } : lnk
      ),
    }));

    setIsConverged(false);
    setEvents((evs) => [
      ...evs,
      {
        seq: evs.length + 1,
        ts: simTime,
        type: 'node_recover',
        src: nodeId,
        data: { status: 'running' },
      },
    ]);

    RouteLabApi.injectEvent('node_recover', { node_id: nodeId });
  };

  const handleInjectPoisonAttack = (targetNode: string, maliciousCost: number) => {
    playChime('attack');
    setCurrentProtocol('poisoning_attack');

    setEvents((evs) => [
      ...evs,
      {
        seq: evs.length + 1,
        ts: simTime,
        type: 'attack_injected',
        src: 'Adversary',
        data: { target: targetNode, forged_metric: maliciousCost },
      },
    ]);

    setIsConverged(false);
    RouteLabApi.injectEvent('link_cost', { u: 'R1', v: targetNode, cost: maliciousCost });
  };

  const handleActivateMitigation = () => {
    playChime('converge');
    setCurrentProtocol('secure_dv');

    setEvents((evs) => [
      ...evs,
      {
        seq: evs.length + 1,
        ts: simTime,
        type: 'mitigation_active',
        src: 'SecureDV',
        data: { cryptographic_validation: true, filter_mode: 'strict' },
      },
    ]);

    setIsConverged(false);
  };

  const scenarioFileMap: Record<string, string> = {
    'course-6-node-dv-vs-ls': '6_node_dv_vs_ls.json',
    'course-8-node-failover': '8_node_bottleneck.json',
    'course-10-node-wan': '10_node_multipath.json',
    'count-to-infinity-flaw': 'count_to_infinity.json',
    'count-to-infinity-remedy': 'count_to_infinity.json',
    'bgp-tier1-policy': 'bgp_tier1_peering.json',
    'poisoning-attack-mitigation': 'route_poisoning_attack.json',
  };

  // Wire handleLaunchScenario to trigger real backend scenario definitions from examples/scenarios/
  const handleLaunchScenario = async (scenarioId: string, protocol: ProtocolType) => {
    playChime('click');
    const fileName = scenarioFileMap[scenarioId] || '6_node_dv_vs_ls.json';

    try {
      const def = await RouteLabApi.getScenario(fileName);
      if (def.topology_type && def.topology_type.includes('8')) {
        setCurrentTopologyName('course-8-node');
      } else if (def.topology_type && def.topology_type.includes('10')) {
        setCurrentTopologyName('course-10-node');
      } else {
        setCurrentTopologyName('course-6-node');
      }

      const chosenProto = (def.default_protocol as ProtocolType) || protocol;
      setCurrentProtocol(chosenProto);
      setSimTime(0.0);
      setIsConverged(false);
      setConvTime(0.0);
      setPackets([]);
      stateHistory.current = [];

      const topo = RouteLabApi.getFallbackTopology(
        def.topology_type && def.topology_type.includes('8')
          ? 'course-8-node'
          : def.topology_type && def.topology_type.includes('10')
          ? 'course-10-node'
          : 'course-6-node'
      );
      setTopology(topo);

      await RouteLabApi.startSimulation(topo, chosenProto, def.quiescence_window_s || 0.3);

      if (def.events && Array.isArray(def.events)) {
        for (const ev of def.events) {
          RouteLabApi.injectEvent(ev.action, ev.params);
        }
        setEvents(
          def.events.map((ev: any, idx: number) => ({
            seq: idx + 1,
            ts: ev.timestamp,
            type: ev.action,
            src: 'scenario_runner',
            data: ev.params || {},
          }))
        );
      }
    } catch {
      if (scenarioId.includes('8')) {
        setCurrentTopologyName('course-8-node');
      } else if (scenarioId.includes('10')) {
        setCurrentTopologyName('course-10-node');
      } else {
        setCurrentTopologyName('course-6-node');
      }
      setCurrentProtocol(protocol);
      handleReset();
    }
  };

  const handlePathChanged = useCallback((p: string[], loop: boolean) => {
    setActivePath(p);
    setLoopDetected(loop);
  }, []);

  const handleSendProbePacket = useCallback((pathNodes: string[]) => {
    if (pathNodes.length < 2) return;
    playChime('click');
    const firstHop = pathNodes[0];
    const secondHop = pathNodes[1];
    const remaining = pathNodes.slice(2);
    setPackets((prev) => [
      ...prev,
      {
        id: `probe-${firstHop}->${secondHop}-${Date.now()}`,
        src: firstHop,
        dst: secondHop,
        progress: 0.0,
        speed: 1.2,
        protocol: currentProtocol,
        payloadType: 'probe',
        remainingHops: remaining,
      },
    ]);
  }, [playChime, currentProtocol]);

  const selectedNodeTelemetry = selectedNode ? nodeTelemetry[selectedNode] : null;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100vw',
        height: '100vh',
        overflow: 'hidden',
        background: 'var(--bg-canvas)',
        position: 'relative',
      }}
    >
      {/* 1. Top Instrument Bar */}
      <InstrumentBar
        currentTopologyName={currentTopologyName}
        onSelectTopology={setCurrentTopologyName}
        currentProtocol={currentProtocol}
        onSelectProtocol={setCurrentProtocol}
        isRunning={isRunning}
        onTogglePlay={handleTogglePlay}
        onStep={handleStep}
        onReset={handleReset}
        speed={speed}
        onChangeSpeed={setSpeed}
        simTime={simTime}
        isConverged={isConverged}
        convTime={convTime}
        fps={fps}
        theme={theme}
        onToggleTheme={() => setTheme((t) => (t === 'light' ? 'dark' : 'light'))}
        isPhysicsActive={isPhysicsActive}
        onTogglePhysics={() => setIsPhysicsActive((p) => !p)}
        selectedNode={selectedNode}
        onToggleInspector={() => {
          if (selectedNode) {
            setSelectedNode(null);
          } else {
            const firstNode = Object.keys(topology.nodes)[0] || 'R1';
            setSelectedNode(firstNode);
          }
        }}
        onOpenCompare={() => setIsCompareOpen(true)}
        onOpenScenarios={() => setIsScenariosOpen(true)}
        onOpenAttacks={() => setIsAttacksOpen(true)}
        onOpenLogs={() => setIsLogsOpen(true)}
        onOpenExport={() => setIsExportOpen(true)}
        onOpenExplain={() => setIsExplainOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      {/* 2. Main Drafting Table Canvas */}
      <main style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        <TopologyCanvas
          topology={topology}
          selectedNode={selectedNode}
          onSelectNode={setSelectedNode}
          onMutateLink={(u, v, up, cost) => handleMutateLink(u, v, up, cost)}
          packets={packets}
          activePath={activePath}
          loopDetected={loopDetected}
          isPhysicsActive={isPhysicsActive}
          theme={theme}
        />

        {/* 3. Golden Quill Path Tracer Panel with protocol-aware criteria */}
        <PathTracerPanel
          topology={topology}
          allRoutes={allRoutes}
          onPathChanged={handlePathChanged}
          onSendProbePacket={handleSendProbePacket}
          protocol={currentProtocol}
        />

        {/* 4. Node Inspector Drawer with delineated metric units */}
        <NodeInspectorDrawer
          nodeId={selectedNode}
          onClose={() => setSelectedNode(null)}
          onSelectNode={setSelectedNode}
          topology={topology}
          routes={selectedNode ? allRoutes[selectedNode] || [] : []}
          protocol={currentProtocol}
          isCrashed={selectedNodeTelemetry?.isCrashed || false}
          onCrashNode={handleCrashNode}
          onRecoverNode={handleRecoverNode}
          packetsSent={selectedNodeTelemetry?.tx || 0}
          packetsReceived={selectedNodeTelemetry?.rx || 0}
          flapsCount={selectedNodeTelemetry?.flaps || 0}
        />

        {/* 5. Bottom Timeline Scrubber with historical scrubbing */}
        <TimelineScrubber
          currentTime={simTime}
          maxTime={15.0}
          isRunning={isRunning}
          onTogglePlay={handleTogglePlay}
          onSeek={handleSeek}
          events={events}
        />
      </main>

      {/* 6. Modals */}
      <CompareWorkbench
        isOpen={isCompareOpen}
        onClose={() => setIsCompareOpen(false)}
        topology={topology}
      />

      <FailureAttackModal
        isOpen={isAttacksOpen}
        onClose={() => setIsAttacksOpen(false)}
        topology={topology}
        onMutateLinkState={(u, v, up) => handleMutateLink(u, v, up, 1)}
        onMutateLinkCost={(u, v, cost) => handleMutateLink(u, v, true, cost)}
        onInjectPoisonAttack={handleInjectPoisonAttack}
        onActivateMitigation={handleActivateMitigation}
        onCrashNode={handleCrashNode}
      />

      <ScenarioBuilderModal
        isOpen={isScenariosOpen}
        onClose={() => setIsScenariosOpen(false)}
        onLaunchScenario={handleLaunchScenario}
      />

      <VirtualizedPacketLog
        isOpen={isLogsOpen}
        onClose={() => setIsLogsOpen(false)}
        events={events}
        onClear={() => setEvents([])}
      />

      <ExportModal
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        topology={topology}
        convergence={convergenceRecord}
        protocol={currentProtocol}
      />

      <ExplainModeModal
        isOpen={isExplainOpen}
        onClose={() => setIsExplainOpen(false)}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        quiescenceWindow={quiescenceWindow}
        onUpdateQuiescence={setQuiescenceWindow}
        soundEnabled={soundEnabled}
        onToggleSound={() => setSoundEnabled((s) => !s)}
        clockMode={clockMode}
        onUpdateClockMode={setClockMode}
        wsUrl={wsUrl}
        onUpdateWsUrl={setWsUrl}
      />
    </div>
  );
};

export default App;
