import React, { useState } from 'react';
import { 
  X, Trash2, Plus, Minus, Tag, ArrowRight, ShieldCheck, 
  Clock, MapPin, CheckCircle2, ShoppingBag, AlertCircle 
} from 'lucide-react';

export default function CartDrawer({
  isOpen,
  onClose,
  cart,
  onUpdateQuantity,
  onClearCart,
  onApplyCoupon,
  onCheckout,
  onOpenOrders,
}) {
  const [couponCode, setCouponCode] = useState('');
  const [couponMsg, setCouponMsg] = useState(null);
  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const [placedOrder, setPlacedOrder] = useState(null);

  if (!isOpen) return null;

  const items = cart?.items || [];
  const itemCount = cart?.item_count || items.length || 0;
  const itemTotal = cart?.item_total || 0;
  const deliveryFee = cart?.delivery_fee || 0;
  const taxes = cart?.taxes || 0;
  const discount = cart?.discount || 0;
  const finalAmount = cart?.final_amount || 0;
  const restaurantName = cart?.restaurant_name || (cart?.cart_type === 'instamart' ? 'Instamart Store' : 'Swiggy');

  const handleApplyCoupon = async (e) => {
    e.preventDefault();
    if (!couponCode.trim()) return;
    const res = await onApplyCoupon(couponCode.trim());
    if (res?.message) {
      setCouponMsg({ type: 'success', text: res.message });
    } else {
      setCouponMsg({ type: 'success', text: `Coupon ${couponCode.toUpperCase()} applied!` });
    }
  };

  const handleProceedCheckout = async () => {
    setIsCheckingOut(true);
    try {
      const order = await onCheckout();
      setPlacedOrder(order);
    } catch (err) {
      setCouponMsg({ type: 'error', text: err.message || 'Checkout failed. Please try again.' });
    } finally {
      setIsCheckingOut(false);
    }
  };

  return (
    <div className="modal-backdrop cart-backdrop" onClick={onClose}>
      <div className="cart-drawer" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="cart-drawer-header">
          <div className="cart-header-title-box">
            <div className="cart-header-icon">
              <ShoppingBag size={20} color="var(--orange-primary)" />
            </div>
            <div>
              <h2 className="cart-drawer-title">Your Cart</h2>
              <span className="cart-restaurant-sub">
                {restaurantName} ({itemCount} {itemCount === 1 ? 'item' : 'items'})
              </span>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close cart">
            <X size={20} />
          </button>
        </div>

        {placedOrder ? (
          /* Order Placed Success View */
          <div className="cart-success-view">
            <div className="success-icon-bubble">
              <CheckCircle2 size={54} color="#16a34a" />
            </div>
            <h3 className="success-title">Order Placed Successfully!</h3>
            <p className="success-sub">
              Your order from <strong>{placedOrder.restaurant_name || restaurantName}</strong> is confirmed via Swiggy MCP.
            </p>
            
            <div className="order-summary-card">
              <div className="order-summary-row">
                <span>Order ID</span>
                <span className="order-code">#{placedOrder.order_id}</span>
              </div>
              <div className="order-summary-row">
                <span>Total Paid (COD)</span>
                <span className="order-total-val">₹{placedOrder.total_amount || finalAmount}</span>
              </div>
              <div className="order-summary-row">
                <span>Estimated Delivery</span>
                <span className="order-eta-val">⚡ {placedOrder.eta || '25-35 mins'}</span>
              </div>
            </div>

            <div className="success-actions">
              <button 
                className="cart-checkout-btn primary"
                onClick={() => {
                  onClose();
                  onOpenOrders && onOpenOrders();
                }}
              >
                <span>Track Live Order</span>
                <ArrowRight size={18} />
              </button>
              <button className="cart-clear-btn" onClick={onClose}>
                Continue Browsing
              </button>
            </div>
          </div>
        ) : items.length === 0 ? (
          /* Empty Cart State */
          <div className="empty-cart-state">
            <div className="empty-icon-wrap">
              <ShoppingBag size={48} color="var(--text-secondary)" style={{ opacity: 0.4 }} />
            </div>
            <h3>Your cart is empty</h3>
            <p>Explore food menus or Instamart groceries and add items to your cart.</p>
            <button className="cart-browse-btn" onClick={onClose}>
              Browse Dishes & Menu
            </button>
          </div>
        ) : (
          /* Cart Items & Bill Breakdown */
          <div className="cart-drawer-body">
            {/* Delivery details header pill */}
            <div className="cart-delivery-pill">
              <Clock size={15} color="var(--orange-primary)" />
              <span>Delivery in <strong>25-35 mins</strong> to your location</span>
            </div>

            {/* Items List */}
            <div className="cart-items-scroll">
              {items.map((item, idx) => (
                <div key={item.id || idx} className="cart-item-row">
                  {/* Veg / Non-Veg Indicator */}
                  <div className={`veg-indicator ${item.is_veg ? 'veg' : 'non-veg'}`}>
                    <span className="veg-dot"></span>
                  </div>

                  <div className="cart-item-details">
                    <span className="cart-item-name">{item.name}</span>
                    <span className="cart-item-unit-price">₹{item.price}</span>
                  </div>

                  {/* Quantity Stepper */}
                  <div className="cart-qty-stepper">
                    <button 
                      className="qty-btn"
                      onClick={() => onUpdateQuantity(item.id, (item.quantity || 1) - 1)}
                      title="Decrease quantity"
                    >
                      {item.quantity === 1 ? <Trash2 size={13} color="#ef4444" /> : <Minus size={13} />}
                    </button>
                    <span className="qty-number">{item.quantity}</span>
                    <button 
                      className="qty-btn"
                      onClick={() => onUpdateQuantity(item.id, (item.quantity || 1) + 1)}
                      title="Increase quantity"
                    >
                      <Plus size={13} />
                    </button>
                  </div>

                  {/* Total item price */}
                  <div className="cart-item-total">
                    ₹{Math.round((item.price * (item.quantity || 1)) * 100) / 100}
                  </div>
                </div>
              ))}
            </div>

            {/* Coupon Box */}
            <div className="cart-coupon-section">
              <form onSubmit={handleApplyCoupon} className="coupon-input-group">
                <Tag size={16} color="var(--orange-primary)" />
                <input 
                  type="text" 
                  placeholder="Enter coupon (e.g. SWIGGY50)"
                  value={couponCode}
                  onChange={(e) => setCouponCode(e.target.value)}
                  className="coupon-input"
                />
                <button type="submit" className="coupon-apply-btn">
                  Apply
                </button>
              </form>
              {couponMsg && (
                <div className={`coupon-msg ${couponMsg.type}`}>
                  {couponMsg.text}
                </div>
              )}
              {cart?.applied_coupon && (
                <div className="active-coupon-tag">
                  <span>Coupon <strong>{cart.applied_coupon}</strong> applied (-₹{discount})</span>
                  <button 
                    className="remove-coupon-btn" 
                    onClick={() => onApplyCoupon('')}
                    title="Remove coupon"
                  >
                    <X size={12} />
                  </button>
                </div>
              )}
            </div>

            {/* Bill Details */}
            <div className="cart-bill-section">
              <h4 className="bill-title">Bill Details</h4>
              <div className="bill-row">
                <span>Item Total</span>
                <span>₹{itemTotal}</span>
              </div>
              <div className="bill-row">
                <span>Delivery Fee</span>
                <span>{deliveryFee === 0 ? <span className="free-tag">FREE</span> : `₹${deliveryFee}`}</span>
              </div>
              <div className="bill-row">
                <span>Taxes and Packing Charges</span>
                <span>₹{taxes}</span>
              </div>
              {discount > 0 && (
                <div className="bill-row discount">
                  <span>Coupon Discount</span>
                  <span>-₹{discount}</span>
                </div>
              )}
              <div className="bill-divider"></div>
              <div className="bill-row total">
                <span>TO PAY</span>
                <span className="final-total">₹{finalAmount}</span>
              </div>
            </div>

            {/* Security Guarantee */}
            <div className="cart-assurance">
              <ShieldCheck size={16} color="#16a34a" />
              <span>100% Genuine Swiggy MCP Checkout • Cash on Delivery</span>
            </div>

            {/* Drawer Footer CTA */}
            <div className="cart-drawer-footer">
              <button className="cart-clear-btn" onClick={onClearCart}>
                Clear Cart
              </button>
              <button 
                className="cart-checkout-btn" 
                onClick={handleProceedCheckout}
                disabled={isCheckingOut}
              >
                {isCheckingOut ? (
                  <span className="checkout-spinner">Placing Order...</span>
                ) : (
                  <>
                    <span>Proceed to Pay (₹{finalAmount})</span>
                    <ArrowRight size={18} />
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
