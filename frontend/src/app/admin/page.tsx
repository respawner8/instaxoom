"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Shield,
  Coins,
  Users,
  Clock,
  ArrowLeft,
  Plus,
  Search,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  LogOut,
  Mail,
  UserCheck,
  RefreshCw,
  History,
  Edit3,
  Trash2,
  Copy,
  Check,
  X,
  Image as ImageIcon,
  Activity,
  Eye,
  Zap,
  TrendingUp,
  BarChart3,
  Calendar,
} from "lucide-react";
import { useAuth, User } from "@/context/AuthContext";

export interface DailyMetricTrend {
  date: string;
  visits: number;
  unique_visitors: number;
  generations: number;
}

export interface AdminMetricsOverview {
  total_site_visits: number;
  live_visitors_today: number;
  total_images_generated: number;
  images_generated_today: number;
  daily_trends: DailyMetricTrend[];
}

interface AdminUserItem {
  id: string;
  email: string;
  name: string;
  avatar_url?: string;
  role: string;
  credits: number;
  free_credits_claimed?: boolean;
  created_at: string;
  last_login_at: string;
}

interface PendingCreditItem {
  id: string;
  email: string;
  credits: number;
  status: string;
  created_at: string;
}

interface TransactionItem {
  id: string;
  user_email: string;
  amount: number;
  balance_after: number;
  action: string;
  description?: string;
  created_at: string;
}

interface AdminThemeItem {
  id: string;
  title: string;
  category: string;
  tagline: string;
  prompt_template: string;
  hashtags: string[];
  preview_image_url?: string;
  is_active: boolean;
  order_index: number;
  created_at: string;
  updated_at: string;
}


