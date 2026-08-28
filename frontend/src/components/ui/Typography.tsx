import React from 'react'

export function H1({ children }: { children: React.ReactNode }) {
  return <h1 className="text-3xl lg:text-4xl font-extrabold text-slate-900">{children}</h1>
}

export function H2({ children }: { children: React.ReactNode }) {
  return <h2 className="text-2xl font-semibold text-slate-900">{children}</h2>
}

export function Body({ children }: { children: React.ReactNode }) {
  return <p className="text-base text-slate-700">{children}</p>
}

export default { H1, H2, Body }
