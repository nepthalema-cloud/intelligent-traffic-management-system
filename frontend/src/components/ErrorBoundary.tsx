import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { error: Error | null; info: ErrorInfo | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, info: null }

  componentDidCatch(error: Error, info: ErrorInfo) {
    this.setState({ error, info })
    console.error('[ErrorBoundary] Caught render error:', error)
    console.error('[ErrorBoundary] Component stack:', info.componentStack)
  }

  render() {
    const { error, info } = this.state
    if (error) {
      return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-8">
          <div className="w-full max-w-2xl rounded-2xl border border-red-200 bg-white shadow-lg overflow-hidden">
            <div className="bg-red-50 border-b border-red-100 px-6 py-4 flex items-center gap-3">
              <svg className="h-5 w-5 text-red-500 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd"/>
              </svg>
              <h1 className="text-base font-semibold text-red-700">React render error — Dashboard failed to mount</h1>
            </div>
            <div className="px-6 py-5 space-y-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Error message</p>
                <pre className="rounded-lg bg-red-50 border border-red-100 px-4 py-3 text-sm text-red-800 font-mono whitespace-pre-wrap break-words">
                  {error.message}
                </pre>
              </div>
              {error.stack && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Stack trace</p>
                  <pre className="rounded-lg bg-slate-50 border border-slate-200 px-4 py-3 text-xs text-slate-600 font-mono whitespace-pre-wrap break-words max-h-48 overflow-y-auto">
                    {error.stack}
                  </pre>
                </div>
              )}
              {info?.componentStack && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Component stack</p>
                  <pre className="rounded-lg bg-slate-50 border border-slate-200 px-4 py-3 text-xs text-slate-600 font-mono whitespace-pre-wrap break-words max-h-48 overflow-y-auto">
                    {info.componentStack}
                  </pre>
                </div>
              )}
              <button
                type="button"
                onClick={() => this.setState({ error: null, info: null })}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
              >
                Try again
              </button>
            </div>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