export default function AdminPage() {
  const router = useRouter();
  const { user, token, isLoading: authLoading, logout } = useAuth();

  // Admin Data states
  const [usersList, setUsersList] = useState<AdminUserItem[]>([]);
  const [pendingList, setPendingList] = useState<PendingCreditItem[]>([]);
  const [transactionsList, setTransactionsList] = useState<TransactionItem[]>([]);
  const [themesList, setThemesList] = useState<AdminThemeItem[]>([]);
  const [metricsData, setMetricsData] = useState<AdminMetricsOverview | null>(null);
  const [isLoadingData, setIsLoadingData] = useState<boolean>(true);

  // Form states
  const [assignEmail, setAssignEmail] = useState<string>("");
  const [assignCredits, setAssignCredits] = useState<number>(5);
  const [assignNote, setAssignNote] = useState<string>("Admin trial credit grant");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [actionNotice, setActionNotice] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  // Filter & tab states
  const [activeTab, setActiveTab] = useState<"users" | "pending" | "transactions" | "themes" | "activity">("users");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [themeSearchQuery, setThemeSearchQuery] = useState<string>("");

  // Theme Management Modal & Actions state
  const [isThemeModalOpen, setIsThemeModalOpen] = useState<boolean>(false);
  const [editingTheme, setEditingTheme] = useState<AdminThemeItem | null>(null);
  const [isDeletingThemeId, setIsDeletingThemeId] = useState<string | null>(null);
  const [copiedPromptId, setCopiedPromptId] = useState<string | null>(null);

  const [themeFormData, setThemeFormData] = useState({
    id: "",
    title: "",
    category: "Professional",
    tagline: "",
    prompt_template: "",
    hashtags: "",
    preview_image_url: "",
    is_active: true,
    order_index: 0,
  });
  const [isSubmittingTheme, setIsSubmittingTheme] = useState<boolean>(false);
  const [themeModalError, setThemeModalError] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Check auth and role
  useEffect(() => {
    if (!authLoading) {
      if (!user || user.role !== "admin") {
        router.push("/");
      } else if (token) {
        loadAdminData();
      }
    }
  }, [user, token, authLoading, router]);

  const loadAdminData = async () => {
    if (!token) return;
    setIsLoadingData(true);

    try {
      const headers = { Authorization: `Bearer ${token}` };
      const [usersRes, pendingRes, txRes, themesRes, metricsRes] = await Promise.all([
        fetch(`${apiUrl}/api/admin/users`, { headers }),
        fetch(`${apiUrl}/api/admin/pending-credits`, { headers }),
        fetch(`${apiUrl}/api/admin/transactions`, { headers }),
        fetch(`${apiUrl}/api/admin/themes`, { headers }),
        fetch(`${apiUrl}/api/admin/metrics/overview`, { headers }),
      ]);

      if (usersRes.ok) {
        const data = await usersRes.json();
        setUsersList(data);
      }
      if (pendingRes.ok) {
        const data = await pendingRes.json();
        setPendingList(data);
      }
      if (txRes.ok) {
        const data = await txRes.json();
        setTransactionsList(data);
      }
      if (themesRes.ok) {
        const data = await themesRes.json();
        setThemesList(data);
      }
      if (metricsRes.ok) {
        const data = await metricsRes.json();
        setMetricsData(data);
      }
    } catch (err) {
      console.error("Error loading admin data:", err);
    } finally {
      setIsLoadingData(false);
    }
  };

  const openCreateThemeModal = () => {
    setEditingTheme(null);
    setThemeFormData({
      id: "",
      title: "",
      category: "Professional",
      tagline: "",
      prompt_template: "",
      hashtags: "#CreatorBot",
      preview_image_url: "",
      is_active: true,
      order_index: themesList.length,
    });
    setThemeModalError(null);
    setIsThemeModalOpen(true);
  };

  const openEditThemeModal = (theme: AdminThemeItem) => {
    setEditingTheme(theme);
    setThemeFormData({
      id: theme.id,
      title: theme.title,
      category: theme.category,
      tagline: theme.tagline,
      prompt_template: theme.prompt_template,
      hashtags: (theme.hashtags || []).join(", "),
      preview_image_url: theme.preview_image_url || "",
      is_active: theme.is_active,
      order_index: theme.order_index,
    });
    setThemeModalError(null);
    setIsThemeModalOpen(true);
  };

  const handleSaveTheme = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    if (!themeFormData.title.trim()) {
      setThemeModalError("Title is required.");
      return;
    }
    if (!themeFormData.prompt_template.trim()) {
      setThemeModalError("Prompt template is required.");
      return;
    }

    setIsSubmittingTheme(true);
    setThemeModalError(null);

    try {
      const rawHashtags = themeFormData.hashtags
        .split(",")
        .map((h) => h.trim())
        .filter(Boolean);

      const payload = {
        title: themeFormData.title.trim(),
        category: themeFormData.category.trim() || "General",
        tagline: themeFormData.tagline.trim(),
        prompt_template: themeFormData.prompt_template.trim(),
        hashtags: rawHashtags,
        preview_image_url: themeFormData.preview_image_url.trim() || null,
        is_active: themeFormData.is_active,
        order_index: Number(themeFormData.order_index) || 0,
        ...(editingTheme ? {} : { id: themeFormData.id.trim() || undefined }),
      };

      const url = editingTheme
        ? `${apiUrl}/api/admin/themes/${encodeURIComponent(editingTheme.id)}`
        : `${apiUrl}/api/admin/themes`;
      const method = editingTheme ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Failed to save theme.");
      }

      setActionNotice({
        type: "success",
        message: editingTheme
          ? `Prompt theme "${themeFormData.title}" updated successfully.`
          : `New prompt theme "${themeFormData.title}" created successfully.`,
      });
      setIsThemeModalOpen(false);
      loadAdminData();
    } catch (err: any) {
      setThemeModalError(err.message || "An error occurred while saving.");
    } finally {
      setIsSubmittingTheme(false);
    }
  };

  const handleDeleteTheme = async (themeId: string, title: string) => {
    if (!token) return;
    const confirmed = window.confirm(
      `Are you sure you want to permanently delete the prompt theme "${title}"?`
    );
    if (!confirmed) return;

    setIsDeletingThemeId(themeId);
    try {
      const res = await fetch(`${apiUrl}/api/admin/themes/${encodeURIComponent(themeId)}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Failed to delete prompt theme.");
      }

      setActionNotice({
        type: "success",
        message: `Prompt theme "${title}" has been deleted.`,
      });
      loadAdminData();
    } catch (err: any) {
      setActionNotice({
        type: "error",
        message: err.message || "Failed to delete prompt theme.",
      });
    } finally {
      setIsDeletingThemeId(null);
    }
  };

  const handleToggleActiveTheme = async (theme: AdminThemeItem) => {
    if (!token) return;
    try {
      const res = await fetch(`${apiUrl}/api/admin/themes/${encodeURIComponent(theme.id)}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ is_active: !theme.is_active }),
      });
      if (res.ok) {
        setThemesList((prev) =>
          prev.map((t) => (t.id === theme.id ? { ...t, is_active: !t.is_active } : t))
        );
      }
    } catch (err) {
      console.error("Failed to toggle theme active status:", err);
    }
  };

  const handleCopyPrompt = (themeId: string, promptText: string) => {
    navigator.clipboard.writeText(promptText);
    setCopiedPromptId(themeId);
    setTimeout(() => setCopiedPromptId(null), 2000);
  };


  const handleAssignCredits = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !assignEmail.trim() || assignCredits <= 0) return;

    setIsSubmitting(true);
    setActionNotice(null);

    try {
      const res = await fetch(`${apiUrl}/api/admin/credits/assign`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          email: assignEmail.trim().toLowerCase(),
          credits: assignCredits,
          description: assignNote.trim(),
        }),
      });

      const data = await res.json();

      if (res.ok) {
        setActionNotice({
          type: "success",
          message: data.message || `Successfully granted ${assignCredits} credits to ${assignEmail}!`,
        });
        setAssignEmail("");
        setAssignCredits(5);
        await loadAdminData();
      } else {
        setActionNotice({
          type: "error",
          message: data.detail || "Failed to assign credits. Please verify the email.",
        });
      }
    } catch (err: any) {
      setActionNotice({
        type: "error",
        message: err.message || "Network error while assigning credits.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickAdd = (targetEmail: string) => {
    setAssignEmail(targetEmail);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  if (authLoading || (!user && !authLoading)) {
    return (
      <div className="min-h-screen bg-[#0a0a0c] flex items-center justify-center text-neutral-400">
        <div className="flex items-center gap-3">
          <RefreshCw className="w-5 h-5 animate-spin text-rose-500" />
          <span>Verifying administrator permissions...</span>
        </div>
      </div>
    );
  }

  if (user?.role !== "admin") {
    return (
      <div className="min-h-screen bg-[#0a0a0c] flex flex-col items-center justify-center text-neutral-300 gap-4">
        <Shield className="w-12 h-12 text-rose-500" />
        <h2 className="text-xl font-bold">Access Restricted</h2>
        <p className="text-sm text-neutral-400">This portal is reserved for CreatorBot administrators.</p>
        <Link
          href="/"
          className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-sm font-semibold transition"
        >
          Return to Studio
        </Link>
      </div>
    );
  }

  const totalCreditsCirculating = usersList.reduce((acc, u) => acc + (u.credits || 0), 0);
  const totalPendingCredits = pendingList.reduce((acc, p) => acc + (p.credits || 0), 0);

  const filteredUsers = usersList.filter(
    (u) =>
      u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (u.name && u.name.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const filteredThemes = themesList.filter((t) => {
    if (!themeSearchQuery.trim()) return true;
    const q = themeSearchQuery.toLowerCase();
    return (
      t.title.toLowerCase().includes(q) ||
      t.category.toLowerCase().includes(q) ||
      (t.tagline && t.tagline.toLowerCase().includes(q)) ||
      t.prompt_template.toLowerCase().includes(q) ||
      t.id.toLowerCase().includes(q)
    );
  });

  return (
    <div className="min-h-screen bg-[#0a0a0c] text-neutral-100 flex flex-col">
      {/* Top Header */}
      <header className="border-b border-neutral-800/80 backdrop-blur-md sticky top-0 z-50 bg-[#0a0a0c]/80 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-2 text-xs font-semibold text-neutral-400 hover:text-white transition px-3 py-1.5 rounded-lg bg-neutral-900 border border-neutral-800"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>AI Studio</span>
          </Link>

          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-tr from-amber-500 via-rose-500 to-purple-600 flex items-center justify-center font-bold text-white shadow-md shadow-rose-500/20">
              <Shield className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-lg tracking-tight">Admin Portal</span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  SUPERUSER
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs text-neutral-300">
            {user.avatar_url ? (
              <img
                src={user.avatar_url}
                alt={user.name || user.email}
                className="w-7 h-7 rounded-full border border-neutral-700"
              />
            ) : (
              <div className="w-7 h-7 rounded-full bg-rose-500/20 border border-rose-500/40 flex items-center justify-center text-rose-300 font-bold">
                {user.email[0].toUpperCase()}
              </div>
            )}
            <span className="hidden sm:inline font-medium">{user.email}</span>
          </div>

          <button
            onClick={() => {
              logout();
              router.push("/");
            }}
            className="flex items-center gap-1.5 text-xs font-medium text-neutral-400 hover:text-rose-400 transition px-2.5 py-1.5 rounded-lg hover:bg-neutral-900"
            title="Sign out"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto w-full px-4 py-8 flex-1 space-y-8">
        
        {/* Global Action Notice */}
        {actionNotice && (
          <div
            className={`p-4 rounded-2xl text-sm flex items-start justify-between gap-3 border shadow-lg transition-all ${
              actionNotice.type === "success"
                ? "bg-emerald-950/50 border-emerald-500/40 text-emerald-200"
                : "bg-rose-950/50 border-rose-500/40 text-rose-200"
            }`}
          >
            <div className="flex items-center gap-3">
              {actionNotice.type === "success" ? (
                <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-400" />
              ) : (
                <AlertCircle className="w-5 h-5 shrink-0 text-rose-400" />
              )}
              <span className="font-semibold text-xs sm:text-sm">{actionNotice.message}</span>
            </div>
            <button
              onClick={() => setActionNotice(null)}
              className="p-1 hover:bg-neutral-800/60 rounded-lg text-neutral-400 hover:text-white transition shrink-0"
              title="Dismiss"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Platform Traffic & Generation Activity - Primary KPI Hero Grid */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-400 flex items-center gap-2">
              <Activity className="w-3.5 h-3.5 text-emerald-400" />
              Traffic & Generation Activity
            </h3>
            <button
              onClick={() => setActiveTab("activity")}
              className="text-[11px] text-rose-400 hover:text-rose-300 font-medium flex items-center gap-1 transition"
            >
              <BarChart3 className="w-3.5 h-3.5" />
              <span>View 7-day breakdown</span>
            </button>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {/* 1. Live Users Visiting Today */}
            <div
              onClick={() => setActiveTab("activity")}
              className="bg-neutral-900/60 border border-emerald-500/30 hover:border-emerald-500/50 rounded-2xl p-5 backdrop-blur-xl transition group shadow-lg shadow-emerald-950/10 cursor-pointer"
            >
              <div className="flex items-center justify-between text-neutral-400 text-xs font-medium mb-2">
                <span className="group-hover:text-emerald-300 transition flex items-center gap-1.5 font-semibold">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                  Live Visitors Today
                </span>
                <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <Users className="w-4 h-4" />
                </div>
              </div>
              <div className="text-3xl font-extrabold text-white tracking-tight">
                {metricsData ? metricsData.live_visitors_today.toLocaleString() : "—"}
              </div>
              <p className="text-[11px] text-neutral-500 mt-1 flex items-center justify-between">
                <span>Unique daily visitors</span>
                <span className="text-emerald-400 font-bold text-[10px] bg-emerald-500/10 px-1.5 py-0.5 rounded">Today</span>
              </p>
            </div>

            {/* 2. Images Generated Per Day (Today) */}
            <div
              onClick={() => setActiveTab("activity")}
              className="bg-neutral-900/60 border border-amber-500/30 hover:border-amber-500/50 rounded-2xl p-5 backdrop-blur-xl transition group shadow-lg shadow-amber-950/10 cursor-pointer"
            >
              <div className="flex items-center justify-between text-neutral-400 text-xs font-medium mb-2">
                <span className="group-hover:text-amber-300 transition flex items-center gap-1.5 font-semibold">
                  <Zap className="w-3.5 h-3.5 text-amber-400" />
                  Images Generated Today
                </span>
                <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  <Sparkles className="w-4 h-4" />
                </div>
              </div>
              <div className="text-3xl font-extrabold text-white tracking-tight">
                {metricsData ? metricsData.images_generated_today.toLocaleString() : "—"}
              </div>
              <p className="text-[11px] text-neutral-500 mt-1 flex items-center justify-between">
                <span>Creations produced today</span>
                <span className="text-amber-400 font-bold text-[10px] bg-amber-500/10 px-1.5 py-0.5 rounded">Today</span>
              </p>
            </div>

            {/* 3. Total Site Visits */}
            <div
              onClick={() => setActiveTab("activity")}
              className="bg-neutral-900/60 border border-sky-500/30 hover:border-sky-500/50 rounded-2xl p-5 backdrop-blur-xl transition group shadow-lg shadow-sky-950/10 cursor-pointer"
            >
              <div className="flex items-center justify-between text-neutral-400 text-xs font-medium mb-2">
                <span className="group-hover:text-sky-300 transition flex items-center gap-1.5 font-semibold">
                  <Eye className="w-3.5 h-3.5 text-sky-400" />
                  Total Site Visits
                </span>
                <div className="p-1.5 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
                  <TrendingUp className="w-4 h-4" />
                </div>
              </div>
              <div className="text-3xl font-extrabold text-white tracking-tight">
                {metricsData ? metricsData.total_site_visits.toLocaleString() : "—"}
              </div>
              <p className="text-[11px] text-neutral-500 mt-1 flex items-center justify-between">
                <span>Total sessions recorded</span>
                <span className="text-sky-400 font-bold text-[10px] bg-sky-500/10 px-1.5 py-0.5 rounded">Lifetime</span>
              </p>
            </div>

            {/* 4. Total Images Generated Till Now */}
            <div
              onClick={() => setActiveTab("activity")}
              className="bg-neutral-900/60 border border-rose-500/30 hover:border-rose-500/50 rounded-2xl p-5 backdrop-blur-xl transition group shadow-lg shadow-rose-950/10 cursor-pointer"
            >
              <div className="flex items-center justify-between text-neutral-400 text-xs font-medium mb-2">
                <span className="group-hover:text-rose-300 transition flex items-center gap-1.5 font-semibold">
                  <ImageIcon className="w-3.5 h-3.5 text-rose-400" />
                  Total Images Generated
                </span>
                <div className="p-1.5 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
                  <Coins className="w-4 h-4" />
                </div>
              </div>
              <div className="text-3xl font-extrabold text-white tracking-tight">
                {metricsData ? metricsData.total_images_generated.toLocaleString() : "—"}
              </div>
              <p className="text-[11px] text-neutral-500 mt-1 flex items-center justify-between">
                <span>Portraits generated till now</span>
                <span className="text-rose-400 font-bold text-[10px] bg-rose-500/10 px-1.5 py-0.5 rounded">Lifetime</span>
              </p>
            </div>
          </div>
        </div>

        {/* Accounts & Credits KPI Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-2xl p-5 backdrop-blur-xl">
            <div className="flex items-center justify-between text-neutral-400 text-xs font-medium mb-2">
              <span>Registered Users</span>
              <Users className="w-4 h-4 text-rose-400" />
            </div>
            <div className="text-3xl font-extrabold text-white">{usersList.length}</div>
            <p className="text-[11px] text-neutral-500 mt-1">Google OAuth registered accounts</p>
          </div>

          <div
            onClick={() => setActiveTab("themes")}
            className="bg-neutral-900/60 border border-neutral-800/80 rounded-2xl p-5 backdrop-blur-xl cursor-pointer hover:border-rose-500/50 transition group"
          >
            <div className="flex items-center justify-between text-neutral-400 text-xs font-medium mb-2">
              <span className="group-hover:text-rose-300 transition">Prompts & Themes</span>
              <Sparkles className="w-4 h-4 text-rose-400" />
            </div>
            <div className="text-3xl font-extrabold text-white">{themesList.length}</div>
            <p className="text-[11px] text-neutral-500 mt-1">
              {themesList.filter((t) => t.is_active).length} active styles published
            </p>
          </div>

          <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-2xl p-5 backdrop-blur-xl">
            <div className="flex items-center justify-between text-neutral-400 text-xs font-medium mb-2">
              <span>Circulating Credits</span>
              <Coins className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-3xl font-extrabold text-white">{totalCreditsCirculating}</div>
            <p className="text-[11px] text-neutral-500 mt-1">Live balances across all users</p>
          </div>

          <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-2xl p-5 backdrop-blur-xl">
            <div className="flex items-center justify-between text-neutral-400 text-xs font-medium mb-2">
              <span>Pending Grants</span>
              <Clock className="w-4 h-4 text-purple-400" />
            </div>
            <div className="text-3xl font-extrabold text-white">{pendingList.length}</div>
            <p className="text-[11px] text-neutral-500 mt-1">{totalPendingCredits} credits reserved</p>
          </div>

          <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-2xl p-5 backdrop-blur-xl col-span-2 sm:col-span-1">
            <div className="flex items-center justify-between text-neutral-400 text-xs font-medium mb-2">
              <span>Audit Records</span>
              <History className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-3xl font-extrabold text-white">{transactionsList.length}</div>
            <p className="text-[11px] text-neutral-500 mt-1">Recent generation & grant events</p>
          </div>
        </div>

        {/* Credit Assignment Form Card */}
        <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-3xl p-6 sm:p-8 backdrop-blur-xl shadow-2xl">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="w-5 h-5 text-amber-400" />
            <h2 className="text-xl font-bold">Assign Trial Credits</h2>
          </div>
          <p className="text-neutral-400 text-xs sm:text-sm mb-6">
            Grant generation credits directly to any email. If the user hasn&apos;t signed up yet, credits are securely reserved in Neon PostgreSQL and automatically granted on their first Google login.
          </p>

          <form onSubmit={handleAssignCredits} className="space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              
              {/* Email Input */}
              <div className="space-y-1.5 md:col-span-2">
                <label className="text-xs font-semibold text-neutral-300 flex items-center gap-1.5">
                  <Mail className="w-3.5 h-3.5 text-rose-400" />
                  Recipient Email
                </label>
                <input
                  type="email"
                  required
                  placeholder="e.g. colleague@company.com or creator@gmail.com"
                  value={assignEmail}
                  onChange={(e) => setAssignEmail(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 focus:border-rose-500/80 focus:ring-1 focus:ring-rose-500 text-sm text-neutral-100 placeholder-neutral-600 outline-none transition"
                />
              </div>

              {/* Credits Amount */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-neutral-300 flex items-center gap-1.5">
                  <Coins className="w-3.5 h-3.5 text-amber-400" />
                  Credits (1 credit = 1 portrait)
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min="1"
                    max="1000"
                    required
                    value={assignCredits}
                    onChange={(e) => setAssignCredits(parseInt(e.target.value) || 1)}
                    className="w-full px-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 focus:border-amber-500/80 focus:ring-1 focus:ring-amber-500 text-sm text-neutral-100 outline-none transition"
                  />
                  <div className="flex gap-1">
                    {[5, 10, 25].map((preset) => (
                      <button
                        type="button"
                        key={preset}
                        onClick={() => setAssignCredits(preset)}
                        className={`px-2 py-2 text-xs font-semibold rounded-lg border transition ${
                          assignCredits === preset
                            ? "bg-amber-500/20 border-amber-500/60 text-amber-300"
                            : "bg-neutral-800/80 border-neutral-700 text-neutral-400 hover:text-white"
                        }`}
                      >
                        +{preset}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Note & Submit */}
            <div className="flex flex-col sm:flex-row gap-4 items-end">
              <div className="space-y-1.5 flex-1 w-full">
                <label className="text-xs font-semibold text-neutral-300">
                  Grant Description / Note (Visible in Audit Log)
                </label>
                <input
                  type="text"
                  placeholder="e.g. VIP Creator Trial Grant"
                  value={assignNote}
                  onChange={(e) => setAssignNote(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 focus:border-neutral-700 text-sm text-neutral-100 placeholder-neutral-600 outline-none transition"
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting || !assignEmail.trim()}
                className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 via-rose-500 to-purple-600 hover:from-amber-600 hover:via-rose-600 hover:to-purple-700 text-white font-semibold text-sm transition shadow-lg shadow-rose-500/25 disabled:opacity-50 flex items-center justify-center gap-2 whitespace-nowrap"
              >
                {isSubmitting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Processing...</span>
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" />
                    <span>Grant Credits</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>

        {/* Tabbed Data Section */}
        <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-3xl p-6 sm:p-8 backdrop-blur-xl shadow-2xl space-y-6">
          
          {/* Header & Tabs */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-neutral-800/80 pb-4">
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={() => setActiveTab("users")}
                className={`px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 ${
                  activeTab === "users"
                    ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                    : "text-neutral-400 hover:text-white"
                }`}
              >
                <Users className="w-3.5 h-3.5" />
                <span>Users ({usersList.length})</span>
              </button>

              <button
                onClick={() => setActiveTab("pending")}
                className={`px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 ${
                  activeTab === "pending"
                    ? "bg-purple-500/20 text-purple-300 border border-purple-500/40"
                    : "text-neutral-400 hover:text-white"
                }`}
              >
                <Clock className="w-3.5 h-3.5" />
                <span>Pending Grants ({pendingList.length})</span>
              </button>

              <button
                onClick={() => setActiveTab("transactions")}
                className={`px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 ${
                  activeTab === "transactions"
                    ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                    : "text-neutral-400 hover:text-white"
                }`}
              >
                <History className="w-3.5 h-3.5" />
                <span>Audit Log</span>
              </button>

              <button
                onClick={() => setActiveTab("themes")}
                className={`px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 ${
                  activeTab === "themes"
                    ? "bg-rose-500/20 text-rose-300 border border-rose-500/40 shadow-sm shadow-rose-500/20"
                    : "text-neutral-400 hover:text-white"
                }`}
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Prompts & Themes ({themesList.length})</span>
              </button>

              <button
                onClick={() => setActiveTab("activity")}
                className={`px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 ${
                  activeTab === "activity"
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm shadow-emerald-500/20"
                    : "text-neutral-400 hover:text-white"
                }`}
              >
                <BarChart3 className="w-3.5 h-3.5" />
                <span>Activity & Trends</span>
              </button>
            </div>

            <div className="flex items-center gap-3">
              {activeTab === "users" && (
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-neutral-500 absolute left-3 top-3" />
                  <input
                    type="text"
                    placeholder="Search by email or name..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-8 pr-3 py-1.5 rounded-lg bg-neutral-950 border border-neutral-800 text-xs text-neutral-100 placeholder-neutral-600 outline-none w-48 sm:w-60 focus:border-neutral-700"
                  />
                </div>
              )}

              {activeTab === "themes" && (
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 text-neutral-500 absolute left-3 top-3" />
                    <input
                      type="text"
                      placeholder="Filter prompts or themes..."
                      value={themeSearchQuery}
                      onChange={(e) => setThemeSearchQuery(e.target.value)}
                      className="pl-8 pr-3 py-1.5 rounded-lg bg-neutral-950 border border-neutral-800 text-xs text-neutral-100 placeholder-neutral-600 outline-none w-44 sm:w-56 focus:border-neutral-700"
                    />
                  </div>
                  <button
                    onClick={openCreateThemeModal}
                    className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-rose-500 to-purple-600 hover:from-rose-600 hover:to-purple-700 text-white font-semibold text-xs flex items-center gap-1.5 transition shadow-md shadow-rose-500/20 whitespace-nowrap"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>New Prompt</span>
                  </button>
                </div>
              )}

              <button
                onClick={loadAdminData}
                disabled={isLoadingData}
                className="p-2 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-400 hover:text-white transition"
                title="Refresh Table"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isLoadingData ? "animate-spin text-rose-400" : ""}`} />
              </button>
            </div>
          </div>

          {/* Tab 1: Registered Users */}
          {activeTab === "users" && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-neutral-300">
                <thead className="bg-neutral-950/60 text-neutral-400 uppercase tracking-wider font-semibold border-b border-neutral-800">
                  <tr>
                    <th className="py-3 px-4">User</th>
                    <th className="py-3 px-4">Role</th>
                    <th className="py-3 px-4 text-center">Credit Balance</th>
                    <th className="py-3 px-4 text-center">Free Trial</th>
                    <th className="py-3 px-4">Created Date</th>
                    <th className="py-3 px-4">Last Login</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/60 font-medium">
                  {filteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-neutral-500">
                        {searchQuery ? "No users matching search query." : "No registered users yet."}
                      </td>
                    </tr>
                  ) : (
                    filteredUsers.map((u) => (
                      <tr key={u.id} className="hover:bg-neutral-800/30 transition">
                        <td className="py-3 px-4 flex items-center gap-2.5">
                          {u.avatar_url ? (
                            <img src={u.avatar_url} alt={u.name} className="w-7 h-7 rounded-full border border-neutral-700" />
                          ) : (
                            <div className="w-7 h-7 rounded-full bg-neutral-800 border border-neutral-700 flex items-center justify-center font-bold text-neutral-300">
                              {u.email[0].toUpperCase()}
                            </div>
                          )}
                          <div>
                            <div className="font-semibold text-neutral-100">{u.name || "Unnamed"}</div>
                            <div className="text-[11px] text-neutral-400 font-mono">{u.email}</div>
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                              u.role === "admin"
                                ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                                : "bg-neutral-800 text-neutral-300 border border-neutral-700"
                            }`}
                          >
                            {u.role.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center">
                          <span className="inline-flex items-center gap-1 font-bold text-amber-300 bg-amber-500/10 px-2.5 py-1 rounded-full border border-amber-500/20">
                            <Coins className="w-3 h-3" />
                            {u.credits}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center">
                          {u.free_credits_claimed ? (
                            <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                              Claimed
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-[10px] font-bold text-neutral-400 bg-neutral-800 px-2 py-0.5 rounded-full border border-neutral-700">
                              Unclaimed
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-neutral-400 text-[11px]">
                          {u.created_at ? new Date(u.created_at).toLocaleDateString() : "-"}
                        </td>
                        <td className="py-3 px-4 text-neutral-400 text-[11px]">
                          {u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : "-"}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => handleQuickAdd(u.email)}
                            className="px-2.5 py-1 rounded-lg bg-neutral-800 hover:bg-rose-500/20 hover:border-rose-500/40 hover:text-rose-300 border border-neutral-700 text-neutral-300 text-[11px] font-medium transition flex items-center gap-1 ml-auto"
                          >
                            <Plus className="w-3 h-3" />
                            <span>Add Credits</span>
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Tab 2: Pending Invitations */}
          {activeTab === "pending" && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-neutral-300">
                <thead className="bg-neutral-950/60 text-neutral-400 uppercase tracking-wider font-semibold border-b border-neutral-800">
                  <tr>
                    <th className="py-3 px-4">Reserved Email</th>
                    <th className="py-3 px-4 text-center">Credits Waiting</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Reserved Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/60 font-medium">
                  {pendingList.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="py-8 text-center text-neutral-500">
                        No pending grants waiting for signup.
                      </td>
                    </tr>
                  ) : (
                    pendingList.map((p) => (
                      <tr key={p.id} className="hover:bg-neutral-800/30 transition">
                        <td className="py-3 px-4 font-mono text-neutral-200">
                          {p.email}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <span className="inline-flex items-center gap-1 font-bold text-purple-300 bg-purple-500/10 px-2.5 py-1 rounded-full border border-purple-500/20">
                            <Coins className="w-3 h-3" />
                            {p.credits}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            Awaiting Google Sign-in
                          </span>
                        </td>
                        <td className="py-3 px-4 text-neutral-400 text-[11px]">
                          {p.created_at ? new Date(p.created_at).toLocaleDateString() : "-"}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Tab 3: Transactions Audit Log */}
          {activeTab === "transactions" && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-neutral-300">
                <thead className="bg-neutral-950/60 text-neutral-400 uppercase tracking-wider font-semibold border-b border-neutral-800">
                  <tr>
                    <th className="py-3 px-4">Timestamp</th>
                    <th className="py-3 px-4">User</th>
                    <th className="py-3 px-4">Action</th>
                    <th className="py-3 px-4 text-center">Amount</th>
                    <th className="py-3 px-4 text-center">Balance After</th>
                    <th className="py-3 px-4">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/60 font-medium">
                  {transactionsList.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-neutral-500">
                        No credit activity logged yet.
                      </td>
                    </tr>
                  ) : (
                    transactionsList.map((tx) => (
                      <tr key={tx.id} className="hover:bg-neutral-800/30 transition">
                        <td className="py-3 px-4 text-neutral-400 text-[11px] whitespace-nowrap">
                          {tx.created_at ? new Date(tx.created_at).toLocaleString() : "-"}
                        </td>
                        <td className="py-3 px-4 font-mono text-neutral-200">
                          {tx.user_email}
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                              tx.action === "generation"
                                ? "bg-rose-500/10 text-rose-300 border border-rose-500/20"
                                : "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20"
                            }`}
                          >
                            {tx.action.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center font-bold">
                          <span className={tx.amount > 0 ? "text-emerald-400" : "text-rose-400"}>
                            {tx.amount > 0 ? `+${tx.amount}` : tx.amount}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center font-semibold text-neutral-300">
                          {tx.balance_after}
                        </td>
                        <td className="py-3 px-4 text-neutral-400 text-[11px]">
                          {tx.description || "-"}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Tab 4: Prompts & Themes */}
          {activeTab === "themes" && (
            <div className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-neutral-950/60 border border-neutral-800/80 rounded-2xl p-4">
                <div>
                  <h3 className="text-sm font-semibold text-neutral-200">
                    Active Catalog & FLUX Prompt Presets
                  </h3>
                  <p className="text-xs text-neutral-400">
                    Create, edit, reorder, or delete AI portrait styles and prompt templates.
                  </p>
                </div>
                <button
                  onClick={openCreateThemeModal}
                  className="px-4 py-2 rounded-xl bg-gradient-to-r from-rose-500 to-purple-600 hover:from-rose-600 hover:to-purple-700 text-white font-semibold text-xs flex items-center justify-center gap-2 transition shadow-md shadow-rose-500/20 whitespace-nowrap self-start sm:self-auto"
                >
                  <Plus className="w-4 h-4" />
                  <span>Add New Prompt</span>
                </button>
              </div>

              {filteredThemes.length === 0 ? (
                <div className="text-center py-12 border border-dashed border-neutral-800 rounded-2xl space-y-3">
                  <Sparkles className="w-8 h-8 text-neutral-600 mx-auto" />
                  <p className="text-sm text-neutral-400 font-medium">
                    {themeSearchQuery ? "No themes match your search query." : "No themes found in database."}
                  </p>
                  <button
                    onClick={openCreateThemeModal}
                    className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-xs font-semibold text-neutral-200 transition"
                  >
                    + Create First Theme
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {filteredThemes.map((theme) => (
                    <div
                      key={theme.id}
                      className={`relative flex flex-col justify-between bg-neutral-950/70 border rounded-2xl p-4 transition-all duration-200 ${
                        theme.is_active
                          ? "border-neutral-800/90 hover:border-neutral-700 shadow-lg"
                          : "border-neutral-800/40 opacity-70"
                      }`}
                    >
                      {/* Top Bar: Preview & Title */}
                      <div className="space-y-3">
                        <div className="flex items-start gap-3">
                          {theme.preview_image_url ? (
                            <img
                              src={theme.preview_image_url}
                              alt={theme.title}
                              className="w-14 h-14 rounded-xl object-cover border border-neutral-800 shrink-0 bg-neutral-900"
                              onError={(e) => {
                                (e.target as HTMLElement).style.display = "none";
                              }}
                            />
                          ) : (
                            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-neutral-800 to-neutral-900 border border-neutral-800 flex items-center justify-center shrink-0 text-neutral-500">
                              <ImageIcon className="w-6 h-6" />
                            </div>
                          )}

                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-1">
                              <h4 className="text-sm font-bold text-neutral-100 truncate">
                                {theme.title}
                              </h4>
                              <span
                                onClick={() => handleToggleActiveTheme(theme)}
                                className={`cursor-pointer px-2 py-0.5 rounded-full text-[10px] font-bold shrink-0 transition ${
                                  theme.is_active
                                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/20"
                                    : "bg-neutral-800 text-neutral-500 border border-neutral-700 hover:bg-neutral-700"
                                }`}
                                title="Click to toggle active status"
                              >
                                {theme.is_active ? "ACTIVE" : "INACTIVE"}
                              </span>
                            </div>

                            <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                              <span className="text-[10px] font-medium bg-rose-500/10 text-rose-300 border border-rose-500/20 px-2 py-0.5 rounded-md">
                                {theme.category}
                              </span>
                              <span className="text-[10px] text-neutral-500 font-mono">
                                order: #{theme.order_index}
                              </span>
                            </div>

                            <p className="text-xs text-neutral-400 line-clamp-2 mt-1.5 leading-snug">
                              {theme.tagline || "No tagline provided."}
                            </p>
                          </div>
                        </div>

                        {/* Prompt Template Code Block */}
                        <div className="space-y-1">
                          <div className="flex items-center justify-between text-[10px] font-semibold text-neutral-400">
                            <span>Prompt Template</span>
                            <button
                              onClick={() => handleCopyPrompt(theme.id, theme.prompt_template)}
                              className="flex items-center gap-1 text-neutral-400 hover:text-white transition"
                              title="Copy prompt text"
                            >
                              {copiedPromptId === theme.id ? (
                                <>
                                  <Check className="w-3 h-3 text-emerald-400" />
                                  <span className="text-emerald-400">Copied</span>
                                </>
                              ) : (
                                <>
                                  <Copy className="w-3 h-3" />
                                  <span>Copy</span>
                                </>
                              )}
                            </button>
                          </div>
                          <div className="bg-neutral-900/90 border border-neutral-800/90 rounded-xl p-2.5 max-h-24 overflow-y-auto font-mono text-[11px] text-neutral-300 leading-relaxed">
                            {theme.prompt_template}
                          </div>
                        </div>

                        {/* Hashtags */}
                        {theme.hashtags && theme.hashtags.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {theme.hashtags.map((tag, idx) => (
                              <span
                                key={idx}
                                className="text-[10px] text-neutral-400 bg-neutral-900 border border-neutral-800/80 px-1.5 py-0.5 rounded"
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Footer Actions */}
                      <div className="flex items-center justify-between border-t border-neutral-900 pt-3 mt-3">
                        <span className="text-[10px] font-mono text-neutral-500 truncate max-w-[140px]">
                          {theme.id}
                        </span>

                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => openEditThemeModal(theme)}
                            className="px-2.5 py-1 rounded-lg bg-neutral-800/90 hover:bg-neutral-700 text-neutral-200 hover:text-white text-xs font-medium transition flex items-center gap-1"
                            title="Edit prompt & theme"
                          >
                            <Edit3 className="w-3 h-3" />
                            <span>Edit</span>
                          </button>

                          <button
                            onClick={() => handleDeleteTheme(theme.id, theme.title)}
                            disabled={isDeletingThemeId === theme.id}
                            className="p-1.5 rounded-lg bg-neutral-900 hover:bg-rose-950/60 text-neutral-400 hover:text-rose-400 border border-neutral-800 hover:border-rose-800/50 transition disabled:opacity-50"
                            title="Delete prompt"
                          >
                            {isDeletingThemeId === theme.id ? (
                              <RefreshCw className="w-3.5 h-3.5 animate-spin text-rose-400" />
                            ) : (
                              <Trash2 className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Tab 5: Daily Activity & Trends */}
          {activeTab === "activity" && (
            <div className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-neutral-800/80 pb-4">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-emerald-400" />
                    7-Day Activity & Growth Progression
                  </h3>
                  <p className="text-xs text-neutral-400 mt-0.5">
                    Daily breakdown of unique visitors, site sessions, and portrait generations.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-neutral-400 bg-neutral-950 px-2.5 py-1 rounded-lg border border-neutral-800">
                    UTC Timezone
                  </span>
                </div>
              </div>

              {!metricsData || metricsData.daily_trends.length === 0 ? (
                <div className="py-12 text-center text-neutral-500 text-xs">
                  No activity recorded in the past 7 days yet.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-neutral-300">
                    <thead className="bg-neutral-950/60 text-neutral-400 uppercase tracking-wider font-semibold border-b border-neutral-800">
                      <tr>
                        <th className="py-3 px-4">Date</th>
                        <th className="py-3 px-4 text-center">Live Unique Visitors</th>
                        <th className="py-3 px-4 text-center">Total Site Visits</th>
                        <th className="py-3 px-4 text-center">Images Generated</th>
                        <th className="py-3 px-4 text-right">Traffic Volume</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-800/60 font-medium">
                      {metricsData.daily_trends.map((item, idx) => {
                        const isToday = idx === metricsData.daily_trends.length - 1;
                        const maxVisits = Math.max(...metricsData.daily_trends.map((d) => d.visits), 1);
                        const widthPct = Math.min(100, Math.round((item.visits / maxVisits) * 100));

                        return (
                          <tr key={item.date} className={`hover:bg-neutral-800/30 transition ${isToday ? "bg-emerald-950/15" : ""}`}>
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-neutral-200">{item.date}</span>
                                {isToday && (
                                  <span className="text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 px-1.5 py-0.5 rounded font-bold">
                                    Today
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="py-3 px-4 text-center">
                              <span className="inline-flex items-center gap-1 font-bold text-emerald-300 bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-500/20">
                                <Users className="w-3 h-3" />
                                {item.unique_visitors}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-center">
                              <span className="inline-flex items-center gap-1 font-bold text-sky-300 bg-sky-500/10 px-2.5 py-0.5 rounded-full border border-sky-500/20">
                                <Eye className="w-3 h-3" />
                                {item.visits}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-center">
                              <span className="inline-flex items-center gap-1 font-bold text-amber-300 bg-amber-500/10 px-2.5 py-0.5 rounded-full border border-amber-500/20">
                                <Zap className="w-3 h-3" />
                                {item.generations}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-right">
                              <div className="w-24 sm:w-32 bg-neutral-950 rounded-full h-2 overflow-hidden border border-neutral-800 ml-auto">
                                <div
                                  className="bg-gradient-to-r from-emerald-500 to-sky-500 h-full rounded-full transition-all duration-500"
                                  style={{ width: `${Math.max(widthPct, item.visits > 0 ? 10 : 0)}%` }}
                                ></div>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

        </div>

        {/* Create / Edit Theme Modal */}
        {isThemeModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="relative w-full max-w-2xl bg-neutral-900 border border-neutral-800 rounded-3xl p-6 sm:p-8 shadow-2xl max-h-[90vh] overflow-y-auto space-y-6">
              
              {/* Modal Header */}
              <div className="flex items-center justify-between border-b border-neutral-800 pb-4">
                <div>
                  <h3 className="text-lg font-bold text-neutral-100 flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-rose-400" />
                    <span>{editingTheme ? "Edit Prompt Theme" : "Create New Prompt Theme"}</span>
                  </h3>
                  <p className="text-xs text-neutral-400 mt-0.5">
                    {editingTheme
                      ? `Updating preset: ${editingTheme.id}`
                      : "Add a new portrait style and prompt template to the platform."}
                  </p>
                </div>
                <button
                  onClick={() => setIsThemeModalOpen(false)}
                  className="p-2 rounded-xl text-neutral-400 hover:text-white hover:bg-neutral-800 transition"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Error Notice */}
              {themeModalError && (
                <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{themeModalError}</span>
                </div>
              )}

              {/* Form */}
              <form onSubmit={handleSaveTheme} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  
                  {/* Title */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-neutral-300">
                      Theme Title <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Perfect Headshot or Neon Cyberpunk"
                      value={themeFormData.title}
                      onChange={(e) => setThemeFormData({ ...themeFormData, title: e.target.value })}
                      className="w-full px-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 focus:border-rose-500 focus:ring-1 focus:ring-rose-500 text-sm text-neutral-100 outline-none transition"
                    />
                  </div>

                  {/* Category */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-neutral-300">
                      Category
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Professional, Vintage, Sci-Fi, Studio Polish"
                      value={themeFormData.category}
                      onChange={(e) => setThemeFormData({ ...themeFormData, category: e.target.value })}
                      className="w-full px-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 focus:border-neutral-700 text-sm text-neutral-100 outline-none transition"
                    />
                  </div>

                  {/* Unique ID / Slug (Only editable if creating) */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-neutral-300">
                      Theme ID / Slug {editingTheme ? "(Immutable)" : "(Optional slug)"}
                    </label>
                    <input
                      type="text"
                      disabled={!!editingTheme}
                      placeholder="e.g. trend-perfect-headshot (auto-generated if empty)"
                      value={themeFormData.id}
                      onChange={(e) => setThemeFormData({ ...themeFormData, id: e.target.value })}
                      className="w-full px-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 focus:border-neutral-700 text-sm text-neutral-100 font-mono disabled:opacity-50 outline-none transition"
                    />
                  </div>

                  {/* Order Index */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-neutral-300">
                      Display Order Index
                    </label>
                    <input
                      type="number"
                      value={themeFormData.order_index}
                      onChange={(e) =>
                        setThemeFormData({
                          ...themeFormData,
                          order_index: parseInt(e.target.value) || 0,
                        })
                      }
                      className="w-full px-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 focus:border-neutral-700 text-sm text-neutral-100 outline-none transition"
                    />
                  </div>
                </div>

                {/* Tagline */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-neutral-300">
                    Tagline (User-facing subtitle)
                  </label>
                  <input
                    type="text"
                    placeholder="Short catchy explanation of this style..."
                    value={themeFormData.tagline}
                    onChange={(e) => setThemeFormData({ ...themeFormData, tagline: e.target.value })}
                    className="w-full px-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 focus:border-neutral-700 text-sm text-neutral-100 outline-none transition"
                  />
                </div>

                {/* Prompt Template */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-neutral-300 flex items-center justify-between">
                    <span>
                      Prompt Template <span className="text-rose-400">*</span>
                    </span>
                    <span className="text-[10px] text-neutral-500 font-normal">
                      Full prompt passed to FLUX / Azure inference
                    </span>
                  </label>
                  <textarea
                    rows={4}
                    required
                    placeholder="e.g. ultra-sharp professional executive headshot portrait, crisp studio lighting, 85mm portrait lens..."
                    value={themeFormData.prompt_template}
                    onChange={(e) =>
                      setThemeFormData({ ...themeFormData, prompt_template: e.target.value })
                    }
                    className="w-full px-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 focus:border-rose-500 focus:ring-1 focus:ring-rose-500 text-xs text-neutral-100 font-mono outline-none transition resize-y"
                  />
                </div>

                {/* Preview Image URL */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-neutral-300">
                    Preview Image URL (HTTPS)
                  </label>
                  <input
                    type="url"
                    placeholder="https://images.unsplash.com/photo-..."
                    value={themeFormData.preview_image_url}
                    onChange={(e) =>
                      setThemeFormData({ ...themeFormData, preview_image_url: e.target.value })
                    }
                    className="w-full px-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 focus:border-neutral-700 text-sm text-neutral-100 outline-none transition"
                  />
                  {themeFormData.preview_image_url && (
                    <div className="mt-2 flex items-center gap-3 p-2 bg-neutral-950 rounded-xl border border-neutral-800">
                      <img
                        src={themeFormData.preview_image_url}
                        alt="Preview"
                        className="w-12 h-12 rounded-lg object-cover"
                        onError={(e) => {
                          (e.target as HTMLElement).style.display = "none";
                        }}
                      />
                      <span className="text-xs text-neutral-400 truncate">
                        Preview image verified
                      </span>
                    </div>
                  )}
                </div>

                {/* Hashtags */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-neutral-300">
                    Hashtags (Comma-separated)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. #ProfessionalHeadshot, #CreatorBot, #AIStudio"
                    value={themeFormData.hashtags}
                    onChange={(e) =>
                      setThemeFormData({ ...themeFormData, hashtags: e.target.value })
                    }
                    className="w-full px-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 focus:border-neutral-700 text-sm text-neutral-100 outline-none transition"
                  />
                </div>

                {/* Active Checkbox */}
                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="checkbox"
                    id="themeActiveToggle"
                    checked={themeFormData.is_active}
                    onChange={(e) =>
                      setThemeFormData({ ...themeFormData, is_active: e.target.checked })
                    }
                    className="w-4 h-4 rounded text-rose-500 bg-neutral-950 border-neutral-700 focus:ring-0 focus:ring-offset-0"
                  />
                  <label htmlFor="themeActiveToggle" className="text-xs font-medium text-neutral-300 cursor-pointer">
                    Active (Visible to users on home page)
                  </label>
                </div>

                {/* Submit Buttons */}
                <div className="flex items-center justify-end gap-3 pt-4 border-t border-neutral-800">
                  <button
                    type="button"
                    onClick={() => setIsThemeModalOpen(false)}
                    className="px-5 py-2.5 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-neutral-300 hover:text-white text-xs font-semibold transition"
                  >
                    Cancel
                  </button>

                  <button
                    type="submit"
                    disabled={isSubmittingTheme}
                    className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-rose-500 via-pink-500 to-purple-600 hover:from-rose-600 hover:via-pink-600 hover:to-purple-700 text-white font-semibold text-xs transition shadow-lg shadow-rose-500/25 disabled:opacity-50 flex items-center gap-2"
                  >
                    {isSubmittingTheme ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Saving...</span>
                      </>
                    ) : (
                      <>
                        <Check className="w-3.5 h-3.5" />
                        <span>{editingTheme ? "Update Prompt" : "Create Prompt"}</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

      </main>
    </div>
  );
}

