import type { TopologyData, ProtocolType, SimEventItem, ComparisonMetrics } from '../types';

const API_BASE = 'http://localhost:8000';
const WS_BASE = 'ws://localhost:8000/ws/simulation';

export class RouteLabApi {
  static async listTopologies(): Promise<string[]> {
    try {
      const res = await fetch(`${API_BASE}/api/topologies`);
      if (!res.ok) throw new Error(`API error: ${res.statusText}`);
      const data = await res.json();
      if (Array.isArray(data)) {
        return data.map((t: any) => t.name || t);
      }
      return data.topologies || ['course-6-node', 'course-8-node', 'course-10-node'];
    } catch {
      return ['course-6-node', 'course-8-node', 'course-10-node', 'ring-10', 'grid-9'];
    }
  }

  static async getTopology(name: string): Promise<TopologyData> {
    try {
      const res = await fetch(`${API_BASE}/api/topologies/${name}`);
      if (!res.ok) throw new Error(`API error: ${res.statusText}`);
      const data = await res.json();
      if (data && data.nodes && data.links) {
        return data;
      }
      return this.getFallbackTopology(name);
    } catch {
      return this.getFallbackTopology(name);
    }
  }

  static async generateTopology(
    generator: string,
    params: Record<string, any>
  ): Promise<TopologyData> {
    try {
      const res = await fetch(`${API_BASE}/api/topologies/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: generator, ...params }),
      });
      if (!res.ok) throw new Error(`API error: ${res.statusText}`);
      return await res.json();
    } catch {
      return this.getFallbackTopology('course-6-node');
    }
  }

  static async startSimulation(
    topology: TopologyData,
    protocol: ProtocolType,
    quiescence_s = 0.5,
    clockMode = 'virtual',
    clockSpeed = 1.0
  ): Promise<any> {
    const topology_data = {
      nodes: Object.entries(topology.nodes).map(([id, data]) => ({
        id,
        x: data.x,
        y: data.y,
        as_number: data.as_number,
      })),
      links: topology.links.map((link) => ({
        source: link.source,
        target: link.target,
        cost: link.cost,
        latency_ms: link.latency_ms,
        jitter_ms: link.jitter_ms,
        loss_rate: link.loss_rate,
        bandwidth_bps: link.bandwidth_bps,
      })),
    };

    try {
      const res = await fetch(`${API_BASE}/api/simulation/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topology_name: topology.name || 'Course-6-Node-Benchmark',
          topology_data,
          protocol_name: protocol,
          quiescence_window_s: quiescence_s,
          clock_mode: clockMode,
          clock_speed: clockSpeed,
        }),
      });
      if (!res.ok) {
        throw new Error(`Failed to start backend simulation: ${res.statusText}`);
      }
      return await res.json();
    } catch (e) {
      console.warn('Backend connection failed:', e);
      return { status: 'offline', error: String(e) };
    }
  }

  static async pauseSimulation(): Promise<any> {
    try {
      const res = await fetch(`${API_BASE}/api/simulation/pause`, { method: 'POST' });
      return await res.json();
    } catch {
      return { status: 'paused' };
    }
  }

  static async resumeSimulation(): Promise<any> {
    try {
      const res = await fetch(`${API_BASE}/api/simulation/resume`, { method: 'POST' });
      return await res.json();
    } catch {
      return { status: 'resumed' };
    }
  }

  static async stepSimulation(step_duration_s = 0.1): Promise<any> {
    try {
      const res = await fetch(`${API_BASE}/api/simulation/step`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ step_duration_s }),
      });
      return await res.json();
    } catch {
      return { status: 'stepped' };
    }
  }

  static async injectEvent(action: string, params: Record<string, any>): Promise<any> {
    try {
      const res = await fetch(`${API_BASE}/api/simulation/events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, params }),
      });
      return await res.json();
    } catch (e) {
      return { status: 'injection_failed', error: String(e) };
    }
  }

  static async getEvents(limit = 500): Promise<SimEventItem[]> {
    try {
      const res = await fetch(`${API_BASE}/api/simulation/events?limit=${limit}`);
      if (!res.ok) throw new Error('API error');
      const data = await res.json();
      return data.events || [];
    } catch {
      return [];
    }
  }

  static async listScenarios(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/api/scenarios`);
    if (!res.ok) throw new Error(`Failed to list scenarios: ${res.statusText}`);
    return await res.json();
  }

  static async getScenario(fileName: string): Promise<any> {
    const res = await fetch(`${API_BASE}/api/scenarios/${fileName}`);
    if (!res.ok) throw new Error(`Failed to load scenario ${fileName}: ${res.statusText}`);
    return await res.json();
  }

  static async runScenario(fileName: string, overrideProtocol?: ProtocolType): Promise<any> {
    const res = await fetch(`${API_BASE}/api/scenarios/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_name: fileName,
        override_protocol: overrideProtocol,
      }),
    });
    if (!res.ok) throw new Error(`Scenario run failed: ${res.statusText}`);
    return await res.json();
  }

  static async runCompare(
    topology: TopologyData,
    protocols: ProtocolType[],
    duration_s = 5.0
  ): Promise<Record<string, ComparisonMetrics>> {
    const backendTopologyData = {
      nodes: Object.entries(topology.nodes).map(([id, data]) => ({
        id,
        x: data.x,
        y: data.y,
        as_number: data.as_number,
      })),
      links: topology.links.map((link) => ({
        source: link.source,
        target: link.target,
        cost: link.cost,
        latency_ms: link.latency_ms,
        jitter_ms: link.jitter_ms,
        loss_rate: link.loss_rate,
        bandwidth_bps: link.bandwidth_bps,
      })),
    };

    const res = await fetch(`${API_BASE}/api/simulation/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topology_name: topology.name || 'Course-6-Node-Benchmark',
        topology_data: backendTopologyData,
        protocols,
        events: [],
        time_limit_s: duration_s,
      }),
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Comparison API failed (${res.status}): ${errText}`);
    }

    const data = await res.json();
    const rawMetrics = data.metrics || data.results || {};
    const normalized: Record<string, ComparisonMetrics> = {};
    for (const [key, m] of Object.entries(rawMetrics) as [string, any][]) {
      normalized[key] = {
        protocol: m.protocol_name || m.protocol || key,
        convergence_time_s: m.convergence_time_s ?? 0,
        total_messages: m.total_control_messages ?? m.total_messages ?? 0,
        total_bytes: m.total_control_bytes ?? m.total_bytes ?? 0,
        total_flaps: m.total_route_flaps ?? m.total_flaps ?? 0,
        stretch: m.average_path_stretch ?? m.stretch ?? 1.0,
      };
    }
    return normalized;
  }

  static connectWebSocket(
    onMessage: (delta: any) => void,
    onStatusChange?: (connected: boolean) => void
  ): { close: () => void; send: (msg: any) => void } {
    let ws: WebSocket | null = null;
    let isClosed = false;

    const connect = () => {
      try {
        ws = new WebSocket(WS_BASE);
        ws.onopen = () => {
          onStatusChange?.(true);
        };
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            onMessage(data);
          } catch (e) {
            console.error('Failed to parse WS payload:', e);
          }
        };
        ws.onclose = () => {
          onStatusChange?.(false);
          if (!isClosed) {
            setTimeout(connect, 3000);
          }
        };
        ws.onerror = () => {
          ws?.close();
        };
      } catch {
        onStatusChange?.(false);
        if (!isClosed) {
          setTimeout(connect, 3000);
        }
      }
    };

    connect();

    return {
      close: () => {
        isClosed = true;
        ws?.close();
      },
      send: (msg: any) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify(msg));
        }
      },
    };
  }

  static getFallbackTopology(name: string): TopologyData {
    if (name.includes('8')) {
      return {
        name: 'Course-8-Node Mesh',
        description: '8-node mesh with redundant paths for failover demonstration',
        nodes: {
          R1: { x: 120, y: 150 },
          R2: { x: 300, y: 100 },
          R3: { x: 480, y: 100 },
          R4: { x: 660, y: 150 },
          R5: { x: 660, y: 350 },
          R6: { x: 480, y: 400 },
          R7: { x: 300, y: 400 },
          R8: { x: 120, y: 350 },
        },
        links: [
          { source: 'R1', target: 'R2', cost: 2, latency_ms: 10, jitter_ms: 2, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R2', target: 'R3', cost: 3, latency_ms: 10, jitter_ms: 2, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R3', target: 'R4', cost: 1, latency_ms: 10, jitter_ms: 2, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R4', target: 'R5', cost: 4, latency_ms: 10, jitter_ms: 2, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R5', target: 'R6', cost: 2, latency_ms: 10, jitter_ms: 2, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R6', target: 'R7', cost: 3, latency_ms: 10, jitter_ms: 2, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R7', target: 'R8', cost: 1, latency_ms: 10, jitter_ms: 2, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R8', target: 'R1', cost: 4, latency_ms: 10, jitter_ms: 2, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R2', target: 'R7', cost: 5, latency_ms: 15, jitter_ms: 3, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R3', target: 'R6', cost: 5, latency_ms: 15, jitter_ms: 3, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
        ],
      };
    }

    if (name.includes('10')) {
      return {
        name: 'Course-10-Node WAN',
        description: '10-node backbone with high diameter and diverse path costs',
        nodes: {
          R1: { x: 100, y: 250 },
          R2: { x: 220, y: 150 },
          R3: { x: 220, y: 350 },
          R4: { x: 380, y: 150 },
          R5: { x: 380, y: 350 },
          R6: { x: 540, y: 150 },
          R7: { x: 540, y: 350 },
          R8: { x: 700, y: 150 },
          R9: { x: 700, y: 350 },
          R10: { x: 820, y: 250 },
        },
        links: [
          { source: 'R1', target: 'R2', cost: 1, latency_ms: 10, jitter_ms: 1, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R1', target: 'R3', cost: 4, latency_ms: 15, jitter_ms: 2, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R2', target: 'R4', cost: 2, latency_ms: 10, jitter_ms: 1, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R3', target: 'R5', cost: 1, latency_ms: 10, jitter_ms: 1, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R4', target: 'R6', cost: 3, latency_ms: 12, jitter_ms: 2, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R5', target: 'R7', cost: 2, latency_ms: 10, jitter_ms: 1, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R6', target: 'R8', cost: 1, latency_ms: 10, jitter_ms: 1, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R7', target: 'R9', cost: 4, latency_ms: 15, jitter_ms: 2, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R8', target: 'R10', cost: 2, latency_ms: 10, jitter_ms: 1, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R9', target: 'R10', cost: 1, latency_ms: 10, jitter_ms: 1, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R4', target: 'R5', cost: 2, latency_ms: 10, jitter_ms: 1, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
          { source: 'R6', target: 'R7', cost: 2, latency_ms: 10, jitter_ms: 1, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
        ],
      };
    }

    // Default Course 6-Node Topology
    return {
      name: 'Course-6-Node',
      description: 'Standard 6-node topology from course specification',
      nodes: {
        R1: { x: 120, y: 250, as_number: 100 },
        R2: { x: 300, y: 130, as_number: 100 },
        R3: { x: 300, y: 370, as_number: 100 },
        R4: { x: 500, y: 130, as_number: 200 },
        R5: { x: 500, y: 370, as_number: 200 },
        R6: { x: 680, y: 250, as_number: 300 },
      },
      links: [
        { source: 'R1', target: 'R2', cost: 1, latency_ms: 10, jitter_ms: 2, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
        { source: 'R1', target: 'R3', cost: 4, latency_ms: 20, jitter_ms: 3, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
        { source: 'R2', target: 'R4', cost: 2, latency_ms: 10, jitter_ms: 2, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
        { source: 'R3', target: 'R5', cost: 1, latency_ms: 10, jitter_ms: 1, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
        { source: 'R2', target: 'R3', cost: 2, latency_ms: 15, jitter_ms: 2, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
        { source: 'R4', target: 'R5', cost: 3, latency_ms: 10, jitter_ms: 2, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
        { source: 'R4', target: 'R6', cost: 5, latency_ms: 25, jitter_ms: 4, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
        { source: 'R5', target: 'R6', cost: 2, latency_ms: 10, jitter_ms: 1, loss_rate: 0, bandwidth_bps: 10000000, is_up: true },
      ],
    };
  }
}
