import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Register Service Worker for PWA installability & caching
if ('serviceWorker' in navigator) {
  const registerSW = () => {
    navigator.serviceWorker.register('/sw.js').catch((err) => {
      console.warn('PWA service worker registration skipped:', err);
    });
  };

  if (document.readyState === 'complete') {
    registerSW();
  } else {
    window.addEventListener('load', registerSW);
  }
}

