import React, { useEffect, useRef } from 'react'

type Vehicle = {
  x: number
  y: number
  w: number
  h: number
  speed: number
  color: string
  id: string
  plate: string
}

function rand(min: number, max: number) { return Math.random() * (max - min) + min }

export const CinematicScene: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const rafRef = useRef<number | null>(null)
  const mountedRef = useRef(false)

  useEffect(() => {
    const canvas = canvasRef.current!
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    let dpr = Math.max(1, window.devicePixelRatio || 1)

    function resize() {
      dpr = Math.max(1, window.devicePixelRatio || 1)
      const rect = canvas.getBoundingClientRect()
      canvas.width = Math.round(rect.width * dpr)
      canvas.height = Math.round(rect.height * dpr)
      canvas.style.width = `${rect.width}px`
      canvas.style.height = `${rect.height}px`
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    window.addEventListener('resize', resize)
    resize()

    const vehicles: Vehicle[] = []
    const lanes = 4
    const laneH = canvas.height / dpr / (lanes + 1)
    for (let i = 0; i < 8; i++) {
      const lane = (i % lanes) + 1
      vehicles.push({
        x: rand(-300, canvas.width / dpr),
        y: lane * laneH + rand(-10, 10),
        w: rand(60, 120),
        h: rand(30, 48),
        speed: rand(0.6, 2.6),
        color: '#0ff',
        id: `ID${Math.floor(rand(1000,9999))}`,
        plate: `ABC-${Math.floor(rand(100,999))}`
      })
    }

    let last = performance.now()

    function drawRoad() {
      const w = canvas.width / dpr
      const h = canvas.height / dpr
      // dark gradient road
      const g = ctx.createLinearGradient(0, 0, 0, h)
      g.addColorStop(0, '#030617')
      g.addColorStop(1, '#061021')
      ctx.fillStyle = g
      ctx.fillRect(0, 0, w, h)

      // lane markings
      ctx.strokeStyle = 'rgba(255,255,255,0.03)'
      ctx.lineWidth = 1
      const lanes = 4
      for (let i = 1; i <= lanes; i++) {
        const y = (h / (lanes + 1)) * i
        ctx.beginPath()
        ctx.setLineDash([10, 18])
        ctx.moveTo(0, y)
        ctx.lineTo(w, y)
        ctx.stroke()
      }
      ctx.setLineDash([])
    }

    function drawHUD(w: number) {
      // scanning radar
      const cx = 120
      const cy = 120
      ctx.save()
      ctx.translate(cx, cy)
      const t = performance.now() / 1000
      for (let i = 0; i < 3; i++) {
        ctx.beginPath()
        ctx.strokeStyle = `rgba(0,180,255,${0.06 - i*0.015})`
        ctx.lineWidth = 1
        ctx.arc(0, 0, 30 + i * 18, 0, Math.PI * 2)
        ctx.stroke()
      }
      // sweeping line
      ctx.rotate(t % (Math.PI * 2))
      const grd = ctx.createLinearGradient(0,0,120,0)
      grd.addColorStop(0,'rgba(0,255,250,0.12)')
      grd.addColorStop(1,'rgba(0,255,250,0)')
      ctx.fillStyle = grd
      ctx.beginPath()
      ctx.moveTo(0,0)
      ctx.arc(0,0,60, -0.12, 0.12)
      ctx.closePath()
      ctx.fill()
      ctx.restore()

      // small HUD boxes
      ctx.fillStyle = 'rgba(0,0,0,0.35)'
      ctx.fillRect(w - 260, 40, 220, 120)
      ctx.strokeStyle = 'rgba(0,200,255,0.18)'
      ctx.strokeRect(w - 260, 40, 220, 120)
      ctx.fillStyle = '#6ee7ff'
      ctx.font = '12px Inter, system-ui, sans-serif'
      ctx.fillText('SYSTEM STATUS', w - 240, 60)
      ctx.fillStyle = '#9feaff'
      ctx.fillText('AI: YOLOv8n', w - 240, 82)
      ctx.fillText('Detection: ACTIVE', w - 240, 100)
      ctx.fillText('Streams: 4/4', w - 240, 118)
    }

    function drawVehicle(v: Vehicle) {
      const { x, y, w: vw, h: vh } = v
      // vehicle body
      ctx.fillStyle = 'rgba(10,20,30,0.7)'
      roundRect(ctx, x, y - vh/2, vw, vh, 6)
      ctx.fill()

      // headlights and taillights
      ctx.fillStyle = 'rgba(255,255,220,0.9)'
      ctx.fillRect(x + vw - 8, y - vh/3, 6, vh/6)
      ctx.fillStyle = 'rgba(255,40,40,0.9)'
      ctx.fillRect(x + 2, y - vh/3, 6, vh/6)

      // detection box
      ctx.strokeStyle = 'rgba(0,220,255,0.9)'
      ctx.lineWidth = 2
      ctx.strokeRect(x - 6, y - vh/2 - 8, vw + 12, vh + 16)

      // labels
      ctx.fillStyle = '#7ef0ff'
      ctx.font = '12px Inter, system-ui, sans-serif'
      ctx.fillText(v.id, x, y - vh/2 - 14)
      ctx.fillStyle = '#bffaff'
      ctx.fillText(`${v.plate} • ${(v.speed*10).toFixed(0)} km/h`, x, y + vh/2 + 18)
      // confidence bar
      const conf = 0.88 + (Math.sin(performance.now()/700 + parseInt(v.id.replace(/\D/g,''))||0)*0.02)
      ctx.fillStyle = 'rgba(0,200,255,0.14)'
      ctx.fillRect(x, y + vh/2 + 24, vw * 0.6, 6)
      ctx.fillStyle = 'rgba(0,200,255,0.95)'
      ctx.fillRect(x, y + vh/2 + 24, vw * 0.6 * conf, 6)
    }

    function roundRect(ctx: CanvasRenderingContext2D, x:number, y:number, w:number, h:number, r:number) {
      ctx.beginPath()
      ctx.moveTo(x+r,y)
      ctx.lineTo(x+w-r,y)
      ctx.quadraticCurveTo(x+w,y,x+w,y+r)
      ctx.lineTo(x+w,y+h-r)
      ctx.quadraticCurveTo(x+w,y+h,x+w-r,y+h)
      ctx.lineTo(x+r,y+h)
      ctx.quadraticCurveTo(x,y+h,x,y+h-r)
      ctx.lineTo(x,y+r)
      ctx.quadraticCurveTo(x,y,x+r,y)
      ctx.closePath()
    }

    function step(now: number) {
      const dt = Math.min(40, now - last) / 16
      last = now
      const w = canvas.width / dpr
      const h = canvas.height / dpr
      ctx.clearRect(0,0,w,h)
      drawRoad()
      // update vehicles
      vehicles.forEach(v => {
        v.x += v.speed * dt * 1.8
        if (v.x - v.w > w + 200) {
          v.x = -rand(120, 420)
          v.y = ((Math.floor(rand(1,4))+1) * (h/(lanes+1))) + rand(-6,6)
          v.speed = rand(0.6, 2.6)
          v.plate = `ABC-${Math.floor(rand(100,999))}`
        }
        drawVehicle(v)
      })
      drawHUD(w)
      rafRef.current = requestAnimationFrame(step)
    }

    mountedRef.current = true
    rafRef.current = requestAnimationFrame(step)

    return () => {
      mountedRef.current = false
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return (
    <div className="cinematic-left w-full h-full relative cinematic-fade-in">
      <canvas ref={canvasRef} className="cinematic-canvas absolute inset-0 w-full h-full" />
      <div className="hud-overlay pointer-events-none">
        <div className="hud-title">AI TRAFFIC MONITORING</div>
      </div>
    </div>
  )
}

export default CinematicScene
