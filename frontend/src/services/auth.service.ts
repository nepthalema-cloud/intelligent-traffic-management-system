import { apiClient } from '@/lib/apiClient'
import type { ApiSuccess, LoginResponse, RefreshResponse, UserProfile } from '@/types/api'

export const authService = {
  async login(username: string, password: string) {
    const { data } = await apiClient.post<ApiSuccess<LoginResponse>>(
      '/auth/login/',
      { username, password }
    )
    return data.data
  },

  async refresh(refresh: string) {
    const { data } = await apiClient.post<ApiSuccess<RefreshResponse>>(
      '/auth/refresh/',
      { refresh }
    )
    return data.data
  },

  async logout(refresh: string) {
    await apiClient.post('/auth/logout/', { refresh })
  },

  async me() {
    const { data } = await apiClient.get<ApiSuccess<UserProfile>>('/auth/me/')
    return data.data
  },
}
