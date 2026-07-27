import React, { useRef, useMemo } from 'react'
import { useTexture } from '@react-three/drei'
import * as THREE from 'three'

// White line material — shared
const WHITE = new THREE.MeshBasicMaterial({
  color: '#ffffff',
  transparent: true,
  opacity: 0.82,
  side: THREE.DoubleSide,
  depthWrite: false,
})

// Thin white line mesh helper
function Line({ pos, w, h, rotation = [0, 0, 0] }) {
  return (
    <mesh position={pos} rotation={rotation} material={WHITE} receiveShadow={false}>
      <planeGeometry args={[w, h]} />
    </mesh>
  )
}

// Circle ring helper (center circle, penalty arcs)
function Ring({ pos, r1, r2, segs = 64 }) {
  return (
    <mesh position={pos} material={WHITE}>
      <ringGeometry args={[r1, r2, segs]} />
    </mesh>
  )
}

// Small dot helper (spots)
function Spot({ pos }) {
  return (
    <mesh position={pos} material={WHITE}>
      <circleGeometry args={[0.12, 24]} />
    </mesh>
  )
}

export default function Pitch({ visualType }) {
  const grassTexture = useTexture('/textures/pitch_grass_dark.jpg')

  useMemo(() => {
    grassTexture.wrapS = THREE.RepeatWrapping
    grassTexture.wrapT = THREE.RepeatWrapping
    grassTexture.repeat.set(1, 1)
    grassTexture.anisotropy = 8
  }, [grassTexture])

  const Z = 0.11  // offset above pitch surface to prevent z-fighting

  // Field dimensions: 30 wide × 20 deep
  const W = 30, H = 20
  const hw = W / 2, hh = H / 2   // 15, 10

  return (
    <group rotation={[-Math.PI / 2, 0, 0]}>
      {/* ── TERRAIN ── */}
      <mesh receiveShadow castShadow>
        <boxGeometry args={[W, H, 0.22]} />
        <meshStandardMaterial
          map={grassTexture}
          roughness={0.88}
          metalness={0.04}
          envMapIntensity={0.3}
        />
      </mesh>

      {/* ══════════ MARKINGS GROUP ══════════ */}
      <group position={[0, 0, Z]}>

        {/* ── OUTER TOUCHLINES ── */}
        <Line pos={[0,     hh,  0]} w={W} h={0.1} />
        <Line pos={[0,    -hh,  0]} w={W} h={0.1} />
        <Line pos={[-hw,   0,   0]} w={0.1} h={H} />
        <Line pos={[ hw,   0,   0]} w={0.1} h={H} />

        {/* ── HALFWAY LINE ── */}
        <Line pos={[0, 0, 0]} w={0.1} h={H} />

        {/* ── CENTER CIRCLE & SPOT ── */}
        <Ring pos={[0, 0, 0]} r1={2.92} r2={3.05} />
        <Spot pos={[0, 0, 0]} />

        {/* ══ PENALTY AREA LEFT ══ */}
        <Line pos={[-11,    0, 0]} w={0.1} h={9.0} />
        <Line pos={[-13,  4.5, 0]} w={4.0} h={0.1} />
        <Line pos={[-13, -4.5, 0]} w={4.0} h={0.1} />
        <Spot pos={[-10.5, 0, 0]} />

        {/* ══ PENALTY AREA RIGHT ══ */}
        <Line pos={[ 11,    0, 0]} w={0.1} h={9.0} />
        <Line pos={[ 13,  4.5, 0]} w={4.0} h={0.1} />
        <Line pos={[ 13, -4.5, 0]} w={4.0} h={0.1} />
        <Spot pos={[ 10.5, 0, 0]} />

        {/* ══ 6-YARD BOXES ══ */}
        <Line pos={[-12.6,   0, 0]} w={0.1} h={3.6} />
        <Line pos={[-13.5, 1.8, 0]} w={1.8} h={0.1} />
        <Line pos={[-13.5,-1.8, 0]} w={1.8} h={0.1} />
        <Line pos={[ 12.6,   0, 0]} w={0.1} h={3.6} />
        <Line pos={[ 13.5, 1.8, 0]} w={1.8} h={0.1} />
        <Line pos={[ 13.5,-1.8, 0]} w={1.8} h={0.1} />

        {/* ══ PENALTY ARCS ══ */}
        <mesh position={[-10.5, 0, 0]}>
          <ringGeometry args={[2.92, 3.05, 64, 1, Math.PI * 0.62, Math.PI * 0.76]} />
          <meshBasicMaterial color="#ffffff" transparent opacity={0.82} side={THREE.DoubleSide} depthWrite={false} />
        </mesh>
        <mesh position={[10.5, 0, 0]}>
          <ringGeometry args={[2.92, 3.05, 64, 1, Math.PI * 1.62, Math.PI * 0.76]} />
          <meshBasicMaterial color="#ffffff" transparent opacity={0.82} side={THREE.DoubleSide} depthWrite={false} />
        </mesh>

        {/* ══ CORNER ARCS ══ */}
        {[[-hw, -hh], [-hw, hh], [hw, -hh], [hw, hh]].map(([cx, cy], i) => (
          <mesh key={i} position={[cx, cy, 0]}>
            <ringGeometry args={[0.88, 0.98, 32, 1,
              Math.PI * (i === 0 ? 0.0 : i === 1 ? 1.5 : i === 2 ? 0.5 : 1.0),
              Math.PI / 2]}
            />
            <meshBasicMaterial color="#ffffff" transparent opacity={0.82} side={THREE.DoubleSide} depthWrite={false} />
          </mesh>
        ))}

      </group>

      {/* ══════════ DYNAMIC PROMPT-DRIVEN OVERLAYS ══════════ */}

      {/* A. PRESSING VISUALIZATION */}
      {visualType === 'pressing' && (
        <group position={[0, 0, Z + 0.02]}>
          {/* Active press blocks (glowing hot zones) */}
          <mesh position={[-6, 3, 0]}>
            <circleGeometry args={[2.5, 32]} />
            <meshBasicMaterial color="#ef4444" transparent opacity={0.4} />
          </mesh>
          <mesh position={[-5, -4, 0]}>
            <circleGeometry args={[2.0, 32]} />
            <meshBasicMaterial color="#ef4444" transparent opacity={0.35} />
          </mesh>
          <mesh position={[3, 1, 0]}>
            <circleGeometry args={[2.8, 32]} />
            <meshBasicMaterial color="#ef4444" transparent opacity={0.3} />
          </mesh>

          {/* Glowing contour rings */}
          <mesh position={[-6, 3, 0.005]}>
            <ringGeometry args={[2.4, 2.5, 32]} />
            <meshBasicMaterial color="#f87171" transparent opacity={0.8} />
          </mesh>
          <mesh position={[-5, -4, 0.005]}>
            <ringGeometry args={[1.9, 2.0, 32]} />
            <meshBasicMaterial color="#f87171" transparent opacity={0.8} />
          </mesh>
          <mesh position={[3, 1, 0.005]}>
            <ringGeometry args={[2.7, 2.8, 32]} />
            <meshBasicMaterial color="#f87171" transparent opacity={0.8} />
          </mesh>
        </group>
      )}

      {/* B. KEY PASSES VISUALIZATION */}
      {visualType === 'passes' && (
        <group position={[0, 0, Z + 0.02]}>
          {/* Player Node points */}
          {/* Passer */}
          <mesh position={[-7, -3, 0]}>
            <circleGeometry args={[0.35, 32]} />
            <meshBasicMaterial color="#06b6d4" />
          </mesh>
          {/* Receiver */}
          <mesh position={[4, 2, 0]}>
            <circleGeometry args={[0.35, 32]} />
            <meshBasicMaterial color="#10b981" />
          </mesh>

          {/* Key Pass Lane Arrow */}
          <Line pos={[-1.5, -0.5, 0.005]} w={12} h={0.12} rotation={[0, 0, 0.42]} />
          {/* Arrowhead */}
          <mesh position={[4.1, 2.1, 0.005]} rotation={[0, 0, -1.15]}>
            <coneGeometry args={[0.3, 0.7, 4]} />
            <meshBasicMaterial color="#10b981" />
          </mesh>
        </group>
      )}

      {/* C. EXPECTED THREAT (xT) FLOW */}
      {visualType === 'xt' && (
        <group position={[0, 0, Z + 0.02]}>
          {/* Heat map blocks for Threat Flow */}
          <mesh position={[4, 5, 0]}>
            <planeGeometry args={[5, 4]} />
            <meshBasicMaterial color="#eab308" transparent opacity={0.25} />
          </mesh>
          <mesh position={[8, 2, 0]}>
            <planeGeometry args={[4, 6]} />
            <meshBasicMaterial color="#f97316" transparent opacity={0.3} />
          </mesh>
          <mesh position={[12, 0, 0]}>
            <planeGeometry args={[4, 10]} />
            <meshBasicMaterial color="#ef4444" transparent opacity={0.4} />
          </mesh>
        </group>
      )}

    </group>
  )
}
