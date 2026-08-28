# TrafficOps Frontend

React + TypeScript + Vite frontend for the AI-Powered Smart Traffic Management System.

## Prerequisites

- Node.js 18+
- The Django backend running on `http://localhost:8000`

## Quick start

```bash
# 1. Copy environment config
cp .env.example .env

# 2. Install dependencies
npm install --legacy-peer-deps

# 3. Start dev server (opens at http://localhost:5173)
npm run dev
```

## Configuration

Edit `.env` to point at your backend:

```
VITE_API_BASE_URL=http://localhost:8000
VITE_API_TIMEOUT=30000
```

The backend's CORS config already whitelists `http://localhost:5173`.

## Build

```bash
npm run build       # production build → dist/
npm run preview     # preview production build locally
```

## Type-check

```bash
npx tsc --noEmit
```

## Architecture

```
src/
  components/
    dashboard/   # ActiveIncidents, RecentEvents, MeasurementsFeed,
                 # SignalStatusList, CameraHealthSummary
    layout/      # AppLayout, Sidebar, TopBar
    map/         # TrafficMap (Leaflet/OpenStreetMap)
    ui/          # StatCard, StatusBadge, LoadingSpinner,
                 # EmptyState, ErrorMessage, SectionHeader
  lib/
    apiClient.ts # Axios instance + JWT Bearer + refresh interceptor
  pages/         # DashboardPage, IncidentsPage, EventsPage,
                 # MeasurementsPage, SignalsPage, CamerasPage,
                 # RoadsPage, LoginPage, UnauthorizedPage
  router/
    ProtectedRoute.tsx
  services/      # auth, traffic, cameras, roads service modules
  store/
    authStore.ts  # Zustand auth state
  types/
    api.ts        # All TypeScript types matching backend serializers
  utils/
    time.ts       # Relative time formatting
```

## Role-based access

| Role | Dashboard | Incidents | Events | Measurements | Signals | Cameras | Roads |
|---|---|---|---|---|---|---|---|
| System Administrator | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Traffic Control Officer | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Traffic Analyst | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ |
| Law Enforcement | ✓ | ✓ | ✓ | — | — | — | — |
| Camera/Sensor Technician | ✓ | — | — | — | — | ✓ | — |
| Payment/Fines Officer | ✓ only | — | — | — | — | — | — |

## Map

Uses OpenStreetMap tiles (CartoDB dark style) via Leaflet + react-leaflet.
No API key required. Intersection markers are shown when lat/lng is present
in the backend Intersection records. Active incidents and events linked to
intersections with coordinates are shown as coloured markers.
