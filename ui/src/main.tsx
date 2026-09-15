import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App } from './App'
import './styles.css'

declare global {
  interface Window {
    __GITPULSE_MOUNT__?: string
  }
}

const mount = window.__GITPULSE_MOUNT__ ?? '/git'
const basename = mount.endsWith('/') ? mount.slice(0, -1) : mount

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter basename={basename || '/'}>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
