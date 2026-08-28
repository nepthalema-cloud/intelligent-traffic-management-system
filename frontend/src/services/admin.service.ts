import { apiClient } from '@/lib/apiClient'
import type { PaginatedResponse, AuditEvent, AdminUser } from '@/types/api'

// ---------------------------------------------------------------------------
// Audit log  (System Admin only)
// ---------------------------------------------------------------------------

export const auditService = {
  async list(params?: Record<string, string | number>) {
    const { data } = await apiClient.get<PaginatedResponse<AuditEvent>>(
      '/audit/events/',
      { params: { page_size: 20, ...params } }
    )
    return data
  },
}

// ---------------------------------------------------------------------------
// User management  (System Admin only)
// ---------------------------------------------------------------------------

export const userService = {
  async list(params?: Record<string, string | number>) {
    const { data } = await apiClient.get<PaginatedResponse<AdminUser>>(
      '/auth/users/',
      { params: { page_size: 50, ...params } }
    )
    return data
  },

  async assignRole(userId: number, role: string) {
    const { data } = await apiClient.post<{ success: boolean; data: AdminUser }>(
      `/auth/users/${userId}/roles/`,
      { role }
    )
    return data.data
  },

  async removeRole(userId: number, role: string) {
    await apiClient.delete(`/auth/users/${userId}/roles/${encodeURIComponent(role)}/`)
  },

  async setStatus(userId: number, is_active: boolean) {
    const { data } = await apiClient.patch<{ success: boolean; data: AdminUser }>(
      `/auth/users/${userId}/status/`,
      { is_active }
    )
    return data.data
  },
}
