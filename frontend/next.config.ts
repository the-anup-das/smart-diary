import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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

export default nextConfig;
