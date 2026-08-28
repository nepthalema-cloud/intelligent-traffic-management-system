/**
 * TrafficMap — interactive OpenStreetMap/Leaflet map.
 *
 * Layers:
 *  🔵 Intersections        (cyan)
 *  🔴 Active Incidents     (red)   — intersection-linked
 *  🟡 Traffic Events       (amber) — intersection-linked
 *  📷 Cameras              (purple)
 *  📡 Sensors              (teal)
 *  🚦 Traffic Signals      (green)
 *
 * Map tiles: CartoDB dark matter (OpenStreetMap data, no API key)
 */

import { useEffect, useState } from 'react'
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import { roadsService } from '@/services/roads.service'
import { incidentService, eventService, signalService } from '@/services/traffic.service'
import { cameraService, sensorService } from '@/services/cameras.service'
import type {
  Intersection, TrafficIncident, TrafficEvent,
  TrafficSignal, Camera, Sensor, RoadSegment,
} from '@/types/api'
import { formatRelative } from '@/utils/time'

// Fix Leaflet default marker icon paths broken by Vite bundling
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl:       'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl:     'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

function makeIcon(colour: string, symbol: string) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 40" width="28" height="40">
    <path fill="${colour}" stroke="rgba(255,255,255,0.7)" stroke-width="1.2"
      d="M14 0C6.268 0 0 6.268 0 14c0 10.5 14 26 14 26S28 24.5 28 14C28 6.268 21.732 0 14 0z"/>
    <text x="14" y="19" text-anchor="middle" font-size="12" font-family="sans-serif">${symbol}</text>
  </svg>`
  return L.divIcon({ html: svg, className: '', iconSize: [28, 40], iconAnchor: [14, 40], popupAnchor: [0, -40] })
}

const icons = {
  intersection: makeIcon('#2563eb', '✕'),   // blue-600
  incident:     makeIcon('#dc2626', '!'),    // red-600
  event:        makeIcon('#d97706', '⚡'),   // amber-600
  camera:       makeIcon('#7c3aed', '📷'),  // violet-700
  sensor:       makeIcon('#0d9488', '📡'),  // teal-600
  signal:       makeIcon('#16a34a', '🚦'),  // green-600
}

function FitBounds({ positions }: { positions: [number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (positions.length === 0) return
    map.fitBounds(L.latLngBounds(positions), { padding: [40, 40], maxZoom: 15 })
  }, [map, positions])
  return null
}

const INCIDENT_TYPE_LABEL: Record<string, string> = {
  accident: '💥 Accident', road_closure: '🚧 Road Closure',
  hazard: '⚠️ Hazard', flooding: '🌊 Flooding', fire: '🔥 Fire', other: '📌 Other',
}

interface TrafficMapProps {
  /** Set true to compact the legend (used in dashboard) */
  compact?: boolean
}

export function TrafficMap({ compact = false }: TrafficMapProps) {
  const [intersections, setIntersections] = useState<Intersection[]>([])
  const [incidents,     setIncidents]     = useState<TrafficIncident[]>([])
  const [events,        setEvents]        = useState<TrafficEvent[]>([])
  const [signals,       setSignals]       = useState<TrafficSignal[]>([])
  const [cameras,       setCameras]       = useState<Camera[]>([])
  const [sensors,       setSensors]       = useState<Sensor[]>([])
  const [segments,      setSegments]      = useState<RoadSegment[]>([])
  const [loading,       setLoading]       = useState(true)

  useEffect(() => {
    async function load() {
      setLoading(true)
      const results = await Promise.allSettled([
        roadsService.listIntersections({ page_size: 100 }),
        incidentService.list({ page_size: 50, is_active: 1 }),
        eventService.list({ page_size: 50 }),
        signalService.list({ page_size: 100 }),
        cameraService.list({ page_size: 100 }),
        sensorService.list({ page_size: 100 }),
        roadsService.listSegments({ page_size: 100 }),
      ])
      if (results[0].status === 'fulfilled') setIntersections(results[0].value.results)
      if (results[1].status === 'fulfilled')
        setIncidents(results[1].value.results.filter(i => i.state !== 'closed'))
      if (results[2].status === 'fulfilled')
        setEvents(results[2].value.results.filter(e => e.is_active))
      if (results[3].status === 'fulfilled') setSignals(results[3].value.results)
      if (results[4].status === 'fulfilled') setCameras(results[4].value.results)
      if (results[5].status === 'fulfilled') setSensors(results[5].value.results)
      if (results[6].status === 'fulfilled') setSegments(results[6].value.results)
      setLoading(false)
    }
    void load()
  }, [])

  // Helper: coords from intersection id
  const intCoords = (id: number | null): [number, number] | null => {
    if (id === null) return null
    const i = intersections.find(x => x.id === id)
    return (i?.latitude != null && i?.longitude != null) ? [i.latitude, i.longitude] : null
  }

  /**
   * Derive midpoint from a segment's start+end intersection coordinates.
   * Returns null if either endpoint lacks coordinates.
   * This avoids placing markers at wrong positions while still showing
   * segment-linked devices that would otherwise be invisible on the map.
   */
  const segmentMidpoint = (segmentId: number | null): [number, number] | null => {
    if (segmentId === null) return null
    const seg = segments.find(s => s.id === segmentId)
    if (!seg) return null
    const start = intCoords(seg.start_intersection)
    const end   = intCoords(seg.end_intersection)
    if (!start || !end) return null
    return [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2]
  }

  // Resolve marker position: try intersection first, then segment midpoint
  const deviceCoords = (
    intersectionId: number | null,
    segmentId: number | null,
  ): [number, number] | null => {
    return intCoords(intersectionId) ?? segmentMidpoint(segmentId)
  }

  const geoIntersections = intersections.filter(i => i.latitude != null && i.longitude != null)
  const allPositions: [number, number][] = geoIntersections.map(i => [i.latitude!, i.longitude!])
  const hasMapData = geoIntersections.length > 0 || incidents.length > 0 || events.length > 0

  return (
    <div className="relative h-full w-full rounded-xl overflow-hidden border border-slate-200 shadow-sm">
      {loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/80">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-blue-500" />
            Loading map…
          </div>
        </div>
      )}

      {/* No-data overlay — shown when map loaded but no roads/incidents registered yet */}
      {!loading && !hasMapData && (
        <div className="absolute inset-x-0 bottom-0 z-10 flex items-center justify-center pb-4">
          <div className="rounded-full bg-black/50 backdrop-blur-sm px-4 py-1.5">
            <p className="text-xs text-white/80">
              No road network data registered yet — map centered on Gondar, Ethiopia
            </p>
          </div>
        </div>
      )}

      <MapContainer center={[12.6030, 37.4521]} zoom={13} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          maxZoom={20}
        />
        {allPositions.length > 0 && <FitBounds positions={allPositions} />}

        {/* Intersection markers */}
        {geoIntersections.map(i => (
          <Marker key={`int-${i.id}`} position={[i.latitude!, i.longitude!]} icon={icons.intersection}>
            <Popup>
              <p className="font-semibold">{i.name}</p>
              {i.description && <p className="text-xs text-gray-600 mt-1">{i.description}</p>}
              <p className="text-xs text-gray-500 mt-1 font-mono">
                {i.latitude?.toFixed(5)}, {i.longitude?.toFixed(5)}
              </p>
            </Popup>
          </Marker>
        ))}

        {/* Active incident markers */}
        {incidents.map(inc => {
          const pos = intCoords(inc.intersection)
          if (!pos) return null
          return (
            <Marker key={`inc-${inc.id}`} position={pos} icon={icons.incident}>
              <Popup>
                <p className="font-semibold text-red-700">{inc.title}</p>
                <p className="text-xs mt-1">{INCIDENT_TYPE_LABEL[inc.incident_type]}</p>
                <p className="text-xs text-gray-600 mt-1">State: <strong>{inc.state}</strong></p>
                <p className="text-xs text-gray-500">{formatRelative(inc.occurred_at)}</p>
              </Popup>
            </Marker>
          )
        })}

        {/* Active event markers */}
        {events.map(ev => {
          const pos = intCoords(ev.intersection)
          if (!pos) return null
          return (
            <Marker key={`ev-${ev.id}`} position={pos} icon={icons.event}>
              <Popup>
                <p className="font-semibold text-amber-700 capitalize">{ev.event_type.replace('_', ' ')}</p>
                <p className="text-xs mt-1">{ev.description}</p>
                <p className="text-xs text-gray-500 mt-1">{formatRelative(ev.occurred_at)}</p>
              </Popup>
            </Marker>
          )
        })}

        {/* Traffic signal markers */}
        {signals.map(sig => {
          const pos = intCoords(sig.intersection)
          if (!pos) return null
          return (
            <Marker key={`sig-${sig.id}`} position={pos} icon={icons.signal}>
              <Popup>
                <p className="font-semibold text-green-700">{sig.name}</p>
                <p className="text-xs text-gray-600 mt-1">{sig.intersection_name}</p>
                <p className="text-xs mt-1">
                  Type: {sig.controller_type || 'N/A'} &nbsp;|&nbsp;
                  {sig.is_active ? '🟢 Active' : '⚫ Inactive'}
                </p>
              </Popup>
            </Marker>
          )
        })}

        {/* Camera markers (intersection or segment midpoint) */}
        {cameras.map(cam => {
          const pos = deviceCoords(cam.intersection, cam.segment)
          if (!pos) return null
          return (
            <Marker key={`cam-${cam.id}`} position={pos} icon={icons.camera}>
              <Popup>
                <p className="font-semibold" style={{ color: '#7c3aed' }}>{cam.name}</p>
                <p className="text-xs text-gray-600 mt-1">{cam.camera_type}</p>
                {cam.ip_address && <p className="text-xs font-mono text-gray-500 mt-0.5">{cam.ip_address}</p>}
                <p className="text-xs mt-1">{cam.is_active ? '🟢 Active' : '⚫ Inactive'}</p>
                {cam.segment_name && <p className="text-xs text-gray-500">Segment: {cam.segment_name}</p>}
              </Popup>
            </Marker>
          )
        })}

        {/* Sensor markers (intersection or segment midpoint) */}
        {sensors.map(sen => {
          const pos = deviceCoords(sen.intersection, sen.segment)
          if (!pos) return null
          return (
            <Marker key={`sen-${sen.id}`} position={pos} icon={icons.sensor}>
              <Popup>
                <p className="font-semibold" style={{ color: '#0d9488' }}>{sen.name}</p>
                <p className="text-xs text-gray-600 mt-1">{sen.sensor_type}</p>
                <p className="text-xs mt-1">{sen.is_active ? '🟢 Active' : '⚫ Inactive'}</p>
                {sen.segment_name && <p className="text-xs text-gray-500">Segment: {sen.segment_name}</p>}
              </Popup>
            </Marker>
          )
        })}
      </MapContainer>

      {/* Legend */}
      <div className={`absolute bottom-3 right-3 z-[1000] rounded-lg border border-slate-200 bg-white/95 px-3 py-2 text-xs text-slate-600 shadow-md backdrop-blur ${compact ? 'hidden sm:flex flex-col gap-1' : 'flex flex-col gap-1'}`}>
        {[
          ['bg-blue-600',   'Intersection'],
          ['bg-red-600',    'Active Incident'],
          ['bg-amber-500',  'Traffic Event'],
          ['bg-violet-600', 'Camera'],
          ['bg-teal-600',   'Sensor'],
          ['bg-green-600',  'Signal'],
        ].map(([bg, label]) => (
          <div key={label} className="flex items-center gap-1.5">
            <span className={`inline-block h-2 w-2 rounded-full ${bg}`} />
            {label}
          </div>
        ))}
      </div>
    </div>
  )
}
