'use client';

import React, { useEffect } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { useTheme } from '@/context/ThemeContext';

export const GlobalBackgroundCanvas: React.FC = () => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  // Global Cursor Position State
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  // Ultra-Smooth Physics Springs
  const springX = useSpring(mouseX, { stiffness: 60, damping: 25 });
  const springY = useSpring(mouseY, { stiffness: 60, damping: 25 });

  // Dynamic Light Orb Offset Transforms
  const orb1X = useTransform(springX, [0, 1920], [-100, 100]);
  const orb1Y = useTransform(springY, [0, 1080], [-100, 100]);

  const orb2X = useTransform(springX, [0, 1920], [120, -120]);
  const orb2Y = useTransform(springY, [0, 1080], [120, -120]);

  const orb3X = useTransform(springX, [0, 1920], [-80, 80]);
  const orb3Y = useTransform(springY, [0, 1080], [80, -80]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      mouseX.set(e.clientX);
      mouseY.set(e.clientY);
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, [mouseX, mouseY]);

  return (
    <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
      {/* 1. MOUSE-FOLLOWING INTENSE GLOW SPOTLIGHT */}
      <motion.div
        style={{
          x: springX,
          y: springY,
          translateX: '-50%',
          translateY: '-50%',
        }}
        className={`absolute w-[600px] h-[600px] rounded-full blur-[140px] transition-colors duration-500 ${
          isDark ? 'bg-indigo-600/20' : 'bg-indigo-400/30'
        }`}
      />

      {/* 2. DYNAMIC FLOATING AMBIENT GLOW SPHERES (OPPOSITE MOTION PARALLAX) */}
      <motion.div
        style={{ x: orb1X, y: orb1Y }}
        className={`absolute top-0 left-1/4 w-[750px] h-[750px] rounded-full blur-[180px] transition-colors duration-700 ${
          isDark ? 'bg-purple-600/15' : 'bg-indigo-300/35'
        }`}
      />

      <motion.div
        style={{ x: orb2X, y: orb2Y }}
        className={`absolute bottom-0 right-1/4 w-[850px] h-[850px] rounded-full blur-[200px] transition-colors duration-700 ${
          isDark ? 'bg-blue-600/15' : 'bg-purple-300/30'
        }`}
      />

      <motion.div
        style={{ x: orb3X, y: orb3Y }}
        className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[900px] rounded-full blur-[220px] transition-colors duration-700 ${
          isDark ? 'bg-indigo-900/20' : 'bg-blue-200/40'
        }`}
      />

      {/* 3. HIGH-TECH ANIMATED MATRIX STARFIELD DUST */}
      <div className="absolute inset-0">
        {[...Array(16)].map((_, i) => (
          <motion.div
            key={i}
            animate={{
              y: [0, -40, 0],
              x: [0, (i % 2 === 0 ? 20 : -20), 0],
              opacity: [0.2, 0.7, 0.2],
              scale: [1, 1.4, 1],
            }}
            transition={{
              duration: 5 + (i % 4),
              repeat: Infinity,
              ease: 'easeInOut',
              delay: i * 0.3,
            }}
            className={`absolute w-1.5 h-1.5 rounded-full ${
              isDark ? 'bg-indigo-300/40 shadow-indigo-400/50 shadow-md' : 'bg-indigo-600/40'
            }`}
            style={{
              top: `${(i * 6.5) % 100}%`,
              left: `${(i * 11.5) % 100}%`,
            }}
          />
        ))}
      </div>

      {/* 4. PRECISE CYBERNETIC GRID CANVAS */}
      <div
        className={`absolute inset-0 transition-opacity duration-700 ${
          isDark
            ? 'opacity-[0.09] [background-image:radial-gradient(#818cf8_1px,transparent_1px),linear-gradient(to_right,#4f46e5_1px,transparent_1px),linear-gradient(to_bottom,#4f46e5_1px,transparent_1px)] [background-size:32px_32px,64px_64px,64px_64px]'
            : 'opacity-[0.14] [background-image:radial-gradient(#4f46e5_1px,transparent_1px),linear-gradient(to_right,#6366f1_1px,transparent_1px),linear-gradient(to_bottom,#6366f1_1px,transparent_1px)] [background-size:32px_32px,64px_64px,64px_64px]'
        }`}
      />
    </div>
  );
};
