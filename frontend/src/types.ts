export type ProtocolType =
  | 'distance_vector'
  | 'link_state'
  | 'bgp_lite'
  | 'flooding'
  | 'poisoning_attack'
  | 'secure_dv';

export interface TopologyNode {
  id: string;
  x: number;
  y: number;
  label?: string;
  as_number?: number;
  is_crashed?: boolean;
}

export interface TopologyLink {
  source: string;
  target: string;
  cost: number;
  latency_ms: number;
  jitter_ms: number;
  loss_rate: number;
  bandwidth_bps: number;
  is_up: boolean;
}

export interface TopologyData {
  name: string;
  description?: string;
  nodes: Record<string, { x: number; y: number; as_number?: number }>;
  links: TopologyLink[];
}

export interface RouteEntry {
  destination: string;
  next_hop: string | null;
  metric: number;
  protocol?: string;
  as_path?: number[];
  status?: string;
  flap_count?: number;
}

export interface NodeTelemetry {
  packets_sent: number;
  packets_received: number;
  bytes_sent: number;
  bytes_received: number;
  flaps_count: number;
  status: 'running' | 'crashed' | 'faulty' | 'stopped';
  routes: RouteEntry[];
  lsdb?: Record<string, { seq: number; age: number; neighbors: Record<string, number> }>;
}

export interface ConvergenceRecord {
  is_converged: boolean;
  convergence_time_s: number;
  total_control_messages: number;
  total_control_bytes: number;
  total_flaps: number;
}

export interface SimEventItem {
  seq: number;
  ts: number;
  type: string;
  src: string;
  data: Record<string, any>;
}

export interface PacketCourier {
  id: string;
  src: string;
  dst: string;
  progress: number; // 0.0 to 1.0
  speed: number;
  protocol: string;
  payloadType: string;
}

export interface ComparisonMetrics {
  protocol: string;
  convergence_time_s: number;
  total_messages: number;
  total_bytes: number;
  total_flaps: number;
  stretch: number;
}
