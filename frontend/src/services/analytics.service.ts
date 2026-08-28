import { apiClient } from '@/lib/apiClient'
import type { PaginatedResponse, TrafficFlowSummary, IncidentReportSummary, ViolationSummary } from '@/types/api'

export const analyticsService = {
  async listFlow(params?: Record<string, string | number>) {
    const { data } = await apiClient.get<PaginatedResponse<TrafficFlowSummary>>(
      '/analytics/flow/', { params: { page_size: 20, ...params } }
    )
    return data
  },

  async listIncidents(params?: Record<string, string | number>) {
    const { data } = await apiClient.get<PaginatedResponse<IncidentReportSummary>>(
      '/analytics/incidents/', { params: { page_size: 20, ...params } }
    )
    return data
  },

  async listViolations(params?: Record<string, string | number>) {
    const { data } = await apiClient.get<PaginatedResponse<ViolationSummary>>(
      '/analytics/violations/', { params: { page_size: 20, ...params } }
    )
    return data
  },
}
