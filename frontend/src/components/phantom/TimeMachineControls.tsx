/**
 * Time Machine Controls for PHANTOMNET "Phantom Observatory".
 * Provides scrub/seek, play/pause, speed adjustment (0.1x to 5x), and live vs replay switching.
 */

import React from "react";
import { Play, Pause, RotateCcw, FastForward, Radio, Gauge } from "lucide-react";
import { usePhantomStore } from "../../store/phantomStore";

const SPEEDS = [0.1, 0.5, 1.0, 2.0, 5.0];

export const TimeMachineControls: React.FC = () => {
  const {
    playbackTime,
    maxTime,
    isPlaying,
    speed,
    fps,
    isLive,
    setIsPlaying,
    setPlaybackTime,
    setSpeed,
    setIsLive,
    resetObservatory,
  } = usePhantomStore();

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setPlaybackTime(val);
  };

  return (
    <div className="po-controls">
      {/* Upper row: Scrubber progress and time display */}
      <div className="po-scrub-row">
        <span className="po-time-text">t={playbackTime.toFixed(2)}s</span>

        <input
          type="range"
          min={0}
          max={Math.max(10, maxTime)}
          step={0.01}
          value={playbackTime}
          onChange={handleSliderChange}
          disabled={isLive}
          className="po-slider"
        />

        <span style={{ fontSize: 12, color: "#64748b", minWidth: 70, textAlign: "right" }}>
          max={maxTime.toFixed(2)}s
        </span>
      </div>

      {/* Lower row: Interactive playback controls */}
      <div className="po-buttons-row">
        {/* Play/Pause & Reset */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            disabled={isLive}
            className="po-action-btn"
            title={isPlaying ? "Pause Timeline" : "Play Timeline"}
          >
            {isPlaying ? (
              <Pause style={{ width: 16, height: 16 }} />
            ) : (
              <Play style={{ width: 16, height: 16, marginLeft: 2 }} />
            )}
          </button>

          <button
            onClick={resetObservatory}
            disabled={isLive}
            className="po-action-btn"
            style={{
              background: "#0d131f",
              borderColor: "#1a2538",
              color: "#94a3b8",
            }}
            title="Rewind to beginning (t=0.0s)"
          >
            <RotateCcw style={{ width: 16, height: 16 }} />
          </button>
        </div>

        {/* Speed multiplier selection */}
        <div className="po-speed-group">
          <FastForward style={{ width: 14, height: 14, marginLeft: 6, color: "#64748b" }} />
          {SPEEDS.map((s) => (
            <button
              key={s}
              onClick={() => setSpeed(s)}
              disabled={isLive}
              className={`po-speed-btn ${speed === s ? "active" : ""}`}
            >
              {s}x
            </button>
          ))}
        </div>

        {/* Live vs Replay Mode & FPS telemetry */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button
            onClick={() => setIsLive(!isLive)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "6px 14px",
              borderRadius: 8,
              fontSize: 11,
              fontFamily: "var(--po-font-mono)",
              fontWeight: 700,
              cursor: "pointer",
              border: isLive ? "1px solid #ff0055" : "1px solid #1a2538",
              background: isLive ? "rgba(255, 0, 85, 0.2)" : "#0d131f",
              color: isLive ? "#ff0055" : "#94a3b8",
              transition: "all 0.2s",
            }}
          >
            <Radio style={{ width: 14, height: 14 }} />
            <span>{isLive ? "LIVE STREAM" : "REPLAY MODE"}</span>
          </button>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 14px",
              borderRadius: 8,
              background: "#0d131f",
              border: "1px solid #1a2538",
              fontSize: 12,
              fontFamily: "var(--po-font-mono)",
              color: "#f1f5f9",
            }}
          >
            <Gauge style={{ width: 14, height: 14, color: "#00ffaa" }} />
            <span style={{ color: "#00ffaa", fontWeight: 800 }}>{fps}</span>
            <span style={{ color: "#64748b" }}>FPS</span>
          </div>
        </div>
      </div>
    </div>
  );
};
