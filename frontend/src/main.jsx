import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { SplashScreen } from '@capacitor/splash-screen'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Instantly dismiss native splash screen the moment DOM renders
SplashScreen.hide().catch(() => {});
