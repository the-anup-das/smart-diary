"use client"
import * as React from "react"
import { Mic, MicOff, Loader2, Brain, Download, Cpu, AlertTriangle, RefreshCw } from "lucide-react"

const CHUNK_DURATION_MS = 5000
const WARM_POLL_INTERVAL_MS = 5000
const SILENCE_THRESHOLD = 30 // Increased to ignore louder background noise
const SILENCE_TIMEOUT_MS = 1500 // How long to wait for a pause before transcribing
const MAX_CHUNK_DURATION_MS = 15000 // Force transcribe after 15s even if no pause

// Estimated load time in seconds (first load = download + load, subsequent = load only)
const ESTIMATED_FIRST_LOAD_S = 45
const ESTIMATED_RELOAD_S = 8
const CRITICAL_TIMEOUT_S = 180 // 3 minutes

type RecorderState = "idle" | "warming" | "recording" | "error"
type WarmPhase = "downloading" | "loading" | "ready" | "failed"

interface VoiceRecorderProps {
  onTranscript: (text: string) => void
  onRecordingChange?: (isRecording: boolean) => void
  disabled?: boolean
  modelName?: string
}

export function VoiceRecorder({ onTranscript, onRecordingChange, disabled, modelName }: VoiceRecorderProps) {
  const [state, setState] = React.useState<RecorderState>("idle")
  const [isTranscribing, setIsTranscribing] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [isTalking, setIsTalking] = React.useState(false)

  // Warming progress state
  const [warmProgress, setWarmProgress] = React.useState(0)
  const [warmPhase, setWarmPhase] = React.useState<WarmPhase>("downloading")
  const [warmElapsed, setWarmElapsed] = React.useState(0)
  const [warmError, setWarmError] = React.useState<string | null>(null)
  
  const warmStartRef = React.useRef<number>(0)
  const warmTimerRef = React.useRef<ReturnType<typeof setInterval> | null>(null)
  const isFirstLoadRef = React.useRef(true)

  const streamRef = React.useRef<MediaStream | null>(null)
  const isRecordingRef = React.useRef(false)
  const chunkTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const warmPollRef = React.useRef<ReturnType<typeof setInterval> | null>(null)

  // Audio analysis refs
  const audioCtxRef = React.useRef<AudioContext | null>(null)
  const analyserRef = React.useRef<AnalyserNode | null>(null)
  const animFrameRef = React.useRef<number | null>(null)
  const maxVolumeInChunkRef = React.useRef<number>(0)
  const waveContainerRef = React.useRef<HTMLDivElement>(null)
  
  // VAD UI Debounce
  const isTalkingRef = React.useRef(false)
  const talkingTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const silenceFlushTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const maxDurationTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  // ─── progress bar ticker ──────────────────────────────────────────────────

  const startWarmProgress = React.useCallback(() => {
    warmStartRef.current = Date.now()
    setWarmProgress(0)
    setWarmElapsed(0)
    setWarmPhase("downloading")
    setWarmError(null)

    const total = isFirstLoadRef.current ? ESTIMATED_FIRST_LOAD_S : ESTIMATED_RELOAD_S

    if (warmTimerRef.current) clearInterval(warmTimerRef.current)
    warmTimerRef.current = setInterval(() => {
      const elapsed = (Date.now() - warmStartRef.current) / 1000
      setWarmElapsed(Math.floor(elapsed))

      // Progress asymptotically approaches 95%
      const raw = elapsed / total
      const progress = Math.min(95, (1 - Math.exp(-raw * 2.5)) * 100)
      setWarmProgress(progress)

      if (progress < 60) setWarmPhase("downloading")
      else setWarmPhase("loading")

      // Detect if we are stuck
      if (elapsed > CRITICAL_TIMEOUT_S) {
        setWarmPhase("failed")
        setWarmError("Taking too long. The model might be too large for your system's RAM.")
        if (warmPollRef.current) clearInterval(warmPollRef.current)
      }
    }, 500)
  }, [])

  const stopWarmProgress = React.useCallback((success: boolean) => {
    if (warmTimerRef.current) clearInterval(warmTimerRef.current)
    if (success) {
      setWarmProgress(100)
      setWarmPhase("ready")
      isFirstLoadRef.current = false
    }
  }, [])

  // ─── transcribe one blob ──────────────────────────────────────────────────

  const transcribeBlob = React.useCallback(async (blob: Blob) => {
    if (blob.size < 1024) return
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
  }, [onTranscript])

  // ─── audio visualizer ─────────────────────────────────────────────────────

  const updateVolume = React.useCallback(() => {
    if (!analyserRef.current || !isRecordingRef.current) return
    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount)
    analyserRef.current.getByteFrequencyData(dataArray)
    let max = 0
    for (let i = 0; i < dataArray.length; i++) { if (dataArray[i] > max) max = dataArray[i] }
    
    maxVolumeInChunkRef.current = Math.max(maxVolumeInChunkRef.current, max)
    
    // UI Feedback for VAD
    if (max >= SILENCE_THRESHOLD) {
      if (!isTalkingRef.current) {
        isTalkingRef.current = true
        setIsTalking(true)
      }
      if (talkingTimerRef.current) clearTimeout(talkingTimerRef.current)
      talkingTimerRef.current = setTimeout(() => {
        isTalkingRef.current = false
        setIsTalking(false)
      }, 1000)

      // SMART FLUSH: Reset the silence timer because we just heard sound
      if (silenceFlushTimerRef.current) clearTimeout(silenceFlushTimerRef.current)
      silenceFlushTimerRef.current = null
    } else {
      // We are silent right now. If we were recently talking, start the countdown to flush.
      if (isTalkingRef.current && !silenceFlushTimerRef.current) {
        silenceFlushTimerRef.current = setTimeout(() => {
           // Silence period reached! Flush the current recording.
           if (typeof (window as any).__voiceFlush === "function") {
             (window as any).__voiceFlush()
           }
        }, SILENCE_TIMEOUT_MS)
      }
    }

    if (waveContainerRef.current) {
      const scale = 1 + (max / 255) * 0.5
      waveContainerRef.current.style.setProperty("--vol-scale", scale.toString())
    }
    animFrameRef.current = requestAnimationFrame(updateVolume)
  }, [])

  // ─── chunked recording loop ───────────────────────────────────────────────

  const recordChunk = React.useCallback((stream: MediaStream) => {
    const chunks: Blob[] = []
    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/webm"
    const recorder = new MediaRecorder(stream, { mimeType })
    
    // Logic to manually trigger a flush from outside
    const flush = () => {
      if (recorder.state === "recording") recorder.stop()
    }

    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data) }
    recorder.onstop = async () => {
      if (silenceFlushTimerRef.current) clearTimeout(silenceFlushTimerRef.current)
      if (maxDurationTimerRef.current) clearTimeout(maxDurationTimerRef.current)
      silenceFlushTimerRef.current = null
      maxDurationTimerRef.current = null

      if (maxVolumeInChunkRef.current >= SILENCE_THRESHOLD) {
        transcribeBlob(new Blob(chunks, { type: mimeType }))
      }
      
      maxVolumeInChunkRef.current = 0
      // Safety check: only restart if we are still supposed to be recording AND the stream is still active
      if (isRecordingRef.current && stream.active) {
        recordChunk(stream)
      }
    }

    if (stream.active) {
      recorder.start()
    } else {
      stopRecording()
    }

    // 1. SILENCE MONITOR: If updateVolume sees silence, it will eventually call this 'flush'
    // We attach the flush function to a ref so updateVolume can see it
    (window as any).__voiceFlush = flush

    // 2. SAFETY LIMIT: Stop after MAX_CHUNK_DURATION_MS no matter what
    maxDurationTimerRef.current = setTimeout(flush, MAX_CHUNK_DURATION_MS)

  }, [transcribeBlob])

  // ─── begin recording ──────────────────────────────────────────────────────

  const beginRecording = React.useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      isRecordingRef.current = true
      setState("recording")
      onRecordingChange?.(true)
      const AC = window.AudioContext || (window as any).webkitAudioContext
      audioCtxRef.current = new AC()
      const source = audioCtxRef.current.createMediaStreamSource(stream)
      analyserRef.current = audioCtxRef.current.createAnalyser()
      analyserRef.current.fftSize = 256
      source.connect(analyserRef.current)
      maxVolumeInChunkRef.current = 0
      updateVolume()
      recordChunk(stream)
    } catch (e: any) {
      if (e.name === "NotAllowedError") {
        setError("Microphone access denied. Check browser permissions for this site.")
      } else if (e.name === "NotFoundError") {
        setError("No microphone found. Please connect a microphone.")
      } else {
        setError(`Mic error: ${e.name || e.message}. Try allowing microphone in browser settings.`)
      }
      setState("error")
    }
  }, [recordChunk, onRecordingChange, updateVolume])

  // ─── stop recording ───────────────────────────────────────────────────────

  const stopRecording = React.useCallback(() => {
    isRecordingRef.current = false
    setState("idle")
    onRecordingChange?.(false)
    if (chunkTimerRef.current) clearTimeout(chunkTimerRef.current)
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    if (audioCtxRef.current && audioCtxRef.current.state !== "closed") audioCtxRef.current.close()
    audioCtxRef.current = null
    analyserRef.current = null
    setIsTalking(false)
    isTalkingRef.current = false
    if (talkingTimerRef.current) clearTimeout(talkingTimerRef.current)
    if (waveContainerRef.current) waveContainerRef.current.style.setProperty("--vol-scale", "1")
  }, [onRecordingChange])

  // ─── mic click handler ────────────────────────────────────────────────────

  const handleMicClick = React.useCallback(async () => {
    if (state === "recording") { stopRecording(); return }
    if (state === "warming" && warmPhase !== "failed") return
    
    setError(null)
    setWarmError(null)

    try {
      const res = await fetch("/api/voice/status")
      const data = await res.json()
      
      if (data.error_detail) {
        setWarmPhase("failed")
        setWarmError(data.error_detail)
        setState("warming")
        return
      }

      if (data.model_loaded) { await beginRecording(); return }

      setState("warming")
      startWarmProgress()

      if (warmPollRef.current) clearInterval(warmPollRef.current)
      warmPollRef.current = setInterval(async () => {
        try {
          const r = await fetch("/api/voice/status")
          const d = await r.json()
          
          if (d.error_detail) {
            setWarmPhase("failed")
            setWarmError(d.error_detail)
            if (warmPollRef.current) clearInterval(warmPollRef.current)
            if (warmTimerRef.current) clearInterval(warmTimerRef.current)
            return
          }

          if (d.model_loaded) {
            if (warmPollRef.current) clearInterval(warmPollRef.current)
            stopWarmProgress(true)
            setTimeout(() => beginRecording(), 300)
          }
        } catch { /* keep polling */ }
      }, WARM_POLL_INTERVAL_MS)
    } catch {
      await beginRecording()
    }
  }, [state, warmPhase, beginRecording, stopRecording, startWarmProgress, stopWarmProgress])

  // Cleanup
  React.useEffect(() => {
    return () => {
      isRecordingRef.current = false
      if (chunkTimerRef.current) clearTimeout(chunkTimerRef.current)
      if (warmPollRef.current) clearInterval(warmPollRef.current)
      if (warmTimerRef.current) clearInterval(warmTimerRef.current)
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
      streamRef.current?.getTracks().forEach((t) => t.stop())
      if (audioCtxRef.current && audioCtxRef.current.state !== "closed") audioCtxRef.current.close().catch(() => {})
    }
  }, [])

  const isRecording = state === "recording"
  const isWarming = state === "warming"
  const shortModel = (modelName || "whisper").split("/").pop() || "whisper"

  const phaseIcon = warmPhase === "failed" 
    ? <AlertTriangle className="w-3 h-3" />
    : warmPhase === "downloading"
    ? <Download className="w-3 h-3" />
    : warmPhase === "loading"
    ? <Cpu className="w-3 h-3" />
    : <Brain className="w-3 h-3" />

  const phaseLabel = warmPhase === "failed"
    ? "Failed to load"
    : warmPhase === "downloading"
    ? `Downloading ${shortModel}…`
    : warmPhase === "loading"
    ? `Loading ${shortModel}…`
    : "Ready!"

  return (
    <div className="flex items-center gap-2" ref={waveContainerRef}>
      {/* Mic button */}
      <button
        type="button"
        onClick={handleMicClick}
        disabled={disabled}
        title={isWarming ? "Loading Whisper model…" : isRecording ? "Stop voice input" : "Start voice input"}
        className={`
          relative p-2 rounded-full transition-all duration-200 cursor-pointer flex-shrink-0
          disabled:opacity-40 disabled:cursor-not-allowed
          ${isRecording
            ? "bg-red-500/10 text-red-500 hover:bg-red-500/20"
            : isWarming
            ? warmPhase === "failed" ? "bg-red-500/10 text-red-500" : "bg-amber-500/10 text-amber-500"
            : "text-gray-400 hover:bg-black/5 dark:hover:bg-white/5 hover:text-gray-600 dark:hover:text-gray-300"
          }
        `}
      >
        {(isRecording || isWarming) && (
          <span
            className={`absolute inset-0 rounded-full ${isRecording ? "bg-red-500/25" : warmPhase === "failed" ? "bg-red-500/10" : "bg-amber-500/25 animate-ping"}`}
            style={isRecording ? { transform: "scale(var(--vol-scale, 1))", transition: "transform 0.1s ease-out" } : undefined}
          />
        )}
        {isWarming && warmPhase !== "failed"
          ? <Loader2 className="w-4 h-4 relative z-10 animate-spin" />
          : isWarming && warmPhase === "failed"
          ? <RefreshCw className="w-4 h-4 relative z-10" />
          : isRecording
          ? <MicOff className="w-4 h-4 relative z-10" />
          : <Mic className="w-4 h-4" />
        }
      </button>

      {/* Warming progress card */}
      {isWarming && (
        <div className={`flex flex-col gap-1 border rounded-xl px-3 py-2 min-w-[240px] shadow-sm ${
          warmPhase === "failed" ? "bg-red-500/8 border-red-500/20" : "bg-amber-500/8 border-amber-500/20"
        }`}>
          {/* Header row */}
          <div className="flex items-center justify-between gap-2">
            <div className={`flex items-center gap-1.5 ${warmPhase === "failed" ? "text-red-500" : "text-amber-500"}`}>
              {phaseIcon}
              <span className="text-xs font-semibold">{phaseLabel}</span>
            </div>
            <span className={`text-[10px] font-mono tabular-nums ${warmPhase === "failed" ? "text-red-400/70" : "text-amber-400/70"}`}>
              {warmElapsed}s
            </span>
          </div>

          {/* Progress bar */}
          <div className={`w-full h-1.5 rounded-full overflow-hidden ${warmPhase === "failed" ? "bg-red-500/15" : "bg-amber-500/15"}`}>
            <div
              className={`h-full rounded-full transition-all duration-500 ease-out ${warmPhase === "failed" ? "bg-red-500" : ""}`}
              style={warmPhase !== "failed" ? {
                width: `${warmProgress}%`,
                background: "linear-gradient(90deg, #f59e0b, #fbbf24)",
                boxShadow: "0 0 6px rgba(245,158,11,0.5)",
              } : { width: '100%' }}
            />
          </div>

          {/* Footer: model name + estimated time / error */}
          <div className="flex flex-col gap-0.5">
            <div className="flex items-center justify-between">
              <span className={`text-[10px] font-mono truncate max-w-[150px] ${warmPhase === "failed" ? "text-red-400/60" : "text-amber-400/60"}`}>
                {shortModel}
              </span>
              {warmPhase !== "failed" && (
                <span className="text-[10px] text-amber-400/60">
                  {warmProgress < 95
                    ? `~${Math.max(0, (isFirstLoadRef.current ? ESTIMATED_FIRST_LOAD_S : ESTIMATED_RELOAD_S) - warmElapsed)}s left`
                    : "Almost there…"
                  }
                </span>
              )}
            </div>
            {warmError && (
              <span className="text-[9px] text-red-500 font-medium leading-tight mt-0.5 line-clamp-2">
                {warmError}
              </span>
            )}
            {warmPhase === "failed" && (
              <span className="text-[9px] text-gray-500 italic mt-0.5">
                Tip: Try a smaller model like 'base.en' if this persists.
              </span>
            )}
          </div>
        </div>
      )}

      {/* Recording status */}
      {isRecording && !isTranscribing && (
        <span className={`text-xs font-medium transition-colors duration-300 select-none ${isTalking ? "text-red-500 animate-pulse" : "text-gray-400"}`}>
          {isTalking ? "Voice detected…" : "Silent (Waiting for voice)…"}
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
