import React from 'react';
import { X, Star, Clock, MapPin, ShoppingBag, Utensils, Calendar, Plus, Tag, ShieldCheck } from 'lucide-react';

export default function ItemDetailModal({ item, type, onClose, onAction, onAddToCart }) {
  if (!item) return null;

  const isProduct = type === 'product';
  const isDineout = type === 'dineout';
  const isFood = type === 'food';
  const isDish = type === 'dish';

  const title = item.name || item.displayName || 'Details';
  const subtitle = item.restaurantName || item.cuisine || item.brand || item.category || (isDineout ? 'Dining & Table Reservation' : 'Swiggy');
  const rating = item.rating || item.avgRating || '4.2';
  const distance = item.distance_km ? `${item.distance_km} km` : (item.distanceKm ? `${item.distanceKm} km` : '');
  const locality = item.locality || item.area || '';
  const price = item.price || item.costForTwo || item.avg_cost_for_two || '';
  const mrp = item.mrp;
  const sla = item.sla || (isProduct ? '15-25 mins' : '30-40 mins');
  const menuHighlights = item.menu_highlights || [];

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-container" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close-btn" onClick={onClose} aria-label="Close modal">
          <X size={18} />
        </button>

        {item.imageUrl && (
          <div className="modal-image-container">
            <img 
              src={item.imageUrl} 
              alt={title} 
              className="modal-image" 
              onError={(e) => { e.target.style.display = 'none'; }} 
            />
            {item.offer && <span className="modal-badge">{item.offer}</span>}
          </div>
        )}

        <div className="modal-content">
          <div className="modal-header">
            <div>
              <h2 className="modal-title">{title}</h2>
              {subtitle && <p className="modal-subtitle">{subtitle}</p>}
            </div>
            <div className="modal-rating">
              <Star size={14} fill="#b45309" color="#b45309" />
              <span>{rating}</span>
            </div>
          </div>

          <div className="modal-meta-row">
            {distance && (
              <span className="meta-pill">
                <MapPin size={13} /> {distance}
              </span>
            )}
            {locality && (
              <span className="meta-pill">
                <MapPin size={13} /> {locality}
              </span>
            )}
            {sla && (
              <span className="meta-pill">
                <Clock size={13} /> {sla} {typeof sla === 'number' ? 'mins' : ''}
              </span>
            )}
            {item.quantity && (
              <span className="meta-pill">
                <Tag size={13} /> {item.quantity}
              </span>
            )}
            <span className="meta-pill certified">
              <ShieldCheck size={13} /> Verified Swiggy MCP
            </span>
          </div>

          {/* Pricing Row for Products & Dishes */}
          {(isProduct || isDish) && (
            <div className="modal-pricing-box">
              <div className="pricing-info">
                <span className="current-price">₹{price}</span>
                {mrp && mrp > price && (
                  <>
                    <span className="mrp-price">₹{mrp}</span>
                    <span className="discount-tag">
                      {Math.round(((mrp - price) / mrp) * 100)}% OFF
                    </span>
                  </>
                )}
              </div>
              <span className="stock-status in-stock">⚡ Fresh & Available to Order</span>
            </div>
          )}

          {item.description && (
            <div className="modal-section" style={{ marginTop: '12px' }}>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.6 }}>
                {item.description}
              </p>
            </div>
          )}

          {/* Dining Cost for Dineout */}
          {isDineout && (
            <div className="modal-pricing-box">
              <div className="pricing-info">
                <span className="current-price">{price}</span>
                <span className="mrp-price" style={{ textDecoration: 'none', color: 'var(--text-secondary)' }}>approx cost for two</span>
              </div>
              <span className="stock-status in-stock">Instant Confirmation</span>
            </div>
          )}

          {/* Menu Highlights for Food Restaurants */}
          {isFood && menuHighlights.length > 0 && (
            <div className="modal-section">
              <h3 className="section-title">Popular Items & Highlights</h3>
              <div className="popular-items-list">
                {menuHighlights.map((dish, i) => (
                  <div key={i} className="popular-item-row">
                    <span className="dish-name">{dish}</span>
                    <button
                      className="add-dish-btn"
                      onClick={() => {
                        const cleanDish = dish.replace(/\s*\(₹[0-9.]+\)/, '').trim();
                        const priceMatch = dish.match(/₹([0-9.]+)/);
                        const dishPrice = priceMatch ? parseFloat(priceMatch[1]) : 150;
                        if (onAddToCart) {
                          onAddToCart({
                            id: `highlight_${i}_${item.id}`,
                            name: cleanDish,
                            price: dishPrice,
                            is_veg: true,
                            restaurant_id: item.id,
                            restaurant_name: title
                          }, title);
                        } else {
                          onAction(`order ${cleanDish} from ${title}`);
                        }
                        onClose();
                      }}
                    >
                      <Plus size={13} /> Add to Cart
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Bottom CTA Action Buttons */}
          <div className="modal-footer">
            {isDish && (
              <button
                className="modal-primary-btn orange"
                onClick={() => {
                  if (onAddToCart) {
                    onAddToCart(item, item.restaurantName);
                  } else {
                    onAction(`order ${title}`);
                  }
                  onClose();
                }}
              >
                <Plus size={18} /> Add to Cart (₹{price})
              </button>
            )}

            {isProduct && (
              <button
                className="modal-primary-btn green"
                onClick={() => {
                  if (onAddToCart) {
                    onAddToCart({
                      id: item.id,
                      name: title,
                      price: price,
                      is_veg: true,
                      type: 'instamart'
                    }, 'Instamart Store');
                  } else {
                    onAction(`add 1 ${title}`);
                  }
                  onClose();
                }}
              >
                <ShoppingBag size={17} /> Add to Cart (₹{price})
              </button>
            )}

            {isFood && (
              <div className="btn-group">
                <button
                  className="modal-secondary-btn"
                  onClick={() => {
                    onAction(`show menu for ${title}`);
                    onClose();
                  }}
                >
                  <Utensils size={15} /> View Full Menu
                </button>
                <button
                  className="modal-primary-btn orange"
                  onClick={() => {
                    onAction(`order from ${title}`);
                    onClose();
                  }}
                >
                  <ShoppingBag size={17} /> Order Food
                </button>
              </div>
            )}

            {isDineout && (
              <button
                className="modal-primary-btn purple"
                onClick={() => {
                  onAction(`book a table at ${title} for 2 guests`);
                  onClose();
                }}
              >
                <Calendar size={17} /> Book Table (2 Guests)
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
