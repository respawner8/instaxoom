"use client";

import React, { useState, useEffect } from "react";
import {
  Sparkles,
  Upload,
  Instagram,
  Share2,
  Download,
  CheckCircle2,
  Flame,
  RefreshCw,
  Layers,
  AlertCircle,
  Sliders,
  RotateCcw,
  Tag,
  X,
  UserCheck,
  Crop
} from "lucide-react";
import { autoCropAndDetectFace, ProcessedPhotoResult } from "@/lib/faceCropper";

interface Theme {
  id: string;
  title: string;
  category: string;
  tagline: string;
  hashtags: string[];
  prompt_template: string;
  preview_image_url?: string;
}

const DEFAULT_THEMES: Theme[] = [
  {
    id: "trend-retro-90s-yearbook",
    title: "1990s Yearbook",
    category: "Vintage",
    tagline: "Authentic 1994 vintage yearbook portrait with film grain, soft flash, and blue studio backdrop.",
    hashtags: ["#90sYearbook", "#VintageAesthetic", "#instaXoom"],
    prompt_template: "1990s high school yearbook photo, 35mm film photography, soft direct camera flash lighting, slightly faded vintage colors, textured blue studio portrait backdrop, smiling high school student, authentic 90s hair and collar shirt",
  },
  {
    id: "trend-cyberpunk-neon",
    title: "Cyberpunk 2077",
    category: "Sci-Fi",
    tagline: "Dystopian night city portrait drenched in vivid magenta and cyan neon reflections.",
    hashtags: ["#Cyberpunk", "#NeonTokyo", "#instaXoom"],
    prompt_template: "cyberpunk portrait, high-tech glowing neon rain-slicked city streets background, dramatic volumetric rim lighting, vivid magenta and cyan reflections, wearing futuristic cybernetic collar and techwear jacket, 8k cinematic film still, detailed reflections",
  },
  {
    id: "trend-70s-polaroid",
    title: "1970s Polaroid",
    category: "Retro",
    tagline: "Nostalgic analog snapshot with warm sun-drenched golden tones and subtle light leaks.",
    hashtags: ["#70sVibe", "#AnalogFilm", "#PolaroidAesthetic"],
    prompt_template: "1970s vintage polaroid snapshot, warm sepia and golden hour daylight, subtle authentic light leak, soft analog film grain, retro 70s casual wardrobe, candid intimate expression, Kodachrome color palette, nostalgic mood",
  },
  {
    id: "trend-old-money-luxury",
    title: "Old Money Luxury",
    category: "Editorial",
    tagline: "Timeless editorial portrait in a Mediterranean villa garden with natural golden sunlight.",
    hashtags: ["#OldMoney", "#QuietLuxury", "#EditorialPortrait"],
    prompt_template: "editorial luxury portrait in Lake Como villa terrace garden, soft afternoon golden sunlight, natural bokeh cypress trees and lake in background, wearing tailored cream linen blazer, elegant poised expression, Vogue magazine cover aesthetic",
  },
  {
    id: "trend-studio-ghibli",
    title: "Studio Ghibli",
    category: "Anime",
    tagline: "Dreamy, hand-painted anime portrait with vibrant skies and whimsical storybook atmosphere.",
    hashtags: ["#GhibliStyle", "#AnimePortrait", "#ArtisticAesthetic"],
    prompt_template: "masterpiece anime portrait in the whimsical art style of Studio Ghibli, painted watercolor clouds, gentle summer breeze moving hair, warm afternoon light, vibrant hand-drawn aesthetic, high details, Hayao Miyazaki aesthetic",
  },
];

const SUGGESTED_MODIFIERS = [
  "smiling warmly",
  "vintage leather jacket",
  "35mm direct flash",
  "dramatic golden hour",
  "high fashion jewelry",
  "wind in hair",
];

