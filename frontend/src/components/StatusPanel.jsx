import React, { useEffect, useState, useRef } from 'react';
import { Shield, MapPin, Navigation, Search, Check, X, RefreshCw } from 'lucide-react';

export default function StatusPanel({ activeLocation, onLocationChange }) {
  const [servers, setServers] = useState({
    food: 'pending',
    instamart: 'pending',
    dineout: 'pending'
  });
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [savedAddresses, setSavedAddresses] = useState([]);
  const [isDetectingGps, setIsDetectingGps] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const searchTimeoutRef = useRef(null);

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
          setServers({
            food: data.servers.food || 'disconnected',
            instamart: data.servers.instamart || 'disconnected',
            dineout: data.servers.dineout || 'disconnected'
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

  // Browser Geolocation Detection
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
        } catch {
          onLocationChange?.({
            label: `GPS (${lat.toFixed(3)}, ${lng.toFixed(3)})`,
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

  // Search places via Nominatim
  const handleSearchChange = (e) => {
    const query = e.target.value;
    setSearchQuery(query);

    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    if (!query.trim() || query.length < 3) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    searchTimeoutRef.current = setTimeout(async () => {
      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&countrycodes=in&limit=4`,
          { headers: { 'User-Agent': 'SwiggyMCPOrchestrator/1.0' } }
        );
        const results = await res.json();
        setSearchResults(results || []);
      } catch (err) {
        console.warn('Place search error:', err);
      } finally {
        setIsSearching(false);
      }
    }, 400);
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

  const getStatusClass = (status) => {
    if (status === 'connected') return 'connected';
    if (status === 'degraded') return 'degraded';
    return 'disconnected';
  };

  return (
    <>
      <div className="header-panel">
        <div className="brand-title">
          <Shield size={18} />
          SWIGGY MCP CONTROL PLANE
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap', justifyContent: 'center' }}>
          {/* Interactive Location Pill */}
          <button 
            type="button"
            className="location-pill location-pill-interactive" 
            title="Click to detect live GPS or choose delivery location"
            onClick={() => setIsModalOpen(true)}
          >
            {activeLocation?.isLiveGps ? (
              <span className="live-dot" title="Live GPS Active" />
            ) : (
              <MapPin size={13} color="#ea580c" />
            )}
            <span className="location-pill-text">
              {activeLocation?.label || (isDetectingGps ? 'Detecting Live GPS...' : 'Select Location')}
            </span>
            <span className="location-change-tag">Change</span>
          </button>

          <div className="mcp-status-group">
            {Object.entries(servers).map(([name, status]) => (
              <div key={name} className="mcp-status-item">
                <div className={`status-dot ${getStatusClass(status)}`}></div>
                <span style={{ textTransform: 'capitalize' }}>{name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Location Selector Modal */}
      {isModalOpen && (
        <div className="location-modal-backdrop" onClick={() => setIsModalOpen(false)}>
          <div className="location-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="location-modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Navigation size={18} color="#ea580c" />
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
                  <Navigation size={16} className={isDetectingGps ? 'spin' : ''} />
                </div>
                <div style={{ textAlign: 'left', flex: 1 }}>
                  <div style={{ fontWeight: 700, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    Detect My Current Location
                    <span className="live-badge">GPS</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                    Using your device's live hardware location
                  </div>
                </div>
                {activeLocation?.isLiveGps && <Check size={16} color="#10b981" />}
              </button>

              {/* Option 2: Search Custom Location */}
              <div style={{ marginTop: '14px' }}>
                <div className="location-search-box">
                  <Search size={14} color="#94a3b8" />
                  <input
                    type="text"
                    placeholder="Search city, area or street (e.g. Indiranagar, Bengaluru)..."
                    value={searchQuery}
                    onChange={handleSearchChange}
                    className="location-search-input"
                  />
                  {isSearching && <RefreshCw size={14} className="spin" color="#ea580c" />}
                </div>

                {searchResults.length > 0 && (
                  <div className="location-search-results">
                    {searchResults.map((r, idx) => (
                      <div 
                        key={idx} 
                        className="location-search-item"
                        onClick={() => handleSelectSearchResult(r)}
                      >
                        <MapPin size={13} color="#ea580c" style={{ flexShrink: 0, marginTop: '2px' }} />
                        <span style={{ fontSize: '12px', lineHeight: '1.4' }}>{r.display_name}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Option 3: Saved Swiggy Addresses */}
              {savedAddresses.length > 0 && (
                <div style={{ marginTop: '16px' }}>
                  <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.5px' }}>
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
                            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                              {addr.userName ? `${addr.userName} • ` : ''}{addr.addressTag || 'Delivery'}
                            </span>
                          </div>
                          <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px', lineHeight: '1.3' }}>
                            {addr.addressLine || addr.fullAddress}
                          </div>
                          {isSelected && (
                            <div className="selected-indicator">
                              <Check size={12} color="#fff" />
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
