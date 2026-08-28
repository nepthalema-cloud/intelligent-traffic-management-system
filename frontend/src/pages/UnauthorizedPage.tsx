import { Link } from 'react-router-dom'

export function UnauthorizedPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 text-center px-4">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-red-100">
        <svg className="h-7 w-7 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
      </div>
      <h1 className="text-xl font-bold text-slate-900 mb-2">Access Denied</h1>
      <p className="text-slate-500 mb-6 text-sm max-w-sm">
        Your role does not have permission to view this page. Contact your system administrator.
      </p>
      <Link to="/dashboard"
        className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 transition-colors shadow-sm">
        Go to Dashboard
      </Link>
    </div>
  )
}
