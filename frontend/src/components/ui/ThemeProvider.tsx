import React, { useEffect, useState } from 'react'
import { colors, typography, radius, shadows, spacing } from '@/theme'

export type Theme = {
  colors: typeof colors
  typography: typeof typography
  radius: typeof radius
  shadows: typeof shadows
  spacing: typeof spacing
}

export type AppTheme = 'light' | 'dark'

interface ThemeContextValue {
  theme: AppTheme
  setTheme: (theme: AppTheme) => void
  toggleTheme: () => void
  appTheme: Theme
}

const theme: Theme = {
  colors,
  typography,
  radius,
  shadows,
  spacing,
}

const THEME_KEY = 'trafficops-theme'

export const ThemeContext = React.createContext<ThemeContextValue>({
  theme: 'light',
  setTheme: () => undefined,
  toggleTheme: () => undefined,
  appTheme: theme,
})

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [themeName, setThemeName] = useState<AppTheme>(() => {
    if (typeof window === 'undefined') return 'light'
    const stored = window.localStorage.getItem(THEME_KEY)
    return stored === 'dark' ? 'dark' : 'light'
  })

  useEffect(() => {
    window.localStorage.setItem(THEME_KEY, themeName)
    document.documentElement.style.colorScheme = themeName
    document.documentElement.dataset.theme = themeName
    document.body.dataset.theme = themeName
  }, [themeName])

  const value = React.useMemo<ThemeContextValue>(
    () => ({
      theme: themeName,
      setTheme: setThemeName,
      toggleTheme: () => setThemeName(prev => (prev === 'dark' ? 'light' : 'dark')),
      appTheme: theme,
    }),
    [themeName]
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  return React.useContext(ThemeContext)
}
