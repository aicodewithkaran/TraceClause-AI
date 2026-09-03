'use client';

import React, { useState } from 'react';
import { Check, Sparkles, X, Users, User, ArrowRight, ShieldCheck, Zap } from 'lucide-react';

interface PricingModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const PaymentModal: React.FC<PricingModalProps> = ({ isOpen, onClose }) => {
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleCheckout = (planTier: 'solo' | 'team') => {
    setLoading(true);
    
    // Read hosted Razorpay payment page URLs from environment variables
    const soloLink = process.env.NEXT_PUBLIC_RAZORPAY_SOLO_LINK || 'https://razorpay.com';
    const teamLink = process.env.NEXT_PUBLIC_RAZORPAY_TEAM_LINK || 'https://razorpay.com';
    const targetLink = planTier === 'solo' ? soloLink : teamLink;

    // Redirect user directly to the Razorpay Payment Page
    window.location.href = targetLink;
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-xl flex items-center justify-center p-4 overflow-y-auto">
      {/* Glow ambient background sphere */}
      <div className="absolute w-[600px] h-[600px] bg-purple-600/20 blur-[180px] rounded-full pointer-events-none" />

      <div className="bg-slate-900/90 border border-slate-800/80 rounded-3xl max-w-3xl w-full p-6 lg:p-8 space-y-6 relative shadow-2xl backdrop-blur-2xl text-slate-100 my-auto">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-2 rounded-full text-slate-400 hover:text-white bg-slate-800/60 hover:bg-slate-800 border border-slate-700/50 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Header */}
        <div className="text-center space-y-2 max-w-xl mx-auto">
          <div className="inline-flex items-center space-x-1.5 px-3.5 py-1 rounded-full bg-gradient-to-r from-purple-500/10 via-indigo-500/10 to-purple-500/10 text-purple-400 text-xs font-bold border border-purple-500/20 shadow-sm">
            <Sparkles className="w-3.5 h-3.5 text-purple-400" />
            <span>Launch Special Pricing — Limited Time</span>
          </div>
          <h3 className="text-3xl font-black tracking-tight text-white">
            Supercharge Your Legal Audits
          </h3>
          <p className="text-xs text-slate-400 leading-relaxed">
            Choose the plan that fits your monthly contract review volume. Instant activation via secure Razorpay checkout.
          </p>
        </div>

        {/* Pricing Cards Grid (Awwwards Web3 Dark Theme Inspired) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
          
          {/* ================= SOLO PLAN CARD ================= */}
          <div className="p-6 rounded-3xl bg-slate-950/80 border border-slate-800 hover:border-indigo-500/40 transition-all duration-300 relative flex flex-col justify-between group shadow-xl">
            {/* Ambient inner glow */}
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/5 blur-3xl rounded-full pointer-events-none" />

