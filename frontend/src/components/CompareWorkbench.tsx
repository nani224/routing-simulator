import React, { useState, useEffect, useRef, useMemo } from 'react';
import type {
  TopologyData,
  ProtocolType,
  ComparisonReportResponse,
  PacketTraceEvent,
} from '../types';
import { RouteLabApi } from '../services/api';
import {
  X,
  Layers,
  Play,
  Pause,
  RotateCcw,
  Trophy,
  CheckCircle2,
  Zap,
  Clock,
  Gauge,
  Send,
  Sparkles,
} from 'lucide-react';

interface CompareWorkbenchProps {
  isOpen: boolean;
  onClose: () => void;
  topology: TopologyData;
}

interface CourierParticle {
  id: string;
  src: string;
  dst: string;
  x: number;
  y: number;
  progress: number;
  protocol: string;
}

export const CompareWorkbench: React.FC<CompareWorkbenchProps> = ({
  isOpen,
  onClose,
  topology,
}) => {
  const [protoA, setProtoA] = useState<ProtocolType>('distance_vector');
  const [protoB, setProtoB] = useState<ProtocolType>('link_state');
  const [report, setReport] = useState<ComparisonReportResponse | null>(null);
  const [isComparing, setIsComparing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Playback & Animation State
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackTime, setPlaybackTime] = useState<number>(0);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1.0);

  // Canvas refs
  const canvasRefA = useRef<HTMLCanvasElement | null>(null);
  const canvasRefB = useRef<HTMLCanvasElement | null>(null);
  const animFrameId = useRef<number | null>(null);
  const lastWallTimeRef = useRef<number>(performance.now());

  // Determine max simulation time from convergence times and traces
  const maxSimTime = useMemo(() => {
    if (!report) return 2.0;
    const tA = report.metrics[protoA]?.convergence_time_s || 1.0;
    const tB = report.metrics[protoB]?.convergence_time_s || 1.0;
    let maxTrace = Math.max(tA, tB);

    const tracesA = report.packet_traces[protoA] || [];
    const tracesB = report.packet_traces[protoB] || [];
    if (tracesA.length > 0) {
      maxTrace = Math.max(maxTrace, tracesA[tracesA.length - 1].ts);
    }
    if (tracesB.length > 0) {
      maxTrace = Math.max(maxTrace, tracesB[tracesB.length - 1].ts);
    }
    return Math.max(1.0, Number((maxTrace + 0.35).toFixed(3)));
  }, [report, protoA, protoB]);

  // Run Benchmark & fetch packet traces
  const handleRunComparison = async () => {
    setIsComparing(true);
    setError(null);
    setIsPlaying(false);
    setPlaybackTime(0);

    try {
      const data = await RouteLabApi.runCompare(topology, [protoA, protoB], 5.0);
      setReport(data);
      // Auto-start visual playback race!
      setPlaybackTime(0);
      setIsPlaying(true);
      lastWallTimeRef.current = performance.now();
    } catch (err: any) {
      setError(err?.message || 'Comparison benchmark failed on backend');
    } finally {
      setIsComparing(false);
    }
  };

  // Playback timer ticker via requestAnimationFrame
  useEffect(() => {
    if (!isPlaying) {
      if (animFrameId.current) cancelAnimationFrame(animFrameId.current);
      return;
    }

    lastWallTimeRef.current = performance.now();

    const loop = (wallNow: number) => {
      const deltaSec = (wallNow - lastWallTimeRef.current) / 1000;
      lastWallTimeRef.current = wallNow;

      setPlaybackTime((prev) => {
        // Visual playback pace: 1 simulation second takes ~3 real seconds at 1x
        const simDelta = (deltaSec / 3.0) * playbackSpeed;
        const next = prev + simDelta;
        if (next >= maxSimTime) {
          setIsPlaying(false);
          return maxSimTime;
        }
        return next;
      });

      animFrameId.current = requestAnimationFrame(loop);
    };

    animFrameId.current = requestAnimationFrame(loop);
    return () => {
      if (animFrameId.current) cancelAnimationFrame(animFrameId.current);
    };
  }, [isPlaying, playbackSpeed, maxSimTime]);

  // Helper: map link lookup for latency
  const linkLatencyMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const l of topology.links) {
      map.set(`${l.source}->${l.target}`, (l.latency_ms || 20) / 1000);
      map.set(`${l.target}->${l.source}`, (l.latency_ms || 20) / 1000);
    }
    return map;
  }, [topology.links]);

  // Compute active couriers at playbackTime for a given protocol
  const getActiveCouriers = (
    proto: string,
    traces: PacketTraceEvent[],
    coords: Record<string, { x: number; y: number }>
  ): { couriers: CourierParticle[]; deliveredCount: number; inFlightCount: number } => {
    const couriers: CourierParticle[] = [];
    let deliveredCount = 0;
    let inFlightCount = 0;

    for (const ev of traces) {
      if (ev.type !== 'packet_sent') continue;
      const key = `${ev.src}->${ev.dst}`;
      const transitDuration = Math.max(0.12, (linkLatencyMap.get(key) || 0.05) * 2.5);
      const startT = ev.ts;
      const endT = startT + transitDuration;

      if (playbackTime < startT) {
        continue;
      } else if (playbackTime >= endT) {
        deliveredCount++;
      } else {
        inFlightCount++;
        const p = Math.min(1.0, Math.max(0.0, (playbackTime - startT) / transitDuration));
        const srcPos = coords[ev.src];
        const dstPos = coords[ev.dst];
        if (srcPos && dstPos) {
          couriers.push({
            id: `pkt-${ev.seq}`,
            src: ev.src,
            dst: ev.dst,
            x: srcPos.x + (dstPos.x - srcPos.x) * p,
            y: srcPos.y + (dstPos.y - srcPos.y) * p,
            progress: p,
            protocol: proto,
          });
        }
      }
    }

    return { couriers, deliveredCount, inFlightCount };
  };

  // Render network topology & packet couriers on canvas
  const renderCanvas = (
    canvas: HTMLCanvasElement | null,
    protoName: string,
    accentColor: string,
    particleColor: string
  ) => {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    const dpr = window.devicePixelRatio || 1;

    if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
      canvas.width = width * dpr;
      canvas.height = height * dpr;
    }

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    // Compute bounding box of topology nodes
    const nodeIds = Object.keys(topology.nodes);
    if (nodeIds.length === 0) {
      ctx.restore();
      return;
    }

    let minX = Infinity,
      maxX = -Infinity,
      minY = Infinity,
      maxY = -Infinity;
    for (const id of nodeIds) {
      const n = topology.nodes[id];
      if (n.x < minX) minX = n.x;
      if (n.x > maxX) maxX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.y > maxY) maxY = n.y;
    }

    const padding = 38;
    const rangeX = Math.max(1, maxX - minX);
    const rangeY = Math.max(1, maxY - minY);
    const scale = Math.min((width - 2 * padding) / rangeX, (height - 2 * padding) / rangeY);
    const offsetX = padding + (width - 2 * padding - rangeX * scale) / 2;
    const offsetY = padding + (height - 2 * padding - rangeY * scale) / 2;

    const screenCoords: Record<string, { x: number; y: number }> = {};
    for (const id of nodeIds) {
      const n = topology.nodes[id];
      screenCoords[id] = {
        x: offsetX + (n.x - minX) * scale,
        y: offsetY + (n.y - minY) * scale,
      };
    }

    // 1. Draw Subtle Drafting Grid Background
    ctx.strokeStyle = 'rgba(180, 150, 120, 0.08)';
    ctx.lineWidth = 1;
    const gridStep = 24;
    for (let x = 0; x < width; x += gridStep) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y < height; y += gridStep) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // 2. Draw Links
    for (const link of topology.links) {
      const p1 = screenCoords[link.source];
      const p2 = screenCoords[link.target];
      if (!p1 || !p2) continue;

      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.strokeStyle = 'rgba(140, 110, 80, 0.28)';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Midpoint cost tag
      const midX = (p1.x + p2.x) / 2;
      const midY = (p1.y + p2.y) / 2;
      ctx.fillStyle = 'rgba(40, 32, 24, 0.75)';
      ctx.beginPath();
      ctx.arc(midX, midY, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = 'rgba(180, 150, 100, 0.4)';
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.fillStyle = '#f5eedc';
      ctx.font = '9px monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(link.cost ?? 1), midX, midY);
    }

    // 3. Draw Nodes
    for (const id of nodeIds) {
      const pos = screenCoords[id];
      if (!pos) continue;

      // Outer glow
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 14, 0, Math.PI * 2);
      ctx.fillStyle = accentColor.replace(')', ', 0.15)').replace('rgb', 'rgba');
      ctx.fill();

      // Node circle
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 11, 0, Math.PI * 2);
      ctx.fillStyle = '#1e1a17';
      ctx.fill();
      ctx.strokeStyle = accentColor;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Node label
      ctx.fillStyle = '#f5eedc';
      ctx.font = 'bold 9px monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(id, pos.x, pos.y);
    }

    // 4. Draw Animated Moving Packet Couriers
    const traces = report?.packet_traces[protoName] || [];
    const { couriers } = getActiveCouriers(protoName, traces, screenCoords);

    for (const courier of couriers) {
      // Outer pulse glow
      const grad = ctx.createRadialGradient(
        courier.x,
        courier.y,
        1,
        courier.x,
        courier.y,
        10
      );
      grad.addColorStop(0, particleColor);
      grad.addColorStop(0.5, particleColor.replace(')', ', 0.5)').replace('rgb', 'rgba'));
      grad.addColorStop(1, 'rgba(0, 0, 0, 0)');

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(courier.x, courier.y, 10, 0, Math.PI * 2);
      ctx.fill();

      // Core packet bead
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(courier.x, courier.y, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = particleColor;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Trailing tail particles
      const srcPos = screenCoords[courier.src];
      const dstPos = screenCoords[courier.dst];
      if (srcPos && dstPos) {
        for (let i = 1; i <= 3; i++) {
          const trailP = Math.max(0, courier.progress - i * 0.05);
          const tx = srcPos.x + (dstPos.x - srcPos.x) * trailP;
          const ty = srcPos.y + (dstPos.y - srcPos.y) * trailP;
          ctx.beginPath();
          ctx.arc(tx, ty, Math.max(1, 3.5 - i * 0.9), 0, Math.PI * 2);
          ctx.fillStyle = particleColor.replace(')', `, ${0.45 - i * 0.12})`).replace('rgb', 'rgba');
          ctx.fill();
        }
      }
    }

    // 5. Convergence Halo / Celebration Ring if already converged at playbackTime
    const metrics = report?.metrics[protoName];
    if (metrics && playbackTime >= metrics.convergence_time_s) {
      ctx.fillStyle = 'rgba(46, 196, 182, 0.12)';
      ctx.fillRect(0, height - 28, width, 28);
      ctx.fillStyle = '#2ec4b6';
      ctx.font = 'bold 10px monospace';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      ctx.fillText(
        `✓ CONVERGED at ${metrics.convergence_time_s.toFixed(3)}s`,
        width - 12,
        height - 14
      );
    }

    ctx.restore();
  };

  // Render both canvases on animation tick / playback update
  useEffect(() => {
    if (!isOpen) return;
    renderCanvas(canvasRefA.current, protoA, '#d95d39', 'rgb(255, 122, 89)');
    renderCanvas(canvasRefB.current, protoB, '#2a9d8f', 'rgb(46, 196, 182)');
  }, [isOpen, playbackTime, report, protoA, protoB, topology]);

  if (!isOpen) return null;

  const resA = report?.metrics[protoA];
  const resB = report?.metrics[protoB];

  // Active courier counters for UI headers
  const tracesA = report?.packet_traces[protoA] || [];
  const tracesB = report?.packet_traces[protoB] || [];
  const statsA = getActiveCouriers(protoA, tracesA, {});
  const statsB = getActiveCouriers(protoB, tracesB, {});

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(15, 12, 10, 0.82)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        padding: '1.2rem',
      }}
    >
      <div
        className="carto-card"
        style={{
          width: '1120px',
          maxWidth: '96vw',
          maxHeight: '92vh',
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--surface-card)',
          border: '2px solid var(--border-brass)',
          boxShadow: 'var(--shadow-lg)',
          borderRadius: '8px',
          overflow: 'hidden',
        }}
      >
        {/* Header Bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.9rem 1.4rem',
            borderBottom: '1px solid var(--border-ink)',
            background: 'var(--surface-inset)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                background: 'oklch(from var(--accent-brass) l c h / 0.18)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: '1px solid var(--border-brass)',
              }}
            >
              <Layers size={18} color="var(--accent-brass)" />
            </div>
            <div>
              <div
                style={{
                  fontWeight: 800,
                  fontFamily: 'var(--font-heading)',
                  fontSize: '1.15rem',
                  letterSpacing: '0.02em',
                }}
              >
                Comparative Algorithm Visual Benchmark Lab
              </div>
              <div
                style={{
                  fontSize: '0.68rem',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-muted)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                }}
              >
                <span>COURSE SCENARIO LAB</span>
                <span>•</span>
                <span>SIDE-BY-SIDE REAL-TIME PACKET PROPAGATION & CONVERGENCE RACE</span>
              </div>
            </div>
          </div>
          <button
            className="btn-brass"
            style={{ width: '32px', height: '32px', padding: 0 }}
            onClick={onClose}
          >
            <X size={16} />
          </button>
        </div>

        {/* Algorithm Selection & Run Command Bar */}
        <div
          style={{
            padding: '0.9rem 1.4rem',
            borderBottom: '1px solid var(--border-ink)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            background: 'var(--surface-card)',
            flexWrap: 'wrap',
          }}
        >
          {/* Protocol A Picker */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flex: 1, minWidth: '220px' }}>
            <div
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                background: 'var(--accent-terracotta)',
                boxShadow: '0 0 8px var(--accent-terracotta)',
              }}
            />
            <span style={{ fontSize: '0.82rem', fontWeight: 700 }}>Protocol A:</span>
            <select
              value={protoA}
              onChange={(e) => setProtoA(e.target.value as ProtocolType)}
              style={{
                flex: 1,
                padding: '0.45rem 0.6rem',
                borderRadius: '4px',
                border: '1px solid var(--border-ink)',
                background: 'var(--surface-inset)',
                color: 'var(--text-primary)',
                fontWeight: 600,
                fontSize: '0.85rem',
              }}
            >
              <option value="distance_vector">Distance Vector (Bellman-Ford)</option>
              <option value="link_state">Link State (OSPF / Dijkstra)</option>
              <option value="bgp_lite">BGP-Lite (Path Vector)</option>
              <option value="flooding">Flooding Baseline</option>
            </select>
          </div>

          {/* VS Divider */}
          <div
            style={{
              padding: '0.2rem 0.6rem',
              borderRadius: '4px',
              background: 'var(--surface-inset)',
              border: '1px solid var(--border-brass)',
              fontWeight: 800,
              fontSize: '0.75rem',
              color: 'var(--accent-brass)',
              fontFamily: 'var(--font-mono)',
            }}
          >
            VS
          </div>

          {/* Protocol B Picker */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flex: 1, minWidth: '220px' }}>
            <div
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                background: 'var(--accent-verdigris)',
                boxShadow: '0 0 8px var(--accent-verdigris)',
              }}
            />
            <span style={{ fontSize: '0.82rem', fontWeight: 700 }}>Protocol B:</span>
            <select
              value={protoB}
              onChange={(e) => setProtoB(e.target.value as ProtocolType)}
              style={{
                flex: 1,
                padding: '0.45rem 0.6rem',
                borderRadius: '4px',
                border: '1px solid var(--border-ink)',
                background: 'var(--surface-inset)',
                color: 'var(--text-primary)',
                fontWeight: 600,
                fontSize: '0.85rem',
              }}
            >
              <option value="link_state">Link State (OSPF / Dijkstra)</option>
              <option value="distance_vector">Distance Vector (Bellman-Ford)</option>
              <option value="bgp_lite">BGP-Lite (Path Vector)</option>
              <option value="flooding">Flooding Baseline</option>
            </select>
          </div>

          {/* Launch Benchmark Button */}
          <button
            className="btn-brass btn-brass-primary"
            onClick={handleRunComparison}
            disabled={isComparing}
            style={{
              padding: '0.55rem 1.2rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontWeight: 700,
              fontSize: '0.85rem',
            }}
          >
            <Play size={15} />
            {isComparing ? 'Running Benchmark & Tracing...' : 'Run Visual Comparison Race'}
          </button>
        </div>

        {/* Scrollable Main Visual Lab */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.2rem', display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
          {error && (
            <div
              style={{
                padding: '0.9rem',
                borderRadius: '6px',
                background: 'oklch(from var(--accent-crimson) l c h / 0.12)',
                border: '1px solid var(--accent-crimson)',
                color: 'var(--accent-crimson)',
                fontSize: '0.82rem',
                fontFamily: 'var(--font-mono)',
              }}
            >
              <strong>Benchmark Error:</strong> {error}
            </div>
          )}

          {/* Dual Visual Side-by-Side Simulation Arenas */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '1.2rem',
            }}
          >
            {/* Arena A */}
            <div
              style={{
                border: '1px solid var(--border-ink)',
                borderRadius: '6px',
                background: 'var(--surface-inset)',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              {/* Arena A Header */}
              <div
                style={{
                  padding: '0.6rem 0.9rem',
                  background: 'rgba(217, 93, 57, 0.1)',
                  borderBottom: '1px solid rgba(217, 93, 57, 0.25)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <div
                    style={{
                      width: '10px',
                      height: '10px',
                      borderRadius: '50%',
                      background: 'var(--accent-terracotta)',
                    }}
                  />
                  <span
                    style={{
                      fontWeight: 800,
                      fontSize: '0.88rem',
                      fontFamily: 'var(--font-mono)',
                      color: 'var(--accent-terracotta)',
                      textTransform: 'uppercase',
                    }}
                  >
                    {protoA.replace('_', ' ')}
                  </span>
                </div>

                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.8rem',
                    fontSize: '0.72rem',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  <span style={{ color: 'var(--text-secondary)' }}>
                    In Flight: <strong style={{ color: 'var(--accent-terracotta)' }}>{statsA.inFlightCount}</strong>
                  </span>
                  <span style={{ color: 'var(--text-secondary)' }}>
                    Delivered: <strong>{statsA.deliveredCount}</strong> / {tracesA.filter((t) => t.type === 'packet_sent').length}
                  </span>
                  {resA && playbackTime >= resA.convergence_time_s ? (
                    <span
                      style={{
                        padding: '0.15rem 0.4rem',
                        borderRadius: '3px',
                        background: 'oklch(from var(--accent-verdigris) l c h / 0.18)',
                        color: 'var(--accent-verdigris)',
                        fontWeight: 700,
                      }}
                    >
                      CONVERGED ({resA.convergence_time_s.toFixed(3)}s)
                    </span>
                  ) : (
                    <span
                      style={{
                        padding: '0.15rem 0.4rem',
                        borderRadius: '3px',
                        background: 'rgba(217, 93, 57, 0.15)',
                        color: 'var(--accent-terracotta)',
                        fontWeight: 700,
                      }}
                    >
                      MUTATING
                    </span>
                  )}
                </div>
              </div>

              {/* Canvas A */}
              <div style={{ position: 'relative', width: '100%', height: '260px' }}>
                <canvas
                  ref={canvasRefA}
                  style={{ width: '100%', height: '100%', display: 'block' }}
                />
                {!report && (
                  <div
                    style={{
                      position: 'absolute',
                      inset: 0,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'rgba(20, 16, 12, 0.4)',
                      color: 'var(--text-muted)',
                      fontSize: '0.82rem',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    Click &apos;Run Visual Comparison Race&apos; to simulate
                  </div>
                )}
              </div>
            </div>

            {/* Arena B */}
            <div
              style={{
                border: '1px solid var(--border-ink)',
                borderRadius: '6px',
                background: 'var(--surface-inset)',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              {/* Arena B Header */}
              <div
                style={{
                  padding: '0.6rem 0.9rem',
                  background: 'rgba(42, 157, 143, 0.1)',
                  borderBottom: '1px solid rgba(42, 157, 143, 0.25)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <div
                    style={{
                      width: '10px',
                      height: '10px',
                      borderRadius: '50%',
                      background: 'var(--accent-verdigris)',
                    }}
                  />
                  <span
                    style={{
                      fontWeight: 800,
                      fontSize: '0.88rem',
                      fontFamily: 'var(--font-mono)',
                      color: 'var(--accent-verdigris)',
                      textTransform: 'uppercase',
                    }}
                  >
                    {protoB.replace('_', ' ')}
                  </span>
                </div>

                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.8rem',
                    fontSize: '0.72rem',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  <span style={{ color: 'var(--text-secondary)' }}>
                    In Flight: <strong style={{ color: 'var(--accent-verdigris)' }}>{statsB.inFlightCount}</strong>
                  </span>
                  <span style={{ color: 'var(--text-secondary)' }}>
                    Delivered: <strong>{statsB.deliveredCount}</strong> / {tracesB.filter((t) => t.type === 'packet_sent').length}
                  </span>
                  {resB && playbackTime >= resB.convergence_time_s ? (
                    <span
                      style={{
                        padding: '0.15rem 0.4rem',
                        borderRadius: '3px',
                        background: 'oklch(from var(--accent-verdigris) l c h / 0.18)',
                        color: 'var(--accent-verdigris)',
                        fontWeight: 700,
                      }}
                    >
                      CONVERGED ({resB.convergence_time_s.toFixed(3)}s)
                    </span>
                  ) : (
                    <span
                      style={{
                        padding: '0.15rem 0.4rem',
                        borderRadius: '3px',
                        background: 'rgba(42, 157, 143, 0.15)',
                        color: 'var(--accent-verdigris)',
                        fontWeight: 700,
                      }}
                    >
                      MUTATING
                    </span>
                  )}
                </div>
              </div>

              {/* Canvas B */}
              <div style={{ position: 'relative', width: '100%', height: '260px' }}>
                <canvas
                  ref={canvasRefB}
                  style={{ width: '100%', height: '100%', display: 'block' }}
                />
                {!report && (
                  <div
                    style={{
                      position: 'absolute',
                      inset: 0,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'rgba(20, 16, 12, 0.4)',
                      color: 'var(--text-muted)',
                      fontSize: '0.82rem',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    Click &apos;Run Visual Comparison Race&apos; to simulate
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Synchronized Playback Control Dock */}
          {report && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '1rem',
                padding: '0.7rem 1.2rem',
                borderRadius: '6px',
                border: '1px solid var(--border-brass)',
                background: 'var(--surface-card)',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <button
                className="btn-brass"
                onClick={() => setIsPlaying(!isPlaying)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.4rem 0.8rem',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                }}
              >
                {isPlaying ? <Pause size={14} /> : <Play size={14} />}
                {isPlaying ? 'Pause' : 'Play Race'}
              </button>
              <button
                className="btn-brass"
                onClick={() => {
                  setPlaybackTime(0);
                  setIsPlaying(true);
                  lastWallTimeRef.current = performance.now();
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.4rem 0.8rem',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                }}
                title="Replay Race from Beginning"
              >
                <RotateCcw size={14} />
                Replay
              </button>

              {/* Time Scrubber */}
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
                <Clock size={15} color="var(--accent-brass)" />
                <input
                  type="range"
                  min="0"
                  max={maxSimTime}
                  step="0.005"
                  value={playbackTime}
                  onChange={(e) => {
                    setPlaybackTime(parseFloat(e.target.value));
                    setIsPlaying(false);
                  }}
                  style={{
                    flex: 1,
                    accentColor: 'var(--accent-brass)',
                    cursor: 'pointer',
                  }}
                />
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.82rem',
                    fontWeight: 700,
                    minWidth: '100px',
                    textAlign: 'right',
                    color: 'var(--text-primary)',
                  }}
                >
                  {playbackTime.toFixed(3)}s / {maxSimTime.toFixed(3)}s
                </span>
              </div>

              {/* Speed Multipliers */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                {[0.5, 1.0, 2.0, 4.0].map((spd) => (
                  <button
                    key={spd}
                    className={`btn-brass ${playbackSpeed === spd ? 'btn-brass-primary' : ''}`}
                    onClick={() => setPlaybackSpeed(spd)}
                    style={{
                      padding: '0.25rem 0.5rem',
                      fontSize: '0.72rem',
                      fontFamily: 'var(--font-mono)',
                      fontWeight: 700,
                    }}
                  >
                    {spd}x
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Direct Benchmark Metrics Matrix & Winners */}
          {report && resA && resB ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div
                style={{
                  border: '1px solid var(--border-ink)',
                  borderRadius: '6px',
                  background: 'var(--surface-card)',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    padding: '0.7rem 1rem',
                    background: 'var(--surface-inset)',
                    borderBottom: '1px solid var(--border-ink)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Trophy size={16} color="var(--accent-brass)" />
                    <span style={{ fontWeight: 800, fontSize: '0.9rem', fontFamily: 'var(--font-heading)' }}>
                      Direct Side-by-Side Benchmark Evaluation
                    </span>
                  </div>
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontFamily: 'var(--font-mono)',
                      color: 'var(--text-muted)',
                    }}
                  >
                    IDENTICAL VIRTUAL CLOCK (SEED {report.seed})
                  </span>
                </div>

                {/* Benchmark Table */}
                <table
                  style={{
                    width: '100%',
                    borderCollapse: 'collapse',
                    fontSize: '0.82rem',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-ink)', background: 'var(--surface-inset)' }}>
                      <th style={{ padding: '0.6rem 1rem', textAlign: 'left', fontWeight: 700 }}>
                        Evaluation Metric
                      </th>
                      <th
                        style={{
                          padding: '0.6rem 1rem',
                          textAlign: 'left',
                          color: 'var(--accent-terracotta)',
                          fontWeight: 700,
                        }}
                      >
                        {protoA.replace('_', ' ').toUpperCase()}
                      </th>
                      <th
                        style={{
                          padding: '0.6rem 1rem',
                          textAlign: 'left',
                          color: 'var(--accent-verdigris)',
                          fontWeight: 700,
                        }}
                      >
                        {protoB.replace('_', ' ').toUpperCase()}
                      </th>
                      <th style={{ padding: '0.6rem 1rem', textAlign: 'left', fontWeight: 700 }}>
                        Winner / Delta
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {/* Convergence Time */}
                    <tr style={{ borderBottom: '1px solid var(--border-ink)' }}>
                      <td style={{ padding: '0.6rem 1rem', fontWeight: 600 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <Clock size={14} color="var(--accent-brass)" />
                          Convergence Speed
                        </div>
                      </td>
                      <td style={{ padding: '0.6rem 1rem' }}>{resA.convergence_time_s.toFixed(3)}s</td>
                      <td style={{ padding: '0.6rem 1rem' }}>{resB.convergence_time_s.toFixed(3)}s</td>
                      <td style={{ padding: '0.6rem 1rem' }}>
                        {resA.convergence_time_s < resB.convergence_time_s ? (
                          <span style={{ color: 'var(--accent-terracotta)', fontWeight: 700 }}>
                            🏆 {protoA.replace('_', ' ')} (
                            {(resB.convergence_time_s / (resA.convergence_time_s || 0.001)).toFixed(1)}x faster)
                          </span>
                        ) : resB.convergence_time_s < resA.convergence_time_s ? (
                          <span style={{ color: 'var(--accent-verdigris)', fontWeight: 700 }}>
                            🏆 {protoB.replace('_', ' ')} (
                            {(resA.convergence_time_s / (resB.convergence_time_s || 0.001)).toFixed(1)}x faster)
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>🤝 Identical</span>
                        )}
                      </td>
                    </tr>

                    {/* Control Messages */}
                    <tr style={{ borderBottom: '1px solid var(--border-ink)' }}>
                      <td style={{ padding: '0.6rem 1rem', fontWeight: 600 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <Send size={14} color="var(--accent-brass)" />
                          Control Messages
                        </div>
                      </td>
                      <td style={{ padding: '0.6rem 1rem' }}>{resA.total_messages} pkts</td>
                      <td style={{ padding: '0.6rem 1rem' }}>{resB.total_messages} pkts</td>
                      <td style={{ padding: '0.6rem 1rem' }}>
                        {resA.total_messages < resB.total_messages ? (
                          <span style={{ color: 'var(--accent-terracotta)', fontWeight: 700 }}>
                            🏆 {protoA.replace('_', ' ')} (-
                            {Math.round(((resB.total_messages - resA.total_messages) / (resB.total_messages || 1)) * 100)}%)
                          </span>
                        ) : resB.total_messages < resA.total_messages ? (
                          <span style={{ color: 'var(--accent-verdigris)', fontWeight: 700 }}>
                            🏆 {protoB.replace('_', ' ')} (-
                            {Math.round(((resA.total_messages - resB.total_messages) / (resA.total_messages || 1)) * 100)}%)
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>🤝 Equal</span>
                        )}
                      </td>
                    </tr>

                    {/* Control Wire Bytes */}
                    <tr style={{ borderBottom: '1px solid var(--border-ink)' }}>
                      <td style={{ padding: '0.6rem 1rem', fontWeight: 600 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <Gauge size={14} color="var(--accent-brass)" />
                          Wire Byte Overhead
                        </div>
                      </td>
                      <td style={{ padding: '0.6rem 1rem' }}>{resA.total_bytes.toLocaleString()} B</td>
                      <td style={{ padding: '0.6rem 1rem' }}>{resB.total_bytes.toLocaleString()} B</td>
                      <td style={{ padding: '0.6rem 1rem' }}>
                        {resA.total_bytes < resB.total_bytes ? (
                          <span style={{ color: 'var(--accent-terracotta)', fontWeight: 700 }}>
                            🏆 {protoA.replace('_', ' ')} (Lower Overhead)
                          </span>
                        ) : (
                          <span style={{ color: 'var(--accent-verdigris)', fontWeight: 700 }}>
                            🏆 {protoB.replace('_', ' ')} (Lower Overhead)
                          </span>
                        )}
                      </td>
                    </tr>

                    {/* Route Flaps */}
                    <tr style={{ borderBottom: '1px solid var(--border-ink)' }}>
                      <td style={{ padding: '0.6rem 1rem', fontWeight: 600 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <Zap size={14} color="var(--accent-brass)" />
                          Route Flaps / Instabilities
                        </div>
                      </td>
                      <td style={{ padding: '0.6rem 1rem' }}>{resA.total_flaps} flaps</td>
                      <td style={{ padding: '0.6rem 1rem' }}>{resB.total_flaps} flaps</td>
                      <td style={{ padding: '0.6rem 1rem' }}>
                        {resA.total_flaps < resB.total_flaps ? (
                          <span style={{ color: 'var(--accent-terracotta)', fontWeight: 700 }}>
                            🏆 {protoA.replace('_', ' ')} (More Stable)
                          </span>
                        ) : resB.total_flaps < resA.total_flaps ? (
                          <span style={{ color: 'var(--accent-verdigris)', fontWeight: 700 }}>
                            🏆 {protoB.replace('_', ' ')} (More Stable)
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>🤝 Equal Flaps</span>
                        )}
                      </td>
                    </tr>

                    {/* Path Stretch */}
                    <tr>
                      <td style={{ padding: '0.6rem 1rem', fontWeight: 600 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <Sparkles size={14} color="var(--accent-brass)" />
                          Path Stretch (vs Oracle)
                        </div>
                      </td>
                      <td style={{ padding: '0.6rem 1rem' }}>{resA.stretch.toFixed(2)}x</td>
                      <td style={{ padding: '0.6rem 1rem' }}>{resB.stretch.toFixed(2)}x</td>
                      <td style={{ padding: '0.6rem 1rem' }}>
                        {Math.abs(resA.stretch - 1.0) < Math.abs(resB.stretch - 1.0) ? (
                          <span style={{ color: 'var(--accent-terracotta)', fontWeight: 700 }}>
                            🏆 {protoA.replace('_', ' ')} (Optimal Path)
                          </span>
                        ) : Math.abs(resB.stretch - 1.0) < Math.abs(resA.stretch - 1.0) ? (
                          <span style={{ color: 'var(--accent-verdigris)', fontWeight: 700 }}>
                            🏆 {protoB.replace('_', ' ')} (Optimal Path)
                          </span>
                        ) : (
                          <span style={{ color: 'var(--accent-brass)', fontWeight: 700 }}>
                            🤝 Both Optimal (1.00x)
                          </span>
                        )}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Course Architectural Insight Callout */}
              <div
                style={{
                  padding: '1rem',
                  border: '1px solid var(--border-brass)',
                  borderRadius: '6px',
                  background: 'oklch(from var(--accent-brass) l c h / 0.08)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
                  <CheckCircle2 size={16} color="var(--accent-brass)" />
                  <span style={{ fontWeight: 800, fontSize: '0.88rem' }}>Algorithmic Analysis & Takeaways</span>
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  {report.summary_notes.length > 0 ? (
                    report.summary_notes.map((note, idx) => <p key={idx}>• {note}</p>)
                  ) : (
                    <p>
                      Link State (OSPF) relies on synchronized link-state databases and local Dijkstra SPF execution,
                      providing deterministic convergence without route loops. Distance Vector (RIP) relies on iterative
                      neighbor vector updates with lower per-packet byte overhead but potential transient flaps under topology mutations.
                    </p>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div
              style={{
                textAlign: 'center',
                padding: '2rem 1rem',
                color: 'var(--text-muted)',
                fontSize: '0.85rem',
              }}
            >
              Select two algorithms above and click <strong>Run Visual Comparison Race</strong> to watch real packets stream between nodes side-by-side!
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
