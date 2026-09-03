'use client';

import React, { useState } from 'react';
import { Check, CreditCard, Sparkles, X } from 'lucide-react';
import axios from 'axios';

interface PricingModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface RazorpayResponse {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

export const PaymentModal: React.FC<PricingModalProps> = ({ isOpen, onClose }) => {
  // Razorpay set as single primary gateway on frontend (Stripe backend preserved)
  const [provider] = useState<'stripe' | 'razorpay'>('razorpay');
  const [loading, setLoading] = useState(false);
  const [userEmail, setUserEmail] = useState('');

  if (!isOpen) return null;

  const handleCheckout = async (planTier: 'solo' | 'team') => {
    if (!userEmail) {
      alert('Please enter your email address for receipt and plan activation.');
      return;
    }

    setLoading(true);
    try {
      if (provider === 'stripe') {
        const res = await axios.post('http://localhost:8000/api/v1/payments/stripe/create-checkout-session', {
          plan_tier: planTier,
          user_email: userEmail,
        });
        if (res.data.checkout_url) {
          window.location.href = res.data.checkout_url;
        }
      } else {
        const amountUsd = planTier === 'solo' ? 79 : 299;
        const orderRes = await axios.post('http://localhost:8000/api/v1/payments/razorpay/create-order', {
          plan_tier: planTier,
          amount_usd: amountUsd,
          user_email: userEmail,
        });

        const options = {
          key: orderRes.data.key_id,
          amount: orderRes.data.amount,
          currency: orderRes.data.currency || 'USD',
          name: 'TraceClause AI',
          description: `${planTier.toUpperCase()} Plan Subscription ($${amountUsd}/mo)`,
          order_id: orderRes.data.order_id,
          handler: async function (response: RazorpayResponse) {
            await axios.post('http://localhost:8000/api/v1/payments/razorpay/verify', {
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
              user_email: userEmail,
            });
            alert('Payment Verified! Your subscription is active.');
            onClose();
          },
          prefill: { email: userEmail },
          theme: { color: '#4f46e5' },
        };

        const rzp = new (window as unknown as { Razorpay: new (opts: unknown) => { open: () => void } }).Razorpay(options);
        rzp.open();
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Server error';
      alert(`Checkout initiation failed: ${message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-3xl w-full p-6 space-y-6 relative shadow-2xl">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-full text-slate-400 hover:text-white bg-slate-800/50"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Title */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-400 text-xs font-semibold border border-indigo-500/20">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Upgrade TraceClause AI</span>
          </div>
          <h3 className="text-2xl font-bold text-white">Choose Your B2B Plan</h3>
          <p className="text-xs text-slate-400">
            Instant subscription access via secure Razorpay checkout (USD).
          </p>
        </div>

        {/* Email Input */}
        <div className="space-y-4 bg-slate-950 p-4 rounded-2xl border border-slate-800">
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">Your Account Email</label>
            <input
              type="email"
              value={userEmail}
              onChange={(e) => setUserEmail(e.target.value)}
              placeholder="alex@company.com"
              className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div className="flex items-center justify-between px-3 py-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-xs text-indigo-300">
            <div className="flex items-center space-x-2">
              <CreditCard className="w-4 h-4 text-indigo-400" />
              <span className="font-semibold">Razorpay Secure Checkout</span>
            </div>
            <span className="font-mono text-[11px] text-indigo-400 font-bold">USD Global</span>
          </div>
        </div>

        {/* Tier Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Solo Tier */}
          <div className="p-5 rounded-2xl bg-slate-950 border border-indigo-500/30 space-y-3 relative flex flex-col justify-between">
            <div className="space-y-3">
              <h4 className="font-bold text-white text-base">Solo Plan</h4>
              <p className="text-2xl font-extrabold text-indigo-400">
                $79 <span className="text-xs font-normal text-slate-400">/ month</span>
              </p>
              <ul className="text-xs text-slate-300 space-y-2">
                <li className="flex items-center space-x-2"><Check className="w-3.5 h-3.5 text-indigo-400" /><span>1 Seat</span></li>
                <li className="flex items-center space-x-2"><Check className="w-3.5 h-3.5 text-indigo-400" /><span>20 Reviews / month</span></li>
                <li className="flex items-center space-x-2"><Check className="w-3.5 h-3.5 text-indigo-400" /><span>AI Redline Counter-Language</span></li>
                <li className="flex items-center space-x-2"><Check className="w-3.5 h-3.5 text-indigo-400" /><span>Interactive RAG Chat</span></li>
                <li className="flex items-center space-x-2"><Check className="w-3.5 h-3.5 text-indigo-400" /><span>Export Redlined Word (.docx)</span></li>
              </ul>
            </div>
            <button
              onClick={() => handleCheckout('solo')}
              disabled={loading}
              className="w-full mt-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition-colors"
            >
              Subscribe to Solo ($79/mo)
            </button>
          </div>

          {/* Team Tier */}
          <div className="p-5 rounded-2xl bg-slate-950 border border-emerald-500/30 space-y-3 relative flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <h4 className="font-bold text-white text-base">Team Plan</h4>
                <span className="bg-emerald-500/10 text-emerald-400 text-[10px] font-bold px-2 py-0.5 rounded-full border border-emerald-500/20">Up to 4 Seats</span>
              </div>
              <p className="text-2xl font-extrabold text-emerald-400">
                $299 <span className="text-xs font-normal text-slate-400">/ month</span>
              </p>
              <ul className="text-xs text-slate-300 space-y-2">
                <li className="flex items-center space-x-2"><Check className="w-3.5 h-3.5 text-emerald-400" /><span>4 Seats included</span></li>
                <li className="flex items-center space-x-2"><Check className="w-3.5 h-3.5 text-emerald-400" /><span>100 Reviews / month (Pooled)</span></li>
                <li className="flex items-center space-x-2"><Check className="w-3.5 h-3.5 text-emerald-400" /><span>Shared Workspace & Reports</span></li>
                <li className="flex items-center space-x-2"><Check className="w-3.5 h-3.5 text-emerald-400" /><span>Custom Playbook Rules</span></li>
                <li className="flex items-center space-x-2"><Check className="w-3.5 h-3.5 text-emerald-400" /><span>Priority Support (&lt;12h SLA)</span></li>
              </ul>
            </div>
            <button
              onClick={() => handleCheckout('team')}
              disabled={loading}
              className="w-full mt-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition-colors"
            >
              Subscribe to Team ($299/mo)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
