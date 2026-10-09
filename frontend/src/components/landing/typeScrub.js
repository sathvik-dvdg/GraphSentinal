import { useTransform } from 'framer-motion'

const DEFAULT_STEP = 20

// Scroll-scrubbed font weight, snapped to steps of 20. A variable font has to
// rebuild and re-rasterise every glyph for each new weight, and an unsnapped
// scrub asks for a new fractional weight on every frame, which at display
// sizes costs several milliseconds a frame. Snapped, most frames reuse the
// previous weight and scrubbing back reuses cached glyphs. Twenty units is
// about two thirds of a pixel of stem at the hero title's size, so it still
// reads as a continuous scrub.
export function useSteppedWeight(source, input, output, step = DEFAULT_STEP) {
  const weight = useTransform(source, input, output)
  return useTransform(weight, (value) => Math.round(value / step) * step)
}
