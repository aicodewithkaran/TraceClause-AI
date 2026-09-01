# 08. Deployment Runbook & Production Release Strategy

This document outlines step-by-step instructions for deploying the FastAPI backend to Railway/Render and the Next.js frontend to Vercel for **ScanShield AI v2**.

---

## 🚀 Backend Deployment (Railway / Render)

### Option A: Deploying to Railway (Recommended)

1. Connect your GitHub repository to [Railway.app](https://railway.app).
2. Create a new service from GitHub repo ➔ Root directory: `/backend`.
3. Set the start command:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
4. Set Environment Variables in Railway Dashboard:
   - `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `STRIPE_SECRET_KEY`, `ALLOWED_ORIGINS`.
5. Railway provides your backend domain: `https://scanshield-api.up.railway.app`.

---

## 🌐 Frontend Deployment (Vercel)

1. Connect your GitHub repository to [Vercel.com](https://vercel.com).
2. Set Root Directory: `frontend`.
3. Framework Preset: **Next.js**.
4. Set Environment Variables:
   - `NEXT_PUBLIC_API_BASE_URL` = `https://scanshield-api.up.railway.app/api/v1`
   - `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` = `pk_live_...`
5. Click **Deploy**!

---

## 📋 Pre-Launch Production Checklist

- [x] CORS configuration restricts origins strictly to `https://scanshield.vercel.app`.
- [x] Stripe webhook secret verified in production environment.
- [x] Pydantic output validation retries enabled.
- [x] Rate limiting active via Redis / slowapi.
- [x] SSL/TLS active on all backend API endpoints.
- [x] Uptime monitoring active via Better Stack / UptimeRobot.
