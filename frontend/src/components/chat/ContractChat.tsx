'use client';

import React, { useState } from 'react';
import { Send, Bot, User, Loader2, Sparkles, CheckCircle2 } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { useTheme } from '@/context/ThemeContext';

interface ContractChatProps {
  contractText: string;
  isReady?: boolean;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: string[];
}

export const ContractChat: React.FC<ContractChatProps> = ({ contractText, isReady = true }) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: isReady 
        ? 'TraceClause AI is now ready, ask me anything.' 
        : "Please wait, we're preparing your contract context...",
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim() || loading || !isReady) return;

    const userQuery = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userQuery }]);
    setLoading(true);

    try {
      const res = await apiClient.chatWithContract(contractText, userQuery);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: res.answer,
          citations: res.citations,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, I failed to search contract context. Please try again.',
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`flex flex-col h-[650px] rounded-3xl overflow-hidden shadow-2xl border transition-all ${
      isDark ? 'bg-slate-900/90 border-slate-800' : 'bg-white border-slate-200'
    }`}>
      {/* Header */}
      <div className={`p-4 border-b flex items-center justify-between ${
        isDark ? 'bg-slate-950/80 border-slate-800' : 'bg-slate-50 border-slate-200'
      }`}>
        <div className="flex items-center space-x-2">
          <Sparkles className="w-5 h-5 text-indigo-500" />
          <h3 className={`font-bold text-sm ${isDark ? 'text-white' : 'text-slate-900'}`}>
            TraceClause AI Assistant
          </h3>
        </div>
        {isReady ? (
          <span className="text-[10px] uppercase font-mono px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold flex items-center space-x-1">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            <span>Ready</span>
          </span>
        ) : (
          <span className="text-[10px] uppercase font-mono px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-semibold flex items-center space-x-1 animate-pulse">
            <Loader2 className="w-3 h-3 text-amber-400 animate-spin" />
            <span>Preparing Context...</span>
          </span>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={`flex items-start space-x-2.5 ${
              m.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            {m.role === 'assistant' && (
              <div className="w-7 h-7 rounded-full bg-indigo-600/20 text-indigo-500 border border-indigo-500/30 flex items-center justify-center flex-shrink-0 shadow">
                <Bot className="w-4 h-4" />
              </div>
            )}

            <div
              className={`max-w-[80%] rounded-2xl p-3.5 shadow-sm leading-relaxed ${
                m.role === 'user'
                  ? 'bg-indigo-600 text-white rounded-tr-none'
                  : isDark
                  ? 'bg-slate-800/90 text-slate-100 border border-slate-700/60 rounded-tl-none'
                  : 'bg-slate-100 text-slate-900 border border-slate-200 rounded-tl-none'
              }`}
            >
              <p>{m.content}</p>
              {m.citations && m.citations.length > 0 && (
                <div className="mt-2.5 pt-2 border-t border-slate-700/40 space-y-1">
                  <p className="text-[10px] font-semibold text-indigo-400">Sources / Citations:</p>
                  {m.citations.map((c, i) => (
                    <span
                      key={i}
                      className="inline-block text-[10px] font-mono bg-slate-950 text-indigo-300 px-2 py-0.5 rounded border border-indigo-900/30 mr-1"
                    >
                      {c}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {m.role === 'user' && (
              <div className="w-7 h-7 rounded-full bg-slate-700 text-slate-200 flex items-center justify-center flex-shrink-0 shadow">
                <User className="w-4 h-4" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center space-x-2 text-indigo-500 text-xs py-2 font-medium">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Analyzing contract context...</span>
          </div>
        )}
      </div>

      {/* Input */}
      <div className={`p-3 border-t flex items-center space-x-2 ${
        isDark ? 'bg-slate-950/90 border-slate-800' : 'bg-slate-50 border-slate-200'
      }`}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder={isReady ? "Ask a question about this contract..." : "Please wait while context is prepared..."}
          disabled={!isReady || loading}
          className={`flex-1 border rounded-xl px-3.5 py-2.5 text-xs focus:outline-none focus:border-indigo-500 transition-colors ${
            isDark 
              ? 'bg-slate-900 border-slate-800 text-white placeholder-slate-500' 
              : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400'
          }`}
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim() || !isReady}
          className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-50 transition-colors shadow-md"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
