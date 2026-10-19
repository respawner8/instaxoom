"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  ArrowLeft,
  Download,
  Share2,
  RefreshCw,
  ExternalLink,
  Sparkles,
  Image as ImageIcon,
  Calendar,
  Check,
  Trash2,
  AlertTriangle,
} from "lucide-react";

export interface GenerationItem {
  id: string;
  job_id: string;
  theme_id: string;
  theme_title?: string;
  prompt?: string;
  aspect_ratio: string;
  engine: string;
  image_url: string;
  thumbnail_url?: string;
  storage_provider: string;
  created_at: string | null;
}

interface MyImagesModalProps {
  isOpen: boolean;
  onClose: () => void;
  generations: GenerationItem[];
  isLoading: boolean;
  onRefresh: () => void;
  onDelete?: (id: string) => Promise<void> | void;
  apiUrl: string;
}

export default function MyImagesModal({
  isOpen,
  onClose,
  generations,
  isLoading,
  onRefresh,
  onDelete,
  apiUrl,
}: MyImagesModalProps) {
  const [selectedImage, setSelectedImage] = useState<GenerationItem | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [failedImageIds, setFailedImageIds] = useState<Set<string>>(new Set());

  // Auto-reset delete confirmation after 4 seconds
  useEffect(() => {
    if (!confirmDeleteId) return;
    const timer = setTimeout(() => {
      setConfirmDeleteId(null);
    }, 4000);
    return () => clearTimeout(timer);
  }, [confirmDeleteId]);

  // Handle ESC key navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (selectedImage) {
          setSelectedImage(null);
        } else {
          onClose();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, selectedImage, onClose]);

  if (!isOpen) return null;

  const getFullImageUrl = (url: string) => {
    if (!url) return "";
    return url.startsWith("http") ? url : `${apiUrl}${url}`;
  };

  const formatDate = (isoString: string | null) => {
    if (!isoString) return "Recently";
    try {
      const date = new Date(isoString);
      return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      }).format(date);
    } catch {
      return "Recently";
    }
  };

  const handleDownload = async (item: GenerationItem, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setDownloadingId(item.id);
    try {
      const fullUrl = getFullImageUrl(item.image_url);
      const res = await fetch(fullUrl);
      const blob = await res.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = `creatorbot_${item.theme_id || "portrait"}_${item.job_id.slice(0, 8)}.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.error("Download failed:", err);
      window.open(getFullImageUrl(item.image_url), "_blank");
    } finally {
      setDownloadingId(null);
    }
  };

  const handleCopyLink = async (item: GenerationItem, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      const fullUrl = getFullImageUrl(item.image_url);
      await navigator.clipboard.writeText(fullUrl);
      setCopiedId(item.id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      console.error("Failed to copy link:", err);
    }
  };

  const handleShare = async (item: GenerationItem, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const fullUrl = getFullImageUrl(item.image_url);
    if (navigator.share) {
      try {
        await navigator.share({
          title: `My CreatorBot ${item.theme_title || "Portrait"}`,
          text: `Check out my AI portrait generated on CreatorBot! Generate yours today: www.creatorbot.si`,
          url: fullUrl,
        });
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          handleCopyLink(item);
        }
      }
    } else {
      handleCopyLink(item);
    }
  };

  const handleDelete = async (item: GenerationItem, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();

    if (confirmDeleteId !== item.id) {
      setConfirmDeleteId(item.id);
      return;
    }

    setDeletingId(item.id);
    try {
      if (onDelete) {
        await onDelete(item.id);
      }
      if (selectedImage?.id === item.id) {
        setSelectedImage(null);
      }
    } catch (err) {
      console.error("Failed to delete generation:", err);
    } finally {
      setDeletingId(null);
      setConfirmDeleteId(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 md:p-6 bg-black/85 backdrop-blur-md animate-in fade-in duration-200"
      onClick={() => {
        if (selectedImage) {
          setSelectedImage(null);
        } else {
          onClose();
        }
      }}
    >
      {/* Modal Dialog Container */}
      <div
        className="bg-[#121217] border border-neutral-800 rounded-xl sm:rounded-2xl w-full max-w-5xl max-h-[92vh] sm:max-h-[90vh] flex flex-col shadow-2xl overflow-hidden relative"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Dynamic Header depending on whether inspecting a specific image or browsing the gallery */}
        {selectedImage ? (
          /* Detail View Header */
          <div className="px-3.5 sm:px-5 py-3 sm:py-3.5 border-b border-neutral-800/80 flex items-center justify-between bg-neutral-900/80 backdrop-blur-md sticky top-0 z-10 gap-2">
            <button
              onClick={() => setSelectedImage(null)}
              className="flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-xl bg-neutral-800/80 hover:bg-neutral-800 text-neutral-300 hover:text-white border border-neutral-700/60 text-xs font-semibold transition shrink-0"
            >
              <ArrowLeft className="w-3.5 h-3.5 shrink-0" />
              <span className="hidden sm:inline">Back to Gallery</span>
              <span className="sm:hidden">Back</span>
            </button>

            <div className="text-center min-w-0">
              <h3 className="text-xs sm:text-sm font-bold text-white truncate max-w-[140px] sm:max-w-md">
                {selectedImage.theme_title || "Portrait Details"}
              </h3>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-xl text-neutral-400 hover:text-white bg-neutral-800/60 hover:bg-neutral-800 border border-neutral-700/60 transition shrink-0"
              title="Close (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ) : (
          /* Gallery Grid Header */
          <div className="px-4 sm:px-5 py-3 sm:py-4 border-b border-neutral-800/80 flex items-center justify-between bg-neutral-900/80 backdrop-blur-md sticky top-0 z-10 gap-2">
            <div className="flex items-center gap-2 sm:gap-2.5 min-w-0">
              <div className="p-1.5 sm:p-2 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-400 shrink-0">
                <ImageIcon className="w-4 h-4 sm:w-5 sm:h-5" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-1.5 sm:gap-2">
                  <h2 className="text-sm sm:text-lg font-bold text-white tracking-tight truncate">My Generations</h2>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 font-semibold border border-purple-500/30 shrink-0">
                    {generations.length}
                  </span>
                </div>
                <p className="text-xs text-neutral-400 hidden sm:block">
                  Your high-resolution AI portraits saved in durable cloud storage
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
              <button
                onClick={onRefresh}
                disabled={isLoading}
                title="Refresh gallery"
                className="p-1.5 sm:p-2 rounded-xl text-neutral-400 hover:text-white bg-neutral-800/60 hover:bg-neutral-800 border border-neutral-700/60 transition disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 sm:w-4 sm:h-4 ${isLoading ? "animate-spin text-purple-400" : ""}`} />
              </button>
              <button
                onClick={onClose}
                className="p-1.5 sm:p-2 rounded-xl text-neutral-400 hover:text-white bg-neutral-800/60 hover:bg-neutral-800 border border-neutral-700/60 transition"
                title="Close (Esc)"
              >
                <X className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Modal Body: Either Single Image Detail View OR Grid of Portraits */}
        {selectedImage ? (
          /* Detail View */
          <div className="flex-1 overflow-y-auto flex flex-col md:flex-row bg-[#0e0e12]">
            {/* Image Preview Area */}
            <div className="flex-1 bg-black/60 flex items-center justify-center p-4 sm:p-6 min-h-[350px] md:min-h-[500px]">
              {failedImageIds.has(selectedImage.id) ? (
                <div className="flex flex-col items-center justify-center text-center p-6 max-w-sm rounded-2xl bg-neutral-900 border border-neutral-800 shadow-xl">
                  <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mb-3">
                    <AlertTriangle className="w-6 h-6" />
                  </div>
                  <h4 className="text-sm font-bold text-white mb-1">Image Preview Unavailable</h4>
                  <p className="text-xs text-neutral-400 mb-4 leading-relaxed">
                    This portrait was generated before persistent cloud blob storage was activated and is no longer available on the server.
                  </p>
                  <button
                    onClick={() => handleDelete(selectedImage)}
                    disabled={deletingId === selectedImage.id}
                    className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition border ${
                      confirmDeleteId === selectedImage.id
                        ? "bg-rose-600 text-white border-rose-500 animate-pulse"
                        : "bg-rose-500/20 hover:bg-rose-500 text-rose-300 hover:text-white border-rose-500/30"
                    }`}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>
                      {deletingId === selectedImage.id
                        ? "Deleting..."
                        : confirmDeleteId === selectedImage.id
                        ? "Confirm Remove?"
                        : "Remove this Record"}
                    </span>
                  </button>
                </div>
              ) : (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img
                  src={getFullImageUrl(selectedImage.image_url)}
                  alt={selectedImage.theme_title || "Portrait"}
                  onError={() => setFailedImageIds((prev) => new Set(prev).add(selectedImage.id))}
                  className="max-h-[65vh] w-auto max-w-full object-contain rounded-xl shadow-2xl border border-neutral-800/60"
                />
              )}
            </div>

            {/* Sidebar Metadata & Actions */}
            <div className="w-full md:w-80 p-5 sm:p-6 flex flex-col justify-between border-t md:border-t-0 md:border-l border-neutral-800/80 bg-[#121217]">
              <div>
                <span className="text-[10px] uppercase font-extrabold tracking-wider text-purple-400 block mb-1">
                  Portrait Details
                </span>
                <h3 className="text-lg font-bold text-white mb-3">
                  {selectedImage.theme_title || "Custom Portrait"}
                </h3>

                <div className="space-y-3 text-xs text-neutral-300 mb-6">
                  <div className="flex items-center gap-2 text-neutral-400">
                    <Calendar className="w-3.5 h-3.5" />
                    <span>{formatDate(selectedImage.created_at)}</span>
                  </div>

                  <div className="p-3 rounded-xl bg-neutral-900 border border-neutral-800 text-[11px] text-neutral-300 leading-relaxed max-h-48 overflow-y-auto custom-scrollbar">
                    <span className="font-semibold text-neutral-400 block mb-1">Prompt:</span>
                    {selectedImage.prompt || "Likeness-preserved portrait generation"}
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="space-y-2.5 pt-4 border-t border-neutral-800">
                <button
                  onClick={() => handleDownload(selectedImage)}
                  disabled={downloadingId === selectedImage.id}
                  className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-rose-500 to-purple-600 hover:brightness-110 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-rose-500/20 transition disabled:opacity-50"
                >
                  <Download className="w-4 h-4" />
                  <span>
                    {downloadingId === selectedImage.id ? "Downloading..." : "Download Full Portrait"}
                  </span>
                </button>

                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => handleShare(selectedImage)}
                    className="py-2 px-3 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-neutral-200 font-semibold text-xs flex items-center justify-center gap-1.5 transition border border-neutral-700"
                  >
                    <Share2 className="w-3.5 h-3.5 text-rose-400" />
                    <span>Share</span>
                  </button>
                  <button
                    onClick={() => handleCopyLink(selectedImage)}
                    className="py-2 px-3 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-neutral-200 font-semibold text-xs flex items-center justify-center gap-1.5 transition border border-neutral-700"
                  >
                    {copiedId === selectedImage.id ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-emerald-400 font-bold">Copied!</span>
                      </>
                    ) : (
                      <>
                        <ExternalLink className="w-3.5 h-3.5 text-purple-400" />
                        <span>Copy Link</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Delete Portrait Button */}
                <button
                  onClick={() => handleDelete(selectedImage)}
                  disabled={deletingId === selectedImage.id}
                  className={`w-full py-2 px-3 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition border ${
                    confirmDeleteId === selectedImage.id
                      ? "bg-rose-600 hover:bg-rose-700 text-white border-rose-500 animate-pulse"
                      : "bg-neutral-900 hover:bg-rose-500/10 text-neutral-400 hover:text-rose-400 border-neutral-800 hover:border-rose-500/30"
                  }`}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>
                    {deletingId === selectedImage.id
                      ? "Deleting..."
                      : confirmDeleteId === selectedImage.id
                      ? "Click again to confirm delete"
                      : "Delete Portrait"}
                  </span>
                </button>
              </div>
            </div>
          </div>
        ) : (
          /* Grid View */
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 custom-scrollbar">
            {isLoading && generations.length === 0 ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                {[...Array(8)].map((_, idx) => (
                  <div
                    key={idx}
                    className="aspect-[4/5] rounded-xl bg-neutral-800/40 border border-neutral-800 animate-pulse flex flex-col justify-end p-3"
                  >
                    <div className="h-4 bg-neutral-700/50 rounded w-3/4 mb-2" />
                    <div className="h-3 bg-neutral-700/30 rounded w-1/2" />
                  </div>
                ))}
              </div>
            ) : generations.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="w-16 h-16 rounded-2xl bg-neutral-900 border border-neutral-800 flex items-center justify-center mb-4 text-purple-400 shadow-inner">
                  <Sparkles className="w-8 h-8 animate-pulse" />
                </div>
                <h3 className="text-base font-semibold text-white mb-1">No portraits yet</h3>
                <p className="text-sm text-neutral-400 max-w-sm mb-5">
                  Upload a photo, choose a trending aesthetic above, and create your first AI portrait!
                </p>
                <button
                  onClick={onClose}
                  className="px-4 py-2 rounded-xl bg-gradient-to-r from-rose-500 to-purple-600 text-white text-xs font-bold hover:brightness-110 transition shadow-lg shadow-purple-500/20"
                >
                  Create a Portrait Now
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 sm:gap-4">
                {generations.map((item) => {
                  const thumbUrl = getFullImageUrl(item.thumbnail_url || item.image_url);
                  const isBroken = failedImageIds.has(item.id);

                  return (
                    <div
                      key={item.id}
                      onClick={() => setSelectedImage(item)}
                      className="group relative aspect-[4/5] rounded-xl overflow-hidden bg-neutral-900 border border-neutral-800 hover:border-purple-500/50 transition cursor-pointer shadow-md"
                    >
                      {/* Portrait Image or Broken Placeholder */}
                      {isBroken ? (
                        <div className="w-full h-full flex flex-col items-center justify-center bg-neutral-900/95 p-3 text-center border border-dashed border-neutral-800">
                          <AlertTriangle className="w-6 h-6 text-amber-400/80 mb-1" />
                          <span className="text-[11px] font-semibold text-neutral-300">Unavailable</span>
                          <span className="text-[9px] text-neutral-500 mt-0.5">Pre-cloud image</span>
                          <button
                            onClick={(e) => handleDelete(item, e)}
                            disabled={deletingId === item.id}
                            className={`mt-2.5 px-2 py-0.5 rounded text-[10px] font-semibold flex items-center gap-1 border transition ${
                              confirmDeleteId === item.id
                                ? "bg-rose-600 text-white border-rose-500 animate-pulse"
                                : "bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border-rose-500/20"
                            }`}
                          >
                            <Trash2 className="w-2.5 h-2.5" />
                            <span>{confirmDeleteId === item.id ? "Confirm?" : "Delete"}</span>
                          </button>
                        </div>
                      ) : (
                        /* eslint-disable-next-line @next/next/no-img-element */
                        <img
                          src={thumbUrl}
                          alt={item.theme_title || "Portrait"}
                          loading="lazy"
                          onError={() => setFailedImageIds((prev) => new Set(prev).add(item.id))}
                          className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
                        />
                      )}

                      {/* Hover / Touch Overlay */}
                      <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/30 to-transparent sm:from-black/90 sm:via-black/20 sm:opacity-90 sm:group-hover:opacity-100 transition flex flex-col justify-between p-2 sm:p-3 pointer-events-none">
                        {/* Top Badges */}
                        <div className="flex items-center justify-between pointer-events-auto">
                          <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full bg-black/60 backdrop-blur-md text-white border border-white/10">
                            {item.aspect_ratio || "4:5"}
                          </span>
                          {item.storage_provider === "azure_blob" && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-500/30 text-blue-300 font-medium backdrop-blur-md border border-blue-400/20">
                              Cloud
                            </span>
                          )}
                        </div>

                        {/* Bottom Info & Quick Actions */}
                        <div className="pointer-events-auto">
                          <p className="text-xs font-bold text-white truncate drop-shadow-sm">
                            {item.theme_title || "Custom Portrait"}
                          </p>
                          <div className="flex items-center justify-between text-[10px] text-neutral-400 mt-0.5">
                            <span className="truncate pr-1">{formatDate(item.created_at)}</span>

                            {/* Quick Action Buttons */}
                            <div
                              className="flex items-center gap-1 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition shrink-0"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {!isBroken && (
                                <>
                                  <button
                                    onClick={(e) => handleDownload(item, e)}
                                    disabled={downloadingId === item.id}
                                    title="Download"
                                    className="p-1 rounded-md bg-white/20 hover:bg-white text-white hover:text-black transition backdrop-blur-md"
                                  >
                                    <Download className="w-3 h-3" />
                                  </button>
                                  <button
                                    onClick={(e) => handleCopyLink(item, e)}
                                    title="Copy link"
                                    className="p-1 rounded-md bg-white/20 hover:bg-white text-white hover:text-black transition backdrop-blur-md"
                                  >
                                    {copiedId === item.id ? (
                                      <Check className="w-3 h-3 text-emerald-400" />
                                    ) : (
                                      <ExternalLink className="w-3 h-3" />
                                    )}
                                  </button>
                                </>
                              )}
                              <button
                                onClick={(e) => handleDelete(item, e)}
                                disabled={deletingId === item.id}
                                title={confirmDeleteId === item.id ? "Click again to confirm delete" : "Delete portrait"}
                                className={`p-1 rounded-md transition backdrop-blur-md ${
                                  confirmDeleteId === item.id
                                    ? "bg-rose-600 text-white animate-pulse"
                                    : "bg-white/20 hover:bg-rose-500 text-white"
                                }`}
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
