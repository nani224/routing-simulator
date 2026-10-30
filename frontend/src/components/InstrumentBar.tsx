import React from 'react';
import type { ProtocolType } from '../types';
import {
  Compass,
  Play,
  Pause,
  SkipForward,
  RotateCcw,
  Sliders,
  Radio,
  BookOpen,
  Share2,
  FileText,
  Sun,
  Moon,
  Zap,
  Activity,
  Layers,
  Sparkles,
} from 'lucide-react';

interface InstrumentBarProps {
  currentTopologyName: string;
  onSelectTopology: (name: string) => void;
  currentProtocol: ProtocolType;
  onSelectProtocol: (proto: ProtocolType) => void;
  isRunning: boolean;
  onTogglePlay: () => void;
  onStep: () => void;
  onReset: () => void;
  speed: number;
  onChangeSpeed: (spd: number) => void;
  simTime: number;
  isConverged: boolean;
  convTime: number;
  fps: number;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  isPhysicsActive: boolean;
  onTogglePhysics: () => void;
  selectedNode?: string | null;
  onToggleInspector?: () => void;
  onOpenCompare: () => void;
  onOpenScenarios: () => void;
  onOpenAttacks: () => void;
  hasActiveAttacks?: boolean;
  onOpenLogs: () => void;
  onOpenExport: () => void;
  onOpenExplain: () => void;
  onOpenSettings: () => void;
}

