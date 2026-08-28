import React from 'react'

interface PrimaryButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode
}

export function PrimaryButton({ className = '', children, ...rest }: PrimaryButtonProps) {
  return (
    <button
      className={['inline-flex w-full items-center justify-center rounded-[22px] px-6 py-3 text-sm font-semibold text-white transition duration-200 shadow-[0_20px_60px_rgba(33,212,253,0.28)] hover:shadow-[0_24px_80px_rgba(33,212,253,0.32)] focus:outline-none focus:ring-2 focus:ring-cyan-300/40', className].join(' ')}
      style={{ background: 'linear-gradient(135deg, #21D4FD 0%, #2563EB 100%)' }}
      {...rest}
    >
      {children}
    </button>
  )
}
