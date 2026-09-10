import React, { useState, useEffect } from 'react';
import { Download, Share2, PlusSquare, X, Smartphone, Check, Sparkles } from 'lucide-react';

/**
 * InstallPwaButton
 * Professional PWA installation handler:
 * - Detects standalone/already-installed mode (hides automatically)
 * - Captures Chromium beforeinstallprompt for 1-tap native installation
 * - Detects iOS devices and shows a clean, step-by-step "Add to Home Screen" visual guide
 * - Matches luxury obsidian-emerald crystal glass styling
 */
export default function InstallPwaButton({ className = '', variant = 'header' }) {
  const [deferredPrompt, setDeferredPrompt] = useState(
    typeof window !== 'undefined' ? window.deferredPrompt || null : null
  );
  const [isStandalone, setIsStandalone] = useState(false);
  const [isIos, setIsIos] = useState(false);
  const [showIosModal, setShowIosModal] = useState(false);
  const [showDesktopTip, setShowDesktopTip] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);

  useEffect(() => {
    // 1. Check if already installed / running in standalone window
    const checkStandalone = () => {
      const isStandaloneMedia = window.matchMedia('(display-mode: standalone)').matches;
      const isIosStandalone = window.navigator.standalone === true;
      return isStandaloneMedia || isIosStandalone;
    };

    if (checkStandalone()) {
      setIsStandalone(true);
      return;
    }

    // 2. Check if global prompt already captured
    if (window.deferredPrompt) {
      setDeferredPrompt(window.deferredPrompt);
    }

    const handlePromptReady = () => {
      if (window.deferredPrompt) {
        setDeferredPrompt(window.deferredPrompt);
      }
    };
    window.addEventListener('pwa-prompt-ready', handlePromptReady);

    // 3. Detect iOS device
    const userAgent = window.navigator.userAgent.toLowerCase();
    const isIosDevice = /iphone|ipad|ipod/.test(userAgent) && !window.MSStream;
    setIsIos(isIosDevice);

    // 4. Capture Chromium beforeinstallprompt if triggered after mount
    const handleBeforeInstallPrompt = (e) => {
      e.preventDefault();
      window.deferredPrompt = e;
      setDeferredPrompt(e);
    };

    // 5. Listen for successful install
    const handleAppInstalled = () => {
      setIsInstalled(true);
      window.deferredPrompt = null;
      setDeferredPrompt(null);
      setTimeout(() => setIsStandalone(true), 3000);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleAppInstalled);

    return () => {
      window.removeEventListener('pwa-prompt-ready', handlePromptReady);
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleAppInstalled);
    };
  }, []);

  // If already running as an installed standalone app, hide the button
  if (isStandalone) {
    return null;
  }

  const handleInstallClick = async () => {
    const promptEvent = deferredPrompt || window.deferredPrompt;

    // Direct 1-Click Native System Install Prompt (Android & Desktop Chrome/Edge)
    if (promptEvent) {
      promptEvent.prompt();
      const choiceResult = await promptEvent.userChoice;
      if (choiceResult?.outcome === 'accepted') {
        setIsInstalled(true);
        window.deferredPrompt = null;
        setDeferredPrompt(null);
      }
      return;
    }

    // If iOS Safari (Apple restricts direct JS prompt, shows 2-step Add to Home Screen)
    if (isIos) {
      setShowIosModal(true);
      return;
    }

    // Desktop/Other fallback if browser hasn't granted install prompt yet
    setShowDesktopTip(true);
  };

  return (
    <>
      <button
        type="button"
        onClick={handleInstallClick}
        className={`install-pwa-btn ${variant === 'chip' ? 'install-pwa-chip' : ''} ${className}`}
        title="Install Swiggy MCP to your home screen or desktop"
        aria-label="Install App"
      >
        {isInstalled ? (
          <>
            <Check size={13} color="#34d399" strokeWidth={2.5} />
            <span className="install-pwa-text">Installed</span>
          </>
        ) : (
          <>
            <div className="install-icon-dot-wrap">
              <Download size={13} className="install-pwa-icon" />
              <span className="install-pulse-glow" />
            </div>
            <span className="install-pwa-text">Install App</span>
          </>
        )}
      </button>

      {/* iOS Instructions Modal */}
      {showIosModal && (
        <div className="location-modal-backdrop" onClick={() => setShowIosModal(false)}>
          <div className="pwa-guide-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="pwa-guide-header">
              <div className="pwa-guide-title-box">
                <Smartphone size={16} color="#34d399" />
                <h3>Install on iPhone / iPad</h3>
              </div>
              <button
                type="button"
                className="pwa-close-btn"
                onClick={() => setShowIosModal(false)}
                aria-label="Close"
              >
                <X size={14} />
              </button>
            </div>

            <div className="pwa-guide-body">
              <p className="pwa-guide-intro">
                Install <strong>Swiggy MCP</strong> to your iOS Home Screen for instant full-screen access:
              </p>

              <div className="pwa-step-card">
                <div className="pwa-step-number">1</div>
                <div className="pwa-step-content">
                  <div className="pwa-step-heading">
                    Tap the <strong>Share</strong> button
                  </div>
                  <div className="pwa-step-sub">
                    Located in Safari's bottom toolbar <Share2 size={15} className="inline-ios-icon" />
                  </div>
                </div>
              </div>

              <div className="pwa-step-card">
                <div className="pwa-step-number">2</div>
                <div className="pwa-step-content">
                  <div className="pwa-step-heading">
                    Select <strong>"Add to Home Screen"</strong>
                  </div>
                  <div className="pwa-step-sub">
                    Scroll down and look for <PlusSquare size={15} className="inline-ios-icon" />
                  </div>
                </div>
              </div>

              <div className="pwa-step-card">
                <div className="pwa-step-number">3</div>
                <div className="pwa-step-content">
                  <div className="pwa-step-heading">
                    Tap <strong>"Add"</strong> in the top right
                  </div>
                  <div className="pwa-step-sub">
                    Swiggy MCP will appear as a full-screen app icon!
                  </div>
                </div>
              </div>

              <div className="pwa-features-pill">
                <Sparkles size={12} color="#34d399" />
                <span>0 MB Download &bull; Instant Launch &bull; Offline Ready</span>
              </div>

              <button
                type="button"
                className="pwa-guide-gotit-btn"
                onClick={() => setShowIosModal(false)}
              >
                Got It
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Desktop Tip Modal */}
      {showDesktopTip && (
        <div className="location-modal-backdrop" onClick={() => setShowDesktopTip(false)}>
          <div className="pwa-guide-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="pwa-guide-header">
              <div className="pwa-guide-title-box">
                <Download size={16} color="#34d399" />
                <h3>Install Swiggy MCP</h3>
              </div>
              <button
                type="button"
                className="pwa-close-btn"
                onClick={() => setShowDesktopTip(false)}
                aria-label="Close"
              >
                <X size={14} />
              </button>
            </div>

            <div className="pwa-guide-body">
              <p className="pwa-guide-intro">
                You can install Swiggy MCP as a standalone desktop app directly from your browser:
              </p>

              <div className="pwa-step-card">
                <div className="pwa-step-number">1</div>
                <div className="pwa-step-content">
                  <div className="pwa-step-heading">Look for the Install Icon in the URL bar</div>
                  <div className="pwa-step-sub">
                    Click the <strong>Install</strong> or <strong>⊕</strong> icon on the right side of Chrome or Edge address bar.
                  </div>
                </div>
              </div>

              <div className="pwa-step-card">
                <div className="pwa-step-number">2</div>
                <div className="pwa-step-content">
                  <div className="pwa-step-heading">Or open the Browser Menu</div>
                  <div className="pwa-step-sub">
                    Click <strong>⋮ &rarr; Save and share &rarr; Install Swiggy MCP</strong>.
                  </div>
                </div>
              </div>

              <div className="pwa-features-pill">
                <Sparkles size={12} color="#34d399" />
                <span>Runs in dedicated app window &bull; Dock & Taskbar support</span>
              </div>

              <button
                type="button"
                className="pwa-guide-gotit-btn"
                onClick={() => setShowDesktopTip(false)}
              >
                Got It
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
