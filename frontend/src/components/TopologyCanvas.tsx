import React, { useRef, useEffect, useState } from 'react';
import type { TopologyData, PacketCourier } from '../types';

interface TopologyCanvasProps {
  topology: TopologyData;
  selectedNode: string | null;
  onSelectNode: (nodeId: string | null) => void;
  onMutateLink: (u: string, v: string, up: boolean, cost: number) => void;
  packets: PacketCourier[];
  activePath?: string[];
  loopDetected?: boolean;
  isPhysicsActive?: boolean;
  theme?: 'light' | 'dark';
}

export const TopologyCanvas: React.FC<TopologyCanvasProps> = ({
  topology,
  selectedNode,
  onSelectNode,
  onMutateLink,
  packets,
  activePath = [],
  loopDetected = false,
  isPhysicsActive = false,
  theme = 'light',
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Pan and Zoom viewport state
  const [offset, setOffset] = useState<{ x: number; y: number }>({ x: 80, y: 60 });
  const [zoom, setZoom] = useState<number>(1.0);
  const [isPanning, setIsPanning] = useState<boolean>(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  const [draggedNode, setDraggedNode] = useState<string | null>(null);
  const [nodePositions, setNodePositions] = useState<Record<string, { x: number; y: number }>>({});
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [hoveredLink, setHoveredLink] = useState<{ u: string; v: string } | null>(null);
  const clickRef = useRef<{ clientX: number; clientY: number; node: string | null } | null>(null);

  // Sync node positions from topology prop
  useEffect(() => {
    const initialPositions: Record<string, { x: number; y: number }> = {};
    for (const [id, coord] of Object.entries(topology.nodes)) {
      initialPositions[id] = { ...coord };
    }
    setNodePositions(initialPositions);
  }, [topology.name, topology.nodes]);

  // Force-directed physics step
  useEffect(() => {
    if (!isPhysicsActive) return;
    let animId: number;

    const stepPhysics = () => {
      setNodePositions((prev) => {
        const next = { ...prev };
        const nodeIds = Object.keys(next);
        const kRepulsion = 4000;
        const kSpring = 0.04;
        const targetLen = 140;

        // Repulsion
        for (let i = 0; i < nodeIds.length; i++) {
          for (let j = i + 1; j < nodeIds.length; j++) {
            const u = nodeIds[i];
            const v = nodeIds[j];
            const dx = next[u].x - next[v].x;
            const dy = next[u].y - next[v].y;
            const distSq = Math.max(25, dx * dx + dy * dy);
            const dist = Math.sqrt(distSq);
            const force = kRepulsion / distSq;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;

            if (u !== draggedNode) {
              next[u].x += fx;
              next[u].y += fy;
            }
            if (v !== draggedNode) {
              next[v].x -= fx;
              next[v].y -= fy;
            }
          }
        }

        // Spring attraction along links
        for (const link of topology.links) {
          const u = link.source;
          const v = link.target;
          if (!next[u] || !next[v]) continue;

          const dx = next[v].x - next[u].x;
          const dy = next[v].y - next[u].y;
          const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
          const displacement = dist - targetLen;
          const force = kSpring * displacement;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;

          if (u !== draggedNode) {
            next[u].x += fx;
            next[u].y += fy;
          }
          if (v !== draggedNode) {
            next[v].x -= fx;
            next[v].y -= fy;
          }
        }

        return next;
      });

      animId = requestAnimationFrame(stepPhysics);
    };

    animId = requestAnimationFrame(stepPhysics);
    return () => cancelAnimationFrame(animId);
  }, [isPhysicsActive, draggedNode, topology.links]);

  // Canvas drawing loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;

    const render = () => {
      // Resize to container size
      if (containerRef.current) {
        const { clientWidth, clientHeight } = containerRef.current;
        if (canvas.width !== clientWidth || canvas.height !== clientHeight) {
          canvas.width = clientWidth;
          canvas.height = clientHeight;
        }
      }

      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      ctx.save();
      ctx.translate(offset.x, offset.y);
      ctx.scale(zoom, zoom);

      const isDark = theme === 'dark';
      const inkColor = isDark ? '#E0E1DD' : '#22201D';
      const brassColor = isDark ? '#E0A96D' : '#B87333';
      const parchmentBg = isDark ? '#142436' : '#FCFAF6';

      // 1. Draw Subtle Compass Rose Watermark in center-right
      ctx.save();
      ctx.translate(550, 300);
      ctx.strokeStyle = isDark ? 'rgba(224, 225, 221, 0.05)' : 'rgba(184, 115, 51, 0.08)';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(0, 0, 160, 0, Math.PI * 2);
      ctx.arc(0, 0, 120, 0, Math.PI * 2);
      ctx.arc(0, 0, 60, 0, Math.PI * 2);
      ctx.stroke();

      for (let deg = 0; deg < 360; deg += 45) {
        const rad = (deg * Math.PI) / 180;
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(Math.cos(rad) * 160, Math.sin(rad) * 160);
        ctx.stroke();
      }
      ctx.restore();

      // 2. Draw Links
      for (const link of topology.links) {
        const p1 = nodePositions[link.source];
        const p2 = nodePositions[link.target];
        if (!p1 || !p2) continue;

        const isHovered =
          hoveredLink &&
          ((hoveredLink.u === link.source && hoveredLink.v === link.target) ||
            (hoveredLink.u === link.target && hoveredLink.v === link.source));

        const isPathEdge =
          activePath.length > 1 &&
          activePath.some((node, idx) => {
            if (idx >= activePath.length - 1) return false;
            const next = activePath[idx + 1];
            return (
              (node === link.source && next === link.target) ||
              (node === link.target && next === link.source)
            );
          });

        ctx.save();

        if (!link.is_up) {
          // Severed / Down Link Visual
          ctx.strokeStyle = isDark ? '#EF476F' : '#B92D2B';
          ctx.lineWidth = isHovered ? 3 : 2;
          ctx.setLineDash([6, 6]);
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.stroke();

          // Draw severed 'X' icon at link midpoint
          const midX = (p1.x + p2.x) / 2;
          const midY = (p1.y + p2.y) / 2;
          ctx.setLineDash([]);
          ctx.fillStyle = isDark ? '#EF476F' : '#B92D2B';
          ctx.beginPath();
          ctx.arc(midX, midY, 11, 0, Math.PI * 2);
          ctx.fill();

          ctx.strokeStyle = '#FFFFFF';
          ctx.lineWidth = 2.5;
          ctx.beginPath();
          ctx.moveTo(midX - 5, midY - 5);
          ctx.lineTo(midX + 5, midY + 5);
          ctx.moveTo(midX + 5, midY - 5);
          ctx.lineTo(midX - 5, midY + 5);
          ctx.stroke();
        } else {
          // Normal Operational Link
          if (isPathEdge) {
            // Golden Quill Path Highlight
            ctx.strokeStyle = loopDetected ? (isDark ? '#EF476F' : '#B92D2B') : '#FFB703';
            ctx.lineWidth = 5;
            ctx.shadowColor = loopDetected ? '#EF476F' : '#FFB703';
            ctx.shadowBlur = 10;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
            ctx.shadowBlur = 0;
          }

          ctx.strokeStyle = isHovered ? brassColor : isDark ? 'rgba(224, 225, 221, 0.45)' : 'rgba(34, 32, 29, 0.35)';
          ctx.lineWidth = isHovered ? 2.5 : 1.5;
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.stroke();

          // Link metric pill badge at midpoint
          const midX = (p1.x + p2.x) / 2;
          const midY = (p1.y + p2.y) / 2;
          const pillText = `c:${link.cost}`;

          ctx.fillStyle = parchmentBg;
          ctx.strokeStyle = brassColor;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.roundRect(midX - 16, midY - 9, 32, 18, 4);
          ctx.fill();
          ctx.stroke();

          ctx.fillStyle = inkColor;
          ctx.font = '600 10px JetBrains Mono';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(pillText, midX, midY + 1);
        }

        ctx.restore();
      }

      // 3. Draw Traveling Packet Couriers
      for (const pkt of packets) {
        const p1 = nodePositions[pkt.src];
        const p2 = nodePositions[pkt.dst];
        if (!p1 || !p2) continue;

        const curX = p1.x + (p2.x - p1.x) * pkt.progress;
        const curY = p1.y + (p2.y - p1.y) * pkt.progress;

        ctx.save();
        const isProbe = pkt.payloadType === 'probe';
        ctx.fillStyle = isProbe
          ? '#E0A96D'
          : pkt.protocol.includes('dv')
          ? '#C87533'
          : pkt.protocol.includes('ls')
          ? '#3D8B7A'
          : pkt.protocol.includes('bgp')
          ? '#2A5298'
          : '#D9822B';

        ctx.shadowColor = ctx.fillStyle;
        ctx.shadowBlur = isProbe ? 14 : 9;
        ctx.beginPath();
        ctx.arc(curX, curY, isProbe ? 6.5 : 5, 0, Math.PI * 2);
        ctx.fill();

        // Subtle outer pulse ring
        ctx.strokeStyle = ctx.fillStyle;
        ctx.lineWidth = isProbe ? 2 : 1.2;
        ctx.beginPath();
        ctx.arc(curX, curY, isProbe ? 11 : 8, 0, Math.PI * 2);
        ctx.stroke();

        if (isProbe) {
          // Trailing motion spark for live probe packet
          const sparkP = Math.max(0, pkt.progress - 0.12);
          const sx = p1.x + (p2.x - p1.x) * sparkP;
          const sy = p1.y + (p2.y - p1.y) * sparkP;
          ctx.beginPath();
          ctx.arc(sx, sy, 3.5, 0, Math.PI * 2);
          ctx.fillStyle = 'rgba(224, 169, 109, 0.6)';
          ctx.fill();
        }

        ctx.restore();
      }

      // 4. Draw Nodes (Antique Sextant / Compass Dial Dialect)
      for (const [id, coord] of Object.entries(nodePositions)) {
        const isSelected = selectedNode === id;
        const isHovered = hoveredNode === id;
        const isPathNode = activePath.includes(id);

        ctx.save();
        ctx.translate(coord.x, coord.y);

        // Flap / Loop Warning Halo
        if (loopDetected && isPathNode) {
          ctx.strokeStyle = 'rgba(239, 71, 111, 0.7)';
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.arc(0, 0, 32, 0, Math.PI * 2);
          ctx.stroke();
        } else if (isSelected) {
          ctx.strokeStyle = brassColor;
          ctx.lineWidth = 2.5;
          ctx.setLineDash([3, 3]);
          ctx.beginPath();
          ctx.arc(0, 0, 30, 0, Math.PI * 2);
          ctx.stroke();
          ctx.setLineDash([]);
        }

        // Outer Brass Ring
        ctx.fillStyle = parchmentBg;
        ctx.strokeStyle = isSelected ? brassColor : isHovered ? brassColor : inkColor;
        ctx.lineWidth = isSelected ? 3 : 2;
        ctx.shadowColor = isDark ? 'rgba(0,0,0,0.5)' : 'rgba(35, 25, 15, 0.12)';
        ctx.shadowBlur = isSelected ? 12 : 6;

        ctx.beginPath();
        ctx.arc(0, 0, 22, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.shadowBlur = 0;

        // Inner Compass Compass Dial Ring
        ctx.strokeStyle = isDark ? 'rgba(224, 225, 221, 0.15)' : 'rgba(34, 32, 29, 0.15)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(0, 0, 17, 0, Math.PI * 2);
        ctx.stroke();

        // Node ID Label
        ctx.fillStyle = inkColor;
        ctx.font = '700 12px Cinzel, Outfit, serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(id, 0, 0);

        // AS Number Badge if present
        const nodeInfo = topology.nodes[id];
        if (nodeInfo && nodeInfo.as_number) {
          ctx.fillStyle = brassColor;
          ctx.font = '600 9px JetBrains Mono';
          ctx.fillText(`AS${nodeInfo.as_number}`, 0, 32);
        }

        ctx.restore();
      }

      ctx.restore();

      // 5. Draw Minimap in bottom-left corner
      const mmWidth = 140;
      const mmHeight = 100;
      const mmX = 20;
      const mmY = h - mmHeight - 20;

      ctx.save();
      ctx.fillStyle = isDark ? 'rgba(20, 36, 54, 0.85)' : 'rgba(252, 250, 246, 0.85)';
      ctx.strokeStyle = brassColor;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(mmX, mmY, mmWidth, mmHeight, 4);
      ctx.fill();
      ctx.stroke();

      // Draw mini nodes
      const allCoords = Object.values(nodePositions);
      if (allCoords.length > 0) {
        const minX = Math.min(...allCoords.map((c) => c.x));
        const maxX = Math.max(...allCoords.map((c) => c.x)) + 1;
        const minY = Math.min(...allCoords.map((c) => c.y));
        const maxY = Math.max(...allCoords.map((c) => c.y)) + 1;

        const scaleX = (mmWidth - 24) / (maxX - minX || 1);
        const scaleY = (mmHeight - 24) / (maxY - minY || 1);
        const mmScale = Math.min(scaleX, scaleY);

        ctx.fillStyle = inkColor;
        for (const coord of allCoords) {
          const nx = mmX + 12 + (coord.x - minX) * mmScale;
          const ny = mmY + 12 + (coord.y - minY) * mmScale;
          ctx.beginPath();
          ctx.arc(nx, ny, 2.5, 0, Math.PI * 2);
          ctx.fill();
        }

        // Viewport rectangle in minimap
        const vpX = mmX + 12 + (-offset.x / zoom - minX) * mmScale;
        const vpY = mmY + 12 + (-offset.y / zoom - minY) * mmScale;
        const vpW = (w / zoom) * mmScale;
        const vpH = (h / zoom) * mmScale;

        ctx.strokeStyle = brassColor;
        ctx.lineWidth = 1;
        ctx.strokeRect(
          Math.max(mmX, vpX),
          Math.max(mmY, vpY),
          Math.min(mmWidth - 4, vpW),
          Math.min(mmHeight - 4, vpH)
        );
      }

      ctx.fillStyle = brassColor;
      ctx.font = '700 8px Outfit';
      ctx.fillText('MINIMAP', mmX + 8, mmY + 12);
      ctx.restore();

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [
    topology,
    nodePositions,
    selectedNode,
    hoveredNode,
    hoveredLink,
    offset,
    zoom,
    packets,
    activePath,
    loopDetected,
    theme,
  ]);

  // Coordinate conversion helper
  const getSimCoords = (clientX: number, clientY: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const x = (clientX - rect.left - offset.x) / zoom;
    const y = (clientY - rect.top - offset.y) / zoom;
    return { x, y };
  };

  // Find node under cursor with generous hit radius
  const findNodeAt = (simX: number, simY: number): string | null => {
    for (const [id, coord] of Object.entries(nodePositions)) {
      const dx = simX - coord.x;
      const dy = simY - coord.y;
      if (Math.sqrt(dx * dx + dy * dy) <= 32) {
        return id;
      }
    }
    return null;
  };

  // Find link under cursor
  const findLinkAt = (simX: number, simY: number): { u: string; v: string } | null => {
    for (const link of topology.links) {
      const p1 = nodePositions[link.source];
      const p2 = nodePositions[link.target];
      if (!p1 || !p2) continue;

      // Distance from point to segment
      const dx = p2.x - p1.x;
      const dy = p2.y - p1.y;
      const lenSq = dx * dx + dy * dy;
      if (lenSq === 0) continue;

      const t = Math.max(0, Math.min(1, ((simX - p1.x) * dx + (simY - p1.y) * dy) / lenSq));
      const projX = p1.x + t * dx;
      const projY = p1.y + t * dy;
      const dist = Math.sqrt((simX - projX) ** 2 + (simY - projY) ** 2);

      if (dist <= 14) {
        return { u: link.source, v: link.target };
      }
    }
    return null;
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const { x, y } = getSimCoords(e.clientX, e.clientY);
    const clickedNode = findNodeAt(x, y);

    clickRef.current = { clientX: e.clientX, clientY: e.clientY, node: clickedNode };

    if (clickedNode) {
      setDraggedNode(clickedNode);
      onSelectNode(clickedNode);
    } else {
      const clickedLink = findLinkAt(x, y);
      if (clickedLink) {
        // Toggle link state on click
        const lnk = topology.links.find(
          (l) =>
            (l.source === clickedLink.u && l.target === clickedLink.v) ||
            (l.source === clickedLink.v && l.target === clickedLink.u)
        );
        if (lnk) {
          onMutateLink(lnk.source, lnk.target, !lnk.is_up, lnk.cost);
        }
      } else {
        // Background click: pan canvas (do not deselect immediately on mousedown)
        setIsPanning(true);
        setPanStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
      }
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (isPanning) {
      setOffset({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      });
      return;
    }

    const { x, y } = getSimCoords(e.clientX, e.clientY);

    if (draggedNode) {
      setNodePositions((prev) => ({
        ...prev,
        [draggedNode]: { x, y },
      }));
      return;
    }

    // Update hover indicators
    const node = findNodeAt(x, y);
    setHoveredNode(node);
    if (!node) {
      const link = findLinkAt(x, y);
      setHoveredLink(link);
    } else {
      setHoveredLink(null);
    }
  };

  const handleMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsPanning(false);
    setDraggedNode(null);

    // If mouse didn't drag (< 6px), treat as clean click
    if (clickRef.current) {
      const dist = Math.hypot(
        e.clientX - clickRef.current.clientX,
        e.clientY - clickRef.current.clientY
      );
      if (dist < 6) {
        if (clickRef.current.node) {
          onSelectNode(clickRef.current.node);
        } else {
          const { x, y } = getSimCoords(e.clientX, e.clientY);
          const node = findNodeAt(x, y);
          if (node) {
            onSelectNode(node);
          } else if (!findLinkAt(x, y)) {
            // Only deselect when explicitly clicking empty canvas
            onSelectNode(null);
          }
        }
      }
      clickRef.current = null;
    }
  };

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    const newZoom = Math.min(3.0, Math.max(0.3, zoom * zoomFactor));

    // Zoom toward mouse position
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    setOffset({
      x: mouseX - (mouseX - offset.x) * (newZoom / zoom),
      y: mouseY - (mouseY - offset.y) * (newZoom / zoom),
    });
    setZoom(newZoom);
  };

  return (
    <div
      ref={containerRef}
      className="drafting-canvas-bg"
      style={{
        width: '100%',
        height: '100%',
        position: 'relative',
        overflow: 'hidden',
        cursor: isPanning ? 'grabbing' : draggedNode ? 'grabbing' : hoveredNode ? 'pointer' : 'default',
      }}
    >
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onWheel={handleWheel}
        style={{ display: 'block', width: '100%', height: '100%' }}
      />

      {/* Floating Canvas Zoom Controls */}
      <div
        style={{
          position: 'absolute',
          top: '16px',
          right: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          background: 'var(--surface-card)',
          border: '1px solid var(--border-brass)',
          borderRadius: '4px',
          padding: '4px',
          boxShadow: 'var(--shadow-md)',
        }}
      >
        <button
          className="btn-brass"
          style={{ width: '32px', height: '32px', padding: 0 }}
          onClick={() => setZoom((z) => Math.min(3.0, z * 1.2))}
          title="Zoom In"
        >
          +
        </button>
        <button
          className="btn-brass"
          style={{ width: '32px', height: '32px', padding: 0 }}
          onClick={() => setZoom((z) => Math.max(0.3, z * 0.8))}
          title="Zoom Out"
        >
          -
        </button>
        <button
          className="btn-brass"
          style={{ width: '32px', height: '32px', padding: 0, fontSize: '0.65rem' }}
          onClick={() => {
            setZoom(1.0);
            setOffset({ x: 80, y: 60 });
          }}
          title="Reset View"
        >
          1:1
        </button>
      </div>
    </div>
  );
};
