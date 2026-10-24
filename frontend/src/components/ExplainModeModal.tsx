import React, { useState } from 'react';
import { X, BookOpen, ChevronRight, ChevronLeft } from 'lucide-react';

interface ExplainModeModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ExplainModeModal: React.FC<ExplainModeModalProps> = ({ isOpen, onClose }) => {
  const [step, setStep] = useState<number>(0);

  if (!isOpen) return null;

  const lessons = [
    {
      title: '1. Distance Vector & The Bellman-Ford Equation',
      subtitle: 'DECENTRALIZED ROUTING VIA LOCAL NEIGHBOR VECTORS',
      content: (
        <div>
          <p style={{ marginBottom: '0.8rem', lineHeight: 1.5 }}>
            Distance Vector protocols (like RIP) are <em>decentralized and iterative</em>. Each node knows only the cost of directly connected links and exchanges its current distance vector with its immediate neighbors.
          </p>
          <div
            style={{
              padding: '0.8rem',
              borderRadius: '4px',
              background: 'var(--surface-inset)',
              border: '1px solid var(--border-brass)',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.82rem',
              marginBottom: '0.8rem',
              textAlign: 'center',
            }}
          >
            D_x(y) = min_v &#123; c(x, v) + D_v(y) &#125;
          </div>
          <p style={{ lineHeight: 1.5 }}>
            Whenever a node receives an update from neighbor <code>v</code>, it recomputes its shortest path to all destinations <code>y</code>. If the metric improves or if the next-hop node changes cost, the update triggers outward propagation.
          </p>
        </div>
      ),
    },
    {
      title: '2. The Count-to-Infinity Flaw & Poison Reverse',
      subtitle: 'HOW TWO-NODE ROUTING LOOPS MULTIPLY METRICS TO INFINITY',
      content: (
        <div>
          <p style={{ marginBottom: '0.8rem', lineHeight: 1.5 }}>
            Consider three nodes <code>A — B — C</code>. If the link between <code>B</code> and <code>C</code> breaks:
          </p>
          <ul style={{ paddingLeft: '1.2rem', marginBottom: '0.8rem', lineHeight: 1.6 }}>
            <li><code>B</code> knows <code>C</code> is down, but <code>A</code> was previously advertising a route to <code>C</code> via <code>B</code> with cost 2.</li>
            <li><code>B</code> mistakenly believes <code>A</code> has an alternate path to <code>C</code>, so <code>B</code> updates its next hop to <code>A</code> with cost 3!</li>
            <li><code>A</code> then updates its cost to 4, <code>B</code> to 5, bouncing upward until hitting infinity (16 in RIP).</li>
          </ul>
          <p style={{ lineHeight: 1.5 }}>
            <strong>Split Horizon with Poison Reverse</strong> solves this: If <code>A</code> routes to <code>C</code> through <code>B</code>, <code>A</code> advertises its distance to <code>C</code> back to <code>B</code> as <strong>infinity (&infin;)</strong>, immediately preventing <code>B</code> from looping back through <code>A</code>.
          </p>
        </div>
      ),
    },
    {
      title: '3. Link State & Dijkstra’s Shortest Path First (OSPF)',
      subtitle: 'GLOBAL TOPOLOGY REPLICATION WITH HEAPQ DIJKSTRA',
      content: (
        <div>
          <p style={{ marginBottom: '0.8rem', lineHeight: 1.5 }}>
            Unlike Distance Vector, Link State protocols (such as OSPF and IS-IS) are based on <em>complete network visibility</em>:
          </p>
          <ul style={{ paddingLeft: '1.2rem', marginBottom: '0.8rem', lineHeight: 1.6 }}>
            <li>Every router generates a <strong>Link State Advertisement (LSA)</strong> describing its active neighbors and link costs.</li>
            <li>LSAs are reliably flooded throughout the entire domain using monotonic sequence numbers.</li>
            <li>Each router builds an identical <strong>Link State Database (LSDB)</strong> representing the complete graph <code>G = (V, E)</code>.</li>
            <li>Each node runs Dijkstra’s algorithm independently using a min-heap priority queue (<code>heapq</code>) to compute the shortest-path tree rooted at itself.</li>
          </ul>
          <p style={{ lineHeight: 1.5 }}>
            This completely eliminates count-to-infinity and allows rapid convergence upon link failures.
          </p>
        </div>
      ),
    },
    {
      title: '4. BGP-Lite & Inter-Domain Policy Routing',
      subtitle: 'PATH VECTORS, AS_PATH LOOP PREVENTION & LOCAL-PREF',
      content: (
        <div>
          <p style={{ marginBottom: '0.8rem', lineHeight: 1.5 }}>
            The Border Gateway Protocol (BGP) is the routing protocol of the global Internet, operating across Autonomous Systems (AS):
          </p>
          <ul style={{ paddingLeft: '1.2rem', marginBottom: '0.8rem', lineHeight: 1.6 }}>
            <li><strong>Path Vector</strong>: BGP advertisements include the entire list of autonomous systems traversed: <code>AS_PATH = [AS100, AS200, AS300]</code>.</li>
            <li><strong>Loop Freedom</strong>: If a router receives an advertisement containing its own AS number in the <code>AS_PATH</code>, it rejects the route immediately!</li>
            <li><strong>Policy Routing (LOCAL_PREF)</strong>: Routes are chosen based on commercial agreements and preference policies rather than raw physical hop count or link cost.</li>
          </ul>
        </div>
      ),
    },
    {
      title: '5. Route Poisoning Attacks & Defense',
      subtitle: 'CYBERSECURITY IN ROUTING PROTOCOLS',
      content: (
        <div>
          <p style={{ marginBottom: '0.8rem', lineHeight: 1.5 }}>
            Traditional routing protocols trust updates from neighbors without verification. A compromised or rogue node can execute a <strong>Route Poisoning Attack</strong> by forging a distance vector claiming cost 1 to a target destination.
          </p>
          <p style={{ marginBottom: '0.8rem', lineHeight: 1.5 }}>
            Neighboring nodes eagerly adopt this forged path, redirecting high-value traffic through the adversary or causing denial of service.
          </p>
          <p style={{ lineHeight: 1.5 }}>
            <strong>Secure Distance Vector</strong> mitigates this by requiring cryptographic link-state consistency validation, bounded rate limits on metric drops, and origin-authenticated route filtering.
          </p>
        </div>
      ),
    },
  ];

