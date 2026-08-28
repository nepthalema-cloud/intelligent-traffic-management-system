// ---------------------------------------------------------------------------
// Standard API envelope shapes matching backend common/responses.py
// ---------------------------------------------------------------------------

export interface ApiSuccess<T> {
  success: true
  message: string
  data: T
}

export interface ApiError {
  success: false
  message: string
  errors: unknown
}

export type ApiResponse<T> = ApiSuccess<T> | ApiError

// Paginated list envelope matching backend StandardResultsPagination
export interface PaginatedResponse<T> {
  count: number
  total_pages: number
  current_page: number
  next: string | null
  previous: string | null
  results: T[]
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface LoginResponse {
  access: string
  refresh: string
}

export interface RefreshResponse {
  access: string
  refresh?: string
}

export interface UserProfile {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  is_active: boolean
  date_joined: string
  roles: string[]
}

// ---------------------------------------------------------------------------
// RBAC role constants — must match backend apps/accounts/roles.py
// ---------------------------------------------------------------------------

export const ROLES = {
  SYSTEM_ADMIN: 'System Administrator',
  TRAFFIC_CONTROL_OFFICER: 'Traffic Control Officer',
  TRAFFIC_ANALYST: 'Traffic Analyst',
  LAW_ENFORCEMENT: 'Law Enforcement / Authorized Officer',
  CAMERA_TECHNICIAN: 'Camera/Sensor Technician',
  PAYMENT_FINES_OFFICER: 'Payment/Fines Officer',
  PUBLIC_USER: 'Public User',
} as const

export type Role = (typeof ROLES)[keyof typeof ROLES]

// ---------------------------------------------------------------------------
// Traffic Incidents
// ---------------------------------------------------------------------------

export type IncidentState =
  | 'reported'
  | 'investigating'
  | 'managing'
  | 'resolved'
  | 'closed'

export type IncidentType =
  | 'accident'
  | 'road_closure'
  | 'hazard'
  | 'flooding'
  | 'fire'
  | 'other'

export interface TrafficIncident {
  id: number
  title: string
  description: string
  incident_type: IncidentType
  state: IncidentState
  occurred_at: string
  segment_ids: number[]
  intersection: number | null
  intersection_name: string | null
  created_by: number | null
  created_by_username: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

// ---------------------------------------------------------------------------
// Traffic Events
// ---------------------------------------------------------------------------

export type EventType =
  | 'congestion'
  | 'incident'
  | 'roadwork'
  | 'weather'
  | 'signal_fault'
  | 'other'

export interface TrafficEvent {
  id: number
  event_type: EventType
  description: string
  occurred_at: string
  segment: number | null
  segment_road_name: string | null
  intersection: number | null
  intersection_name: string | null
  created_by: number | null
  created_by_username: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

// ---------------------------------------------------------------------------
// Traffic Measurements
// ---------------------------------------------------------------------------

export interface TrafficMeasurement {
  id: number
  segment: number | null
  segment_name: string | null
  camera: number | null
  camera_name: string | null
  sensor: number | null
  sensor_name: string | null
  measured_at: string
  vehicle_count: number | null
  avg_speed_kmh: number | null
  occupancy_pct: number | null
  created_at: string
}

// ---------------------------------------------------------------------------
// Traffic Signals
// ---------------------------------------------------------------------------

export interface TrafficSignal {
  id: number
  name: string
  intersection: number
  intersection_name: string
  controller_type: string
  controller_identifier: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface SignalPhase {
  id: number
  signal: number
  signal_name: string
  phase_number: number
  name: string
  movement: string
  minimum_green_seconds: number
  maximum_green_seconds: number
  yellow_seconds: number
  all_red_seconds: number
  is_active: boolean
  created_at: string
  updated_at: string
}

// ---------------------------------------------------------------------------
// Cameras & Sensors
// ---------------------------------------------------------------------------

export interface Camera {
  id: number
  name: string
  camera_type: string
  model: string
  description: string
  ip_address: string
  stream_url: string
  segment: number | null
  segment_name: string | null
  intersection: number | null
  intersection_name: string | null
  installed_at: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CameraHealth {
  camera: number
  camera_name: string
  health_status: string
  connectivity_status: string
  last_seen: string | null
  checked_at: string
  detail: Record<string, unknown> | null
}

export interface Sensor {
  id: number
  name: string
  sensor_type: string
  model: string
  description: string
  segment: number | null
  segment_name: string | null
  intersection: number | null
  intersection_name: string | null
  installed_at: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface SensorHealth {
  sensor: number
  sensor_name: string
  health_status: string
  connectivity_status: string
  last_seen: string | null
  checked_at: string
  detail: Record<string, unknown> | null
}

// ---------------------------------------------------------------------------
// Roads
// ---------------------------------------------------------------------------

export interface Road {
  id: number
  name: string
  description: string
  road_type: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Intersection {
  id: number
  name: string
  description: string
  latitude: number | null
  longitude: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface RoadSegment {
  id: number
  road: number
  road_name: string
  name: string
  start_intersection: number | null
  start_intersection_name: string | null
  end_intersection: number | null
  end_intersection_name: string | null
  length_meters: number | null
  speed_limit_kmh: number | null
  lane_count: number
  direction: string
  is_active: boolean
  created_at: string
  updated_at: string
}

// ---------------------------------------------------------------------------
// Audit
// ---------------------------------------------------------------------------

export interface AuditEvent {
  id: string
  timestamp: string
  actor_id: number | null
  actor_username: string | null
  action: string
  target_type: string | null
  target_id: string | null
  ip_address: string | null
  user_agent: string | null
  outcome: 'success' | 'failure' | 'denied'
  detail: Record<string, unknown> | null
}

// ---------------------------------------------------------------------------
// Admin user (returned by GET /auth/users/)
// ---------------------------------------------------------------------------

export interface AdminUser {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  is_active: boolean
  is_staff: boolean
  date_joined: string
  last_login: string | null
  roles: string[]
}

// ---------------------------------------------------------------------------
// Analytics (Phase 4E)
// ---------------------------------------------------------------------------

export interface TrafficFlowSummary {
  id: number
  segment: number | null
  segment_name: string | null
  period_type: 'hourly' | 'daily'
  period_start: string
  period_end: string
  total_vehicle_count: number | null
  avg_speed_kmh: number | null
  avg_occupancy_pct: number | null
  sample_count: number
  created_at: string
}

export interface IncidentReportSummary {
  id: number
  segment: number | null
  segment_name: string | null
  period_type: string
  period_start: string
  period_end: string
  total_incidents: number
  by_type: Record<string, number>
  by_state: Record<string, number>
  created_at: string
}

export interface ViolationSummary {
  id: number
  segment: number | null
  segment_name: string | null
  period_type: string
  period_start: string
  period_end: string
  total_violations: number
  by_type: Record<string, number>
  created_at: string
}

// ---------------------------------------------------------------------------
// System Status (Phase 5)
// ---------------------------------------------------------------------------

export type SystemMode = 'live' | 'degraded' | 'demo' | 'offline'

export interface SystemStatus {
  mode: SystemMode
  cameras_total: number
  cameras_connected: number
  ai_processing_active: boolean
  last_measurement_at: string | null
  last_measurement_source: string | null
  server_time: string
}

export interface CameraStream {
  camera_id: number
  camera_name: string
  available: boolean
  hls_url: string | null
  is_test_source: boolean
  source_label: string
  reason?: string
}

// ---------------------------------------------------------------------------
// Camera connection status (Phase 5 — 7-state onboarding pipeline)
// ---------------------------------------------------------------------------

export type CameraState =
  | 'saved'
  | 'rtsp_unreachable'
  | 'auth_failed'
  | 'stream_connected'
  | 'hls_available'
  | 'ai_processing'
  | 'live'

export interface CameraConnectionStatus {
  state: CameraState
  state_label: string
  colour: 'slate' | 'red' | 'amber' | 'blue' | 'cyan' | 'green'
  detail: string
  checked_at: string
  hls_url?: string | null
}

// Camera onboarding form payload
export interface CameraOnboardPayload {
  name: string
  camera_type: string
  model?: string
  description?: string
  ip_address?: string
  rtsp_port?: number
  rtsp_path?: string
  hls_path?: string
  stream_url?: string
  segment?: number | null
  intersection?: number | null
  rtsp_username?: string
  rtsp_password?: string
}

// ---------------------------------------------------------------------------
// Camera calibration (Phase 5 — speed estimation)
// ---------------------------------------------------------------------------

export interface CameraCalibration {
  camera_id: number
  meters_per_pixel: number | null
  calibrated_at: string | null
  is_valid: boolean
  notes: string
}

// Extended SystemStatus with per-camera breakdown
export interface CameraSystemEntry {
  camera_id: number
  camera_name: string
  mode: CameraState | 'hls_available' | 'stream_connected' | 'saved' | 'offline'
  source_type: 'cctv' | 'test_video' | 'live_webcam'
  health_status: string
  connectivity_status: string
  ai_processing_active: boolean
  hls_available: boolean
  last_seen: string | null
}
