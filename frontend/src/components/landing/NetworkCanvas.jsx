import { useEffect, useMemo } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { PALETTE, applyCamera, createNetworkScene } from './networkScene'

// getProgress() returns { intro, story }. The canvas renders on demand: a frame
// is drawn only when requestRender (registered through onReady) is called, so
// nothing runs while the scene is still or off-screen.
function Network({ getProgress, side, centered, onReady }) {
  const scene = useMemo(() => createNetworkScene(), [])
  const invalidate = useThree((s) => s.invalidate)
  const gl = useThree((s) => s.gl)
  const camera = useThree((s) => s.camera)
  const root = useThree((s) => s.scene)

  useEffect(() => () => scene.dispose(), [scene])
  // Compile every shader up front. Left to the first frame an object becomes
  // visible, compilation stalls the scroll at the start of a chapter.
  useEffect(() => scene.warm(gl, camera, root), [scene, gl, camera, root])
  useEffect(() => {
    onReady?.(invalidate)
    invalidate()
  }, [onReady, invalidate, side])

  useFrame(({ camera, size }) => {
    const { intro, story } = getProgress()
    scene.update(intro, story)
    applyCamera(camera, { intro, story, aspect: size.width / size.height, side, centered })
  })

  return <primitive object={scene.group} />
}

export default function NetworkCanvas({
  getProgress,
  side = true,
  centered = false,
  onReady,
  frameloop = 'demand',
  gl,
  onCreated,
  dpr = [1, 1.5],
}) {
  return (
    <Canvas
      flat
      frameloop={frameloop}
      dpr={dpr}
      camera={{ fov: 32, near: 0.1, far: 80, manual: true }}
      gl={{ antialias: true, powerPreference: 'high-performance', ...gl }}
      onCreated={onCreated}
      aria-hidden="true"
    >
      <color attach="background" args={[PALETTE.bone]} />
      <Network getProgress={getProgress} side={side} centered={centered} onReady={onReady} />
    </Canvas>
  )
}
