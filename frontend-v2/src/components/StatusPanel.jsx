import React, { useEffect, useState, useRef } from 'react';
import { Shield, MapPin, Navigation, Search, Check, X, RefreshCw, ChevronDown } from 'lucide-react';
import InstallPwaButton from './InstallPwaButton';

export default function StatusPanel({ 
  activeLocation, 
  onLocationChange
}) {
  const [servers, setServers] = useState({
    food: 'pending',
    instamart: 'pending',
    dineout: 'pending'
  });
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isMcpOpen, setIsMcpOpen] = useState(false);
  const mcpDropdownRef = useRef(null);
  const [savedAddresses, setSavedAddresses] = useState([]);
  const [isDetectingGps, setIsDetectingGps] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const searchTimeoutRef = useRef(null);

  // Close MCP status dropdown on outside tap
  useEffect(() => {
    if (!isMcpOpen) return;
    const handleOutsideClick = (e) => {
      if (mcpDropdownRef.current && !mcpDropdownRef.current.contains(e.target)) {
        setIsMcpOpen(false);
      }
    };
    document.addEventListener('pointerdown', handleOutsideClick);
    return () => document.removeEventListener('pointerdown', handleOutsideClick);
  }, [isMcpOpen]);

  // 1. Initial Live Location Auto-Detection
  useEffect(() => {
    // If no active location set yet, detect live GPS
    if (!activeLocation) {
      detectLiveGps();
    }
    fetchSavedAddresses();

    // Poll MCP server statuses
    const fetchStatus = async () => {
      try {
        const res = await fetch('/mcp/status');
        const data = await res.json();
        if (data.servers) {
          const parseServerStatus = (s) => {
            if (!s) return 'disconnected';
            if (typeof s === 'object') return s.initialized ? 'connected' : 'disconnected';
            if (typeof s === 'string') return s;
            return 'disconnected';
          };
          setServers({
            food: parseServerStatus(data.servers.food),
            instamart: parseServerStatus(data.servers.instamart),
            dineout: parseServerStatus(data.servers.dineout)
          });
        }
      } catch (err) {
        console.error('Failed to fetch status', err);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  // Fetch saved addresses from Swiggy
  const fetchSavedAddresses = async () => {
    try {
      const res = await fetch('/addresses');
      const data = await res.json();
      const list = data?.data?.addresses || data?.addresses || [];
      setSavedAddresses(list);
      
      // If GPS wasn't detected and no active location, default to first saved address
      if (!activeLocation && list.length > 0) {
        const first = list[0];
        const line = first.addressLine || first.fullAddress || '';
        const parts = line.split(',').map(s => s.trim()).filter(Boolean);
        const label = parts.length > 1 ? `${parts[0]}, ${parts[1]}` : (parts[0] || first.label || 'Saved Address');
        onLocationChange?.({
          label: `${first.addressCategory || 'Saved'}: ${label}`,
          addressLine: line,
          addressId: first.id,
          city: first.city || '',
          isLiveGps: false,
        });
      }
    } catch (e) {
      console.warn('Could not fetch saved addresses:', e);
    }
  };

  // Browser Geolocation Detection (with localStorage cache for reverse-geocode)
  const detectLiveGps = () => {
    if (!navigator.geolocation) {
      console.warn('Geolocation not supported by browser');
      fetchSavedAddresses();
      return;
    }

    setIsDetectingGps(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        const cacheKey = `geo_cache_${lat.toFixed(3)}_${lng.toFixed(3)}`;

        // Check localStorage cache first
        try {
          const cached = localStorage.getItem(cacheKey);
          if (cached) {
            const locObj = JSON.parse(cached);
            locObj.latitude = lat;
            locObj.longitude = lng;
            onLocationChange?.(locObj);
            setIsDetectingGps(false);
            setIsModalOpen(false);
            return;
          }
        } catch {}

        try {
          const res = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`,
            { headers: { 'User-Agent': 'SwiggyMCPOrchestrator/1.0' } }
          );
          const geo = await res.json();
          const a = geo.address || {};
          const locality = a.suburb || a.neighbourhood || a.road || a.residential || a.village || a.town || a.city || 'Current Area';
          const city = a.city || a.state_district || a.state || '';
          const displayLabel = city ? `${locality}, ${city}` : locality;
          
          const locObj = {
            label: displayLabel,
            locality: locality,
            city: city,
            addressLine: geo.display_name,
            postalCode: a.postcode || '',
            latitude: lat,
            longitude: lng,
            isLiveGps: true,
          };
          onLocationChange?.(locObj);
          // Cache the result
          try { localStorage.setItem(cacheKey, JSON.stringify(locObj)); } catch {}
        } catch {
          // Graceful fallback: try to use last known cached location
          let fallbackLabel = `GPS (${lat.toFixed(3)}, ${lng.toFixed(3)})`;
          try {
            // Search for any cached geo result nearby
            for (let i = 0; i < localStorage.length; i++) {
              const k = localStorage.key(i);
              if (k && k.startsWith('geo_cache_')) {
                const cached = JSON.parse(localStorage.getItem(k));
                if (cached?.locality) {
                  fallbackLabel = `📍 Using your last known location: ${cached.locality}`;
                  break;
                }
              }
            }
          } catch {}
          onLocationChange?.({
            label: fallbackLabel,
            latitude: lat,
            longitude: lng,
            isLiveGps: true,
          });
        } finally {
          setIsDetectingGps(false);
          setIsModalOpen(false);
        }
      },
      (err) => {
        console.warn('Browser geolocation denied or unavailable:', err);
        setIsDetectingGps(false);
        fetchSavedAddresses();
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };

  // Search places via Nominatim (AbortController + 700ms debounce)
  const searchAbortRef = useRef(null);
  const handleSearchChange = (e) => {
    const query = e.target.value;
    setSearchQuery(query);

    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    // Abort any in-flight request
    if (searchAbortRef.current) {
      searchAbortRef.current.abort();
      searchAbortRef.current = null;
    }

    if (!query.trim() || query.length < 3) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    searchTimeoutRef.current = setTimeout(async () => {
      const controller = new AbortController();
      searchAbortRef.current = controller;
      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&countrycodes=in&limit=4`,
          { 
            headers: { 'User-Agent': 'SwiggyMCPOrchestrator/1.0' },
            signal: controller.signal 
          }
        );
        const results = await res.json();
        setSearchResults(results || []);
      } catch (err) {
        if (err.name !== 'AbortError') {
          console.warn('Place search error:', err);
        }
      } finally {
        setIsSearching(false);
      }
    }, 700);
  };

  const handleSelectSearchResult = (result) => {
    const parts = result.display_name.split(',').map(s => s.trim()).filter(Boolean);
    const shortName = parts.slice(0, 2).join(', ');
    const cityName = parts.find(p => ['Bengaluru', 'Bangalore', 'Hyderabad', 'Mumbai', 'Delhi', 'Vijayawada', 'Amaravati', 'Chennai', 'Pune'].some(c => p.toLowerCase().includes(c.toLowerCase()))) || parts[1] || '';
    
    onLocationChange?.({
      label: shortName,
      locality: parts[0],
      city: cityName,
      addressLine: result.display_name,
      latitude: parseFloat(result.lat),
      longitude: parseFloat(result.lon),
      isLiveGps: false,
    });
    setIsModalOpen(false);
    setSearchQuery('');
    setSearchResults([]);
  };

  const handleSelectSavedAddress = (addr) => {
    const line = addr.addressLine || addr.fullAddress || '';
    const parts = line.split(',').map(s => s.trim()).filter(Boolean);
    const label = parts.length > 1 ? `${parts[0]}, ${parts[1]}` : (parts[0] || addr.label || 'Saved Address');
    onLocationChange?.({
      label: `${addr.addressCategory || 'Saved'}: ${label}`,
      addressLine: line,
      addressId: addr.id,
      city: addr.city || '',
      isLiveGps: false,
    });
    setIsModalOpen(false);
  };

  const getStatusString = (status) => {
    if (!status) return 'disconnected';
    if (typeof status === 'object') {
      return status.initialized ? 'connected' : 'disconnected';
    }
    if (typeof status === 'string') return status;
    return 'disconnected';
  };

  const getStatusClass = (status) => {
    const s = getStatusString(status);
    if (s === 'connected') return 'connected';
    if (s === 'degraded' || s === 'pending') return 'pending';
    return 'disconnected';
  };

  const getOverallMcpStatus = () => {
    const vals = Object.values(servers).map(getStatusString);
    if (vals.length > 0 && vals.every(v => v === 'connected')) return 'connected';
    if (vals.some(v => v === 'degraded' || v === 'pending')) return 'pending';
    return 'disconnected';
  };

  return (
    <>
      <div className="header-panel collapsed-header">
        {/* Compact Location Pill */}
        <button 
          type="button"
          className="location-pill location-pill-interactive" 
          title="Click to detect live GPS or choose delivery location"
          onClick={() => setIsModalOpen(true)}
        >
          {activeLocation?.isLiveGps ? (
            <span className="live-dot" title="Live GPS Active" />
          ) : (
            <MapPin size={13} color="var(--orange-primary)" />
          )}
          <span className="location-pill-text">
            {activeLocation?.label || (isDetectingGps ? 'Detecting GPS...' : 'Select Location')}
          </span>
          <span className="location-change-tag">Change</span>
        </button>

        <div className="header-actions-cluster">
          <InstallPwaButton />

          {/* Single Small MCP Status Indicator (Expands on Tap) */}
          <div className="mcp-dropdown-container" ref={mcpDropdownRef}>
            <button 
              type="button"
              className={`mcp-compact-badge ${isMcpOpen ? 'active' : ''}`}
              onClick={() => setIsMcpOpen(prev => !prev)}
              title="Tap to see MCP server status"
              aria-label="MCP Server Status"
              aria-expanded={isMcpOpen}
            >
              <div className={`status-dot ${getOverallMcpStatus()}`}></div>
              <span className="mcp-badge-label">MCP</span>
              <ChevronDown size={12} className={`mcp-chevron ${isMcpOpen ? 'rotated' : ''}`} />
            </button>

            {isMcpOpen && (
              <div className="mcp-popover-menu">
                <div className="mcp-popover-header">
                  <Shield size={13} color="var(--orange-primary)" />
                  <span>ACTIVE MCP SERVERS</span>
                </div>
                <div className="mcp-popover-list">
                  {Object.entries(servers).map(([name, status]) => (
                    <div key={name} className="mcp-popover-item">
                      <div className={`status-dot ${getStatusClass(status)}`}></div>
                      <span className="popover-server-name">{name}</span>
                      <span className={`popover-server-status ${getStatusClass(status)}`}>{getStatusString(status)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Location Selector Modal */}
      {isModalOpen && (
        <div className="location-modal-backdrop" onClick={() => setIsModalOpen(false)}>
          <div className="location-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="location-modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Navigation size={18} color="var(--orange-primary)" />
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700 }}>Choose Delivery Location</h3>
              </div>
              <button className="modal-close-btn" onClick={() => setIsModalOpen(false)}>
                <X size={16} />
              </button>
            </div>

            <div className="location-modal-body">
              {/* Option 1: Live GPS Detection */}
              <button 
                type="button" 
                className="live-detect-action-btn"
                onClick={detectLiveGps}
                disabled={isDetectingGps}
              >
                <div className="live-detect-icon-wrapper">
                  <Navigation size={18} className={isDetectingGps ? 'spin' : ''} />
                </div>
                <div style={{ flex: 1, textAlign: 'left' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontWeight: 700, fontSize: '14px', color: '#ffffff' }}>Detect Current GPS Location</span>
                    <span className="live-badge">LIVE</span>
                  </div>
                  <div style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.75)', marginTop: '2px' }}>
                    {isDetectingGps ? 'Pinpointing high-accuracy GPS coordinates...' : 'Using browser high-accuracy device location'}
                  </div>
                </div>
              </button>

              {/* Option 2: Search Custom Location */}
              <div style={{ marginTop: '14px' }}>
                <div className="location-search-box">
                  <Search size={15} color="rgba(255, 255, 255, 0.6)" />
                  <input
                    type="text"
                    placeholder="Search city, area or street (e.g. Indiranagar, Bengaluru)..."
                    value={searchQuery}
                    onChange={handleSearchChange}
                    className="location-search-input"
                  />
                  {isSearching && <RefreshCw size={14} className="spin" color="var(--orange-primary)" />}
                </div>

                {searchResults.length > 0 && (
                  <div className="location-search-results">
                    {searchResults.map((r, idx) => (
                      <div 
                        key={idx} 
                        className="location-search-item"
                        onClick={() => handleSelectSearchResult(r)}
                      >
                        <MapPin size={13} color="var(--orange-primary)" style={{ flexShrink: 0, marginTop: '2px' }} />
                        <span style={{ fontSize: '12px', lineHeight: '1.4', color: '#ffffff' }}>{r.display_name}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Option 3: Saved Swiggy Addresses */}
              {savedAddresses.length > 0 && (
                <div style={{ marginTop: '16px' }}>
                  <div style={{ fontSize: '11px', fontWeight: 700, color: 'rgba(255, 255, 255, 0.65)', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.5px' }}>
                    Saved Swiggy Addresses ({savedAddresses.length})
                  </div>
                  <div className="saved-addresses-list">
                    {savedAddresses.map((addr) => {
                      const isSelected = activeLocation?.addressId === addr.id;
                      return (
                        <div 
                          key={addr.id}
                          className={`saved-address-card ${isSelected ? 'selected' : ''}`}
                          onClick={() => handleSelectSavedAddress(addr)}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span className="address-category-tag">{addr.addressCategory || addr.label || 'Home'}</span>
                            <span style={{ fontSize: '13px', fontWeight: 600, color: '#ffffff' }}>
                              {addr.userName ? `${addr.userName} • ` : ''}{addr.addressTag || 'Delivery'}
                            </span>
                          </div>
                          <div style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.72)', marginTop: '4px', lineHeight: '1.4' }}>
                            {addr.addressLine || addr.fullAddress}
                          </div>
                          {isSelected && (
                            <div className="selected-indicator">
                              <Check size={12} color="#062013" strokeWidth={3} />
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
