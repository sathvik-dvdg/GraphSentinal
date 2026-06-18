// [Windows] GraphSentinel
import React from 'react';

export default function FeaturesBentoGrid() {
  return (
    <section className="flex flex-col gap-8 mt-24 mb-12 z-10 relative max-w-5xl mx-auto w-full px-4" id="features">
      <div className="flex flex-col gap-2 items-center text-center">
        <h2 className="text-2xl font-bold text-on-surface">Architectural Integrity</h2>
        <p className="text-sm text-on-surface-variant max-w-2xl">Engineered for absolute resilience. Our systems proactively neutralize threats before they breach the perimeter.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Card 1: 24/7 Monitoring */}
        <div className="glass-card rounded-xl p-6 flex flex-col gap-4 md:col-span-2 group hover:border-primary-container/50 transition-colors items-center text-center">
          <div className="w-12 h-12 rounded-lg bg-surface-container-high border border-outline-variant/30 flex items-center justify-center text-primary-container group-hover:scale-110 transition-transform">
            <span className="material-symbols-outlined">radar</span>
          </div>
          <div className="flex flex-col items-center">
            <h3 className="text-xl font-semibold text-on-surface mb-2">24/7 Active Monitoring</h3>
            <p className="text-sm text-on-surface-variant">Continuous surveillance of your network perimeter utilizing advanced heuristic analysis and machine learning models to detect anomalies instantly.</p>
          </div>
          {/* Decorative technical visualizer */}
          <div className="mt-auto pt-6 border-t border-outline-variant/20 flex gap-1 h-12 items-end opacity-70">
            <div className="w-2 bg-primary-container/80 h-[20%]"></div>
            <div className="w-2 bg-primary-container/60 h-[50%]"></div>
            <div className="w-2 bg-primary-container h-[80%]"></div>
            <div className="w-2 bg-primary-container/40 h-[30%]"></div>
            <div className="w-2 bg-primary-container/90 h-[100%]"></div>
            <div className="w-2 bg-primary-container/50 h-[60%]"></div>
            <div className="w-2 bg-primary-container/70 h-[40%]"></div>
            <div className="w-2 bg-primary-container/30 h-[90%]"></div>
          </div>
        </div>

        {/* Card 2: Zero-Trust */}
        <div className="glass-card rounded-xl p-6 flex flex-col gap-4 group hover:border-primary-container/50 transition-colors items-center text-center">
          <div className="w-12 h-12 rounded-lg bg-surface-container-high border border-outline-variant/30 flex items-center justify-center text-primary-container group-hover:scale-110 transition-transform">
            <span className="material-symbols-outlined">lock_person</span>
          </div>
          <div className="flex flex-col items-center">
            <h3 className="text-xl font-semibold text-on-surface mb-2">Zero-Trust Architecture</h3>
            <p className="text-sm text-on-surface-variant">Verify explicitly. Every access request is fully authenticated, authorized, and encrypted before granting access, regardless of origin.</p>
          </div>
          <div className="mt-auto pt-4 flex flex-wrap gap-2 justify-center">
            <span className="px-2 py-1 bg-surface-container-highest rounded text-on-surface font-mono text-[10px] uppercase border border-outline-variant/50">MFA Required</span>
            <span className="px-2 py-1 bg-surface-container-highest rounded text-on-surface font-mono text-[10px] uppercase border border-outline-variant/50">End-to-End</span>
          </div>
        </div>

        {/* Card 3: Encrypted Core */}
        <div className="glass-card rounded-xl p-6 flex flex-col gap-4 group hover:border-primary-container/50 transition-colors items-center text-center">
          <div className="w-12 h-12 rounded-lg bg-surface-container-high border border-outline-variant/30 flex items-center justify-center text-primary-container group-hover:scale-110 transition-transform">
            <span className="material-symbols-outlined">enhanced_encryption</span>
          </div>
          <div className="flex flex-col items-center">
            <h3 className="text-xl font-semibold text-on-surface mb-2">Military-Grade Encryption</h3>
            <p className="text-sm text-on-surface-variant">Data at rest and in transit is secured using AES-256 standards, rendering intercepted payloads completely useless to attackers.</p>
          </div>
        </div>

        {/* Card 4: Threat Intel */}
        <div className="glass-card rounded-xl p-6 flex flex-col gap-4 md:col-span-2 group hover:border-primary-container/50 transition-colors relative overflow-hidden items-center text-center">
          {/* Decorative background grid in card */}
          <div className="absolute inset-0 opacity-10 pointer-events-none" style={{ backgroundImage: "linear-gradient(to right, #00f2ff 1px, transparent 1px), linear-gradient(to bottom, #00f2ff 1px, transparent 1px)", backgroundSize: "10px 10px", maskImage: "linear-gradient(to right, black, transparent)" }}></div>
          
          <div className="w-12 h-12 rounded-lg bg-surface-container-high border border-outline-variant/30 flex items-center justify-center text-primary-container group-hover:scale-110 transition-transform z-10">
            <span className="material-symbols-outlined">public</span>
          </div>
          <div className="z-10 relative flex flex-col items-center">
            <h3 className="text-xl font-semibold text-on-surface mb-2">Global Threat Intel</h3>
            <p className="text-sm text-on-surface-variant max-w-lg">Leveraging a decentralized network of security sensors worldwide to anticipate and block zero-day vulnerabilities before they propagate to your specific instance.</p>
          </div>
        </div>
      </div>
    </section>
  );
}
