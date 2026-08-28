import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="app-container">
      <div className="app-sidebar">
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      </div>
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="app-topbar">
          <TopBar onMenuClick={() => setSidebarOpen(true)} />
        </div>
        <main className="app-main page-enter">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
