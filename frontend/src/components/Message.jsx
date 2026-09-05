import React from 'react';
import OrchestrationTimeline from './OrchestrationTimeline';
import ReactMarkdown from 'react-markdown';
import { Bot, User } from 'lucide-react';

export default function Message({ msg, isLatestAgentMsg }) {
  const isAgent = msg.role === 'agent';

  // Extract restaurants and products from tool calls to render rich cards if available
  let restaurants = [];
  let products = [];
  if (isAgent && msg.tool_calls) {
    const searchRes = msg.tool_calls.find(t => t.tool === 'search_restaurants' || t.tool === 'search_restaurants_dineout');
    if (searchRes && searchRes.result && searchRes.result.data) {
      const d = searchRes.result.data;
      if (Array.isArray(d.restaurants)) {
        restaurants = d.restaurants;
      }
    }

    const prodRes = msg.tool_calls.find(t => t.tool === 'search_products');
    if (prodRes && prodRes.result && prodRes.result.data) {
      const d = prodRes.result.data;
      if (Array.isArray(d.products)) {
        products = d.products;
      }
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
            {restaurants.map((rest, idx) => {
              const cuisineStr = Array.isArray(rest.cuisines) 
                ? rest.cuisines.slice(0, 3).join(', ') 
                : (rest.cuisine || rest.category || 'Restaurant');
              const rating = rest.avgRating || rest.rating || '4.2';
              const dist = rest.distanceKm ? `${rest.distanceKm} km` : (rest.distance_km ? `${rest.distance_km} km` : '');
              const cost = rest.costForTwo || rest.costForTwoMessage || '';

              return (
                <div key={idx} className="entity-card">
                  {rest.imageUrl && (
                    <img 
                      src={rest.imageUrl} 
                      alt={rest.name} 
                      className="card-image"
                      onError={(e) => { e.target.style.display = 'none'; }} 
                    />
                  )}
                  {rest.offer && <div className="card-badge">{rest.offer}</div>}
                  <div className="card-title">{rest.name}</div>
                  <div className="card-subtitle">{cuisineStr}</div>
                  <div className="card-meta">
                    <span className="card-rating">★ {rating}</span>
                    {dist && <span>{dist}</span>}
                    {cost && <span style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>{cost}</span>}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {products.length > 0 && (
          <div className="cards-carousel">
            {products.map((prod, idx) => (
              <div key={idx} className="entity-card">
                {prod.imageUrl && (
                  <img 
                    src={prod.imageUrl} 
                    alt={prod.name} 
                    className="card-image"
                    onError={(e) => { e.target.style.display = 'none'; }} 
                  />
                )}
                <div className="card-title" style={{ fontSize: '15px' }}>{prod.name}</div>
                <div className="card-subtitle">{prod.brand || prod.category || prod.weight || 'Grocery'}</div>
                <div className="card-meta">
                  <span style={{ fontSize: '16px', fontWeight: 800, color: 'var(--orange-primary)' }}>
                    ₹{prod.price || prod.finalPrice || '0'}
                  </span>
                  {prod.quantity && <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{prod.quantity}</span>}
                </div>
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
