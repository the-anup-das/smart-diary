"use client"
import * as React from "react"
import { AlertTriangle, X } from "lucide-react"

export interface DeleteEntryInfo {
  id: string
  date: string
}

interface DeleteConfirmationModalProps {
  entry: DeleteEntryInfo
  onCancel: () => void
  onConfirm: () => Promise<void>
}

export function DeleteConfirmationModal({ entry, onCancel, onConfirm }: DeleteConfirmationModalProps) {
  const [isDeleting, setIsDeleting] = React.useState(false)
  
  // Format date correctly handling potential timezone shifts
  const dateLabel = new Date(entry.date + 'T00:00:00').toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
  })

  React.useEffect(() => {
    document.body.style.overflow = 'hidden'
    const handleEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel() }
    window.addEventListener('keydown', handleEsc)
    return () => {
      document.body.style.overflow = 'unset'
      window.removeEventListener('keydown', handleEsc)
    }
  }, [onCancel])

  const handleConfirm = async () => {
    setIsDeleting(true)
    await onConfirm()
    setIsDeleting(false)
  }

  return (
    <div
      className="fixed inset-0 z-[110] flex items-center justify-center bg-background/70 backdrop-blur-xl fade-in"
      onClick={onCancel}
    >
      <div
        className="relative w-full max-w-md mx-4 rounded-2xl bg-white dark:bg-gray-900 border border-black/10 dark:border-white/10 shadow-2xl p-6 fade-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onCancel}
          className="absolute top-4 right-4 p-1.5 rounded-full text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-black/5 dark:hover:bg-white/5 transition-all cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Icon + Title */}
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-14 h-14 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
            <AlertTriangle className="w-7 h-7 text-red-500" />
          </div>
          <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-1">Delete this entry?</h2>
          <p className="text-sm text-gray-500">{dateLabel}</p>
          <p className="text-xs text-gray-400 mt-3 max-w-xs">
            This entry will be hidden immediately and permanently purged after 90 days. This cannot be undone.
          </p>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            disabled={isDeleting}
            className="flex-1 h-11 rounded-xl border border-black/10 dark:border-white/10 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-black/5 dark:hover:bg-white/5 transition-all cursor-pointer disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={isDeleting}
            className="flex-1 h-11 rounded-xl bg-red-600 hover:bg-red-700 text-white text-sm font-semibold transition-all cursor-pointer shadow-lg hover:shadow-red-500/30 hover:-translate-y-0.5 disabled:opacity-50 disabled:pointer-events-none active:scale-95"
          >
            {isDeleting ? 'Deleting...' : 'Delete Entry'}
          </button>
        </div>
      </div>
    </div>
  )
}
