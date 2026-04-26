"use client"
import * as React from "react"
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Image from '@tiptap/extension-image'
import { FeedbackDashboard } from "./FeedbackDashboard"
import { EchoesWidget } from "./EchoesWidget"
import { MorningIntentions } from "./MorningIntentions"
import { CheckCircle2, Trash, WifiOff } from "lucide-react"
import { DeleteConfirmationModal } from "./DeleteConfirmationModal"
import { useNetworkStatus } from "@/lib/useNetworkStatus"
import { VoiceRecorder } from "./VoiceRecorder"

export function JournalEditor({ initialContent = "", initialId = null }: { initialContent?: string, initialId?: string | null }) {
  const isOnline = useNetworkStatus()
  const [isSaving, setIsSaving] = React.useState(false)
  const [isProcessing, setIsProcessing] = React.useState(false)
  const [processStage, setProcessStage] = React.useState<string>("")
  const [feedbackData, setFeedbackData] = React.useState<any>(null)
  const [aiError, setAiError] = React.useState<string | null>(null)
  const [lastSaved, setLastSaved] = React.useState<Date | null>(null)
  const [currentEntryId, setCurrentEntryId] = React.useState<string | null>(initialId)
  const [showIntentions, setShowIntentions] = React.useState(initialContent.length < 15)
  const [preferences, setPreferences] = React.useState<any>({})
  const [showDeleteModal, setShowDeleteModal] = React.useState(false)
  const [isVoiceRecording, setIsVoiceRecording] = React.useState(false)
  const [sttEnabled, setSttEnabled] = React.useState(false)
  const timeoutRef = React.useRef<NodeJS.Timeout | null>(null)

  React.useEffect(() => {
    fetch("/api/users/me")
      .then(res => res.json())
      .then(data => {
        if (!data.detail && data.preferences) {
          setPreferences(data.preferences)
        }
      })
      .catch(() => {})
  }, [])

  // Check if STT is configured and kick off a background model warm-up
  React.useEffect(() => {
    fetch("/api/voice/status")
      .then(res => res.json())
      .then(data => {
        if (data.enabled) {
          setSttEnabled(true)
          // Fire-and-forget: pre-load the Whisper model while the user writes
          fetch("/api/voice/warm", { method: "POST" }).catch(() => {})
        }
      })
      .catch(() => {})
  }, [])

  React.useEffect(() => {
    if (isOnline) {
      const offlineDraft = localStorage.getItem('offline_draft');
      if (offlineDraft) {
        setIsSaving(true);
        fetch('/api/entries', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: offlineDraft })
        })
        .then(res => res.json())
        .then(resData => {
           if (resData.id) setCurrentEntryId(resData.id);
           localStorage.removeItem('offline_draft');
           setLastSaved(new Date());
        })
        .catch(console.error)
        .finally(() => setIsSaving(false));
      }
    }
  }, [isOnline]);

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit,
      Image,
      Placeholder.configure({
        placeholder: "What's heavily occupying your thoughts today? (Use '-' for bullets or '#' for headers)",
        emptyEditorClass: 'cursor-text before:content-[attr(data-placeholder)] before:absolute before:text-gray-600 before:opacity-50 before:pointer-events-none',
      }),
    ],
    content: initialContent,
    editorProps: {
      attributes: {
        class: 'prose dark:prose-invert prose-lg md:prose-xl max-w-none focus:outline-none min-h-[400px]',
      },
      scrollThreshold: 200,
      scrollMargin: 200,
    },
    onUpdate: ({ editor }) => {
      // Clear transient AI engine errors when the user resumes typing
      if (aiError) setAiError(null);

      // Trigger debounce save
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
      
      setIsSaving(true)
      timeoutRef.current = setTimeout(async () => {
        try {
          const htmlContent = editor.getHTML()
          
          if (!navigator.onLine) {
            localStorage.setItem('offline_draft', htmlContent);
            setLastSaved(new Date());
            setIsSaving(false);
            return;
          }

          const res = await fetch('/api/entries', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: htmlContent })
          });
          if (res.ok) {
            const resData = await res.json();
            setCurrentEntryId(resData.id);
            setIsSaving(false);
            setLastSaved(new Date());
          } else {
            setIsSaving(false);
          }
        } catch (err) {
          console.error('Save failed:', err);
          setIsSaving(false);
        }
      }, 1500) 
    }
  })

  async function handleSaveAndReflect() {
    if (!editor) return;
    
    if (!isOnline) {
      setAiError("You are currently offline. AI reflection requires a network connection. Your draft is securely saved locally.");
      return;
    }
    
    setIsProcessing(true);
    setFeedbackData(null);
    setAiError(null);

    // Step 1: Force-save the current draft immediately (bypass debounce)
    setProcessStage("Saving entry...");
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    try {
      const htmlContent = editor.getHTML();
      const saveRes = await fetch('/api/entries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: htmlContent })
      });
      if (saveRes.ok) {
        setLastSaved(new Date());
        setIsSaving(false);
      }
    } catch (err) {
      setAiError("Failed to save entry before analysis.");
      setIsProcessing(false);
      setProcessStage("");
      return;
    }

    // Step 2: Trigger AI analysis
    setProcessStage("Reflecting with AI...");
    try {
      const res = await fetch('/api/analyze', { method: 'POST' });
      const rawText = await res.text();
      
      if (!res.ok) {
        try {
          const errData = JSON.parse(rawText);
          setAiError(errData.error || errData.detail || `Server Failed (Status: ${res.status})`);
        } catch {
          setAiError(`Server Error (Status: ${res.status})`);
        }
        return;
      }
      
      const data = JSON.parse(rawText);
      if (data.success) {
        setFeedbackData(data.feedback);
      } else {
        setAiError(data.error || "Failed to parse AI response.");
      }
    } catch (err: any) {
      setAiError(err.message || "Network layer failed to connect to AI engine.");
    } finally {
      setIsProcessing(false);
      setProcessStage("");
    }
  }

  async function handleDelete() {
    if (!currentEntryId) return;
    if (!isOnline) {
      setAiError("Deletion requires an active network connection to sync with the cloud.");
      return;
    }
    setShowDeleteModal(true);
  }

  async function confirmDelete() {
    if (!currentEntryId) return;
    const res = await fetch(`/api/entries/${currentEntryId}`, { method: 'DELETE' });
    if (res.ok) {
      editor?.commands.setContent("");
      setCurrentEntryId(null);
      setFeedbackData(null);
      setLastSaved(null);
      setShowDeleteModal(false);
    }
  }

  // Cleanup timeout on unmount
  React.useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  const handleSelectIntention = (prompt: string) => {
    if (editor) {
      editor.commands.focus('end');
      editor.commands.insertContent(`<h2>${prompt}</h2><p></p>`);
      setShowIntentions(false);
    }
  }

  const handleTranscript = React.useCallback((text: string) => {
    if (!editor) return
    // Move cursor to the very end, then insert the transcribed text.
    // A space is prepended unless the document is empty.
    editor.commands.focus('end')
    const isEmpty = editor.getText().trim().length === 0
    editor.commands.insertContent(isEmpty ? text : ' ' + text)
  }, [editor])

  const wordCount = editor ? editor.getText().trim().split(/\s+/).filter(w => w.length > 0).length : 0;

  return (
    <div className="flex flex-col h-full w-full pt-6">
      <div className="flex justify-between items-center mb-10 px-2 lg:px-6">
        <h1 className="text-3xl font-serif font-bold tracking-tight text-gray-900 dark:text-gray-100">
          {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
        </h1>
        <div className="flex items-center space-x-4 fade-in">
          {preferences?.enable_deletion && currentEntryId && (
            <button 
              onClick={handleDelete}
              className="p-2 rounded-full hover:bg-red-500/10 text-gray-400 hover:text-red-500 transition-colors cursor-pointer group"
              title="Delete Current Entry"
            >
              <Trash className="w-4 h-4" />
            </button>
          )}
          {/* Voice recorder — only shown when STT_BASE_URL is configured */}
          {sttEnabled && (
            <VoiceRecorder
              onTranscript={handleTranscript}
              onRecordingChange={setIsVoiceRecording}
              disabled={!isOnline}
            />
          )}
          {preferences?.targets?.daily_words && !preferences?.hide_word_target ? (
            <div className={`flex items-center space-x-2 px-3 py-1 rounded-full border ${wordCount >= preferences.targets.daily_words ? 'bg-green-500/10 border-green-500/20 text-green-600 dark:text-green-400' : 'bg-black/5 dark:bg-white/5 border-black/5 dark:border-white/5 text-gray-500 dark:text-gray-400'}`}>
              <span className="text-sm font-mono tracking-wide font-medium">
                {wordCount} <span className={`opacity-60 font-normal ${wordCount >= preferences.targets.daily_words ? 'text-green-600 dark:text-green-400' : 'text-gray-400'}`}>/ {preferences.targets.daily_words} words</span>
              </span>
            </div>
          ) : (
            <span className="text-sm text-gray-400 font-mono tracking-wide">{wordCount} words</span>
          )}
          <div className="flex items-center space-x-2 text-sm text-gray-500 font-medium bg-black/5 dark:bg-white/5 px-4 py-1.5 rounded-full border border-black/10 dark:border-white/10">
            {isSaving ? (
              <>
                <span className="w-2 h-2 rounded-full bg-success animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]"></span>
                <span>Saving...</span>
              </>
            ) : lastSaved ? (
              !isOnline ? (
                <span className="flex items-center text-orange-500 gap-1.5 font-semibold"><WifiOff className="w-3.5 h-3.5" /> Saved locally</span>
              ) : (
                <span>Saved {lastSaved.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
              )
            ) : (
              <span>Draft</span>
            )}
          </div>
        </div>
      </div>
      
      <EchoesWidget />
      
      <MorningIntentions isVisible={showIntentions} onSelect={handleSelectIntention} />
      
      <div className="flex-1 relative overflow-hidden group">
        <div className={`w-full h-full bg-transparent ${preferences?.typography === 'sans' ? 'font-sans' : 'font-serif'} text-lg leading-loose text-gray-800 dark:text-gray-200 px-2 lg:px-6 pt-4 pb-[300px] custom-scrollbar overflow-y-auto scroll-smooth scroll-pb-[200px]`}>
          <EditorContent editor={editor} />
        </div>
        {/* Subtle gradient overlay to fade text at bottom elegantly */}
        <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-background to-transparent pointer-events-none"></div>
      </div>

      {/* Save & Reflect FAB */}
      <div className="absolute bottom-8 right-6 lg:right-10 z-50" suppressHydrationWarning>
         <button 
           onClick={handleSaveAndReflect}
           disabled={!editor || isProcessing || wordCount < 3}
           suppressHydrationWarning
           className={`shadow-[0_8px_30px_rgba(139,92,246,0.4)] ring-4 ${
             isVoiceRecording
               ? 'ring-red-500/40 shadow-[0_8px_30px_rgba(239,68,68,0.35)]'
               : 'ring-primary/20'
           } bg-gradient-to-br from-primary to-violet-600 text-white border border-white/20 flex items-center justify-center cursor-pointer group disabled:opacity-40 disabled:cursor-not-allowed hover:-translate-y-1 active:scale-95 transition-all duration-300 ease-out h-[56px] rounded-full overflow-hidden ${isProcessing ? 'w-[220px]' : 'w-[56px] hover:w-[200px]'}`}
         >
           {isProcessing ? (
             <span className="flex items-center space-x-2 px-4">
               <span className="animate-spin text-xl">⏳</span>
               <span className="font-bold text-sm tracking-wide whitespace-nowrap">{processStage}</span>
             </span>
           ) : (
             <>
               <CheckCircle2 className="w-6 h-6 flex-shrink-0 group-hover:scale-110 transition-transform drop-shadow-md" />
               <span className="font-bold whitespace-nowrap max-w-0 group-hover:max-w-[150px] group-hover:ml-2 group-hover:pr-3 opacity-0 group-hover:opacity-100 transition-all duration-300 ease-out text-sm tracking-wide flex-shrink-0 overflow-hidden">
                  Save & Reflect
               </span>
             </>
           )}
         </button>
      </div>

      {aiError && (
        <div className="mb-6 mx-2 lg:mx-6 p-4 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-xl flex items-start justify-between fade-in shadow-sm">
          <div className="flex items-center text-red-600 dark:text-red-400 text-sm font-medium">
            <span className="mr-2">⚠️</span>
            <span>AI Engine Trace: {aiError}</span>
          </div>
          <button 
            onClick={() => setAiError(null)} 
            className="ml-4 text-red-500/70 hover:text-red-600 dark:hover:text-red-400 transition-colors cursor-pointer text-lg leading-none"
            title="Dismiss Error"
          >
            &times;
          </button>
        </div>
      )}

      <FeedbackDashboard feedback={feedbackData} preferences={preferences} onClose={() => setFeedbackData(null)} />

      {showDeleteModal && (
        <DeleteConfirmationModal
          entry={{ 
            id: currentEntryId || "", 
            date: new Date().toISOString().split('T')[0] 
          }}
          onCancel={() => setShowDeleteModal(false)}
          onConfirm={confirmDelete}
        />
      )}
    </div>
  )
}

