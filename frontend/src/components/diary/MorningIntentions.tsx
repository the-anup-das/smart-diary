"use client"
import * as React from "react"
import { Sunrise, Plus } from "lucide-react"

export function MorningIntentions({ onSelect, isVisible }: { onSelect: (prompt: string) => void, isVisible: boolean }) {
  const [intentions, setIntentions] = React.useState<string[]>([])
  const [loading, setLoading] = React.useState(true)

  React.useEffect(() => {
    if (!isVisible) return;
    
    fetch("/api/analyze/intentions")
      .then(res => res.json())
      .then(data => {
        if (data.intentions) {
          setIntentions(data.intentions)
        }
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [isVisible])

  if (!isVisible) return null;
  if (!loading && intentions.length === 0) return null;

  return (
    <div className="mb-8 fade-in relative px-2 lg:px-6">
       <div className="flex items-center space-x-2 mb-3">
         <Sunrise className="w-5 h-5 text-amber-500" />
         <h3 className="text-sm font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-500">Morning Intentions</h3>
       </div>
       
       {loading ? (
         <div className="grid grid-cols-1 md:grid-cols-3 gap-3 animate-pulse">
           {[1, 2, 3].map(i => <div key={i} className="h-24 bg-black/5 dark:bg-white/5 rounded-xl w-full border border-black/5 dark:border-white/5"></div>)}
         </div>
       ) : (
         <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
           {intentions.map((prompt, i) => (
             <button
               key={i}
               onClick={() => onSelect(prompt)}
               className="text-left p-4 rounded-xl border border-amber-500/20 bg-amber-500/5 hover:bg-amber-500/10 cursor-pointer transition-all group flex flex-col justify-between"
             >
               <p className="text-sm text-gray-800 dark:text-gray-200 leading-snug line-clamp-3 mb-2">"{prompt}"</p>
               <span className="text-xs font-semibold text-amber-600 dark:text-amber-500 flex items-center mt-auto opacity-0 group-hover:opacity-100 transition-opacity">
                 <Plus className="w-3 h-3 mr-1" /> Use this prompt
               </span>
             </button>
           ))}
         </div>
       )}
    </div>
  )
}
