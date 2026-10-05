// Framing shared by the frame sequence (SequenceCanvas) and the camera
// (networkScene). Kept free of three.js so the hero can use it before the 3D
// bundle loads.

// The desktop frames are rendered at this size; the picture is drawn centred
// and height-held, so a wider window gets bare ground either side.
export const LANDSCAPE_FRAME = { width: 2304, height: 972 }
export const LANDSCAPE_FRAME_ASPECT = LANDSCAPE_FRAME.width / LANDSCAPE_FRAME.height

// The cinematic holds its opening composition until here, then swings into the
// story's first frame while the hero fades.
export const HERO_SWING_START = 0.78

const sat = (x) => Math.min(1, Math.max(0, x))

// 0..1 across the swing, eased.
export function heroSwing(intro) {
  const t = sat((intro - HERO_SWING_START) / (1 - HERO_SWING_START))
  return t * t * (3 - 2 * t)
}
