'use client';

import React, { useState } from 'react';
import { Check, Sparkles, X, Users, User, ArrowRight, ShieldCheck, Zap, Loader2 } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { apiClient } from '@/lib/api-client';

interface PricingModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const PaymentModal: React.FC<PricingModalProps> = ({ isOpen, onClose }) => {
  const { user, profile, refreshProfile } = useAuth();
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const loadRazorpayScript = (): Promise<boolean> => {
    return new Promise((resolve) => {
      if (typeof window !== 'undefined' && (window as any).Razorpay) {
        resolve(true);
        return;
      }
      const script = document.createElement('script');
      script.src = 'https://checkout.razorpay.com/v1/checkout.js';
      script.async = true;
      script.onload = () => resolve(true);
      script.onerror = () => resolve(false);
      document.body.appendChild(script);
    });
  };

  const handleCheckout = async (planTier: 'solo' | 'team') => {
    setErrorMsg(null);
    setLoading(true);

    try {
      if (!user) {
        throw new Error('Please sign in to upgrade your subscription.');
      }

      // 1. Ensure Razorpay Checkout script is loaded
      const isScriptLoaded = await loadRazorpayScript();
      if (!isScriptLoaded) {
        throw new Error('Unable to connect to Razorpay checkout. Please check your internet connection.');
      }

      // 2. Request Authoritative Server-Priced Order
      const order = await apiClient.createRazorpayOrder(planTier);

      // 3. Open Razorpay In-App Standard Modal
      const options = {
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        name: 'TraceClause AI',
        description: `${planTier.toUpperCase()} Plan (30-Day Contract Audit Access)`,
        order_id: order.order_id,
        prefill: {
          name: profile?.full_name || 'Legal Professional',
          email: user.email || '',
          contact: profile?.phone_number || ''
        },
        theme: {
          color: planTier === 'team' ? '#f97316' : '#6366f1'
        },
        modal: {
          ondismiss: () => {
            setLoading(false);
          }
        },
        handler: async (response: any) => {
          try {
            // 4. Verify Payment on Backend
            const verification = await apiClient.verifyRazorpayCheckout({
              purchase_id: order.purchase_id,
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature
            });

            if (verification.success) {
              await refreshProfile();
              onClose();
            } else {
              setErrorMsg(verification.message || 'Payment verification failed. Please contact support.');
            }
          } catch (verifyErr: any) {
            setErrorMsg(verifyErr?.response?.data?.detail || 'Verification error occurred. Please contact support.');
          } finally {
            setLoading(false);
          }
        }
      };

      const rzpInstance = new (window as any).Razorpay(options);
      rzpInstance.on('payment.failed', (failRes: any) => {
        setErrorMsg(`Payment failed: ${failRes.error?.description || 'Transaction declined'}`);
        setLoading(false);
      });
      rzpInstance.open();
    } catch (err: any) {
      setErrorMsg(err?.response?.data?.detail || err.message || 'Failed to initiate checkout.');
      setLoading(false);
    }
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
            <span>Launch Special Pricing — 30-Day Access Pass</span>
          </div>
          <h3 className="text-3xl font-black tracking-tight text-white">
            Supercharge Your Legal Audits
          </h3>
          <p className="text-xs text-slate-400 leading-relaxed">
            Choose the plan that fits your review volume. Instant activation via secure in-app Razorpay checkout.
          </p>

          {errorMsg && (
            <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium">
              {errorMsg}
            </div>
          )}
        </div>

        {/* Pricing Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
          
          {/* ================= SOLO PLAN CARD ================= */}
          <div className="p-6 rounded-3xl bg-slate-950/80 border border-slate-800 hover:border-indigo-500/40 transition-all duration-300 relative flex flex-col justify-between group shadow-xl">
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/5 blur-3xl rounded-full pointer-events-none" />

            <div className="space-y-4 relative z-10">
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

                <div>
                  <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-gradient-to-r from-amber-500/20 via-orange-500/20 to-amber-500/20 text-amber-400 border border-amber-500/30 animate-pulse shadow-sm shadow-amber-500/10">
                    <Zap className="w-3 h-3 text-amber-400 fill-amber-400" />
                    <span>Save 34% (Launch Special)</span>
                  </span>
                </div>
              </div>

              <div className="pt-2">
                <div className="flex items-baseline space-x-2">
                  <span className="text-slate-500 line-through text-sm font-semibold tracking-wider">
                    $119/mo
                  </span>
                  <span className="text-3xl font-black text-white tracking-tight">
                    $79
                  </span>
                  <span className="text-xs text-slate-400 font-medium">/ 30 days</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1">
                  Ideal for solo practitioners, attorneys & consultants.
                </p>
              </div>

              <div className="h-px bg-slate-800/80 my-3" />

              <ul className="text-xs text-slate-300 space-y-2.5">
                <li className="flex items-center space-x-2.5 font-semibold text-white">
                  <Check className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>20 Contract Audits / month</span>
                </li>
                <li className="flex items-center space-x-2.5">
                  <Check className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>1 User Seat</span>
                </li>
                <li className="flex items-center space-x-2.5">
                  <Check className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>AI Redlines & Counter-proposals</span>
                </li>
                <li className="flex items-center space-x-2.5">
                  <Check className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>Grounded RAG Interactive Chat</span>
                </li>
                <li className="flex items-center space-x-2.5">
                  <Check className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>Native Word (.docx) Redline Export</span>
                </li>
              </ul>
            </div>

            <button
              onClick={() => handleCheckout('solo')}
              disabled={loading}
              className="w-full mt-6 py-3.5 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white font-black text-xs transition-all shadow-xl shadow-indigo-600/25 hover:shadow-indigo-600/40 hover:scale-[1.02] flex items-center justify-center space-x-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Connecting Secure Checkout...</span>
                </>
              ) : (
                <>
                  <span>Choose Solo Plan ($79)</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>

          {/* ================= TEAM PLAN CARD ================= */}
          <div className="p-6 rounded-3xl bg-slate-950/90 border-2 border-purple-500/50 hover:border-purple-400 transition-all duration-300 relative flex flex-col justify-between group shadow-2xl shadow-purple-500/10">
            <div className="absolute -top-3.5 right-6">
              <span className="px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-lg shadow-purple-500/30 border border-purple-400/30">
                Most Popular
              </span>
            </div>

            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-48 h-24 bg-purple-500/15 blur-2xl rounded-full pointer-events-none" />

            <div className="space-y-4 relative z-10">
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

                <div>
                  <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-gradient-to-r from-purple-500/25 via-indigo-500/25 to-purple-500/25 text-purple-300 border border-purple-500/40 animate-pulse shadow-sm shadow-purple-500/20">
                    <ShieldCheck className="w-3 h-3 text-purple-300" />
                    <span>Save 25% (Founder Tier)</span>
                  </span>
                </div>
              </div>

              <div className="pt-2">
                <div className="flex items-baseline space-x-2">
                  <span className="text-slate-500 line-through text-sm font-semibold tracking-wider">
                    $399/mo
                  </span>
                  <span className="text-3xl font-black text-white tracking-tight">
                    $299
                  </span>
                  <span className="text-xs text-purple-300 font-medium">/ 30 days</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1">
                  Built for legal teams, law firms & corporate procurement.
                </p>
              </div>

              <div className="h-px bg-slate-800/80 my-3" />

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

            <button
              onClick={() => handleCheckout('team')}
              disabled={loading}
              className="w-full mt-6 py-3.5 rounded-2xl bg-gradient-to-r from-orange-500 via-amber-500 to-orange-600 hover:from-orange-400 hover:to-amber-500 text-white font-black text-xs transition-all shadow-xl shadow-orange-500/25 hover:shadow-orange-500/40 hover:scale-[1.02] flex items-center justify-center space-x-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Connecting Secure Checkout...</span>
                </>
              ) : (
                <>
                  <span>Choose Team Plan ($299)</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>

        </div>
      </div>
    </div>
  );
};
