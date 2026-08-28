import { apiClient } from '@/lib/apiClient'
import type {
  PaginatedResponse,
  TrafficIncident,
  TrafficEvent,
  TrafficMeasurement,
  TrafficSignal,
  SignalPhase,
} from '@/types/api'

// ---------------------------------------------------------------------------
// Traffic Incidents
// ---------------------------------------------------------------------------

export const incidentService = {
  async list(params?: Record<string, string | number>) {
    const { data } = await apiClient.get<PaginatedResponse<TrafficIncident>>(
      '/traffic/incidents/',
      { params: { page_size: 20, ...params } }
    )
    return data
  },

  async get(id: number) {
    const { data } = await apiClient.get<{ success: boolean; data: TrafficIncident }>(
      `/traffic/incidents/${id}/`
    )
    return data.data
  },

  async create(payload: {
    title: string
    description: string
    incident_type: string
    occurred_at: string
    segment_ids?: number[]
    intersection?: number | null
  }) {
    const { data } = await apiClient.post<{ success: boolean; data: TrafficIncident }>(
      '/traffic/incidents/',
      payload
    )
    return data.data
  },

  async update(id: number, payload: Partial<{
    title: string
    description: string
    incident_type: string
    occurred_at: string
    segment_ids: number[]
    intersection: number | null
  }>) {
    const { data } = await apiClient.patch<{ success: boolean; data: TrafficIncident }>(
      `/traffic/incidents/${id}/`,
      payload
    )
    return data.data
  },

  async transition(id: number, state: string) {
    const { data } = await apiClient.patch<{ success: boolean; data: TrafficIncident }>(
      `/traffic/incidents/${id}/state/`,
      { state }
    )
    return data.data
  },
}

// ---------------------------------------------------------------------------
// Traffic Events
// ---------------------------------------------------------------------------

export const eventService = {
  async list(params?: Record<string, string | number>) {
    const { data } = await apiClient.get<PaginatedResponse<TrafficEvent>>(
      '/traffic/events/',
      { params: { page_size: 20, ...params } }
    )
    return data
  },

  async get(id: number) {
    const { data } = await apiClient.get<{ success: boolean; data: TrafficEvent }>(
      `/traffic/events/${id}/`
    )
    return data.data
  },

  async create(payload: {
    event_type: string
    description: string
    occurred_at: string
    intersection?: number | null
    segment?: number | null
  }) {
    const { data } = await apiClient.post<{ success: boolean; data: TrafficEvent }>(
      '/traffic/events/',
      payload
    )
    return data.data
  },

  async setActive(id: number, is_active: boolean) {
    const { data } = await apiClient.patch<{ success: boolean; data: TrafficEvent }>(
      `/traffic/events/${id}/status/`,
      { is_active }
    )
    return data.data
  },

  async update(id: number, payload: Partial<{ event_type: string; description: string }>) {
    const { data } = await apiClient.patch<{ success: boolean; data: TrafficEvent }>(
      `/traffic/events/${id}/`,
      payload
    )
    return data.data
  },
}

// ---------------------------------------------------------------------------
// Traffic Measurements
// ---------------------------------------------------------------------------

export const measurementService = {
  async list(params?: Record<string, string | number>) {
    const { data } = await apiClient.get<PaginatedResponse<TrafficMeasurement>>(
      '/traffic/measurements/',
      { params: { page_size: 20, ...params } }
    )
    return data
  },
}

// ---------------------------------------------------------------------------
// Traffic Signals
// ---------------------------------------------------------------------------

export const signalService = {
  async list(params?: Record<string, string | number>) {
    const { data } = await apiClient.get<PaginatedResponse<TrafficSignal>>(
      '/traffic/signals/',
      { params: { page_size: 50, ...params } }
    )
    return data
  },

  async get(id: number) {
    const { data } = await apiClient.get<{ success: boolean; data: TrafficSignal }>(
      `/traffic/signals/${id}/`
    )
    return data.data
  },

  async phases(signalId: number) {
    const { data } = await apiClient.get<PaginatedResponse<SignalPhase>>(
      `/traffic/signals/${signalId}/phases/`,
      { params: { page_size: 50 } }
    )
    return data
  },
}