export const InstrumentBar: React.FC<InstrumentBarProps> = ({
  currentTopologyName,
  onSelectTopology,
  currentProtocol,
  onSelectProtocol,
  isRunning,
  onTogglePlay,
  onStep,
  onReset,
  speed,
  onChangeSpeed,
  simTime,
  isConverged,
  convTime,
  fps,
  theme,
  onToggleTheme,
  isPhysicsActive,
  onTogglePhysics,
  selectedNode,
  onToggleInspector,
  onOpenCompare,
  onOpenScenarios,
  onOpenAttacks,
  hasActiveAttacks = false,
  onOpenLogs,
  onOpenExport,
  onOpenExplain,
  onOpenSettings,
}) => {
  return (
    <header
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0.45rem 1rem',
        background: 'var(--surface-card)',
        borderBottom: '2px solid var(--border-brass)',
        boxShadow: 'var(--shadow-md)',
        zIndex: 50,
        gap: '0.75rem',
        flexWrap: 'nowrap',
        overflowX: 'auto',
      }}
    >
      {/* 1. Brand Logo & Course Team Badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexShrink: 0 }}>
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            background: 'var(--accent-brass)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#FFFFFF',
            boxShadow: 'var(--shadow-brass)',
          }}
        >
          <Compass size={18} />
        </div>
        <div>
          <div
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: '1.05rem',
              fontWeight: 800,
              letterSpacing: '0.05em',
              color: 'var(--text-primary)',
              lineHeight: 1.1,
            }}
          >
            RouteLab
          </div>
          <div
            style={{
              fontSize: '0.64rem',
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-muted)',
              letterSpacing: '0.04em',
            }}
          >
            TEAM 20 · CARTOGRAPHER
          </div>
        </div>
      </div>

      <div style={{ width: '1px', height: '24px', background: 'var(--border-ink)' }} />

      {/* 2. Topology & Protocol Selectors */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
        {/* Topology Selector */}
        <select
          value={currentTopologyName}
          onChange={(e) => onSelectTopology(e.target.value)}
          style={{
            background: 'var(--surface-inset)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border-ink)',
            borderRadius: '4px',
            padding: '0.35rem 0.6rem',
            fontSize: '0.8rem',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          <option value="course-6-node">Course 6-Node</option>
          <option value="course-8-node">Course 8-Node Mesh</option>
          <option value="course-10-node">Course 10-Node WAN</option>
          <option value="ring-10">Ring 10</option>
          <option value="scale-free-20">Scale-Free 20</option>
        </select>

        {/* Protocol Selector */}
        <select
          value={currentProtocol}
          onChange={(e) => onSelectProtocol(e.target.value as ProtocolType)}
          style={{
            background: 'var(--surface-inset)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border-brass)',
            borderRadius: '4px',
            padding: '0.35rem 0.6rem',
            fontSize: '0.8rem',
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          <option value="distance_vector">Distance Vector (RIP / Bellman-Ford)</option>
          <option value="link_state">Link State (OSPF / Dijkstra)</option>
          <option value="bgp_lite">BGP-Lite (Path Vector / AS_PATH)</option>
          <option value="flooding">Flooding Baseline</option>
          <option value="poisoning_attack">Poisoning Attack Simulation</option>
          <option value="secure_dv">Secure DV (Mitigated)</option>
        </select>
      </div>

      <div style={{ width: '1px', height: '24px', background: 'var(--border-ink)' }} />

      {/* 3. Playback Instruments */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexShrink: 0 }}>
        <button
          className={isRunning ? 'btn-brass' : 'btn-brass btn-brass-primary'}
          onClick={onTogglePlay}
          title={isRunning ? 'Pause Simulation' : 'Start Simulation'}
        >
          {isRunning ? <Pause size={14} /> : <Play size={14} />}
          {isRunning ? 'Pause' : 'Run'}
        </button>

        <button className="btn-brass" onClick={onStep} title="Step Forward 0.1s">
          <SkipForward size={14} />
          Step
        </button>

        <button className="btn-brass" onClick={onReset} title="Reset Simulation">
          <RotateCcw size={14} />
        </button>

        {/* Speed Slider */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', marginLeft: '0.3rem' }}>
          <span style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
            {speed.toFixed(1)}x
          </span>
          <input
            type="range"
            min="0.2"
            max="4.0"
            step="0.2"
            value={speed}
            onChange={(e) => onChangeSpeed(parseFloat(e.target.value))}
            style={{ width: '60px', accentColor: 'var(--accent-brass)' }}
          />
        </div>
      </div>

      <div style={{ width: '1px', height: '24px', background: 'var(--border-ink)' }} />

      {/* 4. Convergence Status Parchment Seal */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          padding: '0.25rem 0.6rem',
          background: isConverged
            ? 'oklch(from var(--accent-verdigris) l c h / 0.12)'
            : 'oklch(from var(--accent-amber) l c h / 0.12)',
          border: `1px solid ${
            isConverged ? 'var(--accent-verdigris)' : 'var(--accent-amber)'
          }`,
          borderRadius: '4px',
          flexShrink: 0,
        }}
      >
        <Activity
          size={14}
          color={isConverged ? 'var(--accent-verdigris)' : 'var(--accent-amber)'}
        />
        <div style={{ fontSize: '0.74rem', fontFamily: 'var(--font-mono)' }}>
          <span style={{ fontWeight: 700 }}>
            {isConverged ? 'CONVERGED' : 'CONVERGING...'}
          </span>{' '}
          {convTime > 0 && <span>({convTime.toFixed(3)}s)</span>}
        </div>
        <div
          style={{
            fontSize: '0.68rem',
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-muted)',
            borderLeft: '1px solid var(--border-ink)',
            paddingLeft: '0.4rem',
          }}
        >
          t={simTime.toFixed(2)}s · {fps} FPS
        </div>
      </div>

      <div style={{ width: '1px', height: '24px', background: 'var(--border-ink)' }} />

      {/* 5. Tool Triggers */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexShrink: 0 }}>
        <button
          className={isPhysicsActive ? 'btn-brass btn-brass-primary' : 'btn-brass'}
          onClick={onTogglePhysics}
          title="Toggle Force-Directed Auto-Layout"
        >
          <Sparkles size={13} />
          Layout
        </button>

        <button
          className={selectedNode ? 'btn-brass btn-brass-primary' : 'btn-brass'}
          onClick={onToggleInspector}
          title="Toggle Node Inspector (Routing Tables & LSDB)"
        >
          <Compass size={13} />
          {selectedNode ? `Inspect (${selectedNode})` : 'Inspect'}
        </button>

        <button className="btn-brass" onClick={onOpenCompare} title="Side-by-Side Algorithm Comparison">
          <Layers size={13} />
          Compare
        </button>

        <button
          className={hasActiveAttacks ? 'btn-brass btn-brass-primary' : 'btn-brass'}
          style={
            hasActiveAttacks
              ? {
                  background: 'var(--accent-crimson)',
                  borderColor: 'var(--accent-crimson)',
                  color: '#FFFFFF',
                  boxShadow: '0 0 8px oklch(from var(--accent-crimson) l c h / 0.5)',
                }
              : undefined
          }
          onClick={onOpenAttacks}
          title={
            hasActiveAttacks
              ? 'Active Attacks / Perturbations running — Click to inspect or clear'
              : 'Failure & Poisoning Attack Lab'
          }
        >
          <Zap size={13} />
          {hasActiveAttacks ? 'Attacks (Active)' : 'Attacks'}
        </button>

        <button className="btn-brass" onClick={onOpenScenarios} title="Course Preset Scenarios">
          <Radio size={13} />
          Scenarios
        </button>

        <button className="btn-brass" onClick={onOpenLogs} title="Simulation Event Stream">
          <FileText size={13} />
          Logs
        </button>

        <button className="btn-brass" onClick={onOpenExport} title="Export Maps, CSV, JSON, PDF">
          <Share2 size={13} />
          Export
        </button>

        <button className="btn-brass" onClick={onOpenExplain} title="Interactive Guided Walkthrough">
          <BookOpen size={13} />
          Explain
        </button>

        <button className="btn-brass" onClick={onOpenSettings} title="Settings & Parameters">
          <Sliders size={13} />
        </button>

        <button
          className="btn-brass"
          onClick={onToggleTheme}
          title={theme === 'light' ? 'Switch to Nautical Blueprint (Dark)' : 'Switch to Antique Parchment (Light)'}
        >
          {theme === 'light' ? <Moon size={13} /> : <Sun size={13} />}
        </button>
      </div>
    </header>
  );
};
