import { useEffect, useRef } from 'react'

/**
 * Runs `callback` immediately and then every `intervalMs` milliseconds.
 * Stops polling when the component unmounts or when `enabled` is false.
 */
export function usePolling(
  callback: () => void,
  intervalMs: number,
  enabled = true,
) {
  const savedCallback = useRef(callback)
  // Always use the latest callback without restarting the interval
  useEffect(() => { savedCallback.current = callback }, [callback])

  useEffect(() => {
    if (!enabled) return
    savedCallback.current()
    const id = setInterval(() => savedCallback.current(), intervalMs)
    return () => clearInterval(id)
  }, [intervalMs, enabled])
}
