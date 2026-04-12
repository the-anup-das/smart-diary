/**
 * Mood & Sentiment display utilities.
 * Maps raw AI scores/labels into human-friendly, colorful representations.
 */

export type MoodTier = {
  label: string
  color: string        // tailwind text color
  bg: string           // tailwind bg for pills
  border: string       // tailwind border color
  hex: string          // raw hex for SVG
}

export function getMoodTier(score: number): MoodTier {
  if (score <= 2) return { label: "Struggling", color: "text-red-500", bg: "bg-red-500/10", border: "border-red-500/20", hex: "#ef4444" }
  if (score <= 4) return { label: "Low Energy", color: "text-orange-500", bg: "bg-orange-500/10", border: "border-orange-500/20", hex: "#f97316" }
  if (score <= 6) return { label: "Balanced", color: "text-amber-500", bg: "bg-amber-500/10", border: "border-amber-500/20", hex: "#f59e0b" }
  if (score <= 8) return { label: "Good", color: "text-emerald-500", bg: "bg-emerald-500/10", border: "border-emerald-500/20", hex: "#10b981" }
  return { label: "Thriving", color: "text-violet-500", bg: "bg-violet-500/10", border: "border-violet-500/20", hex: "#8b5cf6" }
}

export function getMoodHex(score: number): string {
  // Continuous gradient: red(1) → orange(3) → amber(5) → green(7) → violet(10)
  if (score <= 3) {
    const t = (score - 1) / 2
    return lerpColor("#ef4444", "#f97316", t)
  }
  if (score <= 5) {
    const t = (score - 3) / 2
    return lerpColor("#f97316", "#f59e0b", t)
  }
  if (score <= 7) {
    const t = (score - 5) / 2
    return lerpColor("#f59e0b", "#10b981", t)
  }
  const t = (score - 7) / 3
  return lerpColor("#10b981", "#8b5cf6", t)
}

function lerpColor(a: string, b: string, t: number): string {
  const parse = (hex: string) => [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)]
  const [r1, g1, b1] = parse(a)
  const [r2, g2, b2] = parse(b)
  const r = Math.round(r1 + (r2 - r1) * t)
  const g = Math.round(g1 + (g2 - g1) * t)
  const bl = Math.round(b1 + (b2 - b1) * t)
  return `rgb(${r},${g},${bl})`
}

export const SENTIMENT_STYLES: Record<string, { color: string; bg: string; glow: string }> = {
  Joyful:   { color: "text-emerald-400", bg: "bg-emerald-500/10", glow: "shadow-[0_0_12px_rgba(16,185,129,0.3)]" },
  Calm:     { color: "text-blue-400",    bg: "bg-blue-500/10",    glow: "shadow-[0_0_12px_rgba(59,130,246,0.3)]" },
  Focused:  { color: "text-violet-400",  bg: "bg-violet-500/10",  glow: "shadow-[0_0_12px_rgba(139,92,246,0.3)]" },
  Neutral:  { color: "text-gray-400",    bg: "bg-gray-500/10",    glow: "shadow-[0_0_12px_rgba(156,163,175,0.2)]" },
  Anxious:  { color: "text-amber-400",   bg: "bg-amber-500/10",   glow: "shadow-[0_0_12px_rgba(245,158,11,0.3)]" },
  Stressed: { color: "text-orange-400",  bg: "bg-orange-500/10",  glow: "shadow-[0_0_12px_rgba(249,115,22,0.3)]" },
  Sad:      { color: "text-indigo-400",  bg: "bg-indigo-500/10",  glow: "shadow-[0_0_12px_rgba(99,102,241,0.3)]" },
  Excited:  { color: "text-pink-400",    bg: "bg-pink-500/10",    glow: "shadow-[0_0_12px_rgba(236,72,153,0.3)]" },
}

export function getSentimentStyle(sentiment: string) {
  return SENTIMENT_STYLES[sentiment] || { color: "text-primary", bg: "bg-primary/10", glow: "shadow-[0_0_12px_rgba(139,92,246,0.2)]" }
}
