/**
 * Lens Toggle Bar for PHANTOMNET "Phantom Observatory".
 * Allows turning visualization layers on and off to prevent visual clutter.
 */

import React from "react";
import {
  Eye,
  Shield,
  Sliders,
  Cpu,
  Share2,
  FileText,
  Activity,
} from "lucide-react";
import { usePhantomStore, type LensType } from "../../store/phantomStore";

interface LensConfig {
  id: LensType;
  label: string;
  icon: React.FC<{ className?: string; style?: React.CSSProperties }>;
  accentColor: string;
  description: string;
}

const LENSES: LensConfig[] = [
  {
    id: "conduit",
    label: "Conduit",
    icon: Activity,
    accentColor: "#00f3ff",
    description: "Physical glowing tunnel pipe and packets",
  },
  {
    id: "fingerprint",
    label: "Fingerprint Strip",
    icon: Sliders,
    accentColor: "#00ffaa",
    description: "Raw vs Masked packet size & interval barcodes",
  },
  {
    id: "censor",
    label: "Censor's Eye",
    icon: Eye,
    accentColor: "#ff0055",
    description: "Adversarial scanner grid & gate-slam barrier",
  },
  {
    id: "foundry",
    label: "Mask Foundry",
    icon: Cpu,
    accentColor: "#c084fc",
    description: "Policy decision reasoning & overhead gauge",
  },
  {
    id: "orrery",
    label: "Arms Race Orrery",
    icon: Shield,
    accentColor: "#ffb700",
    description: "Attacker vs defender rounds & live Pareto frontier",
  },
  {
    id: "mesh",
    label: "Mesh Layer",
    icon: Share2,
    accentColor: "#38bdf8",
    description: "RouteLab mesh topology reroutes vs oracle path",
  },
  {
    id: "evidence",
    label: "Evidence Wall",
    icon: FileText,
    accentColor: "#10b981",
    description: "Live measured cryptographic & throughput benchmarks",
  },
];

export const LensToggleBar: React.FC = () => {
  const { activeLenses, toggleLens } = usePhantomStore();

  return (
    <div className="po-lens-bar">
      <div className="po-lens-label">
        <span className="po-lens-indicator" />
        <span>ACTIVE LENSES:</span>
      </div>

      <div className="po-lens-group">
        {LENSES.map((lens) => {
          const isActive = activeLenses[lens.id];
          const Icon = lens.icon;

          return (
            <button
              key={lens.id}
              onClick={() => toggleLens(lens.id)}
              title={lens.description}
              className={`po-lens-btn ${isActive ? "active" : ""}`}
              style={
                isActive
                  ? {
                      borderColor: `${lens.accentColor}80`,
                      boxShadow: `0 0 12px ${lens.accentColor}30`,
                    }
                  : undefined
              }
            >
              <Icon
                style={{
                  width: 14,
                  height: 14,
                  color: isActive ? lens.accentColor : "#94a3b8",
                }}
              />
              <span>{lens.label}</span>
              <span
                className="po-lens-btn-dot"
                style={
                  isActive
                    ? { backgroundColor: lens.accentColor, boxShadow: `0 0 6px ${lens.accentColor}` }
                    : undefined
                }
              />
            </button>
          );
        })}
      </div>
    </div>
  );
};
