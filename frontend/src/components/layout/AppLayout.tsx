import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { useTheme } from '@/components/ui/ThemeProvider'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { theme } = useTheme()

  return (
    <div className="app-shell-theme" data-theme={theme}>
      <div className="app-container">
        <div className="app-sidebar">
          <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        </div>
        <div className="app-shell-main">
          <div className="app-topbar">
            <TopBar onMenuClick={() => setSidebarOpen(true)} />
          </div>
          <main className="app-main page-enter">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}
