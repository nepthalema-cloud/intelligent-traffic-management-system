import React, { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { PerspectiveCamera, Html, Edges } from '@react-three/drei'
import { EffectComposer, Bloom, DepthOfField, Noise, Vignette } from '@react-three/postprocessing'
import * as THREE from 'three'

type VehicleProps = {
  id: string
  lane: number
  z: number
  speed: number
  plate?: string | null
  color?: string
  type: string
  confidence: number
}

const lanePositions = [-8, -4, 0, 4, 8]
const vehicleColors = ['#1b4fff', '#1ec4ff', '#06d9ff', '#0ccdb5', '#939aff']
const vehicleTypes = ['CAR', 'TRUCK', 'BUS', 'VAN']

function Vehicle({ id, lane, z: initialZ, speed, plate, color = '#0ff', type, confidence }: VehicleProps) {
  const ref = useRef<THREE.Group>(null!)
  const laneX = lanePositions[lane - 1]

  useFrame((state, delta) => {
    const mesh = ref.current
    mesh.position.z += speed * delta * 60
    mesh.position.x = laneX + Math.sin(state.clock.elapsedTime * 0.18 + lane) * 0.4
    mesh.position.y = -0.6 + Math.sin(state.clock.elapsedTime * 1.6 + lane) * 0.02
    const scale = 1 + THREE.MathUtils.clamp((mesh.position.z + 520) / 900, 0, 0.8)
    mesh.scale.setScalar(scale)
    if (mesh.position.z > 24) {
      mesh.position.z = -520 - Math.random() * 240
      mesh.position.y = -0.6
      mesh.scale.setScalar(1 + Math.random() * 0.1)
    }
  })

  return (
    <group ref={ref} position={[laneX, -0.6, initialZ]}>
      <group>
        <mesh position={[0, 0.18, 0]}>
          <boxGeometry args={[1.7, 0.35, 3.6]} />
          <meshStandardMaterial color={color} metalness={0.64} roughness={0.15} emissive={'#001d33'} emissiveIntensity={0.18} />
        </mesh>
        <mesh position={[0, 0.58, -0.5]} scale={[1.0, 0.28, 1.6]}> 
          <boxGeometry args={[1.2, 0.22, 1.6]} />
          <meshStandardMaterial color={'#081f34'} metalness={0.35} roughness={0.18} emissive={'#001b2c'} emissiveIntensity={0.16} />
        </mesh>
        <mesh position={[0, 0.38, 1.44]} scale={[0.95, 0.14, 0.22]}> 
          <boxGeometry args={[1.3, 0.16, 0.14]} />
          <meshStandardMaterial color={'#0f4d84'} metalness={0.4} roughness={0.14} emissive={'#0b5d97'} emissiveIntensity={0.25} />
        </mesh>
        <mesh position={[0, 0.38, -1.88]} scale={[0.96, 0.14, 0.2]}> 
          <boxGeometry args={[1.25, 0.14, 0.12]} />
          <meshStandardMaterial color={'#071e33'} metalness={0.35} roughness={0.16} emissive={'#03161f'} emissiveIntensity={0.1} />
        </mesh>
        <mesh position={[0.64, 0.22, 1.78]} scale={[0.36, 0.12, 0.08]}> 
          <boxGeometry args={[1, 0.2, 0.15]} />
          <meshStandardMaterial color={'#84fbff'} emissive={'#84fbff'} emissiveIntensity={1.9} />
        </mesh>
        <mesh position={[-0.64, 0.22, 1.78]} scale={[0.36, 0.12, 0.08]}> 
          <boxGeometry args={[1, 0.2, 0.15]} />
          <meshStandardMaterial color={'#84fbff'} emissive={'#84fbff'} emissiveIntensity={1.9} />
        </mesh>
        <mesh position={[0.64, 0.22, -1.78]} scale={[0.36, 0.12, 0.08]}> 
          <boxGeometry args={[1, 0.2, 0.15]} />
          <meshStandardMaterial color={'#ff5d91'} emissive={'#ff5d91'} emissiveIntensity={1.9} />
        </mesh>
        <mesh position={[-0.64, 0.22, -1.78]} scale={[0.36, 0.12, 0.08]}> 
          <boxGeometry args={[1, 0.2, 0.15]} />
          <meshStandardMaterial color={'#ff5d91'} emissive={'#ff5d91'} emissiveIntensity={1.9} />
        </mesh>
        <mesh position={[0, 0.22, 1.2]} scale={[1.25, 0.1, 0.18]}> 
          <boxGeometry args={[1.6, 0.12, 0.2]} />
          <meshStandardMaterial color={'#173b63'} metalness={0.2} roughness={0.1} emissive={'#0a3354'} emissiveIntensity={0.08} />
        </mesh>
        <Edges threshold={15} color="#4dd8ff" />
      </group>

      <Html position={[0, 0.95, 0]} distanceFactor={5} occlude>
        <div style={{ pointerEvents: 'none', transform: 'translateY(-8px)' }}>
          <div style={{ padding: '8px 12px', borderRadius: 10, background: 'rgba(2,8,17,0.72)', border: '1px solid rgba(64,222,255,0.12)', color: '#abfbff', fontSize: 11, minWidth: 130, boxShadow: '0 0 30px rgba(2,156,255,0.12)' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#e6f7ff' }}>{type} • {id}</div>
            <div style={{ marginTop: 6, display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <span style={{ opacity: 0.9 }}>{plate ?? 'PLATE N/A'}</span>
              <span style={{ opacity: 0.9 }}>{Math.round(speed * 32)} km/h</span>
            </div>
            <div style={{ marginTop: 6, display: 'flex', justifyContent: 'space-between', color: '#7ee7ff', fontSize: 10 }}>
              <span>CONF {Math.round(confidence * 100)}%</span>
              <span>TRACK {Math.floor(Math.random() * 98 + 1)}</span>
            </div>
          </div>
        </div>
      </Html>
    </group>
  )
}

function Road() {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.24, 0]} receiveShadow>
        <planeGeometry args={[240, 140]} />
        <meshStandardMaterial color={'#040b16'} metalness={0.1} roughness={0.45} />
      </mesh>
      {[...Array(5)].map((_, index) => {
        const x = -12 + index * 6
        return (
          <mesh key={index} position={[x, -1.23, 0]} rotation={[-Math.PI / 2, 0, 0]}>
            <planeGeometry args={[2.2, 140]} />
            <meshStandardMaterial color={'#00395c'} emissive={'#00395c'} emissiveIntensity={0.35} transparent opacity={0.18} />
          </mesh>
        )
      })}
      {[...Array(32)].map((_, index) => {
        const z = -140 + index * 9
        return (
          <mesh key={`stripe-${index}`} position={[0, -1.22, z]} rotation={[-Math.PI / 2, 0, 0]}>
            <planeGeometry args={[0.4, 2]} />
            <meshStandardMaterial color={'#53c9ff'} emissive={'#53c9ff'} emissiveIntensity={0.8} transparent opacity={0.25} />
          </mesh>
        )
      })}
    </group>
  )
}

function Skyline() {
  const buildings = useMemo(() => {
    return Array.from({ length: 14 }, (_, index) => ({
      x: -65 + index * 10,
      height: 18 + Math.random() * 32,
      color: index % 2 === 0 ? '#10305b' : '#0b2444',
      windowColor: index % 3 === 0 ? '#2cecff' : '#2f8dff',
    }))
  }, [])

  return (
    <group position={[0, 1.5, -140]}>
      {buildings.map((building, idx) => (
        <group key={idx} position={[building.x, 0, 0]}>
          <mesh position={[0, building.height / 2, 0]}>
            <boxGeometry args={[8, building.height, 10]} />
            <meshStandardMaterial color={building.color} roughness={0.4} metalness={0.2} emissive={'#001626'} emissiveIntensity={0.03} />
          </mesh>
          <mesh position={[0, building.height - 4, 5.5]} rotation={[-Math.PI / 2, 0, 0]}>
            <planeGeometry args={[8, 6]} />
            <meshBasicMaterial color={building.windowColor} transparent opacity={0.12} side={THREE.DoubleSide} />
          </mesh>
        </group>
      ))}
    </group>
  )
}

function Overpass() {
  return (
    <group position={[0, 1.2, -15]}>
      <mesh position={[0, 0, 0]}>
        <boxGeometry args={[120, 2.6, 8]} />
        <meshStandardMaterial color={'#061c34'} metalness={0.2} roughness={0.3} emissive={'#011627'} emissiveIntensity={0.05} />
      </mesh>
      <mesh position={[-58, -1.5, 0]}>
        <boxGeometry args={[4, 10, 4]} />
        <meshStandardMaterial color={'#08172d'} metalness={0.22} roughness={0.35} />
      </mesh>
      <mesh position={[58, -1.5, 0]}>
        <boxGeometry args={[4, 10, 4]} />
        <meshStandardMaterial color={'#08172d'} metalness={0.22} roughness={0.35} />
      </mesh>
    </group>
  )
}

function SceneHud() {
  return (
    <group>
      <Html position={[-18, 6, -20]} transform occlude>
        <div style={{ width: 260, padding: 14, borderRadius: 16, background: 'rgba(2,12,22,0.42)', border: '1px solid rgba(64,220,255,0.2)', boxShadow: '0 0 40px rgba(0,160,255,0.12)', color: '#a9f7ff', fontSize: 12 }}>
          <div style={{ marginBottom: 10, fontSize: 12, letterSpacing: 1.2, textTransform: 'uppercase', color: '#80d8ff' }}>Live AI Traffic Monitoring</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <span>Vehicles</span><span style={{ textAlign: 'right', color: '#dffcff' }}>24</span>
            <span>Detected</span><span style={{ textAlign: 'right', color: '#dffcff' }}>18</span>
            <span>Average</span><span style={{ textAlign: 'right', color: '#dffcff' }}>72 km/h</span>
            <span>Plate OCR</span><span style={{ textAlign: 'right', color: '#dffcff' }}>89%</span>
          </div>
        </div>
      </Html>
      <Html position={[18, 6, -22]} transform occlude>
        <div style={{ width: 220, padding: 12, borderRadius: 16, background: 'rgba(2,12,22,0.4)', border: '1px solid rgba(64,220,255,0.16)', boxShadow: '0 0 30px rgba(0,160,255,0.1)', color: '#b3f2ff', fontSize: 12 }}>
          <div style={{ marginBottom: 10, fontSize: 12, letterSpacing: 1.1, textTransform: 'uppercase', color: '#82d2ff' }}>System Status</div>
          <div style={{ display: 'grid', gap: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>AI Model</span><span>YOLOv8n</span></div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Object Tracking</span><span style={{ color: '#86ffb2' }}>Active</span></div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Plate OCR</span><span style={{ color: '#86ffb2' }}>Active</span></div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Streams</span><span>4 / 4</span></div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Health</span><span style={{ color: '#86ffb2' }}>Optimal</span></div>
          </div>
        </div>
      </Html>
    </group>
  )
}

function TrafficVehicles() {
  const vehicles = useMemo(() => {
    const list: VehicleProps[] = []
    for (let i = 0; i < 18; i++) {
      const lane = (i % 5) + 1
      list.push({
        id: `${vehicleTypes[i % vehicleTypes.length]}-${120 + i}`,
        lane,
        z: -Math.random() * 760 - 20,
        speed: 0.75 + Math.random() * 1.9,
        plate: Math.random() > 0.35 ? `ABC-${100 + Math.floor(Math.random() * 900)}` : null,
        color: vehicleColors[i % vehicleColors.length],
        type: vehicleTypes[i % vehicleTypes.length],
        confidence: 0.78 + Math.random() * 0.16,
      })
    }
    return list
  }, [])

  return <>{vehicles.map(v => <Vehicle key={`${v.id}-${v.z}`} {...v} />)}</>
}

export const R3FTrafficScene: React.FC = () => {
  return (
    <div className="r3f-canvas h-full w-full">
      <Canvas shadows camera={{ position: [0, 7, 30], fov: 32 }} gl={{ antialias: true }}>
        <fog attach="fog" args={[0x000914, 6, 65]} />
        <color attach="background" args={[0x02060f]} />
        <ambientLight intensity={0.45} />
        <directionalLight position={[10, 15, 10]} intensity={0.85} color="#a0caff" />
        <pointLight position={[-14, 10, -30]} intensity={1.2} color="#4bf3ff" distance={120} />
        <pointLight position={[14, 11, -28]} intensity={0.9} color="#4bf3ff" distance={100} />

        <Road />
        <Skyline />
        <Overpass />
        <SceneHud />
        <TrafficVehicles />

        <EffectComposer multisampling={4}>
          <DepthOfField focusDistance={0.015} focalLength={0.03} bokehScale={3} />
          <Bloom luminanceThreshold={0.18} luminanceSmoothing={0.7} intensity={1.1} />
          <Noise opacity={0.04} />
          <Vignette eskil={false} offset={0.3} darkness={0.65} />
        </EffectComposer>

        <PerspectiveCamera makeDefault position={[0, 8, 33]} fov={32} />
      </Canvas>
    </div>
  )
}

export default R3FTrafficScene
