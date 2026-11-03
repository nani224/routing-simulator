/**
 * Zustand Store for PHANTOMNET "Phantom Observatory" WebGL visual interface.
 * Pure event-driven state: UI renders events only.
 */

import { create } from "zustand";
import type { PhantomEvent } from "../types/events";

export type LensType =
  | "conduit"
  | "fingerprint"
  | "censor"
  | "foundry"
  | "orrery"
  | "mesh"
  | "evidence";

export interface TrainRoundData {
  round: number;
  attackerLoss: number;
  defenderReward: number;
  paretoStealth: number;
  paretoOverhead: number;
  timestamp: number;
}

export interface HandshakeProgress {
  stage: number;
  messageType?: string;
  ephPubClient?: string;
  ephPubServer?: string;
  sessionId?: string;
  completed: boolean;
  rekeyCount: number;
}

export interface OverheadMetrics {
  bandwidthOverhead: number;
  latencyCostMs: number;
  stealthGain: number;
}

export interface MeshTopologySnapshot {
  nodes: string[];
  deadNodes: string[];
  activePath: string[];
  oracleOptimalPath: string[];
}

export interface PacketVisualItem {
  id: string;
  seq: number;
  t: number;
  size: number;
  dir: "TX" | "RX";
  isDropped: boolean;
  maskId: string;
}

interface PhantomState {
  // Episode & Event Stream
  events: PhantomEvent[];
  playbackTime: number;
  maxTime: number;
  isPlaying: boolean;
  speed: number;
  isLive: boolean;
  runId: string;
  runHash: string;
  fps: number;

  // Lenses configuration
  activeLenses: Record<LensType, boolean>;
  toggleLens: (lens: LensType) => void;

  // Live state projected from events up to playbackTime
  connState: string;
  censorScore: number;
  censorAction: "ALLOW" | "THROTTLE" | "BLOCK" | "RETRAIN" | string | null;
  gateSlam: boolean;
  throttleLevel: number; // 0 (none) to 1 (max throttle)
  activeMask: string;
  reasoningTicker: string;
  overheadGauge: OverheadMetrics;
  handshake: HandshakeProgress;
  trainRounds: TrainRoundData[];
  benchmarks: Record<string, number | string>;
  mesh: MeshTopologySnapshot;

  // Visual packet queues for WebGL rendering
  recentRawPackets: PacketVisualItem[];
  recentMaskedPackets: PacketVisualItem[];
  livePacketsInFlight: PacketVisualItem[];

  // Actions
  setEvents: (events: PhantomEvent[], runId?: string, runHash?: string) => void;
  appendEvents: (newEvents: PhantomEvent[]) => void;
  setPlaybackTime: (time: number) => void;
  setIsPlaying: (playing: boolean) => void;
  setSpeed: (speed: number) => void;
  setIsLive: (isLive: boolean) => void;
  setFps: (fps: number) => void;
  triggerGateSlam: (slam: boolean) => void;
  resetObservatory: () => void;
  stepForward: (dt: number) => void;
}