  const currentLesson = lessons[step];

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
          width: '680px',
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
            padding: '0.9rem 1.4rem',
            borderBottom: '1px solid var(--border-ink)',
            background: 'var(--surface-inset)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <BookOpen size={18} color="var(--accent-brass)" />
            <div>
              <div style={{ fontWeight: 800, fontFamily: 'var(--font-heading)', fontSize: '1rem' }}>
                {currentLesson.title}
              </div>
              <div style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                {currentLesson.subtitle}
              </div>
            </div>
          </div>
          <button className="btn-brass" style={{ width: '30px', height: '30px', padding: 0 }} onClick={onClose}>
            <X size={15} />
          </button>
        </div>

        {/* Lesson Body */}
        <div style={{ padding: '1.6rem', fontSize: '0.84rem', color: 'var(--text-primary)', minHeight: '260px' }}>
          {currentLesson.content}
        </div>

        {/* Footer Navigation */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.8rem 1.4rem',
            borderTop: '1px solid var(--border-ink)',
            background: 'var(--surface-inset)',
          }}
        >
          <button
            className="btn-brass"
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0}
            style={{ opacity: step === 0 ? 0.4 : 1 }}
          >
            <ChevronLeft size={14} />
            Previous
          </button>

          <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            Lesson {step + 1} of {lessons.length}
          </div>

          <button
            className="btn-brass btn-brass-primary"
            onClick={() => {
              if (step < lessons.length - 1) {
                setStep((s) => s + 1);
              } else {
                onClose();
              }
            }}
          >
            {step < lessons.length - 1 ? (
              <>
                Next Lesson
                <ChevronRight size={14} />
              </>
            ) : (
              'Complete Walkthrough'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
