import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ErrorBoundary } from '@/components/ErrorBoundary'

const root = document.getElementById('root')
if (!root) throw new Error('Root element #root not found')

// StrictMode is intentionally omitted: react-leaflet's MapContainer uses
// Leaflet's imperative DOM initialization which is incompatible with
// StrictMode's deliberate double-mount in development. Enabling StrictMode
// causes "Map container is already initialized." on every render.
// The ErrorBoundary above provides equivalent crash visibility.
createRoot(root).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>,
)
