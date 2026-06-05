"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { API_URL, authFetch } from "@/lib/api";

export interface User {
  email: string;
  name: string;
  role: string;
  profile_image?: string;
  grade: number;
  reward_points: number;
  coupon_count: number;
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    // Check local storage for token on mount
    const checkAuth = async () => {
      const token = localStorage.getItem("token");
      if (token) {
        try {
          // 방문 적립(best-effort) 후 최신 사용자 정보 조회 (authFetch 가 토큰 자동 첨부)
          try { await authFetch(`${API_URL}/api/auth/me/visit-reward`, { method: "POST" }); } catch {}
          const res = await authFetch(`${API_URL}/api/auth/me`);
          if (res.ok) {
            const data = await res.json();
            setUser({ 
              email: data.email, 
              name: data.name, 
              role: data.role, 
              profile_image: data.profile_image,
              grade: data.grade !== undefined ? data.grade : 4,
              reward_points: data.reward_points !== undefined ? data.reward_points : 0,
              coupon_count: data.coupon_count !== undefined ? data.coupon_count : 0
            });
          } else {
            // Token expired or invalid
            localStorage.removeItem("token");
            setUser(null);
          }
        } catch (error) {
          console.error("Auth check failed (Backend offline)", error);
          setUser(null);
        }
      }
      setLoading(false);
    };
    checkAuth();
  }, []);

  const login = (token: string, userData: User) => {
    localStorage.setItem("token", token);
    setUser(userData);
    router.push("/");
  };

  const logout = () => {
    localStorage.removeItem("token");
    setUser(null);
    router.push("/");
  };

  return { user, loading, login, logout };
}
