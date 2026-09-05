import React, { useState, useEffect, useRef } from 'react';
import StatusPanel from './components/StatusPanel';
import Message from './components/Message';
import FloatingCartBar from './components/FloatingCartBar';
import CartDrawer from './components/CartDrawer';
import OrdersDrawer from './components/OrdersDrawer';
import { Send, Terminal } from 'lucide-react';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [cart, setCart] = useState({ has_items: false, items: [], item_count: 0, final_amount: 0 });
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [isOrdersOpen, setIsOrdersOpen] = useState(false);
  const messagesListRef = useRef(null);

  useEffect(() => {
    // Check real auth status on load
    fetch('/auth/status')
      .then(res => res.json())
      .then(data => {
        setIsAuthenticated(data.authenticated);
        if (data.authenticated) {
          fetchCart();
        }
      })
      .catch(() => setIsAuthenticated(false));
  }, []);

  const fetchCart = async () => {
    try {
      const res = await fetch('/cart');
      const data = await res.json();
      setCart(data);
    } catch (err) {
      console.warn('Cart fetch error:', err);
    }
  };

  const scrollToBottom = () => {
    if (messagesListRef.current) {
      messagesListRef.current.scrollTo({
        top: messagesListRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const [activeLocation, setActiveLocation] = useState(() => {
    try {
      const saved = localStorage.getItem('swiggy_active_location');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const handleLocationChange = (newLoc) => {
    setActiveLocation(newLoc);
    try {
      localStorage.setItem('swiggy_active_location', JSON.stringify(newLoc));
    } catch (e) {
      console.warn('Storage error:', e);
    }
  };

  const handleSend = async (actionQuery) => {
    const textToSend = (typeof actionQuery === 'string' ? actionQuery : inputValue).trim();
    if (!textToSend) return;
    
    const userMsg = { role: 'user', content: textToSend };
    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);

    try {
      const context = {};
      if (activeLocation) {
        if (activeLocation.latitude) context.latitude = activeLocation.latitude;
        if (activeLocation.longitude) context.longitude = activeLocation.longitude;
        if (activeLocation.city) context.city = activeLocation.city;
        if (activeLocation.locality) context.locality = activeLocation.locality;
        if (activeLocation.addressLine) context.addressLine = activeLocation.addressLine;
        if (activeLocation.addressId) context.address_id = activeLocation.addressId;
        if (activeLocation.isLiveGps) context.is_live_gps = true;
      }

      const response = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: textToSend, context })
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        if (response.status === 401) {
          setIsAuthenticated(false);
          throw new Error('Session expired. Please re-authenticate.');
        }
        throw new Error(errorData?.error || 'Failed to send message');
      }
      
      const data = await response.json();
      
      const agentMsg = {
        role: 'agent',
        content: data.response || 'No response from Swiggy.',
        active_server: data.active_server,
        rankings: data.rankings || [],
        tool_calls: data.tool_calls || []
      };
      
      setMessages(prev => [...prev, agentMsg]);
    } catch (error) {
      console.error(error);
      const errorMsg = { role: 'agent', content: `⚠️ ${error.message || 'Sorry, there was an error processing your request.'}` };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddToCart = async (dishOrProd, restaurantName) => {
    try {
      const payload = {
        type: dishOrProd.type || (dishOrProd.brand ? 'instamart' : 'food'),
        restaurant_id: dishOrProd.restaurantId || dishOrProd.restaurant_id || 'rest_1',
        restaurant_name: restaurantName || dishOrProd.restaurantName || 'Restaurant',
        item_id: String(dishOrProd.id || dishOrProd.itemId),
        name: dishOrProd.name,
        price: dishOrProd.price || 0,
        quantity: 1,
        is_veg: dishOrProd.isVeg ?? true,
        image_url: dishOrProd.imageUrl || '',
        address_id: activeLocation?.addressId
      };
      const res = await fetch('/cart/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const updatedCart = await res.json();
        setCart(updatedCart);
      }
    } catch (err) {
      console.error('Failed to add item to cart', err);
    }
  };

  const handleUpdateQuantity = async (itemId, quantity) => {
    try {
      const res = await fetch('/cart/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_id: String(itemId),
          quantity,
          address_id: activeLocation?.addressId
        })
      });
      if (res.ok) {
        const updatedCart = await res.json();
        setCart(updatedCart);
      }
    } catch (err) {
      console.error('Failed to update cart quantity', err);
    }
  };

  const handleClearCart = async () => {
    try {
      const res = await fetch('/cart/clear', { method: 'POST' });
      if (res.ok) {
        const updatedCart = await res.json();
        setCart(updatedCart);
      }
    } catch (err) {
      console.error('Failed to clear cart', err);
    }
  };

  const handleApplyCoupon = async (code) => {
    try {
      const res = await fetch('/cart/apply-coupon', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          coupon_code: code,
          address_id: activeLocation?.addressId
        })
      });
      if (res.ok) {
        const updatedCart = await res.json();
        setCart(updatedCart);
        return updatedCart;
      }
    } catch (err) {
      console.error('Failed to apply coupon', err);
    }
  };

  const handleCheckout = async () => {
    const res = await fetch('/cart/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        address_id: activeLocation?.addressId
      })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.error || 'Failed to place order');
    }
    const orderData = await res.json();
    fetchCart();
    return orderData;
  };

  const handleReorder = async (items, merchantName) => {
    for (const item of items) {
      await handleAddToCart(item, merchantName);
    }
    setIsCartOpen(true);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (isAuthenticated === null) {
    return (
      <div className="app-container" style={{ justifyContent: 'center', alignItems: 'center' }}>
        <div className="activity-indicator">
          <div className="spinner"></div> System Initializing...
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="app-container" style={{ justifyContent: 'center', alignItems: 'center' }}>
        <div className="control-plane-card" style={{ maxWidth: '400px', textAlign: 'center' }}>
          <Terminal size={48} className="text-orange" style={{ margin: '0 auto 20px' }} />
          <h1 style={{ marginBottom: '10px' }}>Swiggy AI Control Plane</h1>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '30px' }}>
            Authentication required to access MCP orchestration layer.
          </p>
          <a 
            href="/auth/start" 
            style={{ 
              display: 'inline-block', 
              backgroundColor: 'var(--orange-primary)', 
              color: 'white', 
              padding: '12px 24px', 
              borderRadius: '6px', 
              textDecoration: 'none',
              fontWeight: 'bold'
            }}
          >
            Connect Swiggy Account
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      <StatusPanel 
        activeLocation={activeLocation} 
        onLocationChange={handleLocationChange}
        cartCount={cart?.item_count || 0}
        onOpenCart={() => setIsCartOpen(true)}
        onOpenOrders={() => setIsOrdersOpen(true)}
      />
      
      <main className="main-content">
        <div className="chat-container">
          <div className="messages-list" ref={messagesListRef}>
            {messages.length === 0 && (
              <div style={{ textAlign: 'center', marginTop: '100px', color: 'var(--text-secondary)' }}>
                <Terminal size={48} style={{ margin: '0 auto 20px', opacity: 0.5 }} />
                <p>System ready. Awaiting operational parameters.</p>
              </div>
            )}
            
            {messages.map((msg, idx) => (
              <Message 
                key={idx} 
                msg={msg} 
                isLatestAgentMsg={msg.role === 'agent' && idx === messages.length - 1} 
                onAction={handleSend}
                onAddToCart={handleAddToCart}
              />
            ))}
            
            {isLoading && (
              <div className="activity-indicator">
                <div className="spinner"></div> 
                <span className="typing-text">Processing request...</span>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Floating Bottom Cart Bar */}
      <FloatingCartBar 
        cart={cart} 
        onOpenCart={() => setIsCartOpen(true)} 
      />

      <div className="input-container">
        <div style={{ maxWidth: '900px', margin: '0 auto', width: '100%' }}>
          <div className="input-box">
            <input
              type="text"
              className="chat-input"
              placeholder="Enter request (e.g., 'Find me something spicy under ₹300')..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
            />
            <button 
              className="send-button" 
              onClick={handleSend} 
              disabled={!inputValue.trim() || isLoading}
            >
              <Send size={16} />
            </button>
          </div>
          <div style={{ textAlign: 'center', marginTop: '12px', fontSize: '11px', color: 'var(--text-secondary)' }}>
            Powered by <span style={{ fontWeight: 'bold', color: 'var(--orange-primary)' }}>Swiggy MCP</span> &bull; Developed by <span style={{ fontWeight: 'bold' }}>Ketan Chokkara</span>
          </div>
        </div>
      </div>

      {/* Sliding Cart Drawer */}
      <CartDrawer 
        isOpen={isCartOpen}
        onClose={() => setIsCartOpen(false)}
        cart={cart}
        onUpdateQuantity={handleUpdateQuantity}
        onClearCart={handleClearCart}
        onApplyCoupon={handleApplyCoupon}
        onCheckout={handleCheckout}
        onOpenOrders={() => {
          setIsCartOpen(false);
          setIsOrdersOpen(true);
        }}
      />

      {/* Sliding Orders & Live Tracking Drawer */}
      <OrdersDrawer 
        isOpen={isOrdersOpen}
        onClose={() => setIsOrdersOpen(false)}
        onReorder={handleReorder}
      />
    </div>
  );
}
