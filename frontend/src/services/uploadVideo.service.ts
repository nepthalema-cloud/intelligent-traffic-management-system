import { apiClient, API_ORIGIN } from '@/lib/apiClient'

function normalizeMediaUrl(url: string | null | undefined) {
  if (!url) return url
  const trimmed = url.trim()
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  if (trimmed.startsWith('/')) return `${API_ORIGIN}${trimmed}`
  return `${API_ORIGIN}/${trimmed}`
}

function normalizeDownloadData(data: any) {
  if (!data) return data
  const normalized = { ...data }
  normalized.annotated_video = normalizeMediaUrl(data.annotated_video)
  if (normalized.result) {
    normalized.result = { ...normalized.result }
    normalized.result.csv_url = normalizeMediaUrl(normalized.result.csv_url)
    normalized.result.pdf_url = normalizeMediaUrl(normalized.result.pdf_url)
  }
  if (normalized.full_results?.snapshots) {
    normalized.full_results = { ...normalized.full_results }
    normalized.full_results.snapshots = normalized.full_results.snapshots.map((s: any) => ({
      ...s,
      image_url: normalizeMediaUrl(s.image_url || s.image),
    }))
  }
  return normalized
}

export async function uploadVideo(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await apiClient.post<{ success: boolean; data: { job_id: string } }>('/cameras/upload-analysis/', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data.data.job_id
}

export async function checkJobStatus(jobId: string) {
  const { data } = await apiClient.get<{ success: boolean; data: { job_id: number; status: string; result: any } }>(`/cameras/upload-analysis/${jobId}/`)
  return data.data
}

export async function downloadResults(jobId: string) {
  const { data } = await apiClient.get<{ success: boolean; data: { annotated_video?: string; result: any; full_results?: any } }>(`/cameras/upload-analysis/${jobId}/download/`)
  return normalizeDownloadData(data.data)
}
