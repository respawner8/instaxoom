"use client";

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";
import { GoogleOAuthProvider } from "@react-oauth/google";

export interface User {
  id: string;
  email: string;
  name?: string;
  avatar_url?: string;
  role: "user" | "admin";
  credits: number;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  loginWithGoogle: (credential: string) => Promise<User>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  updateCredits: (credits: number) => void;
  isConfigured: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const googleClientId =
    process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ||
    "demo-instaxoom-oauth-id.apps.googleusercontent.com";
  const isConfigured = Boolean(
    process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID &&
      process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID !==
        "demo-instaxoom-oauth-id.apps.googleusercontent.com"
  );

  const refreshUser = async () => {
    if (typeof window === "undefined") return;
    const savedToken = localStorage.getItem("instaxoom_jwt");
    if (!savedToken) {
      setUser(null);
      setToken(null);
      setIsLoading(false);
      return;
    }

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/auth/me`, {
        headers: {
          Authorization: `Bearer ${savedToken}`,
        },
      });

      if (res.ok) {
        const userData: User = await res.json();
        setUser(userData);
        setToken(savedToken);
      } else {
        localStorage.removeItem("instaxoom_jwt");
        setUser(null);
        setToken(null);
      }
    } catch (err) {
      console.warn("Could not verify session with backend:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
  }, []);

  const loginWithGoogle = async (credential: string): Promise<User> => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const res = await fetch(`${apiUrl}/api/auth/google`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ credential }),
    });

    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Google authentication failed" }));
      throw new Error(err.detail || "Authentication failed");
    }

    const data = await res.json();
    const accessToken = data.access_token;
    const userData: User = data.user;

    localStorage.setItem("instaxoom_jwt", accessToken);
    setToken(accessToken);
    setUser(userData);

    return userData;
  };

  const logout = () => {
    localStorage.removeItem("instaxoom_jwt");
    setUser(null);
    setToken(null);
  };

  const updateCredits = (credits: number) => {
    setUser((prev) => (prev ? { ...prev, credits } : prev));
  };

  return (
    <GoogleOAuthProvider clientId={googleClientId}>
      <AuthContext.Provider
        value={{
          user,
          token,
          isLoading,
          loginWithGoogle,
          logout,
          refreshUser,
          updateCredits,
          isConfigured,
        }}
      >
        {children}
      </AuthContext.Provider>
    </GoogleOAuthProvider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
