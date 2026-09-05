import React, { useState } from 'react';
import OrchestrationTimeline from './OrchestrationTimeline';
import ItemDetailModal from './ItemDetailModal';
import ReactMarkdown from 'react-markdown';
import { Bot, User, Plus, ShoppingBag, Utensils, Calendar, Info, Check, X } from 'lucide-react';

export const FALLBACK_FOOD_IMG = 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=660&auto=format&fit=crop&q=80';
export const FALLBACK_REST_IMG = 'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=660&auto=format&fit=crop&q=80';
export const FALLBACK_GROCERY_IMG = 'https://images.unsplash.com/photo-1542838132-92c53300491e?w=660&auto=format&fit=crop&q=80';

export default function Message({ msg, isLatestAgentMsg, onAction, onAddToCart }) {
  const isAgent = msg.role === 'agent';
  const [activeModalItem, setActiveModalItem] = useState(null);
  const [modalType, setModalType] = useState('food');

  // Extract restaurants, dishes, and products from tool calls to render rich cards if available
  let restaurants = [];
  let dishes = [];
  let products = [];
  let isDineoutServer = msg.active_server === 'dineout';

  if (isAgent && msg.tool_calls) {
    // 1. Extract Dishes
    const dishTool = msg.tool_calls.find(t => t.tool === 'restaurant_menu_dishes');
    if (dishTool && dishTool.result?.data?.dishes) {
      dishes = dishTool.result.data.dishes;
    }

    // 2. Extract Restaurants (search across all matching tool calls)
    const restaurantTools = msg.tool_calls.filter(t => t.tool === 'search_restaurants' || t.tool === 'search_restaurants_dineout');
    for (const searchRes of restaurantTools) {
      if (!searchRes?.result) continue;
      if (searchRes.tool === 'search_restaurants_dineout') {
        isDineoutServer = true;
      }
      let d = searchRes.result.data;
      if (typeof d === 'string') {
        try { d = JSON.parse(d); } catch (e) {}
      }
      const s = searchRes.result.structured;
      let foundRests = [];
      if (Array.isArray(d)) {
        foundRests = d;
      } else if (d && Array.isArray(d.restaurants)) {
        foundRests = d.restaurants;
        if (!dishes.length && Array.isArray(d.dishes)) {
          dishes = d.dishes;
        }
      } else if (s && Array.isArray(s.restaurants)) {
        foundRests = s.restaurants;
        if (!dishes.length && Array.isArray(s.dishes)) {
          dishes = s.dishes;
        }
      }
      if (foundRests.length > 0) {
        restaurants = foundRests;
        break;
      }
    }

    // 3. Extract Instamart Products
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

  // Segmented Tab Management: strictly ONE card section at a time fulfilling MCP Orchestration Motto
  const hasDishes = dishes.length > 0;
  const hasRestaurants = restaurants.length > 0;
  const hasProducts = products.length > 0;
  const hasAnyCards = hasDishes || hasRestaurants || hasProducts;

  // Default priority: Dishes > Restaurants > Products (unless dineout, then Restaurants)
  const defaultTab = isDineoutServer && hasRestaurants ? 'restaurants' : (hasDishes ? 'dishes' : (hasRestaurants ? 'restaurants' : 'products'));
  const [activeTab, setActiveTab] = useState(defaultTab);
  const [selectedRestFilter, setSelectedRestFilter] = useState(null);

  // Resolved current tab ensuring we don't display an empty tab
  let currentTab = activeTab;
  if (currentTab === 'dishes' && !hasDishes) {
    currentTab = hasRestaurants ? 'restaurants' : (hasProducts ? 'products' : null);
  } else if (currentTab === 'restaurants' && !hasRestaurants) {
    currentTab = hasDishes ? 'dishes' : (hasProducts ? 'products' : null);
  } else if (currentTab === 'products' && !hasProducts) {
    currentTab = hasDishes ? 'dishes' : (hasRestaurants ? 'restaurants' : null);
  }

  // Extract unique restaurant names from dishes for filter pills
  const dishRestaurantNames = Array.from(
    new Set(dishes.map(d => d.restaurantName).filter(Boolean))
  );

  // Filtered dishes based on restaurant selection
  const displayedDishes = selectedRestFilter 
    ? dishes.filter(d => d.restaurantName === selectedRestFilter)
    : dishes;

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

        {/* Single Unified Interactive Card Deck (Fulfilling MCP Orchestration Motto) */}
        {hasAnyCards && (
          <div className="unified-card-deck">
            {/* Tab Header if multiple entity types exist */}
            {( (hasDishes && hasRestaurants) || (hasDishes && hasProducts) || (hasRestaurants && hasProducts) ) && (
              <div className="deck-header-bar">
                <div className="deck-tabs-pills">
                  {hasDishes && (
                    <button 
                      className={`deck-tab-pill ${currentTab === 'dishes' ? 'active' : ''}`}
                      onClick={() => setActiveTab('dishes')}
                    >
                      <Utensils size={13} />
                      <span>Dishes ({dishes.length})</span>
                    </button>
                  )}
                  {hasRestaurants && (
                    <button 
                      className={`deck-tab-pill ${currentTab === 'restaurants' ? 'active' : ''}`}
                      onClick={() => setActiveTab('restaurants')}
                    >
                      <ShoppingBag size={13} />
                      <span>Restaurants ({restaurants.length})</span>
                    </button>
                  )}
                  {hasProducts && (
                    <button 
                      className={`deck-tab-pill ${currentTab === 'products' ? 'active' : ''}`}
                      onClick={() => setActiveTab('products')}
                    >
                      <span>Instamart ({products.length})</span>
                    </button>
                  )}
                </div>

                <span className="deck-subtitle-hint">
                  {currentTab === 'dishes' && 'Real Swiggy Menu • Instant Add to Cart'}
                  {currentTab === 'restaurants' && (isDineoutServer ? 'Reserve Tables' : 'Delivering Near You')}
                  {currentTab === 'products' && 'Instant Grocery Delivery'}
                </span>
              </div>
            )}

            {/* Restaurant Filter Chips when viewing dishes from multiple restaurants */}
            {currentTab === 'dishes' && dishRestaurantNames.length > 1 && (
              <div className="deck-filter-row">
                <span className="deck-filter-label">Filter:</span>
                <div className="deck-filter-chips">
                  <button 
                    className={`filter-chip ${selectedRestFilter === null ? 'active' : ''}`}
                    onClick={() => setSelectedRestFilter(null)}
                  >
                    All ({dishes.length})
                  </button>
                  {dishRestaurantNames.map(rName => (
                    <button 
                      key={rName}
                      className={`filter-chip ${selectedRestFilter === rName ? 'active' : ''}`}
                      onClick={() => setSelectedRestFilter(selectedRestFilter === rName ? null : rName)}
                    >
                      {rName}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Tab 1: Dishes Carousel */}
            {currentTab === 'dishes' && displayedDishes.length > 0 && (
              <div className="cards-carousel dishes-carousel">
                {displayedDishes.map((dish, idx) => (
                  <div 
                    key={dish.id || idx} 
                    className="dish-card"
                    onClick={() => {
                      setActiveModalItem(dish);
                      setModalType('dish');
                    }}
                  >
                    <div className="dish-card-image-wrap">
                      <img 
                        src={dish.imageUrl || FALLBACK_FOOD_IMG} 
                        alt={dish.name} 
                        className="dish-card-img"
                        onError={(e) => { 
                          e.target.onerror = null;
                          e.target.src = FALLBACK_FOOD_IMG;
                        }}
                      />
                      {dish.isBestseller && <span className="dish-bestseller-tag">⭐ Bestseller</span>}
                    </div>

                    <div className="dish-card-body">
                      <div className="dish-veg-row">
                        <div className={`veg-indicator ${dish.isVeg ? 'veg' : 'non-veg'}`}>
                          <span className="veg-dot"></span>
                        </div>
                        {dish.rating && (
                          <span className="dish-rating-badge">★ {dish.rating}</span>
                        )}
                      </div>

                      <h4 className="dish-title">{dish.name}</h4>
                      {dish.restaurantName && (
                        <span className="dish-rest-sub">{dish.restaurantName}</span>
                      )}

                      <div className="dish-bottom-row">
                        <span className="dish-price">₹{dish.price}</span>
                        <button 
                          className="dish-add-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (onAddToCart) {
                              onAddToCart(dish, dish.restaurantName);
                            } else {
                              onAction && onAction(`add 1 ${dish.name}`);
                            }
                          }}
                        >
                          <Plus size={14} />
                          <span>ADD</span>
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Tab 2: Restaurants Carousel */}
            {currentTab === 'restaurants' && restaurants.length > 0 && (
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
                      <img 
                        src={rest.imageUrl || (isDineoutServer ? FALLBACK_REST_IMG : FALLBACK_FOOD_IMG)} 
                        alt={rest.name} 
                        className="card-image"
                        onError={(e) => { 
                          e.target.onerror = null;
                          e.target.src = isDineoutServer ? FALLBACK_REST_IMG : FALLBACK_FOOD_IMG;
                        }} 
                      />
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
                                if (hasDishes) {
                                  setSelectedRestFilter(rest.name);
                                  setActiveTab('dishes');
                                } else {
                                  onAction && onAction(`show menu for ${rest.name}`);
                                }
                              }}
                            >
                              <Utensils size={13} /> {hasDishes ? 'View Dishes' : 'Menu'}
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

            {/* Tab 3: Instamart Products Carousel */}
            {currentTab === 'products' && products.length > 0 && (
              <div className="cards-carousel">
                {products.map((prod, idx) => (
                  <div key={idx} className="entity-card" onClick={() => {
                    setActiveModalItem(prod);
                    setModalType('product');
                  }}>
                      <img 
                        src={prod.imageUrl || FALLBACK_GROCERY_IMG} 
                        alt={prod.name} 
                        className="card-image"
                        onError={(e) => { 
                          e.target.onerror = null;
                          e.target.src = FALLBACK_GROCERY_IMG;
                        }} 
                      />
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
                          if (onAddToCart) {
                            onAddToCart({
                              id: prod.id || `im_${idx}`,
                              name: prod.name,
                              price: prod.price || prod.finalPrice || 0,
                              imageUrl: prod.imageUrl,
                              isVeg: true,
                              type: 'instamart'
                            }, 'Instamart Store');
                          } else {
                            onAction && onAction(`add 1 ${prod.name}`);
                          }
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
          onAddToCart={onAddToCart}
        />
      )}
    </div>
  );
}
