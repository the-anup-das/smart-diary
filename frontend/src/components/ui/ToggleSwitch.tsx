"use client"
import * as React from "react"

export function ToggleSwitch({ checked, onChange, label, description }: any) {
  return (
    <div className="flex items-center justify-between py-3">
      <div>
        <p className="font-medium text-sm text-gray-900 dark:text-gray-100">{label}</p>
        {description && <p className="text-xs text-gray-500 line-clamp-2 max-w-sm">{description}</p>}
      </div>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary/50 ${checked ? 'bg-primary' : 'bg-gray-200 dark:bg-gray-700'}`}
      >
        <span
          className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${checked ? 'translate-x-5' : 'translate-x-0'}`}
        />
      </button>
    </div>
  )
}
