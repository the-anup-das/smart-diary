import type { NextConfig } from "next";
import withPWAInit from "@ducanh2912/next-pwa";

const withPWA = withPWAInit({
  dest: "public",
  disable: 
    process.env.PWA_DISABLED === "true" || 
    (process.env.NODE_ENV === "development" && process.env.LOCAL_FORCE_PWA_ENABLE !== "true"),
  register: true,
  cacheOnFrontEndNav: true,
});

const nextConfig: NextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        // Route any /api/ API call silently directly to the local Python FastAPI container running behind the scenes.
        destination: `${process.env.INTERNAL_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/api/:path*` 
      }
    ]
  }
};

export default withPWA(nextConfig);
