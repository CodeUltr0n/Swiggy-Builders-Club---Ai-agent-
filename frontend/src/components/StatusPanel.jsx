import React, { useEffect, useState } from 'react';
import { Server, Shield } from 'lucide-react';

export default function StatusPanel() {
  const [servers, setServers] = useState({
    food: 'pending',
    instamart: 'pending',
    dineout: 'pending'
  });

  useEffect(() => {
    // Poll MCP status every 5s
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

  const getStatusClass = (status) => {
    if (status === 'connected') return 'connected';
    if (status === 'degraded') return 'degraded';
    return 'disconnected';
  };

  return (
    <div className="header-panel">
      <div className="brand-title">
        <Shield size={18} />
        SWIGGY MCP CONTROL PLANE
      </div>
      
      <div className="mcp-status-group">
        {Object.entries(servers).map(([name, status]) => (
          <div key={name} className="mcp-status-item">
            <div className={`status-dot ${getStatusClass(status)}`}></div>
            <span style={{ textTransform: 'capitalize' }}>{name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
