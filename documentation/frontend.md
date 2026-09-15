# Frontend Architecture & Client Guide

This document outlines the architecture, UX design, and Instagram integration for the **instaXoom** web client and future mobile extensions.

---

## 1. Tech Stack & Key Libraries

- **Framework:** Next.js 15 (App Router)
- **UI & Styling:** React 19, Tailwind CSS
- **Icons:** Lucide React
- **Type Safety:** TypeScript 5.4+
- **Containerization:** Node 20 Alpine multi-stage Docker build

---

## 2. Core Modules & User Flows

### A. Multi-Theme Selection & Daily Trend
- Fetches available themes from the backend (`GET /api/trends/today`).
- Features 5 curated aesthetic presets:
  - **1990s Yearbook:** 35mm flash, textured blue backdrop, vintage clothing.
  - **Cyberpunk 2077:** Night city neon reflections, volumetric magenta/cyan rim lighting.
  - **1970s Warm Polaroid:** Faded Kodachrome tones, subtle light leaks, candid 70s fashion.
  - **Old Money / Quiet Luxury:** Lake Como terrace garden, golden hour bokeh, tailored cream blazer.
  - **Studio Ghibli Anime:** Whimsical painterly watercolor skies, anime aesthetic, Miyazaki art style.
- Visual theme cards display active glow states, tags, and instantly switch the prompt context.

### B. Dev & Real-Time Prompt Customizer
- **Interactive Prompt Box (`<textarea>`):** Allows developers and power users to modify prompt details (lighting, attire, expressions, backdrops) in real time before generating.
- **Reset to Theme Default:** Single-click button to revert custom edits back to the theme's core prompt template.
- **Quick Add Modifiers:** Clickable chips for instant prompt styling (`+ smiling warmly`, `+ 35mm direct flash`, `+ vintage leather jacket`, `+ cinematic rim lighting`, `+ soft bokeh background`).

### C. Multi-Photo Face Uploader & PuLID Likeness
- **File Input:** Accepts 1 to 5 selfie photos (JPEG, PNG, WEBP).
- **Visual Feedback:** Shows instant thumbnail previews of all selected photos with individual remove buttons.
- **Face Likeness:** Photos condition the facial identity in ComfyUI via PuLID-Flux and InsightFace AntelopeV2.

### D. Instagram Aspect Ratio (Standard 4:5 Portrait)
- **Format:** `4:5` Portrait (864 × 1080 / 1080 × 1350)
- **Rationale:** The 4:5 vertical aspect ratio maximizes screen real estate in the Instagram mobile feed, achieving the highest visual engagement compared to square or landscape formats.

### E. Export & Instagram Sharing
- **Web Share API (`navigator.share`):** On mobile devices, clicking "Share to Instagram" triggers the native OS share sheet directly into Instagram.
- **Desktop Fallback:** Automatically copies trending hashtags (`#90sYearbook #instaXoom`) to clipboard and downloads the high-res generated portrait.

---

## 3. Directory Layout

```
frontend/
├── src/
│   └── app/
│       ├── layout.tsx       # Root metadata, theme, and font setup
│       ├── page.tsx         # Daily Trend generator, photo uploader & share modal
│       └── globals.css      # Dark mode color tokens & base Tailwind styling
├── public/                  # Static assets and favicons
├── package.json             # Next.js 15 dependencies
├── tailwind.config.ts       # Theme configuration & Instagram accent colors
└── tsconfig.json            # Strict TypeScript configuration
```

---

## 4. Mobile Roadmap (Web Now, Android Later)

- **Phase 1 (Current):** Responsive Mobile Web running in Next.js 15.
- **Phase 2 (Android):**
  - Reuses backend REST API contracts (`/api/trends/today`, `/api/trends/generate`).
  - Native Android implementation can leverage Jetpack Compose for system photo pickers and direct Android `Intent.ACTION_SEND` targeting the Instagram package (`com.instagram.android`).
