/**
 * Mask Foundry Lens for PHANTOMNET "Phantom Observatory".
 * Renders real-time policy reasoning ticker, active mask profile, and overhead dial gauges.
 */

import React from "react";
import { Cpu, Terminal, TrendingUp, Clock, ShieldCheck } from "lucide-react";
import { usePhantomStore } from "../../store/phantomStore";

export const MaskFoundryLens: React.FC = () => {
  const { activeMask, reasoningTicker, overheadGauge } = usePhantomStore();

  return (
    <div className="po-panel" style={{ borderColor: "rgba(192, 132, 252, 0.4)" }}>
      {/* Header */}
      <div className="po-panel-header">
        <div className="po-panel-title" style={{ color: "var(--po-purple)" }}>
          <Cpu style={{ width: 16, height: 16 }} />
          <span>MASK FOUNDRY // POLICY DECISION ENGINE</span>
        </div>
        <div
          style={{
            padding: "2px 8px",
            borderRadius: 6,
            background: "rgba(192, 132, 252, 0.2)",
            border: "1px solid rgba(192, 132, 252, 0.4)",
            fontSize: 11,
            fontWeight: 700,
            color: "#e9d5ff",
          }}
        >
          PROFILE: [{activeMask.toUpperCase()}]
        </div>
      </div>

      {/* Reasoning ticker terminal */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 10,
          padding: 12,
          borderRadius: 8,
          background: "var(--po-surface-inset)",
          border: "1px solid var(--po-border)",
          fontSize: 12,
          lineHeight: "1.6",
        }}
      >
        <Terminal style={{ width: 16, height: 16, color: "var(--po-cyan)", marginTop: 2, flexShrink: 0 }} />
        <div style={{ color: "#cbd5e1" }}>
          <span style={{ color: "var(--po-cyan)", fontWeight: 700 }}>&gt; POLICY_REASONING: </span>
          {reasoningTicker}
        </div>
      </div>

      {/* Overhead & stealth telemetry gauges */}
      <div className="po-grid-3">
        {/* Bandwidth Overhead */}
        <div className="po-card" style={{ alignItems: "center", textAlign: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "#94a3b8" }}>
            <TrendingUp style={{ width: 14, height: 14, color: "var(--po-amber)" }} />
            <span>BW OVERHEAD</span>
          </div>
          <div className="po-card-val" style={{ color: "var(--po-amber)" }}>
            +{overheadGauge.bandwidthOverhead.toFixed(1)}%
          </div>
          <div style={{ width: "100%", height: 6, background: "#1c2738", borderRadius: 4, marginTop: 8, overflow: "hidden" }}>
            <div
              style={{
                width: `${Math.min(100, overheadGauge.bandwidthOverhead * 2)}%`,
                height: "100%",
                background: "var(--po-amber)",
                borderRadius: 4,
                transition: "width 0.3s ease",
              }}
            />
          </div>
        </div>

        {/* Latency Cost */}
        <div className="po-card" style={{ alignItems: "center", textAlign: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "#94a3b8" }}>
            <Clock style={{ width: 14, height: 14, color: "var(--po-cyan)" }} />
            <span>LATENCY COST</span>
          </div>
          <div className="po-card-val" style={{ color: "var(--po-cyan)" }}>
            +{overheadGauge.latencyCostMs.toFixed(2)} ms
          </div>
          <div style={{ width: "100%", height: 6, background: "#1c2738", borderRadius: 4, marginTop: 8, overflow: "hidden" }}>
            <div
              style={{
                width: `${Math.min(100, overheadGauge.latencyCostMs * 20)}%`,
                height: "100%",
                background: "var(--po-cyan)",
                borderRadius: 4,
                transition: "width 0.3s ease",
              }}
            />
          </div>
        </div>

        {/* Stealth Gain */}
        <div className="po-card" style={{ alignItems: "center", textAlign: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "#94a3b8" }}>
            <ShieldCheck style={{ width: 14, height: 14, color: "var(--po-mint)" }} />
            <span>STEALTH GAIN</span>
          </div>
          <div className="po-card-val" style={{ color: "var(--po-mint)" }}>
            {(overheadGauge.stealthGain * 100).toFixed(0)}%
          </div>
          <div style={{ width: "100%", height: 6, background: "#1c2738", borderRadius: 4, marginTop: 8, overflow: "hidden" }}>
            <div
              style={{
                width: `${Math.min(100, overheadGauge.stealthGain * 100)}%`,
                height: "100%",
                background: "var(--po-mint)",
                borderRadius: 4,
                transition: "width 0.3s ease",
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
