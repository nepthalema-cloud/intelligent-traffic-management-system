/**
 * Zustand auth store.
 *
 * Persists tokens in localStorage via tokenStorage.
 * On mount, if tokens exist, restores the session by fetching /auth/me/.
 * Listens for the 'atms:session-expired' custom event from the API client.
 */

import { create } from 'zustand'
import { authService } from '@/services/auth.service'
import { tokenStorage } from '@/lib/apiClient'
import type { UserProfile, Role } from '@/types/api'

interface AuthState {
  user: UserProfile | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null

  login(username: string, password: string): Promise<void>
  logout(): Promise<void>
  restoreSession(): Promise<void>
  clearError(): void
  hasRole(role: Role): boolean
  hasAnyRole(roles: Role[]): boolean
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  async login(username, password) {
    set({ isLoading: true, error: null })
    try {
      const { access, refresh } = await authService.login(username, password)
      tokenStorage.setTokens(access, refresh)
      const user = await authService.me()
      set({ user, isAuthenticated: true, isLoading: false })
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        'Login failed. Check your credentials.'
      tokenStorage.clear()
      set({ isLoading: false, error: msg, user: null, isAuthenticated: false })
    }
  },

  async logout() {
    const refresh = tokenStorage.getRefresh()
    if (refresh) {
      try {
        await authService.logout(refresh)
      } catch {
        // Ignore logout API errors — always clear local state
      }
    }
    tokenStorage.clear()
    set({ user: null, isAuthenticated: false, error: null })
  },

  async restoreSession() {
    const access = tokenStorage.getAccess()
    if (!access) return

    set({ isLoading: true })
    try {
      const user = await authService.me()
      set({ user, isAuthenticated: true, isLoading: false })
    } catch {
      tokenStorage.clear()
      set({ user: null, isAuthenticated: false, isLoading: false })
    }
  },

  clearError() {
    set({ error: null })
  },

  hasRole(role) {
    return get().user?.roles.includes(role) ?? false
  },

  hasAnyRole(roles) {
    const userRoles = get().user?.roles ?? []
    return roles.some(r => userRoles.includes(r))
  },
}))

// Listen for session-expired events fired by the API client interceptor
window.addEventListener('atms:session-expired', () => {
  useAuthStore.setState({ user: null, isAuthenticated: false })
})
