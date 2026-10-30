import React, { useState } from 'react';
import type { RouteEntry, TopologyData } from '../types';
import { X, Power, ShieldCheck, Database, ListTree, Activity } from 'lucide-react';

interface NodeInspectorDrawerProps {
  nodeId: string | null;
  onClose: () => void;
  topology: TopologyData;
  routes: RouteEntry[];
  protocol: string;
  isCrashed: boolean;
  onCrashNode: (nodeId: string) => void;
  onRecoverNode: (nodeId: string) => void;
  packetsSent: number;
  packetsReceived: number;
  flapsCount: number;
}

export const NodeInspectorDrawer: React.FC<NodeInspectorDrawerProps> = ({
  nodeId,
  onClose,
  topology,
  routes,
  protocol,
  isCrashed,
  onCrashNode,
  onRecoverNode,
  packetsSent,
  packetsReceived,
  flapsCount,
}) => {
  const [activeTab, setActiveTab] = useState<'routes' | 'neighbors' | 'lsdb'>('routes');

  if (!nodeId) return null;

  const nodeData = topology.nodes[nodeId];
  const neighborLinks = topology.links.filter(
    (l) => l.source === nodeId || l.target === nodeId
  );

  return (
    <div
      className="carto-card"
      style={{
        position: 'absolute',
        top: '60px',
        right: '16px',
        bottom: '80px',
        width: '380px',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 40,
        boxShadow: 'var(--shadow-lg)',
        border: '2px solid var(--border-brass)',
        background: 'var(--surface-card)',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.75rem 1rem',
          borderBottom: '1px solid var(--border-ink)',
          background: 'var(--surface-inset)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div
            style={{
              width: '28px',
              height: '28px',
              borderRadius: '50%',
              background: isCrashed ? 'var(--accent-crimson)' : 'var(--accent-brass)',
              color: '#FFFFFF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 800,
              fontFamily: 'var(--font-display)',
              fontSize: '0.85rem',
            }}
          >
            {nodeId}
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.92rem', fontFamily: 'var(--font-heading)' }}>
              Router {nodeId}
            </div>
            <div style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              {nodeData?.as_number ? `AS${nodeData.as_number} · ` : ''}
              {isCrashed ? 'STATUS: CRASHED' : 'STATUS: RUNNING'}
            </div>
          </div>
        </div>

        <button
          className="btn-brass"
          style={{ width: '28px', height: '28px', padding: 0 }}
          onClick={onClose}
        >
          <X size={14} />
        </button>
      </div>

      {/* Action Bar (Crash / Recover) */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.5rem 1rem',
          borderBottom: '1px solid var(--border-ink)',
          background: 'var(--surface-card)',
        }}
      >
        <div style={{ display: 'flex', gap: '0.4rem' }}>
          {isCrashed ? (
            <button
              className="btn-brass btn-brass-primary"
              style={{ background: 'var(--accent-verdigris)', borderColor: 'var(--accent-verdigris)' }}
              onClick={() => onRecoverNode(nodeId)}
            >
              <ShieldCheck size={13} />
              Recover Node
            </button>
          ) : (
            <button
              className="btn-brass"
              style={{ color: 'var(--accent-crimson)', borderColor: 'var(--accent-crimson)' }}
              onClick={() => onCrashNode(nodeId)}
            >
              <Power size={13} />
              Crash Node
            </button>
          )}
        </div>

        {/* Telemetry Chips */}
        <div style={{ display: 'flex', gap: '0.4rem', fontSize: '0.68rem', fontFamily: 'var(--font-mono)' }}>
          <span title="Packets Sent / Received">
            TX:{packetsSent} RX:{packetsReceived}
          </span>
          <span style={{ color: flapsCount > 0 ? 'var(--accent-crimson)' : 'var(--text-muted)' }} title="Route Flaps">
            Flaps:{flapsCount}
          </span>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div
        style={{
          display: 'flex',
          borderBottom: '1px solid var(--border-ink)',
          background: 'var(--surface-inset)',
        }}
      >
        <button
          style={{
            flex: 1,
            padding: '0.4rem',
            background: activeTab === 'routes' ? 'var(--surface-card)' : 'transparent',
            border: 'none',
            borderBottom: activeTab === 'routes' ? '2px solid var(--accent-brass)' : 'none',
            fontWeight: 600,
            fontSize: '0.74rem',
            cursor: 'pointer',
            color: activeTab === 'routes' ? 'var(--text-primary)' : 'var(--text-muted)',
          }}
          onClick={() => setActiveTab('routes')}
        >
          <ListTree size={12} style={{ display: 'inline', marginRight: '4px' }} />
          Routing Table
        </button>

        <button
          style={{
            flex: 1,
            padding: '0.4rem',
            background: activeTab === 'neighbors' ? 'var(--surface-card)' : 'transparent',
            border: 'none',
            borderBottom: activeTab === 'neighbors' ? '2px solid var(--accent-brass)' : 'none',
            fontWeight: 600,
            fontSize: '0.74rem',
            cursor: 'pointer',
            color: activeTab === 'neighbors' ? 'var(--text-primary)' : 'var(--text-muted)',
          }}
          onClick={() => setActiveTab('neighbors')}
        >
          <Activity size={12} style={{ display: 'inline', marginRight: '4px' }} />
          Neighbors ({neighborLinks.length})
        </button>

        {protocol.includes('ls') && (
          <button
            style={{
              flex: 1,
              padding: '0.4rem',
              background: activeTab === 'lsdb' ? 'var(--surface-card)' : 'transparent',
              border: 'none',
              borderBottom: activeTab === 'lsdb' ? '2px solid var(--accent-brass)' : 'none',
              fontWeight: 600,
              fontSize: '0.74rem',
              cursor: 'pointer',
              color: activeTab === 'lsdb' ? 'var(--text-primary)' : 'var(--text-muted)',
            }}
            onClick={() => setActiveTab('lsdb')}
          >
            <Database size={12} style={{ display: 'inline', marginRight: '4px' }} />
            LSDB
          </button>
        )}
      </div>

      {/* Content Area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem' }}>
        {activeTab === 'routes' && (
          <div>
            {routes.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                No active routes calculated yet
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Dest</th>
                    <th>Next Hop</th>
                    <th>
                      {protocol.includes('flood')
                        ? 'Hop Count'
                        : protocol.includes('bgp')
                        ? 'AS-Path Length'
                        : 'Cumulative Cost'}
                    </th>
                    {protocol.includes('bgp') ? <th>AS_PATH Sequence</th> : <th>Protocol</th>}
                  </tr>
                </thead>
                <tbody>
                  {routes.map((r, i) => {
                    const metricDisplay = protocol.includes('flood')
                      ? `${r.metric} hops`
                      : protocol.includes('bgp')
                      ? `${r.as_path ? r.as_path.length : 1} AS hops`
                      : r.metric >= 9999
                      ? '∞ (POISON)'
                      : r.metric >= 16 && protocol.includes('dv')
                      ? '16 (UNREACHABLE)'
                      : `${r.metric} cost`;

                    return (
                      <tr key={i}>
                        <td style={{ fontWeight: 700 }}>{r.destination}</td>
                        <td>{r.next_hop || 'DIRECT'}</td>
                        <td
                          style={{
                            color:
                              r.metric >= 16 || metricDisplay.includes('∞')
                                ? 'var(--accent-crimson)'
                                : 'inherit',
                          }}
                        >
                          {metricDisplay}
                        </td>
                        {protocol.includes('bgp') ? (
                          <td style={{ color: 'var(--accent-cobalt)', fontSize: '0.7rem' }}>
                            [{r.as_path ? r.as_path.join(' ➔ ') : 'LOCAL'}]
                          </td>
                        ) : (
                          <td>
                            <span className={`badge-protocol badge-${protocol.slice(0, 2)}`}>
                              {protocol.slice(0, 2).toUpperCase()}
                            </span>
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}

        {activeTab === 'neighbors' && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Neighbor</th>
                <th>Cost</th>
                <th>Latency</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {neighborLinks.map((link, i) => {
                const nbrId = link.source === nodeId ? link.target : link.source;
                return (
                  <tr key={i}>
                    <td style={{ fontWeight: 700 }}>{nbrId}</td>
                    <td>{link.cost}</td>
                    <td>{link.latency_ms}ms</td>
                    <td>
                      <span
                        style={{
                          color: link.is_up ? 'var(--accent-verdigris)' : 'var(--accent-crimson)',
                          fontWeight: 700,
                        }}
                      >
                        {link.is_up ? 'ONLINE' : 'DOWN'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}

        {activeTab === 'lsdb' && (
          <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
            <div style={{ marginBottom: '0.4rem', fontWeight: 700, color: 'var(--accent-verdigris)' }}>
              Link State Database (LSDB) View:
            </div>
            {Object.keys(topology.nodes).map((nid) => (
              <div
                key={nid}
                style={{
                  padding: '0.4rem',
                  border: '1px solid var(--border-ink)',
                  borderRadius: '4px',
                  marginBottom: '0.4rem',
                  background: 'var(--surface-inset)',
                }}
              >
                <div style={{ fontWeight: 700 }}>LSA Origin: Router {nid}</div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.68rem' }}>
                  Seq: 0x80000001 · MaxAge: 3600s
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
