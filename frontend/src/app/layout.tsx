
import { Inter, Merriweather } from "next/font/google";
import { ThemeProvider } from "@/components/ThemeProvider";
import { MoodProvider } from "@/components/MoodProvider";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const merriweather = Merriweather({
  variable: "--font-merriweather",
  weight: ["300", "400", "700"],
  subsets: ["latin"],
});

import type { Metadata, Viewport } from "next";

export const viewport: Viewport = {
  themeColor: "#8b5cf6",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export const metadata: Metadata = {
  title: "AI Diary Platform",
  description: "A digital diary with AI insights and cognitive tracking",
  appleWebApp: {
    capable: true,
    title: "Smart Diary",
    statusBarStyle: "default",
    startupImage: [
      '/icon-512x512.png',
    ],
  },
  icons: {
    icon: '/icon-192x192.png',
    apple: '/icon-192x192.png',
  },
  formatDetection: {
    telephone: false,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${inter.variable} ${merriweather.variable} h-full antialiased`}
    >
      <body 
        suppressHydrationWarning 
        className="min-h-full flex flex-col bg-background text-foreground transition-colors duration-300"
      >
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <MoodProvider>
            {children}
          </MoodProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
