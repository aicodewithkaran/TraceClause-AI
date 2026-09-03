'use client';

import React, { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { COUNTRIES_LIST } from '@/lib/countries';
import { NetworkBackgroundCanvas } from '@/components/ui/NetworkBackgroundCanvas';
import { 
  ShieldCheck, 
  Sparkles, 
  CheckCircle2, 
  User, 
  Mail, 
  Globe, 
  Briefcase, 
  Phone, 
  KeyRound, 
  Loader2,
  ArrowRight,
  ShieldAlert,
  PenTool,
  Lock,
  Scale,
  FileText
} from 'lucide-react';

export const AuthView: React.FC = () => {
  const { login, signup } = useAuth();
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form Fields
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [country, setCountry] = useState('United States');
  const [professionSelect, setProfessionSelect] = useState('Legal Counsel / Attorney');
  const [customProfession, setCustomProfession] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === 'signin') {
        await login({ email, password });
      } else {
        const finalProfession = professionSelect === 'Other' ? customProfession.trim() : professionSelect;

        if (!fullName || !email || !password || !country || !finalProfession) {
          setError('Please fill in all mandatory fields (*)');
          setLoading(false);
          return;
        }

        await signup({
          email,
          password,
          full_name: fullName,
          country,
          profession: finalProfession,
          phone_number: phoneNumber,
        });
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Authentication failed. Please try again.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`min-h-screen grid grid-cols-1 lg:grid-cols-10 transition-colors duration-300 relative overflow-hidden ${
      isDark ? 'bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'
    }`}>
      {/* Motion-Sensitive Interactive Network Background Canvas */}
      <NetworkBackgroundCanvas />

      {/* LEFT 70% PANEL (USPs & STATIC HIGH-TECH GRID) */}
      <div className={`lg:col-span-7 p-8 lg:p-12 flex flex-col justify-between relative z-10 border-b lg:border-b-0 lg:border-r transition-colors ${
        isDark 
          ? 'bg-slate-950/30 border-slate-800/50' 
          : 'bg-white/30 border-slate-200/70'
      }`}>
        {/* Glow Background Layer */}
        <div className={`absolute top-0 left-0 w-[600px] h-[600px] blur-[160px] pointer-events-none rounded-full ${
          isDark ? 'bg-indigo-600/15' : 'bg-indigo-400/20'
        }`} />

        {/* Brand Header */}
        <div className="relative z-10 space-y-2">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-2xl bg-indigo-600/20 text-indigo-500 border border-indigo-500/30 shadow-lg shadow-indigo-600/10">
              <ShieldCheck className="w-7 h-7" />
            </div>
            <div>
              <span className={`font-black text-2xl tracking-tight ${isDark ? 'text-white' : 'text-slate-900'}`}>
                TraceClause AI
              </span>
              <span className="ml-3 text-xs font-mono font-semibold px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-500 border border-indigo-500/20">
                v2.0 Legal RAG Platform
              </span>
            </div>
          </div>
        </div>

        {/* Main USP Hero Headline */}
        <div className="relative z-10 max-w-2xl my-6 space-y-4">
          <div className="inline-flex items-center space-x-2 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-500 text-xs font-bold shadow-sm">
            <Sparkles className="w-4 h-4" />
            <span>AI-Powered Commercial Contract Intelligence</span>
          </div>

          <h1 className={`text-3xl lg:text-4xl font-black tracking-tight leading-tight ${
            isDark ? 'text-white' : 'text-slate-900'
          }`}>
            Review Contracts 10x Faster with Instant AI Clause Redlining
          </h1>

          <p className={`text-xs lg:text-sm leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            TraceClause AI scans complex commercial agreements, flags hidden liabilities & uncapped indemnities, auto-generates safer counter-language, and lets you query your contracts via RAG.
          </p>
        </div>

        {/* STATIC CLEAN HIGH-TECH USP GRID (No floating cards) */}
        <div className="relative z-10 grid grid-cols-1 sm:grid-cols-2 gap-4 my-2">
          {/* Card 1 */}
          <div className={`p-4.5 rounded-2xl border shadow-xl transition-all ${
            isDark ? 'bg-slate-900/75 border-slate-800/80' : 'bg-white/80 border-slate-200/80 shadow-slate-200/50'
          }`}>
            <div className="flex items-start space-x-3">
              <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-500 flex-shrink-0">
                <Lock className="w-5 h-5" />
              </div>
              <div className="space-y-0.5">
                <h4 className={`text-xs font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  Zero Storage Guarantee
                </h4>
                <p className={`text-[11px] leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  Files parsed in RAM memory & auto-purged immediately. 0 Bytes saved on disk.
                </p>
              </div>
            </div>
          </div>

          {/* Card 2 */}
          <div className={`p-4.5 rounded-2xl border shadow-xl transition-all ${
            isDark ? 'bg-slate-900/75 border-slate-800/80' : 'bg-white/80 border-slate-200/80 shadow-slate-200/50'
          }`}>
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
          </div>

          {/* Card 3 */}
          <div className={`p-4.5 rounded-2xl border shadow-xl transition-all ${
            isDark ? 'bg-slate-900/75 border-slate-800/80' : 'bg-white/80 border-slate-200/80 shadow-slate-200/50'
          }`}>
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
          </div>

          {/* Card 4 */}
          <div className={`p-4.5 rounded-2xl border shadow-xl transition-all ${
            isDark ? 'bg-slate-900/75 border-slate-800/80' : 'bg-white/80 border-slate-200/80 shadow-slate-200/50'
          }`}>
            <div className="flex items-start space-x-3">
              <div className="p-2.5 rounded-xl bg-amber-500/10 text-amber-500 flex-shrink-0">
                <FileText className="w-5 h-5" />
              </div>
              <div className="space-y-0.5">
                <h4 className={`text-xs font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  Semantic Vector Indexing
                </h4>
                <p className={`text-[11px] leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  1536-dim Gemini MRL embeddings & interactive RAG contract search.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* USP Trust Indicators Footer */}
        <div className={`relative z-10 pt-4 border-t flex flex-wrap items-center justify-between gap-4 text-xs ${
          isDark ? 'border-slate-800 text-slate-400' : 'border-slate-200 text-slate-500'
        }`}>
          <span className="flex items-center space-x-1.5"><CheckCircle2 className="w-4 h-4 text-emerald-500" /><span>Zero Raw File Disk Storage</span></span>
          <span className="flex items-center space-x-1.5"><CheckCircle2 className="w-4 h-4 text-emerald-500" /><span>SOC-2 Aligned User Isolation</span></span>
          <span className="flex items-center space-x-1.5"><CheckCircle2 className="w-4 h-4 text-emerald-500" /><span>Dual RAG Vector Engine</span></span>
        </div>
      </div>

      {/* RIGHT 30% PANEL (SIGNUP / LOGIN FORMS) */}
      <div className={`lg:col-span-3 p-8 lg:p-10 flex flex-col justify-center relative z-10 overflow-y-auto transition-colors ${
        isDark ? 'bg-slate-900/85 border-l border-slate-800/80' : 'bg-white/90 border-l border-slate-200'
      }`}>
        <div className="w-full max-w-sm mx-auto space-y-6">
          {/* Header Controls */}
          <div className="space-y-2 text-center">
            <h3 className={`text-2xl font-black ${isDark ? 'text-white' : 'text-slate-900'}`}>
              {mode === 'signin' ? 'Welcome Back' : 'Create Account'}
            </h3>
            <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              {mode === 'signin' 
                ? 'Sign in to access your TraceClause dashboard' 
                : 'Get started with AI-powered legal clause analysis'}
            </p>

            {/* Mode Switcher Tabs */}
            <div className={`grid grid-cols-2 gap-1 p-1 rounded-xl border mt-4 ${
              isDark ? 'bg-slate-950 border-slate-800' : 'bg-slate-100 border-slate-200'
            }`}>
              <button
                onClick={() => { setMode('signin'); setError(null); }}
                className={`py-2 rounded-lg text-xs font-bold transition-all ${
                  mode === 'signin' 
                    ? 'bg-indigo-600 text-white shadow-md' 
                    : isDark ? 'text-slate-400 hover:text-white' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Sign In
              </button>
              <button
                onClick={() => { setMode('signup'); setError(null); }}
                className={`py-2 rounded-lg text-xs font-bold transition-all ${
                  mode === 'signup' 
                    ? 'bg-indigo-600 text-white shadow-md' 
                    : isDark ? 'text-slate-400 hover:text-white' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Sign Up
              </button>
            </div>
          </div>

          {/* Form Element */}
          <form onSubmit={handleSubmit} className="space-y-3.5 text-xs">
            {mode === 'signup' && (
              <>
                {/* Full Name */}
                <div>
                  <label className={`font-semibold block mb-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                    Full Name <span className="text-red-500">*</span>
                  </label>
                  <div className="relative">
                    <User className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                      type="text"
                      required
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="Jane Doe"
                      className={`w-full pl-9 pr-3 py-2.5 rounded-xl border focus:outline-none focus:border-indigo-500 transition-colors ${
                        isDark ? 'bg-slate-950 border-slate-800 text-white placeholder-slate-500' : 'bg-slate-50 border-slate-300 text-slate-900'
                      }`}
                    />
                  </div>
                </div>

                {/* Country */}
                <div>
                  <label className={`font-semibold block mb-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                    Country <span className="text-red-500">*</span>
                  </label>
                  <div className="relative">
                    <Globe className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <select
                      value={country}
                      onChange={(e) => setCountry(e.target.value)}
                      className={`w-full pl-9 pr-3 py-2.5 rounded-xl border focus:outline-none focus:border-indigo-500 transition-colors ${
                        isDark ? 'bg-slate-950 border-slate-800 text-white' : 'bg-slate-50 border-slate-300 text-slate-900'
                      }`}
                    >
                      {COUNTRIES_LIST.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Profession */}
                <div>
                  <label className={`font-semibold block mb-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                    What You Do / Profession <span className="text-red-500">*</span>
                  </label>
                  <div className="relative">
                    <Briefcase className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <select
                      value={professionSelect}
                      onChange={(e) => setProfessionSelect(e.target.value)}
                      className={`w-full pl-9 pr-3 py-2.5 rounded-xl border focus:outline-none focus:border-indigo-500 transition-colors ${
                        isDark ? 'bg-slate-950 border-slate-800 text-white' : 'bg-slate-50 border-slate-300 text-slate-900'
                      }`}
                    >
                      <option value="Legal Counsel / Attorney">Legal Counsel / Attorney</option>
                      <option value="Founder / CEO">Founder / CEO</option>
                      <option value="Procurement Manager">Procurement Manager</option>
                      <option value="Sales / Operations">Sales / Operations</option>
                      <option value="Freelancer / Consultant">Freelancer / Consultant</option>
                      <option value="Other">Other (Please specify)</option>
                    </select>
                  </div>
                </div>

                {/* Custom Profession Input */}
                {professionSelect === 'Other' && (
                  <div className="pt-1">
                    <label className={`font-semibold block mb-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                      Specify Profession <span className="text-red-500">*</span>
                    </label>
                    <div className="relative">
                      <PenTool className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                      <input
                        type="text"
                        required
                        value={customProfession}
                        onChange={(e) => setCustomProfession(e.target.value)}
                        placeholder="e.g. Contract Compliance Specialist"
                        className={`w-full pl-9 pr-3 py-2.5 rounded-xl border focus:outline-none focus:border-indigo-500 transition-colors ${
                          isDark ? 'bg-slate-950 border-slate-800 text-white placeholder-slate-500' : 'bg-slate-50 border-slate-300 text-slate-900'
                        }`}
                      />
                    </div>
                  </div>
                )}

                {/* Phone Number */}
                <div>
                  <label className={`font-semibold block mb-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    Phone Number <span className="text-slate-400 font-normal">(Optional)</span>
                  </label>
                  <div className="relative">
                    <Phone className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                      type="tel"
                      value={phoneNumber}
                      onChange={(e) => setPhoneNumber(e.target.value)}
                      placeholder="+1 (555) 000-0000"
                      className={`w-full pl-9 pr-3 py-2.5 rounded-xl border focus:outline-none focus:border-indigo-500 transition-colors ${
                        isDark ? 'bg-slate-950 border-slate-800 text-white placeholder-slate-500' : 'bg-slate-50 border-slate-300 text-slate-900'
                      }`}
                    />
                  </div>
                </div>
              </>
            )}

            {/* Email */}
            <div>
              <label className={`font-semibold block mb-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                Email Address <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="alex@company.com"
                  className={`w-full pl-9 pr-3 py-2.5 rounded-xl border focus:outline-none focus:border-indigo-500 transition-colors ${
                    isDark ? 'bg-slate-950 border-slate-800 text-white placeholder-slate-500' : 'bg-slate-50 border-slate-300 text-slate-900'
                  }`}
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label className={`font-semibold block mb-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                Password <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <KeyRound className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className={`w-full pl-9 pr-3 py-2.5 rounded-xl border focus:outline-none focus:border-indigo-500 transition-colors ${
                    isDark ? 'bg-slate-950 border-slate-800 text-white placeholder-slate-500' : 'bg-slate-50 border-slate-300 text-slate-900'
                  }`}
                />
              </div>
            </div>

            {error && (
              <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-center space-x-2">
                <ShieldAlert className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs flex items-center justify-center space-x-2 transition-all shadow-lg shadow-indigo-600/20 disabled:opacity-50 mt-2"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <span>{mode === 'signin' ? 'Sign In to Dashboard' : 'Create Free Account'}</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
