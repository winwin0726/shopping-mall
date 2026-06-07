import type { NextConfig } from "next";
import withPWAInit from "next-pwa";

const withPWA = withPWAInit({
  dest: "public",
  disable: true, // 터널 테스트 중 서비스워커 캐싱 방지 (정식 배포 시 환경에 맞게 조정)
});

const nextConfig: NextConfig = {
  turbopack: {},
  images: {
    unoptimized: true, // 터널/외부호스트 이미지를 그대로 서빙 (호스트 제한 우회)
    remotePatterns: [
      { protocol: 'https', hostname: 'images.unsplash.com' },
      { protocol: 'https', hostname: 'cdn.pixabay.com' },
      { protocol: 'http', hostname: 'localhost', port: '8002' },
      { protocol: 'http', hostname: '127.0.0.1', port: '8002' },
      { protocol: 'https', hostname: 'cdn-icons-png.flaticon.com' },
    ],
  },
  // 프론트가 받은 /api, /uploads 요청을 백엔드(8002)로 내부 전달 → 브라우저 입장에선 같은 출처
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://127.0.0.1:8002/api/:path*' },
      { source: '/uploads/:path*', destination: 'http://127.0.0.1:8002/uploads/:path*' },
    ];
  },
  async redirects() {
    return [
      { source: '/signup', destination: '/register', permanent: true },
    ];
  },
};

export default withPWA(nextConfig);
