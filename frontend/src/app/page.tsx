'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Dropzone } from '@/components/upload/Dropzone';
import { SplitView } from '@/components/review/SplitView';
import { PaymentModal } from '@/components/pricing/PaymentModal';
import { SettingsModal } from '@/components/settings/SettingsModal';
import { AuthModal } from '@/components/auth/AuthModal';
import { TermsAcceptanceModal } from '@/components/auth/TermsAcceptanceModal';
import { GlobalBackgroundCanvas } from '@/components/ui/GlobalBackgroundCanvas';
import { ContractAnalysisResponse } from '@/types/contract';
import { useTheme } from '@/context/ThemeContext';
import { useAuth } from '@/context/AuthContext';
import { CURRENT_LEGAL_VERSION } from '@/lib/constants';
import { apiClient } from '@/lib/api-client';
import { Shield, Sparkles, Scale, FileSearch, CreditCard, Sun, Moon, LogOut, User as UserIcon, Loader2, Settings, Lock, FileText, Clock, ArrowUpRight, History, Download, Search, Plus, Zap, CheckCircle2, FileCode, Layers, ArrowRight, Rocket, Trash2 } from 'lucide-react';

export default function Home() {
  const { theme, toggleTheme } = useTheme();
  const { user, profile, logout, refreshProfile, loading, acceptTermsAndPrivacy } = useAuth();
  const isDark = theme === 'dark';

  const [activeTab, setActiveTab] = useState<'analyzer' | 'history'>('analyzer');
  const [analysisResult, setAnalysisResult] = useState<ContractAnalysisResponse | null>(null);
  const [isPaymentOpen, setIsPaymentOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [savedReports, setSavedReports] = useState<any[]>([]);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [historySearchQuery, setHistorySearchQuery] = useState('');

  const dropzoneRef = useRef<HTMLDivElement>(null);

  // Check if logged-in user needs to accept / re-accept Terms of Service & Privacy Policy
  const needsTermsAcceptance = Boolean(user && profile && profile.tos_accepted_version !== CURRENT_LEGAL_VERSION);
  const isUpdateNotice = Boolean(user && profile && profile.tos_accepted_version && profile.tos_accepted_version !== CURRENT_LEGAL_VERSION);

  // Automatically close Auth modal upon successful login / signup
  useEffect(() => {
    if (user) {
      setIsAuthOpen(false);
    }
  }, [user]);

  // 1. Session Persistence: Load active analysis on page refresh
  useEffect(() => {
    try {
      const cached = sessionStorage.getItem('active_analysis');
      if (cached) {
        setAnalysisResult(JSON.parse(cached));
      }
    } catch {
      // Ignore cache parse error
    }
  }, []);

  // 2. Fetch User Saved Reports History
  const fetchHistory = async () => {
    if (!user) return;
    setReportsLoading(true);
    try {
      const reports = await apiClient.getHistory();
      setSavedReports(reports || []);
    } catch {
      // Ignore history error
    } finally {
      setReportsLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      fetchHistory();
    }
  }, [user]);

  const handleSetAnalysis = (result: ContractAnalysisResponse | null) => {
    setAnalysisResult(result);
    if (result) {
      try {
        sessionStorage.setItem('active_analysis', JSON.stringify(result));
      } catch { }
      refreshProfile();
      fetchHistory();
    } else {
      try {
        sessionStorage.removeItem('active_analysis');
      } catch { }
    }
  };

  const handleDownloadDocx = async (reportId: string, fileName: string) => {
    try {
      const blob = await apiClient.exportDocx(reportId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${fileName.replace(/\s+/g, '_')}_redline.docx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to download DOCX redline report.');
    }
  };

  const handleDeleteReport = async (reportId: string) => {
    if (!window.confirm("Are you sure you want to permanently delete this contract report from your Audit Vault? This action cannot be undone.")) {
      return;
    }
    try {
      await apiClient.deleteReport(reportId);
      await fetchHistory();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to delete contract report.");
    }
  };

  const scrollToDropzone = () => {
    if (dropzoneRef.current) {
      dropzoneRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const filteredHistory = savedReports.filter(r =>
    r.file_name?.toLowerCase().includes(historySearchQuery.toLowerCase())
  );

  // Calculate live quota counts
  const tier = (profile?.subscription_tier || 'free').toLowerCase();
  const usedAudits = profile?.lifetime_free_audits_used ?? profile?.weekly_quota_used ?? 0;
  const remainingAudits = Math.max(0, 3 - usedAudits);

  // Show Loading Spinner while checking auth state
  if (loading) {
    return (
      <div className={`min-h-screen flex flex-col items-center justify-center space-y-4 ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'
        }`}>
        <GlobalBackgroundCanvas />
        <Loader2 className="w-10 h-10 text-indigo-500 animate-spin relative z-10" />
        <p className="text-xs font-semibold tracking-wide uppercase text-slate-400 relative z-10">Loading TraceClause AI Session...</p>
      </div>
    );
  }

  return (
    <main className={`min-h-screen transition-colors duration-300 font-sans selection:bg-indigo-500 selection:text-white relative overflow-hidden ${isDark ? 'bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'
      }`}>
      {/* PERSISTENT GLOBAL BACKGROUND GRAPHIC CANVAS */}
      <GlobalBackgroundCanvas />

      {/* Payment, Settings, Auth, and Mandatory Legal Modals */}
      <PaymentModal isOpen={isPaymentOpen} onClose={() => setIsPaymentOpen(false)} />
      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
      <AuthModal isOpen={isAuthOpen} onClose={() => setIsAuthOpen(false)} />
      <TermsAcceptanceModal
        isOpen={needsTermsAcceptance}
        onAccept={acceptTermsAndPrivacy}
        isUpdateNotice={isUpdateNotice}
        allowClose={false}
      />

      {/* Navigation Header */}
      <header className={`border-b backdrop-blur-xl sticky top-0 z-50 transition-colors relative ${isDark ? 'border-slate-800/80 bg-slate-950/80' : 'border-slate-200 bg-white/80'
        }`}>
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-6">
            <div className="flex items-center space-x-3 cursor-pointer" onClick={() => { setActiveTab('analyzer'); handleSetAnalysis(null); }}>
              <div className="p-2 rounded-xl bg-indigo-600/20 text-indigo-500 border border-indigo-500/30 shadow-sm">
                <Shield className="w-5 h-5" />
              </div>
              <span className={`font-extrabold text-lg tracking-tight ${isDark ? 'text-white' : 'text-slate-900'}`}>
                TraceClause AI
              </span>
            </div>

            {/* LOGGED IN USER TABS */}
            {user && (
              <div className={`hidden sm:flex items-center p-1 rounded-xl border text-xs font-bold ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-slate-100 border-slate-200'
                }`}>
                <button
                  onClick={() => {
                    setActiveTab('analyzer');
                    handleSetAnalysis(null);
                  }}
                  className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg transition-all ${activeTab === 'analyzer' && !analysisResult
                      ? 'bg-indigo-600 text-white shadow-md'
                      : isDark ? 'text-slate-400 hover:text-white' : 'text-slate-600 hover:text-slate-900'
                    }`}
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>New Audit</span>
                </button>

                <button
                  onClick={() => {
                    setActiveTab('history');
                    fetchHistory();
                  }}
                  className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg transition-all ${activeTab === 'history'
                      ? 'bg-indigo-600 text-white shadow-md'
                      : isDark ? 'text-slate-400 hover:text-white' : 'text-slate-600 hover:text-slate-900'
                    }`}
                >
                  <History className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Audit Vault</span>
                  {savedReports.length > 0 && (
                    <span className="px-1.5 py-0.2 rounded-full bg-indigo-500/20 text-indigo-300 text-[10px] font-mono">
                      {savedReports.length}
                    </span>
                  )}
                </button>
              </div>
            )}
          </div>

          {/* Right Header Navigation & Actions */}
          <div className="flex items-center space-x-3">
            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className={`p-2 rounded-xl border flex items-center space-x-2 text-xs font-semibold transition-all ${isDark
                  ? 'bg-slate-900 border-slate-800 text-amber-400 hover:bg-slate-800'
                  : 'bg-slate-100 border-slate-200 text-indigo-600 hover:bg-slate-200'
                }`}
              title="Toggle Dark / Light Theme"
            >
              {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>

            {user ? (
              <>
                {/* LOGGED IN USER BADGE */}
                <div className={`hidden md:flex items-center space-x-2 px-3 py-1.5 rounded-xl border text-xs font-semibold ${isDark ? 'bg-slate-900 border-slate-800 text-slate-300' : 'bg-slate-100 border-slate-200 text-slate-700'
                  }`}>
                  <UserIcon className="w-3.5 h-3.5 text-indigo-500" />
                  <span>{profile?.full_name || user.email?.split('@')[0]}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-400 font-mono uppercase font-bold">
                    {tier === 'free' ? `Audits remaining: ${remainingAudits} / 3` : `${tier.toUpperCase()} Plan Active`}
                  </span>
                </div>

                {/* Settings Trigger Button */}
                <button
                  onClick={() => setIsSettingsOpen(true)}
                  className={`p-2 rounded-xl border flex items-center space-x-1.5 text-xs font-semibold transition-all ${isDark
                      ? 'bg-slate-900 border-slate-800 text-slate-300 hover:text-white'
                      : 'bg-slate-100 border-slate-200 text-slate-700 hover:text-slate-900'
                    }`}
                  title="Account Settings"
                >
                  <Settings className="w-4 h-4 text-indigo-500" />
                  <span className="hidden sm:inline">Settings</span>
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
              </>
            ) : (
              <>
                {/* GUEST VIEW HEADER BUTTONS */}
                <button
                  onClick={() => setIsAuthOpen(true)}
                  className={`px-3.5 py-2 rounded-xl border text-xs font-bold transition-all ${isDark
                      ? 'bg-slate-900 border-slate-800 text-slate-300 hover:text-white'
                      : 'bg-slate-100 border-slate-200 text-slate-700 hover:text-slate-900'
                    }`}
                >
                  Sign In
                </button>

                <button
                  onClick={() => setIsAuthOpen(true)}
                  className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all shadow-md shadow-indigo-600/20"
                >
                  <Rocket className="w-3.5 h-3.5" />
                  <span>Get Started Free</span>
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="max-w-7xl mx-auto px-6 py-10 relative z-10">
        {/* TAB 1: ANALYZER / HOME OVERVIEW VIEW */}
        {activeTab === 'analyzer' && (
          !analysisResult ? (
            <div className="space-y-16">
              {/* SECTION 1: HEADER & HERO */}
              <div className="text-center max-w-4xl mx-auto space-y-6 pt-4">
                <div className="inline-flex items-center space-x-2 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-500 text-xs font-bold shadow-sm backdrop-blur-md">
                  <Sparkles className="w-4 h-4" />
                  <span>AI-Powered Commercial Contract Intelligence</span>
                </div>

                <h1 className={`text-4xl md:text-6xl font-black tracking-tight leading-tight ${isDark ? 'text-white' : 'text-slate-900'
                  }`}>
                  Enterprise-Grade Legal Risk Intelligence, Automated.
                </h1>

                <p className={`text-base md:text-lg leading-relaxed max-w-3xl mx-auto ${isDark ? 'text-slate-300' : 'text-slate-600'
                  }`}>
                  Traditional contract reviews take 3 to 5 hours per document and cost hundreds of dollars in billable hours. TraceClause ingests your vendor agreements, maps clauses against legal risk taxonomies using native 1536-dim vector search, and generates client-ready Word redlines in under 60 seconds.
                </p>

                {/* GUEST DISCLAIMER BADGE (HIDDEN IF LOGGED IN) */}
                {!user && (
                  <p className="text-xs font-semibold text-indigo-400/90 tracking-wide pt-1">
                    *3 lifetime audits included. No credit card required.*
                  </p>
                )}
              </div>

              {/* SECTION 2: FILE UPLOAD MODULE (LOGGED IN ONLY) OR GUEST CTA GATEWAY */}
              <div ref={dropzoneRef} className="pt-2">
                {user ? (
                  <div className="space-y-4">
                    <div className="text-center space-y-1">
                      <h3 className={`text-lg font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                        Secure Upload & Processing Pipeline
                      </h3>
                      <p className="text-xs text-slate-400">
                        Upload your PDF or DOCX contract below to run vector analysis.
                      </p>
                    </div>
                    <Dropzone onAnalysisComplete={(result) => handleSetAnalysis(result)} />
                  </div>
                ) : (
                  <div className={`p-10 rounded-3xl border text-center space-y-5 shadow-2xl backdrop-blur-xl max-w-3xl mx-auto ${isDark ? 'bg-slate-900/80 border-slate-800' : 'bg-white border-slate-200 shadow-slate-200/50'
                    }`}>
                    <div className="p-4 rounded-2xl bg-indigo-500/10 text-indigo-400 w-fit mx-auto border border-indigo-500/20">
                      <Rocket className="w-8 h-8 animate-bounce" />
                    </div>
                    <div className="space-y-2">
                      <h3 className={`text-2xl font-black ${isDark ? 'text-white' : 'text-slate-900'}`}>
                        Ready to Audit Your Contracts in Under 60 Seconds?
                      </h3>
                      <p className={`text-xs max-w-lg mx-auto ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                        Create your free account now to analyze up to 3 contracts with zero storage retention and instant DOCX redlines.
                      </p>
                    </div>

                    <div className="pt-2 space-y-2">
                      <button
                        onClick={() => setIsAuthOpen(true)}
                        className="px-8 py-4 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white font-extrabold text-sm transition-all shadow-xl shadow-indigo-600/30 inline-flex items-center space-x-2.5"
                      >
                        <span>🚀 Create Free Account & Test 3 Audits</span>
                        <ArrowRight className="w-4 h-4" />
                      </button>
                      <p className="text-[11px] text-slate-400 font-semibold block">
                        *3 lifetime audits included. No credit card required.*
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* SECTION 3: THE DATA-BACKED IMPACT BAR (REAL METRICS) */}
              <div className="space-y-6 pt-4">
                <div className="text-center space-y-2">
                  <span className="text-xs font-bold uppercase tracking-widest text-indigo-500 font-mono">Platform Authority</span>
                  <h2 className={`text-2xl md:text-3xl font-extrabold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    Data-Backed Performance Benchmarks
                  </h2>
                </div>

                <div className={`rounded-3xl border overflow-hidden shadow-2xl backdrop-blur-xl ${isDark ? 'bg-slate-900/70 border-slate-800' : 'bg-white border-slate-200 shadow-slate-200/50'
                  }`}>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className={`border-b ${isDark ? 'border-slate-800 bg-slate-950/60 text-slate-400' : 'border-slate-200 bg-slate-100/70 text-slate-600'}`}>
                          <th className="p-4 font-bold uppercase text-[10px] tracking-wider">Metric</th>
                          <th className="p-4 font-bold uppercase text-[10px] tracking-wider">Benchmark / Impact</th>
                          <th className="p-4 font-bold uppercase text-[10px] tracking-wider">Why It Matters</th>
                        </tr>
                      </thead>
                      <tbody className={`divide-y ${isDark ? 'divide-slate-800/80 text-slate-300' : 'divide-slate-200 text-slate-700'}`}>
                        <tr className="hover:bg-indigo-500/5 transition-colors">
                          <td className="p-4 font-bold flex items-center space-x-2">
                            <Zap className="w-4 h-4 text-indigo-500 flex-shrink-0" />
                            <span>Review Speed</span>
                          </td>
                          <td className="p-4 font-extrabold text-indigo-400 font-mono text-sm">
                            4 Minutes <span className="text-xs font-normal text-slate-400 font-sans">vs. 3.5 Hours</span>
                          </td>
                          <td className="p-4 leading-relaxed text-slate-400">
                            Eliminates the initial manual parsing bottleneck for standard MSAs and NDAs.
                          </td>
                        </tr>

                        <tr className="hover:bg-indigo-500/5 transition-colors">
                          <td className="p-4 font-bold flex items-center space-x-2">
                            <Layers className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                            <span>Hallucination Guard</span>
                          </td>
                          <td className="p-4 font-bold text-emerald-400 font-mono">
                            Hierarchical Semantic Chunking
                          </td>
                          <td className="p-4 leading-relaxed text-slate-400">
                            Links cross-referenced definitions across pages so liability caps are never miscalculated.
                          </td>
                        </tr>

                        <tr className="hover:bg-indigo-500/5 transition-colors">
                          <td className="p-4 font-bold flex items-center space-x-2">
                            <FileCode className="w-4 h-4 text-blue-400 flex-shrink-0" />
                            <span>Output Format</span>
                          </td>
                          <td className="p-4 font-bold text-blue-400 font-mono">
                            Native Microsoft Word (.docx)
                          </td>
                          <td className="p-4 leading-relaxed text-slate-400">
                            Delivers actual strikethroughs, green underlines, and margin callouts—not useless web chat text.
                          </td>
                        </tr>

                        <tr className="hover:bg-indigo-500/5 transition-colors">
                          <td className="p-4 font-bold flex items-center space-x-2">
                            <Scale className="w-4 h-4 text-amber-400 flex-shrink-0" />
                            <span>Risk Detection</span>
                          </td>
                          <td className="p-4 font-bold text-amber-400 font-mono">
                            Taxonomy-Driven Scoring
                          </td>
                          <td className="p-4 leading-relaxed text-slate-400">
                            Instantly highlights one-sided indemnification, IP assignment traps, and unfair termination clauses.
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              {/* SECTION 4: CORE CAPABILITIES ARCHITECTURE */}
              <div className="space-y-8 pt-4">
                <div className="text-center space-y-2">
                  <span className="text-xs font-bold uppercase tracking-widest text-indigo-500 font-mono">System Mechanics</span>
                  <h2 className={`text-2xl md:text-3xl font-extrabold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    Core Capabilities Architecture
                  </h2>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {/* Capability 1 */}
                  <div className={`p-8 rounded-3xl border space-y-4 shadow-xl backdrop-blur-xl transition-all hover:border-indigo-500/50 ${isDark ? 'bg-slate-900/70 border-slate-800' : 'bg-white border-slate-200 shadow-slate-200/50'
                    }`}>
                    <div className="p-3.5 rounded-2xl bg-indigo-500/10 text-indigo-400 w-fit border border-indigo-500/20">
                      <Zap className="w-6 h-6" />
                    </div>
                    <h3 className={`text-lg font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                      ⚡ Automated Ingestion & Hierarchical Parsing
                    </h3>
                    <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                      Standard RAG tools break down legal documents randomly, causing the AI to miss critical cross-references (like Section 14 pointing back to Section 8). TraceClause extracts clause parentage and defined terms into a persistent session context before embedding.
                    </p>
                  </div>

                  {/* Capability 2 */}
                  <div className={`p-8 rounded-3xl border space-y-4 shadow-xl backdrop-blur-xl transition-all hover:border-indigo-500/50 ${isDark ? 'bg-slate-900/70 border-slate-800' : 'bg-white border-slate-200 shadow-slate-200/50'
                    }`}>
                    <div className="p-3.5 rounded-2xl bg-emerald-500/10 text-emerald-400 w-fit border border-emerald-500/20">
                      <Shield className="w-6 h-6" />
                    </div>
                    <h3 className={`text-lg font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                      🛡️ Instant Liability & Risk Mapping
                    </h3>
                    <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                      Our engine runs hybrid pgvector queries against legal risk taxonomies. It flags high-exposure clauses—such as uncapped liabilities, non-standard indemnities, and aggressive data security carve-outs—and assigns an immediate risk score.
                    </p>
                  </div>

                  {/* Capability 3 */}
                  <div className={`p-8 rounded-3xl border space-y-4 shadow-xl backdrop-blur-xl transition-all hover:border-indigo-500/50 ${isDark ? 'bg-slate-900/70 border-slate-800' : 'bg-white border-slate-200 shadow-slate-200/50'
                    }`}>
                    <div className="p-3.5 rounded-2xl bg-blue-500/10 text-blue-400 w-fit border border-blue-500/20">
                      <FileText className="w-6 h-6" />
                    </div>
                    <h3 className={`text-lg font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                      📝 Direct `.docx` Redlining Engine
                    </h3>
                    <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                      Stop copying and pasting AI responses into Word. TraceClause compiles structured JSON outputs straight into professional Word documents with tracked changes, ready to send directly back to your vendor or client.
                    </p>
                  </div>
                </div>
              </div>

              {/* SECTION 5: CONDITIONAL CALL-TO-ACTION (THE DYNAMIC GATE) */}
              <div className="pt-6">
                {user ? (
                  <div className={`p-10 rounded-3xl border text-center space-y-4 shadow-2xl backdrop-blur-xl max-w-3xl mx-auto ${isDark ? 'bg-slate-900/80 border-slate-800' : 'bg-white border-slate-200 shadow-slate-200/50'
                    }`}>
                    <h3 className={`text-2xl font-black ${isDark ? 'text-white' : 'text-slate-900'}`}>
                      Launch Your Next Contract Audit
                    </h3>
                    <p className={`text-xs max-w-md mx-auto ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                      You are authenticated on {tier === 'free' ? 'Free Trial' : `${tier.toUpperCase()} Tier`}. Upload your document to run immediate vector extraction.
                    </p>
                    <button
                      onClick={scrollToDropzone}
                      className="px-8 py-4 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white font-extrabold text-sm transition-all shadow-xl shadow-indigo-600/30 inline-flex items-center space-x-2.5"
                    >
                      <span>🚀 Launch New Contract Audit</span>
                      <ArrowRight className="w-4 h-4" />
                    </button>
                    <p className="text-[11px] text-slate-400 font-semibold block">
                      *Redirects directly to your secure upload pipeline.*
                    </p>
                  </div>
                ) : (
                  <div className={`p-10 rounded-3xl border text-center space-y-4 shadow-2xl backdrop-blur-xl max-w-3xl mx-auto ${isDark ? 'bg-slate-900/80 border-slate-800' : 'bg-white border-slate-200 shadow-slate-200/50'
                    }`}>
                    <h3 className={`text-2xl font-black ${isDark ? 'text-white' : 'text-slate-900'}`}>
                      Start Audit Trial Now
                    </h3>
                    <p className={`text-xs max-w-md mx-auto ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                      Try enterprise-grade legal clause analysis right now with zero commitment.
                    </p>
                    <button
                      onClick={() => setIsAuthOpen(true)}
                      className="px-8 py-4 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white font-extrabold text-sm transition-all shadow-xl shadow-indigo-600/30 inline-flex items-center space-x-2.5"
                    >
                      <span>🚀 Create Free Account & Test 3 Audits</span>
                      <ArrowRight className="w-4 h-4" />
                    </button>
                    <p className="text-[11px] text-slate-400 font-semibold block">
                      *3 lifetime audits included. No credit card required.*
                    </p>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <SplitView
              analysis={analysisResult}
              onReset={() => handleSetAnalysis(null)}
            />
          )
        )}

        {/* TAB 2: AUDIT VAULT / CONTRACT HISTORY VIEW */}
        {activeTab === 'history' && user && (
          <div className="space-y-6 max-w-6xl mx-auto">
            {/* Vault Header & Search */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b pb-6 border-slate-800">
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <History className="w-6 h-6 text-indigo-500" />
                  <h2 className={`text-2xl font-extrabold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    Audit Vault & Saved Redlines
                  </h2>
                </div>
                <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  Review, search, and download past contract audits stored in your isolated workspace database.
                </p>
              </div>

              {/* Search Bar */}
              <div className="relative min-w-[260px]">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  value={historySearchQuery}
                  onChange={(e) => setHistorySearchQuery(e.target.value)}
                  placeholder="Search contract file names..."
                  className={`w-full pl-9 pr-4 py-2 rounded-xl border text-xs focus:outline-none focus:border-indigo-500 ${isDark ? 'bg-slate-900 border-slate-800 text-white' : 'bg-white border-slate-300 text-slate-900'
                    }`}
                />
              </div>
            </div>

            {/* Reports Grid */}
            {reportsLoading ? (
              <div className="flex flex-col items-center justify-center py-16 space-y-3">
                <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
                <p className="text-xs text-slate-400 font-semibold">Retrieving your saved contract reports...</p>
              </div>
            ) : filteredHistory.length === 0 ? (
              <div className={`text-center py-16 px-4 rounded-3xl border space-y-3 ${isDark ? 'bg-slate-900/50 border-slate-800' : 'bg-white border-slate-200'
                }`}>
                <FileSearch className="w-10 h-10 text-indigo-400 mx-auto opacity-60" />
                <h3 className={`text-base font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {historySearchQuery ? 'No matching contract reports found' : 'No saved contract audits yet'}
                </h3>
                <p className={`text-xs max-w-sm mx-auto ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  Upload your first contract PDF or DOCX file to automatically store structured redlines in your Audit Vault.
                </p>
                <button
                  onClick={() => setActiveTab('analyzer')}
                  className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-bold shadow-md hover:bg-indigo-500 transition-all inline-flex items-center space-x-1.5"
                >
                  <Plus className="w-4 h-4" />
                  <span>Start New Audit</span>
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filteredHistory.map((report) => (
                  <div
                    key={report.id}
                    className={`p-5 rounded-2xl border flex flex-col justify-between space-y-4 transition-all hover:border-indigo-500/50 shadow-xl ${isDark ? 'bg-slate-900/80 border-slate-800' : 'bg-white border-slate-200'
                      }`}
                  >
                    <div className="space-y-3">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center space-x-3">
                          <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                            <FileText className="w-6 h-6" />
                          </div>
                          <div>
                            <h4 className={`font-bold text-sm truncate max-w-[220px] ${isDark ? 'text-white' : 'text-slate-900'}`}>
                              {report.file_name}
                            </h4>
                            <div className="flex items-center space-x-2 text-[11px] text-slate-400 mt-1">
                              <Clock className="w-3 h-3" />
                              <span>{new Date(report.created_at).toLocaleDateString()}</span>
                              <span>•</span>
                              <span>{report.clauses_json?.length || 0} Clauses</span>
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center space-x-1.5">
                          <span className={`text-[10px] font-extrabold uppercase px-2.5 py-1 rounded-full border ${report.overall_risk_score === 'HIGH RISK'
                              ? 'bg-red-500/10 text-red-400 border-red-500/30'
                              : report.overall_risk_score === 'MEDIUM RISK'
                                ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                                : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                            }`}>
                            {report.overall_risk_score}
                          </span>
                          <button
                            onClick={() => handleDeleteReport(report.id)}
                            title="Delete report permanently"
                            className="p-1 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800/50">
                      <button
                        onClick={() => {
                          const formattedResult: ContractAnalysisResponse = {
                            file_name: report.file_name,
                            extracted_text: report.summary_json?.extracted_text || '',
                            summary: report.summary_json,
                            clauses: report.clauses_json || []
                          };
                          handleSetAnalysis(formattedResult);
                          setActiveTab('analyzer');
                        }}
                        className="py-2 px-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition-all flex items-center justify-center space-x-1 shadow-md"
                      >
                        <span>Inspect Audit</span>
                        <ArrowUpRight className="w-3.5 h-3.5" />
                      </button>

                      <button
                        onClick={() => handleDownloadDocx(report.id, report.file_name)}
                        className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center space-x-1 ${isDark ? 'bg-slate-950 border-slate-800 text-slate-300 hover:text-white' : 'bg-slate-100 border-slate-300 text-slate-700'
                          }`}
                      >
                        <Download className="w-3.5 h-3.5 text-indigo-400" />
                        <span>Export .DOCX</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
