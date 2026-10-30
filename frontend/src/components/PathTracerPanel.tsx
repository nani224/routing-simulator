import React, { useState } from 'react';
import type { RouteEntry, TopologyData } from '../types';
import { Navigation, AlertOctagon, CheckCircle2, ArrowRight, Send } from 'lucide-react';

interface PathTracerPanelProps {
  topology: TopologyData;
  allRoutes: Record<string, RouteEntry[]>;
  onPathChanged: (path: string[], loop: boolean) => void;
  onSendProbePacket?: (path: string[]) => void;
  protocol?: string;
}

export const PathTracerPanel: React.FC<PathTracerPanelProps> = ({
  topology,
  allRoutes,
  onPathChanged,
  onSendProbePacket,
  protocol = 'distance_vector',
}) => {
  const nodeIds = Object.keys(topology.nodes);
  const [srcNode, setSrcNode] = useState<string>(nodeIds[0] || 'R1');
  const [dstNode, setDstNode] = useState<string>(nodeIds[nodeIds.length - 1] || 'R6');

  // Compute routed path dynamically using current routing tables
  const computePath = (
    src: string,
    dst: string
  ): { path: string[]; hasLoop: boolean; isBlackhole: boolean; totalCost: number; hops: number } => {
    const visited = new Set<string>();
    const path: string[] = [src];
    let curr = src;
    let hasLoop = false;
    let isBlackhole = false;
    let totalCost = 0;

    while (curr !== dst) {
      visited.add(curr);
      const routes = allRoutes[curr] || [];
      const entry = routes.find((r) => r.destination === dst);

      if (!entry || !entry.next_hop) {
        // No route or null next-hop
        isBlackhole = true;
        break;
      }

      const next = entry.next_hop;
      // Accumulate link cost from topology
      const link = topology.links.find(
        (l) => (l.source === curr && l.target === next) || (l.source === next && l.target === curr)
      );
      if (link) totalCost += link.cost;

      if (visited.has(next)) {
        // Loop detected!
        path.push(next);
        hasLoop = true;
        break;
      }

      path.push(next);
      curr = next;

      if (path.length > 20) {
        hasLoop = true;
        break;
      }
    }

    return { path, hasLoop, isBlackhole, totalCost, hops: Math.max(0, path.length - 1) };
  };

  const { path, hasLoop, isBlackhole, totalCost, hops } = computePath(srcNode, dstNode);

  const getProtocolCriteriaLabel = () => {
    if (protocol.includes('flood')) return 'HOP-COUNT PATH (Flooding Discovery)';
    if (protocol.includes('bgp')) return 'SELECTED AS-PATH (Policy Path-Vector)';
    if (protocol.includes('ls')) return 'DIJKSTRA SHORTEST PATH (Link-State SPF)';
    return 'BELLMAN-FORD SHORTEST PATH (Distance Vector)';
  };

  const getMetricSummary = () => {
    if (protocol.includes('flood')) return `Hop Count: ${hops} hops`;
    if (protocol.includes('bgp')) {
      const asSequence = path.map((nid) => topology.nodes[nid]?.as_number || 100);
      return `AS-Path: [${asSequence.join(' ➔ ')}] (${asSequence.length} AS hops)`;
    }
    return `Cumulative Metric Cost: ${totalCost}`;
  };

  // Notify canvas of active path and loop status ONLY when path value or loop state actually changes
  const pathKey = path.join('->');
  const prevPathKeyRef = React.useRef<string>('');
  const prevLoopRef = React.useRef<boolean>(false);

  React.useEffect(() => {
    if (prevPathKeyRef.current !== pathKey || prevLoopRef.current !== hasLoop) {
      prevPathKeyRef.current = pathKey;
      prevLoopRef.current = hasLoop;
      onPathChanged(path, hasLoop);
    }
  }, [pathKey, hasLoop, onPathChanged]);

  return (
    <div
      className="carto-card"
      style={{
        position: 'absolute',
        top: '60px',
        left: '16px',
        width: '320px',
        background: 'var(--surface-card)',
        border: '2px solid var(--border-brass)',
        padding: '0.8rem 1rem',
        zIndex: 30,
        boxShadow: 'var(--shadow-md)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem' }}>
        <Navigation size={15} color="var(--accent-brass)" />
        <span style={{ fontWeight: 800, fontFamily: 'var(--font-heading)', fontSize: '0.86rem' }}>
          Golden Quill Path Tracer
        </span>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.6rem' }}>
        <div style={{ flex: 1 }}>
          <label style={{ fontSize: '0.66rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            SOURCE
          </label>
          <select
            value={srcNode}
            onChange={(e) => setSrcNode(e.target.value)}
            style={{
              width: '100%',
              padding: '0.3rem',
              borderRadius: '4px',
              border: '1px solid var(--border-ink)',
              background: 'var(--surface-inset)',
              color: 'var(--text-primary)',
              fontWeight: 700,
            }}
          >
            {nodeIds.map((nid) => (
              <option key={nid} value={nid}>
                {nid}
              </option>
            ))}
          </select>
        </div>

        <ArrowRight size={14} style={{ marginTop: '14px', color: 'var(--text-muted)' }} />

        <div style={{ flex: 1 }}>
          <label style={{ fontSize: '0.66rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            DESTINATION
          </label>
          <select
            value={dstNode}
            onChange={(e) => setDstNode(e.target.value)}
            style={{
              width: '100%',
              padding: '0.3rem',
              borderRadius: '4px',
              border: '1px solid var(--border-ink)',
              background: 'var(--surface-inset)',
              color: 'var(--text-primary)',
              fontWeight: 700,
            }}
          >
            {nodeIds.map((nid) => (
              <option key={nid} value={nid}>
                {nid}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Path Breadcrumb & Status */}
      <div
        style={{
          padding: '0.5rem',
          borderRadius: '4px',
          background: hasLoop
            ? 'oklch(from var(--accent-crimson) l c h / 0.12)'
            : isBlackhole
            ? 'oklch(from var(--accent-amber) l c h / 0.12)'
            : 'var(--surface-inset)',
          border: `1px solid ${
            hasLoop ? 'var(--accent-crimson)' : isBlackhole ? 'var(--accent-amber)' : 'var(--border-ink)'
          }`,
          fontFamily: 'var(--font-mono)',
          fontSize: '0.74rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.3rem' }}>
          {hasLoop ? (
            <>
              <AlertOctagon size={13} color="var(--accent-crimson)" />
              <span style={{ color: 'var(--accent-crimson)', fontWeight: 800 }}>ROUTING LOOP DETECTED</span>
            </>
          ) : isBlackhole ? (
            <>
              <AlertOctagon size={13} color="var(--accent-amber)" />
              <span style={{ color: 'var(--accent-amber)', fontWeight: 800 }}>BLACKHOLE / UNREACHABLE</span>
            </>
          ) : (
            <>
              <CheckCircle2 size={13} color="var(--accent-verdigris)" />
              <span style={{ color: 'var(--accent-verdigris)', fontWeight: 800 }}>
                {getProtocolCriteriaLabel()}
              </span>
            </>
          )}
        </div>

        <div style={{ color: 'var(--text-primary)', fontWeight: 600, marginBottom: '0.3rem' }}>
          {path.join(' ➔ ')}
        </div>

        {!hasLoop && !isBlackhole && path.length > 1 && onSendProbePacket && (
          <button
            onClick={() => onSendProbePacket(path)}
            className="btn-brass"
            style={{
              marginTop: '0.4rem',
              width: '100%',
              padding: '0.35rem 0.6rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.4rem',
              fontSize: '0.72rem',
              fontWeight: 700,
              cursor: 'pointer',
            }}
            title="Dispatch an authentic live probe packet along this routed path"
          >
            <Send size={12} />
            Send Live Probe Packet ({path[0]} ➔ {path[path.length - 1]})
          </button>
        )}

        {!hasLoop && !isBlackhole && (
          <div style={{ fontSize: '0.68rem', color: 'var(--text-secondary)' }}>
            {getMetricSummary()}
          </div>
        )}
      </div>
    </div>
  );
};
