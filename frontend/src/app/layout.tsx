import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "instaXoom | Daily AI Trends for Instagram",
  description: "Generate viral AI portraits tailored for Instagram feed, stories, and reels using daily trends.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased bg-[#09090b] text-[#fafafa] selection:bg-pink-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}
