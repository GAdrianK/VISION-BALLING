import React, { memo } from 'react'
import { ShaderGradient, ShaderGradientCanvas } from 'shadergradient'

const StadiumScene = memo(function StadiumScene() {
  return (
    <ShaderGradientCanvas
      style={{ position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none' }}
    >
      <ShaderGradient
        animate="on"
        axesHelper="on"
        bgColor1="#000000"
        bgColor2="#000000"
        brightness={1.1}
        cAzimuthAngle={0}
        cDistance={7.1}
        cPolarAngle={140}
        cameraZoom={17.3}
        color1="#ff2bff"
        color2="#a052ff"
        color3="#ff1443"
        destination="onCanvas"
        embedMode="off"
        envPreset="city"
        format="gif"
        fov={45}
        frameRate={10}
        gizmoHelper="hide"
        grain="off"
        lightType="3d"
        pixelDensity={1}
        positionX={0}
        positionY={0}
        positionZ={0}
        range="disabled"
        rangeEnd={40}
        rangeStart={0}
        reflection={0.1}
        rotationX={0}
        rotationY={0}
        rotationZ={0}
        shader="defaults"
        type="sphere"
        uAmplitude={1.4}
        uDensity={1.1}
        uFrequency={5.5}
        uSpeed={0.1}
        uStrength={1}
        uTime={0}
        wireframe={false}
      />
    </ShaderGradientCanvas>
  )
})

export default StadiumScene
