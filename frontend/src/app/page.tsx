'use client';

import React, { useState } from 'react';
import { Dropzone } from '@/components/upload/Dropzone';
import { SplitView } from '@/components/review/SplitView';
import { PaymentModal } from '@/components/pricing/PaymentModal';
import { SettingsModal } from '@/components/settings/SettingsModal';
import { AuthView } from '@/components/auth/AuthView';
import { GlobalBackgroundCanvas } from '@/components/ui/GlobalBackgroundCanvas';
import { ContractAnalysisResponse } from '@/types/contract';
import { useTheme } from '@/context/ThemeContext';
import { useAuth } from '@/context/AuthContext';
import { Shield, Sparkles, Scale, FileSearch, CreditCard, Sun, Moon, LogOut, User as UserIcon, Loader2, Settings, Lock } from 'lucide-react';

export default function Home() {
  const { theme, toggleTheme } = useTheme();
  const { user, profile, logout, loading } = useAuth();
  const isDark = theme === 'dark';

  const [analysisResult, setAnalysisResult] = useState<ContractAnalysisResponse | null>(null);
  const [isPaymentOpen, setIsPaymentOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Show Loading Spinner while checking auth state
  if (loading) {
    return (
      <div className={`min-h-screen flex flex-col items-center justify-center space-y-4 ${
        isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'
      }`}>
        <GlobalBackgroundCanvas />
        <Loader2 className="w-10 h-10 text-indigo-500 animate-spin relative z-10" />
        <p className="text-xs font-semibold tracking-wide uppercase text-slate-400 relative z-10">Loading TraceClause AI Session...</p>
      </div>
    );
  }

  // If Unauthenticated -> Render Auth Page (With Persisted Global Background)
  if (!user) {
    return (
      <>
        <GlobalBackgroundCanvas />
        <AuthView />
      </>
    );
  }

  // If Authenticated -> Render Full Dashboard (With Persisted Global Background)
  return (
    <main className={`min-h-screen transition-colors duration-300 font-sans selection:bg-indigo-500 selection:text-white relative overflow-hidden ${
      isDark ? 'bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'
    }`}>
      {/* PERSISTENT GLOBAL BACKGROUND GRAPHIC CANVAS */}
      <GlobalBackgroundCanvas />

      {/* Payment & Settings Modals */}
      <PaymentModal isOpen={isPaymentOpen} onClose={() => setIsPaymentOpen(false)} />
      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />

      {/* Authenticated Navigation Header */}
      <header className={`border-b backdrop-blur-xl sticky top-0 z-50 transition-colors relative ${
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
                TraceClause AI
              </span>
              <span className="ml-2.5 text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-500 border border-indigo-500/20">
                v2.0 Isolated
              </span>
            </div>
          </div>

          {/* User Profile & Actions */}
          <div className="flex items-center space-x-3">
            {/* User Real Signup Name Badge */}
            <div className={`hidden md:flex items-center space-x-2 px-3 py-1.5 rounded-xl border text-xs font-semibold ${
              isDark ? 'bg-slate-900 border-slate-800 text-slate-300' : 'bg-slate-100 border-slate-200 text-slate-700'
            }`}>
              <UserIcon className="w-3.5 h-3.5 text-indigo-500" />
              <span>{profile?.full_name || user.email?.split('@')[0]}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-400 font-mono uppercase">
                {profile?.subscription_tier || 'free'}
              </span>
            </div>

            {/* Settings Trigger Button */}
            <button
              onClick={() => setIsSettingsOpen(true)}
              className={`p-2 rounded-xl border flex items-center space-x-1.5 text-xs font-semibold transition-all ${
                isDark 
                  ? 'bg-slate-900 border-slate-800 text-slate-300 hover:text-white' 
                  : 'bg-slate-100 border-slate-200 text-slate-700 hover:text-slate-900'
              }`}
              title="Account Settings"
            >
              <Settings className="w-4 h-4 text-indigo-500" />
              <span className="hidden sm:inline">Settings</span>
            </button>

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
            </button>

            {/* Upgrade Plan */}
            <button
              onClick={() => setIsPaymentOpen(true)}
              className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all shadow-md shadow-indigo-600/20"
            >
              <CreditCard className="w-4 h-4" />
              <span className="hidden sm:inline">Upgrade</span>
            </button>

            {/* Logout Button */}
            <button
              onClick={logout}
              className="p-2 rounded-xl border border-red-500/30 bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-all text-xs font-semibold flex items-center space-x-1"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="max-w-7xl mx-auto px-6 py-10 relative z-10">
        {!analysisResult ? (
          <div className="space-y-12">
            {/* Hero Section */}
            <div className="text-center max-w-3xl mx-auto space-y-4 pt-4">
              <div className="inline-flex items-center space-x-2 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-500 text-xs font-bold shadow-sm backdrop-blur-md">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Isolated Workspace • {profile?.full_name || 'Active Session'}</span>
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
              <div className={`p-6 rounded-3xl border space-y-3 shadow-xl backdrop-blur-xl transition-all ${
                isDark ? 'bg-slate-900/70 border-slate-800' : 'bg-white/90 border-slate-200 shadow-slate-200/50'
              }`}>
                <div className="p-3 rounded-2xl bg-emerald-500/10 text-emerald-500 w-fit">
                  <Lock className="w-6 h-6" />
                </div>
                <h3 className={`text-base font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  Zero Storage Guarantee
                </h3>
                <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Raw uploaded files are extracted in RAM & purged immediately post-analysis. 0 Bytes stored on disk.
                </p>
              </div>

              <div className={`p-6 rounded-3xl border space-y-3 shadow-xl backdrop-blur-xl transition-all ${
                isDark ? 'bg-slate-900/70 border-slate-800' : 'bg-white/90 border-slate-200 shadow-slate-200/50'
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

              <div className={`p-6 rounded-3xl border space-y-3 shadow-xl backdrop-blur-xl transition-all ${
                isDark ? 'bg-slate-900/70 border-slate-800' : 'bg-white/90 border-slate-200 shadow-slate-200/50'
              }`}>
                <div className="p-3 rounded-2xl bg-amber-500/10 text-amber-500 w-fit">
                  <Scale className="w-6 h-6" />
                </div>
                <h3 className={`text-base font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  Structured Redlining
                </h3>
                <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Outputs clean JSON redlines featuring Risk Level, Explanation, and Suggested Counter-Language.
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
