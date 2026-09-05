import React, { useState, useEffect } from 'react';
import { 
  X, Package, Clock, CheckCircle2, Bike, Phone, MapPin, 
  RotateCcw, ChevronRight, ShieldCheck, Utensils, ShoppingBag 
} from 'lucide-react';

export default function OrdersDrawer({ isOpen, onClose, onReorder }) {
  const [ordersData, setOrdersData] = useState({ orders: [], mcp_orders: [] });
  const [activeTracking, setActiveTracking] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (isOpen) {
      fetchOrders();
    }
  }, [isOpen]);

  const fetchOrders = async () => {
    setIsLoading(true);
    try {
      const res = await fetch('/orders');
      const data = await res.json();
      setOrdersData(data);

      // If there are orders, pick the latest one for live tracking
      const all = [...(data.orders || []), ...(data.mcp_orders || [])];
      if (all.length > 0) {
        const latestId = all[0].id || all[0].order_id || all[0].orderId;
        if (latestId) {
          fetchTracking(latestId);
        }
      }
    } catch (err) {
      console.error('Failed to load orders', err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchTracking = async (orderId) => {
    try {
      const res = await fetch(`/orders/track/${orderId}`);
      const data = await res.json();
      setActiveTracking(data);
    } catch (err) {
      console.error('Failed to load tracking', err);
    }
  };

  if (!isOpen) return null;

  const allOrders = ordersData.orders || [];

  return (
    <div className="modal-backdrop cart-backdrop" onClick={onClose}>
      <div className="cart-drawer orders-drawer" onClick={(e) => e.stopPropagation()}>
        {/* Drawer Header */}
        <div className="cart-drawer-header">
          <div className="cart-header-title-box">
            <div className="cart-header-icon orange">
              <Package size={20} color="var(--orange-primary)" />
            </div>
            <div>
              <h2 className="cart-drawer-title">Live Orders & History</h2>
              <span className="cart-restaurant-sub">
                Track active deliveries in real-time
              </span>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close orders">
            <X size={20} />
          </button>
        </div>

        <div className="cart-drawer-body">
          {isLoading ? (
            <div className="activity-indicator" style={{ padding: '40px 0', textAlign: 'center' }}>
              <div className="spinner"></div>
              <span>Fetching your Swiggy orders...</span>
            </div>
          ) : allOrders.length === 0 ? (
            <div className="empty-cart-state">
              <div className="empty-icon-wrap">
                <Package size={48} color="var(--text-secondary)" style={{ opacity: 0.4 }} />
              </div>
              <h3>No past orders yet</h3>
              <p>Place your first order using Swiggy MCP to track live deliveries here.</p>
              <button className="cart-browse-btn" onClick={onClose}>
                Order Food Now
              </button>
            </div>
          ) : (
            <div className="orders-scroll-container">
              {/* Active Order Live Tracker Card */}
              {activeTracking && (
                <div className="live-tracking-card">
                  <div className="tracking-card-header">
                    <div>
                      <span className="live-pulse-badge">
                        <span className="pulse-dot"></span> LIVE TRACKING
                      </span>
                      <h3 className="tracking-order-title">
                        Order #{activeTracking.order_id}
                      </h3>
                    </div>
                    <div className="tracking-eta-box">
                      <Clock size={16} color="var(--orange-primary)" />
                      <span className="eta-text">{activeTracking.eta || '24 mins'}</span>
                    </div>
                  </div>

                  {/* 4-Step Progress Stepper */}
                  <div className="tracking-stepper">
                    {[
                      { label: 'Order Confirmed', step: 1, done: true },
                      { label: 'Food Preparing', step: 2, done: (activeTracking.step || 2) >= 2, active: (activeTracking.step || 2) === 2 },
                      { label: 'Out for Delivery', step: 3, done: (activeTracking.step || 2) >= 3, active: (activeTracking.step || 2) === 3 },
                      { label: 'Delivered', step: 4, done: (activeTracking.step || 2) >= 4 }
                    ].map((st, i) => (
                      <div key={i} className={`step-item ${st.done ? 'completed' : ''} ${st.active ? 'current' : ''}`}>
                        <div className="step-circle">
                          {st.done && !st.active ? <CheckCircle2 size={14} /> : st.step}
                        </div>
                        <span className="step-label">{st.label}</span>
                      </div>
                    ))}
                  </div>

                  {/* Delivery Partner Details */}
                  {activeTracking.delivery_partner && (
                    <div className="rider-card">
                      <div className="rider-avatar">
                        <Bike size={20} color="white" />
                      </div>
                      <div className="rider-info">
                        <div className="rider-name">
                          {activeTracking.delivery_partner.name}
                          <span className="rider-rating">{activeTracking.delivery_partner.rating}</span>
                        </div>
                        <div className="rider-vehicle">
                          {activeTracking.delivery_partner.vehicle} &bull; Delivery Partner
                        </div>
                      </div>
                      <a 
                        href={`tel:${activeTracking.delivery_partner.phone}`} 
                        className="rider-call-btn" 
                        title="Call delivery partner"
                      >
                        <Phone size={15} />
                      </a>
                    </div>
                  )}
                </div>
              )}

              {/* Order History Section */}
              <div className="past-orders-section">
                <h4 className="orders-section-heading">Recent Orders ({allOrders.length})</h4>
                
                {allOrders.map((ord, idx) => {
                  const items = ord.items || [];
                  return (
                    <div key={ord.id || idx} className="past-order-card">
                      <div className="past-order-header">
                        <div>
                          <span className="past-order-merchant">{ord.merchant_name || 'Swiggy Food'}</span>
                          <span className="past-order-time">{ord.timestamp || 'Recent'}</span>
                        </div>
                        <span className="order-status-pill">{ord.status || 'PLACED'}</span>
                      </div>

                      <div className="past-order-items">
                        {items.map((it, i) => (
                          <div key={i} className="past-item-line">
                            <span>{it.quantity || 1}x {it.name || 'Item'}</span>
                            <span>₹{it.price || it.total_price || 0}</span>
                          </div>
                        ))}
                      </div>

                      <div className="past-order-footer">
                        <div className="past-order-total">
                          <span>Total Amount</span>
                          <strong>₹{ord.total_amount || 0}</strong>
                        </div>

                        <button 
                          className="reorder-btn"
                          onClick={() => {
                            if (onReorder) {
                              onReorder(items, ord.merchant_name);
                            }
                            onClose();
                          }}
                        >
                          <RotateCcw size={13} />
                          <span>Reorder</span>
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
