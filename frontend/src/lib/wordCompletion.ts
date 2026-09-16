/**
 * Word completion for the editor: local, private, instant.
 *
 * Candidates come from three places, ranked in this order:
 *   1. words the writer has used in past entries (from /api/entries/vocabulary), by frequency
 *   2. words already typed in the current entry
 *   3. a small list of common longer English words, as a floor for new writers
 * Nothing leaves the browser while suggesting; the vocabulary is fetched once and cached.
 */

export interface VocabWord {
  w: string
  n: number
}

const CACHE_KEY = "vocab_cache_v1"
const CACHE_TTL_MS = 12 * 60 * 60 * 1000
const MIN_WORD = 4
const MIN_REMAINDER = 2

/** Common longer words that a new writer would want completed before their own vocabulary exists. */
export const COMMON_WORDS: string[] = (
  "about above absolutely across actually afternoon afterwards again against almost already although always " +
  "another anxious anything anyway around because become before behind being believe better between beyond " +
  "birthday breakfast brother called cannot certain certainly change coming completely conversation could " +
  "daughter decided decision deserve different difficult dinner during early either energy enough especially " +
  "evening every everyone everything exactly excited exercise expected family feeling finally finished first " +
  "forward friend friends frustrated getting going grateful great happened happy having honestly hopefully " +
  "however husband important instead interesting journal little manager maybe meeting minutes moment money " +
  "morning mother myself nervous nothing noticed office others outside overthinking parents people perhaps " +
  "person planning probably problem project promise question quickly rather really realised realized relaxed " +
  "remember right school several should sister sleep something sometimes started still stopped stressed " +
  "suddenly support sure surprised their there these thing think thinking though thought through together " +
  "today tomorrow tonight trying under understand until usually wanted weekend whatever whether while without " +
  "wonder wondering working worried worrying would write writing yesterday yourself"
).split(" ")

interface Candidate {
  word: string
  score: number
}

export class CompletionIndex {
  private buckets = new Map<string, Candidate[]>()
  private known = new Set<string>()

  constructor(vocab: VocabWord[] = [], common: string[] = COMMON_WORDS) {
    for (const { w, n } of vocab) this.insert(w, 10 + n * 10)
    for (const w of common) this.insert(w, 1)
    this.sortAll()
  }

  /** Words typed in the current entry join the index so a word used once completes the second time. */
  learn(text: string) {
    let changed = false
    for (const raw of text.match(/[A-Za-z][A-Za-z']{3,}/g) || []) {
      const w = raw.toLowerCase().replace(/'+$/, "")
      if (w.length >= MIN_WORD && !this.known.has(w)) {
        this.insert(w, 5)
        changed = true
      }
    }
    if (changed) this.sortAll()
  }

  /** The best full word for a typed prefix, or null when nothing worth suggesting. */
  complete(prefix: string): string | null {
    const p = prefix.toLowerCase()
    if (p.length < 3) return null
    const bucket = this.buckets.get(p.slice(0, 3))
    if (!bucket) return null
    for (const c of bucket) {
      if (c.word.startsWith(p) && c.word.length - p.length >= MIN_REMAINDER) return c.word
    }
    return null
  }

  private insert(word: string, score: number) {
    if (word.length < MIN_WORD || !/^[a-z][a-z']*$/.test(word)) return
    this.known.add(word)
    const key = word.slice(0, 3)
    const bucket = this.buckets.get(key) || []
    const existing = bucket.find(c => c.word === word)
    if (existing) existing.score = Math.max(existing.score, score)
    else bucket.push({ word, score })
    this.buckets.set(key, bucket)
  }

  private sortAll() {
    for (const bucket of this.buckets.values()) {
      bucket.sort((a, b) => b.score - a.score || a.word.length - b.word.length || a.word.localeCompare(b.word))
    }
  }
}

/** Fetch the writer's vocabulary, using a half-day localStorage cache so the editor opens instantly. */
export async function loadVocabulary(): Promise<CompletionIndex> {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    if (raw) {
      const cached = JSON.parse(raw)
      if (Date.now() - cached.ts < CACHE_TTL_MS && Array.isArray(cached.words)) return new CompletionIndex(cached.words)
    }
  } catch {}
  try {
    const res = await fetch("/api/entries/vocabulary")
    if (res.ok) {
      const data = await res.json()
      const words: VocabWord[] = Array.isArray(data.words) ? data.words : []
      try { localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), words })) } catch {}
      return new CompletionIndex(words)
    }
  } catch {}
  return new CompletionIndex([])
}
