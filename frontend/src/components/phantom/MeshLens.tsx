/**
 * Mesh Layer Lens for PHANTOMNET "Phantom Observatory".
 * Renders RouteLab topology interaction, relay health, dynamic failover, and oracle comparison.
 */

import React from "react";
import { Share2, AlertTriangle, CheckCircle2 } from "lucide-react";
import { usePhantomStore } from "../../store/phantomStore";

export const MeshLens: React.FC = () => {
  const { mesh } = usePhantomStore();

  const isOptimal =
    mesh.activePath.length > 0 &&
    mesh.oracleOptimalPath.length > 0 &&
    mesh.activePath.join("->") === mesh.oracleOptimalPath.join("->");

  return (
    <div className="po-panel" style={{ borderColor: "rgba(56, 189, 248, 0.4)" }}>
      {/* Header */}
      <div className="po-panel-header">
        <div className="po-panel-title" style={{ color: "#38bdf8" }}>
          <Share2 style={{ width: 16, height: 16 }} />
          <span>ROUTELAB MESH LENS // ORACLE PATH COMPARISON</span>
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "2px 10px",
            borderRadius: 6,
            background: isOptimal ? "rgba(0, 255, 170, 0.15)" : "rgba(255, 183, 0, 0.15)",
            border: isOptimal ? "1px solid rgba(0, 255, 170, 0.4)" : "1px solid rgba(255, 183, 0, 0.4)",
            fontSize: 11,
            fontWeight: 700,
            color: isOptimal ? "var(--po-mint)" : "var(--po-amber)",
          }}
        >
          {isOptimal ? (
            <>
              <CheckCircle2 style={{ width: 14, height: 14, color: "var(--po-mint)" }} />
              <span>ORACLE OPTIMAL</span>
            </>
          ) : (
            <>
              <AlertTriangle style={{ width: 14, height: 14, color: "var(--po-amber)" }} />
              <span>FAILOVER REROUTE</span>
            </>
          )}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {/* Active Route Path */}
        <div className="po-card" style={{ gap: 6 }}>
          <span style={{ fontSize: 11, color: "#94a3b8" }}>ACTIVE TRANSMISSION PATH:</span>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6, color: "var(--po-cyan)", fontWeight: 700 }}>
            {mesh.activePath.map((node, i) => (
              <React.Fragment key={node}>
                <span
                  style={{
                    padding: "2px 8px",
                    borderRadius: 6,
                    background: "rgba(0, 243, 255, 0.1)",
                    border: "1px solid rgba(0, 243, 255, 0.3)",
                  }}
                >
                  {node}
                </span>
                {i < mesh.activePath.length - 1 && <span style={{ color: "#64748b" }}>&rarr;</span>}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Oracle Optimal Path */}
        <div className="po-card" style={{ gap: 6 }}>
          <span style={{ fontSize: 11, color: "#94a3b8" }}>ORACLE OPTIMAL REFERENCE:</span>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6, color: "var(--po-mint)", fontWeight: 700 }}>
            {mesh.oracleOptimalPath.map((node, i) => (
              <React.Fragment key={node}>
                <span
                  style={{
                    padding: "2px 8px",
                    borderRadius: 6,
                    background: "rgba(0, 255, 170, 0.1)",
                    border: "1px solid rgba(0, 255, 170, 0.3)",
                  }}
                >
                  {node}
                </span>
                {i < mesh.oracleOptimalPath.length - 1 && (
                  <span style={{ color: "#64748b" }}>&rarr;</span>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>

      {mesh.deadNodes.length > 0 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: 10,
            borderRadius: 8,
            background: "rgba(255, 0, 85, 0.12)",
            border: "1px solid rgba(255, 0, 85, 0.35)",
            fontSize: 12,
            color: "var(--po-magenta)",
            fontWeight: 700,
          }}
        >
          <AlertTriangle style={{ width: 16, height: 16, flexShrink: 0 }} />
          <span>RELAY NODE CASUALTY DETECTED: [{mesh.deadNodes.join(", ")}]</span>
        </div>
      )}
    </div>
  );
};
