import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import type { Role } from '@/types/api'

interface ProtectedRouteProps {
  /** If provided, at least one of these roles is required */
  roles?: Role[]
}

/**
 * Wraps routes that require authentication (and optionally a specific role).
 * Redirects to /login with the original path preserved in state.
 */
export function ProtectedRoute({ roles }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, hasAnyRole } = useAuthStore()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50">
        <div className="h-9 w-9 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (roles && roles.length > 0 && !hasAnyRole(roles)) {
    return <Navigate to="/unauthorized" replace />
  }

  return <Outlet />
}
