interface LoadingSpinnerProps {
  label?: string
  size?: 'sm' | 'md'
}

export function LoadingSpinner({ label = 'Loading…', size = 'md' }: LoadingSpinnerProps) {
  const sz = size === 'sm' ? 'h-4 w-4 border-2' : 'h-7 w-7 border-[3px]'
  return (
    <div className="flex items-center justify-center gap-2.5 py-8 text-slate-400">
      <div className={`animate-spin rounded-full border-slate-200 border-t-blue-500 ${sz}`} />
      <span className="text-sm">{label}</span>
    </div>
  )
}
