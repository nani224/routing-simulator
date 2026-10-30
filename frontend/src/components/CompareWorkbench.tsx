import React, { useState } from 'react';
import type { TopologyData, ProtocolType, ComparisonMetrics } from '../types';
import { RouteLabApi } from '../services/api';
import { X, Layers, Play, CheckCircle2 } from 'lucide-react';

interface CompareWorkbenchProps {
  isOpen: boolean;
  onClose: () => void;
  topology: TopologyData;
}

export const CompareWorkbench: React.FC<CompareWorkbenchProps> = ({
  isOpen,
  onClose,
  topology,
}) => {
  const [protoA, setProtoA] = useState<ProtocolType>('distance_vector');
  const [protoB, setProtoB] = useState<ProtocolType>('link_state');
  const [results, setResults] = useState<Record<string, ComparisonMetrics> | null>(null);
  const [isComparing, setIsComparing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleRunComparison = async () => {
    setIsComparing(true);
    setError(null);
    try {
      const data = await RouteLabApi.runCompare(topology, [protoA, protoB], 5.0);
      setResults(data);
    } catch (err: any) {
      setError(err?.message || 'Comparison benchmark failed on backend');
    } finally {
      setIsComparing(false);
    }
  };

  const resA = results ? results[protoA] : null;
  const resB = results ? results[protoB] : null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(20, 16, 12, 0.7)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        padding: '1.5rem',
      }}
    >
      <div
        className="carto-card"
        style={{
          width: '760px',
          maxWidth: '100%',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--surface-card)',
          border: '2px solid var(--border-brass)',
          boxShadow: 'var(--shadow-lg)',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Layers size={20} color="var(--accent-brass)" />
            <div>
              <div style={{ fontWeight: 800, fontFamily: 'var(--font-heading)', fontSize: '1.05rem' }}>
                Comparative Algorithm Evaluation Workbench
              </div>
              <div style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                COURSE SCENARIO EVALUATION · IDENTICAL TOPOLOGY & EVENT SCHEDULE
              </div>
            </div>
          </div>
          <button className="btn-brass" style={{ width: '32px', height: '32px', padding: 0 }} onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        {/* Algorithm Configuration Bar */}
        <div
          style={{
            padding: '1rem 1.4rem',
            borderBottom: '1px solid var(--border-ink)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            background: 'var(--surface-card)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flex: 1 }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>Protocol A:</span>
            <select
              value={protoA}
              onChange={(e) => setProtoA(e.target.value as ProtocolType)}
              style={{
                flex: 1,
                padding: '0.4rem',
                borderRadius: '4px',
                border: '1px solid var(--border-ink)',
                background: 'var(--surface-inset)',
                color: 'var(--text-primary)',
                fontWeight: 600,
              }}
            >
              <option value="distance_vector">Distance Vector (Bellman-Ford)</option>
              <option value="link_state">Link State (OSPF / Dijkstra)</option>
              <option value="bgp_lite">BGP-Lite (Path Vector)</option>
              <option value="flooding">Flooding Baseline</option>
            </select>
          </div>

          <div style={{ fontWeight: 800, color: 'var(--accent-brass)' }}>VS</div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flex: 1 }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>Protocol B:</span>
            <select
              value={protoB}
              onChange={(e) => setProtoB(e.target.value as ProtocolType)}
              style={{
                flex: 1,
                padding: '0.4rem',
                borderRadius: '4px',
                border: '1px solid var(--border-ink)',
                background: 'var(--surface-inset)',
                color: 'var(--text-primary)',
                fontWeight: 600,
              }}
            >
              <option value="link_state">Link State (OSPF / Dijkstra)</option>
              <option value="distance_vector">Distance Vector (Bellman-Ford)</option>
              <option value="bgp_lite">BGP-Lite (Path Vector)</option>
              <option value="flooding">Flooding Baseline</option>
            </select>
          </div>

          <button
            className="btn-brass btn-brass-primary"
            onClick={handleRunComparison}
            disabled={isComparing}
          >
            <Play size={14} />
            {isComparing ? 'Running Benchmark...' : 'Run Benchmark'}
          </button>
        </div>

        {/* Results Area */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.4rem' }}>
          {error && (
            <div
              style={{
                padding: '0.9rem',
                marginBottom: '1rem',
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

          {!results ? (
            <div
              style={{
                textAlign: 'center',
                padding: '3rem 1rem',
                color: 'var(--text-muted)',
                fontSize: '0.85rem',
              }}
            >
              Select two routing algorithms above and click <strong>Run Benchmark</strong> to compare convergence speed, message count, byte overhead, and route flaps on the active {topology.name} topology.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.4rem' }}>
              {/* Dual Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                {/* Card A */}
                <div
                  style={{
                    padding: '1rem',
                    border: '1px solid var(--border-ink)',
                    borderRadius: '6px',
                    background: 'var(--surface-inset)',
                  }}
                >
                  <div style={{ fontWeight: 800, fontSize: '0.95rem', marginBottom: '0.6rem', color: 'var(--accent-terracotta)' }}>
                    {resA?.protocol || protoA}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}>
                    <div>Convergence Time: <strong>{resA?.convergence_time_s.toFixed(3)}s</strong></div>
                    <div>Control Messages: <strong>{resA?.total_messages}</strong></div>
                    <div>Control Bytes: <strong>{resA?.total_bytes.toLocaleString()} B</strong></div>
                    <div>Route Flaps: <strong>{resA?.total_flaps}</strong></div>
                    <div>Path Stretch: <strong>{resA?.stretch.toFixed(2)}x</strong></div>
                  </div>
                </div>

                {/* Card B */}
                <div
                  style={{
                    padding: '1rem',
                    border: '1px solid var(--border-ink)',
                    borderRadius: '6px',
                    background: 'var(--surface-inset)',
                  }}
                >
                  <div style={{ fontWeight: 800, fontSize: '0.95rem', marginBottom: '0.6rem', color: 'var(--accent-verdigris)' }}>
                    {resB?.protocol || protoB}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}>
                    <div>Convergence Time: <strong>{resB?.convergence_time_s.toFixed(3)}s</strong></div>
                    <div>Control Messages: <strong>{resB?.total_messages}</strong></div>
                    <div>Control Bytes: <strong>{resB?.total_bytes.toLocaleString()} B</strong></div>
                    <div>Route Flaps: <strong>{resB?.total_flaps}</strong></div>
                    <div>Path Stretch: <strong>{resB?.stretch.toFixed(2)}x</strong></div>
                  </div>
                </div>
              </div>

              {/* Comparative Analysis Callout */}
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
                  <span style={{ fontWeight: 700, fontSize: '0.88rem' }}>Course Comparative Finding</span>
                </div>
                <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                  {resA && resB && resA.convergence_time_s < resB.convergence_time_s
                    ? `${resA.protocol} converged faster (${resA.convergence_time_s}s vs ${resB.convergence_time_s}s) with ${(resB.convergence_time_s / (resA.convergence_time_s || 0.001)).toFixed(1)}x speedup.`
                    : `${resB?.protocol} achieved faster convergence with ${resB?.total_messages} control messages compared to ${resA?.total_messages} messages.`}
                  {' '}Link State trades initial flooding overhead for deterministic Dijkstra SPF recalculation without transient counting-to-infinity.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
