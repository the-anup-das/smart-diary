"use client"
import * as React from "react"
import Link from "next/link"
import { MessageCircle, Send, Sparkles, CalendarDays } from "lucide-react"

interface Source {
  id: string
  date: string
  displayDate: string
  snippet: string
}

interface Message {
  role: "user" | "assistant"
  content: string
  sources?: Source[]
}

const SUGGESTIONS = [
  "What patterns do you see in my mood lately?",
  "When did I last write about work stress?",
  "What was I grateful for this month?",
  "What open worries keep coming back?",
]

export default function ChatPage() {
  const [messages, setMessages] = React.useState<Message[]>([])
  const [input, setInput] = React.useState("")
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState("")
  const bottomRef = React.useRef<HTMLDivElement>(null)
  const inputRef = React.useRef<HTMLTextAreaElement>(null)

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  async function send(text: string) {
    const question = text.trim()
    if (!question || loading) return
    setError("")
    setInput("")
    const nextMessages: Message[] = [...messages, { role: "user", content: question }]
    setMessages(nextMessages)
    setLoading(true)
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: nextMessages.map(m => ({ role: m.role, content: m.content })),
        }),
      })
      if (res.ok) {
        const data = await res.json()
        setMessages(prev => [...prev, { role: "assistant", content: data.reply, sources: data.sources }])
      } else if (res.status === 429) {
        setError("You're chatting faster than the journal can think — give it a minute.")
      } else {
        const data = await res.json().catch(() => null)
        setError(data?.detail || "The journal couldn't answer that. Please try again.")
      }
    } catch {
      setError("Could not reach the server. Check that the backend is running.")
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  return (
    <div className="flex flex-col w-full h-full max-w-3xl mx-auto pt-6 pb-4 fade-in">
      {/* Header */}
      <div className="flex items-center space-x-3 mb-6 px-2">
        <MessageCircle className="w-7 h-7 text-primary" />
        <h1 className="text-3xl font-serif font-bold tracking-tight text-gray-900 dark:text-gray-100">
          Chat with your journal
        </h1>
      </div>

      {/* Conversation */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-2 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Sparkles className="w-12 h-12 text-primary/40 mb-4" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
              Your diary remembers.
            </h2>
            <p className="text-sm text-gray-500 max-w-md mb-8">
              Ask about past moods, recurring themes, or anything you've written.
              Answers are grounded in your real entries — with dates.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left text-sm px-4 py-3 rounded-xl bg-white/50 dark:bg-black/20 border border-black/5 dark:border-white/10 text-gray-600 dark:text-gray-300 hover:border-primary/30 hover:text-primary transition-colors cursor-pointer"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                m.role === "user"
                  ? "bg-primary text-white shadow-md"
                  : "bg-white/60 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 text-gray-800 dark:text-gray-200 shadow-sm"
              }`}
            >
              {m.content}
              {m.role === "assistant" && m.sources && m.sources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-black/5 dark:border-white/10">
                  <span className="text-[10px] uppercase tracking-wide text-gray-400 font-semibold flex items-center gap-1">
                    <CalendarDays className="w-3 h-3" /> Drawn from
                  </span>
                  <div className="flex flex-wrap gap-1.5 mt-1.5">
                    {m.sources.map(s => (
                      <Link
                        key={s.id}
                        href={`/history?date=${s.date}`}
                        title={s.snippet}
                        aria-label={`Open the entry from ${s.displayDate} in History`}
                        className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-[11px] font-medium border border-primary/20 hover:bg-primary/20 hover:border-primary/40 transition-colors"
                      >
                        {s.displayDate}
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="rounded-2xl px-4 py-3 bg-white/60 dark:bg-black/20 border border-black/5 dark:border-white/10 shadow-sm">
              <span className="flex gap-1.5 items-center h-4" aria-label="Thinking">
                {[0, 1, 2].map(i => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-primary/60 animate-bounce"
                    style={{ animationDelay: `${i * 150}ms` }}
                  />
                ))}
              </span>
            </div>
          </div>
        )}

        {error && (
          <p className="text-danger text-sm font-medium text-center" role="alert">{error}</p>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Composer */}
      <div className="mt-4 px-2">
        <div className="flex items-end gap-2 rounded-2xl bg-white/60 dark:bg-black/20 backdrop-blur-xl border border-black/10 dark:border-white/10 shadow-lg p-2 focus-within:ring-2 focus-within:ring-primary/30 transition-shadow">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder="Ask your journal anything…"
            aria-label="Message your journal"
            className="flex-1 resize-none bg-transparent px-3 py-2.5 text-sm text-gray-900 dark:text-gray-100 placeholder:text-gray-400 focus:outline-none max-h-32"
          />
          <button
            onClick={() => send(input)}
            disabled={!input.trim() || loading}
            aria-label="Send message"
            className="p-2.5 rounded-xl bg-primary text-white shadow-md hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-all flex-shrink-0"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-[11px] text-gray-400 text-center mt-2">
          Answers come only from your own entries and stay on your server.
        </p>
      </div>
    </div>
  )
}
