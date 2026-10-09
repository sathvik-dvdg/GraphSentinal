// Dev-only page driven by export.mjs. It mounts the landing page's network
// scene at a fixed size and exposes window.__renderFrame so each frame can be
// stepped and captured deterministically.
import ReactDOM from 'react-dom/client'
import NetworkCanvas from '../../src/components/landing/NetworkCanvas'

const params = new URLSearchParams(window.location.search)
const width = Number(params.get('w')) || 1920
const height = Number(params.get('h')) || 1080
const centered = params.get('centered') === '1'

const progress = { intro: 0, story: 0 }
const stage = document.getElementById('stage')
stage.style.width = `${width}px`
stage.style.height = `${height}px`

ReactDOM.createRoot(stage).render(
  <NetworkCanvas
    getProgress={() => progress}
    centered={centered}
    side={false}
    frameloop="never"
    dpr={1}
    gl={{ preserveDrawingBuffer: true }}
    onCreated={(state) => {
      window.__renderFrame = (intro, story, quality = 0.8) => {
        progress.intro = intro
        progress.story = story
        state.advance(0)
        return state.gl.domElement.toDataURL('image/webp', quality)
      }
    }}
  />,
)