export default function Home() {
  const [themes, setThemes] = useState<Theme[]>(DEFAULT_THEMES);
  const [selectedTheme, setSelectedTheme] = useState<Theme>(DEFAULT_THEMES[0]);
  const [customPrompt, setCustomPrompt] = useState<string>(DEFAULT_THEMES[0].prompt_template);
  const [isPromptEdited, setIsPromptEdited] = useState<boolean>(false);

  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [previewUrls, setPreviewUrls] = useState<string[]>([]);
  const [isCropping, setIsCropping] = useState<boolean>(false);
  const [croppingStatus, setCroppingStatus] = useState<string>("");
  const [detectedGender, setDetectedGender] = useState<"male" | "female" | null>(null);
  const [genderConfidence, setGenderConfidence] = useState<number | null>(null);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [generationProgress, setGenerationProgress] = useState<number>(0);
  const [generatedImage, setGeneratedImage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${apiUrl}/api/trends/today`)
      .then((res) => res.json())
      .then((data) => {
        if (data.themes && Array.isArray(data.themes) && data.themes.length > 0) {
          setThemes(data.themes);
          if (!isPromptEdited) {
            const first = data.themes[0];
            setSelectedTheme(first);
            setCustomPrompt(first.prompt_template);
          }
        }
      })
      .catch((err) => console.log("Using default themes:", err));
  }, []);

  const handleThemeSelect = (theme: Theme) => {
    setSelectedTheme(theme);
    setCustomPrompt(theme.prompt_template);
    setIsPromptEdited(false);
    setErrorMessage(null);
  };

  const handlePromptChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setCustomPrompt(e.target.value);
    setIsPromptEdited(e.target.value !== selectedTheme.prompt_template);
  };

  const handleResetPrompt = () => {
    setCustomPrompt(selectedTheme.prompt_template);
    setIsPromptEdited(false);
  };

  const handleAddModifier = (mod: string) => {
    setCustomPrompt((prev) => (prev.endsWith(",") || prev.endsWith(", ") ? `${prev} ${mod}` : `${prev}, ${mod}`));
    setIsPromptEdited(true);
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const rawFiles = Array.from(e.target.files).slice(0, 5);
    if (rawFiles.length === 0) return;

    setIsCropping(true);
    setCroppingStatus("Detecting faces & auto-cropping to 4:5 headshots...");
    setErrorMessage(null);

    try {
      const processedResults: ProcessedPhotoResult[] = [];
      for (let i = 0; i < rawFiles.length; i++) {
        setCroppingStatus(`Processing selfie ${i + 1} of ${rawFiles.length}...`);
        const res = await autoCropAndDetectFace(rawFiles[i]);
        processedResults.push(res);
      }

      setUploadedFiles(processedResults.map((r) => r.file));
      setPreviewUrls(processedResults.map((r) => r.previewUrl));

      // Calculate aggregated majority gender from all detected photos
      const validGenders = processedResults.filter((r) => r.gender !== "unknown");
      if (validGenders.length > 0) {
        const maleResults = validGenders.filter((r) => r.gender === "male");
        const femaleResults = validGenders.filter((r) => r.gender === "female");

        if (maleResults.length >= femaleResults.length) {
          const avgConf = Math.round(
            maleResults.reduce((sum, r) => sum + r.genderConfidence, 0) / maleResults.length
          );
          setDetectedGender("male");
          setGenderConfidence(avgConf);
        } else {
          const avgConf = Math.round(
            femaleResults.reduce((sum, r) => sum + r.genderConfidence, 0) / femaleResults.length
          );
          setDetectedGender("female");
          setGenderConfidence(avgConf);
        }
      } else {
        setDetectedGender(null);
        setGenderConfidence(null);
      }
    } catch (err: any) {
      console.warn("Auto-cropper encountered error, using original uploads:", err);
      setUploadedFiles(rawFiles);
      setPreviewUrls(rawFiles.map((file) => URL.createObjectURL(file)));
    } finally {
      setIsCropping(false);
      setCroppingStatus("");
    }
  };

  const handleRemovePhoto = (index: number) => {
    setUploadedFiles((prev) => prev.filter((_, i) => i !== index));
    setPreviewUrls((prev) => prev.filter((_, i) => i !== index));
    if (uploadedFiles.length <= 1) {
      setDetectedGender(null);
      setGenderConfidence(null);
    }
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
      // Pass ALL uploaded and cropped photos to ComfyUI for multi-face pooling
      uploadedFiles.forEach((file) => formData.append("photos", file));
      formData.append("aspect_ratio", "4:5");
      formData.append("theme_id", selectedTheme.id);
      formData.append("prompt", customPrompt);
      if (detectedGender) {
        formData.append("gender", detectedGender);
      }

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
    const hashtagStr = selectedTheme.hashtags.join(" ");
    if (navigator.share) {
      try {
        await navigator.share({
          title: `${selectedTheme.title} on instaXoom`,
          text: `Transformed myself with the ${selectedTheme.title} aesthetic on instaXoom! ${hashtagStr}`,
          url: window.location.href,
        });
      } catch (e) {
        console.log("Share dismissed", e);
      }
    } else {
      navigator.clipboard.writeText(`Transformed myself with the ${selectedTheme.title} aesthetic on instaXoom! ${hashtagStr}`);
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
            <span>Dev & Multi-Theme Active</span>
          </div>
        </div>
      </header>

      {/* Hero / Header */}
      <div className="max-w-4xl mx-auto w-full px-4 pt-10 pb-16 flex-1 flex flex-col items-center">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-gradient-to-r from-rose-500/10 via-purple-500/10 to-amber-500/10 border border-rose-500/20 text-rose-300 text-xs font-semibold mb-6">
          <Sparkles className="w-3.5 h-3.5 text-rose-400 animate-pulse" />
          <span>AI PORTRAIT GENERATOR &bull; FLUX.1 + PuLID</span>
        </div>

        <h1 className="text-4xl md:text-5xl font-black text-center tracking-tight mb-4 max-w-2xl bg-gradient-to-b from-white to-neutral-400 bg-clip-text text-transparent">
          {selectedTheme.title}
        </h1>
        <p className="text-neutral-400 text-center text-sm md:text-base max-w-xl mb-10 leading-relaxed">
          {selectedTheme.tagline}
        </p>

        {/* Main Generator Card */}
        <div className="w-full bg-neutral-900/60 border border-neutral-800/90 rounded-3xl p-6 md:p-8 backdrop-blur-xl shadow-2xl space-y-8">
          
          {/* Step 1: Photo Upload */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <label className="text-sm font-semibold text-neutral-200 flex items-center gap-2">
                <span>1. Upload Face Photos</span>
                <span className="text-xs font-normal text-neutral-500">(1 to 5 photos)</span>
              </label>
              <span className="text-xs text-rose-400 font-medium flex items-center gap-1">
                <Layers className="w-3.5 h-3.5" />
                PuLID Face Likeness
              </span>
            </div>

            <div className="border-2 border-dashed border-neutral-800 hover:border-neutral-700 transition rounded-2xl p-6 text-center bg-neutral-950/40 relative cursor-pointer">
              <input
                type="file"
                multiple
                accept="image/*"
                onChange={handleFileChange}
                disabled={isCropping || isGenerating}
                className="absolute inset-0 opacity-0 cursor-pointer w-full h-full disabled:cursor-not-allowed"
              />
              <div className="flex flex-col items-center gap-2 pointer-events-none">
                <div className="w-12 h-12 rounded-full bg-neutral-900 border border-neutral-800 flex items-center justify-center text-neutral-400">
                  {isCropping ? (
                    <RefreshCw className="w-5 h-5 text-rose-400 animate-spin" />
                  ) : (
                    <Upload className="w-5 h-5 text-neutral-300" />
                  )}
                </div>
                <p className="text-sm font-medium text-neutral-300">
                  {isCropping
                    ? croppingStatus
                    : uploadedFiles.length > 0
                    ? `${uploadedFiles.length} photo(s) selected (4:5 Headshots Auto-Framed)`
                    : "Tap to select or drop photos here"}
                </p>
                <p className="text-xs text-neutral-500">
                  Upload 1 to 5 clear selfies &bull; Faces are automatically detected, cropped to 4:5 headshots, and pooled
                </p>
              </div>
            </div>

            {/* Detected Gender Badge & Manual Override */}
            {detectedGender && (
              <div className="mt-3 p-3 rounded-xl bg-neutral-950/80 border border-neutral-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <UserCheck className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-semibold text-neutral-200">
                    Auto-Detected Subject:
                  </span>
                  <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 capitalize">
                    {detectedGender} {genderConfidence ? `(${genderConfidence}%)` : ""}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => setDetectedGender("male")}
                    className={`text-[11px] px-2.5 py-1 rounded-lg border transition ${
                      detectedGender === "male"
                        ? "bg-rose-500/20 border-rose-500 text-rose-300 font-semibold"
                        : "bg-neutral-900 border-neutral-800 text-neutral-400 hover:text-white"
                    }`}
                  >
                    Male
                  </button>
                  <button
                    type="button"
                    onClick={() => setDetectedGender("female")}
                    className={`text-[11px] px-2.5 py-1 rounded-lg border transition ${
                      detectedGender === "female"
                        ? "bg-rose-500/20 border-rose-500 text-rose-300 font-semibold"
                        : "bg-neutral-900 border-neutral-800 text-neutral-400 hover:text-white"
                    }`}
                  >
                    Female
                  </button>
                </div>
              </div>
            )}

            {/* Upload Previews */}
            {previewUrls.length > 0 && (
              <div className="flex gap-3 mt-4 overflow-x-auto pb-2">
                {previewUrls.map((url, idx) => (
                  <div key={idx} className="relative w-20 h-24 rounded-xl overflow-hidden border border-neutral-700 flex-shrink-0 group shadow-md">
                    <img src={url} alt={`Upload ${idx + 1}`} className="w-full h-full object-cover" />
                    <div className="absolute bottom-0 inset-x-0 bg-black/60 backdrop-blur-xs py-0.5 text-[9px] text-center text-rose-300 font-medium">
                      4:5 Crop
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemovePhoto(idx)}
                      className="absolute top-1 right-1 bg-black/70 hover:bg-rose-600 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Step 2: Theme Selector */}
          <div>
            <label className="block text-sm font-semibold text-neutral-200 mb-3">
              2. Select Aesthetic Theme
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
              {themes.map((theme) => {
                const isActive = theme.id === selectedTheme.id;
                return (
                  <button
                    key={theme.id}
                    type="button"
                    onClick={() => handleThemeSelect(theme)}
                    className={`p-3 rounded-2xl border text-left transition-all relative flex flex-col justify-between ${
                      isActive
                        ? "border-rose-500 bg-rose-500/10 shadow-lg shadow-rose-500/10 scale-[1.02]"
                        : "border-neutral-800 bg-neutral-950/40 hover:border-neutral-700 hover:bg-neutral-900/60"
                    }`}
                  >
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-rose-400">
                        {theme.category}
                      </span>
                      <div className="font-semibold text-sm text-white mt-1 leading-snug">
                        {theme.title}
                      </div>
                    </div>
                    {isActive && (
                      <div className="mt-2 flex items-center gap-1 text-[11px] text-rose-300 font-medium">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Active</span>
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Step 3: Editable Prompt Box (Dev Mode) */}
          <div className="p-5 rounded-2xl border border-neutral-800 bg-neutral-950/60 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-sm font-semibold text-neutral-200 flex items-center gap-2">
                <Sliders className="w-4 h-4 text-amber-400" />
                <span>3. Customize Prompt (Dev & Prompt Tweaker)</span>
              </label>
              {isPromptEdited && (
                <button
                  type="button"
                  onClick={handleResetPrompt}
                  className="text-xs text-neutral-400 hover:text-rose-400 flex items-center gap-1 transition"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Reset to Theme Default</span>
                </button>
              )}
            </div>

            <p className="text-xs text-neutral-500">
              Edit lighting, clothing, expression, or background details directly before generating.
            </p>

            <textarea
              value={customPrompt}
              onChange={handlePromptChange}
              rows={4}
              className="w-full bg-neutral-900 border border-neutral-800 rounded-xl p-3 text-sm text-neutral-200 focus:outline-none focus:border-rose-500/60 focus:ring-1 focus:ring-rose-500/60 transition resize-y font-mono leading-relaxed"
              placeholder="Enter your prompt description..."
            />

            {/* Quick Keyword Modifier Chips */}
            <div className="flex flex-wrap gap-1.5 pt-1">
              <span className="text-[11px] text-neutral-500 self-center mr-1">Quick Add:</span>
              {SUGGESTED_MODIFIERS.map((mod, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleAddModifier(mod)}
                  className="px-2.5 py-1 rounded-lg bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 text-[11px] text-neutral-300 transition"
                >
                  + {mod}
                </button>
              ))}
            </div>
          </div>

          {/* Step 4: Instagram Format (Locked to 4:5) */}
          <div>
            <label className="block text-sm font-semibold text-neutral-200 mb-3">
              4. Instagram Aspect Ratio
            </label>
            <div className="p-4 rounded-2xl border border-rose-500/40 bg-rose-500/10 text-white flex items-center justify-between shadow-lg shadow-rose-500/5">
              <div>
                <div className="font-semibold text-sm flex items-center gap-2">
                  <span>Feed Portrait (4:5)</span>
                  <span className="px-2 py-0.5 text-[11px] rounded-full bg-rose-500/20 text-rose-300 font-medium">Locked</span>
                </div>
                <div className="text-xs text-neutral-400 mt-0.5">
                  864 × 1080 &bull; Maximizes screen engagement in the Instagram mobile feed
                </div>
              </div>
              <div className="h-9 w-7 rounded border border-rose-400/40 bg-rose-500/20 flex items-center justify-center text-[10px] font-mono text-rose-200">
                4:5
              </div>
            </div>
          </div>

          {/* Step 5: Generate CTA */}
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
                <span>Generating {selectedTheme.title} ({generationProgress}%)...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-5 h-5" />
                <span>Generate {selectedTheme.title} Portrait</span>
              </>
            )}
          </button>

          {/* Error Notice */}
          {errorMessage && (
            <div className="p-4 rounded-xl bg-red-950/40 border border-red-800/50 text-red-300 text-sm flex items-center gap-2">
              <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Output Preview & Instagram Export */}
          {generatedImage && (
            <div className="mt-10 pt-8 border-t border-neutral-800 flex flex-col items-center">
              <div className="flex items-center gap-2 text-emerald-400 text-sm font-semibold mb-4">
                <CheckCircle2 className="w-4 h-4" />
                <span>{selectedTheme.title} Ready!</span>
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
                  download="instaxoom_trend.png"
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

