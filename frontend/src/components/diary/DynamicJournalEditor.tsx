"use client"
import dynamic from "next/dynamic"

export const JournalEditor = dynamic(
  () => import("./JournalEditor").then((mod) => mod.JournalEditor),
  { ssr: false }
)
