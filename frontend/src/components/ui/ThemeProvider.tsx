import React from 'react'
import { colors, typography, radius, shadows, spacing } from '@/theme'

export type Theme = {
  colors: typeof colors
  typography: typeof typography
  radius: typeof radius
  shadows: typeof shadows
  spacing: typeof spacing
}

const theme: Theme = {
  colors,
  typography,
  radius,
  shadows,
  spacing,
}

export const ThemeContext = React.createContext<Theme>(theme)

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <ThemeContext.Provider value={theme}>
      {children}
    </ThemeContext.Provider>
  )
}
