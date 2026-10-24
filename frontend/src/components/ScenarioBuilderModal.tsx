import React from 'react';
import { X, Radio, Play, CheckCircle, Flame, ShieldAlert, Globe, Network } from 'lucide-react';
import type { ProtocolType } from '../types';

interface ScenarioBuilderModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLaunchScenario: (scenarioId: string, protocol: ProtocolType) => void;
}

interface ScenarioItem {
  id: string;
  title: string;
  badge: string;
  description: string;
  recommendedProtocol: ProtocolType;
  icon: React.ReactNode;
}

export const ScenarioBuilderModal: React.FC<ScenarioBuilderModalProps> = ({
  isOpen,
  onClose,
  onLaunchScenario,
}) => {
  if (!isOpen) return null;

  const scenarios: ScenarioItem[] = [
    {
      id: 'course-6-node-dv-vs-ls',
      title: 'Course 6-Node: DV vs LS Convergence',
      badge: 'MANDATORY COURSE',
      description: 'Standard 6-node course topology. Evaluates Bellman-Ford periodic vectors vs Dijkstra SPF link-state flooding.',
      recommendedProtocol: 'distance_vector',
      icon: <Network size={18} color="var(--accent-brass)" />,
    },
    {
      id: 'course-8-node-failover',
      title: 'Course 8-Node Mesh: Redundant Failover',
      badge: 'TOPOLOGY BENCHMARK',
      description: '8-node mesh with dual disjoint paths. Triggers a link failure at t=1.0s to measure alternate path convergence speed.',
      recommendedProtocol: 'link_state',
      icon: <CheckCircle size={18} color="var(--accent-verdigris)" />,
    },
    {
      id: 'course-10-node-wan',
      title: 'Course 10-Node WAN: High Diameter Stress',
      badge: 'SCALE TEST',
      description: '10-node backbone with diameter 6. Demonstrates message explosion vs SPF tree computation on large networks.',
      recommendedProtocol: 'link_state',
      icon: <Network size={18} color="var(--accent-cobalt)" />,
    },
    {
      id: 'count-to-infinity-flaw',
      title: 'Count-to-Infinity Flaw (RIP Vulnerability)',
      badge: 'PROTOCOL FLAW',
      description: '3-node line topology (A-B-C). Link B-C severs at t=1.0s with split-horizon disabled. Metric bounces up to 16.',
      recommendedProtocol: 'distance_vector',
      icon: <Flame size={18} color="var(--accent-crimson)" />,
    },
    {
      id: 'count-to-infinity-remedy',
      title: 'Count-to-Infinity Remedy: Poison Reverse',
      badge: 'MITIGATION',
      description: 'Identical 3-node topology with Split Horizon & Poison Reverse active. Loop is neutralized immediately in 1 step.',
      recommendedProtocol: 'distance_vector',
      icon: <CheckCircle size={18} color="var(--accent-gold)" />,
    },
    {
      id: 'bgp-tier1-policy',
      title: 'BGP Tier-1 Peering & Policy Routing',
      badge: 'INTER-DOMAIN',
      description: 'Multi-AS inter-domain peering topology. Uses AS_PATH loop detection and LOCAL_PREF policy route selection.',
      recommendedProtocol: 'bgp_lite',
      icon: <Globe size={18} color="var(--accent-cobalt)" />,
    },
    {
      id: 'poisoning-attack-mitigation',
      title: 'Route Poisoning Attack & Secure DV Defense',
      badge: 'CYBERSECURITY',
      description: 'Adversary node advertises forged metric 1 to hijack traffic. Secure DV cryptographic filtering blocks the malicious update.',
      recommendedProtocol: 'secure_dv',
      icon: <ShieldAlert size={18} color="var(--accent-crimson)" />,
    },
  ];

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(20, 16, 12, 0.7)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        padding: '1.5rem',
      }}
    >
      <div
        className="carto-card"
        style={{
          width: '740px',
          maxWidth: '100%',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--surface-card)',
          border: '2px solid var(--border-brass)',
          boxShadow: 'var(--shadow-lg)',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.9rem 1.4rem',
            borderBottom: '1px solid var(--border-ink)',
            background: 'var(--surface-inset)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Radio size={20} color="var(--accent-brass)" />
            <div>
              <div style={{ fontWeight: 800, fontFamily: 'var(--font-heading)', fontSize: '1.05rem' }}>
                Course Scenario Presets & Schedule Runner
              </div>
              <div style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                ONE-CLICK LAUNCH FOR ALL MANDATORY COURSE EXPERIMENTS
              </div>
            </div>
          </div>
          <button className="btn-brass" style={{ width: '32px', height: '32px', padding: 0 }} onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        {/* Preset List */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
          {scenarios.map((sc) => (
            <div
              key={sc.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.9rem 1.2rem',
                border: '1px solid var(--border-ink)',
                borderRadius: '6px',
                background: 'var(--surface-inset)',
                gap: '1rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.8rem', flex: 1 }}>
                <div style={{ marginTop: '2px' }}>{sc.icon}</div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.88rem' }}>{sc.title}</span>
                    <span
                      style={{
                        fontSize: '0.64rem',
                        fontFamily: 'var(--font-mono)',
                        fontWeight: 700,
                        padding: '0.15rem 0.4rem',
                        borderRadius: '3px',
                        background: 'var(--surface-card)',
                        border: '1px solid var(--border-brass)',
                        color: 'var(--accent-brass)',
                      }}
                    >
                      {sc.badge}
                    </span>
                  </div>
                  <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', lineHeight: 1.35 }}>
                    {sc.description}
                  </p>
                </div>
              </div>

              <button
                className="btn-brass btn-brass-primary"
                onClick={() => {
                  onLaunchScenario(sc.id, sc.recommendedProtocol);
                  onClose();
                }}
              >
                <Play size={13} />
                Launch Scenario
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
