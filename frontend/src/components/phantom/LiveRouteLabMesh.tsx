import { useState } from 'react';
import type { ProtocolType, RouteEntry, TopologyData } from '../../types';
import { RouteLabApi } from '../../services/api';
import { traceRoute } from '../../services/traceRoute';

interface Props {
  topology: TopologyData;
  routes: Record<string, RouteEntry[]>;
  protocol: ProtocolType;
  connected: boolean;
  converged: boolean;
  onOpenRouteLab: () => void;
  onSendProbe: (path: string[]) => Promise<void>;
}

export function LiveRouteLabMesh({ topology, routes, protocol, connected, converged, onOpenRouteLab, onSendProbe }: Props) {
  const nodes = Object.keys(topology.nodes);
  const [selectedSource, setSource] = useState('');
  const [selectedDestination, setDestination] = useState('');
  const source = Object.hasOwn(topology.nodes, selectedSource) ? selectedSource : nodes[0];
  const destination = Object.hasOwn(topology.nodes, selectedDestination) ? selectedDestination : nodes.at(-1);
  const trace = source && destination && source !== destination
    ? traceRoute(topology, routes, source, destination)
    : null;
  const [linkIndex, setLinkIndex] = useState(0);
  const link = topology.links[linkIndex] ?? topology.links[0];
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');

  async function toggleLink() {
    if (!link || pending) return;
    setPending(true);
    setError('');
    try {
      const result = await RouteLabApi.injectEvent(link.is_up ? 'link_down' : 'link_up', {
        u: link.source,
        v: link.target,
      });
      if (result.status !== 'event_injected') setError('RouteLab could not change this link.');
    } finally {
      setPending(false);
    }
  }

  const hops = trace && !trace.isBlackhole && !trace.hasLoop ? trace.path : null;
  const path = hops?.join(' → ');

  async function sendProbe() {
    if (!hops) return;
    setError('');
    try {
      await onSendProbe(hops);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
    }
  }

  return (
    <section className="po-header po-routing-mesh" aria-labelledby="live-routing-mesh-title">
      <div>
        <h2 className="po-title" id="live-routing-mesh-title">Live RouteLab mesh</h2>
        <p className="po-subtitle">
          {topology.name} · {protocol.replaceAll('_', ' ')} · {connected ? (converged ? 'Routes settled' : 'Routes updating') : 'Waiting for RouteLab'}
        </p>
      </div>
      <div>
        <div className="po-routing-actions">
          <select className="btn-brass" aria-label="Source router" value={source ?? ''} onChange={(event) => setSource(event.target.value)}>
            {nodes.map((id) => <option key={id}>{id}</option>)}
          </select>
          <span aria-hidden="true">→</span>
          <select className="btn-brass" aria-label="Destination router" value={destination ?? ''} onChange={(event) => setDestination(event.target.value)}>
            {nodes.map((id) => <option key={id}>{id}</option>)}
          </select>
        </div>
        <p aria-label="Current forwarding path">
          {connected ? path ?? (source === destination ? 'Choose two different routers' : trace?.hasLoop ? 'Routing loop' : 'No forwarding path') : 'Waiting for routing tables'}
        </p>
      </div>
      <div className="po-routing-actions">
        <select
          className="btn-brass"
          aria-label="Simulation link"
          value={topology.links[linkIndex] ? linkIndex : 0}
          onChange={(event) => setLinkIndex(Number(event.target.value))}
          disabled={!connected || pending || !link}
        >
          {topology.links.map((item, index) => (
            <option key={[item.source, item.target].sort().join('↔')} value={index}>
              {[item.source, item.target].sort().join(' ↔ ')} · {item.is_up ? 'Up' : 'Down'}
            </option>
          ))}
        </select>
        <button className="btn-brass" disabled={!connected || pending || !link} onClick={toggleLink}>
          {link?.is_up ? 'Fail link' : 'Restore link'}
        </button>
        <button className="btn-brass" disabled={!connected || !hops} onClick={sendProbe}>Send probe</button>
        <button className="btn-brass" onClick={onOpenRouteLab}>Open RouteLab</button>
        {error && <span role="alert">{error}</span>}
      </div>
    </section>
  );
}
