# Frontend Architecture & Client Guide

This document outlines the architecture, UX design, authentication, and Instagram integration for the **instaXoom** web client.

---

## 1. Tech Stack & Key Libraries

- **Framework:** Next.js 15 (App Router)
- **UI & Styling:** React 19, Tailwind CSS
- **Authentication:** `@react-oauth/google` with persistent JWT storage (`localStorage`)
- **Icons:** Lucide React
- **Face Processing:** `@vladmandic/face-api` (client-side 4:5 auto-framing and gender estimation)
- **Type Safety:** TypeScript 5.4+

---

## 2. Core Modules & User Flows

### A. Authentication & Credit Management (`AuthContext.tsx`)
- **Google Sign-In:** Integrates Google Identity Services via `@react-oauth/google`.
- **Session Persistence:** Saves backend-issued JWT token to `localStorage` (`instaxoom_jwt`).
- **Live Credit Tracking:** Top bar displays live credit balance badge (`✨ X Credits`).
- **Role Routing:** If a signed-in user has `role === "admin"`, the client automatically redirects to the `/admin` portal.

### B. Daily Trend Studio (`/`)
- **Theme Catalogue:** 5 curated aesthetic presets (1990s Yearbook, Cyberpunk 2077, 1970s Polaroid, Old Money Luxury, Studio Ghibli).
- **Prompt Customizer:** Allows real-time prompt modifications and modifier chip injection (`+ smiling warmly`, `+ 35mm direct flash`).
- **Face Uploader & Auto-Cropper:** Auto-frames uploaded face photos into optimal 4:5 portrait dimensions.
- **Generate CTA Button:**
  - Prompt to sign in with Google if unauthenticated.
  - Displays "0 Credits Remaining (Trial Required)" if balance is exhausted.
  - Displays `Generate Portrait • 1 Credit (X left)` when credits are available.

### C. Admin Portal (`/admin`)
- **Protected View:** Accessible only to users whose email matches `ADMIN_EMAILS`. Unauthorized visitors are redirected to `/`.
- **Trial Credit Grant Form:** Assigns credits directly to existing users or reserves them in `pending_credits` for users who haven't signed up yet.
- **KPI Summary Cards:** Displays Registered Users, Circulating Credits, Pending Grants, and Total Transactions.
- **Tabbed Tables:** Searchable User Directory, Pending Grants waiting for signup, and a full Transaction Audit Log.

### D. Export & Instagram Sharing
- **Web Share API (`navigator.share`):** On mobile devices, clicking "Share to Instagram" triggers the native OS share sheet directly into Instagram.
- **WhatsApp Web & Clipboard:** Automatically copies generated portrait image to the system clipboard for immediate pasting into WhatsApp Web or Instagram Direct.

---

## 3. Directory Layout

```
frontend/
├── src/
│   ├── app/
│   │   ├── admin/
│   │   │   └── page.tsx      # Admin dashboard for credit management & audit logs
│   │   ├── layout.tsx        # Root layout wrapped in AuthProvider
│   │   ├── page.tsx          # Daily Trend generator & Instagram export UI
│   │   └── globals.css       # Dark mode color tokens & base Tailwind styling
│   ├── context/
│   │   └── AuthContext.tsx   # Google OAuth, JWT persistence & credit state
│   └── lib/
│       └── faceCropper.ts    # Client-side 4:5 face detection & framing
├── public/                   # Static assets, models, and favicons
├── package.json              # Next.js 15 dependencies
├── tailwind.config.ts        # Theme configuration & accent colors
└── tsconfig.json             # Strict TypeScript configuration
```