            <div className="space-y-4 relative z-10">
              {/* Header & Badges */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                      <User className="w-4 h-4" />
                    </div>
                    <h4 className="font-extrabold text-white text-lg">Solo Plan</h4>
                  </div>
                  <span className="text-[11px] font-mono text-slate-400 bg-slate-900 px-2.5 py-1 rounded-full border border-slate-800 flex items-center space-x-1">
                    <span>1 User Seat</span>
                  </span>
                </div>

                {/* Animated Launch Special Badge */}
                <div>
                  <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-gradient-to-r from-amber-500/20 via-orange-500/20 to-amber-500/20 text-amber-400 border border-amber-500/30 animate-pulse shadow-sm shadow-amber-500/10">
                    <Zap className="w-3 h-3 text-amber-400 fill-amber-400" />
                    <span>Save 34% (Launch Special)</span>
                  </span>
                </div>
              </div>

              {/* Price Anchoring & Strikethrough */}
              <div className="pt-2">
                <div className="flex items-baseline space-x-2">
                  <span className="text-slate-500 line-through text-sm font-semibold tracking-wider">
                    $119/mo
                  </span>
                  <span className="text-3xl font-black text-white tracking-tight">
                    $79
                  </span>
                  <span className="text-xs text-slate-400 font-medium">/ month</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1">
                  Ideal for solo practitioners, attorneys & consultants.
                </p>
              </div>

              <div className="h-px bg-slate-800/80 my-3" />

              {/* Features List */}
              <ul className="text-xs text-slate-300 space-y-2.5">
                <li className="flex items-center space-x-2.5">
                  <Check className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span className="font-medium">20 Contract Audits / month</span>
                </li>
                <li className="flex items-center space-x-2.5">
                  <Check className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>AI Redline Counter-Language</span>
                </li>
                <li className="flex items-center space-x-2.5">
                  <Check className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>Interactive RAG Contract Chat</span>
                </li>
                <li className="flex items-center space-x-2.5">
                  <Check className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>Export Redlined Word (.docx)</span>
                </li>
                <li className="flex items-center space-x-2.5">
                  <Check className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>Standard Email Support (24-48h)</span>
                </li>
              </ul>
            </div>

            {/* CTA Button */}
            <button
              onClick={() => handleCheckout('solo')}
              disabled={loading}
              className="w-full mt-6 py-3.5 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition-all shadow-lg shadow-indigo-600/25 hover:shadow-indigo-600/40 hover:scale-[1.02] flex items-center justify-center space-x-2"
            >
              <span>Choose Solo Plan ($79/mo)</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>

          {/* ================= TEAM PLAN CARD (FEATURED / MOST POPULAR) ================= */}
          <div className="p-6 rounded-3xl bg-gradient-to-b from-slate-900 via-slate-950 to-slate-950 border-2 border-purple-500/50 hover:border-purple-400 transition-all duration-300 relative flex flex-col justify-between group shadow-2xl shadow-purple-500/15 scale-[1.02]">
            
            {/* Floating "Most Popular" Pill Badge */}
            <div className="absolute -top-3.5 right-6">
              <span className="px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest bg-gradient-to-r from-purple-600 to-indigo-600 text-white border border-purple-400/40 shadow-lg shadow-purple-500/30 flex items-center space-x-1">
                <Sparkles className="w-3 h-3 text-amber-300 fill-amber-300" />
                <span>Most Popular</span>
              </span>
            </div>

            {/* Top Glowing Ambient Sphere */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-48 h-24 bg-purple-500/15 blur-2xl rounded-full pointer-events-none" />

            <div className="space-y-4 relative z-10">
              {/* Header & Badges */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <div className="p-2 rounded-xl bg-purple-500/15 text-purple-400 border border-purple-500/30">
                      <Users className="w-4 h-4" />
                    </div>
                    <h4 className="font-extrabold text-white text-lg">Team Plan</h4>
                  </div>
                  <span className="text-[11px] font-mono font-bold text-purple-300 bg-purple-500/10 px-2.5 py-1 rounded-full border border-purple-500/30 flex items-center space-x-1">
                    <span>Up to 4 User Seats</span>
                  </span>
                </div>

                {/* Animated Founder Tier Badge */}
                <div>
                  <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-gradient-to-r from-purple-500/25 via-indigo-500/25 to-purple-500/25 text-purple-300 border border-purple-500/40 animate-pulse shadow-sm shadow-purple-500/20">
                    <ShieldCheck className="w-3 h-3 text-purple-300" />
                    <span>Save 25% (Founder Tier)</span>
                  </span>
                </div>
              </div>

              {/* Price Anchoring & Strikethrough */}
              <div className="pt-2">
                <div className="flex items-baseline space-x-2">
                  <span className="text-slate-500 line-through text-sm font-semibold tracking-wider">
                    $399/mo
                  </span>
                  <span className="text-3xl font-black text-white tracking-tight">
                    $299
                  </span>
                  <span className="text-xs text-purple-300 font-medium">/ month</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1">
                  Built for legal teams, law firms & corporate procurement.
                </p>
              </div>

              <div className="h-px bg-slate-800/80 my-3" />

              {/* Features List */}
              <ul className="text-xs text-slate-200 space-y-2.5">
                <li className="flex items-center space-x-2.5 font-semibold text-white">
                  <Check className="w-4 h-4 text-purple-400 flex-shrink-0" />
                  <span>4 User Seats included</span>
                </li>
                <li className="flex items-center space-x-2.5 font-semibold text-white">
                  <Check className="w-4 h-4 text-purple-400 flex-shrink-0" />
                  <span>100 Contract Audits / month (Pooled)</span>
                </li>
                <li className="flex items-center space-x-2.5">
                  <Check className="w-4 h-4 text-purple-400 flex-shrink-0" />
                  <span>Shared Team Workspace & Reports</span>
                </li>
                <li className="flex items-center space-x-2.5">
                  <Check className="w-4 h-4 text-purple-400 flex-shrink-0" />
                  <span>Custom Playbook Risk Rules</span>
                </li>
                <li className="flex items-center space-x-2.5">
                  <Check className="w-4 h-4 text-purple-400 flex-shrink-0" />
                  <span>Priority SLA Support (&lt;12h Response)</span>
                </li>
              </ul>
            </div>

            {/* Glowing Orange/Purple CTA Button (inspired by reference image) */}
            <button
              onClick={() => handleCheckout('team')}
              disabled={loading}
              className="w-full mt-6 py-3.5 rounded-2xl bg-gradient-to-r from-orange-500 via-amber-500 to-orange-600 hover:from-orange-400 hover:to-amber-500 text-white font-black text-xs transition-all shadow-xl shadow-orange-500/25 hover:shadow-orange-500/40 hover:scale-[1.02] flex items-center justify-center space-x-2"
            >
              <span>Choose Team Plan ($299/mo)</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>

        </div>
      </div>
    </div>
  );
};
