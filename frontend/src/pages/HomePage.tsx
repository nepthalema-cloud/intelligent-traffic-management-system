/**
 * HomePage — public landing page for the AI-Powered Smart Traffic Management System.
 *
 * The "AI Detection" animation in the hero section is a VISUAL DEMONSTRATION ONLY.
 * It illustrates the intended future AI workflow (camera → detection → tracking → alert).
 * No real AI/ML services are running. Real live data is shown in the dashboard after login.
 */

import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'

// ── Animated AI camera scene ──────────────────────────────────────────────

type DetectionBox = {
  id: number
  x: number; y: number; w: number; h: number
  label: string; speed: number
  color: 'green' | 'yellow' | 'red'
  delay: number
}

const DEMO_BOXES: DetectionBox[] = [
  { id: 1, x: 8,  y: 38, w: 20, h: 28, label: 'CAR · 45 km/h',     speed: 45, color: 'green',  delay: 0    },
  { id: 2, x: 36, y: 32, w: 22, h: 30, label: 'CAR · 62 km/h',     speed: 62, color: 'green',  delay: 0.4  },
  { id: 3, x: 62, y: 30, w: 18, h: 26, label: '⚠ VIOLATION · 89 km/h', speed: 89, color: 'red', delay: 0.8 },
  { id: 4, x: 16, y: 68, w: 16, h: 22, label: 'TRUCK · 38 km/h',   speed: 38, color: 'yellow', delay: 1.2  },
]

const colourCss = {
  green:  { border: '#22c55e', bg: 'rgba(34,197,94,0.08)',  text: '#16a34a', badge: 'rgba(34,197,94,0.15)'  },
  yellow: { border: '#f59e0b', bg: 'rgba(245,158,11,0.08)', text: '#b45309', badge: 'rgba(245,158,11,0.15)' },
  red:    { border: '#ef4444', bg: 'rgba(239,68,68,0.10)',  text: '#dc2626', badge: 'rgba(239,68,68,0.18)'  },
}

