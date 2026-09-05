import React from 'react';
import { ShoppingBag, ChevronRight } from 'lucide-react';

export default function FloatingCartBar({ cart, onOpenCart }) {
  if (!cart || !cart.has_items || cart.item_count <= 0) {
    return null;
  }

  const itemCount = cart.item_count || cart.items?.length || 0;
  const amount = cart.final_amount || cart.item_total || 0;
  const restaurantName = cart.restaurant_name || (cart.cart_type === 'instamart' ? 'Instamart Store' : 'Swiggy');

  return (
    <div className="floating-cart-wrapper">
      <div className="floating-cart-bar" onClick={onOpenCart}>
        <div className="cart-bar-left">
          <div className="cart-icon-bubble">
            <ShoppingBag size={18} color="white" />
            <span className="cart-badge-count">{itemCount}</span>
          </div>
          <div className="cart-info">
            <span className="cart-count-text">
              {itemCount} {itemCount === 1 ? 'ITEM' : 'ITEMS'}
            </span>
            <span className="cart-dot-divider">•</span>
            <span className="cart-amount-text">₹{amount}</span>
            {restaurantName && (
              <span className="cart-restaurant-name">from {restaurantName}</span>
            )}
          </div>
        </div>

        <button className="cart-view-btn" onClick={(e) => { e.stopPropagation(); onOpenCart(); }}>
          <span>View Cart</span>
          <ChevronRight size={17} />
        </button>
      </div>
    </div>
  );
}
