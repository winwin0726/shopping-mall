"use client";

import { useState, useEffect } from "react";
import { API_URL } from "@/lib/api";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { ArrowLeft, Loader2, Eye, EyeOff } from "lucide-react";

import { useTheme } from "@/components/ThemeProvider";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [errors, setErrors] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const router = useRouter();
  const { login } = useAuth();
  const { themeConfig, tenantName } = useTheme();

  // 마운트 시 로컬스토리지에 저장된 로그인 정보 불러오기
  useEffect(() => {
    const savedEmail = localStorage.getItem("rememberedEmail");
    const savedPassword = localStorage.getItem("rememberedPassword");
    const savedRememberMe = localStorage.getItem("rememberMe") === "true";

    if (savedRememberMe && savedEmail) {
      setEmail(savedEmail);
      if (savedPassword) {
        setPassword(savedPassword);
      }
      setRememberMe(true);
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors("");
    setIsSubmitting(true);

    try {
      const formData = new URLSearchParams();
      formData.append("username", email);
      formData.append("password", password);

      const apiUrl = API_URL;
      const res = await fetch(`${apiUrl}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData,
      });

      if (!res.ok) {
        throw new Error("이메일 또는 비밀번호가 올바르지 않습니다.");
      }

      const data = await res.json();
      
      // 자동 로그인 상태 저장 여부에 따라 처리
      if (rememberMe) {
        localStorage.setItem("rememberedEmail", email);
        localStorage.setItem("rememberedPassword", password);
        localStorage.setItem("rememberMe", "true");
      } else {
        localStorage.removeItem("rememberedEmail");
        localStorage.removeItem("rememberedPassword");
        localStorage.removeItem("rememberMe");
      }

      login(data.access_token, data.user);
      router.push("/");
    } catch (err: any) {
      setErrors(err.message || "로그인 중 오류가 발생했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-slate-900" style={{ backgroundColor: themeConfig.backgroundColor }}>
      <div className="w-full flex items-center justify-center py-16 px-4">
        <Link href="/" className="absolute top-8 left-8 text-slate-400 hover:text-black dark:hover:text-white flex items-center space-x-2 text-sm font-bold transition-colors">
          <ArrowLeft size={16} /> <span>돌아가기</span>
        </Link>

        <div className="w-full max-w-md">
          <div className="text-center mb-10 mt-6">
            <h2 className="text-3xl font-extrabold text-slate-900 dark:text-white mb-2 tracking-tight">Login</h2>
            <p className="text-slate-500 dark:text-slate-400 mb-8 font-medium">
              {tenantName} 계정에 로그인하세요.
            </p>

            <form onSubmit={handleSubmit} className="space-y-6 text-left">
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-widest mb-2">
                  Email Address
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-4 py-3 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-black dark:focus:ring-white focus:outline-none transition-all dark:text-white"
                  placeholder="ex) luxcate@example.com"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-widest mb-2">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-4 py-3 pr-12 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-black dark:focus:ring-white focus:outline-none transition-all dark:text-white"
                    placeholder="********"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
                  >
                    {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between text-sm font-medium">
                <label className="flex items-center space-x-2 text-slate-700 dark:text-slate-300 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="w-4 h-4 rounded border-slate-300 dark:border-slate-700 text-black dark:text-white focus:ring-black cursor-pointer dark:bg-slate-800"
                  />
                  <span>자동 로그인 (기억하기)</span>
                </label>
                <Link href="#" className="text-slate-400 hover:text-black dark:hover:text-white transition-colors">
                  비밀번호 찾기
                </Link>
              </div>

              {errors && (
                <div className="text-red-500 text-sm font-bold bg-red-50 dark:bg-red-900/30 p-3 rounded-lg border border-red-200 dark:border-red-800">
                  {errors}
                </div>
              )}

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full text-white font-bold py-4 rounded-lg uppercase tracking-widest text-sm hover:opacity-90 transition-all flex justify-center items-center shadow-lg shadow-black/10"
                style={{ 
                  backgroundColor: themeConfig.primaryColor || "#000000",
                  borderRadius: themeConfig.borderRadius === "none" ? "0px" : themeConfig.borderRadius === "sm" ? "4px" : themeConfig.borderRadius === "md" ? "8px" : themeConfig.borderRadius === "lg" ? "16px" : "9999px"
                }}
              >
                {isSubmitting ? <Loader2 className="animate-spin" size={20} /> : "Sign In"}
              </button>
            </form>

            <p className="mt-8 text-center text-sm font-medium text-slate-500">
              아직 계정이 없으신가요?{" "}
              <Link href="/register" className="text-black dark:text-white font-bold hover:underline">
                회원가입
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}