function AICameraScene() {
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 2000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="relative w-full rounded-2xl overflow-hidden select-none"
      style={{ aspectRatio: '16/9', background: 'linear-gradient(160deg, #0f172a 0%, #1e293b 40%, #0f172a 100%)' }}>

      {/* Simulated road scene — pure CSS/SVG, no real camera feed */}
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 60" preserveAspectRatio="none">
        {/* Road surface */}
        <rect x="0" y="40" width="100" height="20" fill="#1e293b"/>
        <rect x="0" y="36" width="100" height="4"  fill="#0f172a"/>
        {/* Lane markings */}
        {[10,20,30,40,50,60,70,80,90].map(x => (
          <rect key={x} x={x} y="49" width="6" height="1.2" fill="#f1f5f9" opacity="0.4"/>
        ))}
        {/* Buildings silhouette */}
        {[5,15,28,42,55,68,78,88].map((x,i) => (
          <rect key={x} x={x} y={8 + (i%3)*6} width={6+(i%2)*3} height={30-(i%3)*6} fill="#1e3a5f" opacity="0.6"/>
        ))}
        {/* Street lights */}
        {[20,50,80].map(x => (
          <g key={x}>
            <rect x={x} y="10" width="0.5" height="30" fill="#475569"/>
            <ellipse cx={x} cy="10" rx="4" ry="1.5" fill="#fbbf24" opacity="0.25"/>
          </g>
        ))}
        {/* Traffic light */}
        <rect x="90" y="20" width="3" height="18" fill="#334155"/>
        <rect x="89" y="18" width="5" height="8" rx="1" fill="#1e293b" stroke="#475569" strokeWidth="0.3"/>
        <circle cx="91.5" cy="20" r="1.2" fill="#ef4444" opacity={tick % 3 === 0 ? '1' : '0.2'}/>
        <circle cx="91.5" cy="23" r="1.2" fill="#f59e0b" opacity={tick % 3 === 1 ? '1' : '0.2'}/>
        <circle cx="91.5" cy="26" r="1.2" fill="#22c55e" opacity={tick % 3 === 2 ? '1' : '0.2'}/>
      </svg>

      {/* Detection overlays */}
      {DEMO_BOXES.map(box => {
        const c = colourCss[box.color]
        return (
          <div key={box.id}
            className="absolute transition-opacity duration-700"
            style={{
              left: `${box.x}%`, top: `${box.y}%`,
              width: `${box.w}%`, height: `${box.h}%`,
              border: `1.5px solid ${c.border}`,
              background: c.bg,
              borderRadius: 4,
              opacity: 0.9,
              animationDelay: `${box.delay}s`,
            }}>
            {/* Corner accents */}
            {['tl','tr','bl','br'].map(corner => (
              <span key={corner} className="absolute w-2.5 h-2.5" style={{
                borderColor: c.border, borderStyle: 'solid', borderWidth: 0,
                ...(corner === 'tl' ? { top: -1, left: -1, borderTopWidth: 2, borderLeftWidth: 2 } :
                    corner === 'tr' ? { top: -1, right: -1, borderTopWidth: 2, borderRightWidth: 2 } :
                    corner === 'bl' ? { bottom: -1, left: -1, borderBottomWidth: 2, borderLeftWidth: 2 } :
                                      { bottom: -1, right: -1, borderBottomWidth: 2, borderRightWidth: 2 }),
              }}/>
            ))}
            {/* Label */}
            <span className="absolute -top-5 left-0 whitespace-nowrap rounded px-1.5 py-0.5 text-[9px] font-bold"
              style={{ background: c.badge, color: c.text, border: `1px solid ${c.border}` }}>
              {box.label}
            </span>
          </div>
        )
      })}

      {/* Scan line animation */}
      <div className="absolute inset-x-0 h-0.5 animate-scan pointer-events-none"
        style={{ background: 'linear-gradient(90deg, transparent, rgba(59,130,246,0.6), transparent)' }}/>

      {/* HUD overlays */}
      <div className="absolute top-3 left-3 flex items-center gap-1.5 rounded-lg bg-black/50 px-2.5 py-1.5 backdrop-blur-sm">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-400"/>
        <span className="text-[10px] font-semibold text-white tracking-wide">TEST VIDEO SOURCE</span>
      </div>

      <div className="absolute top-3 right-3 flex items-center gap-1.5 rounded-lg bg-blue-600/80 px-2.5 py-1.5 backdrop-blur-sm">
        <svg className="h-3 w-3 text-white" fill="currentColor" viewBox="0 0 20 20"><path d="M13 7H7v6h6V7z"/><path fillRule="evenodd" d="M7 2a1 1 0 012 0v1h2V2a1 1 0 112 0v1h2a2 2 0 012 2v2h1a1 1 0 110 2h-1v2h1a1 1 0 110 2h-1v2a2 2 0 01-2 2h-2v1a1 1 0 11-2 0v-1H9v1a1 1 0 11-2 0v-1H5a2 2 0 01-2-2v-2H2a1 1 0 110-2h1V9H2a1 1 0 110-2h1V5a2 2 0 012-2h2V2zM5 5h10v10H5V5z" clipRule="evenodd"/></svg>
        <span className="text-[10px] font-bold text-white tracking-wide">AI PIPELINE (DEMO)</span>
      </div>

      {/* Violation alert */}
      <div className="absolute bottom-3 right-3 animate-pulse">
        <div className="rounded-lg border border-red-500/50 bg-red-950/80 px-3 py-2 backdrop-blur-sm">
          <p className="text-[9px] font-bold text-red-400 uppercase tracking-wider">⚠ Violation Detected</p>
          <p className="text-[9px] text-red-300">Speed: 89 km/h · Limit: 60 km/h</p>
        </div>
      </div>

      {/* System status */}
      <div className="absolute bottom-3 left-3 rounded-lg bg-black/50 px-2.5 py-1.5 backdrop-blur-sm">
        <p className="text-[9px] text-emerald-400 font-medium">● SYSTEM OPERATIONAL · 4 vehicles tracked</p>
      </div>

      {/* Demo disclaimer */}
      <div className="absolute inset-x-0 bottom-0 h-6 flex items-center justify-center">
        <p className="text-[8px] text-slate-500 bg-black/30 px-2 rounded-full">
          Visual demonstration — AI detection illustrated, not currently active
        </p>
      </div>
    </div>
  )
}

// ── Feature cards ─────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" /></svg>,
    title: 'Live Traffic Map',
    desc:  'Interactive Leaflet/OpenStreetMap visualization of the entire road network with real-time incident and event overlays.',
    live:  true,
  },
  {
    icon: <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>,
    title: 'Incident Management',
    desc:  'Full lifecycle tracking from reported → investigating → managing → resolved → closed with role-based operational controls.',
    live:  true,
  },
  {
    icon: <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>,
    title: 'Traffic Analytics',
    desc:  'Hourly and daily aggregated flow summaries, incident reports, and violation statistics across the road network.',
    live:  true,
  },
  {
    icon: <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M15 10l4.553-2.069A1 1 0 0121 8.871v6.258a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>,
    title: 'Camera & Sensor Monitoring',
    desc:  'Fleet-wide health monitoring with per-device connectivity status, last-seen timestamps, and real-time health badges.',
    live:  true,
  },
  {
    icon: <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" /></svg>,
    title: 'Signal Management',
    desc:  'Full signal and phase configuration with green/yellow/all-red timing details. Role-aware controls for TCOs.',
    live:  true,
  },
  {
    icon: <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>,
    title: 'AI-Ready Architecture',
    desc:  'Vehicle detection, OCR, and violation processing pipelines are architecturally defined and ready for AI service integration.',
    live:  false,
  },
]

