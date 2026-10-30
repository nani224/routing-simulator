import React from 'react';
import { Play, Pause, SkipBack, SkipForward, Clock } from 'lucide-react';
import type { SimEventItem } from '../types';

interface TimelineScrubberProps {
  currentTime: number;
  maxTime: number;
  isRunning: boolean;
  onTogglePlay: () => void;
  onSeek: (time: number) => void;
  events: SimEventItem[];
}

export const TimelineScrubber: React.FC<TimelineScrubberProps> = ({
  currentTime,
  maxTime,
  isRunning,
  onTogglePlay,
  onSeek,
  events,
}) => {
  const effectiveMax = Math.max(10.0, maxTime);

  return (
    <div
      style={{
        position: 'absolute',
        bottom: '0',
        left: '0',
        right: '0',
        height: '62px',
        background: 'var(--surface-card)',
        borderTop: '2px solid var(--border-brass)',
        boxShadow: 'var(--shadow-lg)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 1.2rem',
        gap: '1rem',
        zIndex: 35,
      }}
    >
      {/* Scrubber Playback Buttons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexShrink: 0 }}>
        <button
          className="btn-brass"
          style={{ width: '32px', height: '32px', padding: 0 }}
          onClick={() => onSeek(Math.max(0, currentTime - 0.5))}
          title="Step Back 0.5s"
        >
          <SkipBack size={14} />
        </button>

        <button
          className={isRunning ? 'btn-brass' : 'btn-brass btn-brass-primary'}
          style={{ width: '36px', height: '36px', padding: 0 }}
          onClick={onTogglePlay}
          title={isRunning ? 'Pause Simulation' : 'Run / Resume Simulation'}
        >
          {isRunning ? <Pause size={16} /> : <Play size={16} />}
        </button>

        <button
          className="btn-brass"
          style={{ width: '32px', height: '32px', padding: 0 }}
          onClick={() => onSeek(Math.min(effectiveMax, currentTime + 0.5))}
          title="Step Forward 0.5s"
        >
          <SkipForward size={14} />
        </button>
      </div>

      {/* Time Readout */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.4rem',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.8rem',
          fontWeight: 600,
          flexShrink: 0,
        }}
      >
        <Clock size={15} color="var(--accent-brass)" />
        <span>{currentTime.toFixed(2)}s</span>
        <span style={{ color: 'var(--text-muted)' }}>/ {effectiveMax.toFixed(1)}s</span>
      </div>

      {/* Timeline Track with Event Pins */}
      <div style={{ flex: 1, position: 'relative', height: '24px', display: 'flex', alignItems: 'center' }}>
        <input
          type="range"
          min="0"
          max={effectiveMax}
          step="0.05"
          value={currentTime}
          onChange={(e) => onSeek(parseFloat(e.target.value))}
          style={{
            width: '100%',
            accentColor: 'var(--accent-brass)',
            cursor: 'pointer',
            zIndex: 2,
          }}
        />

        {/* Event Markers Overlay */}
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: '50%',
            transform: 'translateY(-50%)',
            pointerEvents: 'none',
            zIndex: 1,
          }}
        >
          {events.slice(-40).map((ev, i) => {
            const leftPct = Math.min(100, Math.max(0, (ev.ts / effectiveMax) * 100));
            return (
              <div
                key={i}
                style={{
                  position: 'absolute',
                  left: `${leftPct}%`,
                  width: '3px',
                  height: '14px',
                  background:
                    ev.type.includes('attack') || ev.type.includes('down')
                      ? 'var(--accent-crimson)'
                      : ev.type.includes('convergence')
                      ? 'var(--accent-verdigris)'
                      : 'var(--border-brass)',
                  borderRadius: '1px',
                  transform: 'translateX(-50%) translateY(-50%)',
                  opacity: 0.75,
                }}
                title={`[${ev.ts.toFixed(2)}s] ${ev.type} (${ev.src})`}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
};
