"use client";

import React, { useState, useEffect } from "react";
import { Sparkles, Upload, Instagram, Share2, Download, CheckCircle2, Flame, RefreshCw, Layers, AlertCircle } from "lucide-react";

export default function Home() {
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [previewUrls, setPreviewUrls] = useState<string[]>([]);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [generationProgress, setGenerationProgress] = useState<number>(0);
  const [generatedImage, setGeneratedImage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [trendData, setTrendData] = useState<{
    title: string;
    tagline: string;
    date: string;
    hashtags: string[];
  }>({
    title: "1990s High School Yearbook",
    tagline: "Transform your selfies into an authentic 1994 vintage yearbook portrait with authentic 35mm film grain and classic blue studio backdrop.",
    date: "DAILY TREND • 90s RETRO",
    hashtags: ["#90sYearbook", "#VintageAesthetic", "#instaXoom"],
  });

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${apiUrl}/api/trends/today`)
      .then((res) => res.json())
      .then((data) => {
        if (data.trend) {
          setTrendData({
            title: data.trend.title || "1990s High School Yearbook",
            tagline: data.trend.tagline || "",
            date: data.trend.date ? `DAILY TREND • ${data.trend.date}` : "DAILY TREND",
            hashtags: data.trend.hashtags || ["#instaXoom"],
          });
        }
      })
      .catch((err) => console.log("Using default trend data:", err));
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const files = Array.from(e.target.files).slice(0, 5);
    setUploadedFiles(files);

    const urls = files.map((file) => URL.createObjectURL(file));
    setPreviewUrls(urls);
    setErrorMessage(null);
  };

  const handleGenerate = async () => {
    if (uploadedFiles.length === 0) return;
    setIsGenerating(true);
    setGenerationProgress(10);
    setGeneratedImage(null);
    setErrorMessage(null);

    // Dynamic progression while ComfyUI processes diffusion steps
    const interval = setInterval(() => {
      setGenerationProgress((prev) => {
        if (prev >= 92) return 92;
        return prev + 6;
      });
    }, 1000);

    try {
      const formData = new FormData();
      uploadedFiles.forEach((file) => formData.append("photos", file));
      formData.append("aspect_ratio", "4:5");

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/trends/generate`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      clearInterval(interval);

      if (res.ok && data.image_url) {
        setGenerationProgress(100);
        const fullUrl = data.image_url.startsWith("http")
          ? data.image_url
          : `${apiUrl}${data.image_url}`;
        setGeneratedImage(fullUrl);
      } else {
        setErrorMessage(data.detail || "Image generation failed. Please try again.");
      }
    } catch (err: any) {
      clearInterval(interval);
      console.error("Generation request error:", err);
      setErrorMessage(err?.message || "Failed to reach inference server. Please check the backend connection.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleShareToInstagram = async () => {
    const hashtagStr = trendData.hashtags.join(" ");
    if (navigator.share) {
      try {
        await navigator.share({
          title: `${trendData.title} on instaXoom`,
          text: `Transformed myself with today's trend on instaXoom! ${hashtagStr}`,
          url: window.location.href,
        });
      } catch (e) {
        console.log("Share dismissed", e);
      }
    } else {
      navigator.clipboard.writeText(`Transformed myself with today's trend on instaXoom! ${hashtagStr}`);
      alert("Caption and hashtags copied! Open Instagram to share your downloaded portrait.");
    }
  };

  return (
    <main className="min-h-screen bg-[#0a0a0c] text-neutral-100 flex flex-col">
      {/* Top Navigation */}
      <header className="border-b border-neutral-800/80 backdrop-blur-md sticky top-0 z-50 bg-[#0a0a0c]/80 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-amber-500 via-rose-500 to-purple-600 flex items-center justify-center font-bold text-white shadow-lg shadow-rose-500/20">
            X
          </div>
          <span className="font-extrabold text-xl tracking-tight bg-gradient-to-r from-white via-neutral-200 to-neutral-400 bg-clip-text text-transparent">
            instaXoom
          </span>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-neutral-900 border border-neutral-800 text-xs font-medium text-neutral-300">
            <Flame className="w-3.5 h-3.5 text-amber-500 fill-amber-500" />
            <span>Today's Drop</span>
          </div>
        </div>
      </header>

      {/* Hero / Daily Trend Showcase */}
      <div className="max-w-4xl mx-auto w-full px-4 pt-10 pb-16 flex-1 flex flex-col items-center">
        {/* Trend Banner Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-gradient-to-r from-rose-500/10 via-purple-500/10 to-amber-500/10 border border-rose-500/20 text-rose-300 text-xs font-semibold mb-6">
          <Sparkles className="w-3.5 h-3.5 text-rose-400 animate-pulse" />
          <span>{trendData.date}</span>
        </div>

        <h1 className="text-4xl md:text-5xl font-black text-center tracking-tight mb-4 max-w-2xl bg-gradient-to-b from-white to-neutral-400 bg-clip-text text-transparent">
          {trendData.title}
        </h1>
        <p className="text-neutral-400 text-center text-sm md:text-base max-w-xl mb-10 leading-relaxed">
          {trendData.tagline}
        </p>

        {/* Generator Card */}
        <div className="w-full bg-neutral-900/60 border border-neutral-800/90 rounded-3xl p-6 md:p-8 backdrop-blur-xl shadow-2xl">
          
          {/* Step 1: Photo Upload */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-3">
              <label className="text-sm font-semibold text-neutral-200 flex items-center gap-2">
                <span>1. Upload Face Photos</span>
                <span className="text-xs font-normal text-neutral-500">(1 to 5 photos)</span>
              </label>
              <span className="text-xs text-rose-400 font-medium flex items-center gap-1">
                <Layers className="w-3.5 h-3.5" />
                3-5 photos give highest likeness
              </span>
            </div>

            <div className="border-2 border-dashed border-neutral-800 hover:border-neutral-700 transition rounded-2xl p-6 text-center bg-neutral-950/40 relative cursor-pointer">
              <input
                type="file"
                multiple
                accept="image/*"
                onChange={handleFileChange}
                className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
              />
              <div className="flex flex-col items-center gap-2 pointer-events-none">
                <div className="w-12 h-12 rounded-full bg-neutral-900 border border-neutral-800 flex items-center justify-center text-neutral-400">
                  <Upload className="w-5 h-5 text-neutral-300" />
                </div>
                <p className="text-sm font-medium text-neutral-300">
                  {uploadedFiles.length > 0
                    ? `${uploadedFiles.length} photo(s) selected`
                    : "Tap to select or drop photos here"}
                </p>
                <p className="text-xs text-neutral-500">
                  Clear selfies with good lighting produce the sharpest results
                </p>
              </div>
            </div>

            {/* Upload Previews */}
            {previewUrls.length > 0 && (
              <div className="flex gap-3 mt-4 overflow-x-auto pb-2">
                {previewUrls.map((url, idx) => (
                  <div key={idx} className="relative w-16 h-16 rounded-xl overflow-hidden border border-neutral-700 flex-shrink-0">
                    <img src={url} alt={`Upload ${idx + 1}`} className="w-full h-full object-cover" />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Step 2: Instagram Format (Locked to 4:5) */}
          <div className="mb-8">
            <label className="block text-sm font-semibold text-neutral-200 mb-3">
              2. Instagram Format
            </label>
            <div className="p-4 rounded-2xl border border-rose-500/40 bg-rose-500/10 text-white flex items-center justify-between shadow-lg shadow-rose-500/5">
              <div>
                <div className="font-semibold text-sm flex items-center gap-2">
                  <span>Feed Portrait (4:5)</span>
                  <span className="px-2 py-0.5 text-[11px] rounded-full bg-rose-500/20 text-rose-300 font-medium">Standard</span>
                </div>
                <div className="text-xs text-neutral-400 mt-0.5">
                  1080 × 1350 &bull; Maximizes mobile screen area in the Instagram feed
                </div>
              </div>
              <div className="h-9 w-7 rounded border border-rose-400/40 bg-rose-500/20 flex items-center justify-center text-[10px] font-mono text-rose-200">
                4:5
              </div>
            </div>
          </div>

          {/* Step 3: Generate CTA */}
          <button
            type="button"
            disabled={uploadedFiles.length === 0 || isGenerating}
            onClick={handleGenerate}
            className={`w-full py-4 rounded-2xl font-bold flex items-center justify-center gap-2 text-base transition-all shadow-xl ${
              uploadedFiles.length === 0 || isGenerating
                ? "bg-neutral-800 text-neutral-500 cursor-not-allowed"
                : "bg-gradient-to-r from-rose-500 via-purple-600 to-amber-500 text-white hover:opacity-95 shadow-rose-500/25 active:scale-[0.99]"
            }`}
          >
            {isGenerating ? (
              <>
                <RefreshCw className="w-5 h-5 animate-spin" />
                <span>Crafting Today's Trend ({generationProgress}%)...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-5 h-5" />
                <span>Generate Yearbook Portrait</span>
              </>
            )}
          </button>

          {/* Error Notice */}
          {errorMessage && (
            <div className="mt-4 p-4 rounded-xl bg-red-950/40 border border-red-800/50 text-red-300 text-sm flex items-center gap-2">
              <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Output Preview & Instagram Export */}
          {generatedImage && (
            <div className="mt-10 pt-8 border-t border-neutral-800 flex flex-col items-center">
              <div className="flex items-center gap-2 text-emerald-400 text-sm font-semibold mb-4">
                <CheckCircle2 className="w-4 h-4" />
                <span>Trend Portrait Ready!</span>
              </div>

              <div className="overflow-hidden rounded-2xl border border-neutral-800 shadow-2xl relative bg-black w-[300px] h-[375px]">
                <img
                  src={generatedImage}
                  alt="Generated Instagram Trend"
                  className="w-full h-full object-cover"
                />
              </div>

              {/* Instagram Sharing Actions */}
              <div className="flex flex-col sm:flex-row gap-3 w-full max-w-sm mt-6">
                <button
                  type="button"
                  onClick={handleShareToInstagram}
                  className="flex-1 py-3 px-4 rounded-xl font-semibold bg-gradient-to-r from-purple-600 to-rose-500 text-white flex items-center justify-center gap-2 hover:opacity-95 text-sm shadow-lg shadow-purple-500/20"
                >
                  <Instagram className="w-4 h-4" />
                  <span>Share to Instagram</span>
                </button>
                <a
                  href={generatedImage}
                  download="instaxoom_trend.jpg"
                  className="py-3 px-4 rounded-xl font-semibold bg-neutral-800 hover:bg-neutral-700 text-white flex items-center justify-center gap-2 text-sm transition"
                >
                  <Download className="w-4 h-4" />
                  <span>Save</span>
                </a>
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
