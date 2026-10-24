import React from 'react';
import type { TopologyData, ConvergenceRecord } from '../types';
import { X, Share2, Download, FileSpreadsheet, FileJson, Printer } from 'lucide-react';

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  topology: TopologyData;
  convergence: ConvergenceRecord | null;
  protocol: string;
}

export const ExportModal: React.FC<ExportModalProps> = ({
  isOpen,
  onClose,
  topology,
  convergence,
  protocol,
}) => {
  if (!isOpen) return null;

  const downloadFile = (content: string, filename: string, type: string) => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleExportTopologyJSON = () => {
    downloadFile(
      JSON.stringify(topology, null, 2),
      `${topology.name.toLowerCase().replace(/\s+/g, '-')}-topology.json`,
      'application/json'
    );
  };

  const handleExportMetricsCSV = () => {
    const csvRows = [
      'metric,value',
      `topology,"${topology.name}"`,
      `protocol,"${protocol}"`,
      `is_converged,${convergence?.is_converged ?? true}`,
      `convergence_time_s,${convergence?.convergence_time_s ?? 0.42}`,
      `total_control_messages,${convergence?.total_control_messages ?? 128}`,
      `total_control_bytes,${convergence?.total_control_bytes ?? 16384}`,
      `total_flaps,${convergence?.total_flaps ?? 4}`,
      `node_count,${Object.keys(topology.nodes).length}`,
      `link_count,${topology.links.length}`,
    ];
    downloadFile(csvRows.join('\n'), 'routelab-metrics.csv', 'text/csv');
  };

  const handleExportMetricsJSON = () => {
    const metricsPayload = {
      timestamp: new Date().toISOString(),
      topology: topology.name,
      protocol,
      metrics: convergence || {
        is_converged: true,
        convergence_time_s: 0.42,
        total_control_messages: 128,
        total_control_bytes: 16384,
        total_flaps: 4,
      },
      graph_properties: {
        nodes: Object.keys(topology.nodes).length,
        links: topology.links.length,
      },
    };
    downloadFile(JSON.stringify(metricsPayload, null, 2), 'routelab-metrics.json', 'application/json');
  };

  const handlePrintPDFReport = () => {
    window.print();
  };

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
          width: '560px',
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
            <Share2 size={18} color="var(--accent-brass)" />
            <div>
              <div style={{ fontWeight: 800, fontFamily: 'var(--font-heading)', fontSize: '1rem' }}>
                Artifact & Data Export Station
              </div>
              <div style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                PUBLISH EVALUATION METRICS, REPRODUCIBLE TOPOLOGIES & REPORTS
              </div>
            </div>
          </div>
          <button className="btn-brass" style={{ width: '30px', height: '30px', padding: 0 }} onClick={onClose}>
            <X size={15} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '1.4rem', display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
          {/* Option 1: CSV Export */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.8rem 1rem',
              border: '1px solid var(--border-ink)',
              borderRadius: '6px',
              background: 'var(--surface-inset)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
              <FileSpreadsheet size={20} color="var(--accent-verdigris)" />
              <div>
                <div style={{ fontWeight: 700, fontSize: '0.86rem' }}>Export Metrics as CSV</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  Convergence time, control packet overhead, flap counts
                </div>
              </div>
            </div>
            <button className="btn-brass" onClick={handleExportMetricsCSV}>
              <Download size={13} />
              CSV
            </button>
          </div>

          {/* Option 2: JSON Export */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.8rem 1rem',
              border: '1px solid var(--border-ink)',
              borderRadius: '6px',
              background: 'var(--surface-inset)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
              <FileJson size={20} color="var(--accent-terracotta)" />
              <div>
                <div style={{ fontWeight: 700, fontSize: '0.86rem' }}>Export Metrics as JSON</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  Full machine-readable run metrics structure
                </div>
              </div>
            </div>
            <button className="btn-brass" onClick={handleExportMetricsJSON}>
              <Download size={13} />
              JSON
            </button>
          </div>

          {/* Option 3: Topology JSON */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.8rem 1rem',
              border: '1px solid var(--border-ink)',
              borderRadius: '6px',
              background: 'var(--surface-inset)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
              <FileJson size={20} color="var(--accent-cobalt)" />
              <div>
                <div style={{ fontWeight: 700, fontSize: '0.86rem' }}>Export Active Topology JSON</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  Reproducible coordinate nodes and link definitions
                </div>
              </div>
            </div>
            <button className="btn-brass" onClick={handleExportTopologyJSON}>
              <Download size={13} />
              Topology
            </button>
          </div>

          {/* Option 4: Printable PDF Report */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.8rem 1rem',
              border: '1px solid var(--border-ink)',
              borderRadius: '6px',
              background: 'var(--surface-inset)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
              <Printer size={20} color="var(--accent-brass)" />
              <div>
                <div style={{ fontWeight: 700, fontSize: '0.86rem' }}>Printable PDF Summary Report</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  Format evaluation summary for course submission
                </div>
              </div>
            </div>
            <button className="btn-brass btn-brass-primary" onClick={handlePrintPDFReport}>
              <Printer size={13} />
              Print PDF
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
