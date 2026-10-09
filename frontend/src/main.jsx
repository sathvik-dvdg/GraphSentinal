import { ClerkProvider } from '@clerk/react';
// [Windows] GraphSentinel — Susheep
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/globals.css'
import { GS } from './constants/colors'

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

// Clerk draws its own sign-in card and account menu, so it is told the landing
// page's colours and faces (from src/constants/colors.js).
const CLERK_APPEARANCE = {
  variables: {
    colorPrimary: GS.danger,
    colorText: GS.text,
    colorTextSecondary: GS.textMuted,
    colorBackground: GS.surface,
    colorInputBackground: GS.base,
    colorInputText: GS.text,
    colorDanger: GS.danger,
    colorSuccess: GS.success,
    fontFamily: "'Hanken Grotesk', system-ui, sans-serif",
    borderRadius: '0.625rem',
  },
}

if (!PUBLISHABLE_KEY) {
  throw new Error("Missing Publishable Key")
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ClerkProvider publishableKey={PUBLISHABLE_KEY} afterSignOutUrl="/" appearance={CLERK_APPEARANCE}>
      <App />
    </ClerkProvider>
  </React.StrictMode>
)