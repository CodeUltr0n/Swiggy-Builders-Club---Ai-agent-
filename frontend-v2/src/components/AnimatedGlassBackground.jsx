import React, { useEffect, useRef } from 'react';

/**
 * AnimatedGlassBackground
 * High-performance 60 FPS flowing wave engine behind frosted glass:
 * - Multi-layered continuous harmonic traveling waves
 * - Dynamic tracker nodes riding the wave crests with radiant neon halos
 * - Faint vertical signal guidelines dropping from the nodes
 * - Bottom emerald light pool / ambient glow bleed matching the user's reference image
 * - Deep velvet obsidian background for maximum frosted glass contrast
 */
export default function AnimatedGlassBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId;
    let width = 0;
    let height = 0;
    let time = 0;

    const handleResize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);
    };

    handleResize();
    window.addEventListener('resize', handleResize);

    // Floating micro-particles rising from the emerald glow
    const particles = Array.from({ length: 28 }, () => ({
      x: Math.random() * (width || 1200),
      y: Math.random() * (height || 800),
      radius: Math.random() * 1.8 + 0.8,
      speedY: Math.random() * 0.5 + 0.2,
      speedX: (Math.random() - 0.5) * 0.25,
      alpha: Math.random() * 0.6 + 0.2,
      phase: Math.random() * Math.PI * 2,
    }));

    // Composite harmonic wave equations
    const getWaveY = (x, t, layer) => {
      if (layer === 0) {
        // Hero Foreground Wave (Dynamic, flowing, high energy)
        const freq1 = 0.0032;
        const freq2 = 0.0068;
        const freq3 = 0.0016;
        const base = height * 0.48;
        const y1 = Math.sin(x * freq1 - t * 1.8) * (height * 0.12);
        const y2 = Math.cos(x * freq2 + t * 1.2) * (height * 0.05);
        const y3 = Math.sin(x * freq3 - t * 0.75) * (height * 0.08);
        return base + y1 + y2 + y3;
      } else if (layer === 1) {
        // Mid Wave Layer (Warm secondary rolling wave)
        const freq1 = 0.0026;
        const freq2 = 0.0052;
        const base = height * 0.54;
        const y1 = Math.sin(x * freq1 - t * 1.3 + 1.4) * (height * 0.15);
        const y2 = Math.cos(x * freq2 + t * 0.85) * (height * 0.06);
        return base + y1 + y2;
      } else {
        // Deep Ambient Background Wave
        const freq = 0.0018;
        const base = height * 0.60;
        const y = Math.sin(x * freq - t * 0.9 + 2.8) * (height * 0.16);
        return base + y;
      }
    };

    const render = () => {
      time += 0.016;

      // 1. Deep Obsidian Velvet Base
      ctx.fillStyle = '#030805';
      ctx.fillRect(0, 0, width, height);

      // 2. Subtle Radial Vignette
      const vignette = ctx.createRadialGradient(
        width * 0.5, height * 0.45, 60,
        width * 0.5, height * 0.45, Math.max(width, height) * 0.8
      );
      vignette.addColorStop(0, 'rgba(4, 26, 15, 0.40)');
      vignette.addColorStop(0.65, 'rgba(3, 14, 8, 0.75)');
      vignette.addColorStop(1, 'rgba(1, 4, 2, 0.98)');
      ctx.fillStyle = vignette;
      ctx.fillRect(0, 0, width, height);

      // 3. Bottom Emerald Light Bleed (Glowing under-glass pool)
      const bottomGlow = ctx.createRadialGradient(
        width * 0.5, height * 0.98, 20,
        width * 0.5, height * 0.98, width * 0.65
      );
      const pulseGlow = 0.28 + Math.sin(time * 1.3) * 0.06;
      bottomGlow.addColorStop(0, `rgba(0, 255, 127, ${pulseGlow})`);
      bottomGlow.addColorStop(0.35, `rgba(16, 185, 129, ${pulseGlow * 0.6})`);
      bottomGlow.addColorStop(0.7, `rgba(5, 150, 105, ${pulseGlow * 0.2})`);
      bottomGlow.addColorStop(1, 'transparent');
      ctx.fillStyle = bottomGlow;
      ctx.fillRect(0, height * 0.35, width, height * 0.65);

      const step = Math.max(6, Math.floor(width / 180));

      // 4. Layer 2: Deep Ambient Wave
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(-20, getWaveY(-20, time, 2));
      for (let x = 0; x <= width + 20; x += step * 2) {
        ctx.lineTo(x, getWaveY(x, time, 2));
      }
      ctx.strokeStyle = 'rgba(16, 185, 129, 0.15)';
      ctx.lineWidth = 5;
      ctx.shadowColor = '#10b981';
      ctx.shadowBlur = 25;
      ctx.stroke();
      ctx.restore();

      // 5. Layer 1: Mid Wave with Lush Gradient Fill Below
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(-20, height);
      ctx.lineTo(-20, getWaveY(-20, time, 1));
      for (let x = 0; x <= width + 20; x += step) {
        ctx.lineTo(x, getWaveY(x, time, 1));
      }
      ctx.lineTo(width + 20, height);
      ctx.closePath();

      const waveGrad = ctx.createLinearGradient(0, height * 0.35, 0, height);
      waveGrad.addColorStop(0, 'rgba(0, 255, 127, 0.16)');
      waveGrad.addColorStop(0.4, 'rgba(16, 185, 129, 0.07)');
      waveGrad.addColorStop(1, 'transparent');
      ctx.fillStyle = waveGrad;
      ctx.fill();

      // Mid wave stroke
      ctx.strokeStyle = 'rgba(52, 211, 153, 0.25)';
      ctx.lineWidth = 3;
      ctx.shadowColor = '#00ff7f';
      ctx.shadowBlur = 16;
      ctx.stroke();
      ctx.restore();

      // 6. Layer 0: Hero Flowing Wave (Continuous Neon Emerald)
      const buildHeroWavePath = () => {
        ctx.beginPath();
        ctx.moveTo(-20, getWaveY(-20, time, 0));
        for (let x = 0; x <= width + 20; x += step) {
          ctx.lineTo(x, getWaveY(x, time, 0));
        }
      };

      // Pass A: Broad Diffuse Glow (simulating glass internal dispersion)
      ctx.save();
      buildHeroWavePath();
      ctx.strokeStyle = 'rgba(0, 255, 127, 0.32)';
      ctx.lineWidth = 16;
      ctx.shadowColor = '#00ff7f';
      ctx.shadowBlur = 45;
      ctx.stroke();
      ctx.restore();

      // Pass B: Intense Mid-Core Emerald Glow
      ctx.save();
      buildHeroWavePath();
      ctx.strokeStyle = 'rgba(16, 185, 129, 0.85)';
      ctx.lineWidth = 6;
      ctx.shadowColor = '#00ff7f';
      ctx.shadowBlur = 20;
      ctx.stroke();
      ctx.restore();

      // Pass C: Sharp Crisp Luminous Core
      ctx.save();
      buildHeroWavePath();
      ctx.strokeStyle = '#e6fffa';
      ctx.lineWidth = 2.5;
      ctx.shadowColor = '#ffffff';
      ctx.shadowBlur = 8;
      ctx.stroke();
      ctx.restore();

      // 7. Dynamic Wave Tracking Nodes & Vertical Signal Guidelines
      const nodeFractions = [0.15, 0.32, 0.50, 0.68, 0.85];
      nodeFractions.forEach((fraction, idx) => {
        const nx = width * fraction;
        const ny = getWaveY(nx, time, 0);
        const isApex = idx === 2; // Center hero apex node

        // Vertical faint guideline dropping from node
        ctx.save();
        ctx.beginPath();
        ctx.setLineDash([3, 4]);
        ctx.moveTo(nx, ny + (isApex ? 12 : 8));
        ctx.lineTo(nx, height * 0.88);
        const guideGrad = ctx.createLinearGradient(nx, ny, nx, height * 0.88);
        guideGrad.addColorStop(0, isApex ? 'rgba(0, 255, 127, 0.45)' : 'rgba(52, 211, 153, 0.25)');
        guideGrad.addColorStop(0.5, 'rgba(16, 185, 129, 0.08)');
        guideGrad.addColorStop(1, 'transparent');
        ctx.strokeStyle = guideGrad;
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.restore();

        // Node Glow & Core
        ctx.save();
        const pulse = Math.sin(time * 3 + idx) * (isApex ? 2.2 : 1.2);
        const radius = isApex ? 9 + pulse : 5 + pulse;

        // Outer radiant aura
        const aura = ctx.createRadialGradient(nx, ny, 0, nx, ny, radius * (isApex ? 4.5 : 3.2));
        aura.addColorStop(0, isApex ? 'rgba(0, 255, 127, 0.85)' : 'rgba(52, 211, 153, 0.6)');
        aura.addColorStop(0.4, isApex ? 'rgba(16, 185, 129, 0.35)' : 'rgba(16, 185, 129, 0.2)');
        aura.addColorStop(1, 'transparent');
        ctx.fillStyle = aura;
        ctx.beginPath();
        ctx.arc(nx, ny, radius * (isApex ? 4.5 : 3.2), 0, Math.PI * 2);
        ctx.fill();

        // Node Solid Core
        ctx.beginPath();
        ctx.arc(nx, ny, radius, 0, Math.PI * 2);
        ctx.fillStyle = isApex ? '#ffffff' : '#d1fae5';
        ctx.shadowColor = '#00ff7f';
        ctx.shadowBlur = isApex ? 22 : 12;
        ctx.fill();

        // Crisp White Rim
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = isApex ? 2 : 1.5;
        ctx.stroke();
        ctx.restore();
      });

      // 8. Floating Micro-particles
      ctx.save();
      particles.forEach((p) => {
        p.y -= p.speedY;
        p.x += p.speedX;
        if (p.y < -10) {
          p.y = height + 10;
          p.x = Math.random() * width;
        }
        if (p.x < -10) p.x = width + 10;
        if (p.x > width + 10) p.x = -10;

        const currentAlpha = p.alpha * (0.6 + Math.sin(time * 2 + p.phase) * 0.4);
        ctx.fillStyle = `rgba(110, 231, 183, ${currentAlpha})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.shadowColor = '#00ff7f';
        ctx.shadowBlur = 6;
        ctx.fill();
      });
      ctx.restore();

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    const handleVisibilityChange = () => {
      if (document.hidden) {
        cancelAnimationFrame(animationFrameId);
      } else {
        animationFrameId = requestAnimationFrame(render);
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 0,
        display: 'block',
      }}
    />
  );
}
