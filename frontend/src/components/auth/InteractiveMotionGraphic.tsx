'use client';

import React from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { 
  Lock, 
  ShieldAlert, 
  Scale, 
  FileText, 
  Cpu, 
  GitBranch, 
  Layers,
  Activity
} from 'lucide-react';
import { useTheme } from '@/context/ThemeContext';

export const InteractiveMotionGraphic: React.FC = () => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  // Smooth Mouse Coordinates for Parallax Floating
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  const springX = useSpring(mouseX, { stiffness: 90, damping: 22 });
  const springY = useSpring(mouseY, { stiffness: 90, damping: 22 });

  // Floating Layers at Different Depths
  const layer1X = useTransform(springX, [-400, 400], [-18, 18]);
  const layer1Y = useTransform(springY, [-400, 400], [-18, 18]);

  const layer2X = useTransform(springX, [-400, 400], [28, -28]);
  const layer2Y = useTransform(springY, [-400, 400], [28, -28]);

  const layer3X = useTransform(springX, [-400, 400], [-42, 42]);
  const layer3Y = useTransform(springY, [-400, 400], [-42, 42]);

  const glowX = useTransform(springX, [-400, 400], [-60, 60]);
  const glowY = useTransform(springY, [-400, 400], [-60, 60]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;
    mouseX.set(x);
    mouseY.set(y);
  };

  return (
    <div
      onMouseMove={handleMouseMove}
      className="relative w-full min-h-[420px] rounded-3xl overflow-hidden p-6 lg:p-8 flex flex-col justify-between cursor-pointer select-none my-2 transition-all"
    >
      {/* Interactive Cursor Light Sphere */}
      <motion.div
        style={{ x: glowX, y: glowY }}
        className={`absolute w-96 h-96 rounded-full blur-[130px] pointer-events-none ${
          isDark ? 'bg-indigo-600/30' : 'bg-indigo-400/35'
        }`}
      />

      {/* Floating Animated Nodes & Orbs */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        {[...Array(9)].map((_, i) => (
          <motion.div
            key={i}
            animate={{
              y: [0, -25, 0],
              x: [0, 12, 0],
              opacity: [0.3, 0.8, 0.3],
              scale: [1, 1.25, 1],
            }}
            transition={{
              duration: 4 + (i % 4),
              repeat: Infinity,
              ease: 'easeInOut',
              delay: i * 0.35,
            }}
            className={`absolute w-2.5 h-2.5 rounded-full ${
              isDark ? 'bg-indigo-400/60 shadow-indigo-500/50 shadow-lg' : 'bg-indigo-600/50'
            }`}
            style={{
              top: `${10 + i * 10}%`,
              left: `${6 + i * 11}%`,
            }}
          />
        ))}
      </div>

      {/* TOP SECTION: 4 WELL-SPACED PRODUCT USP CARDS */}
      <div className="relative z-10 grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* USP 1: Zero Storage Guarantee */}
        <motion.div
          style={{ x: layer1X, y: layer1Y }}
          whileHover={{ scale: 1.03, zIndex: 30 }}
          className={`p-4 rounded-2xl border shadow-xl backdrop-blur-2xl transition-all ${
            isDark 
              ? 'bg-slate-900/85 border-slate-800 hover:border-emerald-500/40' 
              : 'bg-white/95 border-slate-200 hover:border-emerald-400 shadow-slate-200/60'
          }`}
        >
          <div className="flex items-start space-x-3">
            <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-500 flex-shrink-0">
              <Lock className="w-5 h-5" />
            </div>
            <div className="space-y-0.5">
              <h4 className={`text-xs font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                Zero Storage Guarantee
              </h4>
              <p className={`text-[11px] leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                Files processed in RAM memory & auto-purged immediately. 0 Bytes stored.
              </p>
            </div>
          </div>
        </motion.div>

        {/* USP 2: Risk Scoring */}
        <motion.div
          style={{ x: layer2X, y: layer2Y }}
          whileHover={{ scale: 1.03, zIndex: 30 }}
          className={`p-4 rounded-2xl border shadow-xl backdrop-blur-2xl transition-all ${
            isDark 
              ? 'bg-slate-900/85 border-slate-800 hover:border-red-500/40' 
              : 'bg-white/95 border-slate-200 hover:border-red-400 shadow-slate-200/60'
          }`}
        >
          <div className="flex items-start space-x-3">
            <div className="p-2.5 rounded-xl bg-red-500/10 text-red-500 flex-shrink-0">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div className="space-y-0.5">
              <h4 className={`text-xs font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                Liability Risk Scoring
              </h4>
              <p className={`text-[11px] leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                High, Medium & Low liability risk levels classified per section.
              </p>
            </div>
          </div>
        </motion.div>

        {/* USP 3: Safer Redlining */}
        <motion.div
          style={{ x: layer2X, y: layer2Y }}
          whileHover={{ scale: 1.03, zIndex: 30 }}
          className={`p-4 rounded-2xl border shadow-xl backdrop-blur-2xl transition-all ${
            isDark 
              ? 'bg-slate-900/85 border-slate-800 hover:border-indigo-500/40' 
              : 'bg-white/95 border-slate-200 hover:border-indigo-400 shadow-slate-200/60'
          }`}
        >
          <div className="flex items-start space-x-3">
            <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-500 flex-shrink-0">
              <Scale className="w-5 h-5" />
            </div>
            <div className="space-y-0.5">
              <h4 className={`text-xs font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                Safer Counter-Language
              </h4>
              <p className={`text-[11px] leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                Auto-generates safer redlines ready to send counterparties.
              </p>
            </div>
          </div>
        </motion.div>

        {/* USP 4: Semantic Chunking */}
        <motion.div
          style={{ x: layer1X, y: layer1Y }}
          whileHover={{ scale: 1.03, zIndex: 30 }}
          className={`p-4 rounded-2xl border shadow-xl backdrop-blur-2xl transition-all ${
            isDark 
              ? 'bg-slate-900/85 border-slate-800 hover:border-amber-500/40' 
              : 'bg-white/95 border-slate-200 hover:border-amber-400 shadow-slate-200/60'
          }`}
        >
          <div className="flex items-start space-x-3">
            <div className="p-2.5 rounded-xl bg-amber-500/10 text-amber-500 flex-shrink-0">
              <FileText className="w-5 h-5" />
            </div>
            <div className="space-y-0.5">
              <h4 className={`text-xs font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                Semantic Section Chunking
              </h4>
              <p className={`text-[11px] leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                Preserves Article & Section structural legal context.
              </p>
            </div>
          </div>
        </motion.div>
      </div>

      {/* BOTTOM SECTION: SLEEK CYBERNETIC ARCHITECTURE GRAPHIC (REPLACED SCANNER TEXT LINE WITH GRAPHICS!) */}
      <motion.div
        style={{ x: layer3X, y: layer3Y }}
        className={`relative z-20 mt-6 p-4 lg:p-5 rounded-2xl border shadow-2xl backdrop-blur-2xl overflow-hidden transition-all ${
          isDark 
            ? 'bg-slate-900/90 border-indigo-500/30 shadow-indigo-500/10' 
            : 'bg-white/95 border-slate-200 shadow-slate-300/80'
        }`}
      >
        {/* Animated Background Flow Line */}
        <div className="absolute inset-0 pointer-events-none opacity-20">
          <motion.div
            animate={{ x: ['-100%', '100%'] }}
            transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
            className="w-1/3 h-full bg-gradient-to-r from-transparent via-indigo-500 to-transparent"
          />
        </div>

        {/* Graphic Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800/40">
          <div className="flex items-center space-x-2">
            <Cpu className="w-4 h-4 text-indigo-500 animate-pulse" />
            <span className={`text-xs font-bold font-mono ${isDark ? 'text-white' : 'text-slate-900'}`}>
              Neural Vector Pipeline Architecture
            </span>
          </div>

          <div className="flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
            <span className="text-[10px] font-mono font-bold text-emerald-400">1536-Dim Normalized</span>
          </div>
        </div>

        {/* Cybernetic Workflow Nodes Graphic */}
        <div className="grid grid-cols-3 gap-3 pt-3">
          <div className={`p-2.5 rounded-xl border text-center space-y-1 ${
            isDark ? 'bg-slate-950/70 border-slate-800' : 'bg-slate-50 border-slate-200'
          }`}>
            <div className="flex justify-center text-indigo-400">
              <Layers className="w-4 h-4" />
            </div>
            <span className={`text-[10px] font-bold block ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>
              PDF / Word RAM Parse
            </span>
            <span className="text-[9px] text-emerald-400 font-mono">0 Bytes Stored</span>
          </div>

          <div className={`p-2.5 rounded-xl border text-center space-y-1 ${
            isDark ? 'bg-slate-950/70 border-slate-800' : 'bg-slate-50 border-slate-200'
          }`}>
            <div className="flex justify-center text-purple-400">
              <GitBranch className="w-4 h-4" />
            </div>
            <span className={`text-[10px] font-bold block ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>
              Dual Vector Engine
            </span>
            <span className="text-[9px] text-purple-400 font-mono">OpenAI + Gemini</span>
          </div>

          <div className={`p-2.5 rounded-xl border text-center space-y-1 ${
            isDark ? 'bg-slate-950/70 border-slate-800' : 'bg-slate-50 border-slate-200'
          }`}>
            <div className="flex justify-center text-indigo-400">
              <Activity className="w-4 h-4" />
            </div>
            <span className={`text-[10px] font-bold block ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>
              Isolated RAG Search
            </span>
            <span className="text-[9px] text-indigo-400 font-mono">pgvector HNSW</span>
          </div>
        </div>
      </motion.div>
    </div>
  );
};
