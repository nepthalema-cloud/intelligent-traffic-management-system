import React from 'react'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost'
}

export function Button({ variant = 'primary', className = '', children, ...rest }: ButtonProps) {
  const base = 'inline-flex items-center justify-center rounded-2xl px-5 py-3 text-sm font-semibold transition duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60'
  const variants: Record<string,string> = {
    primary: 'bg-blue-600 text-white shadow-sm hover:bg-blue-500 focus:ring-blue-300/40',
    secondary: 'bg-white text-slate-900 border border-slate-200 hover:bg-slate-50 focus:ring-blue-200/20',
    ghost: 'bg-transparent text-slate-700 hover:bg-slate-50 focus:ring-blue-200/10',
  }
  return (
    <button className={[base, variants[variant], className].join(' ')} {...rest}>
      {children}
    </button>
  )
}

export default Button
