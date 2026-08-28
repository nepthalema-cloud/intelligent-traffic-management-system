import { apiClient } from '@/lib/apiClient'
import type { PaginatedResponse, Road, Intersection, RoadSegment } from '@/types/api'

export const roadsService = {
  async listRoads(params?: Record<string, string | number>) {
    const { data } = await apiClient.get<PaginatedResponse<Road>>(
      '/roads/',
      { params: { page_size: 100, ...params } }
    )
    return data
  },

  async listIntersections(params?: Record<string, string | number>) {
    const { data } = await apiClient.get<PaginatedResponse<Intersection>>(
      '/roads/intersections/',
      { params: { page_size: 100, ...params } }
    )
    return data
  },

  async listSegments(params?: Record<string, string | number>) {
    const { data } = await apiClient.get<PaginatedResponse<RoadSegment>>(
      '/roads/segments/',
      { params: { page_size: 100, ...params } }
    )
    return data
  },
}