// ── Stats row ─────────────────────────────────────────────────────────────

const STATS = [
  { value: '7',    label: 'RBAC Roles' },
  { value: '6',    label: 'Traffic Domains' },
  { value: '100%', label: 'REST-API Driven' },
  { value: 'JWT',  label: 'Secure Auth' },
]

// ── Main component ────────────────────────────────────────────────────────

export function HomePage() {
  return (
    <div className="min-h-screen bg-white text-slate-900">
      {/* Nav */}
      <nav className="sticky top-0 z-50 border-b border-slate-100 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 shadow-sm">
              <svg className="h-4 w-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
              </svg>
            </div>
            <span className="text-base font-bold text-slate-900">TrafficOps</span>
          </div>
          <Link to="/login"
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors">
            Sign In →
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="mx-auto max-w-6xl px-6 pt-16 pb-12">
        <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
          {/* Text */}
          <div className="animate-slide-up">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700">
              <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
              AI-Powered Smart Traffic Management
            </div>
            <h1 className="text-4xl font-bold text-slate-900 leading-tight mb-4 lg:text-5xl">
              The intelligent<br />
              <span className="text-blue-600">Traffic Operations</span><br />
              platform
            </h1>
            <p className="text-lg text-slate-600 mb-8 leading-relaxed">
              A complete smart-city traffic management system — real-time incident management,
              interactive mapping, analytics, and AI-ready camera monitoring. Built for
              traffic control officers, analysts, and administrators.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link to="/login"
                className="rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors">
                Explore Dashboard →
              </Link>
              <Link to="/login"
                className="rounded-lg border border-slate-300 bg-white px-6 py-3 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition-colors">
                Sign In
              </Link>
            </div>
            <p className="mt-4 text-xs text-slate-400">
              Demo: <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">Admin</code> / <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">admin1234</code>
            </p>
          </div>

          {/* AI demo scene */}
          <div className="animate-slide-up" style={{ animationDelay: '0.15s' }}>
            <AICameraScene />
            <p className="mt-2 text-center text-xs text-slate-400">
              Planned AI workflow visualization · Real data shown in the dashboard
            </p>
          </div>
        </div>
      </section>

      {/* Stats band */}
      <section className="border-y border-slate-100 bg-slate-50 py-8">
        <div className="mx-auto max-w-6xl px-6">
          <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
            {STATS.map(s => (
              <div key={s.label} className="text-center">
                <p className="text-3xl font-bold text-blue-600">{s.value}</p>
                <p className="text-xs font-medium text-slate-500 mt-1 uppercase tracking-wider">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-6 py-16">
        <div className="mb-10 text-center">
          <h2 className="text-2xl font-bold text-slate-900 mb-3">Everything you need for traffic operations</h2>
          <p className="text-slate-500 max-w-xl mx-auto">
            A fully integrated platform covering the complete traffic management lifecycle —
            from real-time monitoring to analytics and enforcement.
          </p>
        </div>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(f => (
            <div key={f.title} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
              <div className="mb-4 flex items-center justify-between">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
                  {f.icon}
                </span>
                {f.live
                  ? <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 border border-emerald-200">Live</span>
                  : <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500 border border-slate-200">Planned</span>
                }
              </div>
              <h3 className="text-sm font-semibold text-slate-900 mb-1.5">{f.title}</h3>
              <p className="text-xs text-slate-500 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="bg-blue-600 py-16">
        <div className="mx-auto max-w-2xl px-6 text-center">
          <h2 className="text-2xl font-bold text-white mb-3">Ready to see it live?</h2>
          <p className="text-blue-100 mb-8">
            Log in with the demo account to explore the full Traffic Operations dashboard.
            Target deployment: Gondar, Ethiopia.
          </p>
          <Link to="/login"
            className="inline-flex items-center gap-2 rounded-xl bg-white px-7 py-3 text-sm font-semibold text-blue-700 shadow-lg hover:bg-blue-50 transition-colors">
            Open Dashboard →
          </Link>
          <p className="mt-4 text-blue-200 text-sm">
            Demo: <code className="font-mono font-bold">Admin</code> / <code className="font-mono font-bold">admin1234</code>
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-8">
        <div className="mx-auto max-w-6xl px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-slate-500">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded bg-blue-600">
              <svg className="h-3 w-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
              </svg>
            </div>
            <span className="font-semibold text-slate-700">TrafficOps</span>
            <span>AI-Powered Smart Traffic Management System</span>
          </div>
          <p className="text-xs">Backend: Django 6 · DRF · JWT · PostgreSQL · Frontend: React 19 · TypeScript · Vite · Tailwind</p>
        </div>
      </footer>
    </div>
  )
}
