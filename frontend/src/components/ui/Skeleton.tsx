// React import not required with the new JSX runtime

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={[ 'animate-pulse bg-slate-100 rounded-md', className ].join(' ')} />
}

export default Skeleton
