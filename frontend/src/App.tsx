import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { ProtectedRoute } from '@/router/ProtectedRoute'
import { ThemeProvider } from '@/components/ui/ThemeProvider'
import { AppLayout } from '@/components/layout/AppLayout'
import { LoginPage }           from '@/pages/LoginPage'
import { UnauthorizedPage }    from '@/pages/UnauthorizedPage'
import { DashboardPage }       from '@/pages/DashboardPage'
import { IncidentsPage }       from '@/pages/IncidentsPage'
import { EventsPage }          from '@/pages/EventsPage'
import { MeasurementsPage }    from '@/pages/MeasurementsPage'
import { SignalsPage }         from '@/pages/SignalsPage'
import { CamerasPage }         from '@/pages/CamerasPage'
import { RoadsPage }           from '@/pages/RoadsPage'
import { AuditLogPage }        from '@/pages/AuditLogPage'
import { UserManagementPage }  from '@/pages/UserManagementPage'
import { AnalyticsPage }       from '@/pages/AnalyticsPage'
import { VideoAnalysisPage }   from '@/pages/VideoAnalysisPage'
import { ProfilePage }         from '@/pages/ProfilePage'
import { SettingsPage }        from '@/pages/SettingsPage'
import { HomePage }            from '@/pages/HomePage'
import { ROLES } from '@/types/api'

// Exact role sets matching backend views.py RBAC
// ──────────────────────────────────────────────

// Signals: _READ_ROLES = Admin, TCO, Analyst  (Camera Technician also has R — see backend)
const SIGNAL_READ_ROLES = [
  ROLES.SYSTEM_ADMIN,
  ROLES.TRAFFIC_CONTROL_OFFICER,
  ROLES.TRAFFIC_ANALYST,
  ROLES.CAMERA_TECHNICIAN, // backend: R access confirmed
]

// Measurements: Admin, TCO, Analyst, Camera Technician
const MEASUREMENT_READ_ROLES = [
  ROLES.SYSTEM_ADMIN,
  ROLES.TRAFFIC_CONTROL_OFFICER,
  ROLES.TRAFFIC_ANALYST,
  ROLES.CAMERA_TECHNICIAN,
]

// Events: Admin, TCO, Analyst, Law Enforcement
const EVENT_READ_ROLES = [
  ROLES.SYSTEM_ADMIN,
  ROLES.TRAFFIC_CONTROL_OFFICER,
  ROLES.TRAFFIC_ANALYST,
  ROLES.LAW_ENFORCEMENT,
]

// Incidents: Admin, TCO, Analyst, Law Enforcement
const INCIDENT_READ_ROLES = [
  ROLES.SYSTEM_ADMIN,
  ROLES.TRAFFIC_CONTROL_OFFICER,
  ROLES.TRAFFIC_ANALYST,
  ROLES.LAW_ENFORCEMENT,
]

// Roads: Admin, TCO, Analyst
const ROADS_READ_ROLES = [
  ROLES.SYSTEM_ADMIN,
  ROLES.TRAFFIC_CONTROL_OFFICER,
  ROLES.TRAFFIC_ANALYST,
]

// Cameras: Admin, TCO, Camera Technician
const CAMERA_ROLES = [
  ROLES.SYSTEM_ADMIN,
  ROLES.CAMERA_TECHNICIAN,
  ROLES.TRAFFIC_CONTROL_OFFICER,
]

// Analytics: Admin, TCO, Analyst, Law Enforcement, Pay/Fines (superset of all 3 tab permissions)
const ANALYTICS_ROLES = [
  ROLES.SYSTEM_ADMIN,
  ROLES.TRAFFIC_CONTROL_OFFICER,
  ROLES.TRAFFIC_ANALYST,
  ROLES.LAW_ENFORCEMENT,
  ROLES.PAYMENT_FINES_OFFICER,
]

// Admin: System Admin only
const ADMIN_ROLES = [ROLES.SYSTEM_ADMIN]

export default function App() {
  const restoreSession = useAuthStore(s => s.restoreSession)

  useEffect(() => {
    void restoreSession()
  }, [restoreSession])

  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
        {/* Home (public) */}
        <Route path="/" element={<HomePage />} />

        {/* Public auth pages */}
        <Route path="/login"        element={<LoginPage />} />
        <Route path="/unauthorized" element={<UnauthorizedPage />} />

        {/* Protected — all authenticated users see the layout */}
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            {/* Dashboard — all authenticated roles */}
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/settings" element={<SettingsPage />} />

            {/* Incidents */}
            <Route element={<ProtectedRoute roles={INCIDENT_READ_ROLES} />}>
              <Route path="/incidents" element={<IncidentsPage />} />
            </Route>

            {/* Events */}
            <Route element={<ProtectedRoute roles={EVENT_READ_ROLES} />}>
              <Route path="/events" element={<EventsPage />} />
            </Route>

            {/* Measurements */}
            <Route element={<ProtectedRoute roles={MEASUREMENT_READ_ROLES} />}>
              <Route path="/measurements" element={<MeasurementsPage />} />
            </Route>

            {/* Signals */}
            <Route element={<ProtectedRoute roles={SIGNAL_READ_ROLES} />}>
              <Route path="/signals" element={<SignalsPage />} />
            </Route>

            {/* Roads */}
            <Route element={<ProtectedRoute roles={ROADS_READ_ROLES} />}>
              <Route path="/roads" element={<RoadsPage />} />
            </Route>

            {/* Cameras & Sensors */}
            <Route element={<ProtectedRoute roles={CAMERA_ROLES} />}>
              <Route path="/cameras" element={<CamerasPage />} />
            </Route>

            {/* Analytics */}
            <Route element={<ProtectedRoute roles={ANALYTICS_ROLES} />}>
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/video-analysis" element={<VideoAnalysisPage />} />
            </Route>

            {/* Administration */}
            <Route element={<ProtectedRoute roles={ADMIN_ROLES} />}>
              <Route path="/admin/users" element={<UserManagementPage />} />
              <Route path="/admin/audit" element={<AuditLogPage />} />
            </Route>
          </Route>
        </Route>

        {/* Catch-all for unknown paths */}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  </ThemeProvider>
  )
}
