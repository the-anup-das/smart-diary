"use client"
import * as React from "react"
import { Mic, MicOff, Loader2 } from "lucide-react"

/** How long each audio chunk is (ms) before being sent for transcription. */
const CHUNK_DURATION_MS = 5000

/** How often to poll /api/voice/status while the model is warming (ms). */
const WARM_POLL_INTERVAL_MS = 2000

type RecorderState =
  | "idle"          // mic button shown, ready to start
  | "warming"       // model is being loaded, waiting before we can record
  | "recording"     // actively capturing audio in chunks
  | "error"         // non-recoverable error (mic denied, etc.)

interface VoiceRecorderProps {
  /** Called each time a chunk is successfully transcribed. */
  onTranscript: (text: string) => void
  /** Called whenever recording state changes (true = actively recording). */
  onRecordingChange?: (isRecording: boolean) => void
  disabled?: boolean
}

export function VoiceRecorder({ onTranscript, onRecordingChange, disabled }: VoiceRecorderProps) {
  const [state, setState] = React.useState<RecorderState>("idle")
  const [isTranscribing, setIsTranscribing] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const streamRef = React.useRef<MediaStream | null>(null)
  const isRecordingRef = React.useRef(false)
  const chunkTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const warmPollRef = React.useRef<ReturnType<typeof setInterval> | null>(null)

  // ─── transcribe one blob ──────────────────────────────────────────────────

  const transcribeBlob = React.useCallback(
    async (blob: Blob) => {
      if (blob.size < 1024) return  // skip silent/empty chunks

      setIsTranscribing(true)
      try {
        const form = new FormData()
        form.append("audio", blob, "chunk.webm")

        const res = await fetch("/api/voice/transcribe", { method: "POST", body: form })

        if (!res.ok) {
          const err = await res.json().catch(() => ({}))
          throw new Error(err.detail || `Server error ${res.status}`)
        }

        const data = await res.json()
        if (data.text?.trim()) onTranscript(data.text.trim())
      } catch (e: any) {
        setError(e.message || "Transcription failed")
      } finally {
        setIsTranscribing(false)
      }
    },
    [onTranscript]
  )

  // ─── chunked recording loop ───────────────────────────────────────────────

  const recordChunk = React.useCallback(
    (stream: MediaStream) => {
      const chunks: Blob[] = []
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm"

      const recorder = new MediaRecorder(stream, { mimeType })

      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data) }

      recorder.onstop = async () => {
        // Transcribe in background while next chunk starts recording
        transcribeBlob(new Blob(chunks, { type: mimeType }))
        if (isRecordingRef.current) recordChunk(stream)
      }

      recorder.start()
      chunkTimerRef.current = setTimeout(() => {
        if (recorder.state === "recording") recorder.stop()
      }, CHUNK_DURATION_MS)
    },
    [transcribeBlob]
  )

  // ─── start actual recording (mic already granted) ─────────────────────────

  const beginRecording = React.useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      isRecordingRef.current = true
      setState("recording")
      onRecordingChange?.(true)
      recordChunk(stream)
    } catch (e: any) {
      const msg = e.name === "NotAllowedError"
        ? "Microphone access denied — please allow it in your browser settings."
        : "Could not access microphone."
      setError(msg)
      setState("error")
    }
  }, [recordChunk, onRecordingChange])

  // ─── stop recording ───────────────────────────────────────────────────────

  const stopRecording = React.useCallback(() => {
    isRecordingRef.current = false
    setState("idle")
    onRecordingChange?.(false)
    if (chunkTimerRef.current) clearTimeout(chunkTimerRef.current)
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }, [onRecordingChange])

  // ─── click handler: warm if needed, then record ───────────────────────────

  const handleMicClick = React.useCallback(async () => {
    if (state === "recording") { stopRecording(); return }
    if (state === "warming") return  // already waiting for model

    setError(null)

    // Check if the model is loaded — if not, show "Loading…" and poll
    try {
      const res = await fetch("/api/voice/status")
      const data = await res.json()

      if (data.model_loaded) {
        // Model ready — go straight to recording
        await beginRecording()
        return
      }

      // Model not loaded yet — show warming state and poll
      setState("warming")
      warmPollRef.current = setInterval(async () => {
        try {
          const r = await fetch("/api/voice/status")
          const d = await r.json()
          if (d.model_loaded) {
            if (warmPollRef.current) clearInterval(warmPollRef.current)
            await beginRecording()
          }
        } catch { /* keep polling */ }
      }, WARM_POLL_INTERVAL_MS)
    } catch {
      // If status check fails, try recording anyway — warm will happen on first transcribe
      await beginRecording()
    }
  }, [state, beginRecording, stopRecording])

  // Cleanup
  React.useEffect(() => {
    return () => {
      isRecordingRef.current = false
      if (chunkTimerRef.current) clearTimeout(chunkTimerRef.current)
      if (warmPollRef.current) clearInterval(warmPollRef.current)
      streamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  const isRecording = state === "recording"
  const isWarming = state === "warming"

  return (
    <div className="flex items-center gap-1.5">
      {/* Mic button */}
      <button
        type="button"
        onClick={handleMicClick}
        disabled={disabled}
        title={
          isWarming   ? "Loading Whisper model…" :
          isRecording ? "Stop voice input" :
                        "Start voice input"
        }
        className={`
          relative p-2 rounded-full transition-all duration-200 cursor-pointer
          disabled:opacity-40 disabled:cursor-not-allowed
          ${isRecording
            ? "bg-red-500/10 text-red-500 hover:bg-red-500/20"
            : isWarming
            ? "bg-amber-500/10 text-amber-500"
            : "text-gray-400 hover:bg-black/5 dark:hover:bg-white/5 hover:text-gray-600 dark:hover:text-gray-300"
          }
        `}
      >
        {/* Pulsing ring — red while recording, amber while warming */}
        {(isRecording || isWarming) && (
          <span className={`absolute inset-0 rounded-full animate-ping ${
            isRecording ? "bg-red-500/25" : "bg-amber-500/25"
          }`} />
        )}

        {isWarming
          ? <Loader2 className="w-4 h-4 relative z-10 animate-spin" />
          : isRecording
          ? <MicOff className="w-4 h-4 relative z-10" />
          : <Mic className="w-4 h-4" />
        }
      </button>

      {/* Status label */}
      {isWarming && (
        <span className="text-xs text-amber-500 font-medium select-none">
          Loading Whisper…
        </span>
      )}
      {isRecording && !isTranscribing && (
        <span className="text-xs text-red-500 font-medium animate-pulse select-none">
          Listening…
        </span>
      )}
      {isTranscribing && (
        <span className="flex items-center gap-1 text-xs text-primary/80 select-none">
          <Loader2 className="w-3 h-3 animate-spin" />
          <span>Transcribing…</span>
        </span>
      )}

      {/* Dismissible error */}
      {error && state !== "recording" && (
        <span
          className="text-xs text-red-500 max-w-[180px] truncate cursor-pointer"
          title={error}
          onClick={() => setError(null)}
        >
          {error}
        </span>
      )}
    </div>
  )
}
