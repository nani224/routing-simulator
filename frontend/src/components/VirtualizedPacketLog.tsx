import React, { useState, useRef, useEffect } from 'react';
import type { SimEventItem } from '../types';
import { X, FileText, Search, Trash2, ArrowDownCircle } from 'lucide-react';

interface VirtualizedPacketLogProps {
  isOpen: boolean;
  onClose: () => void;
  events: SimEventItem[];
  onClear: () => void;
}

export const VirtualizedPacketLog: React.FC<VirtualizedPacketLogProps> = ({
  isOpen,
  onClose,
  events,
  onClear,
}) => {
  const [search, setSearch] = useState<string>('');
  const [filterType, setFilterType] = useState<string>('all');
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const logEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [events, autoScroll]);

  if (!isOpen) return null;

  const filteredEvents = events.filter((ev) => {
    if (filterType !== 'all' && !ev.type.includes(filterType)) return false;
    if (search) {
      const q = search.toLowerCase();
      const matchSrc = ev.src.toLowerCase().includes(q);
      const matchType = ev.type.toLowerCase().includes(q);
      const matchData = JSON.stringify(ev.data).toLowerCase().includes(q);
      return matchSrc || matchType || matchData;
    }
    return true;
  });

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
          width: '840px',
          maxWidth: '100%',
          height: '80vh',
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
            padding: '0.8rem 1.2rem',
            borderBottom: '1px solid var(--border-ink)',
            background: 'var(--surface-inset)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <FileText size={18} color="var(--accent-brass)" />
            <div>
              <div style={{ fontWeight: 800, fontFamily: 'var(--font-heading)', fontSize: '1rem' }}>
                Simulation Event & Packet Stream Log
              </div>
              <div style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                {filteredEvents.length} RECORDED EVENTS · HIGH-RESOLUTION TIMESTAMPS
              </div>
            </div>
          </div>
          <button className="btn-brass" style={{ width: '30px', height: '30px', padding: 0 }} onClick={onClose}>
            <X size={15} />
          </button>
        </div>

        {/* Toolbar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.6rem',
            padding: '0.6rem 1.2rem',
            borderBottom: '1px solid var(--border-ink)',
            background: 'var(--surface-card)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flex: 1, background: 'var(--surface-inset)', padding: '0.3rem 0.6rem', borderRadius: '4px', border: '1px solid var(--border-ink)' }}>
            <Search size={14} color="var(--text-muted)" />
            <input
              type="text"
              placeholder="Filter by node ID, packet type, payload..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: '100%',
                background: 'transparent',
                border: 'none',
                outline: 'none',
                color: 'var(--text-primary)',
                fontSize: '0.78rem',
              }}
            />
          </div>

          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            style={{
              padding: '0.35rem 0.6rem',
              borderRadius: '4px',
              border: '1px solid var(--border-ink)',
              background: 'var(--surface-inset)',
              color: 'var(--text-primary)',
              fontSize: '0.78rem',
            }}
          >
            <option value="all">All Events</option>
            <option value="packet">Packets</option>
            <option value="link">Link State</option>
            <option value="node">Node State</option>
            <option value="convergence">Convergence</option>
            <option value="attack">Attacks</option>
          </select>

          <button
            className={autoScroll ? 'btn-brass btn-brass-primary' : 'btn-brass'}
            onClick={() => setAutoScroll((v) => !v)}
            title="Toggle Auto-Scroll"
          >
            <ArrowDownCircle size={13} />
            Auto-Scroll
          </button>

          <button className="btn-brass" onClick={onClear} title="Clear Log">
            <Trash2 size={13} />
            Clear
          </button>
        </div>

        {/* Table Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: '60px' }}>Seq</th>
                <th style={{ width: '90px' }}>Time (s)</th>
                <th style={{ width: '130px' }}>Type</th>
                <th style={{ width: '90px' }}>Source</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {filteredEvents.map((ev, i) => (
                <tr key={i}>
                  <td style={{ color: 'var(--text-muted)' }}>#{ev.seq}</td>
                  <td style={{ fontWeight: 600 }}>{ev.ts.toFixed(4)}s</td>
                  <td>
                    <span
                      style={{
                        padding: '0.1rem 0.35rem',
                        borderRadius: '3px',
                        fontSize: '0.68rem',
                        fontWeight: 700,
                        background: ev.type.includes('attack')
                          ? 'oklch(from var(--accent-crimson) l c h / 0.15)'
                          : ev.type.includes('convergence')
                          ? 'oklch(from var(--accent-verdigris) l c h / 0.15)'
                          : 'var(--surface-inset)',
                        color: ev.type.includes('attack')
                          ? 'var(--accent-crimson)'
                          : ev.type.includes('convergence')
                          ? 'var(--accent-verdigris)'
                          : 'var(--text-primary)',
                      }}
                    >
                      {ev.type}
                    </span>
                  </td>
                  <td style={{ fontWeight: 700 }}>{ev.src}</td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.72rem' }}>
                    {JSON.stringify(ev.data)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
};
