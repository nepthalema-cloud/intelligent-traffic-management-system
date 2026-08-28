import React from 'react'

export function Section({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <section className={[ 'rounded-xl border border-slate-100 bg-white p-4', className ].join(' ')}>{children}</section>
}

export default Section
