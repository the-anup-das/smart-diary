"use client"
import * as React from "react"
import { History, X } from "lucide-react"

export function EchoesWidget() {
  const [echo, setEcho] = React.useState<any>(null)
  const [visible, setVisible] = React.useState(true)

  React.useEffect(() => {
    fetch("/api/entries/echoes")
      .then(res => res.json())
      .then(data => {
        if (data.echo) {
          setEcho(data.echo)
        }
      })
      .catch(() => {})
  }, [])

  if (!echo || !visible) return null;

  return (
    <div className="mb-6 fade-in relative mx-2 lg:mx-6">
      <div className="p-5 rounded-2xl bg-gradient-to-r from-primary/5 to-transparent border-l-4 border-primary shadow-sm glass-panel">
        <div className="flex justify-between items-start mb-2">
          <div className="flex items-center space-x-2">
            <History className="w-5 h-5 text-primary" />
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Synchronicity: {echo.date}</h3>
          </div>
          <button onClick={() => setVisible(false)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-primary font-medium mb-3">{echo.similarity_reason}</p>
        <p className="text-sm text-gray-700 dark:text-gray-300 italic leading-relaxed">
          "{echo.content}"
        </p>
      </div>
    </div>
  )
}
