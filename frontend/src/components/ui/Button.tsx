import React from 'react'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost'
}

export function Button({ variant = 'primary', className = '', children, ...rest }: ButtonProps) {
  const base = 'inline-flex items-center justify-center rounded-2xl px-5 py-3 text-sm font-semibold transition duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60'
  const variants: Record<string,string> = {
    primary: 'bg-sky-500 text-white shadow-[0_18px_50px_rgba(14,165,233,0.18)] hover:bg-sky-400 focus:ring-sky-400/35',
    secondary: 'bg-slate-900 text-slate-100 border border-slate-700 hover:bg-slate-800 focus:ring-sky-400/20',
    ghost: 'bg-transparent text-slate-200 hover:bg-slate-900/70 focus:ring-sky-400/20',
  }
  return (
    <button className={[base, variants[variant], className].join(' ')} {...rest}>
      {children}
    </button>
  )
}

export default Button
