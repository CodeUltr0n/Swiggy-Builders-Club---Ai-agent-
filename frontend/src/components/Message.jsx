import React, { useState } from 'react';
import OrchestrationTimeline from './OrchestrationTimeline';
import ItemDetailModal from './ItemDetailModal';
import ReactMarkdown from 'react-markdown';
import { Bot, User, Plus, ShoppingBag, Utensils, Calendar, Info, Check, X } from 'lucide-react';

export default function Message({ msg, isLatestAgentMsg, onAction }) {
  const isAgent = msg.role === 'agent';
  const [activeModalItem, setActiveModalItem] = useState(null);
  const [modalType, setModalType] = useState('food');

  // Extract restaurants and products from tool calls to render rich cards if available
  let restaurants = [];
  let products = [];
  let isDineoutServer = msg.active_server === 'dineout';

  if (isAgent && msg.tool_calls) {
    const searchRes = msg.tool_calls.find(t => t.tool === 'search_restaurants' || t.tool === 'search_restaurants_dineout');
    if (searchRes && searchRes.result) {
      if (searchRes.tool === 'search_restaurants_dineout') {
        isDineoutServer = true;
      }
      const d = searchRes.result.data;
      const s = searchRes.result.structured;
      if (Array.isArray(d)) {
        restaurants = d;
      } else if (d && Array.isArray(d.restaurants)) {
        restaurants = d.restaurants;
      } else if (s && Array.isArray(s.restaurants)) {
        restaurants = s.restaurants;
      }
    }

    const prodRes = msg.tool_calls.find(t => t.tool === 'search_products');
    if (prodRes && prodRes.result) {
      const d = prodRes.result.data;
      const s = prodRes.result.structured;
      const rawList = Array.isArray(d) ? d : (d?.products || s?.products || []);
      if (Array.isArray(rawList)) {
        products = rawList.map(p => {
          const firstVar = Array.isArray(p.variations) && p.variations.length > 0 ? p.variations[0] : {};
          const pVal = p.price?.offerPrice || p.price?.mrp || firstVar.price?.offerPrice || firstVar.price?.mrp || p.price || 0;
          return {
            ...p,
            name: p.displayName || p.name || firstVar.displayName || 'Grocery Item',
            brand: p.brand || firstVar.brandName || '',
            price: pVal,
            mrp: p.price?.mrp || firstVar.price?.mrp || p.mrp,
            imageUrl: firstVar.imageUrl || p.imageUrl || '',
            quantity: firstVar.quantityDescription || p.quantity || '',
            sla: firstVar.sla?.value || p.sla || '20 mins'
          };
        });
      }
    }
  }

  // Detect confirmation state to show interactive [Confirm] / [Cancel] buttons
  const isConfirmPrompt = isAgent && isLatestAgentMsg && (
    msg.content.includes('(yes/no)') ||
    msg.content.includes('Reply **yes** or **no**') ||
    msg.content.includes('Confirm placing this order?') ||
    msg.content.includes('Confirm booking?')
  );

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

        {/* Quick action buttons for confirmation flows */}
        {isConfirmPrompt && (
          <div className="quick-actions-bar">
            <button 
              className="quick-action-btn confirm"
              onClick={() => onAction && onAction('yes')}
            >
              <Check size={16} /> Confirm (Yes)
            </button>
            <button 
              className="quick-action-btn cancel"
              onClick={() => onAction && onAction('no')}
            >
              <X size={16} /> Cancel (No)
            </button>
          </div>
        )}

        {/* Restaurants Carousel (Food & Dineout) */}
        {restaurants.length > 0 && (
          <div className="cards-carousel">
            {restaurants.map((rest, idx) => {
              const cuisineStr = Array.isArray(rest.cuisines) 
                ? rest.cuisines.slice(0, 3).join(', ') 
                : (rest.cuisine || rest.category || 'Restaurant');
              const rating = rest.avgRating || rest.rating || '4.2';
              const dist = rest.distanceKm ? `${rest.distanceKm} km` : (rest.distance_km ? `${rest.distance_km} km` : '');
              const cost = rest.costForTwo || rest.costForTwoMessage || rest.avg_cost_for_two || '';

              return (
                <div key={idx} className="entity-card" onClick={() => {
                  setActiveModalItem(rest);
                  setModalType(isDineoutServer ? 'dineout' : 'food');
                }}>
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

                  {/* Interactive Action Buttons on Card */}
                  <div className="card-actions-row">
                    {!isDineoutServer ? (
                      <>
                        <button 
                          className="card-btn primary orange"
                          onClick={(e) => {
                            e.stopPropagation();
                            onAction && onAction(`order from ${rest.name}`);
                          }}
                        >
                          <ShoppingBag size={13} /> Order Food
                        </button>
                        <button 
                          className="card-btn secondary"
                          onClick={(e) => {
                            e.stopPropagation();
                            onAction && onAction(`show menu for ${rest.name}`);
                          }}
                        >
                          <Utensils size={13} /> Menu
                        </button>
                      </>
                    ) : (
                      <button 
                        className="card-btn primary purple"
                        onClick={(e) => {
                          e.stopPropagation();
                          onAction && onAction(`book a table at ${rest.name} for 2 guests`);
                        }}
                      >
                        <Calendar size={13} /> Book Table
                      </button>
                    )}
                    <button 
                      className="card-btn icon-only"
                      title="View Details"
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveModalItem(rest);
                        setModalType(isDineoutServer ? 'dineout' : 'food');
                      }}
                    >
                      <Info size={14} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Instamart Products Carousel */}
        {products.length > 0 && (
          <div className="cards-carousel">
            {products.map((prod, idx) => (
              <div key={idx} className="entity-card" onClick={() => {
                setActiveModalItem(prod);
                setModalType('product');
              }}>
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
                  <span style={{ fontSize: '16px', fontWeight: 800, color: '#16a34a' }}>
                    ₹{prod.price || prod.finalPrice || '0'}
                  </span>
                  {prod.quantity && <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{prod.quantity}</span>}
                </div>

                {/* Direct Add to Cart Button */}
                <div className="card-actions-row">
                  <button 
                    className="card-btn primary green"
                    onClick={(e) => {
                      e.stopPropagation();
                      onAction && onAction(`add 1 ${prod.name}`);
                    }}
                  >
                    <Plus size={14} /> Add to Cart
                  </button>
                  <button 
                    className="card-btn icon-only"
                    title="View Details"
                    onClick={(e) => {
                      e.stopPropagation();
                      setActiveModalItem(prod);
                      setModalType('product');
                    }}
                  >
                    <Info size={14} />
                  </button>
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

      {/* Item Detail Modal */}
      {activeModalItem && (
        <ItemDetailModal 
          item={activeModalItem} 
          type={modalType} 
          onClose={() => setActiveModalItem(null)} 
          onAction={onAction} 
        />
      )}
    </div>
  );
}
