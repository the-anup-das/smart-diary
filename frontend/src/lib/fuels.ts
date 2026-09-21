/**
 * Four Fuels: what a week of entries says about the four drives behind mood and motivation
 * (dopamine, oxytocin, serotonin, endorphins). The backend counts what the entries mention,
 * day by day; this file is the client for it. See backend/fuels.py for the mapping.
 */
import { localToday, tzOffset } from "@/lib/focus"

export type FuelKey = "drive" | "bond" | "calm" | "spark"
export type FuelLevel = "none" | "quiet" | "low" | "steady" | "strong"

export interface FuelDay {
  date: string
  analysed: boolean
  fed: boolean
  drained: boolean
}

export interface FuelReason {
  text: string
  days: number
}

export interface FuelChallenge {
  id: string
  text: string
  why: string
  builder: string | null
  doneToday: boolean
}

export interface Fuel {
  key: FuelKey
  label: string
  chemical: string
  tagline: string
  fedBy: string
  drainedBy: string
  score: number | null
  previous: number | null
  level: FuelLevel
  fedDays: number
  drainedDays: number
  days: FuelDay[]
  fedByReasons: FuelReason[]
  drainedByReasons: FuelReason[]
  because: string
  challenge: FuelChallenge
}

export interface FuelsData {
  window: { days: number; entries: number; previousEntries: number; today: string }
  fuels: Fuel[]
  headline: string
  note: string
}

export const FUEL_STYLES: Record<FuelKey, { bar: string; text: string; ring: string }> = {
  drive: { bar: "bg-violet-500", text: "text-violet-500", ring: "ring-violet-500/30" },
  bond: { bar: "bg-rose-500", text: "text-rose-500", ring: "ring-rose-500/30" },
  calm: { bar: "bg-sky-500", text: "text-sky-500", ring: "ring-sky-500/30" },
  spark: { bar: "bg-amber-500", text: "text-amber-500", ring: "ring-amber-500/30" },
}

export const LEVEL_LABELS: Record<FuelLevel, string> = {
  none: "no entries yet",
  quiet: "no signal yet",
  low: "running low",
  steady: "steady",
  strong: "strong",
}

export async function fetchFuels(): Promise<FuelsData | null> {
  try {
    const res = await fetch(`/api/insights/fuels?tz_offset=${tzOffset()}`)
    if (!res.ok) return null
    return (await res.json()) as FuelsData
  } catch {
    return null
  }
}

export async function toggleChallenge(id: string, done: boolean): Promise<boolean> {
  try {
    const res = await fetch(`/api/insights/fuels/challenge?tz_offset=${tzOffset()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, date: localToday(), done }),
    })
    return res.ok
  } catch {
    return false
  }
}
