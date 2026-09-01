'use client';

import React, { useState, useRef } from 'react';
import { UploadCloud, FileText, AlertCircle, Loader2, Sparkles, ShieldCheck } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { ContractAnalysisResponse } from '@/types/contract';
import { useTheme } from '@/context/ThemeContext';

interface DropzoneProps {
  onAnalysisComplete: (result: ContractAnalysisResponse) => void;
}

export const Dropzone: React.FC<DropzoneProps> = ({ onAnalysisComplete }) => {
  const { theme } = useTheme();
  const [isDragOver, setIsDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isDark = theme === 'dark';

  const processFile = async (file: File) => {
    if (!file.name.match(/\.(pdf|docx|doc)$/i)) {
      setError('Please upload a PDF or DOCX Word document.');
      return;
    }

    setError(null);
    setLoading(true);
    try {
      setStatusMessage('Parsing contract structure & section boundaries...');
      const extractRes = await apiClient.uploadDocument(file);

      setStatusMessage('AI is evaluating legal liabilities & generating redlines...');
      const analysisRes = await apiClient.analyzeContract(
        extractRes.filename,
        extractRes.extracted_text
      );

      onAnalysisComplete(analysisRes);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to process contract. Please check backend status.');
    } finally {
      setLoading(false);
      setStatusMessage(null);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto my-6">
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-3xl p-10 text-center cursor-pointer transition-all duration-300 shadow-2xl ${
          isDragOver
            ? 'border-indigo-500 bg-indigo-500/10 scale-[1.02]'
            : isDark
            ? 'border-slate-800 bg-slate-900/70 hover:border-indigo-500/50 hover:bg-slate-900/90'
            : 'border-slate-300 bg-white/90 hover:border-indigo-500/50 hover:bg-slate-50'
        }`}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={(e) => e.target.files?.[0] && processFile(e.target.files[0])}
          accept=".pdf,.docx,.doc"
          className="hidden"
        />

        {loading ? (
          <div className="flex flex-col items-center py-8 space-y-4">
            <div className="relative">
              <div className="w-16 h-16 rounded-full border-4 border-indigo-500/20 border-t-indigo-500 animate-spin" />
              <Sparkles className="w-6 h-6 text-indigo-400 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
            </div>
            <p className={`text-base font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
              {statusMessage}
            </p>
            <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              Processing clauses against standard legal playbooks...
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center space-y-4 py-6">
            <div className={`p-5 rounded-2xl border transition-transform duration-300 hover:scale-110 ${
              isDark 
                ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20 shadow-lg shadow-indigo-500/5' 
                : 'bg-indigo-50 text-indigo-600 border-indigo-200 shadow-md'
            }`}>
              <UploadCloud className="w-10 h-10" />
            </div>
            <div className="space-y-1">
              <h3 className={`text-xl font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                Upload Contract for AI Risk Review
              </h3>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Drag & drop your PDF or Word document, or click to browse
              </p>
            </div>
            <div className={`flex items-center space-x-3 text-xs pt-3 font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              <span className="flex items-center space-x-1">
                <FileText className="w-4 h-4 text-indigo-400" />
                <span>PDF & DOCX</span>
              </span>
              <span>•</span>
              <span className="flex items-center space-x-1">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Zero Storage Retention</span>
              </span>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="mt-4 p-4 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400 flex items-center space-x-3 text-xs shadow-lg">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
};
