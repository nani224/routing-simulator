import { useEffect, useRef, useState } from 'react';
import type { TopologyData, TopologyLink } from '../types';
import './TopologyBuilder.css';

const defaultLink = { cost: 1, latency_ms: 10, jitter_ms: 0, loss_rate: 0, bandwidth_bps: 0 };
const linkFields = [
  ['cost', 'Link cost', 0.001],
  ['latency_ms', 'Delay (ms)', 0],
  ['jitter_ms', 'Jitter (ms)', 0],
  ['loss_rate', 'Loss probability (0–1)', 0],
  ['bandwidth_bps', 'Bandwidth (bps, 0 for unlimited)', 0],
] as const;

interface Props {
  initial: TopologyData | null;
  onClose: () => void;
  onSave: (topology: TopologyData) => void;
}

export function TopologyBuilder({ initial, onClose, onSave }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [name, setName] = useState(initial?.name ?? '');
  const [routers, setRouters] = useState(() => Object.entries(initial?.nodes ?? {})
    .map(([id, node]) => ({ id, as_number: node.as_number ?? 65001 })));
  const [links, setLinks] = useState(initial?.links ?? []);
  const [routerName, setRouterName] = useState('');
  const [asn, setAsn] = useState(65001);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [metrics, setMetrics] = useState(defaultLink);
  const [error, setError] = useState('');
  const source = routers.some(({ id }) => id === from) ? from : routers[0]?.id ?? '';
  const target = routers.some(({ id }) => id === to) ? to : routers[1]?.id ?? '';

  useEffect(() => { dialog.current?.showModal(); }, []);

  function addRouter() {
    const id = routerName.trim();
    if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,31}$/.test(id) || Object.hasOwn(Object.prototype, id)) {
      setError('Use 1–32 letters, digits, periods, underscores or hyphens for a router name. Start with a letter or digit.');
      return;
    }
    if (routers.some((router) => router.id === id)) {
      setError('Router names must be unique.');
      return;
    }
    if (!Number.isInteger(asn) || asn < 1 || asn > 4294967295) {
      setError('Enter an autonomous system number between 1 and 4294967295.');
      return;
    }
    setRouters([...routers, { id, as_number: asn }]);
    setRouterName('');
    setError('');
  }

  function addLink() {
    if (!source || !target || source === target) {
      setError('Choose two different routers.');
      return;
    }
    if (linkFields.some(([key, , min]) => !Number.isFinite(metrics[key]) || metrics[key] < min) || metrics.loss_rate > 1) {
      setError('Check the link metrics. Cost must be positive and loss must be between 0 and 1.');
      return;
    }
    const link: TopologyLink = { ...metrics, source, target, is_up: true };
    const existing = links.findIndex((other) =>
      (other.source === source && other.target === target) ||
      (other.source === target && other.target === source));
    setLinks(existing < 0 ? [...links, link] : links.map((other, i) => i === existing ? link : other));
    setError('');
  }

  function save() {
    if (!name.trim() || routers.length < 2) {
      setError('Enter a network name and add at least two routers.');
      return;
    }
    const nodes = Object.fromEntries(routers.map(({ id, as_number }, index) => {
      const angle = Math.PI * 2 * index / routers.length - Math.PI / 2;
      return [id, { x: 480 + 320 * Math.cos(angle), y: 320 + 220 * Math.sin(angle), as_number }];
    }));
    onSave({ name: name.trim(), nodes, links });
  }

  return (
    <dialog className="topology-builder" ref={dialog} aria-labelledby="builder-title" onCancel={onClose}>
      <header>
        <h2 id="builder-title">Topology builder</h2>
        <button type="button" className="btn-brass" onClick={onClose}>Close</button>
      </header>
      <label>Network name<input value={name} maxLength={80} onChange={(event) => setName(event.target.value)} /></label>
      <section aria-labelledby="builder-routers">
        <h3 id="builder-routers">Routers</h3>
        <form onSubmit={(event) => { event.preventDefault(); addRouter(); }}>
          <label>Router name<input value={routerName} onChange={(event) => setRouterName(event.target.value)} /></label>
          <label>Autonomous system<input type="number" min={1} max={4294967295} value={asn || ''} onChange={(event) => setAsn(event.target.valueAsNumber)} /></label>
          <button className="btn-brass">Add router</button>
        </form>
        <ul>{routers.map(({ id, as_number }) => (
          <li key={id}>
            <span>{id} · AS {as_number}</span>
            <button className="btn-brass" aria-label={`Remove router ${id}`} onClick={() => {
              setRouters(routers.filter((router) => router.id !== id));
              setLinks(links.filter((link) => link.source !== id && link.target !== id));
            }}>Remove</button>
          </li>
        ))}</ul>
      </section>
      <section aria-labelledby="builder-links">
        <h3 id="builder-links">Links</h3>
        <form onSubmit={(event) => { event.preventDefault(); addLink(); }}>
          <label>From router<select value={source} onChange={(event) => setFrom(event.target.value)}>
            {routers.map(({ id }) => <option key={id}>{id}</option>)}
          </select></label>
          <label>To router<select value={target} onChange={(event) => setTo(event.target.value)}>
            {routers.map(({ id }) => <option key={id}>{id}</option>)}
          </select></label>
          {linkFields.map(([key, label, min]) => (
            <label key={key}>{label}<input
              type="number" step="any" min={min} max={key === 'loss_rate' ? 1 : undefined}
              value={Number.isNaN(metrics[key]) ? '' : metrics[key]}
              onChange={(event) => setMetrics({ ...metrics, [key]: event.target.valueAsNumber })}
            /></label>
          ))}
          <button className="btn-brass" disabled={routers.length < 2}>Add link</button>
        </form>
        <ul>{links.map((link) => (
          <li key={`${link.source}:${link.target}`}>
            <span>{link.source} ↔ {link.target} · Cost {link.cost} · {link.latency_ms} ms</span>
            <button className="btn-brass" onClick={() => {
              setFrom(link.source);
              setTo(link.target);
              setMetrics(link);
            }}>Edit</button>
            <button className="btn-brass" aria-label={`Remove link ${link.source} to ${link.target}`} onClick={() => setLinks(links.filter((item) => item !== link))}>Remove</button>
          </li>
        ))}</ul>
      </section>
      {error && <p role="alert">{error}</p>}
      <footer><button className="btn-brass btn-brass-primary" onClick={save}>Save and run</button></footer>
    </dialog>
  );
}
