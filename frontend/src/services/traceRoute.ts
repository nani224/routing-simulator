import type { RouteEntry, TopologyData } from '../types';

export function traceRoute(
  topology: TopologyData,
  allRoutes: Record<string, RouteEntry[]>,
  src: string,
  dst: string
): { path: string[]; hasLoop: boolean; isBlackhole: boolean; totalCost: number; hops: number } {
  const visited = new Set<string>();
  const path: string[] = [src];
  let curr = src;
  let hasLoop = false;
  let isBlackhole = false;
  let totalCost = 0;

  while (curr !== dst) {
    visited.add(curr);
    const routes = allRoutes[curr] || [];
    const entry = routes.find((r) => r.destination === dst);

    if (!entry || !entry.next_hop) {
      // No route or null next-hop
      isBlackhole = true;
      break;
    }

    const next = entry.next_hop;
    // Accumulate link cost from topology
    const link = topology.links.find(
      (l) => (l.source === curr && l.target === next) || (l.source === next && l.target === curr)
    );
    if (!link?.is_up) {
      isBlackhole = true;
      break;
    }
    totalCost += link.cost;

    if (visited.has(next)) {
      // Loop detected!
      path.push(next);
      hasLoop = true;
      break;
    }

    path.push(next);
    curr = next;

    if (path.length > 20) {
      hasLoop = true;
      break;
    }
  }

  return { path, hasLoop, isBlackhole, totalCost, hops: Math.max(0, path.length - 1) };
}
