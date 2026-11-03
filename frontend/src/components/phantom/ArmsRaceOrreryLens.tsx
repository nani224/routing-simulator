/**
 * Arms Race Orrery Lens for PHANTOMNET "Phantom Observatory".
 * Renders adversarial co-training rounds, attacker vs defender balance, and live D3 Pareto frontier.
 */

import React, { useMemo } from "react";
import { ShieldAlert, Crosshair, Award } from "lucide-react";
import { usePhantomStore } from "../../store/phantomStore";

export const ArmsRaceOrreryLens: React.FC = () => {
  const { trainRounds } = usePhantomStore();

  // Pareto frontier data points
  const paretoPoints = useMemo(() => {
    if (trainRounds.length === 0) {
      return [
        { overhead: 0, stealth: 0.12, label: "Unshaped" },
        { overhead: 12, stealth: 0.65, label: "Fixed-Pad" },
        { overhead: 24, stealth: 0.88, label: "Learned-CMA" },
        { overhead: 38, stealth: 0.94, label: "Heavy-Cover" },
      ];
    }
    return trainRounds.map((r) => ({
      overhead: r.paretoOverhead * 100,
      stealth: r.paretoStealth,
      label: `Round ${r.round}`,
    }));
  }, [trainRounds]);

  const latestRound = trainRounds.length > 0 ? trainRounds[trainRounds.length - 1] : null;

  return (
    <div className="po-panel" style={{ borderColor: "rgba(255, 183, 0, 0.4)" }}>
      {/* Header */}
      <div className="po-panel-header">
        <div className="po-panel-title" style={{ color: "var(--po-amber)" }}>
          <Crosshair style={{ width: 16, height: 16 }} />
          <span>ARMS RACE ORRERY // ADVERSARIAL CO-TRAINING</span>
        </div>
        <div
          style={{
            padding: "2px 8px",
            borderRadius: 6,
            background: "rgba(255, 183, 0, 0.15)",
            border: "1px solid rgba(255, 183, 0, 0.4)",
            fontSize: 11,
            fontWeight: 700,
            color: "#fef08a",
          }}
        >
          ROUND: {latestRound ? `#${latestRound.round}` : "IDLE"}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, alignItems: "center" }}>
        {/* Attacker vs Defender Balance Cards */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {/* Defender Status */}
          <div
            className="po-card"
            style={{
              flexDirection: "row",
              justifyContent: "space-between",
              alignItems: "center",
              borderColor: "rgba(0, 255, 170, 0.3)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--po-mint)" }}>
              <Award style={{ width: 16, height: 16 }} />
              <span>DEFENDER (POLICY)</span>
            </div>
            <div style={{ fontSize: 13, fontWeight: 800, color: "#ffffff" }}>
              REWARD: {latestRound ? latestRound.defenderReward.toFixed(3) : "0.852"}
            </div>
          </div>

          {/* Attacker Status */}
          <div
            className="po-card"
            style={{
              flexDirection: "row",
              justifyContent: "space-between",
              alignItems: "center",
              borderColor: "rgba(255, 0, 85, 0.3)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--po-magenta)" }}>
              <ShieldAlert style={{ width: 16, height: 16 }} />
              <span>ATTACKER (CENSOR)</span>
            </div>
            <div style={{ fontSize: 13, fontWeight: 800, color: "#ffffff" }}>
              LOSS: {latestRound ? latestRound.attackerLoss.toFixed(3) : "0.148"}
            </div>
          </div>

          <div style={{ fontSize: 11, color: "#94a3b8", lineHeight: 1.5, padding: "0 4px" }}>
            Live adversarial co-training continuously maps the Pareto frontier between packet stealth and transport efficiency.
          </div>
        </div>

        {/* Live SVG Pareto Frontier */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            padding: 8,
            borderRadius: 10,
            background: "var(--po-surface-inset)",
            border: "1px solid var(--po-border)",
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", width: "100%", marginBottom: 4, paddingLeft: 8 }}>
            PARETO FRONTIER: STEALTH VS OVERHEAD
          </div>
          <svg style={{ width: "100%", height: 130 }} viewBox="0 0 280 130">
            {/* Grid Lines */}
            <line x1="30" y1="15" x2="30" y2="110" stroke="#1e293b" strokeWidth="1.5" />
            <line x1="30" y1="110" x2="265" y2="110" stroke="#1e293b" strokeWidth="1.5" />

            {/* Axes Labels */}
            <text x="265" y="125" fill="#64748b" fontSize="9" textAnchor="end" fontFamily="monospace">
              Overhead %
            </text>
            <text x="25" y="12" fill="#64748b" fontSize="9" textAnchor="end" fontFamily="monospace">
              Stealth
            </text>

            {/* Connecting Pareto Curve */}
            <path
              d={paretoPoints
                .map((p, idx) => {
                  const x = 30 + (p.overhead / 50) * 220;
                  const y = 110 - p.stealth * 90;
                  return `${idx === 0 ? "M" : "L"} ${x} ${y}`;
                })
                .join(" ")}
              fill="none"
              stroke="var(--po-amber)"
              strokeWidth="2.5"
              strokeDasharray="4 2"
            />

            {/* Pareto Points */}
            {paretoPoints.map((p) => {
              const x = 30 + (p.overhead / 50) * 220;
              const y = 110 - p.stealth * 90;
              return (
                <g key={p.label}>
                  <circle cx={x} cy={y} r="4" fill="var(--po-cyan)" stroke="#ffffff" strokeWidth="1.5" />
                  <text
                    x={x}
                    y={y - 8}
                    fill="#94a3b8"
                    fontSize="8"
                    textAnchor="middle"
                    fontFamily="monospace"
                  >
                    {p.label}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>
    </div>
  );
};
