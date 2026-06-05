"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2, CheckCircle2, Eye, EyeOff } from "lucide-react";

import { useTheme } from "@/components/ThemeProvider";

export default function RegisterPage() {
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    passwordConfirm: "",
    name: "",
    phone: "",
  });
  const [errors, setErrors] = useState("");
  const [success, setSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showPasswordConfirm, setShowPasswordConfirm] = useState(false);
  const router = useRouter();
  const { themeConfig, tenantName } = useTheme();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors("");

    if (formData.password !== formData.passwordConfirm) {
      setErrors("비밀번호가 일치하지 않습니다.");
      return;
    }

    if (formData.password.length < 8) {
      setErrors("비밀번호는 최소 8자 이상이어야 합니다.");
      return;
    }

    setIsSubmitting(true);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
      const res = await fetch(`${apiUrl}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: formData.email,
          password: formData.password,
          name: formData.name,
          phone: formData.phone,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "회원가입에 실패했습니다. (이메일 중복?)");
      }

      setSuccess(true);
      setTimeout(() => {
        router.push("/login");
      }, 2000);
    } catch (err: any) {
      setErrors(err.message || "회원가입 중 오류가 발생했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900" style={{ backgroundColor: themeConfig.backgroundColor }}>
        <div className="text-center">
          <CheckCircle2 size={64} className="text-green-500 mx-auto mb-6" />
          <h2 className="text-3xl font-extrabold text-slate-900 dark:text-white mb-2 tracking-tight font-sans">Welcome!</h2>
          <p className="text-slate-500 mb-8 font-medium">회원가입이 완료되었습니다. 로그인 페이지로 이동합니다.</p>
          <Loader2 className="animate-spin text-slate-400 mx-auto" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-slate-900" style={{ backgroundColor: themeConfig.backgroundColor }}>
      <div className="w-full flex items-center justify-center py-16 px-4">
        <Link href="/login" className="absolute top-8 left-8 text-slate-400 hover:text-black dark:hover:text-white flex items-center space-x-2 text-sm font-bold transition-colors">
          <ArrowLeft size={24} />
        </Link>

        <div className="w-full max-w-md">
          <div className="text-center mb-10 mt-6">
            <h2 className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">Create Account</h2>
            <p className="text-sm text-slate-500 mt-2 font-medium">{tenantName}에 가입하고 프리미엄 스타일을 경험하세요.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-widest mb-1.5">
                Email Address *
              </label>
              <input
                type="email"
                name="email"
                required
                value={formData.email}
                onChange={handleChange}
                className="w-full px-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-black dark:focus:ring-white focus:outline-none transition-all dark:text-white"
                placeholder="ex) luxcate@example.com"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-widest mb-1.5">
                  Password *
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    name="password"
                    required
                    value={formData.password}
                    onChange={handleChange}
                    className="w-full px-4 py-3 pr-12 bg-slate-50 dark:bg-slate-900 border rounded-lg focus:ring-2 focus:outline-none transition-all dark:text-white border-slate-200 dark:border-slate-700 focus:ring-black dark:focus:ring-white"
                    placeholder="8자 이상"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-widest mb-1.5">
                  Confirm Password *
                </label>
                <div className="relative">
                  <input
                    type={showPasswordConfirm ? "text" : "password"}
                    name="passwordConfirm"
                    required
                    value={formData.passwordConfirm}
                    onChange={handleChange}
                    className={`w-full px-4 py-3 bg-slate-50 dark:bg-slate-900 border rounded-lg focus:ring-2 focus:outline-none transition-all dark:text-white
                      ${formData.passwordConfirm.length > 0 && formData.password !== formData.passwordConfirm ? 'border-red-400 focus:ring-red-400' : 'border-slate-200 dark:border-slate-700 focus:ring-black dark:focus:ring-white'}`}
                    placeholder="비밀번호 확인"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPasswordConfirm(!showPasswordConfirm)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                  >
                    {showPasswordConfirm ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                {formData.passwordConfirm.length > 0 && formData.password !== formData.passwordConfirm && (
                  <p className="text-[10px] text-red-500 mt-1">비밀번호가 일치하지 않습니다.</p>
                )}
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-widest mb-1.5">
                Full Name *
              </label>
              <input
                type="text"
                name="name"
                required
                value={formData.name}
                onChange={handleChange}
                className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-black dark:focus:ring-white focus:outline-none transition-all dark:text-white"
                placeholder="이름을 입력해주세요"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-widest mb-1.5">
                Phone Number (Optional)
              </label>
              <input
                type="tel"
                name="phone"
                value={formData.phone}
                onChange={handleChange}
                className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-black dark:focus:ring-white focus:outline-none transition-all dark:text-white"
                placeholder="010-1234-5678"
              />
            </div>

            {errors && (
              <div className="text-red-500 text-sm font-bold bg-red-50 dark:bg-red-900/30 p-3 rounded-lg border border-red-200 dark:border-red-800 text-center">
                {errors}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full mt-6 text-white font-bold py-4 rounded-lg uppercase tracking-widest text-sm hover:opacity-90 transition-all flex justify-center items-center shadow-lg shadow-black/10"
              style={{
                backgroundColor: themeConfig.primaryColor || "#000000",
                borderRadius: themeConfig.borderRadius === "none" ? "0px" : themeConfig.borderRadius === "sm" ? "4px" : themeConfig.borderRadius === "md" ? "8px" : themeConfig.borderRadius === "lg" ? "16px" : "9999px"
              }}
            >
              {isSubmitting ? <Loader2 className="animate-spin" size={20} /> : "Sign Up"}
            </button>
            <p className="text-center text-xs text-slate-400 mt-4 leading-relaxed font-medium">
              가입 시 {tenantName}의 서비스 이용약관 및 개인정보처리방침에 동의하는 것으로 간주됩니다.
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}