// [Windows] GraphSentinel
import React from 'react';
import Navbar from '../components/landing/Navbar';
import HeroSection from '../components/landing/HeroSection';
import FeaturesBentoGrid from '../components/landing/FeaturesBentoGrid';
import Footer from '../components/landing/Footer';

export default function LandingPage() {
  return (
    <div className="antialiased min-h-screen flex flex-col relative overflow-x-hidden w-full">
      {/* Ambient Background Lighting */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden flex items-center justify-center">
        <div className="w-[800px] h-[800px] rounded-full bg-primary-container/5 blur-[120px] opacity-50 absolute top-[-200px] right-[-200px]"></div>
        <div className="w-[600px] h-[600px] rounded-full bg-primary/5 blur-[100px] opacity-30 absolute bottom-[-100px] left-[-100px]"></div>
      </div>
      
      {/* Background Texture Image */}
      <div className="fixed inset-0 z-0 opacity-10 bg-cover bg-center hero-bg-image pointer-events-none mix-blend-screen" style={{ backgroundImage: "url('https://lh3.googleusercontent.com/aida-public/AB6AXuDfAHECUfGrqrbbHXuwRToMa1MY1QVowH2ylPVFhZftqt4x3DRSVxzYGtKhsbBfMbz2bWgSiWslnUom-YcR4-clvdQKDpBSRlu9Jt_FdJDq5xOTD7wCp6HF-zej7Zcd4En90YeClMGIILxZOLzIsx-bpD7x6eYylXg2UbxwKHNcT9CynF3Gc_S-K5i1_IgRUnVG7rilEtTPpTrxUP3mw7jaJUthqU0Bmil5R20QurE7fjF6lMTfDRSzt_D-q-UOXunUThteareYYUTT')" }}></div>
      
      <Navbar />

      {/* Main Content */}
      <main className="flex-grow z-10 pt-16 pb-24 px-5 max-w-[1200px] mx-auto w-full flex flex-col gap-24">
        <HeroSection />
        <FeaturesBentoGrid />
      </main>

      <Footer />
    </div>
  );
}
