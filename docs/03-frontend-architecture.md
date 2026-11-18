# SECTION 1: SYSTEM OVERVIEW & ARCHITECTURAL EVOLUTION
* **High-Level Purpose**: TraceClause AI v2 Frontend delivers an interactive split-screen legal contract audit dashboard, Audit Vault history viewer, inline authentication popups (`AuthModal.tsx`), 70:30 USP split auth view, interactive 3D mouse parallax graphics, dark glassmorphic pricing modal with Razorpay payment link integration, live quota badge tracking, and a settings modal with safe account deletion.
* **Module Matrix (Version History)**:

| Frontend Feature | Version 1.0 (ScanShield Legacy) | Version 2.0 (TraceClause AI Current) |
| :--- | :--- | :--- |
| **Framework Engine** | Single-page HTML/React | Next.js 16 (App Router + Turbopack + Node 24) |
| **Auth Experience** | None (Public access) | 70:30 USP Split Screen + Interactive 3D Parallax Graphic + **Inline `AuthModal.tsx`** |
| **Audit Vault Viewer**| None | Live Audit History Drawer (`page.tsx` displaying saved Supabase contract reports) |
| **Pricing & Monetization** | Single generic modal | Dark Glassmorphic B2B Modal: Solo ($79/mo) & Team ($299/mo) + **Razorpay Payment Link Integration** + Animated Strikethrough Badges |
| **Feature Tier Locks** | None | Locked RAG drawer, locked `.docx` export button, and blur filter over counter-language on Free trial |
| **Quota Badge Display** | Weekly quota counter | **Live Quota Tracking Badge**: Displays dynamic usage (`{quota_used}/{limit}` audits remaining) across Free, Solo, and Team tiers |
| **Settings Modal** | None | Multi-Tab (Profile, Password, Live Quota Status, Safe Account Delete) |
| **Real User Display** | Hardcoded "ScanShield User" | Dynamic resolution of user signup `full_name` |
| **Global Background** | Static plain background | High-DPI Interactive Cursor Spotlight & Parallax Grid Canvas (`GlobalBackgroundCanvas.tsx`) |

---

# SECTION 2: DEEP DIVE - MODULE VERSION 2.0 (TRACECLAUSE AI FRONTEND ARCHITECTURE)

### Component: Next.js App Router UI & Interactive State Layer

* **Functional Description**: Coordinates client-side authentication views, inline auth modal (`AuthModal.tsx`), drag-and-drop file ingestion, split-screen redline preview, Audit Vault history drawer, feature-gated component locks (RAG, Word Export, Redline Blur), 2-tier pricing checkout with Razorpay payment link integration, live quota tracking, settings modal configuration, and global ambient motion graphics.
* **Technical Specs & Capabilities**:
  - **Framework Stack**: Next.js 16.3, React 19, Tailwind CSS v3, Framer Motion, Lucide Icons.
  - **Node.js Environment**: Node.js v24.20.0 LTS (`npm v11.19.0`).
  - **Package Isolation**: All dependencies stored locally in `/frontend/node_modules/`.

* **Detailed Input/Output Data Dictionary**:

#### UI State Store (`AuthContext` & `page.tsx` state)
| State Field Name | Data Type | Description | Default Value / Constraints |
| :--- | :--- | :--- | :--- |
| `user` | `User \| null` | Supabase auth user object | `null` |
| `profile` | `UserProfile \| null` | User metadata (Name, Profession, Quota) | `null` |
| `theme` | `string` | Theme preference (`'dark'` / `'light'`) | `'dark'` |
| `quotaInfo` | `QuotaInfo \| null` | Live quota metrics (`quota_used`, `limit`, `tier`, `remaining`) | Auto-updated on analysis |
| `auditHistory` | `ContractReport[]` | Saved Audit Vault history reports | Fetched from `/api/v1/contract/my-reports` |
| `isAuthModalOpen` | `boolean` | State for inline authentication popup | `false` |

* **Under-the-Hood Logic & Computations**:
  1. **Dynamic User Display Name**: `AuthContext` retrieves `user.user_metadata?.full_name`. If absent, it reads `profile.full_name` or falls back to email username (`user.email.split('@')[0]`).
  2. **Live Quota Tracking Badge**: Displayed in top navigation bar and settings modal. Automatically updates whenever an audit is completed.
     - **Free Tier**: Displays `Free Audits Remaining: {3 - lifetime_free_audits_used}/3`.
     - **Solo Tier**: Displays `Solo Plan: {monthly_quota_used}/20 audits used`.
     - **Team Tier**: Displays `Team Workspace: {monthly_quota_used}/100 audits used`.
  3. **Audit Vault History Drawer**: Clicking "Audit History" in `page.tsx` triggers `UserIsolationService.get_user_reports`, loading previously analyzed contract reports from Supabase into the split-screen view.
  4. **Inline Auth Modal (`AuthModal.tsx`)**: Allows guest users to sign in or create an account mid-workflow without losing uploaded contract state.
  5. **Tier-Based UI Feature Gating**:
     - **Free Tier (`subscription_tier === 'free'`)**: RAG drawer presents lock banner (`"Upgrade to Solo or Team to chat with this contract"`). Word `.docx` export button is disabled with upgrade tooltip. AI redline counter-language text is masked with a blur filter (`filter: blur(4px)`) and an `"Unlock Redlines"` button opening `PaymentModal`.
     - **Solo & Team Tiers**: Unlocks AI redlines, interactive RAG chat drawer, and native `.docx` report exports. Team tier additionally enables shared workspace management and custom playbook rules.
  6. **Dark Glassmorphic Pricing Modal & Razorpay Payment Links**: Features high-DPI glassmorphism, animated strikethrough badges showing percentage savings, USD/INR currency toggle ($79 / ₹7,499 Solo; $299 / ₹27,999 Team), and direct Razorpay payment link integration (`NEXT_PUBLIC_RAZORPAY_KEY_ID`).
  7. **Interactive Parallax Cursor Spotlight**: `GlobalBackgroundCanvas.tsx` listens for global `mousemove` events and applies `framer-motion` springs (`stiffness: 60, damping: 25`) to animate a `600px` radial light sphere and multi-layer parallax orbs.
  8. **Safe Account Deletion**: Inside `SettingsModal.tsx`, permanent account deletion strictly requires matching string verification (`deleteConfirmationInput === 'DELETE MY ACCOUNT'`).

* **Complete Error Handling & Self-Healing Registry**:

| Error Code | HTTP Status | Component | Trigger Condition | Exception Message | Why this HTTP code | Framework Trap / Code Guard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ERR_AUTH_SIGNUP` | 400 | AuthView / AuthModal | Mandatory signup field blank | `Please fill in all mandatory fields (*)` | Bad Request | Form validation guard |
| `ERR_FEATURE_LOCKED`| 403 | Review / RAG | Free user accessing paid feature | `Access denied: requires Solo or Team plan.` | Forbidden | Opens upgrade `PaymentModal` |
| `ERR_QUOTA_EXCEEDED`| 429 | Analysis / Page | Free/Monthly quota reached | `Free trial limit reached (3/3 contracts)...` | Too Many Requests | Triggers `PaymentModal` upgrade modal |
| `ERR_DELETE_LOCK` | 400 | Settings Modal | Confirmation != `DELETE MY ACCOUNT` | `Type "DELETE MY ACCOUNT" to confirm` | Bad Request | Disabled button state guard |
| `ERR_BUILD_WARN` | 200 | Next.js Engine | Deprecated Node runtime | `Node.js 20 deprecated` | OK (Warning) | Upgraded to Node v24.20.0 LTS |
