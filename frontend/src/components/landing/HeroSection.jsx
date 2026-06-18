import React from 'react';
import { motion } from 'framer-motion';
import Shield3D from './Shield3D';

export default function HeroSection() {
  return (
    <section className="flex flex-col items-center text-center gap-8 relative mt-16 pt-16">
      {/* Shield Visualizer */}
      <div className="relative w-64 h-64 flex items-center justify-center mb-4 group cursor-default">
        {/* Outer glowing rings */}
        <div className="absolute inset-0 rounded-full border border-primary-container/20 animate-[spin_10s_linear_infinite]" />
        <div className="absolute inset-4 rounded-full border border-primary-container/40 border-dashed animate-[spin_15s_linear_infinite_reverse]" />
        <div className="absolute inset-8 rounded-full bg-primary-container/5 blur-xl group-hover:bg-primary-container/10 transition-colors duration-500" />
        
        {/* Core Shield 3D */}
        <Shield3D />
        
        {/* Decorative data points */}
        <div className="absolute w-2 h-2 bg-primary-container top-0 left-1/2 -translate-x-1/2 shadow-[0_0_8px_#00f2ff]" />
        <div className="absolute w-2 h-2 bg-primary-container bottom-0 left-1/2 -translate-x-1/2 shadow-[0_0_8px_#00f2ff]" />
      </div>

      {/* Hero Copy */}
      <div className="flex flex-col gap-4 max-w-2xl z-10 relative">
        <motion.div 
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center justify-center gap-2 px-3 py-1 rounded-full border border-primary-container/30 bg-surface-container/50 backdrop-blur-sm mx-auto mb-2"
        >
          <span className="w-2 h-2 rounded-full bg-primary-container animate-pulse shadow-[0_0_5px_#00f2ff]" />
          <span className="font-mono text-[12px] text-primary-container uppercase tracking-wider">System Status: Optimal</span>
        </motion.div>

        <motion.h1 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-[28px] md:text-[48px] md:leading-[56px] font-bold text-on-surface text-glow"
        >
          Your Digital Fortress,<br/>Secured.
        </motion.h1>

        <motion.p 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-[16px] leading-[24px] text-on-surface-variant max-w-xl mx-auto"
        >
          Deploy uncompromising protection with our advanced zero-trust architecture. Monitor threats in real-time across your entire infrastructure.
        </motion.p>
      </div>

      {/* Primary CTA */}
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, delay: 0.3 }}
        className="flex flex-col sm:flex-row gap-4 mt-4 z-10 relative"
      >
        <button className="bg-primary-container text-on-primary-container font-mono text-[12px] px-8 py-4 rounded-lg font-bold tracking-wider hover:bg-primary transition-all active:scale-95 glow-accent uppercase">
          Start Protection
        </button>
        <button className="bg-transparent border border-primary-container text-primary-container font-mono text-[12px] px-8 py-4 rounded-lg hover:bg-primary-container/10 transition-all active:scale-95 uppercase flex items-center justify-center gap-2">
          <span className="material-symbols-outlined text-[18px]">terminal</span>
          View Docs
        </button>
      </motion.div>
    </section>
  );
}
