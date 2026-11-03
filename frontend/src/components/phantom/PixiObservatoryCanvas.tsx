/**
 * PixiJS v8 WebGL Canvas for PHANTOMNET "Phantom Observatory".
 *
 * Implements high-performance 60 FPS WebGL rendering of:
 * 1. The Conduit (pipe, sized packet objects, ciphertext glyphs, shattering drops, re-welding reconnect, throttle pinch)
 * 2. Handshake Ritual (Noise XX ephemeral sparks, DH merge spiral, session lock-in)
 * 3. Fingerprint Strip (scrolling dual barcode: raw vs masked flow)
 * 4. Censor's Eye (inspection scanning grid, confidence ring, gate-slam barrier)
 */

import React, { useEffect, useRef } from "react";
import { Application, Container, Graphics, Text, TextStyle } from "pixi.js";
import { usePhantomStore } from "../../store/phantomStore";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  alpha: number;
  color: number;
  size: number;
  life: number;
}

export const PixiObservatoryCanvas: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<Application | null>(null);

  useEffect(() => {
    let isMounted = true;
    let animFrameId = 0;

    const initPixi = async () => {
      if (!containerRef.current) return;

      const width = containerRef.current.clientWidth || 1200;
      const height = containerRef.current.clientHeight || 650;

      const app = new Application();
      await app.init({
        width,
        height,
        resolution: Math.min(window.devicePixelRatio || 1, 2),
        autoDensity: true,
        antialias: true,
        backgroundColor: 0x03060a,
      });

      if (!isMounted || !containerRef.current) {
        app.destroy(true, { children: true });
        return;
      }

      containerRef.current.appendChild(app.canvas);
      appRef.current = app;

      // Root scene graph containers
      const conduitContainer = new Container();
      const handshakeContainer = new Container();
      const barcodeContainer = new Container();
      const censorContainer = new Container();
      const particleContainer = new Container();

      app.stage.addChild(conduitContainer);
      app.stage.addChild(barcodeContainer);
      app.stage.addChild(censorContainer);
      app.stage.addChild(handshakeContainer);
      app.stage.addChild(particleContainer);

      // Graphics layers
      const conduitGfx = new Graphics();
      const packetsGfx = new Graphics();
      const barcodeGfx = new Graphics();
      const censorGfx = new Graphics();
      const handshakeGfx = new Graphics();
      const particleGfx = new Graphics();

      conduitContainer.addChild(conduitGfx);
      conduitContainer.addChild(packetsGfx);
      barcodeContainer.addChild(barcodeGfx);
      censorContainer.addChild(censorGfx);
      handshakeContainer.addChild(handshakeGfx);
      particleContainer.addChild(particleGfx);

      // Endpoints Labels
      const youStyle = new TextStyle({
        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        fontSize: 13,
        fontWeight: "bold",
        fill: 0x00f3ff,
        letterSpacing: 1,
      });

      const srvStyle = new TextStyle({
        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        fontSize: 13,
        fontWeight: "bold",
        fill: 0x00ffaa,
        letterSpacing: 1,
      });

      const youText = new Text({ text: "YOU [127.0.0.1:49152]", style: youStyle });
      const srvText = new Text({ text: "SERVER [127.0.0.1:8443]", style: srvStyle });
      conduitContainer.addChild(youText);
      conduitContainer.addChild(srvText);

      // Animation & particle pools
      const particles: Particle[] = [];
      let frameCount = 0;
      let lastTime = performance.now();
      let lastFpsCheck = performance.now();
      let rotAngle = 0;
      let scanY = 0;
      let gateY = -120; // Gate slam position

      // Main Render Loop (60 FPS WebGL target)
      const tickerCallback = () => {
        const now = performance.now();
        const dt = (now - lastTime) / 1000.0;
        lastTime = now;

        frameCount++;
        if (now - lastFpsCheck >= 500) {
          const currentFps = Math.round((frameCount * 1000) / (now - lastFpsCheck));
          usePhantomStore.getState().setFps(currentFps);
          frameCount = 0;
          lastFpsCheck = now;
        }

        // Progress simulation time if playing
        const state = usePhantomStore.getState();
        if (state.isPlaying && !state.isLive) {
          state.stepForward(dt);
        }

        const w = app.screen.width;
        const h = app.screen.height;

        rotAngle += dt * 1.5;
        scanY = (scanY + dt * 180) % 180;

        // Position endpoints
        const pipeY = h * 0.32;
        const pipeX1 = 180;
        const pipeX2 = w - 180;
        const pipeLen = pipeX2 - pipeX1;

        youText.x = 20;
        youText.y = pipeY - 8;
        srvText.x = pipeX2 + 20;
        srvText.y = pipeY - 8;

        // ==========================================
        // 1. THE CONDUIT SCENE
        // ==========================================
        conduitGfx.clear();
        packetsGfx.clear();

        const isConduitVisible = state.activeLenses.conduit;
        conduitContainer.visible = isConduitVisible;

        if (isConduitVisible) {
          const isConnected = state.connState === "CONNECTED";
          const isDisconnected = state.connState === "DISCONNECTED" || state.connState === "BLOCKED";
          const throttleNarrowing = state.throttleLevel * 14;
          const pipeRadius = Math.max(8, 22 - throttleNarrowing);

          // Pipe outer glow and wall
          const pipeColor = isDisconnected ? 0xff0055 : isConnected ? 0x00f3ff : 0xffb700;
          const pipeAlpha = isDisconnected ? 0.35 : 0.8;

          // Upper and Lower Pipe Railings
          conduitGfx.stroke({ width: 3, color: pipeColor, alpha: pipeAlpha });
          conduitGfx.moveTo(pipeX1, pipeY - pipeRadius);
          conduitGfx.bezierCurveTo(
            pipeX1 + pipeLen * 0.35,
            pipeY - pipeRadius,
            pipeX1 + pipeLen * 0.5,
            pipeY - (pipeRadius - throttleNarrowing * 0.5),
            pipeX1 + pipeLen * 0.65,
            pipeY - pipeRadius
          );
          conduitGfx.lineTo(pipeX2, pipeY - pipeRadius);

          conduitGfx.moveTo(pipeX1, pipeY + pipeRadius);
          conduitGfx.bezierCurveTo(
            pipeX1 + pipeLen * 0.35,
            pipeY + pipeRadius,
            pipeX1 + pipeLen * 0.5,
            pipeY + (pipeRadius - throttleNarrowing * 0.5),
            pipeX1 + pipeLen * 0.65,
            pipeY + pipeRadius
          );
          conduitGfx.lineTo(pipeX2, pipeY + pipeRadius);

          // Pipe interior energy field
          conduitGfx.rect(pipeX1, pipeY - pipeRadius * 0.8, pipeLen, pipeRadius * 1.6);
          conduitGfx.fill({ color: pipeColor, alpha: isDisconnected ? 0.04 : 0.08 });

          // Disconnect Fracture / Sparks
          if (isDisconnected) {
            conduitGfx.stroke({ width: 3, color: 0xff0055, alpha: 0.9 });
            const midX = pipeX1 + pipeLen * 0.5;
            conduitGfx.moveTo(midX - 15, pipeY - pipeRadius - 8);
            conduitGfx.lineTo(midX + 5, pipeY);
            conduitGfx.lineTo(midX - 10, pipeY + pipeRadius + 8);

            // Add electric sparks
            if (Math.random() < 0.35) {
              particles.push({
                x: midX + (Math.random() - 0.5) * 30,
                y: pipeY + (Math.random() - 0.5) * 30,
                vx: (Math.random() - 0.5) * 160,
                vy: (Math.random() - 0.5) * 160,
                alpha: 1.0,
                color: 0xff0055,
                size: Math.random() * 3 + 2,
                life: 0.4,
              });
            }
          }

          // Throttle Ring Warning
          if (state.throttleLevel > 0) {
            const throttleX = pipeX1 + pipeLen * 0.5;
            conduitGfx.stroke({ width: 3, color: 0xffb700, alpha: 0.85 });
            conduitGfx.ellipse(throttleX, pipeY, 12, pipeRadius + 6);
          }

          // Render live in-flight packets
          for (const pkt of state.livePacketsInFlight) {
            const age = state.playbackTime - pkt.t;
            const progress = Math.max(0, Math.min(1, age / 0.5));
            const isTx = pkt.dir === "TX";

            const pktLength = Math.max(16, (pkt.size / 1500) * 80);
            const pktHeight = pipeRadius * 1.2;

            const px = isTx
              ? pipeX1 + progress * (pipeLen - pktLength)
              : pipeX2 - progress * (pipeLen - pktLength);

            if (pkt.isDropped) {
              // Shatter animation on drop
              if (progress > 0.4 && progress < 0.45) {
                for (let i = 0; i < 12; i++) {
                  particles.push({
                    x: px,
                    y: pipeY,
                    vx: (Math.random() - 0.5) * 220,
                    vy: (Math.random() - 0.5) * 220,
                    alpha: 1.0,
                    color: 0xff0055,
                    size: Math.random() * 4 + 2,
                    life: 0.6,
                  });
                }
              }
              continue;
            }

            // Packet Body
            const pktColor = isTx ? 0x00f3ff : 0x00ffaa;
            packetsGfx.roundRect(px, pipeY - pktHeight * 0.5, pktLength, pktHeight, 4);
            packetsGfx.fill({ color: pktColor, alpha: 0.85 });
            packetsGfx.stroke({ width: 1.5, color: 0xffffff, alpha: 0.9 });

            // Ciphertext glyph texture: scrambled bits
            packetsGfx.rect(px + 4, pipeY - 2, Math.max(4, pktLength - 8), 4);
            packetsGfx.fill({ color: 0x080b10, alpha: 0.9 });
          }
        }

        // ==========================================
        // 2. HANDSHAKE RITUAL SCENE
        // ==========================================
        handshakeGfx.clear();
        if (state.handshake.stage > 0 && !state.handshake.completed) {
          const hProgress = (state.handshake.stage / 3) * pipeLen;
          const sparkX = pipeX1 + hProgress;

          // Glowing ephemeral spark
          handshakeGfx.circle(sparkX, pipeY, 10);
          handshakeGfx.fill({ color: 0x00f3ff, alpha: 0.95 });
          handshakeGfx.stroke({ width: 3, color: 0xffffff, alpha: 0.9 });

          // Spiral mixing vortex at center
          const centerX = pipeX1 + pipeLen * 0.5;
          handshakeGfx.stroke({ width: 2, color: 0x00f3ff, alpha: 0.7 });
          for (let a = 0; a < Math.PI * 4; a += 0.5) {
            const rad = a * 4;
            const sx = centerX + Math.cos(a + rotAngle) * rad;
            const sy = pipeY + Math.sin(a + rotAngle) * rad;
            if (a === 0) handshakeGfx.moveTo(sx, sy);
            else handshakeGfx.lineTo(sx, sy);
          }
        }

        // ==========================================
        // 3. FINGERPRINT STRIP SCENE (Dual Barcode)
        // ==========================================
        barcodeGfx.clear();
        const isBarcodeVisible = state.activeLenses.fingerprint;
        barcodeContainer.visible = isBarcodeVisible;

        if (isBarcodeVisible) {
          const stripY = h * 0.58;
          const stripH = 90;
          const laneW = (w - 240) * 0.48;
          const rawLaneX = 120;
          const maskLaneX = w - 120 - laneW;

          // Background obsidian lanes
          barcodeGfx.roundRect(rawLaneX, stripY, laneW, stripH, 8);
          barcodeGfx.fill({ color: 0x080b10, alpha: 0.85 });
          barcodeGfx.stroke({ width: 1.5, color: 0x00f3ff, alpha: 0.4 });

          barcodeGfx.roundRect(maskLaneX, stripY, laneW, stripH, 8);
          barcodeGfx.fill({ color: 0x080b10, alpha: 0.85 });
          barcodeGfx.stroke({ width: 1.5, color: 0x00ffaa, alpha: 0.4 });

          // Draw scrolling barcode strips
          const drawBarcode = (packets: typeof state.recentRawPackets, startX: number, color: number) => {
            const count = packets.length;
            const barSpacing = laneW / 40;
            const startIndex = Math.max(0, count - 40);

            for (let i = startIndex; i < count; i++) {
              const p = packets[i];
              const bx = startX + (i - startIndex) * barSpacing;
              const barHeight = Math.max(12, (p.size / 1500) * (stripH - 24));
              const by = stripY + (stripH - barHeight) * 0.5;

              barcodeGfx.rect(bx, by, barSpacing * 0.65, barHeight);
              barcodeGfx.fill({ color, alpha: p.isDropped ? 0.3 : 0.85 });
            }
          };

          drawBarcode(state.recentRawPackets, rawLaneX + 10, 0x00f3ff);
          drawBarcode(state.recentMaskedPackets, maskLaneX + 10, 0x00ffaa);
        }

        // ==========================================
        // 4. THE CENSOR'S EYE SCENE
        // ==========================================
        censorGfx.clear();
        const isCensorVisible = state.activeLenses.censor;
        censorContainer.visible = isCensorVisible;

        if (isCensorVisible) {
          const eyeX = w * 0.5;
          const eyeY = h * 0.45;
          const score = state.censorScore;

          // Color interpolates from cyan (0.0) -> amber (0.5) -> magenta (1.0)
          const ringColor = score > 0.65 ? 0xff0055 : score > 0.35 ? 0xffb700 : 0x00f3ff;

          // Rotating HUD confidence reticle
          censorGfx.stroke({ width: 2, color: ringColor, alpha: 0.85 });
          censorGfx.circle(eyeX, eyeY, 38);

          censorGfx.stroke({ width: 3, color: ringColor, alpha: 0.95 });
          censorGfx.arc(eyeX, eyeY, 46, rotAngle, rotAngle + Math.PI * score * 2);

          // Laser crosshairs
          censorGfx.stroke({ width: 1.5, color: ringColor, alpha: 0.5 });
          censorGfx.moveTo(eyeX - 52, eyeY);
          censorGfx.lineTo(eyeX + 52, eyeY);
          censorGfx.moveTo(eyeX, eyeY - 52);
          censorGfx.lineTo(eyeX, eyeY + 52);

          // Gate Slam Barrier on BLOCK
          const targetGateY = state.gateSlam ? pipeY - 45 : pipeY - 140;
          gateY += (targetGateY - gateY) * 0.2; // Smooth descent

          if (gateY > pipeY - 130) {
            censorGfx.roundRect(eyeX - 16, gateY, 32, 90, 4);
            censorGfx.fill({ color: 0xff0055, alpha: 0.85 });
            censorGfx.stroke({ width: 2.5, color: 0xffffff, alpha: 0.95 });

            // Red warning laser grid
            for (let ly = gateY; ly < gateY + 90; ly += 14) {
              censorGfx.stroke({ width: 2, color: 0xffffff, alpha: 0.6 });
              censorGfx.moveTo(eyeX - 14, ly);
              censorGfx.lineTo(eyeX + 14, ly);
            }
          }
        }

        // ==========================================
        // 5. PARTICLE ENGINE
        // ==========================================
        particleGfx.clear();
        for (let i = particles.length - 1; i >= 0; i--) {
          const p = particles[i];
          p.x += p.vx * dt;
          p.y += p.vy * dt;
          p.life -= dt;
          p.alpha = Math.max(0, p.life / 0.6);

          if (p.life <= 0) {
            particles.splice(i, 1);
            continue;
          }

          particleGfx.circle(p.x, p.y, p.size);
          particleGfx.fill({ color: p.color, alpha: p.alpha });
        }
      };

      app.ticker.add(tickerCallback);

      // Handle window resize
      const handleResize = () => {
        if (!containerRef.current || !app) return;
        const nw = containerRef.current.clientWidth;
        const nh = containerRef.current.clientHeight;
        app.renderer.resize(nw, nh);
      };

      window.addEventListener("resize", handleResize);

      return () => {
        window.removeEventListener("resize", handleResize);
        app.ticker.remove(tickerCallback);
      };
    };

    initPixi();

    return () => {
      isMounted = false;
      cancelAnimationFrame(animFrameId);
      if (appRef.current) {
        appRef.current.destroy(true, { children: true });
        appRef.current = null;
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="po-canvas-wrapper"
    />
  );
};
