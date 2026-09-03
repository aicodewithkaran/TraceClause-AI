'use client';

import React, { useEffect, useRef } from 'react';
import { useTheme } from '@/context/ThemeContext';

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  baseAlpha: number;
  color: string;
}

export const NetworkBackgroundCanvas: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;

    const updateDimensions = () => {
      if (!canvas) return;
      const dpr = window.devicePixelRatio || 1;
      const displayWidth = window.innerWidth;
      const displayHeight = window.innerHeight;

      // Set actual render resolution scaled by devicePixelRatio for crisp non-blurry rendering
      canvas.width = Math.floor(displayWidth * dpr);
      canvas.height = Math.floor(displayHeight * dpr);

      // Scale context to ensure correct drawing units
      ctx.scale(dpr, dpr);
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);

    // Mouse Tracking Physics
    const mouse = {
      x: -1000,
      y: -1000,
      radius: 220,
    };

    const handleMouseMove = (e: MouseEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    };

    const handleMouseLeave = () => {
      mouse.x = -1000;
      mouse.y = -1000;
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseleave', handleMouseLeave);

    // Particle Palette
    const colors = isDark 
      ? ['rgba(99, 102, 241, ', 'rgba(168, 85, 247, ', 'rgba(59, 130, 246, '] 
      : ['rgba(79, 70, 229, ', 'rgba(147, 51, 234, ', 'rgba(37, 99, 235, '];

    // Generate Particles based on logical screen dimensions
    const logicalWidth = window.innerWidth;
    const logicalHeight = window.innerHeight;
    const count = Math.min(Math.floor((logicalWidth * logicalHeight) / 9500), 110);
    const particles: Particle[] = [];

    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * logicalWidth,
        y: Math.random() * logicalHeight,
        vx: (Math.random() - 0.5) * 1.2,
        vy: (Math.random() - 0.5) * 1.2,
        radius: Math.random() * 2.2 + 1.2,
        baseAlpha: Math.random() * 0.5 + 0.4,
        color: colors[Math.floor(Math.random() * colors.length)],
      });
    }

    const render = () => {
      const width = window.innerWidth;
      const height = window.innerHeight;

      ctx.clearRect(0, 0, width, height);

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];

        p.x += p.vx;
        p.y += p.vy;

        // Wrap around edges for continuous smooth motion
        if (p.x < 0) p.x = width;
        if (p.x > width) p.x = 0;
        if (p.y < 0) p.y = height;
        if (p.y > height) p.y = 0;

        // Draw crisp particle dot with subtle glow
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = `${p.color}${p.baseAlpha})`;
        ctx.shadowBlur = 6;
        ctx.shadowColor = `${p.color}0.9)`;
        ctx.fill();
        ctx.shadowBlur = 0;

        // Connect nearby particles with sharp network constellation lines
        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const dx = p.x - p2.x;
          const dy = p.y - p2.y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 140) {
            const alpha = (1 - dist / 140) * (isDark ? 0.4 : 0.3);
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = `${p.color}${alpha})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        }

        // Motion Sensitivity: Connect & Attract to Mouse Cursor
        const mdx = p.x - mouse.x;
        const mdy = p.y - mouse.y;
        const mdist = Math.sqrt(mdx * mdx + mdy * mdy);

        if (mdist < mouse.radius) {
          const mAlpha = (1 - mdist / mouse.radius) * (isDark ? 0.8 : 0.6);

          // Sharp glowing line from particle to mouse cursor
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(mouse.x, mouse.y);
          ctx.strokeStyle = isDark ? `rgba(168, 85, 247, ${mAlpha})` : `rgba(79, 70, 229, ${mAlpha})`;
          ctx.lineWidth = 1.4;
          ctx.stroke();

          // Magnetic gentle nudge towards cursor
          const force = (mouse.radius - mdist) / mouse.radius;
          p.x -= (mdx / mdist) * force * 1.5;
          p.y -= (mdy / mdist) * force * 1.5;
        }
      }

      // Draw subtle mouse cursor glow orb
      if (mouse.x > 0 && mouse.y > 0) {
        const gradient = ctx.createRadialGradient(mouse.x, mouse.y, 0, mouse.x, mouse.y, mouse.radius * 0.7);
        gradient.addColorStop(0, isDark ? 'rgba(99, 102, 241, 0.2)' : 'rgba(79, 70, 229, 0.15)');
        gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(mouse.x, mouse.y, mouse.radius * 0.7, 0, Math.PI * 2);
        ctx.fill();
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', updateDimensions);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, [isDark]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-full h-full pointer-events-none z-0"
      style={{ width: '100vw', height: '100vh' }}
    />
  );
};
