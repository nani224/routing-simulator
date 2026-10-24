import React, { useState } from 'react';
import type { RouteEntry, TopologyData } from '../types';
import { Navigation, AlertOctagon, CheckCircle2, ArrowRight } from 'lucide-react';

interface PathTracerPanelProps {
  topology: TopologyData;
  allRoutes: Record<string, RouteEntry[]>;
  onPathChanged: (path: string[], loop: boolean) => void;
}

export const PathTracerPanel: React.FC<PathTracerPanelProps> = ({
  topology,
  allRoutes,
  onPathChanged,
}) => {
  const nodeIds = Object.keys(topology.nodes);
  const [srcNode, setSrcNode] = useState<string>(nodeIds[0] || 'R1');
  const [dstNode, setDstNode] = useState<string>(nodeIds[nodeIds.length - 1] || 'R6');

  // Compute routed path dynamically using current routing tables
  const computePath = (src: string, dst: string): { path: string[]; hasLoop: boolean; isBlackhole: boolean } => {
    const visited = new Set<string>();
    const path: string[] = [src];
    let curr = src;
    let hasLoop = false;
    let isBlackhole = false;

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

    return { path, hasLoop, isBlackhole };
  };

  const { path, hasLoop, isBlackhole } = computePath(srcNode, dstNode);

  // Notify canvas of active path and loop status
  React.useEffect(() => {
    onPathChanged(path, hasLoop);
  }, [srcNode, dstNode, allRoutes]);

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
              <span style={{ color: 'var(--accent-verdigris)', fontWeight: 800 }}>OPTIMAL ROUTED PATH</span>
            </>
          )}
        </div>

        <div style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
          {path.join(' ➔ ')}
        </div>
      </div>
    </div>
  );
};
