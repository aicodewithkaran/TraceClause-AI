# 03. Frontend Architecture (Next.js UI Blueprint)

This document describes the Next.js 15 UI architecture, component hierarchy, state management strategy, and styling design system for **ScanShield AI v2**.

---

## 📂 Component Directory Hierarchy

```text
frontend/
├── app/
│   ├── layout.tsx              # Root layout & theme providers
│   ├── page.tsx                # Landing page & upload dropzone
│   ├── dashboard/
│   │   └── page.tsx            # Split-Screen Masterwork Dashboard
│   └── globals.css             # Tailwind v4 import & custom utilities
├── components/
│   ├── Navbar.tsx              # Header with Playbook, Theme & Laser Cursor controls
│   ├── FileDropzone.tsx        # Drag & drop upload zone with sample launchers
│   ├── ContractViewer.tsx      # Left panel line-numbered document viewer
│   ├── RiskCardGrid.tsx        # Right panel modular soft-tinted risk cards
│   ├── ChatDrawer.tsx          # Citation-linked AI assistant sliding drawer
│   ├── SkeletonLoader.tsx      # Vector computation shimmer placeholders
│   └── PrecisionCursor.tsx     # Custom laser crosshair tracking dot
├── context/
│   └── ScanShieldContext.tsx   # React State / Zustand store provider
└── hooks/
    └── useContractAudit.ts     # Custom hook for API fetch & SSE streaming
```

---

## 🧠 State Management Strategy

The frontend manages global application state using a centralized Context / Zustand store:

### Managed State Properties:
- `theme`: `'dark'` (Deep Charcoal `#09090b`) or `'light'` (Clean Slate `#f8fafc`).
- `customCursor`: `true` (Laser Crosshair) or `false` (System Native Pointer).
- `activeContract`: Active parsed document payload (document text, line numbers, risk cards).
- `activeLine`: Currently selected line number (scrolls and pulses left panel line).
- `riskFilter`: Active risk level filter (`'all'`, `'high'`, `'medium'`, `'low'`).
- `isDrawerOpen`: `true` / `false` state for the AI Assistant Chat drawer.
- `chatMessages`: Array of AI conversation messages with `[Source: Line X]` citation pills.

---

## 🎨 Styling & Color Palette Tokens

### Dark Mode (Enterprise SaaS Minimalist):
- **Background**: `#09090b`
- **Surface Cards**: `#18181b` with 1px border `rgba(255, 255, 255, 0.08)`
- **Primary Accent**: `#6366f1` (Indigo 500)

### Soft Semantic Risk Tints (Clean & Premium):
- 🔴 **High Risk Card**: `rgba(239, 68, 68, 0.08)` dark tint / `#fef2f2` light tint with `#ef4444` border and `#f87171` text.
- 🟡 **Medium Risk Card**: `rgba(245, 158, 11, 0.08)` dark tint / `#fffbeb` light tint with `#f59e0b` border and `#fbbf24` text.
- 🟢 **Low Risk / Compliant**: `rgba(16, 185, 129, 0.08)` dark tint / `#ecfdf5` light tint with `#10b981` border and `#34d399` text.

---

## 🖥️ Split-Screen Custom Scrollbar & Highlight Utility

```css
/* Custom scrollbar for 50/50 split-screen panels */
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.12);
  border-radius: 9999px;
}

/* Active Line Pulsing Effect */
.line-highlight-pulse {
  animation: borderPulse 1.5s infinite ease-in-out;
}

@keyframes borderPulse {
  0%, 100% { border-left-color: #6366f1; background-color: rgba(99, 102, 241, 0.15); }
  50% { border-left-color: #818cf8; background-color: rgba(99, 102, 241, 0.25); }
}
```
