import { apiClient } from '@/lib/apiClient'
import type { ApiSuccess, SystemStatus, CameraStream } from '@/types/api'

export const systemService = {
  async status(): Promise<SystemStatus> {
    const { data } = await apiClient.get<ApiSuccess<SystemStatus>>('/system/status/')
    return data.data
  },

  async cameraStream(cameraId: number): Promise<CameraStream> {
    const { data } = await apiClient.get<ApiSuccess<CameraStream>>(
      `/cameras/${cameraId}/stream/`
    )
    return data.data
  },
}
