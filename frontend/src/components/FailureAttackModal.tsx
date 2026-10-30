import React, { useState } from 'react';
import type { TopologyData } from '../types';
import {
  X,
  Zap,
  Skull,
  ShieldCheck,
  Scissors,
  Link as LinkIcon,
  Power,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';

interface FailureAttackModalProps {
  isOpen: boolean;
  onClose: () => void;
  topology: TopologyData;
  crashedNodes: string[];
  severedLinks: { source: string; target: string }[];
  hasMutatedCosts: boolean;
  currentProtocol: string;
  onMutateLinkState: (u: string, v: string, up: boolean) => void;
  onRestoreAllLinks: () => void;
  onMutateLinkCost: (u: string, v: string, cost: number) => void;
  onResetLinkCosts: () => void;
  onInjectPoisonAttack: (targetNode: string, maliciousCost: number) => void;
  onClearPoisonAttack: () => void;
  onActivateMitigation: () => void;
  onCrashNode: (nodeId: string) => void;
  onRecoverNode: (nodeId: string) => void;
  onRecoverAllNodes: () => void;
  onResetAllAttacks: () => void;
}

export const FailureAttackModal: React.FC<FailureAttackModalProps> = ({
  isOpen,
  onClose,
  topology,
  crashedNodes,
  severedLinks,
  hasMutatedCosts,
  currentProtocol,
  onMutateLinkState,
  onRestoreAllLinks,
  onMutateLinkCost,
  onResetLinkCosts,
  onInjectPoisonAttack,
  onClearPoisonAttack,
  onActivateMitigation,
  onCrashNode,
  onRecoverNode,
  onRecoverAllNodes,
  onResetAllAttacks,
}) => {
  const [selectedLinkKey, setSelectedLinkKey] = useState<string>('');
  const [newCost, setNewCost] = useState<number>(10);
  const [targetPoisonNode, setTargetPoisonNode] = useState<string>('R6');
  const [maliciousCost, setMaliciousCost] = useState<number>(1);
  const [selectedNodeId, setSelectedNodeId] = useState<string>('R2');

  if (!isOpen) return null;

  const nodeIds = Object.keys(topology.nodes);
  const isPoisonActive = currentProtocol === 'poisoning_attack';
  const isMitigationActive = currentProtocol === 'secure_dv';
  const hasActiveAttacks =
    crashedNodes.length > 0 ||
    severedLinks.length > 0 ||
    isPoisonActive ||
    isMitigationActive ||
    hasMutatedCosts;

  const isSelectedNodeCrashed = crashedNodes.includes(selectedNodeId);

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
          width: '580px',
          maxWidth: '100%',
          maxHeight: '90vh',
          background: 'var(--surface-card)',
          border: '2px solid var(--border-brass)',
          boxShadow: 'var(--shadow-lg)',
          overflowY: 'auto',
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
            position: 'sticky',
            top: 0,
            zIndex: 10,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Zap size={18} color="var(--accent-crimson)" />
            <div>
              <div style={{ fontWeight: 800, fontFamily: 'var(--font-heading)', fontSize: '1rem' }}>
                Failure & Attack Injection Lab
              </div>
              <div style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                PERTURB TOPOLOGY, INJECT ADVERSARIES & EVALUATE RESILIENCE
              </div>
            </div>
          </div>
          <button className="btn-brass" style={{ width: '30px', height: '30px', padding: 0 }} onClick={onClose}>
            <X size={15} />
          </button>
        </div>

        {/* Global Status Banner & Master Reset */}
        <div
          style={{
            padding: '0.8rem 1.2rem',
            borderBottom: '1px solid var(--border-ink)',
            background: hasActiveAttacks
              ? 'oklch(from var(--accent-crimson) l c h / 0.08)'
              : 'oklch(from var(--accent-verdigris) l c h / 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '0.6rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1, minWidth: '240px' }}>
            {hasActiveAttacks ? (
              <AlertTriangle size={18} color="var(--accent-crimson)" style={{ flexShrink: 0 }} />
            ) : (
              <CheckCircle2 size={18} color="var(--accent-verdigris)" style={{ flexShrink: 0 }} />
            )}
            <div>
              <div
                style={{
                  fontSize: '0.82rem',
                  fontWeight: 700,
                  color: hasActiveAttacks ? 'var(--accent-crimson)' : 'var(--accent-verdigris)',
                }}
              >
                {hasActiveAttacks ? 'Active Perturbations Present' : 'Topology & Routing State Nominal'}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                {hasActiveAttacks ? (
                  <span>
                    {severedLinks.length > 0 && `${severedLinks.length} link(s) severed · `}
                    {crashedNodes.length > 0 && `${crashedNodes.length} node(s) crashed · `}
                    {isPoisonActive && 'Poison Attack Active · '}
                    {isMitigationActive && 'Secure DV Active · '}
                    {hasMutatedCosts && 'Link metric modified'}
                  </span>
                ) : (
                  'All links online, routers operational, standard metrics.'
                )}
              </div>
            </div>
          </div>

          {hasActiveAttacks && (
            <button
              className="btn-brass btn-brass-primary"
              style={{
                background: 'var(--accent-crimson)',
                borderColor: 'var(--accent-crimson)',
                color: '#FFFFFF',
                display: 'flex',
                alignItems: 'center',
                gap: '0.35rem',
                fontSize: '0.78rem',
                padding: '0.4rem 0.8rem',
              }}
              onClick={onResetAllAttacks}
              title="Restore all severed links, recover all nodes, revert metrics, and clear attacks"
            >
              <RotateCcw size={13} />
              Reset & Clear All Attacks
            </button>
          )}
        </div>

        {/* Content Sections */}
        <div style={{ padding: '1.2rem', display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
          {/* Section 1: Link Failure & Recovery */}
          <div
            style={{
              padding: '0.9rem',
              border: `1px solid ${severedLinks.length > 0 ? 'var(--accent-terracotta)' : 'var(--border-ink)'}`,
              borderRadius: '6px',
              background: 'var(--surface-inset)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '0.6rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Scissors size={15} color="var(--accent-terracotta)" />
                <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>Link Failure & Recovery</span>
              </div>
              {severedLinks.length > 0 && (
                <button
                  className="btn-brass"
                  style={{
                    fontSize: '0.72rem',
                    padding: '0.2rem 0.5rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.3rem',
                    color: 'var(--accent-verdigris)',
                    borderColor: 'var(--accent-verdigris)',
                  }}
                  onClick={onRestoreAllLinks}
                  title="Restore all currently severed links"
                >
                  <RefreshCw size={11} />
                  Restore All Links ({severedLinks.length})
                </button>
              )}
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
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

            {/* Severed links list */}
            {severedLinks.length > 0 && (
              <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.68rem', color: 'var(--accent-crimson)', fontWeight: 600 }}>
                  Severed Links:
                </span>
                {severedLinks.map((lnk, idx) => (
                  <button
                    key={idx}
                    onClick={() => onMutateLinkState(lnk.source, lnk.target, true)}
                    title="Click to restore this link"
                    style={{
                      background: 'oklch(from var(--accent-crimson) l c h / 0.15)',
                      color: 'var(--accent-crimson)',
                      border: '1px solid var(--accent-crimson)',
                      borderRadius: '4px',
                      padding: '0.15rem 0.4rem',
                      fontSize: '0.68rem',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.25rem',
                    }}
                  >
                    <span>{lnk.source} ↔ {lnk.target}</span>
                    <span style={{ fontSize: '0.6rem', opacity: 0.8 }}>✕ Restore</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Section 2: Link Cost Mutation */}
          <div
            style={{
              padding: '0.9rem',
              border: `1px solid ${hasMutatedCosts ? 'var(--accent-brass)' : 'var(--border-ink)'}`,
              borderRadius: '6px',
              background: 'var(--surface-inset)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '0.6rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <LinkIcon size={15} color="var(--accent-brass)" />
                <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>Mutate Link Cost Metric</span>
              </div>
              {hasMutatedCosts && (
                <button
                  className="btn-brass"
                  style={{
                    fontSize: '0.72rem',
                    padding: '0.2rem 0.5rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.3rem',
                  }}
                  onClick={onResetLinkCosts}
                  title="Revert all modified link metrics to baseline values"
                >
                  <RotateCcw size={11} />
                  Reset Link Costs
                </button>
              )}
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
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
                  width: '56px',
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
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '0.4rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Skull size={16} color="var(--accent-crimson)" />
                <span style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--accent-crimson)' }}>
                  Malicious Route Poisoning Attack
                </span>
              </div>
              {(isPoisonActive || isMitigationActive) && (
                <button
                  className="btn-brass"
                  style={{
                    fontSize: '0.72rem',
                    padding: '0.2rem 0.5rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.3rem',
                    borderColor: 'var(--accent-brass)',
                  }}
                  onClick={onClearPoisonAttack}
                  title="Clear malicious poison announcements and revert to standard Distance Vector"
                >
                  <RotateCcw size={11} />
                  Clear Poison Attack
                </button>
              )}
            </div>
            <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginBottom: '0.6rem' }}>
              Inject forged distance vectors advertising metric 1 to hijack traffic towards a blackhole node.
            </p>

            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <select
                value={targetPoisonNode}
                onChange={(e) => setTargetPoisonNode(e.target.value)}
                style={{
                  flex: 1,
                  minWidth: '150px',
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
                    Target Victim: {nid}
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
                }}
              >
                Inject Poison
              </button>

              <button
                className="btn-brass btn-brass-primary"
                style={{ background: 'var(--accent-gold)', borderColor: 'var(--accent-gold)', color: '#1E1E1E' }}
                onClick={() => {
                  onActivateMitigation();
                }}
                title="Activate HMAC Cryptographic Signing & Metric Sanity Filter"
              >
                <ShieldCheck size={14} />
                Activate Defense
              </button>
            </div>

            {/* Active attack badge */}
            {isPoisonActive && (
              <div
                style={{
                  marginTop: '0.5rem',
                  padding: '0.35rem 0.6rem',
                  background: 'oklch(from var(--accent-crimson) l c h / 0.15)',
                  border: '1px solid var(--accent-crimson)',
                  borderRadius: '4px',
                  fontSize: '0.72rem',
                  color: 'var(--accent-crimson)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <span>⚠️ Poisoning Active: Advertising forged vector to victim destination.</span>
                <span style={{ fontWeight: 700 }}>Protocol: route_poisoning_attack</span>
              </div>
            )}
            {isMitigationActive && (
              <div
                style={{
                  marginTop: '0.5rem',
                  padding: '0.35rem 0.6rem',
                  background: 'oklch(from var(--accent-verdigris) l c h / 0.15)',
                  border: '1px solid var(--accent-verdigris)',
                  borderRadius: '4px',
                  fontSize: '0.72rem',
                  color: 'var(--accent-verdigris)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <span>🛡️ Defense Active: HMAC-SHA256 signature verification filtering forged routes.</span>
                <span style={{ fontWeight: 700 }}>Protocol: secure_dv</span>
              </div>
            )}
          </div>

          {/* Section 4: Abrupt Node Crash Failure & Recovery */}
          <div
            style={{
              padding: '0.9rem',
              border: `1px solid ${crashedNodes.length > 0 ? 'var(--accent-crimson)' : 'var(--border-ink)'}`,
              borderRadius: '6px',
              background: 'var(--surface-inset)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '0.6rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Power size={15} color="var(--accent-crimson)" />
                <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>Simulate Sudden Node Crash Failure</span>
              </div>
              {crashedNodes.length > 0 && (
                <button
                  className="btn-brass"
                  style={{
                    fontSize: '0.72rem',
                    padding: '0.2rem 0.5rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.3rem',
                    color: 'var(--accent-verdigris)',
                    borderColor: 'var(--accent-verdigris)',
                  }}
                  onClick={onRecoverAllNodes}
                  title="Recover all crashed router nodes"
                >
                  <RefreshCw size={11} />
                  Recover All Routers ({crashedNodes.length})
                </button>
              )}
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <select
                value={selectedNodeId}
                onChange={(e) => setSelectedNodeId(e.target.value)}
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
                    Router {nid} {crashedNodes.includes(nid) ? '(CRASHED)' : '(ONLINE)'}
                  </option>
                ))}
              </select>

              {isSelectedNodeCrashed ? (
                <button
                  className="btn-brass btn-brass-primary"
                  style={{ background: 'var(--accent-verdigris)', borderColor: 'var(--accent-verdigris)' }}
                  onClick={() => onRecoverNode(selectedNodeId)}
                >
                  <Power size={13} />
                  Recover {selectedNodeId}
                </button>
              ) : (
                <button
                  className="btn-brass"
                  style={{ borderColor: 'var(--accent-crimson)', color: 'var(--accent-crimson)' }}
                  onClick={() => onCrashNode(selectedNodeId)}
                >
                  <Power size={13} />
                  Crash Router
                </button>
              )}
            </div>

            {/* Crashed nodes list */}
            {crashedNodes.length > 0 && (
              <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.68rem', color: 'var(--accent-crimson)', fontWeight: 600 }}>
                  Crashed Routers:
                </span>
                {crashedNodes.map((nid) => (
                  <button
                    key={nid}
                    onClick={() => onRecoverNode(nid)}
                    title={`Click to recover ${nid}`}
                    style={{
                      background: 'oklch(from var(--accent-crimson) l c h / 0.15)',
                      color: 'var(--accent-crimson)',
                      border: '1px solid var(--accent-crimson)',
                      borderRadius: '4px',
                      padding: '0.15rem 0.4rem',
                      fontSize: '0.68rem',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.25rem',
                    }}
                  >
                    <span>Router {nid}</span>
                    <span style={{ fontSize: '0.6rem', opacity: 0.8 }}>✕ Recover</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
