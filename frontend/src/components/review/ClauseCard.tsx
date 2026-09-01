'use client';

import React, { useState } from 'react';
import { ClauseAnalysis } from '@/types/contract';
import { AlertTriangle, CheckCircle2, ShieldAlert, Copy, Check } from 'lucide-react';
import { useTheme } from '@/context/ThemeContext';

interface ClauseCardProps {
  clause: ClauseAnalysis;
}

export const ClauseCard: React.FC<ClauseCardProps> = ({ clause }) => {
  const { theme } = useTheme();
  const [copied, setCopied] = useState(false);
  const isDark = theme === 'dark';

  const handleCopy = () => {
    navigator.clipboard.writeText(clause.suggested_counter_language);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getRiskBadge = (level: string) => {
    switch (level.toUpperCase()) {
      case 'HIGH':
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-red-500/10 text-red-400 border border-red-500/20">
            <ShieldAlert className="w-3.5 h-3.5 mr-1" /> High Risk
          </span>
        );
      case 'MEDIUM':
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <AlertTriangle className="w-3.5 h-3.5 mr-1" /> Medium Risk
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Low Risk
          </span>
        );
    }
  };

  return (
    <div className={`rounded-2xl p-5 space-y-4 shadow-xl border transition-all ${
      isDark
        ? 'bg-slate-900/80 border-slate-800 hover:border-slate-700'
        : 'bg-white border-slate-200 hover:border-slate-300 shadow-slate-200/50'
    }`}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <span className="text-xs font-mono text-indigo-500 font-semibold">Clause #{clause.clause_number}</span>
          <h4 className={`text-base font-bold mt-0.5 ${isDark ? 'text-white' : 'text-slate-900'}`}>
            {clause.clause_name}
          </h4>
        </div>
        {getRiskBadge(clause.risk_level)}
      </div>

      {/* Explanation */}
      <div className={`rounded-xl p-3.5 text-xs space-y-1 border ${
        isDark 
          ? 'bg-slate-950/60 border-slate-800 text-slate-300' 
          : 'bg-slate-50 border-slate-200 text-slate-700'
      }`}>
        <p className="font-semibold text-slate-400 uppercase tracking-wider text-[10px]">Risk Assessment:</p>
        <p className="leading-relaxed">{clause.risk_explanation}</p>
      </div>

      {/* Suggested Redline */}
      <div className={`rounded-xl p-3.5 text-xs space-y-2 border ${
        isDark
          ? 'bg-indigo-950/20 border-indigo-900/40'
          : 'bg-indigo-50/60 border-indigo-200'
      }`}>
        <div className="flex items-center justify-between">
          <span className="font-semibold text-indigo-400 uppercase tracking-wider text-[10px]">Suggested Redline Counter-Language:</span>
          <button
            onClick={handleCopy}
            className="flex items-center space-x-1 text-[11px] font-semibold text-indigo-500 hover:text-indigo-400 transition-colors"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied' : 'Copy Redline'}</span>
          </button>
        </div>
        <p className={`font-mono text-[11px] leading-relaxed p-3 rounded-lg border ${
          isDark
            ? 'bg-slate-950/90 text-indigo-200 border-indigo-900/30'
            : 'bg-white text-indigo-900 border-indigo-200 shadow-sm'
        }`}>
          {clause.suggested_counter_language}
        </p>
      </div>
    </div>
  );
};
