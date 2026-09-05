import React, { useState, useEffect } from 'react';
import { Activity, CheckCircle2, ChevronRight, Server } from 'lucide-react';

export default function OrchestrationTimeline({ activeServer, rankings, query }) {
  const [stage, setStage] = useState(0);

  // Animate through the stages
  useEffect(() => {
    if (stage < 5) {
      const timer = setTimeout(() => {
        setStage(s => s + 1);
      }, 600); // 600ms per stage for a dramatic effect
      return () => clearTimeout(timer);
    }
  }, [stage]);

  const servers = [
    { name: 'food', label: 'Food MCP', reason: 'High food intent' },
    { name: 'instamart', label: 'Instamart', reason: 'Grocery intent' },
    { name: 'dineout', label: 'Dineout', reason: 'Dining out intent' }
  ];

  // Derive scores from rankings if available, else mock based on activeServer
  const getScore = (serverName) => {
    if (rankings) {
      const r = rankings.find(x => x[0] === serverName);
      if (r) return Math.min(99, Math.round(r[1] * 40)) + '%'; // roughly scale score to percentage
    }
    return serverName === activeServer ? '94%' : (serverName === 'instamart' ? '21%' : '14%');
  };

  const getReason = () => {
    if (activeServer === 'food') return 'High food intent • Dinner time • Current location supports Food';
    if (activeServer === 'instamart') return 'Grocery items detected • High urgency';
    if (activeServer === 'dineout') return 'Table booking request • Evening slot availability';
    return 'Fallback default routing';
  };

  const isComplete = stage >= 5;

  return (
    <div className="control-plane-card">
      <div className="control-plane-header">
        <Activity size={14} className="text-orange" />
        ORCHESTRATOR
      </div>

      <div className="timeline-step">
        <div className="timeline-label">Intent detected</div>
        <div className="timeline-value">
          {stage >= 1 ? <span className="text-orange font-bold">{(activeServer || 'GENERIC').toUpperCase()}_ORDER</span> : '...'}
        </div>
      </div>

      <div className="timeline-step">
        <div className="timeline-label">Context analysis</div>
        <div className="timeline-value">
          {stage >= 2 ? <CheckCircle2 size={14} className="text-orange inline mr-1" /> : '...'}
        </div>
      </div>

      {stage >= 2 && (
        <div style={{ paddingLeft: '140px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
          <div><CheckCircle2 size={12} className="inline mr-1" /> Location</div>
          <div><CheckCircle2 size={12} className="inline mr-1" /> History signal</div>
          <div><CheckCircle2 size={12} className="inline mr-1" /> Time signal</div>
        </div>
      )}

      <div className="timeline-step">
        <div className="timeline-label">Scoring</div>
        <div className="timeline-value">
          {stage >= 3 ? <span className="text-orange">Complete</span> : (stage === 2 ? 'Computing...' : '...')}
        </div>
      </div>

      {stage >= 4 && (
        <div className="routing-container">
          <div className="control-plane-header">
            <Server size={14} /> ROUTING
          </div>
          
          <div style={{ border: '1px solid var(--border-color)', borderRadius: '6px', padding: '8px' }}>
            {servers.map(s => {
              const isSelected = s.name === activeServer;
              return (
                <div key={s.name} className={`routing-server-row ${isSelected ? 'selected' : ''}`}>
                  <span>{s.label}</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {getScore(s.name)}
                    {isSelected && <span style={{ fontSize: '10px' }}>&larr; SELECTED</span>}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="routing-reasoning">
            <strong>Why {activeServer ? activeServer.charAt(0).toUpperCase() + activeServer.slice(1) : 'this'} MCP?</strong><br />
            {getReason()}
          </div>
        </div>
      )}

      {stage >= 5 && (
        <div style={{ marginTop: '16px', color: 'var(--status-success)', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <ChevronRight size={14} /> Executing {activeServer ? activeServer.toUpperCase() : 'SELECTED'} MCP...
        </div>
      )}

    </div>
  );
}
