import React, { useState } from 'react';
import { X, Sliders, Volume2, Cpu, Globe, Gauge } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  quiescenceWindow: number;
  onUpdateQuiescence: (val: number) => void;
  soundEnabled: boolean;
  onToggleSound: () => void;
  clockMode: 'virtual' | 'realtime';
  onUpdateClockMode: (mode: 'virtual' | 'realtime') => void;
  wsUrl: string;
  onUpdateWsUrl: (url: string) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  quiescenceWindow,
  onUpdateQuiescence,
  soundEnabled,
  onToggleSound,
  clockMode,
  onUpdateClockMode,
  wsUrl,
  onUpdateWsUrl,
}) => {
  const [localWsUrl, setLocalWsUrl] = useState<string>(wsUrl);

  if (!isOpen) return null;

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
          width: '540px',
          maxWidth: '100%',
          background: 'var(--surface-card)',
          border: '2px solid var(--border-brass)',
          boxShadow: 'var(--shadow-lg)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.85rem 1.2rem',
            borderBottom: '1px solid var(--border-ink)',
            background: 'var(--surface-inset)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Sliders size={18} color="var(--accent-brass)" />
            <div>
              <div style={{ fontWeight: 800, fontFamily: 'var(--font-heading)', fontSize: '1rem' }}>
                Simulation & Drafting Table Settings
              </div>
              <div style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                CALIBRATE SIMULATION TIMING & SOCKET ENDPOINTS
              </div>
            </div>
          </div>
          <button className="btn-brass" style={{ width: '30px', height: '30px', padding: 0 }} onClick={onClose}>
            <X size={15} />
          </button>
        </div>

        {/* Form Body */}
        <div style={{ padding: '1.4rem', display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
          {/* Clock Mode */}
          <div
            style={{
              padding: '0.8rem 1rem',
              border: '1px solid var(--border-ink)',
              borderRadius: '6px',
              background: 'var(--surface-inset)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
              <Cpu size={16} color="var(--accent-brass)" />
              <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>Simulation Clock Mode</span>
            </div>
            <div style={{ display: 'flex', gap: '0.6rem' }}>
              <button
                className={clockMode === 'virtual' ? 'btn-brass btn-brass-primary' : 'btn-brass'}
                style={{ flex: 1 }}
                onClick={() => onUpdateClockMode('virtual')}
              >
                Deterministic Virtual Clock
              </button>
              <button
                className={clockMode === 'realtime' ? 'btn-brass btn-brass-primary' : 'btn-brass'}
                style={{ flex: 1 }}
                onClick={() => onUpdateClockMode('realtime')}
              >
                Wall-Clock Realtime
              </button>
            </div>
          </div>

          {/* Quiescence Window */}
          <div
            style={{
              padding: '0.8rem 1rem',
              border: '1px solid var(--border-ink)',
              borderRadius: '6px',
              background: 'var(--surface-inset)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Gauge size={16} color="var(--accent-brass)" />
                <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>Convergence Quiescence Window</span>
              </div>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '0.82rem' }}>
                {quiescenceWindow.toFixed(2)}s
              </span>
            </div>
            <input
              type="range"
              min="0.1"
              max="2.0"
              step="0.05"
              value={quiescenceWindow}
              onChange={(e) => onUpdateQuiescence(parseFloat(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--accent-brass)' }}
            />
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
              Duration of zero routing table flaps & zero in-flight messages required to declare convergence.
            </div>
          </div>

          {/* Audio Effects */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.8rem 1rem',
              border: '1px solid var(--border-ink)',
              borderRadius: '6px',
              background: 'var(--surface-inset)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Volume2 size={16} color="var(--accent-brass)" />
              <div>
                <div style={{ fontWeight: 700, fontSize: '0.85rem' }}>Acoustic Cartographer Cues</div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                  Parchment quill ticks and convergence chime sounds
                </div>
              </div>
            </div>
            <button
              className={soundEnabled ? 'btn-brass btn-brass-primary' : 'btn-brass'}
              onClick={onToggleSound}
            >
              {soundEnabled ? 'Enabled' : 'Muted'}
            </button>
          </div>

          {/* WebSocket Server Endpoint */}
          <div
            style={{
              padding: '0.8rem 1rem',
              border: '1px solid var(--border-ink)',
              borderRadius: '6px',
              background: 'var(--surface-inset)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
              <Globe size={16} color="var(--accent-brass)" />
              <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>FastAPI WebSocket Endpoint</span>
            </div>
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              <input
                type="text"
                value={localWsUrl}
                onChange={(e) => setLocalWsUrl(e.target.value)}
                style={{
                  flex: 1,
                  padding: '0.35rem 0.6rem',
                  borderRadius: '4px',
                  border: '1px solid var(--border-ink)',
                  background: 'var(--surface-card)',
                  color: 'var(--text-primary)',
                  fontSize: '0.78rem',
                  fontFamily: 'var(--font-mono)',
                }}
              />
              <button
                className="btn-brass"
                onClick={() => {
                  onUpdateWsUrl(localWsUrl);
                  onClose();
                }}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
