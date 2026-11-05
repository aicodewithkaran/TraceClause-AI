'use client';

import React, { useEffect } from 'react';
import { AuthView } from './AuthView';
import { X } from 'lucide-react';
import { useTheme } from '@/context/ThemeContext';
import { useAuth } from '@/context/AuthContext';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialMode?: 'signin' | 'signup';
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, initialMode }) => {
  const { theme } = useTheme();
  const { user } = useAuth();
  const isDark = theme === 'dark';

  // Automatically close modal as soon as user authentication succeeds
  useEffect(() => {
    if (user && isOpen) {
      onClose();
    }
  }, [user, isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 lg:p-6 overflow-y-auto">
      <div className={`relative w-full max-w-7xl rounded-3xl overflow-hidden shadow-2xl border ${
        isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'
      }`}>
        <button
          onClick={onClose}
          className={`absolute top-4 right-4 z-50 p-2 rounded-full border transition-colors ${
            isDark ? 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white' : 'bg-slate-100 border-slate-200 text-slate-600 hover:text-slate-900'
          }`}
        >
          <X className="w-4 h-4" />
        </button>
        <AuthView onSuccess={onClose} initialMode={initialMode} />
      </div>
    </div>
  );
};
