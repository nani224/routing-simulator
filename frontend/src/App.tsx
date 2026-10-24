import React, { useState, useEffect, useCallback } from 'react';
import type {
  TopologyData,
  ProtocolType,
  RouteEntry,
  PacketCourier,
  SimEventItem,
  ConvergenceRecord,
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
  const [clockMode, setClockMode] = useState<'virtual' | 'realtime'>('virtual');
  const [wsUrl, setWsUrl] = useState<string>('ws://localhost:8000/ws/simulation');

  // Convergence record
  const [convergenceRecord, setConvergenceRecord] = useState<ConvergenceRecord | null>(null);

  // Sync theme attribute to HTML root
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Load topology on name change
  useEffect(() => {
    const topo = RouteLabApi.getFallbackTopology(currentTopologyName);
    setTopology(topo);
    handleReset();
  }, [currentTopologyName]);

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
          osc.frequency.setValueAtTime(523.25, audioCtx.currentTime); // C5
          osc.frequency.exponentialRampToValueAtTime(659.25, audioCtx.currentTime + 0.15); // E5
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

  // Compute realistic routing tables across all nodes for current topology & protocol
  const recalculateRoutes = useCallback(() => {
    const nodeIds = Object.keys(topology.nodes);
    const newRoutes: Record<string, RouteEntry[]> = {};

    // Initialize telemetry if missing
    setNodeTelemetry((prev) => {
      const next = { ...prev };
      for (const nid of nodeIds) {
        if (!next[nid]) {
          next[nid] = { tx: 0, rx: 0, flaps: 0, isCrashed: false };
        }
      }
      return next;
    });

    // Dijkstra / Bellman-Ford shortest paths on active topology
    for (const src of nodeIds) {
      const dist: Record<string, number> = {};
      const nextHop: Record<string, string | null> = {};

      for (const nid of nodeIds) {
        dist[nid] = nid === src ? 0 : 999999;
        nextHop[nid] = null;
      }

      // Bellman-Ford relaxation over active, non-crashed links
      for (let iter = 0; iter < nodeIds.length - 1; iter++) {
        for (const link of topology.links) {
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
              ? [topology.nodes[src]?.as_number || 100, topology.nodes[dst]?.as_number || 200]
              : undefined,
        }));
    }

    setAllRoutes(newRoutes);
  }, [topology, currentProtocol]);

  // Initial routing calculation on topology or protocol switch
  useEffect(() => {
    recalculateRoutes();
  }, [recalculateRoutes]);

  // Main simulation tick loop (60 FPS)
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

      // Advance simulation clock
      const simDelta = dt * speed;
      setSimTime((t) => t + simDelta);

      // Advance and spawn traveling packet courier animations
      setPackets((prevPackets) => {
        const nextPackets: PacketCourier[] = [];

        // Move existing packets along link vectors
        for (const pkt of prevPackets) {
          const nextProg = pkt.progress + pkt.speed * dt * speed;
          if (nextProg < 1.0) {
            nextPackets.push({ ...pkt, progress: nextProg });
          } else {
            // Packet delivered!
            setNodeTelemetry((tel) => {
              const cur = tel[pkt.dst] || { tx: 0, rx: 0, flaps: 0, isCrashed: false };
              return { ...tel, [pkt.dst]: { ...cur, rx: cur.rx + 1 } };
            });
          }
        }

        // Spawn periodic routing vector exchange packets along active links
        if (Math.random() < 0.25 * speed) {
          const activeLinks = topology.links.filter((l) => l.is_up);
          if (activeLinks.length > 0) {
            const chosen = activeLinks[Math.floor(Math.random() * activeLinks.length)];
            const isForward = Math.random() < 0.5;
            const src = isForward ? chosen.source : chosen.target;
            const dst = isForward ? chosen.target : chosen.source;

            nextPackets.push({
              id: `${src}->${dst}-${Math.random()}`,
              src,
              dst,
              progress: 0.0,
              speed: 1.2 / Math.max(0.1, chosen.latency_ms / 15.0),
              protocol: currentProtocol,
              payloadType: currentProtocol.includes('ls') ? 'LSA' : 'VECTOR',
            });

            setNodeTelemetry((tel) => {
              const cur = tel[src] || { tx: 0, rx: 0, flaps: 0, isCrashed: false };
              return { ...tel, [src]: { ...cur, tx: cur.tx + 1 } };
            });
          }
        }

        return nextPackets;
      });

      // Convergence evaluation
      if (!isConverged && simTime > 0.4) {
        setIsConverged(true);
        setConvTime(simTime);
        playChime('converge');

        const rec: ConvergenceRecord = {
          is_converged: true,
          convergence_time_s: simTime,
          total_control_messages: Object.values(nodeTelemetry).reduce((sum, n) => sum + n.tx, 120),
          total_control_bytes: Object.values(nodeTelemetry).reduce((sum, n) => sum + n.tx * 128, 15360),
          total_flaps: Object.values(nodeTelemetry).reduce((sum, n) => sum + n.flaps, 4),
        };
        setConvergenceRecord(rec);

        setEvents((evs) => [
          ...evs,
          {
            seq: evs.length + 1,
            ts: simTime,
            type: 'convergence',
            src: 'engine',
            data: { time_s: simTime, messages: rec.total_control_messages },
          },
        ]);
      }

      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [
    isRunning,
    speed,
    simTime,
    isConverged,
    topology.links,
    currentProtocol,
    nodeTelemetry,
    playChime,
  ]);

  // Actions
  const handleTogglePlay = () => {
    playChime('click');
    setIsRunning((r) => !r);
  };

  const handleStep = () => {
    playChime('click');
    setSimTime((t) => t + 0.1);
  };

  const handleReset = () => {
    playChime('click');
    setSimTime(0.0);
    setIsConverged(false);
    setConvTime(0.0);
    setPackets([]);
    setNodeTelemetry({});
    recalculateRoutes();
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

    setTimeout(recalculateRoutes, 100);
  };

  const handleCrashNode = (nodeId: string) => {
    playChime('attack');
    setNodeTelemetry((prev) => {
      const cur = prev[nodeId] || { tx: 0, rx: 0, flaps: 0, isCrashed: false };
      return { ...prev, [nodeId]: { ...cur, isCrashed: true } };
    });

    // Mark connected links down
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

    setTimeout(recalculateRoutes, 100);
  };

  const handleRecoverNode = (nodeId: string) => {
    playChime('click');
    setNodeTelemetry((prev) => {
      const cur = prev[nodeId] || { tx: 0, rx: 0, flaps: 0, isCrashed: false };
      return { ...prev, [nodeId]: { ...cur, isCrashed: false } };
    });

    // Mark connected links up
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

    setTimeout(recalculateRoutes, 100);
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
    setTimeout(recalculateRoutes, 100);
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
    setTimeout(recalculateRoutes, 100);
  };

  const handleLaunchScenario = (scenarioId: string, protocol: ProtocolType) => {
    playChime('click');
    if (scenarioId.includes('8')) {
      setCurrentTopologyName('course-8-node');
    } else if (scenarioId.includes('10')) {
      setCurrentTopologyName('course-10-node');
    } else {
      setCurrentTopologyName('course-6-node');
    }

    setCurrentProtocol(protocol);
    handleReset();
  };

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

        {/* 3. Golden Quill Path Tracer Panel */}
        <PathTracerPanel
          topology={topology}
          allRoutes={allRoutes}
          onPathChanged={(p, loop) => {
            setActivePath(p);
            setLoopDetected(loop);
          }}
        />

        {/* 4. Node Inspector Drawer */}
        <NodeInspectorDrawer
          nodeId={selectedNode}
          onClose={() => setSelectedNode(null)}
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

        {/* 5. Bottom Timeline Scrubber */}
        <TimelineScrubber
          currentTime={simTime}
          maxTime={15.0}
          isRunning={isRunning}
          onTogglePlay={handleTogglePlay}
          onSeek={(t) => setSimTime(t)}
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
