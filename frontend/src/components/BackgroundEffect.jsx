import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

const vertexShader = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`

const fragmentShader = `
  uniform float uTime;
  uniform float uScroll;
  varying vec2 vUv;

  float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
  }

  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(
      mix(hash(i + vec2(0,0)), hash(i + vec2(1,0)), u.x),
      mix(hash(i + vec2(0,1)), hash(i + vec2(1,1)), u.x),
      u.y
    );
  }

  void main() {
    float t = uTime * 0.04;
    // zoom in slightly as we scroll
    vec2 uv = (vUv - 0.5) * (1.0 - uScroll * 0.15) + 0.5;

    // Slow warp noise
    float n1 = noise(uv * 1.8 + vec2(t * 0.4, t * 0.2));
    float n2 = noise(uv * 3.2 - vec2(t * 0.25, t * 0.35));
    float blended = (n1 + n2 * 0.5) / 1.5;

    // Vibrant Premium Colors
    vec3 colorGreen = vec3(0.015, 0.240, 0.130); // Deep emerald glow
    vec3 colorCyan  = vec3(0.010, 0.145, 0.280); // Electric deep cyan
    vec3 colorViolet = vec3(0.180, 0.050, 0.260); // Space neon violet

    // Shift colors as we scroll
    float blendVal = sin(uv.x * 2.5 + t * 0.15 + uScroll * 2.0) * 0.5 + 0.5;
    vec3 baseColor = mix(colorGreen, colorCyan, blendVal);
    baseColor = mix(baseColor, colorViolet, blended * (0.42 + uScroll * 0.25));

    // Increase vignette to concentrate light behind the main panels
    float vignette = smoothstep(0.0, 0.85, length(vUv - 0.5));
    baseColor *= 1.0 - vignette * (0.35 + uScroll * 0.35);

    gl_FragColor = vec4(baseColor, 1.0);
  }
`

export default function BackgroundEffect({ scrollProgress }) {
  const meshRef = useRef()
  const pointsRef = useRef()
  
  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uScroll: { value: 0 }
  }), [])

  // Create floating particles
  const [positions, speeds] = useMemo(() => {
    const count = 180
    const pos = new Float32Array(count * 3)
    const sp = new Float32Array(count)
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 80
      pos[i * 3 + 1] = (Math.random() - 0.5) * 50
      pos[i * 3 + 2] = (Math.random() - 0.5) * 15 - 5
      sp[i] = 0.05 + Math.random() * 0.12
    }
    return [pos, sp]
  }, [])

  useFrame(({ clock }) => {
    const elapsed = clock.getElapsedTime()
    uniforms.uTime.value = elapsed
    uniforms.uScroll.value = scrollProgress

    if (pointsRef.current) {
      const posAttr = pointsRef.current.geometry.attributes.position
      for (let i = 0; i < speeds.length; i++) {
        // Accelerate rising particles slightly on scroll
        posAttr.array[i * 3 + 1] += speeds[i] * (0.15 + scrollProgress * 0.2)
        if (posAttr.array[i * 3 + 1] > 25) {
          posAttr.array[i * 3 + 1] = -25
        }
      }
      posAttr.needsUpdate = true
    }
  })

  return (
    <group>
      {/* Nebula void quad */}
      <mesh ref={meshRef} position={[0, 0, -25]} scale={[100, 60, 1]}>
        <planeGeometry args={[1, 1]} />
        <shaderMaterial
          vertexShader={vertexShader}
          fragmentShader={fragmentShader}
          uniforms={uniforms}
          depthWrite={false}
        />
      </mesh>

      {/* Bokeh / Dust Particles */}
      <points ref={pointsRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[positions, 3]}
          />
        </bufferGeometry>
        <pointsMaterial
          size={0.32}
          color="#a7f3d0"
          transparent
          opacity={0.4}
          sizeAttenuation={true}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>
    </group>
  )
}
