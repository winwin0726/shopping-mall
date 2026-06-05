import NextAuth from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"

const handler = NextAuth({
  providers: [
    CredentialsProvider({
      name: "Demo Account",
      credentials: {
        username: { label: "Username / Email", type: "text", placeholder: "demo@example.com" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials) {
        // 실제 백엔드(FastAPI) 자격 검증으로 위임 — 데모용 무조건 통과 로직 제거
        if (!credentials?.username || !credentials?.password) return null;
        try {
          const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";
          const body = new URLSearchParams();
          body.append("username", credentials.username);
          body.append("password", credentials.password);
          const res = await fetch(`${apiUrl}/api/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body,
          });
          if (!res.ok) return null;
          const data = await res.json();
          if (!data?.access_token) return null;
          return {
            id: String(data.user?.email ?? credentials.username),
            name: data.user?.name ?? credentials.username,
            email: data.user?.email ?? credentials.username,
          };
        } catch {
          return null;
        }
      }
    })
  ],
  session: {
    strategy: "jwt",
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },
  secret: process.env.NEXTAUTH_SECRET,
  callbacks: {
    async jwt({ token, user }) {
        if (user) { token.id = user.id; }
        return token;
    },
    async session({ session, token }) {
        if (session.user) { (session.user as any).id = token.id; }
        return session;
    }
  },
  pages: {
    signIn: '/api/auth/signin',
  }
});

export { handler as GET, handler as POST }
