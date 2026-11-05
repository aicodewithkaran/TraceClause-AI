'use client';

import React, { useState } from 'react';
import { ContractAnalysisResponse } from '@/types/contract';
import { ClauseCard } from './ClauseCard';
import { ContractChat } from '../chat/ContractChat';
import { FileText, ArrowLeft, MessageSquare, ListFilter, Plus, Lock } from 'lucide-react';
import { useTheme } from '@/context/ThemeContext';
import { useAuth } from '@/context/AuthContext';

interface SplitViewProps {
  analysis: ContractAnalysisResponse;
  onReset: () => void;
}

export const SplitView: React.FC<SplitViewProps> = ({ analysis, onReset }) => {
  const { theme } = useTheme();
  const { profile } = useAuth();
  const isDark = theme === 'dark';
  const tier = (profile?.subscription_tier || 'free').toLowerCase();
  const [filter, setFilter] = useState<'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'>('ALL');
  const [activeTab, setActiveTab] = useState<'CLAUSES' | 'CHAT'>('CLAUSES');

  const filteredClauses = analysis.clauses.filter((c) => {
    if (filter === 'ALL') return true;
    return c.risk_level.toUpperCase() === filter;
  });

  return (
    <div className="w-full space-y-6">
      {/* Top Banner */}
      <div className={`flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-3xl border shadow-xl transition-all ${
        isDark ? 'bg-slate-900/90 border-slate-800' : 'bg-white border-slate-200 shadow-slate-200/50'
      }`}>
        <div className="space-y-1.5">
          <button
            onClick={onReset}
            className="flex items-center space-x-1.5 text-xs font-semibold text-indigo-500 hover:text-indigo-400 transition-colors mb-1"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Upload Another Contract</span>
          </button>
          <h2 className={`text-xl font-extrabold flex items-center space-x-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
            <FileText className="w-5 h-5 text-indigo-500" />
            <span>{analysis.file_name}</span>
          </h2>
          <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            Total Clauses Identified: {analysis.summary.total_clauses}
          </p>
        </div>

        {/* Actions & Score Pill Badges */}
        <div className="flex items-center space-x-3">
          <button
            onClick={onReset}
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all shadow-md"
          >
            <Plus className="w-4 h-4" />
            <span>New Audit</span>
          </button>

          <div className={`text-center px-4 py-2 rounded-2xl border ${
            isDark ? 'bg-slate-950/80 border-slate-800' : 'bg-slate-50 border-slate-200'
          }`}>
            <span className="text-[10px] uppercase font-bold text-slate-400 block tracking-wider">Overall Score</span>
            <span className={`text-sm font-extrabold ${
              analysis.summary.overall_risk_score.includes('HIGH') ? 'text-red-500' : 'text-emerald-500'
            }`}>
              {analysis.summary.overall_risk_score}
            </span>
          </div>
          <div className="text-center px-3.5 py-2 rounded-2xl bg-red-500/10 border border-red-500/20">
            <span className="text-[10px] uppercase font-bold text-red-400 block tracking-wider">High</span>
            <span className="text-sm font-extrabold text-red-500">{analysis.summary.high_risks}</span>
          </div>
          <div className="text-center px-3.5 py-2 rounded-2xl bg-amber-500/10 border border-amber-500/20">
            <span className="text-[10px] uppercase font-bold text-amber-400 block tracking-wider">Medium</span>
            <span className="text-sm font-extrabold text-amber-500">{analysis.summary.medium_risks}</span>
          </div>
        </div>
      </div>

      {/* Main Split Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Original Contract Text */}
        <div className={`lg:col-span-6 rounded-3xl p-6 flex flex-col h-[700px] border shadow-xl ${
          isDark ? 'bg-slate-900/60 border-slate-800' : 'bg-white border-slate-200 shadow-slate-200/50'
        }`}>
          <h3 className={`text-sm font-bold mb-3 flex items-center space-x-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
            <FileText className="w-4 h-4 text-indigo-500" />
            <span>Extracted Contract Text</span>
          </h3>
          <div className={`flex-1 overflow-y-auto rounded-2xl p-4 font-mono text-xs whitespace-pre-wrap leading-relaxed border ${
            isDark 
              ? 'bg-slate-950/90 border-slate-800 text-slate-300' 
              : 'bg-slate-50 border-slate-200 text-slate-800'
          }`}>
            {analysis.extracted_text}
          </div>
        </div>

        {/* Right: Clause Risk Cards Grid or Chat */}
        <div className="lg:col-span-6 flex flex-col space-y-4">
          {/* Controls Bar */}
          <div className={`flex items-center justify-between p-2 rounded-2xl border ${
            isDark ? 'bg-slate-900/90 border-slate-800' : 'bg-white border-slate-200 shadow-sm'
          }`}>
            <div className={`flex items-center space-x-1 p-1 rounded-xl border ${
              isDark ? 'bg-slate-950 border-slate-800' : 'bg-slate-100 border-slate-200'
            }`}>
              <button
                onClick={() => setActiveTab('CLAUSES')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center space-x-1.5 transition-colors ${
                  activeTab === 'CLAUSES' 
                    ? 'bg-indigo-600 text-white shadow-md' 
                    : isDark ? 'text-slate-400 hover:text-white' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <ListFilter className="w-3.5 h-3.5" />
                <span>Risk Breakdown</span>
              </button>
              <button
                onClick={() => setActiveTab('CHAT')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center space-x-1.5 transition-colors ${
                  activeTab === 'CHAT' 
                    ? 'bg-indigo-600 text-white shadow-md' 
                    : isDark ? 'text-slate-400 hover:text-white' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <MessageSquare className="w-3.5 h-3.5" />
                <span>RAG Assistant</span>
                {tier === 'free' && (
                  <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 font-mono font-bold border border-amber-500/30 flex items-center space-x-0.5">
                    <Lock className="w-2.5 h-2.5 mr-0.5" />
                    <span>Solo/Team</span>
                  </span>
                )}
              </button>
            </div>

            {activeTab === 'CLAUSES' && (
              <div className="flex items-center space-x-1 text-xs">
                {(['ALL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((lvl) => (
                  <button
                    key={lvl}
                    onClick={() => setFilter(lvl)}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-colors ${
                      filter === lvl
                        ? isDark ? 'bg-slate-800 text-white border border-slate-700' : 'bg-slate-200 text-slate-900'
                        : isDark ? 'text-slate-500 hover:text-slate-300' : 'text-slate-400 hover:text-slate-700'
                    }`}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Panel View */}
          {activeTab === 'CLAUSES' ? (
            <div className="space-y-4 overflow-y-auto h-[640px] pr-1">
              {filteredClauses.length === 0 ? (
                <div className={`p-8 text-center rounded-2xl border text-xs ${
                  isDark ? 'bg-slate-900/40 border-slate-800 text-slate-400' : 'bg-slate-50 border-slate-200 text-slate-500'
                }`}>
                  No clauses match the selected risk filter.
                </div>
              ) : (
                filteredClauses.map((clause) => (
                  <ClauseCard key={clause.clause_number} clause={clause} />
                ))
              )}
            </div>
          ) : (
            <ContractChat contractText={analysis.extracted_text} />
          )}
        </div>
      </div>
    </div>
  );
};
