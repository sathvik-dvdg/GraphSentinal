// [Windows] GraphSentinel
import React from 'react';

export default function Footer() {
  return (
    <footer className="bg-surface-container-lowest border-t border-outline-variant/20 flex flex-col items-center gap-4 py-8 px-5 w-full mt-auto z-10">
      <div className="flex flex-col md:flex-row gap-4 items-center justify-between w-full max-w-[1200px] mb-4">
        <div className="flex items-center gap-2 text-on-surface-variant opacity-80">
          <span className="material-symbols-outlined text-[18px]">terminal</span>
          <span className="font-mono text-[12px] tracking-widest uppercase">Fortress_OS_v2.4.1</span>
        </div>
        <div className="flex gap-8">
          <a className="font-mono text-[12px] text-on-surface-variant hover:text-primary-container transition-colors opacity-80 hover:opacity-100" href="#">Privacy Policy</a>
          <a className="font-mono text-[12px] text-on-surface-variant hover:text-primary-container transition-colors opacity-80 hover:opacity-100" href="#">Terms of Service</a>
          <a className="font-mono text-[12px] text-on-surface-variant hover:text-primary-container transition-colors opacity-80 hover:opacity-100 flex items-center gap-1" href="#">
            Security Disclosure
            <span className="material-symbols-outlined text-[14px]">lock</span>
          </a>
        </div>
      </div>
      <div className="font-mono text-[12px] text-on-surface-variant opacity-60">
        © 2024 FORTRESS_OS. ENCRYPTED_CONNECTION.
      </div>
    </footer>
  );
}
