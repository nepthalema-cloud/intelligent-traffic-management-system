import { apiClient, API_ORIGIN } from '@/lib/apiClient'

const VIDEO_ANALYSIS_HISTORY_KEY = 'atms_video_analysis_job_history'

function normalizeMediaUrl(url: string | null | undefined) {
  if (!url || typeof url !== 'string') return url

  const trimmed = url.trim().replace(/\\/g, '/')
  if (!trimmed) return trimmed
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  if (trimmed.startsWith('blob:')) return trimmed

  const withoutLeadingSlash = trimmed.replace(/^\/+/, '')
  const lower = withoutLeadingSlash.toLowerCase()

  if (lower.startsWith('media/')) {
    return `${API_ORIGIN}/${withoutLeadingSlash}`
  }

  if (lower.startsWith('uploads/') || lower.startsWith('static/') || lower.startsWith('tmp_videos/')) {
    return `${API_ORIGIN}/media/${withoutLeadingSlash}`
  }

  return `${API_ORIGIN}/${withoutLeadingSlash}`
}

export function readVideoAnalysisJobHistory(): string[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(VIDEO_ANALYSIS_HISTORY_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((value): value is string => typeof value === 'string').slice(0, 10) : []
  } catch {
    return []
  }
}

export function rememberVideoAnalysisJob(jobId: string | number | null) {
  if (!jobId || typeof window === 'undefined') return
  const safeId = String(jobId)
  const next = [safeId, ...readVideoAnalysisJobHistory().filter((id) => id !== safeId)].slice(0, 10)
  window.localStorage.setItem(VIDEO_ANALYSIS_HISTORY_KEY, JSON.stringify(next))
}

export function getLatestVideoAnalysisJobId(): string | null {
  const history = readVideoAnalysisJobHistory()
  return history[0] ?? null
}

export async function findLatestCompletedVideoAnalysisJob(): Promise<string | null> {
  const history = readVideoAnalysisJobHistory()
  const candidates = Array.from(new Set(history.map(String))).filter(Boolean)

  for (const id of candidates) {
    try {
      const summary = await checkJobStatus(id)
      if (summary?.status === 'done') return String(summary.job_id ?? id)
    } catch {
      // Ignore stale or inaccessible IDs and keep probing the next candidate.
    }
  }

  const probeMaxId = 250
  for (let id = probeMaxId; id >= 1; id -= 1) {
    const candidateId = String(id)
    if (candidates.includes(candidateId)) continue

    try {
      const summary = await checkJobStatus(candidateId)
      if (summary?.status === 'done') return String(summary.job_id ?? candidateId)
    } catch {
      // Ignore missing job IDs while probing recent values.
    }
  }

  return null
}

export async function createAuthenticatedMediaUrl(url: string | null | undefined) {
  if (!url || typeof url !== 'string') return null

  const normalized = normalizeMediaUrl(url)
  if (!normalized || typeof normalized !== 'string') return null
  if (normalized.startsWith('blob:')) return normalized

  try {
    const { data, headers } = await apiClient.get(normalized, { responseType: 'blob' })
    const mimeType = typeof headers['content-type'] === 'string' ? headers['content-type'] : 'application/octet-stream'
    const blob = data instanceof Blob ? data : new Blob([data], { type: mimeType })
    if (!(blob instanceof Blob) || blob.size === 0) return null
    return URL.createObjectURL(blob)
  } catch {
    return null
  }
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

  if (normalized.full_results) {
    normalized.full_results = { ...normalized.full_results }

    if (Array.isArray(normalized.full_results.vehicles)) {
      normalized.full_results.vehicles = normalized.full_results.vehicles.map((vehicle: any) => ({
        ...vehicle,
        thumbnail: normalizeMediaUrl(vehicle.thumbnail),
      }))
    }

    if (Array.isArray(normalized.full_results.snapshots)) {
      normalized.full_results.snapshots = normalized.full_results.snapshots.map((s: any) => ({
        ...s,
        image: normalizeMediaUrl(s.image),
        image_url: normalizeMediaUrl(s.image_url || s.image),
      }))
    }
  }

  return normalized
}

export async function uploadVideo(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await apiClient.post<{ success: boolean; data: { job_id: string } }>('/cameras/upload-analysis/', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  const jobId = data.data.job_id
  rememberVideoAnalysisJob(jobId)
  return jobId
}

export async function checkJobStatus(jobId: string) {
  const { data } = await apiClient.get<{ success: boolean; data: { job_id: number; status: string; result: any } }>(`/cameras/upload-analysis/${jobId}/`)
  return data.data
}

export async function downloadResults(jobId: string) {
  const { data } = await apiClient.get<{ success: boolean; data: { annotated_video?: string; result: any; full_results?: any } }>(`/cameras/upload-analysis/${jobId}/download/`)
  return normalizeDownloadData(data.data)
}

export async function getAnnotatedStreamUrl(jobId: string) {
  try {
    const { data } = await apiClient.get<{ success: boolean; data: { url: string } }>(`/cameras/upload-analysis/${jobId}/stream-token/`)
    return data.data?.url ?? null
  } catch {
    return null
  }
}

export async function discardAnalysis(jobId: string) {
  try {
    const { data } = await apiClient.delete<{ success: boolean; data: any }>(`/cameras/upload-analysis/${jobId}/discard/`)
    return data
  } catch (err) {
    throw err
  }
}
