import React, { useState } from 'react'

interface PasswordInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
}

export function PasswordInput({ label, className = '', ...rest }: PasswordInputProps) {
  const [revealed, setRevealed] = useState(false)

  return (
    <label className="block w-full text-sm text-slate-200">
      {label && <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.32em] text-slate-400">{label}</span>}
      <div className="relative">
        <input
          type={revealed ? 'text' : 'password'}
          className={[
            'w-full rounded-[18px] border border-slate-800 bg-slate-950/90 px-4 py-3 pr-20 text-sm text-slate-100 shadow-[inset_0_1px_2px_rgba(255,255,255,0.05)] outline-none transition duration-200 focus:border-cyan-300 focus:ring-2 focus:ring-cyan-300/15',
            className,
          ].join(' ')}
          {...rest}
        />
        <button
          type="button"
          onClick={() => setRevealed(v => !v)}
          className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-300 transition hover:bg-slate-900/70"
        >
          {revealed ? 'Hide' : 'Show'}
        </button>
      </div>
    </label>
  )
}
