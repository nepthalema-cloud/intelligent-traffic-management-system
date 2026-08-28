interface ErrorMessageProps {
  message?: string
  onRetry?: () => void
}

export function ErrorMessage({ message = 'Something went wrong.', onRetry }: ErrorMessageProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-red-100 bg-red-50 py-8 text-center">
      <p className="text-sm font-medium text-red-600">{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry}
          className="rounded-lg border border-red-200 bg-white px-4 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 transition-colors">
          Try again
        </button>
      )}
    </div>
  )
}
