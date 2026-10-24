import React, { useState } from 'react';
import type { TopologyData } from '../types';
import { X, Zap, Skull, ShieldCheck, Scissors, Link as LinkIcon, Power } from 'lucide-react';

interface FailureAttackModalProps {
  isOpen: boolean;
  onClose: () => void;
  topology: TopologyData;
  onMutateLinkState: (u: string, v: string, up: boolean) => void;
  onMutateLinkCost: (u: string, v: string, cost: number) => void;
  onInjectPoisonAttack: (targetNode: string, maliciousCost: number) => void;
  onActivateMitigation: () => void;
  onCrashNode: (nodeId: string) => void;
}

export const FailureAttackModal: React.FC<FailureAttackModalProps> = ({
  isOpen,
  onClose,
  topology,
  onMutateLinkState,
  onMutateLinkCost,
  onInjectPoisonAttack,
  onActivateMitigation,
  onCrashNode,
}) => {
  const [selectedLinkKey, setSelectedLinkKey] = useState<string>('');
  const [newCost, setNewCost] = useState<number>(10);
  const [targetPoisonNode, setTargetPoisonNode] = useState<string>('R6');
  const [maliciousCost, setMaliciousCost] = useState<number>(1);
  const [crashNodeId, setCrashNodeId] = useState<string>('R2');

  if (!isOpen) return null;

  const nodeIds = Object.keys(topology.nodes);

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(20, 16, 12, 0.65)',
        backdropFilter: 'blur(3px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        padding: '1rem',
      }}
    >
      <div
        className="carto-card"
        style={{
          width: '540px',
          maxWidth: '100%',
          background: 'var(--surface-card)',
          border: '2px solid var(--border-brass)',
          boxShadow: 'var(--shadow-lg)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.85rem 1.2rem',
            borderBottom: '1px solid var(--border-ink)',
            background: 'var(--surface-inset)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Zap size={18} color="var(--accent-crimson)" />
            <div>
              <div style={{ fontWeight: 800, fontFamily: 'var(--font-heading)', fontSize: '1rem' }}>
                Failure & Attack Injection Lab
              </div>
              <div style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                PERTURB TOPOLOGY & EVALUATE CONVERGENCE RESILIENCE
              </div>
            </div>
          </div>
          <button className="btn-brass" style={{ width: '30px', height: '30px', padding: 0 }} onClick={onClose}>
            <X size={15} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '1.2rem', display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
          {/* Section 1: Link Failure & Recovery */}
          <div
            style={{
              padding: '0.9rem',
              border: '1px solid var(--border-ink)',
              borderRadius: '6px',
              background: 'var(--surface-inset)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.6rem' }}>
              <Scissors size={15} color="var(--accent-terracotta)" />
              <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>Link Failure & Recovery</span>
            </div>

            <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
              <select
                style={{
                  flex: 1,
                  padding: '0.4rem',
                  borderRadius: '4px',
                  border: '1px solid var(--border-ink)',
                  background: 'var(--surface-card)',
                  color: 'var(--text-primary)',
                  fontSize: '0.8rem',
                }}
                onChange={(e) => setSelectedLinkKey(e.target.value)}
                defaultValue=""
              >
                <option value="" disabled>
                  Select link to sever / restore...
                </option>
                {topology.links.map((lnk, idx) => (
                  <option key={idx} value={`${lnk.source}<->${lnk.target}`}>
                    {lnk.source} ↔ {lnk.target} (cost: {lnk.cost}, status: {lnk.is_up ? 'UP' : 'SEVERED'})
                  </option>
                ))}
              </select>

              <button
                className="btn-brass"
                style={{ borderColor: 'var(--accent-crimson)', color: 'var(--accent-crimson)' }}
                onClick={() => {
                  if (selectedLinkKey) {
                    const [u, v] = selectedLinkKey.split('<->');
                    onMutateLinkState(u, v, false);
                  }
                }}
              >
                Sever Link
              </button>

              <button
                className="btn-brass btn-brass-primary"
                style={{ background: 'var(--accent-verdigris)', borderColor: 'var(--accent-verdigris)' }}
                onClick={() => {
                  if (selectedLinkKey) {
                    const [u, v] = selectedLinkKey.split('<->');
                    onMutateLinkState(u, v, true);
                  }
                }}
              >
                Restore Link
              </button>
            </div>
          </div>

          {/* Section 2: Link Cost Mutation */}
          <div
            style={{
              padding: '0.9rem',
              border: '1px solid var(--border-ink)',
              borderRadius: '6px',
              background: 'var(--surface-inset)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.6rem' }}>
              <LinkIcon size={15} color="var(--accent-brass)" />
              <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>Mutate Link Cost Metric</span>
            </div>

            <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
              <select
                style={{
                  flex: 1,
                  padding: '0.4rem',
                  borderRadius: '4px',
                  border: '1px solid var(--border-ink)',
                  background: 'var(--surface-card)',
                  color: 'var(--text-primary)',
                  fontSize: '0.8rem',
                }}
                onChange={(e) => setSelectedLinkKey(e.target.value)}
                defaultValue=""
              >
                <option value="" disabled>
                  Select link...
                </option>
                {topology.links.map((lnk, idx) => (
                  <option key={idx} value={`${lnk.source}<->${lnk.target}`}>
                    {lnk.source} ↔ {lnk.target} (current cost: {lnk.cost})
                  </option>
                ))}
              </select>

              <input
                type="number"
                min="1"
                max="99"
                value={newCost}
                onChange={(e) => setNewCost(parseInt(e.target.value) || 1)}
                style={{
                  width: '60px',
                  padding: '0.4rem',
                  borderRadius: '4px',
                  border: '1px solid var(--border-ink)',
                  background: 'var(--surface-card)',
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-mono)',
                  textAlign: 'center',
                }}
              />

              <button
                className="btn-brass"
                onClick={() => {
                  if (selectedLinkKey) {
                    const [u, v] = selectedLinkKey.split('<->');
                    onMutateLinkCost(u, v, newCost);
                  }
                }}
              >
                Apply Metric
              </button>
            </div>
          </div>

          {/* Section 3: Route Poisoning Attack & Mitigation */}
          <div
            style={{
              padding: '0.9rem',
              border: '1px solid var(--accent-crimson)',
              borderRadius: '6px',
              background: 'oklch(from var(--accent-crimson) l c h / 0.08)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.4rem' }}>
              <Skull size={16} color="var(--accent-crimson)" />
              <span style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--accent-crimson)' }}>
                Malicious Route Poisoning Attack
              </span>
            </div>
            <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginBottom: '0.6rem' }}>
              Inject forged distance vectors advertising metric 1 to hijack traffic towards a blackhole node.
            </p>

            <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
              <select
                value={targetPoisonNode}
                onChange={(e) => setTargetPoisonNode(e.target.value)}
                style={{
                  flex: 1,
                  padding: '0.4rem',
                  borderRadius: '4px',
                  border: '1px solid var(--border-ink)',
                  background: 'var(--surface-card)',
                  color: 'var(--text-primary)',
                  fontSize: '0.8rem',
                }}
              >
                {nodeIds.map((nid) => (
                  <option key={nid} value={nid}>
                    Target Victim Destination: {nid}
                  </option>
                ))}
              </select>

              <input
                type="number"
                min="0"
                max="99"
                value={maliciousCost}
                onChange={(e) => setMaliciousCost(parseInt(e.target.value) || 0)}
                title="Malicious Advertised Cost"
                style={{
                  width: '50px',
                  padding: '0.4rem',
                  borderRadius: '4px',
                  border: '1px solid var(--border-ink)',
                  background: 'var(--surface-card)',
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-mono)',
                  textAlign: 'center',
                }}
              />

              <button
                className="btn-brass"
                style={{
                  background: 'var(--accent-crimson)',
                  color: '#FFFFFF',
                  borderColor: 'var(--accent-crimson)',
                }}
                onClick={() => {
                  onInjectPoisonAttack(targetPoisonNode, maliciousCost);
                  onClose();
                }}
              >
                Inject Poison
              </button>

              <button
                className="btn-brass btn-brass-primary"
                style={{ background: 'var(--accent-gold)', borderColor: 'var(--accent-gold)', color: '#1E1E1E' }}
                onClick={() => {
                  onActivateMitigation();
                  onClose();
                }}
              >
                <ShieldCheck size={14} />
                Activate Defense
              </button>
            </div>
          </div>

          {/* Section 4: Abrupt Node Crash Injection */}
          <div
            style={{
              padding: '0.9rem',
              border: '1px solid var(--border-ink)',
              borderRadius: '6px',
              background: 'var(--surface-inset)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.6rem' }}>
              <Power size={15} color="var(--accent-crimson)" />
              <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>Simulate Sudden Node Crash Failure</span>
            </div>
            <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
              <select
                value={crashNodeId}
                onChange={(e) => setCrashNodeId(e.target.value)}
                style={{
                  flex: 1,
                  padding: '0.4rem',
                  borderRadius: '4px',
                  border: '1px solid var(--border-ink)',
                  background: 'var(--surface-card)',
                  color: 'var(--text-primary)',
                  fontSize: '0.8rem',
                }}
              >
                {nodeIds.map((nid) => (
                  <option key={nid} value={nid}>
                    Crash Router {nid}
                  </option>
                ))}
              </select>
              <button
                className="btn-brass"
                style={{ borderColor: 'var(--accent-crimson)', color: 'var(--accent-crimson)' }}
                onClick={() => {
                  onCrashNode(crashNodeId);
                  onClose();
                }}
              >
                <Power size={13} />
                Execute Crash
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
