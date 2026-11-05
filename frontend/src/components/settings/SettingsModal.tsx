'use client';

import React, { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { supabase } from '@/lib/supabase';
import { 
  X, 
  User, 
  Mail, 
  Globe, 
  Briefcase, 
  KeyRound, 
  Trash2, 
  ShieldAlert, 
  Check, 
  Loader2, 
  Sparkles,
  AlertTriangle,
  Lock
} from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const { user, profile, logout, refreshProfile } = useAuth();
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const [activeTab, setActiveTab] = useState<'profile' | 'security' | 'danger'>('profile');
  
  // Profile Form States
  const [fullName, setFullName] = useState(profile?.full_name || '');
  const [profession, setProfession] = useState(profile?.profession || '');
  const [profileMessage, setProfileMessage] = useState<string | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);

  // Password Update States
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordLoading, setPasswordLoading] = useState(false);

  // Danger Zone States
  const [deleteConfirmationInput, setDeleteConfirmationInput] = useState('');
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [dangerError, setDangerError] = useState<string | null>(null);

  if (!isOpen) return null;

  const currentTier = (profile?.subscription_tier || 'free').toLowerCase();

  // Tier Matrix Setup
  let tierLimit = 3;
  let tierLabel = 'Free Trial Tier (3 Audits)';
  let usageLabel = 'Lifetime Free Audits Used:';
  let usageCount = profile?.lifetime_free_audits_used ?? profile?.weekly_quota_used ?? 0;

  if (currentTier === 'solo') {
    tierLimit = 20;
    tierLabel = 'Solo Plan ($79/mo)';
    usageLabel = 'Monthly Review Usage:';
    usageCount = profile?.monthly_quota_used || 0;
  } else if (currentTier === 'team') {
    tierLimit = 100;
    tierLabel = 'Team Plan ($299/mo)';
    usageLabel = 'Monthly Review Usage:';
    usageCount = profile?.monthly_quota_used || 0;
  }

  const isUnlimited = currentTier === 'enterprise';

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileMessage(null);
    setProfileLoading(true);

    try {
      if (user) {
        await supabase.auth.updateUser({
          data: { full_name: fullName, profession }
        });

        await supabase.from('profiles').update({
          full_name: fullName,
          profession,
        }).eq('id', user.id);

        await refreshProfile();
        setProfileMessage('Profile details updated successfully!');
      }
    } catch {
      setProfileMessage('Failed to update profile.');
    } finally {
      setProfileLoading(false);
    }
  };

  const handleUpdatePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordMessage(null);
    setPasswordError(null);

    if (newPassword.length < 6) {
      setPasswordError('Password must be at least 6 characters.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError('Passwords do not match.');
      return;
    }

    setPasswordLoading(true);
    try {
      const { error } = await supabase.auth.updateUser({ password: newPassword });
      if (error) throw error;

      setPasswordMessage('Password updated successfully!');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update password.';
      setPasswordError(message);
    } finally {
      setPasswordLoading(false);
    }
  };

  const handleClearHistory = async () => {
    if (!user) return;
    if (confirm('Are you sure you want to delete all contract report history? This action cannot be undone.')) {
      try {
        await supabase.from('contract_reports').delete().eq('user_id', user.id);
        alert('All report history cleared.');
      } catch {
        alert('Failed to clear history.');
      }
    }
  };

  const handleDeleteAccount = async () => {
    if (deleteConfirmationInput !== 'DELETE MY ACCOUNT') {
      setDangerError('Please type "DELETE MY ACCOUNT" exactly to confirm deletion.');
      return;
    }

    setDeleteLoading(true);
    setDangerError(null);

    try {
      if (user) {
        // Call backend API to permanently purge user from Supabase Auth & database
        const { apiClient } = await import('@/lib/api-client');
        await apiClient.deleteAccount();

        // Delete user's report history & profile from database as extra precaution
        await supabase.from('contract_reports').delete().eq('user_id', user.id);
        await supabase.from('profiles').delete().eq('id', user.id);
        
        // Clear all cached storage & auth sessions
        localStorage.clear();
        sessionStorage.clear();
        await supabase.auth.signOut();
        await logout();
        
        onClose();
        alert('Your account and all associated data have been permanently deleted.');
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete account. Please contact support.';
      setDangerError(message);
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className={`rounded-3xl max-w-2xl w-full p-6 space-y-6 relative shadow-2xl border transition-all ${
        isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'
      }`}>
        {/* Close Button */}
        <button
          onClick={onClose}
          className={`absolute top-5 right-5 p-2 rounded-full border transition-colors ${
            isDark ? 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white' : 'bg-slate-100 border-slate-200 text-slate-600 hover:text-slate-900'
          }`}
        >
          <X className="w-4 h-4" />
        </button>

        {/* Modal Header */}
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-5 h-5 text-indigo-500" />
            <h3 className={`text-xl font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Account & Platform Settings</h3>
          </div>
          <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            Manage your profile details, password security, quota tier, and data privacy options.
          </p>
        </div>

        {/* Tab Selection Navigation */}
        <div className={`grid grid-cols-3 gap-1 p-1 rounded-xl border text-xs font-bold ${
          isDark ? 'bg-slate-950 border-slate-800' : 'bg-slate-100 border-slate-200'
        }`}>
          <button
            onClick={() => setActiveTab('profile')}
            className={`py-2 rounded-lg transition-all ${
              activeTab === 'profile' 
                ? 'bg-indigo-600 text-white shadow-md' 
                : isDark ? 'text-slate-400 hover:text-white' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            My Profile
          </button>

          <button
            onClick={() => setActiveTab('security')}
            className={`py-2 rounded-lg transition-all ${
              activeTab === 'security' 
                ? 'bg-indigo-600 text-white shadow-md' 
                : isDark ? 'text-slate-400 hover:text-white' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Security & Password
          </button>

          <button
            onClick={() => setActiveTab('danger')}
            className={`py-2 rounded-lg transition-all ${
              activeTab === 'danger' 
                ? 'bg-red-600 text-white shadow-md' 
                : isDark ? 'text-slate-400 hover:text-white' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Danger Zone
          </button>
        </div>

        {/* TAB 1: PROFILE & QUOTA */}
        {activeTab === 'profile' && (
          <form onSubmit={handleUpdateProfile} className="space-y-4 text-xs">
            {/* Subscription & Quota Card */}
            <div className={`p-4 rounded-2xl border space-y-2.5 ${
              isDark ? 'bg-slate-950 border-slate-800' : 'bg-slate-50 border-slate-200'
            }`}>
              <div className="flex items-center justify-between">
                <span className="font-bold uppercase text-[10px] tracking-wider text-slate-400">Subscription Tier</span>
                <span className="px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-500 border border-indigo-500/20 font-mono font-bold uppercase text-[10px]">
                  {tierLabel}
                </span>
              </div>

              {/* Progress Quota Bar */}
              <div className="space-y-1">
                <div className="flex justify-between text-[11px]">
                  <span className={isDark ? 'text-slate-300' : 'text-slate-600'}>{usageLabel}</span>
                  <span className="font-bold font-mono text-indigo-500">
                    {usageCount} / {isUnlimited ? 'Unlimited' : tierLimit}
                  </span>
                </div>
                {!isUnlimited && (
                  <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                    <div 
                      className="h-full bg-indigo-500 transition-all duration-500"
                      style={{ width: `${Math.min((usageCount / tierLimit) * 100, 100)}%` }}
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Email (Disabled) */}
            <div>
              <label className={`font-semibold block mb-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>Email Address</label>
              <div className="relative">
                <Mail className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="email"
                  disabled
                  value={profile?.email || user?.email || ''}
                  className={`w-full pl-9 pr-3 py-2.5 rounded-xl border opacity-60 cursor-not-allowed ${
                    isDark ? 'bg-slate-950 border-slate-800 text-slate-400' : 'bg-slate-100 border-slate-300 text-slate-600'
                  }`}
                />
              </div>
            </div>

            {/* Full Name */}
            <div>
              <label className={`font-semibold block mb-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>Full Name</label>
              <div className="relative">
                <User className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className={`w-full pl-9 pr-3 py-2.5 rounded-xl border focus:outline-none focus:border-indigo-500 ${
                    isDark ? 'bg-slate-950 border-slate-800 text-white' : 'bg-slate-50 border-slate-300 text-slate-900'
                  }`}
                />
              </div>
            </div>

            {/* Country (Read-Only) */}
            <div>
              <label className={`font-semibold block mb-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>Country</label>
              <div className="relative">
                <Globe className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  disabled
                  value={profile?.country || 'Global'}
                  className={`w-full pl-9 pr-3 py-2.5 rounded-xl border opacity-60 cursor-not-allowed ${
                    isDark ? 'bg-slate-950 border-slate-800 text-slate-400' : 'bg-slate-100 border-slate-300 text-slate-600'
                  }`}
                />
              </div>
            </div>

            {/* Profession */}
            <div>
              <label className={`font-semibold block mb-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>Profession / Role</label>
              <div className="relative">
                <Briefcase className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  value={profession}
                  onChange={(e) => setProfession(e.target.value)}
                  placeholder="e.g. Legal Counsel"
                  className={`w-full pl-9 pr-3 py-2.5 rounded-xl border focus:outline-none focus:border-indigo-500 ${
                    isDark ? 'bg-slate-950 border-slate-800 text-white' : 'bg-slate-50 border-slate-300 text-slate-900'
                  }`}
                />
              </div>
            </div>

            {profileMessage && (
              <p className="text-emerald-400 text-[11px] font-semibold flex items-center space-x-1">
                <Check className="w-4 h-4" /> <span>{profileMessage}</span>
              </p>
            )}

            <button
              type="submit"
              disabled={profileLoading}
              className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition-colors flex items-center justify-center space-x-2 shadow-md"
            >
              {profileLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <span>Save Profile Changes</span>}
            </button>
          </form>
        )}

        {/* TAB 2: SECURITY & PASSWORD */}
        {activeTab === 'security' && (
          <form onSubmit={handleUpdatePassword} className="space-y-4 text-xs">
            <div className={`p-4 rounded-2xl border space-y-1 ${
              isDark ? 'bg-slate-950 border-slate-800' : 'bg-slate-50 border-slate-200'
            }`}>
              <h4 className={`font-bold flex items-center space-x-1.5 ${isDark ? 'text-white' : 'text-slate-900'}`}>
                <Lock className="w-4 h-4 text-indigo-500" /> <span>Update Password</span>
              </h4>
              <p className={`text-[11px] ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                Enter your new account password below. Minimum length is 6 characters.
              </p>
            </div>

            <div>
              <label className={`font-semibold block mb-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>New Password</label>
              <div className="relative">
                <KeyRound className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••"
                  className={`w-full pl-9 pr-3 py-2.5 rounded-xl border focus:outline-none focus:border-indigo-500 ${
                    isDark ? 'bg-slate-950 border-slate-800 text-white' : 'bg-slate-50 border-slate-300 text-slate-900'
                  }`}
                />
              </div>
            </div>

            <div>
              <label className={`font-semibold block mb-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>Confirm New Password</label>
              <div className="relative">
                <KeyRound className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  className={`w-full pl-9 pr-3 py-2.5 rounded-xl border focus:outline-none focus:border-indigo-500 ${
                    isDark ? 'bg-slate-950 border-slate-800 text-white' : 'bg-slate-50 border-slate-300 text-slate-900'
                  }`}
                />
              </div>
            </div>

            {passwordMessage && (
              <p className="text-emerald-400 text-[11px] font-semibold flex items-center space-x-1">
                <Check className="w-4 h-4" /> <span>{passwordMessage}</span>
              </p>
            )}

            {passwordError && (
              <p className="text-red-400 text-[11px] font-semibold flex items-center space-x-1">
                <AlertTriangle className="w-4 h-4" /> <span>{passwordError}</span>
              </p>
            )}

            <button
              type="submit"
              disabled={passwordLoading}
              className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition-colors flex items-center justify-center space-x-2 shadow-md"
            >
              {passwordLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <span>Update Password</span>}
            </button>
          </form>
        )}

        {/* TAB 3: DANGER ZONE */}
        {activeTab === 'danger' && (
          <div className="space-y-5 text-xs">
            <div className={`p-4 rounded-2xl border space-y-3 ${
              isDark ? 'bg-slate-950 border-slate-800' : 'bg-slate-50 border-slate-200'
            }`}>
              <div>
                <h4 className={`font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Clear Contract History</h4>
                <p className={`text-[11px] ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  Deletes all saved analysis redlines and contract metadata from your account history.
                </p>
              </div>
              <button
                onClick={handleClearHistory}
                className="px-4 py-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 hover:bg-amber-500/20 font-bold text-xs transition-colors"
              >
                Clear Report History
              </button>
            </div>

            <div className="p-4 rounded-2xl border border-red-500/30 bg-red-500/10 space-y-3">
              <div>
                <h4 className="font-bold text-red-400 flex items-center space-x-1.5">
                  <ShieldAlert className="w-4 h-4" /> <span>Permanent Account Deletion</span>
                </h4>
                <p className="text-[11px] text-red-300/80 leading-relaxed mt-1">
                  This action cannot be undone. All your user profile data, contract reports, and vector embeddings will be permanently purged.
                </p>
              </div>

              <div className="space-y-1.5 pt-1">
                <label className="text-[11px] font-bold text-red-300 block">
                  To confirm deletion, please type <span className="underline font-mono text-white">DELETE MY ACCOUNT</span> below:
                </label>
                <input
                  type="text"
                  value={deleteConfirmationInput}
                  onChange={(e) => setDeleteConfirmationInput(e.target.value)}
                  placeholder="DELETE MY ACCOUNT"
                  className={`w-full px-3 py-2 rounded-xl border focus:outline-none text-xs font-mono font-bold ${
                    isDark ? 'bg-slate-950 border-red-500/40 text-white placeholder-slate-600' : 'bg-white border-red-300 text-slate-900'
                  }`}
                />
              </div>

              {dangerError && (
                <p className="text-red-400 text-[11px] font-semibold flex items-center space-x-1">
                  <AlertTriangle className="w-4 h-4" /> <span>{dangerError}</span>
                </p>
              )}

              <button
                onClick={handleDeleteAccount}
                disabled={deleteConfirmationInput !== 'DELETE MY ACCOUNT' || deleteLoading}
                className="w-full py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-white font-bold text-xs transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center space-x-2 shadow-lg shadow-red-600/20"
              >
                {deleteLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Trash2 className="w-4 h-4" /><span>Permanently Delete My Account</span></>}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
