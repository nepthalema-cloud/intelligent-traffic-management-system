import React from 'react'

interface TextInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
}

export function TextInput({ label, className = '', ...rest }: TextInputProps) {
  return (
    <label className="block w-full text-sm text-slate-200">
      {label && <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.32em] text-slate-400">{label}</span>}
      <input
        className={[
          'w-full rounded-[18px] border border-slate-800 bg-slate-950/90 px-4 py-3 text-sm text-slate-100 shadow-[inset_0_1px_2px_rgba(255,255,255,0.05)] outline-none transition duration-200 focus:border-cyan-300 focus:ring-2 focus:ring-cyan-300/15',
          className,
        ].join(' ')}
        {...rest}
      />
    </label>
  )
}
