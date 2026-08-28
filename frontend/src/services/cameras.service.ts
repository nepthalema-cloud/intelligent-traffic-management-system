import { apiClient } from '@/lib/apiClient'
import type {
  PaginatedResponse, Camera, CameraHealth,
  Sensor, SensorHealth, CameraConnectionStatus,
} from '@/types/api'

export const cameraService = {
  async list(params?: Record<string, string | number>) {
    const { data } = await apiClient.get<PaginatedResponse<Camera>>(
      '/cameras/', { params: { page_size: 50, ...params } }
    )
    return data
  },

  async get(id: number) {
    const { data } = await apiClient.get<{ success: boolean; data: Camera }>(
      `/cameras/${id}/`
    )
    return data.data
  },

  async create(payload: Partial<Camera> & { name: string }) {
    const { data } = await apiClient.post<{ success: boolean; data: Camera }>(
      '/cameras/', payload
    )
    return data.data
  },

  async update(id: number, payload: Partial<Camera>) {
    const { data } = await apiClient.patch<{ success: boolean; data: Camera }>(
      `/cameras/${id}/`, payload
    )
    return data.data
  },

  async health(cameraId: number) {
    const { data } = await apiClient.get<{ success: boolean; data: CameraHealth }>(
      `/cameras/${cameraId}/health/`
    )
    return data.data
  },

  /** POST a real connectivity test — returns 7-state result */
  async test(cameraId: number): Promise<CameraConnectionStatus> {
    const { data } = await apiClient.post<{ success: boolean; data: CameraConnectionStatus }>(
      `/cameras/${cameraId}/test/`
    )
    return data.data
  },

  /** Store RTSP credentials — password is NEVER returned in any response */
  async setCredentials(cameraId: number, username: string, password: string) {
    const { data } = await apiClient.put<{ success: boolean; data: { has_credentials: boolean; action: string } }>(
      `/cameras/${cameraId}/credentials/`, { username, password }
    )
    return data.data
  },

  async removeCredentials(cameraId: number) {
    await apiClient.delete(`/cameras/${cameraId}/credentials/`)
  },

  async getCalibration(cameraId: number) {
    const { data } = await apiClient.get<{ success: boolean; data: import('@/types/api').CameraCalibration }>(
      `/cameras/${cameraId}/calibration/`
    )
    return data.data
  },

  async setCalibration(cameraId: number, metersPerPixel: number, notes?: string) {
    const { data } = await apiClient.put<{ success: boolean; data: { action: string } }>(
      `/cameras/${cameraId}/calibration/`,
      { meters_per_pixel: metersPerPixel, notes: notes ?? '' }
    )
    return data.data
  },
}

export const sensorService = {
  async list(params?: Record<string, string | number>) {
    const { data } = await apiClient.get<PaginatedResponse<Sensor>>(
      '/cameras/sensors/', { params: { page_size: 50, ...params } }
    )
    return data
  },

  async health(sensorId: number) {
    const { data } = await apiClient.get<{ success: boolean; data: SensorHealth }>(
      `/cameras/sensors/${sensorId}/health/`
    )
    return data.data
  },
}
