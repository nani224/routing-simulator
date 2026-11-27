/**
 * Master Interface Component for PHANTOMNET "Phantom Observatory".
 *
 * Coordinates:
 * - PixiJS WebGL Canvas
 * - Web Worker for off-thread msgpack decoding
 * - Zustand state store
 * - Switchable Lens Layering
 * - Time Machine playback controls
 */

import React, { useEffect, useRef } from "react";
import {
  ShieldAlert,
  ShieldCheck,
  Radio,
  RefreshCw,
  Sliders,
  Play,
  Zap,
  Shield,
} from "lucide-react";
import { usePhantomStore } from "../../store/phantomStore";
import { PixiObservatoryCanvas } from "./PixiObservatoryCanvas";
import { LensToggleBar } from "./LensToggleBar";
import { TimeMachineControls } from "./TimeMachineControls";
import { MaskFoundryLens } from "./MaskFoundryLens";
import { ArmsRaceOrreryLens } from "./ArmsRaceOrreryLens";
import { MeshLens } from "./MeshLens";
import { EvidenceWallLens } from "./EvidenceWallLens";
import type { PhantomEvent } from "../../types/events";
import "./PhantomObservatory.css";

export const PhantomObservatory: React.FC<{ routingMesh: React.ReactNode }> = ({ routingMesh }) => {
  const {
    connState,
    censorScore,
    activeMask,
    activeLenses,
    isLive,
    playbackTime,
    events,
    isPlaying,
    setEvents,
    appendEvents,
    setPlaybackTime,
    setIsPlaying,
  } = usePhantomStore();

  const workerRef = useRef<Worker | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Judge Demo & Interactive Override Handlers
  const handleRunAutoDemo = () => {
    setPlaybackTime(0.0);
    setIsPlaying(true);
  };

  const handleJudgeBlock = () => {
    const now = playbackTime;
    appendEvents([
      {
        version: 1,
        seq: events.length + 1,
        t: now + 0.05,
        kind: "CENSOR_SCORE",
        meta: { score: 0.96, reason: "Judge manual block override" },
      },
      {
        version: 1,
        seq: events.length + 2,
        t: now + 0.1,
        kind: "CENSOR_ACTION",
        meta: { action: "BLOCK", confidence: 0.98 },
      },
      {
        version: 1,
        seq: events.length + 3,
        t: now + 0.15,
        kind: "PKT_DROP",
        size: 1420,
        dir: "TX",
        meta: { reason: "judge_gate_slam" },
      },
      {
        version: 1,
        seq: events.length + 4,
        t: now + 0.2,
        kind: "CONN_STATE",
        state: "BLOCKED",
        meta: { judge_override: true },
      },
    ]);
  };

  const handleJudgeShield = () => {
    const now = playbackTime;
    appendEvents([
      {
        version: 1,
        seq: events.length + 1,
        t: now + 0.05,
        kind: "POLICY_DECISION",
        mask_id: "cmaes-learned-v2",
        meta: {
          reasoning:
            "Judge tactical defense shield activated. Deploying CMA-ES learned mask profile with jitter morphing and dummy padding.",
          bandwidth_overhead: 14.3,
          latency_cost_ms: 3.78,
          stealth_gain: 0.89,
        },
      },
      {
        version: 1,
        seq: events.length + 2,
        t: now + 0.1,
        kind: "MASK_SWITCH",
        mask_id: "cmaes-learned-v2",
        meta: { profile: "cmaes-learned-v2" },
      },
      {
        version: 1,
        seq: events.length + 3,
        t: now + 0.15,
        kind: "CONN_STATE",
        state: "CONNECTED",
        meta: { status: "shield_deployed" },
      },
      {
        version: 1,
        seq: events.length + 4,
        t: now + 0.2,
        kind: "CENSOR_SCORE",
        meta: { score: 0.14 },
      },
      {
        version: 1,
        seq: events.length + 5,
        t: now + 0.25,
        kind: "CENSOR_ACTION",
        meta: { action: "ALLOW" },
      },
    ]);
  };

  // 1-Key Interactive Judge & Demo Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      if (e.code === "KeyD") {
        e.preventDefault();
        handleRunAutoDemo();
      } else if (e.code === "KeyB") {
        e.preventDefault();
        handleJudgeBlock();
      } else if (e.code === "KeyS") {
        e.preventDefault();
        handleJudgeShield();
      } else if (e.code === "KeyR") {
        e.preventDefault();
        setPlaybackTime(0.0);
      } else if (e.code === "Space") {
        e.preventDefault();
        setIsPlaying(!isPlaying);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [events.length, isPlaying, playbackTime, setIsPlaying, setPlaybackTime]);

  // Initialize Web Worker and load initial synthetic episode
  useEffect(() => {
    // Spawn Web Worker for msgpack decoding
    try {
      workerRef.current = new Worker(
        new URL("../../workers/eventDecoder.worker.ts", import.meta.url),
        { type: "module" }
      );

      workerRef.current.onmessage = (e) => {
        const { type, events } = e.data;
        if ((type === "BATCH_DECODED" || type === "EVENTS_DECODED") && events) {
          appendEvents(events);
        }
      };
    } catch {
      // Fallback if worker not supported in test environment
    }

    // Load initial 7-act deterministic synthetic episode via API replay or local fallback
    const loadSyntheticEpisode = async () => {
      try {
        const resp = await fetch("/api/replay/synthetic-episode");
        if (resp.ok) {
          const events: PhantomEvent[] = await resp.json();
          setEvents(events, "synthetic-episode", "sha256-deterministic-seed-42");
          return;
        }
      } catch {
        // Fallback scripted episode if backend server is not running
      }

      // Built-in 7-act scripted fallback generator
      const fallbackEvents: PhantomEvent[] = [];
      let seq = 1;

      // Act 1: Handshake
      fallbackEvents.push(
        { version: 1, seq: seq++, t: 0.1, kind: "CONN_STATE", state: "HANDSHAKE_INIT", meta: {} },
        { version: 1, seq: seq++, t: 0.2, kind: "HANDSHAKE_MSG", meta: { step: 1, pattern: "Noise_XX" } },
        { version: 1, seq: seq++, t: 0.3, kind: "HANDSHAKE_MSG", meta: { step: 2, pattern: "Noise_XX" } },
        { version: 1, seq: seq++, t: 0.4, kind: "HANDSHAKE_MSG", meta: { step: 3, session_id: "0x8f2a1b9c" } },
        { version: 1, seq: seq++, t: 0.5, kind: "CONN_STATE", state: "CONNECTED", meta: {} }
      );

      // Act 2: Unshaped Traffic
      for (let i = 0; i < 15; i++) {
        fallbackEvents.push(
          { version: 1, seq: seq++, t: 0.6 + i * 0.12, kind: "PKT_TX", size: 64 + (i % 5) * 256, dir: "TX", meta: {} },
          { version: 1, seq: seq++, t: 0.65 + i * 0.12, kind: "PKT_RX", size: 128 + (i % 4) * 300, dir: "RX", meta: {} }
        );
      }

      // Act 3: Censor Inspection & Throttle & Block
      fallbackEvents.push(
        { version: 1, seq: seq++, t: 2.6, kind: "CENSOR_SCORE", meta: { score: 0.55 } },
        { version: 1, seq: seq++, t: 2.8, kind: "CENSOR_ACTION", meta: { action: "THROTTLE" } },
        { version: 1, seq: seq++, t: 3.1, kind: "CENSOR_SCORE", meta: { score: 0.88 } },
        { version: 1, seq: seq++, t: 3.3, kind: "CENSOR_ACTION", meta: { action: "BLOCK" } },
        { version: 1, seq: seq++, t: 3.4, kind: "PKT_DROP", size: 1420, meta: {} },
        { version: 1, seq: seq++, t: 3.5, kind: "CONN_STATE", state: "BLOCKED", meta: {} }
      );

      // Act 4: Policy Decision & Mask Switch
      fallbackEvents.push(
        {
          version: 1,
          seq: seq++,
          t: 3.8,
          kind: "POLICY_DECISION",
          mask_id: "jitter_morph",
          meta: {
            reasoning: "Censor signature detected in MTU cluster. Switching to jitter_morph profile with dummy padding.",
            bandwidth_overhead: 18.5,
            latency_cost_ms: 1.15,
            stealth_gain: 0.86,
          },
        },
        { version: 1, seq: seq++, t: 4.0, kind: "MASK_SWITCH", mask_id: "jitter_morph", meta: {} }
      );

      // Act 5: Re-weld & Rekey
      fallbackEvents.push(
        { version: 1, seq: seq++, t: 4.4, kind: "CONN_STATE", state: "RECONNECTING", meta: {} },
        { version: 1, seq: seq++, t: 4.7, kind: "REKEY", meta: { key_rotation: 1 } },
        { version: 1, seq: seq++, t: 5.0, kind: "CONN_STATE", state: "CONNECTED", meta: {} }
      );

      // Act 6: Shaped Stealth Flow
      for (let i = 0; i < 15; i++) {
        fallbackEvents.push(
          { version: 1, seq: seq++, t: 5.2 + i * 0.12, kind: "PKT_TX", size: 512, dir: "TX", mask_id: "jitter_morph", meta: {} },
          { version: 1, seq: seq++, t: 5.25 + i * 0.12, kind: "PKT_RX", size: 512, dir: "RX", mask_id: "jitter_morph", meta: {} }
        );
      }
      fallbackEvents.push(
        { version: 1, seq: seq++, t: 6.8, kind: "CENSOR_SCORE", meta: { score: 0.11 } },
        { version: 1, seq: seq++, t: 7.0, kind: "CENSOR_ACTION", meta: { action: "ALLOW" } }
      );

      // Act 7: Co-Training & Benchmarks
      fallbackEvents.push(
        {
          version: 1,
          seq: seq++,
          t: 7.4,
          kind: "TRAIN_ROUND",
          meta: { round: 1, attacker_loss: 0.22, defender_reward: 0.78, stealth: 0.78, overhead: 0.12 },
        },
        {
          version: 1,
          seq: seq++,
          t: 7.8,
          kind: "TRAIN_ROUND",
          meta: { round: 2, attacker_loss: 0.14, defender_reward: 0.86, stealth: 0.86, overhead: 0.18 },
        },
        {
          version: 1,
          seq: seq++,
          t: 8.2,
          kind: "ROUTE_CHANGE",
          meta: {
            new_path: ["YOU", "Relay-2", "Relay-3", "SERVER"],
            oracle_optimal_path: ["YOU", "Relay-2", "Relay-3", "SERVER"],
            dead_node: "Relay-1",
          },
        },
        {
          version: 1,
          seq: seq++,
          t: 8.6,
          kind: "BENCH_MARK",
          meta: { metric: "Throughput", value: 216.5, unit: "Mbps" },
        },
        {
          version: 1,
          seq: seq++,
          t: 8.8,
          kind: "BENCH_MARK",
          meta: { metric: "RTT", value: 0.61, unit: "ms" },
        }
      );

      setEvents(fallbackEvents, "scripted-7-act-episode", "e8a2fc87ee74ee30dd6124090841");
    };

    loadSyntheticEpisode();

    return () => {
      if (workerRef.current) {
        workerRef.current.terminate();
        workerRef.current = null;
      }
    };
  }, [appendEvents, setEvents]);

  // Live WebSocket connection handling
  useEffect(() => {
    if (!isLive) {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      return;
    }

    const wsUrl = `ws://${window.location.hostname || "127.0.0.1"}:8000/ws/events`;
    const ws = new WebSocket(wsUrl);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onmessage = (e) => {
      if (workerRef.current && e.data instanceof ArrayBuffer) {
        workerRef.current.postMessage({
          type: "DECODE_CHUNK",
          data: e.data,
        });
      }
    };

    return () => {
      ws.close();
    };
  }, [isLive]);

  // Derive connection color & badge
  const isConnected = connState === "CONNECTED";
  const isBlocked = connState === "BLOCKED";
  const statusColor = isBlocked ? "#ff0055" : isConnected ? "#00f3ff" : "#ffb700";

  return (
    <div className="po-root">
      {/* Top Telemetry Header */}
      <div className="po-header">
        <div className="po-brand">
          <div className="po-brand-icon">
            <Radio className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h1 className="po-title">PHANTOM OBSERVATORY</h1>
            <p className="po-subtitle">
              Stealth Encrypted Tunnel &amp; Adversarial Censorship Defense Telemetry
            </p>
            <div
              style={{
                display: "inline-block",
                marginTop: 4,
                padding: "2px 8px",
                borderRadius: 4,
                backgroundColor: "rgba(255, 184, 0, 0.15)",
                border: "1px solid rgba(255, 184, 0, 0.5)",
                color: "#ffb800",
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.05em",
              }}
            >
              ILLUSTRATIVE SCRIPTED EPISODE (synthetic generator)
            </div>
          </div>
        </div>

        {/* Live Status Badges & Judge Interactive Controls */}
        <div className="po-badges">
          {/* Judge Interactive Controls */}
          <div className="po-judge-controls">
            <button
              className="po-judge-btn po-judge-demo"
              title="Shortcut: D (Replay scripted 7-act run)"
              onClick={handleRunAutoDemo}
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>DEMO [D]</span>
            </button>
            <button
              className="po-judge-btn po-judge-block"
              title="Shortcut: B (Judge manual censor gate-slam)"
              onClick={handleJudgeBlock}
            >
              <Zap className="w-3.5 h-3.5" />
              <span>BLOCK [B]</span>
            </button>
            <button
              className="po-judge-btn po-judge-shield"
              title="Shortcut: S (Judge tactical mask switch)"
              onClick={handleJudgeShield}
            >
              <Shield className="w-3.5 h-3.5" />
              <span>SHIELD [S]</span>
            </button>
          </div>

          {/* Connection Status */}
          <div
            className="po-badge"
            style={{
              backgroundColor: `${statusColor}18`,
              borderColor: `${statusColor}60`,
              color: statusColor,
            }}
          >
            {isBlocked ? (
              <ShieldAlert className="w-4 h-4 text-[#ff0055]" />
            ) : isConnected ? (
              <ShieldCheck className="w-4 h-4 text-[#00f3ff]" />
            ) : (
              <RefreshCw className="w-4 h-4 animate-spin text-[#ffb700]" />
            )}
            <span>STATUS: [{connState}]</span>
          </div>

          {/* Active Mask */}
          <div
            className="po-badge"
            style={{
              backgroundColor: "rgba(192, 132, 252, 0.15)",
              borderColor: "rgba(192, 132, 252, 0.4)",
              color: "#c084fc",
            }}
          >
            <Sliders className="w-4 h-4 text-[#a855f7]" />
            <span>MASK: [{activeMask.toUpperCase()}]</span>
          </div>

          {/* Censor Confidence Score */}
          <div
            className="po-badge"
            style={{
              backgroundColor: "#0d131f",
              borderColor: "#1a2538",
              color: "#94a3b8",
            }}
          >
            <span style={{ color: "#64748b" }}>CENSOR CONFIDENCE:</span>
            <span
              style={{
                fontWeight: 800,
                color:
                  censorScore > 0.65 ? "#ff0055" : censorScore > 0.35 ? "#ffb700" : "#00f3ff",
              }}
            >
              {(censorScore * 100).toFixed(1)}%
            </span>
          </div>
        </div>
      </div>

      {/* Lens Toggle Bar */}
      {routingMesh}
      <LensToggleBar />

      {/* Main PixiJS v8 WebGL Canvas */}
      <div className="po-canvas-wrapper">
        <PixiObservatoryCanvas />
      </div>

      {/* Switchable Layer Panels */}
      {activeLenses.foundry && <MaskFoundryLens />}
      {activeLenses.orrery && <ArmsRaceOrreryLens />}
      {activeLenses.mesh && <MeshLens />}
      {activeLenses.evidence && <EvidenceWallLens />}

      {/* Time Machine Playback Controls */}
      <TimeMachineControls />
    </div>
  );
};
