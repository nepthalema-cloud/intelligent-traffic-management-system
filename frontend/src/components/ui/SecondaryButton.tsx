import React from 'react'

interface SecondaryButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode
}

export function SecondaryButton({ className = '', children, ...rest }: SecondaryButtonProps) {
  return (
    <button
      className={['inline-flex w-full items-center justify-center rounded-[22px] border border-slate-700 bg-slate-950/70 px-6 py-3 text-sm font-semibold text-slate-100 transition duration-200 hover:bg-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-400/20', className].join(' ')}
      {...rest}
    >
      {children}
    </button>
  )
}
