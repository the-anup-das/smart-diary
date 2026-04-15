"use client"
import * as React from "react"
import { Sunrise, Sun, Sunset, Moon, Plus, RotateCw } from "lucide-react"

type TimeOfDay = "morning" | "afternoon" | "evening" | "night"

function getTimeOfDay(): TimeOfDay {
  const hour = new Date().getHours()
  if (hour >= 5 && hour < 12) return "morning"
  if (hour >= 12 && hour < 17) return "afternoon"
  if (hour >= 17 && hour < 21) return "evening"
  return "night"
}

const TIME_CONFIG: Record<TimeOfDay, {
  label: string
  icon: React.ElementType
  color: string
  bgColor: string
  borderColor: string
}> = {
  morning: {
    label: "Morning Intentions",
    icon: Sunrise,
    color: "text-amber-600 dark:text-amber-400",
    bgColor: "bg-amber-500/5 hover:bg-amber-500/10",
    borderColor: "border-amber-500/20",
  },
  afternoon: {
    label: "Afternoon Check-in",
    icon: Sun,
    color: "text-orange-600 dark:text-orange-400",
    bgColor: "bg-orange-500/5 hover:bg-orange-500/10",
    borderColor: "border-orange-500/20",
  },
  evening: {
    label: "Evening Reflection",
    icon: Sunset,
    color: "text-rose-600 dark:text-rose-400",
    bgColor: "bg-rose-500/5 hover:bg-rose-500/10",
    borderColor: "border-rose-500/20",
  },
  night: {
    label: "Night Wind-down",
    icon: Moon,
    color: "text-indigo-500 dark:text-indigo-400",
    bgColor: "bg-indigo-500/5 hover:bg-indigo-500/10",
    borderColor: "border-indigo-500/20",
  },
}

export function MorningIntentions({ onSelect, isVisible }: { onSelect: (prompt: string) => void, isVisible: boolean }) {
  const [intentions, setIntentions] = React.useState<string[]>([])
  const [openLoops, setOpenLoops] = React.useState<any[]>([])
  const [loading, setLoading] = React.useState(true)
  const [timeOfDay, setTimeOfDay] = React.useState<TimeOfDay>("morning")

  React.useEffect(() => {
    setTimeOfDay(getTimeOfDay())
  }, [])

  React.useEffect(() => {
    if (!isVisible) return;

    fetch(`/api/analyze/intentions?time_of_day=${timeOfDay}`)
      .then(res => res.json())
      .then(data => {
        if (data.intentions) {
          setIntentions(data.intentions)
        }
        setLoading(false)
      })
      .catch(() => setLoading(false))

    fetch(`/api/open-loops`)
      .then(res => res.json())
      .then(data => {
        if (data.items) {
          setOpenLoops(data.items)
        }
      })
      .catch(() => {})
  }, [isVisible, timeOfDay])

  if (!isVisible) return null;
  if (!loading && intentions.length === 0) return null;

  const config = TIME_CONFIG[timeOfDay]
  const Icon = config.icon

  return (
    <div className="mb-8 fade-in relative px-2 lg:px-6">
       <div className="flex items-center space-x-2 mb-3">
         <Icon className={`w-5 h-5 ${config.color}`} />
         <h3 className={`text-sm font-semibold uppercase tracking-wider ${config.color}`}>{config.label}</h3>
       </div>

       {loading ? (
         <div className="grid grid-cols-1 md:grid-cols-3 gap-3 animate-pulse">
           {[1, 2, 3].map(i => <div key={i} className="h-24 bg-black/5 dark:bg-white/5 rounded-xl w-full border border-black/5 dark:border-white/5"></div>)}
         </div>
       ) : (
         <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
           {openLoops.length > 0 && (
             <button
               onClick={() => onSelect(`Following up on: ${openLoops[0].text}`)}
               className={`text-left p-4 rounded-xl border border-indigo-500/20 bg-indigo-500/5 hover:bg-indigo-500/10 cursor-pointer transition-all group flex flex-col justify-between`}
             >
               <div className="flex items-center space-x-2 mb-2 text-indigo-500 dark:text-indigo-400">
                 <RotateCw className="w-4 h-4" />
                 <span className="text-xs font-bold uppercase tracking-wider">Unresolved Thread</span>
               </div>
               <p className="text-sm text-gray-800 dark:text-gray-200 leading-snug line-clamp-3 mb-2">"{openLoops[0].text}"</p>
               <span className={`text-xs font-semibold text-indigo-500 dark:text-indigo-400 flex items-center mt-auto opacity-0 group-hover:opacity-100 transition-opacity`}>
                 <Plus className="w-3 h-3 mr-1" /> Use this prompt
               </span>
             </button>
           )}
           {intentions.slice(0, openLoops.length > 0 ? 2 : 3).map((prompt, i) => (
             <button
               key={i}
               onClick={() => onSelect(prompt)}
               className={`text-left p-4 rounded-xl border ${config.borderColor} ${config.bgColor} cursor-pointer transition-all group flex flex-col justify-between`}
             >
               <p className="text-sm text-gray-800 dark:text-gray-200 leading-snug line-clamp-3 mb-2">"{prompt}"</p>
               <span className={`text-xs font-semibold ${config.color} flex items-center mt-auto opacity-0 group-hover:opacity-100 transition-opacity`}>
                 <Plus className="w-3 h-3 mr-1" /> Use this prompt
               </span>
             </button>
           ))}
         </div>
       )}
    </div>
  )
}
