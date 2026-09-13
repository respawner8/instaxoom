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

### A. Daily Trend Display
- Fetches the active daily aesthetic from the backend (`GET /api/trends/today`).
- Displays the daily trend banner, tagline, sample preview, and suggested photography guidelines.
- Focuses user attention on a single viral theme per day to drive community engagement.

### B. Multi-Photo Face Uploader (1 to 5 Photos)
- **File Input:** Accepts JPEG, PNG, WEBP images.
- **Visual Feedback:** Shows instant thumbnail previews of all selected photos.
- **Guidance Indicator:** Highlights that 3–5 photos provide optimal face-embedding pooling for superior facial likeness.

### C. Instagram Aspect Ratio (Standard 4:5 Portrait)

- **Format:** `4:5` Portrait (864 × 1080 / 1080 × 1350)
- **Rationale:** The 4:5 vertical aspect ratio maximizes screen real estate in the Instagram mobile feed, achieving the highest visual engagement compared to square or landscape formats.
- **Future Roadmap:** Additional formats (9:16 for Stories/Reels and 1:1 for classic squares) will be enabled in subsequent updates.

### D. Export & Instagram Sharing
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
