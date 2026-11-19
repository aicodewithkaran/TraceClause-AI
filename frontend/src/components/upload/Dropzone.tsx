'use client';

import React, { useState, useRef } from 'react';
import { UploadCloud, FileText, AlertCircle, Sparkles, ShieldCheck } from 'lucide-react';
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
  const [progress, setProgress] = useState<number>(0);
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
    setProgress(10);
    try {
      setStatusMessage('Parsing contract structure in memory...');
      const extractRes = await apiClient.uploadDocument(file);
      setProgress(25);

      try {
        // Preferred production path: submit to durable asynchronous queue
        setStatusMessage('Submitting to contract analysis queue...');
        const jobRes = await apiClient.submitAnalysisJob(
          extractRes.filename,
          extractRes.extracted_text
        );

        setProgress(35);
        setStatusMessage('Job queued: waiting for processing worker...');

        let completed = false;
        const startTime = Date.now();
        const maxWaitMs = 180000; // 3 minute timeout safety

        while (!completed && Date.now() - startTime < maxWaitMs) {
          await new Promise((resolve) => setTimeout(resolve, 1500));
          const jobStatus = await apiClient.getJobStatus(jobRes.job_id);

          if (jobStatus.status === 'processing') {
            const currentPct = jobStatus.progress_percent || 40;
            setProgress(Math.max(35, currentPct));
            if (jobStatus.stage_message) {
              setStatusMessage(jobStatus.stage_message);
            }
          } else if (jobStatus.status === 'completed') {
            setProgress(100);
            setStatusMessage('Audit complete! Opening analysis...');
            completed = true;

            const resData = jobStatus.result || {};
            const summary = typeof resData.summary_json === 'string'
              ? JSON.parse(resData.summary_json)
              : resData.summary_json || {
                  total_clauses: 0,
                  high_risks: 0,
                  medium_risks: 0,
                  low_risks: 0,
                  overall_risk_score: 'LOW RISK'
                };
            const clauses = typeof resData.clauses_json === 'string'
              ? JSON.parse(resData.clauses_json)
              : resData.clauses_json || [];

            onAnalysisComplete({
              file_name: extractRes.filename,
              extracted_text: extractRes.extracted_text,
              summary,
              clauses,
            });
            return;
          } else if (jobStatus.status === 'failed' || jobStatus.status === 'cancelled') {
            throw new Error(jobStatus.error_message || 'Contract analysis job failed. Please try again.');
          }
        }

        if (!completed) {
          throw new Error('Analysis timed out. Please check the Audit Vault or try a shorter document.');
        }
      } catch (queueErr: unknown) {
        // Fallback to synchronous analysis if queue endpoint is unavailable
        const qErr = queueErr as { response?: { status?: number }; message?: string };
        if (qErr?.response?.status === 404 || qErr?.response?.status === 501) {
          setStatusMessage('Processing via direct analysis pipeline...');
          setProgress(50);
          const syncRes = await apiClient.analyzeContract(
            extractRes.filename,
            extractRes.extracted_text
          );
          setProgress(100);
          onAnalysisComplete(syncRes);
        } else {
          throw queueErr;
        }
      }
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(
        apiErr?.response?.data?.detail ||
        apiErr?.message ||
        'Failed to process contract. Please verify backend status.'
      );
    } finally {
      setLoading(false);
      setStatusMessage(null);
      setProgress(0);
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
          <div className="flex flex-col items-center py-8 space-y-4 w-full">
            <div className="relative">
              <div className="w-16 h-16 rounded-full border-4 border-indigo-500/20 border-t-indigo-500 animate-spin" />
              <Sparkles className="w-6 h-6 text-indigo-400 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
            </div>
            <div className="space-y-1 text-center w-full max-w-md">
              <p className={`text-base font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                {statusMessage}
              </p>
              <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                Evaluating commercial risk & generating redlines...
              </p>
              {progress > 0 && (
                <div className="w-full pt-3">
                  <div className="flex justify-between text-[11px] font-semibold text-slate-400 mb-1.5">
                    <span>Audit Pipeline Progress</span>
                    <span>{progress}%</span>
                  </div>
                  <div className={`w-full h-2 rounded-full overflow-hidden border ${isDark ? 'bg-slate-800 border-slate-700' : 'bg-slate-200 border-slate-300'}`}>
                    <div
                      className="bg-indigo-600 h-2 rounded-full transition-all duration-300 ease-out shadow-sm shadow-indigo-500/50"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
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
                <span>In-Memory Parsing • Zero File Disk Storage</span>
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Explicit Data Handling & Privacy Notice */}
      <div className={`mt-3 p-3.5 rounded-2xl border text-[11px] leading-relaxed flex items-start space-x-2.5 ${
        isDark ? 'bg-slate-900/60 border-slate-800 text-slate-400' : 'bg-slate-50 border-slate-200 text-slate-600'
      }`}>
        <ShieldCheck className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
        <span>
          <strong>Privacy & Data Notice:</strong> We do not store your original uploaded file as a persistent file. We process it in memory, temporarily stage extracted text while the audit runs, and delete that staged text when processing completes or fails. If audit history is enabled, the generated report, clause text, and embeddings are stored in your account until you delete them. Contract content is sent securely to our configured AI providers to generate the analysis.
        </span>
      </div>

      {error && (
        <div className="mt-4 p-4 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400 flex items-center space-x-3 text-xs shadow-lg">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Assistive Legal Review Reminder */}
      <p className="mt-3 text-center text-[11px] text-slate-400 dark:text-slate-500">
        TraceClause AI is an assistive workflow tool, not legal counsel. Results require independent attorney review.
      </p>
    </div>
  );
};
