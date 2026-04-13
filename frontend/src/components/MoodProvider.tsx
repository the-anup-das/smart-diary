"use client"

import * as React from "react"
import { getMoodHex } from "@/lib/mood"

export function MoodProvider({ children }: { children: React.ReactNode }) {
  React.useEffect(() => {
    // Only run in browser
    if (typeof document === 'undefined') return;

    fetch("/api/entries/context")
      .then(res => res.json())
      .then(data => {
        if (data.latest_mood !== undefined) {
          const hex = getMoodHex(data.latest_mood);
          document.documentElement.style.setProperty('--primary', hex);
        }
      })
      .catch(console.error);
  }, []);

  return <>{children}</>;
}
