// 백엔드 API 호출 공용 유틸 (단일 소스)
// - API_URL: 환경변수 우선, 폴백은 실제 백엔드 포트(8002)로 통일
// - authFetch: localStorage의 JWT를 Authorization 헤더로 자동 주입

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

/**
 * 인증 토큰을 자동 첨부하는 fetch 래퍼.
 * 기존 헤더(Content-Type 등)는 보존하며, 이미 Authorization이 지정된 경우 덮어쓰지 않는다.
 * FormData 업로드 시에도 Content-Type을 건드리지 않아 안전하다.
 */
export function authFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers = new Headers(init.headers || {});
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(input, { ...init, headers });
}
