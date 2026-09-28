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
} from "lucide-react";
import { useAuth, User } from "@/context/AuthContext";

interface AdminUserItem {
  id: string;
  email: string;
  name: string;
  avatar_url?: string;
  role: string;
  credits: number;
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

export default function AdminPage() {
  const router = useRouter();
  const { user, token, isLoading: authLoading, logout } = useAuth();

  // Admin Data states
  const [usersList, setUsersList] = useState<AdminUserItem[]>([]);
  const [pendingList, setPendingList] = useState<PendingCreditItem[]>([]);
  const [transactionsList, setTransactionsList] = useState<TransactionItem[]>([]);
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
  const [activeTab, setActiveTab] = useState<"users" | "pending" | "transactions">("users");
  const [searchQuery, setSearchQuery] = useState<string>("");

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
      const [usersRes, pendingRes, txRes] = await Promise.all([
        fetch(`${apiUrl}/api/admin/users`, { headers }),
        fetch(`${apiUrl}/api/admin/pending-credits`, { headers }),
        fetch(`${apiUrl}/api/admin/transactions`, { headers }),
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
    } catch (err) {
      console.error("Error loading admin data:", err);
    } finally {
      setIsLoadingData(false);
    }
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
        <p className="text-sm text-neutral-400">This portal is reserved for instaXoom administrators.</p>
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
        
        {/* KPI Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-2xl p-5 backdrop-blur-xl">
            <div className="flex items-center justify-between text-neutral-400 text-xs font-medium mb-2">
              <span>Registered Users</span>
              <Users className="w-4 h-4 text-rose-400" />
            </div>
            <div className="text-3xl font-extrabold text-white">{usersList.length}</div>
            <p className="text-[11px] text-neutral-500 mt-1">Google OAuth registered accounts</p>
          </div>

          <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-2xl p-5 backdrop-blur-xl">
            <div className="flex items-center justify-between text-neutral-400 text-xs font-medium mb-2">
              <span>Circulating Credits</span>
              <Coins className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-3xl font-extrabold text-white">{totalCreditsCirculating}</div>
            <p className="text-[11px] text-neutral-500 mt-1">Live balances across all active users</p>
          </div>

          <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-2xl p-5 backdrop-blur-xl">
            <div className="flex items-center justify-between text-neutral-400 text-xs font-medium mb-2">
              <span>Pending Grants</span>
              <Clock className="w-4 h-4 text-purple-400" />
            </div>
            <div className="text-3xl font-extrabold text-white">{pendingList.length}</div>
            <p className="text-[11px] text-neutral-500 mt-1">{totalPendingCredits} credits reserved for new signups</p>
          </div>

          <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-2xl p-5 backdrop-blur-xl">
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

          {actionNotice && (
            <div
              className={`p-4 rounded-2xl mb-6 text-sm flex items-start gap-3 border ${
                actionNotice.type === "success"
                  ? "bg-emerald-950/40 border-emerald-500/30 text-emerald-300"
                  : "bg-rose-950/40 border-rose-500/30 text-rose-300"
              }`}
            >
              {actionNotice.type === "success" ? (
                <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-400 mt-0.5" />
              ) : (
                <AlertCircle className="w-5 h-5 shrink-0 text-rose-400 mt-0.5" />
              )}
              <div>{actionNotice.message}</div>
            </div>
          )}

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
            <div className="flex items-center gap-2">
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
                    <th className="py-3 px-4">Created Date</th>
                    <th className="py-3 px-4">Last Login</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/60 font-medium">
                  {filteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-neutral-500">
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

        </div>

      </main>
    </div>
  );
}
