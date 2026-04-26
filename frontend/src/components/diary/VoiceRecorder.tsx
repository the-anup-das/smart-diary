"use client"
import * as React from "react"
import { Mic, MicOff, Loader2 } from "lucide-react"

/** How long each audio chunk is (ms) before it's sent for transcription. */
const CHUNK_DURATION_MS = 5000

interface VoiceRecorderProps {
  /** Called each time a chunk is successfully transcribed. */
  onTranscript: (text: string) => void
  /** Called whenever the recording state changes (true = recording). */
  onRecordingChange?: (isRecording: boolean) => void
  disabled?: boolean
}

type RecorderState = "idle" | "recording" | "error"

export function VoiceRecorder({ onTranscript, onRecordingChange, disabled }: VoiceRecorderProps) {
  const [state, setState] = React.useState<RecorderState>("idle")
  const [isTranscribing, setIsTranscribing] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  // Refs so callbacks inside MediaRecorder events always see fresh values
  const streamRef = React.useRef<MediaStream | null>(null)
  const isRecordingRef = React.useRef(false)
  const chunkTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  // ─── transcribe a single audio blob ──────────────────────────────────────

  const transcribeBlob = React.useCallback(
    async (blob: Blob) => {
      // Skip silent / near-empty blobs the browser sometimes emits
      if (blob.size < 1024) return

      setIsTranscribing(true)
      try {
        const formData = new FormData()
        formData.append("audio", blob, "chunk.webm")

        const res = await fetch("/api/voice/transcribe", {
          method: "POST",
          body: formData,
        })

        if (!res.ok) {
          const err = await res.json().catch(() => ({}))
          throw new Error(err.detail || `Server error ${res.status}`)
        }

        const data = await res.json()
        if (data.text?.trim()) {
          onTranscript(data.text.trim())
        }
      } catch (e: any) {
        // Don't surface every chunk error — just show the first one
        setError(e.message || "Transcription failed")
      } finally {
        setIsTranscribing(false)
      }
    },
    [onTranscript]
  )

  // ─── record one chunk, then restart if still recording ───────────────────

  const recordChunk = React.useCallback(
    (stream: MediaStream) => {
      const chunks: Blob[] = []
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm"

      const recorder = new MediaRecorder(stream, { mimeType })

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data)
      }

      recorder.onstop = async () => {
        const blob = new Blob(chunks, { type: mimeType })
        // Fire-and-forget: transcribe in background while next chunk records
        transcribeBlob(blob)
        // Restart immediately if the user hasn't clicked stop yet
        if (isRecordingRef.current) recordChunk(stream)
      }

      recorder.start()

      // Schedule the stop after CHUNK_DURATION_MS
      chunkTimerRef.current = setTimeout(() => {
        if (recorder.state === "recording") recorder.stop()
      }, CHUNK_DURATION_MS)
    },
    [transcribeBlob]
  )

  // ─── public controls ─────────────────────────────────────────────────────

  const startRecording = async () => {
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      isRecordingRef.current = true
      setState("recording")
      onRecordingChange?.(true)
      recordChunk(stream)
    } catch (e: any) {
      const msg =
        e.name === "NotAllowedError"
          ? "Microphone access denied. Please allow it in your browser settings."
          : "Could not access microphone."
      setError(msg)
      setState("error")
    }
  }

  const stopRecording = () => {
    isRecordingRef.current = false
    setState("idle")
    onRecordingChange?.(false)
    if (chunkTimerRef.current) clearTimeout(chunkTimerRef.current)
    // Stopping the stream triggers recorder.onstop → final transcription
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }

  // Cleanup on unmount
  React.useEffect(() => {
    return () => {
      isRecordingRef.current = false
      if (chunkTimerRef.current) clearTimeout(chunkTimerRef.current)
      streamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  const isRecording = state === "recording"

  return (
    <div className="flex items-center gap-1.5">
      {/* Mic button */}
      <button
        type="button"
        onClick={isRecording ? stopRecording : startRecording}
        disabled={disabled}
        title={isRecording ? "Stop voice input" : "Start voice input"}
        className={`
          relative p-2 rounded-full transition-all duration-200 cursor-pointer
          disabled:opacity-40 disabled:cursor-not-allowed
          ${
            isRecording
              ? "bg-red-500/10 text-red-500 hover:bg-red-500/20"
              : "text-gray-400 hover:bg-black/5 dark:hover:bg-white/5 hover:text-gray-600 dark:hover:text-gray-300"
          }
        `}
      >
        {/* Pulsing ring while recording */}
        {isRecording && (
          <span className="absolute inset-0 rounded-full bg-red-500/25 animate-ping" />
        )}
        {isRecording ? (
          <MicOff className="w-4 h-4 relative z-10" />
        ) : (
          <Mic className="w-4 h-4" />
        )}
      </button>

      {/* Status indicators */}
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

      {/* Error (dismissible) */}
      {error && state !== "recording" && (
        <span
          className="text-xs text-red-500 max-w-[160px] truncate cursor-pointer"
          title={error}
          onClick={() => setError(null)}
        >
          {error}
        </span>
      )}
    </div>
  )
}
