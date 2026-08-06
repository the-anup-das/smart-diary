import type { NextConfig } from "next";
import withPWAInit from "@ducanh2912/next-pwa";

const withPWA = withPWAInit({
  dest: "public",
  disable:
    process.env.PWA_DISABLED === "true" ||
    (process.env.NODE_ENV === "development" && process.env.LOCAL_FORCE_PWA_ENABLE !== "true"),
  register: true,
  cacheOnFrontEndNav: true,
  fallbacks: {
    document: "/~offline",
  },
  workboxOptions: {
    // New service workers wait until the user accepts the update prompt
    // (UpdatePrompt.tsx) instead of silently serving a mixed old/new app.
    skipWaiting: false,
    clientsClaim: true,
    runtimeCaching: [
      {
        // Read-only API data: serve fresh when online, fall back to the last
        // good response when the backend is unreachable (offline journaling).
        urlPattern: ({ url, request }: { url: URL; request: Request }) =>
          url.pathname.startsWith("/api/") && request.method === "GET",
        handler: "NetworkFirst",
        options: {
          cacheName: "api-cache",
          networkTimeoutSeconds: 4,
          expiration: { maxEntries: 64, maxAgeSeconds: 24 * 60 * 60 },
          cacheableResponse: { statuses: [200] },
        },
      },
      {
        urlPattern: ({ request }: { request: Request }) =>
          request.destination === "image" || request.destination === "font",
        handler: "StaleWhileRevalidate",
        options: {
          cacheName: "asset-cache",
          expiration: { maxEntries: 128, maxAgeSeconds: 30 * 24 * 60 * 60 },
        },
      },
    ],
  },
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
