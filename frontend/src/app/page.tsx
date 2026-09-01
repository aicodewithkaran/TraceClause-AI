'use client';

import React, { useState } from 'react';
import { Dropzone } from '@/components/upload/Dropzone';
import { SplitView } from '@/components/review/SplitView';
import { PaymentModal } from '@/components/pricing/PaymentModal';
import { ContractAnalysisResponse } from '@/types/contract';
import { useTheme } from '@/context/ThemeContext';
import { Shield, Sparkles, Scale, FileSearch, CreditCard, Sun, Moon } from 'lucide-react';

export default function Home() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';
  const [analysisResult, setAnalysisResult] = useState<ContractAnalysisResponse | null>(null);
  const [isPaymentOpen, setIsPaymentOpen] = useState(false);

  return (
    <main className={`min-h-screen transition-colors duration-300 font-sans selection:bg-indigo-500 selection:text-white ${
      isDark ? 'bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'
    }`}>
      {/* Background Decorative Glow */}
      <div className={`absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-[400px] blur-[140px] pointer-events-none rounded-full ${
        isDark ? 'bg-indigo-600/10' : 'bg-indigo-400/20'
      }`} />

      {/* Payment Modal */}
      <PaymentModal isOpen={isPaymentOpen} onClose={() => setIsPaymentOpen(false)} />

      {/* Navigation Header */}
      <header className={`border-b backdrop-blur-xl sticky top-0 z-50 transition-colors ${
        isDark ? 'border-slate-800/80 bg-slate-950/80' : 'border-slate-200 bg-white/80'
      }`}>
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-indigo-600/20 text-indigo-500 border border-indigo-500/30 shadow-sm">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <span className={`font-extrabold text-lg tracking-tight ${isDark ? 'text-white' : 'text-slate-900'}`}>
                ScanShield AI
              </span>
              <span className="ml-2.5 text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-500 border border-indigo-500/20">
                v2.0 Advanced RAG
              </span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center space-x-3">
            {/* Theme Toggle Button */}
            <button
              onClick={toggleTheme}
              className={`p-2 rounded-xl border flex items-center space-x-2 text-xs font-semibold transition-all ${
                isDark 
                  ? 'bg-slate-900 border-slate-800 text-amber-400 hover:bg-slate-800' 
                  : 'bg-slate-100 border-slate-200 text-indigo-600 hover:bg-slate-200'
              }`}
              title="Toggle Dark / Light Theme"
            >
              {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              <span className="hidden sm:inline">{isDark ? 'Light Theme' : 'Dark Theme'}</span>
            </button>

            {/* Upgrade Button */}
            <button
              onClick={() => setIsPaymentOpen(true)}
              className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all shadow-md shadow-indigo-600/20"
            >
              <CreditCard className="w-4 h-4" />
              <span>Upgrade Plan</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Container */}
      <div className="max-w-7xl mx-auto px-6 py-10 relative">
        {!analysisResult ? (
          <div className="space-y-12">
            {/* Hero Section */}
            <div className="text-center max-w-3xl mx-auto space-y-4 pt-4">
              <div className="inline-flex items-center space-x-2 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-500 text-xs font-bold shadow-sm">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Next-Gen Legal AI & Section-Aware RAG</span>
              </div>
              <h1 className={`text-4xl md:text-5xl font-black tracking-tight leading-tight ${
                isDark ? 'text-white' : 'text-slate-900'
              }`}>
                AI-Powered Contract & Legal Clause Risk Analyzer
              </h1>
              <p className={`text-base leading-relaxed max-w-2xl mx-auto ${
                isDark ? 'text-slate-400' : 'text-slate-600'
              }`}>
                Upload commercial agreements to instantly detect high-risk liabilities, auto-generate safer redline counter-language, and query clauses via RAG.
              </p>
            </div>

            {/* File Dropzone */}
            <Dropzone onAnalysisComplete={(result) => setAnalysisResult(result)} />

            {/* Feature Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4 max-w-5xl mx-auto">
              <div className={`p-6 rounded-3xl border space-y-3 shadow-xl transition-all ${
                isDark ? 'bg-slate-900/60 border-slate-800' : 'bg-white border-slate-200 shadow-slate-200/50'
              }`}>
                <div className="p-3 rounded-2xl bg-indigo-500/10 text-indigo-500 w-fit">
                  <FileSearch className="w-6 h-6" />
                </div>
                <h3 className={`text-base font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  Semantic Chunking
                </h3>
                <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Preserves individual section boundaries, exhibit definitions, and clause context rather than naive text splitting.
                </p>
              </div>

              <div className={`p-6 rounded-3xl border space-y-3 shadow-xl transition-all ${
                isDark ? 'bg-slate-900/60 border-slate-800' : 'bg-white border-slate-200 shadow-slate-200/50'
              }`}>
                <div className="p-3 rounded-2xl bg-emerald-500/10 text-emerald-500 w-fit">
                  <Scale className="w-6 h-6" />
                </div>
                <h3 className={`text-base font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  Structured Redlining
                </h3>
                <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Outputs clean JSON redlines featuring Risk Level, Explanation, and Suggested Counter-Language.
                </p>
              </div>

              <div className={`p-6 rounded-3xl border space-y-3 shadow-xl transition-all ${
                isDark ? 'bg-slate-900/60 border-slate-800' : 'bg-white border-slate-200 shadow-slate-200/50'
              }`}>
                <div className="p-3 rounded-2xl bg-amber-500/10 text-amber-500 w-fit">
                  <Sparkles className="w-6 h-6" />
                </div>
                <h3 className={`text-base font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  Interactive RAG Q&A
                </h3>
                <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Query specific liabilities, indemnities, or termination terms with direct source clause citations.
                </p>
              </div>
            </div>
          </div>
        ) : (
          <SplitView
            analysis={analysisResult}
            onReset={() => setAnalysisResult(null)}
          />
        )}
      </div>
    </main>
  );
}
