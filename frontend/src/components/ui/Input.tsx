import React from 'react'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  variant?: 'surface' | 'dark'
}

export function Input({ label, className = '', variant = 'surface', ...rest }: InputProps) {
  const variants: Record<string,string> = {
    surface: 'w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-400/15',
    dark: 'w-full rounded-2xl border border-slate-700 bg-slate-950/80 px-4 py-3 text-sm text-slate-100 shadow-inner shadow-slate-950/20 outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-400/20',
  }

  return (
    <div className="w-full">
      {label && <label className="block text-sm font-medium text-slate-300 mb-2">{label}</label>}
      <input className={[variants[variant], className].join(' ')} {...rest} />
    </div>
  )
}

export default Input