export const usePhantomStore = create<PhantomState>((set, get) => ({
  events: [],
  playbackTime: 0.0,
  maxTime: 10.0,
  isPlaying: true,
  speed: 1.0,
  isLive: false,
  runId: "scripted-episode",
  runHash: "deterministic-seed-42",
  fps: 60,

  activeLenses: {
    conduit: true,
    fingerprint: true,
    censor: true,
    foundry: false,
    orrery: false,
    mesh: false,
    evidence: false,
  },

  toggleLens: (lens: LensType) =>
    set((state) => ({
      activeLenses: {
        ...state.activeLenses,
        [lens]: !state.activeLenses[lens],
      },
    })),

  connState: "HANDSHAKE_INIT",
  censorScore: 0.05,
  censorAction: "ALLOW",
  gateSlam: false,
  throttleLevel: 0.0,
  activeMask: "plain",
  reasoningTicker: "Tunnel initialized. Noise XX mutual authentication handshake in progress.",
  overheadGauge: {
    bandwidthOverhead: 0.0,
    latencyCostMs: 0.5,
    stealthGain: 0.1,
  },
  handshake: {
    stage: 0,
    completed: false,
    rekeyCount: 0,
  },
  trainRounds: [],
  benchmarks: {
    "Throughput": "216.5 Mbps",
    "RTT": "0.61 ms",
    "Handshake": "8.36 ms",
    "Rekey Overhead": "0.14 ms",
  },
  mesh: {
    nodes: ["YOU", "Relay-1", "Relay-2", "Relay-3", "SERVER"],
    deadNodes: [],
    activePath: ["YOU", "Relay-1", "Relay-3", "SERVER"],
    oracleOptimalPath: ["YOU", "Relay-1", "Relay-3", "SERVER"],
  },

  recentRawPackets: [],
  recentMaskedPackets: [],
  livePacketsInFlight: [],

  setEvents: (events, runId = "scripted-episode", runHash = "") => {
    const maxT = events.length > 0 ? Math.max(...events.map((e) => e.t), 10.0) : 10.0;
    set({
      events,
      maxTime: maxT,
      playbackTime: 0.0,
      runId,
      runHash,
    });
    get().setPlaybackTime(0.0);
  },

  appendEvents: (newEvents) => {
    if (newEvents.length === 0) return;
    set((state) => {
      const merged = [...state.events, ...newEvents];
      const maxT = Math.max(...merged.map((e) => e.t), state.playbackTime);
      return {
        events: merged,
        maxTime: maxT,
      };
    });
  },

  setPlaybackTime: (time) => {
    const { events } = get();
    const clampedTime = Math.max(0, time);

    // Filter events up to clampedTime
    const relevantEvents = events.filter((e) => e.t <= clampedTime);

    // Compute derived state strictly from event spine
    let connState = "DISCONNECTED";
    let censorScore = 0.05;
    let censorAction: string | null = "ALLOW";
    let gateSlam = false;
    let throttleLevel = 0.0;
    let activeMask = "plain";
    let reasoningTicker = "Awaiting traffic telemetry...";
    let overhead = { bandwidthOverhead: 0.0, latencyCostMs: 0.5, stealthGain: 0.1 };
    const handshake: HandshakeProgress = { stage: 0, completed: false, rekeyCount: 0 };
    const trainRounds: TrainRoundData[] = [];
    const benchmarks: Record<string, number | string> = { ...get().benchmarks };
    const mesh: MeshTopologySnapshot = { ...get().mesh };

    const rawPackets: PacketVisualItem[] = [];
    const maskedPackets: PacketVisualItem[] = [];
    const inFlight: PacketVisualItem[] = [];

    for (const ev of relevantEvents) {
      switch (ev.kind) {
        case "CONN_STATE":
          connState = ev.state || connState;
          if (ev.state === "CONNECTED") {
            handshake.completed = true;
          }
          break;
        case "HANDSHAKE_MSG":
          handshake.stage = Number(ev.meta?.step || 1);
          handshake.messageType = String(ev.meta?.pattern || "Noise_XX");
          if (ev.meta?.session_id) {
            handshake.sessionId = String(ev.meta.session_id);
          }
          break;
        case "REKEY":
          handshake.rekeyCount += 1;
          break;
        case "CENSOR_SCORE":
          censorScore = Number(ev.meta?.score ?? ev.meta?.confidence ?? censorScore);
          break;
        case "CENSOR_ACTION": {
          const act = String(ev.meta?.action || "ALLOW");
          censorAction = act;
          if (act === "BLOCK") {
            gateSlam = true;
            connState = "BLOCKED";
          } else if (act === "THROTTLE") {
            throttleLevel = 0.75;
          } else {
            gateSlam = false;
            throttleLevel = 0.0;
          }
          break;
        }
        case "MASK_SWITCH":
          activeMask = ev.mask_id || activeMask;
          reasoningTicker = `Mask switched to [${activeMask}] | Overhead target: ${ev.meta?.overhead ?? "adaptive"}`;
          break;
        case "POLICY_DECISION":
          activeMask = ev.mask_id || activeMask;
          reasoningTicker = String(ev.meta?.reasoning || `Bandwidth overhead +${ev.meta?.overhead ?? 15}%`);
          if (typeof ev.meta?.bandwidth_overhead === "number") {
            overhead = {
              bandwidthOverhead: Number(ev.meta.bandwidth_overhead),
              latencyCostMs: Number(ev.meta.latency_cost_ms ?? 1.2),
              stealthGain: Number(ev.meta.stealth_gain ?? 0.85),
            };
          }
          break;
        case "TRAIN_ROUND":
          trainRounds.push({
            round: Number(ev.meta?.round ?? trainRounds.length + 1),
            attackerLoss: Number(ev.meta?.attacker_loss ?? 0.2),
            defenderReward: Number(ev.meta?.defender_reward ?? 0.8),
            paretoStealth: Number(ev.meta?.stealth ?? 0.85),
            paretoOverhead: Number(ev.meta?.overhead ?? 0.15),
            timestamp: ev.t,
          });
          break;
        case "BENCH_MARK":
          if (ev.meta?.metric && ev.meta?.value !== undefined) {
            benchmarks[String(ev.meta.metric)] = `${ev.meta.value} ${ev.meta.unit || ""}`;
          }
          break;
        case "ROUTE_CHANGE":
          if (Array.isArray(ev.meta?.new_path)) {
            mesh.activePath = ev.meta.new_path as string[];
          }
          if (Array.isArray(ev.meta?.oracle_optimal_path)) {
            mesh.oracleOptimalPath = ev.meta.oracle_optimal_path as string[];
          }
          if (ev.meta?.dead_node) {
            mesh.deadNodes = [String(ev.meta.dead_node)];
          }
          break;
        case "PKT_TX":
        case "PKT_RX": {
          const isTx = (ev.dir || "TX") === "TX";
          const pItem: PacketVisualItem = {
            id: `pkt-${ev.seq}`,
            seq: ev.seq,
            t: ev.t,
            size: ev.size || 512,
            dir: isTx ? "TX" : "RX",
            isDropped: false,
            maskId: ev.mask_id || activeMask,
          };
          rawPackets.push(pItem);
          maskedPackets.push(pItem);

          // If packet is recent (within 0.5s of playbackTime), it is actively in flight
          if (clampedTime - ev.t >= 0 && clampedTime - ev.t < 0.6) {
            inFlight.push(pItem);
          }
          break;
        }
        case "PKT_DROP": {
          const dropItem: PacketVisualItem = {
            id: `drop-${ev.seq}`,
            seq: ev.seq,
            t: ev.t,
            size: ev.size || 512,
            dir: "TX",
            isDropped: true,
            maskId: ev.mask_id || activeMask,
          };
          if (clampedTime - ev.t >= 0 && clampedTime - ev.t < 0.6) {
            inFlight.push(dropItem);
          }
          break;
        }
      }
    }

    set({
      playbackTime: clampedTime,
      connState,
      censorScore,
      censorAction,
      gateSlam,
      throttleLevel,
      activeMask,
      reasoningTicker,
      overheadGauge: overhead,
      handshake,
      trainRounds,
      benchmarks,
      mesh,
      recentRawPackets: rawPackets.slice(-100),
      recentMaskedPackets: maskedPackets.slice(-100),
      livePacketsInFlight: inFlight,
    });
  },

  setIsPlaying: (isPlaying) => set({ isPlaying }),
  setSpeed: (speed) => set({ speed }),
  setIsLive: (isLive) => set({ isLive }),
  setFps: (fps) => set({ fps }),
  triggerGateSlam: (gateSlam) => set({ gateSlam }),

  resetObservatory: () => {
    get().setPlaybackTime(0.0);
  },

  stepForward: (dt) => {
    const { playbackTime, maxTime, isPlaying, speed } = get();
    if (!isPlaying) return;
    const nextTime = playbackTime + dt * speed;
    if (nextTime >= maxTime) {
      // Loop smoothly back to beginning for presentation/demo mode
      get().setPlaybackTime(0.0);
    } else {
      get().setPlaybackTime(nextTime);
    }
  },
}));
