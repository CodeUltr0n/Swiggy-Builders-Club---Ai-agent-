import React from 'react';
import OrchestrationTimeline from './OrchestrationTimeline';
import ReactMarkdown from 'react-markdown';
import { Bot, User } from 'lucide-react';

export default function Message({ msg, isLatestAgentMsg }) {
  const isAgent = msg.role === 'agent';

  // Extract restaurants from tool calls to render rich cards if available
  let restaurants = [];
  if (isAgent && msg.tool_calls) {
    const searchRes = msg.tool_calls.find(t => t.tool === 'search_restaurants' || t.tool === 'search_restaurants_dineout');
    if (searchRes && searchRes.result && searchRes.result.data && searchRes.result.data.restaurants) {
      restaurants = searchRes.result.data.restaurants;
    }
  }

  return (
    <div className={`message-row ${isAgent ? 'agent' : 'user'}`}>
      {isAgent && (
        <div style={{ marginRight: '16px', marginTop: '12px' }}>
          <div style={{ backgroundColor: 'var(--orange-primary)', padding: '8px', borderRadius: '50%' }}>
            <Bot size={20} color="white" />
          </div>
        </div>
      )}
      
      <div className="message-bubble">
        {isAgent && isLatestAgentMsg && msg.rankings && (
          <OrchestrationTimeline 
            activeServer={msg.active_server} 
            rankings={msg.rankings} 
            query={msg.content} 
          />
        )}
        
        <div className="agent-text-content">
          {isAgent ? (
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          ) : (
            msg.content
          )}
        </div>

        {restaurants.length > 0 && (
          <div className="cards-carousel">
            {restaurants.map((rest, idx) => (
              <div key={idx} className="entity-card">
                <div className="card-title">{rest.name}</div>
                <div className="card-subtitle">{rest.cuisine || rest.category || 'Restaurant'}</div>
                <div className="card-meta">
                  <span className="card-rating">★ {rest.rating || '4.5'}</span>
                  {rest.distance_km && <span>{rest.distance_km} km</span>}
                </div>
                <div className="card-action">View Details</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {!isAgent && (
        <div style={{ marginLeft: '16px', marginTop: '12px' }}>
          <div style={{ backgroundColor: 'var(--border-color)', padding: '8px', borderRadius: '50%' }}>
            <User size={20} color="var(--text-secondary)" />
          </div>
        </div>
      )}
    </div>
  );
}
