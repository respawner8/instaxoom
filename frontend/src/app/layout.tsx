import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import TelemetryBootstrap from "@/components/TelemetryBootstrap";
import VisitTracker from "@/components/VisitTracker";

export const metadata: Metadata = {
  title: "CreatorBot | Daily AI Trends for Creators",
  description: "Generate viral AI portraits tailored for creators and social media using daily trends.",
  icons: {
    icon: "/icon.svg",
    apple: "/icon.svg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased bg-[#09090b] text-[#fafafa] selection:bg-pink-500 selection:text-white">
        {/* TelemetryBootstrap registers Web Vitals observers and global error handlers */}
        <TelemetryBootstrap />
        <AuthProvider>
          <VisitTracker />
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
