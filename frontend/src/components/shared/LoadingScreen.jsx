// [Windows] GraphSentinel — Susheep
import { motion } from 'framer-motion'

export default function LoadingScreen() {
  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-gs-bg">
      <motion.div
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        className="flex flex-col items-center gap-6"
      >
        <div className="text-5xl">🛡️</div>
        <h1 className="text-2xl font-bold text-gs-accent font-mono tracking-wider">
          GRAPHSENTINEL
        </h1>

        <div className="flex items-center gap-2 mt-4">
          {[0, 1, 2, 3, 4].map((i) => (
            <motion.div
              key={i}
              className="w-2 h-2 rounded-full bg-gs-accent"
              animate={{ opacity: [0.2, 1, 0.2], scale: [0.8, 1.2, 0.8] }}
              transition={{
                duration: 1,
                repeat: Infinity,
                delay: i * 0.15,
              }}
            />
          ))}
        </div>

        <p className="text-xs text-gray-500 font-mono mt-2">
          Initializing defense systems...
        </p>
      </motion.div>

      <div className="absolute bottom-8 text-xs text-gray-700 font-mono">
        GraphSentinel v1.0.0 · Self-Healing Cyber Defense
      </div>
    </div>
  )
}
