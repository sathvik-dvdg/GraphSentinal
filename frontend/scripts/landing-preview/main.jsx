// Dev-only entry that mounts the landing page by itself, with the app's global
// stylesheet and a router but none of the app shell or auth. Use it to work on
// or check the landing page when the rest of the app is not running:
//
//   npm run dev  ->  http://localhost:5173/scripts/landing-preview/index.html
//
// Add ?live to see the live 3D scene through the opening cinematic.
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import '../../src/styles/globals.css'
import LandingView from '../../src/components/landing/LandingView'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/login" element={<p id="login-stub">Login page (stub)</p>} />
        <Route path="*" element={<LandingView />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
